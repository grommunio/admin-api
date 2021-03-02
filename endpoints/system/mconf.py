# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grammm GmbH

from flask import request, jsonify

import api
from api.core import API, secure
from api.security import checkPermissions

from tools import ldap, mconf
from tools.permissions import SystemAdminPermission


@API.route(api.BaseRoute+"/system/mconf/ldap", methods=["GET", "DELETE"])
@secure(requireDB=True, authLevel="user")
def getLdapConfig():
    checkPermissions(SystemAdminPermission())
    if request.method == "DELETE":
        ldap.disable()
        mconf.dumpLdap({})
        return jsonify(message="LDAP deactivated")
    return jsonify(ldapAvailable=ldap.LDAP_available, data=mconf.LDAP)


@API.route(api.BaseRoute+"/system/mconf/ldap", methods=["PUT"])
@secure(requireDB=True, authLevel="user")
def setLdapConfig():
    checkPermissions(SystemAdminPermission())
    data = request.get_json(silent=True)
    if data is None:
        return jsonify(message="Missing configuration"), 400
    error = ldap.reloadConfig(data)
    if error:
        return jsonify(message=error), 400
    error = mconf.dumpLdap(data)
    return jsonify(message="LDAP configuration updated"+("" if error is None else
                                                         ", save to disk failed: "+error))
