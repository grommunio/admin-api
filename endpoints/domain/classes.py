# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grammm GmbH

from flask import request, jsonify

import api
from api.core import API, secure
from api.security import checkPermissions

from tools.classfilters import ClassFilter
from tools.constants import PropTags
from tools.permissions import DomainAdminPermission, DomainAdminROPermission

from .. import defaultListHandler, defaultObjectHandler

from orm import DB


@API.route(api.BaseRoute+"/domains/<int:domainID>/classes", methods=["GET", "POST"])
@secure(requireDB=True)
def classListEndpoint(domainID):
    checkPermissions(DomainAdminROPermission(domainID) if request.method == "GET" else DomainAdminPermission(domainID))
    from orm.classes import Classes
    if request.method == "POST":
        data = request.get_json(silent=True, cache=True) or {}
        data["domainID"] = domainID
    return defaultListHandler(Classes, filters=(Classes.domainID == domainID,))


@API.route(api.BaseRoute+"/domains/<int:domainID>/classes/<int:ID>", methods=["GET", "PATCH", "DELETE"])
@secure(requireDB=True)
def classObjectEndpoint(domainID, ID):
    checkPermissions(DomainAdminROPermission(domainID) if request.method == "GET" else DomainAdminPermission(domainID))
    from orm.classes import Classes
    return defaultObjectHandler(Classes, ID, "Class", filters=(Classes.domainID == domainID,))


@API.route(api.BaseRoute+"/domains/<int:domainID>/classes/tree", methods=["GET"])
@secure(requireDB=True)
def classTreeEndpoint(domainID):
    checkPermissions(DomainAdminROPermission(domainID))
    from orm.classes import Classes
    try:
        return jsonify(data=Classes.refTree(domainID))
    except ValueError as err:
        return jsonify(message="Failed to create tree: "+err.args[0]), 500


@API.route(api.BaseRoute+"/domains/<int:domainID>/classes/testFilter", methods=["POST"])
@secure(requireDB=True)
def testClassFilter(domainID):
    checkPermissions(DomainAdminPermission(domainID))
    from orm.classes import Classes
    data = request.get_json(silent=True)
    if data is None:
        return jsonify(message="No filter provided"), 400
    try:
        for disj in data:
            for expr in disj:
                if expr["prop"] not in Classes.filterColumns:
                    try:
                        expr["prop"] = getattr(PropTags, expr["prop"].upper())
                    except AttributeError:
                        raise ValueError("Invalid property '{}'".format(expr["prop"]))
    except AttributeError:
        return jsonify(message="'{}' is not a valid property".format(expr["p"])), 400
    try:
        cf = ClassFilter(data)
    except ValueError as err:
        return jsonify(message="Invalid filter: "+err.args[0]), 400
    query = "SELECT uf.id AS id, uf.username AS username FROM (" +\
            cf.sql("id, username, domain_id") +\
            ") AS uf WHERE uf.domain_id = :domainID"
    res = DB.session.execute(query, params={"domainID": domainID}).fetchall()
    return jsonify(data=[{"ID": u.id, "username": u.username} for u in res])
