# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grammm GmbH

import shutil
import traceback

from base64 import b64decode, b64encode
from flask import jsonify, request

import api
from api.core import API, secure
from api.security import checkPermissions

from tools import ldap
from tools.config import Config
from tools.constants import ExmdbCodes
from tools.DataModel import InvalidAttributeError, MismatchROError
from tools.permissions import SystemAdminPermission, DomainAdminPermission
from tools.pyexmdb import pyexmdb
from tools.storage import UserSetup

from orm import DB
if DB is not None:
    from orm.domains import Domains
    from orm.users import Users
    import orm.roles


@API.route(api.BaseRoute+"/ldap/search", methods=["GET"])
@secure(requireDB=True, authLevel="user")
def searchLdap():
    checkPermissions(DomainAdminPermission("*"))
    if not ldap.LDAP_available:
        return jsonify(message="LDAP is not available"), 503
    if "query" not in request.args or len(request.args["query"]) < 3:
        return jsonify(message="Missing or too short query"), 400
    permissions = request.auth["user"].permissions()
    if SystemAdminPermission() in permissions:
        domainFilters = ()
    else:
        domainIDs = {permission.domainID for permission in permissions if isinstance(permission, DomainAdminPermission)}
        if len(domainIDs) == 0:
            return jsonify(data=[])
        domainFilters = () if "*" in domainIDs else (Domains.ID.in_(domainIDs),)
    domainNames = [d[0] for d in Domains.query.filter(*domainFilters).with_entities(Domains.domainname).all()]\
        if len(domainFilters) else None
    ldapusers = ldap.searchUsers(request.args["query"], domainNames)
    return jsonify(data=[{"ID": b64encode(u.ID, b".-").decode("ascii"), "name": u.name, "email": u.email} for u in ldapusers])


@API.route(api.BaseRoute+"/ldap/downsync", methods=["POST"])
@secure(requireDB=True, authLevel="user")
def ldapDownsyncAll():
    checkPermissions(DomainAdminPermission("*"))
    if not ldap.LDAP_available:
        return jsonify(message="LDAP is not available"), 503
    permissions = request.auth["user"].permissions()
    if SystemAdminPermission() in permissions:
        domainFilters = ()
    else:
        domainIDs = {permission.domainID for permission in permissions if isinstance(permission, DomainAdminPermission)}
        if len(domainIDs) == 0:
            return jsonify(data=[])
        domainFilters = () if "*" in domainIDs else (Domains.ID.in_(domainIDs),)
    users = Users.optimized_query(2).filter(Users.externID != None, *domainFilters).all()
    syncStatus = []
    for user in users:
        userdata = ldap.downsyncUser(user.externID)
        if userdata is None:
            syncStatus.append({"ID": user.ID, "username": user.username, "code": 404, "message": "LDAP object not found"})
            continue
        try:
            user.fromdict(userdata)
            syncStatus.append({"ID": user.ID, "username": user.username, "code": 200, "message": "Synchronization successful"})
            DB.session.commit()
        except (MismatchROError, InvalidAttributeError, ValueError):
            API.logger.error(traceback.format_exc())
            syncStatus.append({"ID": user.ID, "username": user.username, "code": 500, "message": "Synchronization error"})
            DB.session.rollback()
        except BaseException as err:
            API.logger.error(traceback.format_exc())
            syncStatus.append({"ID": user.ID, "username": user.username, "code": 503, "message": "Database error"})
            DB.session.rollback()
    return jsonify(data=syncStatus)


@API.route(api.BaseRoute+"/ldap/importUser", methods=["POST"])
@secure(requireDB=True, authLevel="user")
def downloadLdapUser():
    checkPermissions(DomainAdminPermission("*"))
    if not ldap.LDAP_available:
        return jsonify(message="LDAP is not available"), 503
    if "ID" not in request.args:
        return jsonify(message="Missing ID"), 400
    try:
        ID = b64decode(request.args["ID"], b".-")
    except BaseException as err:
        API.logger.error(request.args["ID"]+": "+err.args[0])
        return jsonify(message="Invalid ID"), 400
    force = request.args.get("force")
    userinfo = ldap.getUserInfo(ID)
    if userinfo.email is None:
        return jsonify(message="User not found"), 404
    domain = Domains.query.filter(Domains.domainname == userinfo.email.split("@")[1]).with_entities(Domains.ID).first()
    if domain is None:
        return jsonify(message="Cannot import user: Domain not found"), 400
    if not DomainAdminPermission(domain.ID) in request.auth["user"].permissions():
        return jsonify(message="User not found"), 404
    user = Users.query.filter(Users.externID == ID).first() or\
           Users.query.filter(Users.username == userinfo.email).first()
    if user is not None:
        if user.externID != ID and not force == "true":
            return jsonify(message="Cannot import user: User exists "+
                           ("locally" if user.externID is None else "and is associated with another LDAP object")), 409
        checkPermissions(DomainAdminPermission(user.domainID))
        userdata = ldap.downsyncUser(ID, user.propmap)
        try:
            user.fromdict(userdata)
            user.externID = ID
            DB.session.commit()
            return jsonify(user.fulldesc()), 200
        except (InvalidAttributeError, MismatchROError, ValueError) as err:
            DB.session.rollback()
            return jsonify(message=err.args[0]), 500
    userdata = ldap.downsyncUser(ID)
    error = Users.checkCreateParams(userdata)
    if error is not None:
        return jsonify(message="Cannot import user: "+error), 400
    user = Users(userdata)
    user.externID = ID
    checkPermissions(DomainAdminPermission(user.domainID))
    DB.session.add(user)
    DB.session.flush()
    with UserSetup(user) as us:
        us.run()
    if not us.success:
        return jsonify(message="Error during user setup", error=us.error), us.errorCode
    DB.session.commit()
    return jsonify(user.fulldesc()), 201


@API.route(api.BaseRoute+"/domains/<int:domainID>/users/<int:userID>/downsync", methods=["PUT"])
@secure(requireDB=True, authLevel="user")
def updateLdapUser(domainID, userID):
    checkPermissions(DomainAdminPermission(domainID))
    if not ldap.LDAP_available:
        return jsonify(message="LDAP is not available"), 503
    user = Users.query.filter(Users.ID == userID, Users.domainID == domainID).first()
    if user is None:
        return jsonify(message="User not found"), 404
    ldapID = b64decode(request.args["ID"], ".-") if "ID" in request.args else user.externID
    if ldapID is None:
        return jsonify(message="Cannot synchronize user: Could not determine LDAP object"), 400
    userdata = ldap.downsyncUser(ldapID, user.propmap)
    if userdata is None:
        return jsonify(message="Cannot synchronize user: LDAP object not found"), 404
    user.fromdict(userdata)
    user.externID = ldapID
    DB.session.commit()
    return jsonify(user.fulldesc())


@API.route(api.BaseRoute+"/ldap/check", methods=["GET", "DELETE"])
@secure(requireDB=True, authLevel="user")
def checkLdapUsers():
    checkPermissions(DomainAdminPermission("*"))
    if not ldap.LDAP_available:
        return jsonify(message="LDAP is not available"), 503
    permissions = request.auth["user"].permissions()
    if SystemAdminPermission in permissions:
        domainFilter = ()
    else:
        domainIDs = {permission.domainID for permission in permissions if isinstance(permission, DomainAdminPermission)}
        domainFilter = (Users.domainID == domainID for domainID in domainIDs)
    users = Users.query.filter(Users.externID != None, *domainFilter)\
                       .with_entities(Users.ID, Users.username, Users.externID, Users.maildir)\
                       .all()
    if len(users) == 0:
        return jsonify(message="No LDAP users found", **{"orphaned" if request.method == "GET" else "deleted": []})
    orphaned = [user for user in users if ldap.getUserInfo(user.externID) is None]
    if len(orphaned) == 0:
        return jsonify(message="All LDAP users are valid", **{"orphaned" if request.method == "GET" else "deleted": []})
    orphanedData = [{"ID": user.ID, "username": user.username} for user in orphaned]
    if request.method == "GET":
        return jsonify(orphaned=orphanedData)
    deleteMaildirs = request.args.get("deleteFiles") == "true"
    try:
        options = Config["options"]
        client = pyexmdb.ExmdbQueries(options["exmdbHost"], options["exmdbPort"], options["domainPrefix"], True)
        for user in orphaned:
            client.unloadStore(user.maildir)
    except pyexmdb.ExmdbError as err:
        API.logger.error("Could not unload exmdb store: "+ExmdbCodes.lookup(err.code, hex(err.code)))
    except RuntimeError as err:
        API.logger.error("Could not unload exmdb store: "+err.args[0])
    if deleteMaildirs:
        for user in orphaned:
            shutil.rmtree(user.maildir, ignore_errors=True)
    Users.query.filter(Users.ID.in_(user.ID for user in orphaned)).delete(synchronize_session=False)
    DB.session.commit()
    return jsonify(deleted=orphanedData)
