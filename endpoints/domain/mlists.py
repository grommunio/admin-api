# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grammm GmbH

import api
from api.core import API, secure
from api.security import checkPermissions

from flask import request, jsonify

from .. import defaultListHandler, defaultObjectHandler

from tools.permissions import DomainAdminPermission

from orm import DB
if DB is not None:
    from orm.mlists import MLists


@API.route(api.BaseRoute+"/domains/<int:domainID>/mlists", methods=["GET"])
@secure(requireDB=True)
def mlistListEndpoint(domainID):
    checkPermissions(DomainAdminPermission(domainID))
    return defaultListHandler(MLists, (MLists.domainID == domainID,))


@API.route(api.BaseRoute+"/domains/<int:domainID>/mlists", methods=["POST"])
@secure(requireDB=True)
def createMlist(domainID):
    checkPermissions(DomainAdminPermission(domainID))
    data = request.get_json(silent=True, cache=True) or {}
    data["domainID"] = domainID
    return defaultListHandler(MLists)


@API.route(api.BaseRoute+"/domains/<int:domainID>/mlists/<int:ID>", methods=["GET", "PATCH"])
@secure(requireDB=True)
def mlistObjectEndpoint(domainID, ID):
    checkPermissions(DomainAdminPermission(domainID))
    return defaultObjectHandler(MLists, ID, "Mailing list", filters=(MLists.domainID == domainID,))


@API.route(api.BaseRoute+"/domains/<int:domainID>/mlists/<int:ID>", methods=["DELETE"])
@secure(requireDB=True)
def mlistDeleteEndpoint(domainID, ID):
    checkPermissions(DomainAdminPermission(domainID))
    mlist = MLists.query.filter(MLists.ID == ID, MLists.domainID == domainID).first()
    if mlist is None:
        return jsonify(message="Mailing list not found"), 404
    mlist.delete()
    DB.session.commit()
    return jsonify(message="Mailing list deleted")
