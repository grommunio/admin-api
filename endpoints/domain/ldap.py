# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2022 grommunio GmbH

import shutil

from flask import jsonify, request

import api
from api.core import API, secure
from api.security import checkPermissions

from services import Service, ServiceUnavailableError
from tools.DataModel import InvalidAttributeError, MismatchROError
from tools.permissions import SystemAdminPermission, SystemAdminROPermission, DomainAdminPermission, DomainAdminROPermission
from tools.permissions import OrgAdminPermission
from tools.tasq import TasQServer

from orm import DB


def _getTarget():
    """Get LDAP target organization and domains

    Returns
    -------
    int
        Organization ID or None if not found
    list
        List of domain objects containing ID and domainname
    """
    from orm.domains import Domains
    if "domain" in request.args:
        domainID = int(request.args["domain"])
        checkPermissions(DomainAdminROPermission(domainID))
        domain = Domains.query.filter(Domains.ID == domainID)\
                        .with_entities(Domains.ID, Domains.orgID, Domains.domainname).first()
        return (domain.orgID, [domain]) if domain else (None, [])
    elif "organization" in request.args:
        orgID = int(request.args["organization"])
        checkPermissions(OrgAdminPermission(orgID))
        domains = Domains.query.filter(Domains.orgID == orgID).with_entities(Domains.ID, Domains.domainname).all()
        return orgID, domains
    return None, []


@API.route(api.BaseRoute+"/domains/ldap/search", methods=["GET"])
@secure(requireDB=True, authLevel="user")
def searchLdap():
    if "domain" in request.args:
        checkPermissions(DomainAdminROPermission(int(request.args["domain"])))
    elif "organization" in request.args:
        checkPermissions(OrgAdminPermission(int(request.args["organization"])))
    orgID, domains = _getTarget()
    if len(domains) == 0:
        return jsonify(message="Invalid domain or organization"), 400
    limit = int(request.args.get("limit", 50))
    domainnames = [domain.domainname for domain in domains]
    with Service("ldap", orgID) as ldap:
        ldapusers = ldap.searchUsers(request.args["query"], domainnames, limit=limit or None)
    return jsonify(data=[{"ID": ldap.escape_filter_chars(u.ID), "name": u.name, "email": u.email} for u in ldapusers])


def ldapDownsync(orgID=None, domainID=None):
    params = {"domainID": domainID} if domainID else {"orgID": orgID} if orgID is not None else {}
    params["lang"] = request.args.get("lang", "")
    params["import"] = request.args.get("import") == "true"
    permission = DomainAdminROPermission(domainID) if domainID else \
        OrgAdminPermission(orgID) if orgID else SystemAdminROPermission()
    task = TasQServer.create("ldapSync", params, permission)
    timeout = float(request.args.get("timeout", 1))
    if timeout > 0:
        TasQServer.wait(task.ID, timeout)
    if not task.done:
        return jsonify(message="Created background task #"+str(task.ID), taskID=task.ID), 202
    if task.state == task.COMPLETED:
        return jsonify(message=task.message, data=task.params.get("result", []))
    return jsonify(message="Synchronization failed: "+task.message), 500


@API.route(api.BaseRoute+"/domains/ldap/downsync", methods=["POST"])
@secure(requireDB=True, authLevel="user")
def ldapDownsyncAll():
    checkPermissions(SystemAdminPermission())
    return ldapDownsync()


@API.route(api.BaseRoute+"/domains/<int:domainID>/ldap/downsync", methods=["POST"])
@secure(requireDB=True, authLevel="user")
def ldapDownsyncDomain(domainID):
    checkPermissions(DomainAdminPermission(domainID))
    return ldapDownsync(domainID=domainID)


@API.route(api.BaseRoute+"/domains/ldap/importUser", methods=["POST"])
@secure(requireDB=True, authLevel="user")
def importLdapUser():
    checkPermissions(DomainAdminPermission("*"))
    from services.ldap import LdapService
    from orm.domains import Domains
    from orm.users import Users
    orgID, _ = _getTarget()
    ldap = Service("ldap", orgID).service()

    if "ID" not in request.args:
        return jsonify(message="Missing ID"), 400
    try:
        ID = LdapService.unescapeFilterChars(request.args["ID"])
    except Exception:
        return jsonify(message="Invalid ID"), 400

    force = request.args.get("force")
    lang = request.args.get("lang", "")
    userinfo = ldap.getUserInfo(ID)
    if userinfo is None:
        return jsonify(message="LDAP user not found"), 404

    domain = Domains.query.filter(Domains.domainname == userinfo.email.split("@")[1], Domains.orgID == orgID)\
                          .with_entities(Domains.ID).first()
    if domain is None:
        return jsonify(message="Cannot import user: Domain not found"), 400
    checkPermissions(DomainAdminPermission(domain.ID))
    user = Users.query.filter(Users.externID == ID).first() or\
           Users.query.filter(Users.username == userinfo.email).first()
    if user is not None:
        if user.externID != ID and not force == "true":
            return jsonify(message="Cannot import user: User exists " +
                           ("locally" if user.externID is None else "and is associated with another LDAP object")), 409
        userdata = ldap.downsyncUser(ID, user.properties)
        try:
            user.fromdict(userdata)
            try:
                user.syncStore()
            except Exception:
                pass
            user.externID = ID
            DB.session.commit()
            return jsonify(user.fulldesc()), 200
        except (InvalidAttributeError, MismatchROError, ValueError) as err:
            DB.session.rollback()
            return jsonify(message=err.args[0]), 500

    from orm.misc import DBConf
    from tools.misc import RecursiveDict
    defaults = RecursiveDict({"user": {}, "domain": {}})
    defaults.update(DBConf.getFile("grommunio-admin", "defaults-system", True))
    defaults.update(DBConf.getFile("grommunio-admin", "defaults-domain-"+str(domain.ID)))
    defaults = defaults.get("user", {})

    userdata = ldap.downsyncUser(ID)
    if userdata is None:
        return jsonify(message="Error retrieving user"), 404
    defaults.update(RecursiveDict(userdata))
    defaults["lang"] = lang
    result, code = Users.create(defaults, externID=ID)
    if code != 201:
        return jsonify(message="Failed to create user: "+result), code
    DB.session.add(result)
    DB.session.commit()
    return jsonify(result.fulldesc()), 201


@API.route(api.BaseRoute+"/domains/<int:domainID>/users/<int:userID>/downsync", methods=["PUT"])
@secure(requireDB=True, authLevel="user")
def updateLdapUser(domainID, userID):
    checkPermissions(DomainAdminPermission(domainID))
    from orm.users import Users
    user = Users.query.filter(Users.ID == userID, Users.domainID == domainID).first()
    if user is None:
        return jsonify(message="User not found"), 404
    with Service("ldap", user.orgID) as ldap:
        ldapID = ldap.unescapeFilterChars(request.args["ID"]) if "ID" in request.args else user.externID
        if ldapID is None:
            return jsonify(message="Cannot synchronize user: Could not determine LDAP object"), 400
        userdata = ldap.downsyncUser(ldapID, dict(user.properties.items()))
        if userdata is None:
            return jsonify(message="Cannot synchronize user: LDAP object not found"), 404
        user.fromdict(userdata)
        user.externID = ldapID
        user.lang = user.lang or request.args.get("lang", "")
        DB.session.commit()
        return jsonify(user.fulldesc())


@API.route(api.BaseRoute+"/domains/ldap/check", methods=["GET", "DELETE"])
@secure(requireDB=True, authLevel="user")
def checkLdapUsers():
    from orm.users import Users
    orgID, domains = _getTarget()
    readonly = request.method == "GET"
    if orgID is not None:
        Permission = DomainAdminROPermission if readonly else DomainAdminPermission
        for domain in domains:
            checkPermissions(Permission(domain.ID))
        domainFilter = (Users.domainID.in_(domain.ID for domain in domains),)
    else:
        checkPermissions(SystemAdminROPermission() if readonly else SystemAdminPermission())
        domainFilter = ()
    users = Users.query.filter(Users.externID != None, *domainFilter)\
                       .with_entities(Users.ID, Users.username, Users.externID, Users.maildir, Users.orgID)\
                       .all()
    if len(users) == 0:
        return jsonify(message="No LDAP users found", **{"orphaned" if request.method == "GET" else "deleted": []})
    orphaned = []
    for user in users:
        with Service("ldap", user.orgID) as ldap:
            if ldap.getUserInfo(user.externID) is None:
                orphaned.append(user)
    if len(orphaned) == 0:
        return jsonify(message="All LDAP users are valid", **{"orphaned" if request.method == "GET" else "deleted": []})
    orphanedData = [{"ID": user.ID, "username": user.username} for user in orphaned]
    if request.method == "GET":
        return jsonify(orphaned=orphanedData)
    deleteMaildirs = request.args.get("deleteFiles") == "true"
    homeserver = None
    users = Users.query.filter(Users.ID.in_(orphan.ID for orphan in orphaned)).order_by(Users.homeserverID).all()
    index = 0
    while index < len(users):
        try:
            with Service("exmdb") as exmdb:
                if homeserver != users[index].homeserverID:  # Reuse the exmdb client for users on the same server
                    user = users[index]
                    client = exmdb.ExmdbQueries(exmdb.host if user.homeserverID == 0 else user.homeserver.hostname,
                                                exmdb.port, user.maildir, True)
                    homeserver = user.homeserverID
                while index < len(users) and users[index].homeserverID == homeserver:
                    client.unloadStore(users[index].maildir)
                    if deleteMaildirs:
                        shutil.rmtree(users[index].maildir, ignore_errors=True)
                    users[index].delete()
                    index += 1
        except ServiceUnavailableError:
            API.logger.warning("Failed to unload store: exmdb service not available")
            index += 1
    DB.session.commit()
    return jsonify(deleted=orphanedData)


@API.route(api.BaseRoute+"/domains/ldap/dump", methods=["GET"])
@secure(requireDB=True, authLevel="user")
def dumpLdapUsers():
    orgID, domains = _getTarget()
    permissions = request.auth["user"].permissions()
    if not any(DomainAdminROPermission(domain.ID) in permissions for domain in domains):
        return jsonify(message="Insufficient permissions"), 403
    try:
        with Service("ldap", orgID) as ldap:
            ID = ldap.unescapeFilterChars(request.args["ID"])
    except Exception:
        return jsonify(message="Invalid ID"), 400
    ldapuser = ldap.dumpUser(ID)
    if ldapuser is None:
        return jsonify(message="User not found"), 404
    return jsonify(data=str(ldapuser))


@API.route(api.BaseRoute+"/system/orgs/<int:ID>/ldap/downsync", methods=["POST"])
@secure(requireDB=True, authLevel="user")
def ldapDownsyncOrganization(ID):
    checkPermissions(OrgAdminPermission(ID))
    return ldapDownsync(orgID=ID)
