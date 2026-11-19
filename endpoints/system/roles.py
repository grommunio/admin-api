# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grommunio GmbH

from flask import jsonify, request

import api
from api.core import API, secure
from api.security import checkPermissions

from tools.permissions import Permissions, SystemAdminPermission, SystemAdminROPermission, OrgAdminPermission
from .. import defaultListHandler, defaultObjectHandler, userQuery


@API.route(api.BaseRoute+"/system/users", methods=["GET"])
@secure(requireDB=True, authLevel="user")
def userListEndpointUnrestricted():
    orgID = request.args.get("orgID", type=int)
    if SystemAdminROPermission() in request.auth["user"].permissions() or orgID is None or orgID <= 0:
        checkPermissions(SystemAdminROPermission())
        return userQuery()
    # Organization admins only get the users of their organization
    checkPermissions(OrgAdminPermission(orgID))
    from orm.users import Users
    return userQuery(filters=(Users.orgID == orgID,))


@API.route(api.BaseRoute+"/system/roles/permissions", methods=["GET"])
@secure()
def getAdminPermissions():
    checkPermissions(SystemAdminROPermission())
    return jsonify(data=Permissions.knownPermissions())


@API.route(api.BaseRoute+"/system/roles", methods=["GET", "POST"])
@secure(requireDB=True, authLevel="user")
def adminRolesListEndpoint():
    checkPermissions(SystemAdminROPermission() if request.method == "GET" else SystemAdminPermission())
    from orm.roles import AdminRoles
    return defaultListHandler(AdminRoles)


@API.route(api.BaseRoute+"/system/roles/<int:ID>", methods=["GET", "PATCH", "DELETE"])
@secure(requireDB=True, authLevel="user")
def adminRolesObjectEndpoint(ID):
    checkPermissions(SystemAdminROPermission() if request.method == "GET" else SystemAdminPermission())
    from orm.roles import AdminRoles, AdminUserRoleRelation
    if request.method == "DELETE" and AdminUserRoleRelation.query.filter(AdminUserRoleRelation.roleID == ID).count() > 0:
        return jsonify(message="Cannot delete role that is still in use"), 400
    return defaultObjectHandler(AdminRoles, ID, "Role")
