# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grammm GmbH

import json

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.mysql import INTEGER
from sqlalchemy.orm import relationship

from tools.DataModel import DataModel, Id, Int, RefProp, Text, MissingRequiredAttributeError

from . import DB
from .users import Users


class AdminRoles(DataModel, DB.Model):
    __tablename__  = "admin_roles"

    ID = DB.Column("id", INTEGER(10, unsigned=True), unique=True, primary_key=True)
    name = DB.Column("name", DB.VARCHAR(32), unique=True, nullable=False)
    description = DB.Column("description", DB.VARCHAR(256))

    permissions = relationship("AdminRolePermissionRelation", cascade="all, delete-orphan", single_parent=True)
    users = relationship("AdminUserRoleRelation", cascade="all, delete-orphan")

    _dictmapping_ = ((Id(), Text("name", flags="patch")),
                     (Text("description", flags="patch"),),
                     (RefProp("permissions", flags="patch, managed", link="ID"),
                      RefProp("users", link="userID", flat="user", flags="patch")))


class AdminRolePermissionRelation(DataModel, DB.Model):
    __tablename__ = "admin_role_permission_relation"

    ID = DB.Column("id", INTEGER(10, unsigned=True), primary_key=True)
    roleID = DB.Column("role_id", INTEGER(10, unsigned=True), ForeignKey(AdminRoles.ID), nullable=False)
    permission = DB.Column("permission", DB.VARCHAR(64), nullable=False)
    _params = DB.Column("parameters", DB.TEXT)

    role = relationship(AdminRoles)

    _dictmapping_ = ((Id(), Text("permission", flags="init"), {"attr": "params", "flags": "patch"}), (), (Int("roleID"),))

    @property
    def params(self):
        return json.loads(self._params) if self._params is not None else None

    @params.setter
    def params(self, value):
        self._params = json.dumps(value, separators=(',', ':'))

    def __init__(self, props, role, *args, **kwargs):
        self.role = role
        self.fromdict(props, *args, **kwargs)

    def fromdict(self, patches, *args, **kwargs):
        if "permission" in patches:
            from tools.permissions import Permissions
            try:
                Permissions.create(patches["permission"], patches.get("params"))
            except KeyError as err:
                raise ValueError(*err.args)
        return DataModel.fromdict(self, patches, *args, **kwargs)


class AdminUserRoleRelation(DataModel, DB.Model):
    __tablename__ = "admin_user_role_relation"

    userID = DB.Column("user_id", INTEGER(10, unsigned=True), ForeignKey(Users.ID, ondelete="cascade"), primary_key=True)
    roleID = DB.Column("role_id", INTEGER(10, unsigned=True), ForeignKey(AdminRoles.ID), primary_key=True)

    user = relationship("Users")
    role = relationship(AdminRoles)

    _dictmapping_ = ((RefProp("user"),),
                     (RefProp("role"),))

    def __init__(self, userID, role, *args, **kwargs):
        self.userID = userID
        if isinstance(role, int):
            self.roleID = role
        else:
            self.role = role
