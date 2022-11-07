# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH

import time

from datetime import datetime
from flask import jsonify, request

import api
from api.core import API, secure
from api.errors import InsufficientPermissions
from api.security import checkPermissions

from services import Service

from tools.config import Config
from tools.permissions import DomainAdminROPermission, SystemAdminPermission


def checkAccess(permission):
    """Check whether the request comes from an permitted source or user has sufficient permissions."""
    request.remote_addr in Config["sync"]["policyHosts"] or checkPermissions(permission)


@API.route(api.BaseRoute+"/service/syncPolicy/<username>", methods=["GET"])
@secure(requireDB=True, requireAuth="optional")
def getUserSyncPolicy(username):
    checkAccess(DomainAdminROPermission("*"))
    from orm.domains import Domains
    from orm.users import Users
    user = Users.query.filter(Users.username == username).first()
    if user is None:
        return jsonify(data=Config["sync"]["defaultPolicy"])
    checkAccess(DomainAdminROPermission(user.domainID))
    domain = Domains.query.filter(Domains.ID == user.domainID, Domains._syncPolicy != None).first()
    policy = dict(Config["sync"]["defaultPolicy"])
    if domain is not None:
        policy.update(domain.syncPolicy)
    if user.syncPolicy is not None:
        policy.update(user.syncPolicy)
    return jsonify(data=policy)


@API.route(api.BaseRoute+"/service/wipe/<username>", methods=["GET"])
@secure(requireDB=True, requireAuth="optional")
def getWipeStatus(username):
    from orm.users import Users, UserDevices
    user = Users.query.filter(Users.username == username).first()
    if user is None:
        return jsonify(message="User not found"), 404
    checkAccess(DomainAdminROPermission(user.domainID))
    try:
        devices = {device.deviceID: device.status
                   for device in UserDevices.query.filter(UserDevices.userID == user.ID)}
    except Exception:
        devices = {}
    requested = request.args["devices"].split(",") if "devices" in request.args else None
    if requested:
        data = {deviceID: {"status": devices[deviceID]} if deviceID in devices else UserDevices.DEFAULT
                for deviceID in requested}
    else:
        data = {deviceID: {"status": status} for deviceID, status in devices.items()}
    return jsonify(data=data)


@API.route(api.BaseRoute+"/service/wipe/<username>", methods=["POST"])
@secure(requireDB=True, requireAuth="optional", authLevel="user")
def setWipeStatus(username):
    checkAccess(SystemAdminPermission())
    from orm.users import DB, Users, UserDevices, UserDeviceHistory
    if not DB.minVersion(93):
        return jsonify(message="Database schema too old - please update to at least n93"), 503
    user = Users.query.filter(Users.username == username).first()
    if user is None:
        return jsonify(message="User not found"), 404
    data = request.get_json(silent=True)
    if data is None:
        return jsonify(message="Missing data")
    requested = set(request.args["devices"].split(",")) if "devices" in request.args else None
    devices = {device.deviceID: device for device in UserDevices.query.filter(UserDevices.userID == user.ID)
               if not requested or device.deviceID in requested}
    authenticated = False
    if "password" in data:
        if "user" in request.auth:
            authenticated = request.auth["user"].chkPw(data["password"])
        else:
            authenticated = user.chkPw(data["password"])
    newStatus = data["status"]
    if requested:
        for deviceID in requested:
            if deviceID not in devices:
                if newStatus > 1 and not authenticated:
                    raise InsufficientPermissions()
                devices[deviceID] = UserDevices(dict(userID=user.ID, deviceID=deviceID, status=newStatus))
                DB.session.add(devices[deviceID])
    DB.session.flush()
    timestamp = datetime.fromtimestamp(data["time"]) if "time" in data else datetime.utcnow()
    remote = data.get("remoteIP", request.remote_addr)
    refresh = []
    for device in devices.values():
        if device.status <= 1 and newStatus > 1:
            if not authenticated:
                raise InsufficientPermissions()
            refresh.append(device.deviceID+"|-|"+user.username)
        device.status = newStatus
        DB.session.add(UserDeviceHistory(dict(userDeviceID=device.ID, time=timestamp, remoteIP=remote, status=newStatus)))
    DB.session.commit()
    if refresh:
        with Service("redis") as redis:
            redis.hdel("grommunio-sync:provisioningcache", *refresh)
    return jsonify(message="Success."), 201


@API.route(api.BaseRoute+"/service/userinfo/<username>", methods=["GET"])
@secure(requireDB=True, requireAuth="optional", authLevel="user")
def getUserInfo(username):
    from orm.users import Users
    user = Users.query.filter(Users.username == username).with_entities(Users.domainID, Users.externID).first()
    if user is None:
        return jsonify(message="User not found"), 404
    checkAccess(DomainAdminROPermission(user.domainID))
    return jsonify(ldap=user.externID is not None)
