# -*- coding: utf-8 -*-
"""
Created on Tue Jun 23 16:37:38 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: Grammm GmbH, 2020
"""

import api
from api import API

from flask import request, jsonify

from . import defaultListHandler, defaultObjectHandler

from orm import DB
if DB is not None:
    from orm.users import Users, Groups


@API.route(api.BaseRoute+"/groups", methods=["GET", "POST"])
@api.secure(requireDB=True)
def groupListEndpoint():
    return defaultListHandler(Groups)


@API.route(api.BaseRoute+"/groups/<int:ID>", methods=["GET", "PATCH", "DELETE"])
@api.secure(requireDB=True)
def groupObjectEndpoint(ID):
    return defaultObjectHandler(Groups, ID, "Group")


@API.route(api.BaseRoute+"/users", methods=["GET", "POST"])
@api.secure(requireDB=True)
def userListEndpoint():
    return defaultListHandler(Users)


@API.route(api.BaseRoute+"/users/<int:ID>", methods=["GET", "PATCH", "DELETE"])
@api.secure(requireDB=True)
def userObjectEndpoint(ID):
    return defaultObjectHandler(Users, ID, "User")


@API.route(api.BaseRoute+"/users/<int:ID>/password", methods=["POST"])
@api.secure(requireDB=True)
def setUserPassword(ID):
    user = Users.query.filter(Users.ID == ID).first()
    if user is None:
        return jsonify(message="User not found"), 404
    data = request.get_json(silent=True)
    if data is None or "old" not in data or "new" not in data:
        return jsonify(message="Incomplete data"), 400
    if not user.chkPw(data["old"]):
        return jsonify(message="Old password does not match"), 400
    user.password = data["new"]
    DB.session.commit()
    return jsonify(message="Success")
