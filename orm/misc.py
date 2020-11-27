# -*- coding: utf-8 -*-
"""
Created on Tue Jun 23 14:30:38 2020

@copyright: grammm GmbH, 2020
"""

from . import DB
from tools.DataModel import DataModel, Id, Text, Int, Date

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


class MLists(DataModel, DB.Model):
    __tablename__ = "mlists"

    ID = DB.Column("id", INTEGER(10, unsigned=True), nullable=False, primary_key=True)
    listname = DB.Column("listname", DB.VARCHAR(128), nullable=False, unique=True)
    domainID = DB.Column("domain_id", INTEGER(10, unsigned=True), index=True)
    listType = DB.Column("list_type", TINYINT, nullable=False)
    listPrivilege = DB.Column("list_privilege", TINYINT, nullable=False, server_default="0")

    _dictmapping_ = ((Id(), Text("listname", flags="patch")),
                     (Id("domainID", flags="patch"),
                      Int("listType", flags="patch"),
                      Int("listPrivilege", flags="patch")))


class Associations(DataModel, DB.Model):
    __tablename__ = "associations"

    ID = DB.Column("id", INTEGER(10, unsigned=True), nullable=False, primary_key=True)
    username = DB.Column("username", DB.VARCHAR(128), nullable=False, unique=True)
    listID = DB.Column("list_id", INTEGER(10), nullable=False, index=True)

    _dictmapping_ = ((Id(), Text("username", flags="patch"), Id("listID", flags="patch")))


DB.Index("uq_list_id_username", Associations.listID, Associations.username, unique=True)


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


DB.Index("uq_class_id_username", Members.classID, Members.username, unique=True)


class Specifieds(DataModel, DB.Model):
    __tablename__ = "specifieds"

    ID = DB.Column("id", INTEGER(10, unsigned=True), nullable=False, primary_key=True)
    username = DB.Column("username", DB.VARCHAR(128), nullable=False)
    listID = DB.Column("list_id", INTEGER(10), nullable=False, index=True)

    _dictmapping_ = ((Id(),
                      Text("username", flags="patch"),
                      Id("listID", flags="patch")),)
