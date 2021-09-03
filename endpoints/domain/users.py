# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020-2021 grommunio GmbH

import api

from api.core import API, secure
from api.security import checkPermissions
from base64 import b64decode
from datetime import datetime
from flask import request, jsonify
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased

from .. import defaultListHandler, defaultObjectHandler

from services import Service

from tools import formats
from tools.config import Config
from tools.constants import PropTags, PropTypes, ExchangeErrors
from tools.misc import createMapping, loadPSO
from tools.permissions import SystemAdminPermission, DomainAdminPermission, DomainAdminROPermission
from tools.rop import nxTime
from tools.storage import setDirectoryOwner, setDirectoryPermission

import json
import shutil

from orm import DB


@API.route(api.BaseRoute+"/domains/<int:domainID>/users", methods=["GET"])
@secure(requireDB=True)
def getUsers(domainID):
    checkPermissions(DomainAdminROPermission(domainID))
    from orm.users import Users, UserProperties
    verbosity = int(request.args.get("level", 1))
    query, limit, offset, count = defaultListHandler(Users, filters=(Users.domainID == domainID,), result="query")
    sorts = request.args.getlist("sort")
    for s in sorts:
        sprop, sorder = s.split(",", 1) if "," in s else (s, "asc")
        if hasattr(PropTags, sprop.upper()):
            up = aliased(UserProperties)
            query = query.join(up, (up.userID == Users.ID) & (up.tag == getattr(PropTags, sprop.upper())))\
                         .order_by(up._propvalstr.desc() if sorder == "desc" else up._propvalstr.asc())
    data = [user.todict(verbosity) for user in query.limit(limit).offset(offset).all()]
    if verbosity < 2 and "properties" in request.args:
        tags = [getattr(PropTags, prop.upper(), None) for prop in request.args["properties"].split(",")]
        for user in data:
            user["properties"] = {}
        usermap = createMapping(data, lambda x: x["ID"])
        properties = UserProperties.query.filter(UserProperties.userID.in_(usermap.keys()), UserProperties.tag.in_(tags)).all()
        for prop in properties:
            usermap[prop.userID]["properties"][prop.name] = prop.val
    return jsonify(count=count, data=data)


@API.route(api.BaseRoute+"/domains/<int:domainID>/users", methods=["POST"])
@secure(requireDB=True)
def createUser(domainID):
    checkPermissions(DomainAdminPermission(domainID))
    from orm.users import Users
    data = request.get_json(silent=True) or {}
    data["domainID"] = domainID
    result, code = Users.create(data, reloadGromoxHttp=True)
    if code != 201:
        return jsonify(message=result), code
    return jsonify(result.fulldesc()), 201


@API.route(api.BaseRoute+"/domains/<int:domainID>/users/<int:userID>", methods=["GET", "PATCH"])
@secure(requireDB=True)
def userObjectEndpoint(domainID, userID):
    checkPermissions(DomainAdminROPermission(domainID) if request.method == "GET" else DomainAdminPermission(domainID))
    from orm.users import Users
    return defaultObjectHandler(Users, userID, "User", filters=(Users.domainID == domainID,))


@API.route(api.BaseRoute+"/domains/<int:domainID>/users/<int:userID>", methods=["DELETE"])
@secure(requireDB=True)
def deleteUserEndpoint(domainID, userID):
    checkPermissions(DomainAdminPermission(domainID))
    from orm.users import Users
    user = Users.query.filter(Users.ID == userID, Users.domainID == domainID).first()
    if user is None:
        return jsonify(message="User #{} not found".format(userID)), 404
    return deleteUser(user)


def deleteUser(user):
    if user.ID == 0:
        return jsonify(message="Cannot delete superuser"), 400
    maildir = user.maildir
    user.delete()
    try:
        DB.session.commit()
    except Exception:
        return jsonify(message="Cannot delete user: Database commit failed."), 500
    with Service("exmdb", Service.SUPPRESS_INOP) as exmdb:
        client = exmdb.ExmdbQueries(exmdb.host, exmdb.host, user.maildir, True)
        client.unloadStore(maildir)
    if request.args.get("deleteFiles") == "true":
        shutil.rmtree(maildir, ignore_errors=True)
    return jsonify(message="isded")


@API.route(api.BaseRoute+"/domains/<int:domainID>/users/<int:userID>/password", methods=["PUT"])
@secure(requireDB=True, authLevel="user")
def setUserPassword(domainID, userID):
    checkPermissions(DomainAdminPermission(domainID))
    from orm.users import Users
    if userID == request.auth["user"].ID:
        return jsonify(message="Cannot reset own password, use '/passwd' endpoint instead"), 400
    user = Users.query.filter(Users.ID == userID, Users.domainID == domainID).first()
    if user is None:
        return jsonify(message="User not found"), 404
    if user.externID is not None:
        return jsonify(message="Cannot modify LDAP imported user"), 400
    data = request.get_json(silent=True)
    if data is None or "new" not in data:
        return jsonify(message="Incomplete data"), 400
    user.password = data["new"]
    DB.session.commit()
    return jsonify(message="Success")


@API.route(api.BaseRoute+"/domains/<int:domainID>/users/<int:userID>/roles", methods=["PATCH"])
@secure(requireDB=True)
def updateUserRoles(domainID, userID):
    checkPermissions(SystemAdminPermission())
    from orm.roles import AdminUserRoleRelation, AdminRoles
    data = request.get_json(silent=True)
    if data is None or "roles" not in data:
        return jsonify(message="Missing roles array"), 400
    roles = {role.roleID for role in AdminUserRoleRelation.query.filter(AdminUserRoleRelation.userID == userID).all()}
    requested = set(data["roles"])
    remove = roles-requested
    add = requested-roles
    AdminUserRoleRelation.query.filter(AdminUserRoleRelation.userID == userID, AdminUserRoleRelation.roleID.in_(remove))\
                               .delete(synchronize_session=False)
    for ID in add:
        DB.session.add(AdminUserRoleRelation(userID, ID))
    try:
        DB.session.commit()
    except IntegrityError as err:
        return jsonify(message="Invalid data", error=err.orig.args[1]), 400
    roles = AdminRoles.query.join(AdminUserRoleRelation).filter(AdminUserRoleRelation.userID == userID).all()
    return jsonify(data=[role.ref() for role in roles])


@API.route(api.BaseRoute+"/domains/<int:domainID>/users/<int:userID>/storeProps", methods=["GET", "DELETE"])
@secure(requireDB=True)
def rdUserStoreProps(domainID, userID):
    checkPermissions(DomainAdminROPermission(domainID) if request.method == "GET" else DomainAdminPermission(domainID))
    from orm.users import Users
    user = Users.query.filter(Users.ID == userID, Users.domainID == domainID).with_entities(Users.maildir).first()
    if user is None:
        return jsonify(message="User not found"), 404
    props = [prop for prop in request.args.get("properties", "").split(",") if prop != ""]
    if len(props) == 0:
        return jsonify(data={})
    for i in range(len(props)):
        if not hasattr(PropTags, props[i].upper()) or not isinstance(getattr(PropTags, props[i].upper()), int):
            return jsonify(message="Unknown property '{}'".format(props[i])), 400
        props[i] = getattr(PropTags, props[i].upper())
    with Service("exmdb") as exmdb:
        client = exmdb.ExmdbQueries(exmdb.host, exmdb.host, user.maildir, True)
        if request.method == "DELETE":
            client.removeStoreProperties(user.maildir, props)
            return jsonify(message="Success.")
        response = client.getStoreProperties(user.maildir, 0, props)
    respData = {}
    for propval in response.propvals:
        propname = PropTags.lookup(propval.tag).lower()
        if propval.tag & 0xFFFF == PropTypes.FILETIME:
            respData[propname] = datetime.fromtimestamp(nxTime(int(propval.toString()))).strftime("%Y-%m-%d %H:%M:%S")
        else:
            respData[propname] = PropTypes.pyType(propval.tag)(propval.toString())
    return jsonify(data=respData)


@API.route(api.BaseRoute+"/domains/<int:domainID>/users/<int:userID>/storeProps", methods=["PATCH"])
@secure(requireDB=True)
def setUserStoreProps(domainID, userID):
    checkPermissions(DomainAdminPermission(domainID))
    from orm.users import Users
    user = Users.query.filter(Users.ID == userID, Users.domainID == domainID).with_entities(Users.maildir).first()
    data = request.get_json(silent=True)
    if data is None or len(data) == 0:
        return jsonify(message="Missing data"), 400
    if user is None:
        return jsonify(message="User not found"), 404
    if not user.maildir:
        return jsonify(message="User has no store"), 400
    errors = {}
    propvals = []
    with Service("exmdb") as exmdb:
        for prop, val in data.items():
            tag = getattr(PropTags, prop.upper(), None)
            if tag is None:
                errors[prop] = "Unknown tag"
                continue
            tagtype = tag & 0xFFFF
            if not isinstance(val, PropTypes.pyType(tagtype)):
                errors[prop] = "Invalid type"
                continue
            if tagtype in (PropTypes.STRING, PropTypes.WSTRING):
                propvals.append(exmdb.TaggedPropval_str(tag, val))
            elif tagtype in PropTypes.intTypes:
                propvals.append(exmdb.TaggedPropval_u64(tag, val))
            else:
                errors[prop] = "Unsupported type"

        client = exmdb.ExmdbQueries(exmdb.host, exmdb.port, user.maildir, True)
        result = client.setStoreProperties(user.maildir, 0, propvals)
        for entry in result.problems:
            tag = PropTags.lookup(entry.proptag, hex(entry.proptag)).lower()
            err = ExchangeErrors.lookup(entry.err, hex(entry.err))
            errors[tag] = err
        if len(errors) != 0:
            API.logger.warn("Failed to set proptags: "+", ".join("{} ({})".format(tag, err) for tag, err in errors.items()))
        return jsonify(message="Great success!" if len(errors) == 0 else "Some tags could not be set", errors=errors)


def decodeSyncState(data, username):
    data = b64decode(data)
    if len(data) >= 2 and data[1] == ord(":"):
        API.logger.warning("Loading PHP serialize objects is deprecated")
        return loadPSO(data, decode_strings=True)["StateObject"][1]["devices"][username]["ASDevice"][1]
    elif len(data) >= 1 and data[0] == ord("{"):
        return json.loads(data)["data"]["devices"][username]["data"]
    return None


@API.route(api.BaseRoute+"/domains/<int:domainID>/users/<int:userID>/sync", methods=["GET"])
@secure(requireDB=True)
def getUserSyncData(domainID, userID):
    checkPermissions(DomainAdminROPermission(domainID))
    props = ("deviceid", "devicetype", "useragent", "deviceuser", "firstsynctime", "lastupdatetime", "asversion")
    from orm.users import Users
    user = Users.query.filter(Users.ID == userID, Users.domainID == domainID).with_entities(Users.username, Users.maildir).first()
    if user is None:
        return jsonify(message="User not found"), 404
    with Service("exmdb") as exmdb:
        devices = []
        client = exmdb.ExmdbQueries(exmdb.host, exmdb.port, user.maildir, True)
        data = client.getSyncData(user.maildir, Config["sync"].get("syncStateFolder", "GS-SyncState")).asdict()
        for device, state in data.items():
            try:
                stateobj = decodeSyncState(state, user.username)
                if stateobj is None:
                    continue
                syncstate = {prop: stateobj[prop] for prop in props}
                syncstate["foldersSyncable"] = len(stateobj["contentdata"])
                syncstate["foldersSynced"] = len([folder for folder in stateobj["contentdata"].values() if 1 in folder])
                devices.append(syncstate)
            except Exception as err:
                API.logger.warn("Failed to decode sync state: {}({})".format(type(err).__name__, ", ".join(str(arg) for arg in err.args)))
        return jsonify(data=devices)


@API.route(api.BaseRoute+"/domains/<int:domainID>/users/<int:userID>/delegates", methods=["GET"])
@secure(requireDB=True)
def getUserDelegates(domainID, userID):
    checkPermissions(DomainAdminROPermission(domainID))
    from orm.users import Users
    user = Users.query.filter(Users.ID == userID, Users.domainID == domainID).with_entities(Users.username, Users.maildir).first()
    if user is None:
        return jsonify(message="User not found"), 404
    try:
        with open(user.maildir+"/config/delegates.txt") as file:
            delegates = [line.strip() for line in file if line.strip != ""]
    except (FileNotFoundError, PermissionError, TypeError):
        delegates = []
    return jsonify(data=delegates)


@API.route(api.BaseRoute+"/domains/<int:domainID>/users/<int:userID>/delegates", methods=["PUT"])
@secure(requireDB=True)
def setUserDelegates(domainID, userID):
    checkPermissions(DomainAdminPermission(domainID))
    data = request.get_json(silent=True)
    if not isinstance(data, list):
        return jsonify(message="Invalid or missing data"), 400
    for entry in data:
        if not formats.email.match(entry):
            return jsonify(message="Invalid delegate e-mail '{}'".format(entry))
    from orm.users import Users
    user = Users.query.filter(Users.ID == userID, Users.domainID == domainID).with_entities(Users.username, Users.maildir).first()
    if user is None:
        return jsonify(message="User not found"), 404
    try:
        delegateFile = user.maildir+"/config/delegates.txt"
        with open(delegateFile, "w") as file:
            file.write("\n".join(data))
    except (FileNotFoundError, PermissionError) as err:
        return jsonify(message="Failed to write delegates: "+" - ".join(str(arg) for arg in err.args)), 500
    except TypeError:
        return jsonify(message="User does not support delegates"), 400
    try:
        setDirectoryOwner(delegateFile, Config["options"].get("fileUid"), Config["options"].get("fileGid"))
        setDirectoryPermission(delegateFile, Config["options"].get("filePermissions"))
    except Exception:
        pass
    return jsonify(message="Delegates updated")


@API.route(api.BaseRoute+"/domains/<int:domainID>/users/<int:userID>/sync/<ID>", methods=["DELETE"])
@secure(requireDB=True)
def resyncDevice(domainID, userID, ID):
    checkPermissions(DomainAdminPermission(domainID))
    from orm.users import Users
    user = Users.query.filter(Users.ID == userID, Users.domainID == domainID).with_entities(Users.username, Users.maildir).first()
    if user is None:
        return jsonify(message="User not found"), 404
    with Service("exmdb") as exmdb:
        client = exmdb.ExmdbQueries(exmdb.host, exmdb.port, user.maildir, True)
        client.resyncDevice(user.maildir, Config["sync"].get("syncStateFolder", "GS-SyncState"), ID)
        return jsonify(message="Success")


@API.route(api.BaseRoute+"/domains/<int:domainID>/syncPolicy", methods=["GET"])
@secure(requireDB=True, requireAuth="optional")
def getDomainSyncPolicy(domainID):
    checkPermissions(DomainAdminROPermission(domainID))
    from orm.domains import Domains
    domain = Domains.query.filter(Domains.ID == domainID).first()
    if domain is None:
        return jsonify(message="Domain not found"), 404
    if domain.syncPolicy is None:
        return jsonify(data=Config["sync"]["defaultPolicy"])
    policy = dict(Config["sync"]["defaultPolicy"])
    policy.update(domain.syncPolicy)
    return jsonify(data=policy)


@API.route(api.BaseRoute+"/service/syncPolicy/<username>", methods=["GET"])
@secure(requireDB=True, requireAuth="optional")
def getUserSyncPolicy(username):
    request.remote_addr in Config["sync"]["policyHosts"] or checkPermissions(DomainAdminROPermission("*"))
    from orm.domains import Domains
    from orm.users import Users
    user = Users.query.filter(Users.username == username).first()
    if user is None:
        return jsonify(data=Config["sync"]["defaultPolicy"])
    request.remote_addr in Config["sync"]["policyHosts"] or checkPermissions(DomainAdminROPermission(user.domainID))
    domain = Domains.query.filter(Domains.ID == user.domainID, Domains._syncPolicy != None).first()
    policy = dict(Config["sync"]["defaultPolicy"])
    if domain is not None:
        policy.update(domain.syncPolicy)
    if user.syncPolicy is not None:
        policy.update(user.syncPolicy)
    return jsonify(data=policy)
