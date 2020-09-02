# -*- coding: utf-8 -*-
"""
Created on Tue Jun 23 16:37:38 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: Grammm GmbH, 2020
"""

import api
from api import API

from flask import request, jsonify
from sqlalchemy.exc import IntegrityError

from . import defaultListHandler, defaultObjectHandler

from tools.misc import AutoClean, propvals2dict
from tools.storage import UserSetup
from tools.pyexmdb import pyexmdb
from tools.config import Config

from orm import DB
if DB is not None:
    from orm.ext import AreaList
    from orm.users import Users, Groups
    from orm.orgs import Domains


@API.route(api.BaseRoute+"/groups", methods=["GET", "POST"])
@api.secure(requireDB=True)
def groupListEndpoint():
    return defaultListHandler(Groups)


@API.route(api.BaseRoute+"/groups/<int:ID>", methods=["GET", "PATCH", "DELETE"])
@api.secure(requireDB=True)
def groupObjectEndpoint(ID):
    return defaultObjectHandler(Groups, ID, "Group")


@API.route(api.BaseRoute+"/domains/<int:domainID>/users", methods=["GET"])
@api.secure(requireDB=True)
def userListEndpoint(domainID):
    return defaultListHandler(Users, filters=(Users.domainID == domainID,))


@API.route(api.BaseRoute+"/domains/<int:domainID>/users", methods=["POST"])
@api.secure(requireDB=True)
def createUser(domainID):
    def rollback():
        DB.session.rollback()
    data = request.get_json(silent=True) or {}
    areaID = data.get("areaID")
    data["domainID"] = domainID
    user = defaultListHandler(Users, result="object")
    if not isinstance(user, Users):
        return user  # If the return value is not a user, it is an error response
    area = AreaList.query.filter(AreaList.dataType == AreaList.USER, AreaList.ID == areaID).first()
    try:
        with AutoClean(rollback):
            DB.session.add(user)
            DB.session.flush()
            with UserSetup(user, area) as us:
                us.run()
            if not us.success:
                return jsonify(message="Error during user setup", error=us.error),  us.errorCode
            DB.session.commit()
            return jsonify(user.fulldesc()), 201
    except IntegrityError as err:
        return jsonify(message="Object violates database constraints", error=err.orig.args[1]), 400


@API.route(api.BaseRoute+"/domains/<int:domainID>/users/<int:ID>", methods=["GET", "PATCH", "DELETE"])
@api.secure(requireDB=True)
def userObjectEndpoint(domainID, ID):
    return defaultObjectHandler(Users, ID, "User", filters=(Users.domainID == domainID,))


@API.route(api.BaseRoute+"/domains/<int:domainID>/users/<int:ID>/password", methods=["PUT"])
@api.secure(requireDB=True)
def setUserPassword(domainID, ID):
    user = Users.query.filter(Users.ID == ID, Users.domainID == domainID).first()
    if user is None:
        return jsonify(message="User not found"), 404
    data = request.get_json(silent=True)
    if data is None or "new" not in data:
        return jsonify(message="Incomplete data"), 400
    user.password = data["new"]
    DB.session.commit()
    return jsonify(message="Success")


@API.route(api.BaseRoute+"/domains/<int:domainID>/folders", methods=["GET"])
@api.secure(requireDB=True)
def getPublicFoldersList(domainID):
    domain = Domains.query.filter(Domains.ID == domainID).first()
    if domain is None:
        return jsonify(message="Domain not found"), 404
    client = pyexmdb.ExmdbClient("127.0.0.1", 5000, Config["options"]["domainPrefix"], False)
    table = pyexmdb.getFolderList(client, domain.homedir)
    folders = [propvals2dict(entry) for entry in table.entries]
    return jsonify(data=folders)


@API.route(api.BaseRoute+"/domains/<int:domainID>/folders", methods=["POST"])
@api.secure(requireDB=True)
def createPublicFolder(domainID):
    domain = Domains.query.filter(Domains.ID == domainID).first()
    if domain is None:
        return jsonify(message="Domain not found"), 404
    data = request.json
    client = pyexmdb.ExmdbClient("127.0.0.1", 5000, Config["options"]["domainPrefix"], False)
    response = pyexmdb.createPublicFolder(client, domain.homedir, domain.ID, data["name"], data["container"], data["comment"])
    if response.folderId == 0:
        return jsonify(message="Folder creation failed"), 500
    return jsonify(message="Success", folderID=response.folderId), 201
