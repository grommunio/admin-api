# -*- coding: utf-8 -*-
"""
Created on Mon Oct  5 15:46:26 2020

@copyright: grammm GmbH, 2020
"""

from flask import jsonify, request

import api
from api.core import API, secure
from api.security import checkPermissions

from tools.permissions import Permissions, SystemAdminPermission

from .. import defaultListHandler, defaultObjectHandler

from orm import DB
if DB is not None:
    from orm.users import Users
    from orm.roles import AdminRoles, AdminUserRoleRelation


@API.route(api.BaseRoute+"/system/users", methods=["GET"])
@secure(requireDB=True)
def userListEndpointUnrestricted():
    checkPermissions(SystemAdminPermission())
    return defaultListHandler(Users, filters=(Users.ID != 0,))


@API.route(api.BaseRoute+"/system/roles/permissions", methods=["GET"])
@secure()
def getAdminPermissions():
    checkPermissions(SystemAdminPermission())
    return jsonify(data=Permissions.knownPermissions())


@API.route(api.BaseRoute+"/system/roles", methods=["GET", "POST"])
@secure(requireDB=True, authLevel="user")
def adminRolesListEndpoint():
    checkPermissions(SystemAdminPermission())
    return defaultListHandler(AdminRoles)


@API.route(api.BaseRoute+"/system/roles/<int:ID>", methods=["GET", "PATCH", "DELETE"])
@secure(requireDB=True, authLevel="user")
def adminRolesObjectEndpoint(ID):
    checkPermissions(SystemAdminPermission())
    if request.method == "DELETE" and AdminUserRoleRelation.query.filter(AdminUserRoleRelation.roleID == ID).count() > 0:
        return jsonify(message="Das kannste so nicht machen."), 400
    return defaultObjectHandler(AdminRoles, ID, "Role")
