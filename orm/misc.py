# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grommunio GmbH

from . import DB

from tools.DataModel import DataModel, Id, Text

from sqlalchemy import Column
from sqlalchemy.dialects.mysql import INTEGER, TINYINT, VARCHAR


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
