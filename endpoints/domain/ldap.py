# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2022 grommunio GmbH

import shutil

from flask import jsonify, request

import api
from api.core import API, secure
from api.security import checkPermissions

from services import Service, ServiceUnavailableError
from tools.ldap import downsyncObject, importObject
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
        ldapusers = ldap.searchUsers(request.args.get("query"), domainnames, limit=limit or None,
                                     filterIncomplete=request.args.get("showAll") != "true")
    return jsonify(data=[{"ID": ldap.escape_filter_chars(u.ID), "name": u.name, "email": u.email,
                          "type": u.type, "error": u.error} for u in ldapusers if u.ID])


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
    orgID, domains = _getTarget()
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
        return jsonify(message="LDAP object not found"), 404

    result, code = importObject(userinfo, ldap, orgID=orgID, force=force, lang=lang, syncMembers=True, syncExisting=True)

    return jsonify(result), code


@API.route(api.BaseRoute+"/domains/<int:domainID>/users/<int:userID>/downsync", methods=["PUT"])
@secure(requireDB=True, authLevel="user")
def updateLdapUser(domainID, userID):
    checkPermissions(DomainAdminPermission(domainID))
    from orm.users import Users
    user = Users.query.filter(Users.ID == userID, Users.domainID == domainID).first()
    if user is None:
        return jsonify(message="User not found"), 404
    message, code = downsyncObject(user)
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
                    if user.maildir != "" and user.status != Users.CONTACT:
                        client = exmdb.ExmdbQueries(exmdb.host if user.homeserverID == 0 else user.homeserver.hostname,
                                                    exmdb.port, user.maildir, True)
                    else:
                        client = None
                    homeserver = user.homeserverID
                while index < len(users) and users[index].homeserverID == homeserver:
                    if client is not None:
                        client.unloadStore(users[index].maildir)
                    if deleteMaildirs:
                        shutil.rmtree(users[index].maildir, ignore_errors=True)
                    users[index].delete()
                    index += 1
        except Exception as err:
            API.logger.warning(str(err) + " | Failed to unload store: exmdb service not available")
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
