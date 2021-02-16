# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grammm GmbH

from flask import request, jsonify

import api
from api.core import API, secure
from api.security import checkPermissions

from tools.permissions import DomainAdminPermission

from .. import defaultListHandler, defaultObjectHandler


from orm import DB
if DB is not None:
    from orm.classes import Classes


@API.route(api.BaseRoute+"/domains/classes", methods=["GET", "POST"])
@secure()
def classListEndpoint():
    checkPermissions(DomainAdminPermission("*"))
    return defaultListHandler(Classes)


@API.route(api.BaseRoute+"/domains/classes/<int:ID>", methods=["GET", "PATCH", "DELETE"])
@secure()
def classObjectEndpoint(ID):
    checkPermissions(DomainAdminPermission("*"))
    return defaultObjectHandler(Classes, ID, "Class")


@API.route(api.BaseRoute+"/domains/classes/tree", methods=["GET"])
@secure()
def classTreeEndpoint():
    try:
        return jsonify(data=Classes.refTree())
    except ValueError as err:
        return jsonify(message="Failed to create tree: "+err.args[0]), 500
