# -*- coding: utf-8 -*-
"""
Created on Fri Oct  2 10:06:43 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: Grammm GmbH, 2020
"""

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.mysql import INTEGER

from tools.DataModel import DataModel

from . import DB
from .users import Users


class AdminRoles(DataModel, DB.Model):
    __tablename__  = "admin_roles"

    ID = DB.Column("id", INTEGER(10, unsigned=True), unique=True, primary_key=True)
    name = DB.Column("name", DB.VARCHAR(128))


class AdminPermissions(DataModel, DB.Model):
    __tablename__ = "admin_permissions"

    ID = DB.Column("id", INTEGER(10, unsigned=True), unique=True, primary_key=True)
    name = DB.Column("name", DB.VARCHAR(64))
    params = DB.Column("parameters", DB.BLOB)


class AdminRolePermissionRelation(DB.Model):
    __tablename__ = "admin_role_permission_relationship"

    roleID = DB.Column("role_id", INTEGER(10, unsigned=True), ForeignKey(AdminRoles.ID), primary_key=True)
    permissionID = DB.Column("permission_id", INTEGER(10, unsigned=True), ForeignKey(AdminPermissions.ID), primary_key=True)


class AdminUserRoleRelationship(DB.Model):
    __tablename__ = "admin_user_role_relationship"

    userID = DB.Column("user_id", INTEGER(10, unsigned=True), ForeignKey(Users.ID), primary_key=True)
    roleID = DB.Column("role_id", INTEGER(10, unsigned=True), ForeignKey(AdminRoles.ID), primary_key=True)
