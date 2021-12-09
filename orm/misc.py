# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grommunio GmbH

from . import DB

from tools.DataModel import DataModel, Id, Date, Int, Text

from sqlalchemy import Column
from sqlalchemy.dialects.mysql import INTEGER, TINYINT, VARCHAR, TEXT, TIMESTAMP

import json


class Forwards(DataModel, DB.Base):
    __tablename__ = "forwards"

    ID = Column("id", INTEGER(10, unsigned=True), nullable=False, primary_key=True)
    username = Column("username", VARCHAR(128), nullable=False, unique=True)
    forwardType = Column("forward_type", TINYINT, nullable=False)
    destination = Column("destination", VARCHAR(128), nullable=False)

    _dictmapping_ = ((Id(), Text("username", flags="patch")),
                     (Text("forwardType", flags="patch"),
                      Text("destination", flags="patch")))


class DBConf(DB.Base):
    __tablename__ = "configs"

    ID = Column("id", INTEGER(10, unsigned=True), nullable=False, primary_key=True)
    service = Column("service", VARCHAR(200), nullable=False, index=True)
    file = Column("file", VARCHAR(200), nullable=False, index=True)
    key = Column("key", VARCHAR(200), nullable=False)
    value = Column("value", VARCHAR(200), nullable=False, default="")


class TasQ(DataModel, DB.Base):
    __tablename__ = "task_queue"

    ID = Column("id", INTEGER(10, unsigned=True), primary_key=True)
    command = Column("command", VARCHAR(16))
    state = Column("state", TINYINT(unsigned=True), server_default="0")
    created = Column("created", TIMESTAMP, server_default="now()")
    updated = Column("updated", TIMESTAMP, server_default="now()")
    message = Column("message", VARCHAR(160), server_default="")
    _params = Column("params", TEXT, nullable=True, default="{}")
    access = Column("access", TEXT, nullable=True)

    _dictmapping_ = ((Id(), Text("command", flags="init")),
                     (Id("state"),
                      Date("created", time=True),
                      Date("updated", time=True),
                      Text("message")),
                     ({"attr": "params", "flags": "patch"},))

    @property
    def params(self):
        return json.loads(self._params) if self._params is not None else {}

    @params.setter
    def params(self, value):
        self._params = json.dumps(value, separators=(',', ':'))

    @property
    def permission(self):
        from tools.permissions import Permissions
        return Permissions.load(self.access)

    @permission.setter
    def permission(self, perm):
        from tools.permissions import Permissions
        self.access = Permissions.dump(perm)
