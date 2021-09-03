# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grommunio GmbH

from flask import request, jsonify

import api
from api.core import API, secure
from api.security import checkPermissions

from services import Service, ServiceHub
from services.ldap import LdapService
from tools import mconf
from tools.permissions import SystemAdminPermission, SystemAdminROPermission


@API.route(api.BaseRoute+"/system/mconf/ldap", methods=["GET", "DELETE"])
@secure(requireDB=True, authLevel="user")
def getLdapConfig():
    checkPermissions(SystemAdminROPermission() if request.method == "GET" else SystemAdminPermission())
    if request.method == "DELETE":
        mconf.dumpLdap({})
        ServiceHub.load("ldap", force_reload=True)
        return jsonify(message="LDAP deactivated")
    return jsonify(ldapAvailable=Service.available("ldap"), data=mconf.LDAP)


@API.route(api.BaseRoute+"/system/mconf/ldap", methods=["PUT"])
@secure(requireDB=True, authLevel="user")
def setLdapConfig():
    checkPermissions(SystemAdminPermission())
    data = request.get_json(silent=True)
    if data is None:
        return jsonify(message="Missing configuration"), 400
    error = LdapService.testConfig(data)
    forced = False
    if error:
        if request.args.get("force") == "true":
            forced = True
        else:
            return jsonify(message=error), 400
    error = mconf.dumpLdap(data)
    if error:
        return jsonify(message="Configuration updated, but save to disk failed: "+error), 500
    ServiceHub.load("ldap", force_reload=True)
    return jsonify(message="Force updated LDAP configuration" if forced else "LDAP configuration updated")


@API.route(api.BaseRoute+"/system/mconf/authmgr", methods=["GET", "DELETE"])
@secure(requireDB=True, authLevel="user")
def getAuthmgrConfig():
    checkPermissions(SystemAdminROPermission() if request.method == "GET" else SystemAdminPermission())
    if request.method == "DELETE":
        mconf.dumpAuthmgr({})
        return jsonify(message="authmgr configuration set to default")
    return jsonify(data=mconf.AUTHMGR)


@API.route(api.BaseRoute+"/system/mconf/authmgr", methods=["PUT"])
@secure(requireDB=True, authLevel="user")
def setAuthmgrConfig():
    checkPermissions(SystemAdminPermission())
    data = request.get_json(silent=True)
    if data is None:
        return jsonify(message="Missing configuration"), 400
    error = mconf.dumpAuthmgr(data)
    if error:
        return jsonify(message="Configuration updated, but save to disk failed: "+error), 500
    return jsonify(message="authmgr configuration updated")
