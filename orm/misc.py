# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grammm GmbH

from . import DB

from tools.DataModel import DataModel, Id, Text

from sqlalchemy.dialects.mysql import INTEGER, TINYINT


class Forwards(DataModel, DB.Model):
    __tablename__ = "forwards"

    ID = DB.Column("id", INTEGER(10, unsigned=True), nullable=False, primary_key=True)
    username = DB.Column("username", DB.VARCHAR(128), nullable=False, unique=True)
    forwardType = DB.Column("forward_type", TINYINT, nullable=False)
    destination = DB.Column("destination", DB.VARCHAR(128), nullable=False)

    _dictmapping_ = ((Id(), Text("username", flags="patch")),
                     (Text("forwardType", flags="patch"),
                      Text("destination", flags="patch")))


class Classes(DataModel, DB.Model):
    __tablename__ = "classes"

    ID = DB.Column("id", INTEGER(10, unsigned=True), nullable=False, primary_key=True)
    classname = DB.Column("classname", DB.VARCHAR(128), nullable=False)
    listname = DB.Column("listname", DB.VARCHAR(128), nullable=False, index=True)
    domainID = DB.Column("domain_id", INTEGER(10, unsigned=True), index=True)
    groupID = DB.Column("group_id", INTEGER(10, unsigned=True), index=True)

    _dictmapping_ = ((Id(), Text("classname", flags="patch")),
                     (Text("listname", flags="patch"),
                      Id("domainID", flags="patch"),
                      Id("groupID", flags="patch")))


class Hierarchy(DataModel, DB.Model):
    __tablename__ = "hierarchy"

    ID = DB.Column("id", INTEGER(10, unsigned=True), nullable=False, primary_key=True)
    classID = DB.Column("class_id", INTEGER(10, unsigned=True), nullable=False, index=True)
    childID = DB.Column("child_id", INTEGER(10, unsigned=True), nullable=False, index=True)
    domainID = DB.Column("domain_id", INTEGER(10, unsigned=True), nullable=False, index=True)
    groupID = DB.Column("group_id", INTEGER(10, unsigned=True), nullable=False, index=True)

    _dictmapping_ = ((Id(),
                      Id("classID", flags="patch"),
                      Id("childID", flags="patch"),
                      Id("domainID", flags="patch"),
                      Id("groupID", flags="patch")),)


class Members(DataModel, DB.Model):
    __tablename__ = "members"

    ID = DB.Column("id", INTEGER(10, unsigned=True), nullable=False, primary_key=True)
    username = DB.Column("username", DB.VARCHAR(128), nullable=False, index=True)
    classID = DB.Column("class_id", INTEGER(10, unsigned=True), nullable=False, index=True)
    domainID = DB.Column("domain_id", INTEGER(10, unsigned=True), nullable=False, index=True)
    groupID = DB.Column("group_id", INTEGER(10, unsigned=True), nullable=False, index=True)

    _dictmapping_ = ((Id(),
                      Text("username", flags="patch"),
                      Id("classID", flags="patch"),
                      Id("domainID", flags="patch"),
                      Id("groupID", flags="patch")),)
