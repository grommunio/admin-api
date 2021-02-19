# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grammm GmbH

from flask import request, jsonify

import api
from api.core import API, secure
from api.security import checkPermissions

from tools.classfilters import ClassFilter
from tools.constants import PropTags
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


@API.route(api.BaseRoute+"/domains/classes/testFilter", methods=["POST"])
@secure()
def testClassFilter():
    data = request.get_json(silent=True)
    if data is None:
        return jsonify(message="No filter provided"), 400
    try:
        for disj in data:
                for expr in disj:
                    if "p" in expr:
                        expr["p"] = getattr(PropTags, expr["p"].upper())
    except AttributeError:
        return jsonify(message="'{}' is not a valid property".format(expr["p"])), 400
    try:
        cf = ClassFilter(data)
    except ValueError as err:
        return jsonify(message="Invalid filter: "+err.args[0]), 400
    res = DB.session.execute(cf.sql("id, username")).fetchall()
    return jsonify(data=[{"ID": u.id, "username": u.username} for u in res])
