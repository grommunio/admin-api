# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2022 grommunio GmbH

import api
from api.core import API, secure
from api.security import checkPermissions

from tools.misc import RecursiveDict
from tools.permissions import SystemAdminPermission, DomainAdminPermission, DomainAdminROPermission

from flask import jsonify, request

import json

try:
    with open("res/storelangs.json") as file:
        storeLangs = json.load(file)
except Exception as err:
    API.logger.warn("Failed to load store languages ({}): {}"
                    .format(type(err).__name__, " - ".join(str(arg) for arg in err.args)))
    storeLangs = []


@API.route(api.BaseRoute+"/defaults/storeLangs", methods=["GET"])
@secure(requireAuth=False)
def getStoreLangs():
    return jsonify(data=storeLangs)


@API.route(api.BaseRoute+"/defaults/createParams", methods=["GET"])
@secure(requireDB=True)
def getSystemDefaults():
    checkPermissions(DomainAdminROPermission("*"))
    from orm.misc import DBConf
    data = RecursiveDict({"user": {}, "domain": {}})
    data.update(DBConf.getFile("grommunio-admin", "defaults-system", True))
    if "domain" in request.args and request.args["domain"].isdecimal:
        checkPermissions(DomainAdminROPermission(int(request.args["domain"])))
        data.update(DBConf.getFile("grommunio-admin", "defaults-domain-"+request.args["domain"]))
    return jsonify(data=data)


@API.route(api.BaseRoute+"/defaults/createParams", methods=["PATCH", "PUT"])
@secure(requireDB=True)
def setSystemDefaults():
    checkPermissions(SystemAdminPermission())
    data = request.get_json(silent=True)
    if data is None:
        return jsonify(message="Missing data"), 400
    from orm.misc import DBConf, DB
    data = RecursiveDict(data)
    if request.method == "PATCH":
        orig = DBConf.getFile("grommunio-admin", "defaults-system", True)
        data = orig.update(data)
    DBConf.setFile("grommunio-admin", "defaults-system", data)
    DB.session.commit()
    return jsonify(message="Success")


@API.route(api.BaseRoute+"/defaults/createParams/<int:domainID>", methods=["GET"])
@secure(requireDB=True)
def getDomainDefaults(domainID):
    checkPermissions(DomainAdminROPermission(domainID))
    from orm.misc import DBConf
    data = RecursiveDict({"user": {}, "domain": {}})
    data.update(DBConf.getFile("grommunio-admin", "defaults-domain-"+str(domainID), True))
    return jsonify(data=data)


@API.route(api.BaseRoute+"/defaults/createParams/<int:domainID>", methods=["PATCH"])
@secure(requireDB=True)
def setDomainDefaults(domainID):
    checkPermissions(DomainAdminPermission(domainID))
    data = request.get_json(silent=True)
    if data is None:
        return jsonify(message="Missing data"), 400
    from orm.misc import DBConf, DB
    data = RecursiveDict(data)
    if request.method == "PATCH":
        orig = DBConf.getFile("grommunio-admin", "defaults-domain-"+str(domainID), True)
        data = orig.update(data)
    DBConf.setFile("grommunio-admin", "defaults-domain-"+str(domainID), data)
    DB.session.commit()
    return jsonify(message="Success")
