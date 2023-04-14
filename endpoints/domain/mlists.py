# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grommunio GmbH

import api
from api.core import API, secure
from api.security import checkPermissions

from flask import request, jsonify

from .. import defaultListHandler, defaultObjectHandler

from tools.permissions import DomainAdminPermission, DomainAdminROPermission

from orm import DB


@API.route(api.BaseRoute+"/domains/<int:domainID>/mlists", methods=["GET"])
@secure(requireDB=True)
def mlistListEndpoint(domainID):
    checkPermissions(DomainAdminROPermission(domainID))
    from orm.mlists import MLists
    return defaultListHandler(MLists, (MLists.domainID == domainID,))


@API.route(api.BaseRoute+"/domains/<int:domainID>/mlists", methods=["POST"])
@secure(requireDB=True)
def createMlist(domainID):
    checkPermissions(DomainAdminPermission(domainID))
    from orm.mlists import MLists
    data = request.get_json(silent=True, cache=True) or {}
    data["domainID"] = domainID
    return defaultListHandler(MLists)


@API.route(api.BaseRoute+"/domains/<int:domainID>/mlists/<int:ID>", methods=["GET", "PATCH", "DELETE"])
@secure(requireDB=True)
def mlistObjectEndpoint(domainID, ID):
    checkPermissions(DomainAdminROPermission(domainID) if request.method == "GET" else DomainAdminPermission(domainID))
    from orm.mlists import MLists
    return defaultObjectHandler(MLists, ID, "Mailing list", filters=(MLists.domainID == domainID,))
