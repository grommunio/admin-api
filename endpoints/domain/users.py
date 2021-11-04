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
from tools.constants import PropTags, PropTypes, ExchangeErrors, PrivateFIDs, Permissions
from tools.misc import createMapping, loadPSO
from tools.permissions import SystemAdminPermission, DomainAdminPermission, DomainAdminROPermission
from tools.rop import nxTime, makeEidEx
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
    from orm.users import DB, Users
    user = Users.query.filter(Users.ID == userID, Users.domainID == domainID).first()
    if user is None:
        return jsonify(message="User not found"), 404
    props = [prop for prop in request.args.get("properties", "").split(",") if prop != ""]
    user.properties = {prop: val for prop, val in user.properties.items() if prop not in props}
    if len(props) == 0:
        return jsonify(data={}) if request.method == "GET" else jsonify(message="Nothing to delete")
    for i in range(len(props)):
        if not hasattr(PropTags, props[i].upper()) or not isinstance(getattr(PropTags, props[i].upper()), int):
            return jsonify(message="Unknown property '{}'".format(props[i])), 400
        props[i] = getattr(PropTags, props[i].upper())
    with Service("exmdb") as exmdb:
        client = exmdb.ExmdbQueries(exmdb.host, exmdb.port, user.maildir, True)
        if request.method == "DELETE":
            client.removeStoreProperties(user.maildir, props)
            DB.session.commit()
            return jsonify(message="Success.")
        propvals = client.getStoreProperties(user.maildir, 0, props)
    respData = {}
    for propval in propvals:
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
    from orm.users import DB, Users, UserProperties
    user = Users.query.filter(Users.ID == userID, Users.domainID == domainID).first()
    data = request.get_json(silent=True)
    if data is None or len(data) == 0:
        return jsonify(message="Missing data"), 400
    if user is None:
        return jsonify(message="User not found"), 404
    if not user.maildir:
        return jsonify(message="User has no store"), 400
    errors = {}
    propvals = []
    updated = {}
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
            try:
                propvals.append(exmdb.TaggedPropval(tag, val))
            except TypeError:
                errors[prop] = "Unsupported type"
            updated[prop] = UserProperties({"name": prop, "val": val}, user)

        client = exmdb.ExmdbQueries(exmdb.host, exmdb.port, user.maildir, True)
        problems = client.setStoreProperties(user.maildir, 0, propvals)
        for entry in problems:
            tag = PropTags.lookup(entry.proptag, hex(entry.proptag)).lower()
            err = ExchangeErrors.lookup(entry.err, hex(entry.err))
            errors[tag] = err
        user.properties.update({prop: val for prop, val in updated.items() if prop not in errors})
        DB.session.commit()
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
    from orm.users import DB, Users, UserDevices
    user = Users.query.filter(Users.ID == userID, Users.domainID == domainID).with_entities(Users.username, Users.maildir).first()
    if user is None:
        return jsonify(message="User not found"), 404
    with Service("exmdb") as exmdb:
        devices = {}
        client = exmdb.ExmdbQueries(exmdb.host, exmdb.port, user.maildir, True)
        data = client.getSyncData(user.maildir, Config["sync"].get("syncStateFolder", "GS-SyncState"))
        for device, state in data.items():
            try:
                stateobj = decodeSyncState(state, user.username)
                if stateobj is None:
                    continue
                syncstate = {prop: stateobj[prop] for prop in props}
                syncstate["foldersSyncable"] = len(stateobj["contentdata"])
                syncstate["foldersSynced"] = len([folder for folder in stateobj["contentdata"].values() if 1 in folder])
                syncstate["wipeStatus"] = 0
                devices[syncstate["deviceid"]] = syncstate
            except Exception as err:
                API.logger.warn("Failed to decode sync state: {}({})".format(type(err).__name__, ", ".join(str(arg) for arg in err.args)))
        if DB.minVersion(93):
            for device in UserDevices.query.filter(UserDevices.userID == userID)\
                                           .with_entities(UserDevices.deviceID, UserDevices.status):
                if device.deviceID in devices:
                    devices[device.deviceID]["wipeStatus"] = device.status
                else:
                    devices[device.deviceID] = {"deviceid": device.deviceID, "wipeStatus": device.status}
        return jsonify(data=tuple(devices.values()))


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
    user = Users.query.filter(Users.ID == userID, Users.domainID == domainID)\
                      .with_entities(Users.username, Users.maildir).first()
    if user is None:
        return jsonify(message="User not found"), 404
    with Service("exmdb") as exmdb:
        client = exmdb.ExmdbQueries(exmdb.host, exmdb.port, user.maildir, True)
        client.resyncDevice(user.maildir, Config["sync"].get("syncStateFolder", "GS-SyncState"), ID)
        return jsonify(message="Success")


@API.route(api.BaseRoute+"/domains/<int:domainID>/users/<int:userID>/sync/<deviceID>/wipe", methods=["POST", "DELETE"])
@secure(requireDB=True, authLevel="user")
def setDeviceWipe(domainID, userID, deviceID):
    checkPermissions(DomainAdminPermission(domainID))
    from orm.users import DB, Users, UserDevices, UserDeviceHistory
    user = Users.query.filter(Users.ID == userID, Users.domainID == domainID).first()
    if user is None:
        return jsonify(message="User not found"), 404
    device = UserDevices.query.filter(UserDevices.userID == userID, UserDevices.deviceID == deviceID).first()
    status = device.status if device is not None else 0
    if (status < 2 and request.method == "DELETE") or \
       (status >= 2 and request.method == "POST"):
        return jsonify(message="Nothing to to")
    if request.method == "DELETE":
        device.status = 1
        DB.session.add(UserDeviceHistory(dict(userDeviceID=device.ID, time=datetime.utcnow(), remoteIP=request.remote_addr,
                                              status=0)))
        DB.session.commit()
        return jsonify(message="Wipe canceled")
    data = request.get_json(silent=True) or {}
    if "password" not in data or not request.auth["user"].chkPw(data["password"]):
        return jsonify(message="User password required"), 403
    if device is None:
        device = UserDevices(dict(userID=userID, deviceID=deviceID, status=2))
        DB.session.add(device)
        DB.session.flush()
    device.status = 2
    DB.session.add(UserDeviceHistory(dict(userDeviceID=device.ID, time=datetime.utcnow(), remoteIP=request.remote_addr,
                                          status=2)))
    DB.session.commit()
    return jsonify(message="Device wipe requested.")


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


@API.route(api.BaseRoute+"/domains/<int:domainID>/users/<int:userID>/storeAccess", methods=["POST", "PATCH"])
@secure(requireDB=True)
def setUserStoreAccess(domainID, userID):
    checkPermissions(DomainAdminPermission(domainID))
    from orm.users import Users, DB, UserSecondaryStores
    from sqlalchemy import insert
    user = Users.query.filter(Users.ID == userID, Users.domainID == domainID).with_entities(Users.ID, Users.maildir).first()
    if user is None:
        return jsonify(message="User not found"), 404
    if user.maildir is None:
        return jsonify(message="User has no store"), 400
    data = request.get_json(silent=True)
    if data is None or "username" not in data:
        return jsonify(message="Invalid data"), 400
    secondary = Users.query.with_entities(Users.ID).filter(Users.username == data["username"],
                                                           Users.domainID == domainID).first()
    if secondary is None:
        return jsonify(message="Could not find user to grant access to"), 404
    eid = makeEidEx(0, PrivateFIDs.IPMSUBTREE)
    with Service("exmdb") as exmdb:
        client = exmdb.ExmdbQueries(exmdb.host, exmdb.port, user.maildir, True)
        client.setFolderMember(user.maildir, eid, data["username"], Permissions.STOREOWNER)
    if DB.minVersion(91):
        DB.session.execute(insert(UserSecondaryStores).values(primary=user.ID, secondary=secondary.ID).prefix_with("IGNORE"))
        DB.session.commit()
    return jsonify(message="Success."), 201 if request.method == "POST" else 200


@API.route(api.BaseRoute+"/domains/<int:domainID>/users/<int:userID>/storeAccess", methods=["GET"])
@secure(requireDB=True)
def getUserStoreAccess(domainID, userID):
    checkPermissions(DomainAdminROPermission(domainID))
    from orm.users import Users
    user = Users.query.filter(Users.ID == userID, Users.domainID == domainID).with_entities(Users.maildir).first()
    if user is None:
        return jsonify(message="User not found"), 404
    if user.maildir is None:
        return jsonify(message="User has no store"), 400
    with Service("exmdb") as exmdb:
        client = exmdb.ExmdbQueries(exmdb.host, exmdb.port, user.maildir, True)
        memberList = exmdb.FolderMemberList(client.getFolderMemberList(user.maildir, makeEidEx(0, PrivateFIDs.IPMSUBTREE)))
        members = [{"ID": member.id, "displayName": member.name, "username": member.mail} for member in memberList.members
                   if member.rights & Permissions.STOREOWNER]
        return jsonify(data=members)


@API.route(api.BaseRoute+"/domains/<int:domainID>/users/<int:userID>/storeAccess/<username>", methods=["DELETE"])
@secure(requireDB=True)
def deleteUserStoreAccess(domainID, userID, username):
    checkPermissions(DomainAdminPermission(domainID))
    from orm.users import DB, Users, UserSecondaryStores
    user = Users.query.filter(Users.ID == userID, Users.domainID == domainID).with_entities(Users.ID, Users.maildir).first()
    if user is None:
        return jsonify(message="User not found"), 404
    if user.maildir is None:
        return jsonify(message="User has no store"), 400
    with Service("exmdb") as exmdb:
        client = exmdb.ExmdbQueries(exmdb.host, exmdb.port, user.maildir, True)
        client.setFolderMember(user.maildir, makeEidEx(0, PrivateFIDs.IPMSUBTREE), username, Permissions.STOREOWNER, True)
    if DB.minVersion(91):
        secondary = Users.query.with_entities(Users.ID).filter(Users.username == username).first()
        if secondary is not None:
            UserSecondaryStores.query.filter(UserSecondaryStores.primaryID == user.ID,
                                             UserSecondaryStores.secondaryID == secondary.ID).delete()
        DB.session.commit()
    return jsonify(message="Success")
