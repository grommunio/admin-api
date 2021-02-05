# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grammm GmbH

from . import DB
from .users import Users
from tools.DataModel import DataModel, Id, Int, RefProp, Text

from sqlalchemy.dialects.mysql import INTEGER, TINYINT
from sqlalchemy.orm import relationship, selectinload, validates


class Associations(DataModel, DB.Model):
    __tablename__ = "associations"

    ID = DB.Column("id", INTEGER(10, unsigned=True), nullable=False, primary_key=True)
    username = DB.Column("username", DB.VARCHAR(128), nullable=False, unique=True)
    listID = DB.Column("list_id", INTEGER(10), nullable=False, index=True)

    _dictmapping_ = ((Id(), Text("username", flags="init")),
                     (Id("listID", flags="init"),))

    def fromdict(self, username, *args, **kwargs):
        self.username = username
        return self


class Specifieds(DataModel, DB.Model):
    __tablename__ = "specifieds"

    ID = DB.Column("id", INTEGER(10, unsigned=True), nullable=False, primary_key=True)
    username = DB.Column("username", DB.VARCHAR(128), nullable=False)
    listID = DB.Column("list_id", INTEGER(10), nullable=False, index=True)

    _dictmapping_ = ((Id(),  Text("username", flags="patch")),
                     (Id("listID", flags="patch"),))

    def fromdict(self, username, *args, **kwargs):
        self.username = username
        return self


class MLists(DataModel, DB.Model):
    __tablename__ = "mlists"

    ID = DB.Column("id", INTEGER(10, unsigned=True), nullable=False, primary_key=True)
    listname = DB.Column("listname", DB.VARCHAR(128), nullable=False, unique=True)
    domainID = DB.Column("domain_id", INTEGER(10, unsigned=True), index=True)
    listType = DB.Column("list_type", TINYINT, nullable=False)
    listPrivilege = DB.Column("list_privilege", TINYINT, nullable=False, server_default="0")

    _dictmapping_ = ((Id(), Text("listname", flags="init"), Int("listType", flags="init")),
                     (Id("domainID", flags="init"),
                      Int("listPrivilege", flags="patch")),
                     (RefProp("associations", flags="patch, managed", link="username", flat="username", qopt=selectinload),
                      RefProp("specifieds", flags="patch, managed", link="username", flat="username", qopt=selectinload),))

    user = relationship(Users, primaryjoin=listname == Users.username, foreign_keys=listname, cascade="all, delete-orphan", single_parent=True)
    associations = relationship(Associations, primaryjoin=ID == Associations.listID, foreign_keys=Associations.listID, cascade="all, delete-orphan", single_parent=True)
    specifieds = relationship(Specifieds, primaryjoin=ID == Specifieds.listID, foreign_keys=Specifieds.listID, cascade="all, delete-orphan", single_parent=True)

    TYPE_NORMAL = 0
    TYPE_GROUP = 1
    TYPE_DOMAIN = 2
    TYPE_CLASS = 3

    PRIV_ALL = 0
    PRIV_INTERNAL = 1
    PRIV_DOMAIN = 2
    PRIV_SPECIFIED = 3
    PRIV_OUTGOING = 4

    @classmethod
    def checkCreateParams(cls, data):
        from .domains import Domains
        from .users import Users, Groups
        if "listname" not in data:
            return "Missing list name"
        if "domainID" in data:
            domain = Domains.query.filter(Domains.ID == data["domainID"]).first()
        elif "@" in data["listname"]:
            domain = Domains.query.filter(Domains.domainname == data["listname"].split("@")[1]).first()
        else:
            domain = None
        if domain is None:
            return "Invalid Domain"
        data["domainID"] = domain.ID
        data["domain"] = domain
        if "@" not in data["listname"]:
            data["listname"] += "@"+domain.domainname
        elif data["listname"].split("@")[1] != domain.domainname:
            return "Domain specifications mismatch"
        if "listType" not in data:
            return "Missing list type"
        if Users.query.filter(Users.username == data["listname"]).count() > 0:
            return "User exists"
        if data["listType"] == cls.TYPE_GROUP:
            group = Groups.query.filter(Groups.ID == data.get("groupID", 0)).with_entities(Groups.ID).first()
            if group is None:
                return "Invalid group"
        elif data["listType"] in (cls.TYPE_NORMAL, cls.TYPE_DOMAIN):
            pass
        else:
            return "Unsupported list type"
        if data.get("listPrivilege", 0) not in (cls.PRIV_ALL,
                                                cls.PRIV_INTERNAL,
                                                cls.PRIV_DOMAIN,
                                                cls.PRIV_SPECIFIED,
                                                cls.PRIV_OUTGOING):
            return "Invalid privilege"


    def __init__(self, props, *args, **kwargs):
        from .users import Users
        self.domain = props.pop("domain")
        self.groupID = props.pop("groupID", 0)
        self.listType = props.pop("listType", 0)
        self.listPrivilege = props.pop("listPrivilege", 0)
        self.fromdict(props, *args, **kwargs)
        self.user = Users({"username": self.listname,
                           "domainID": self.domain.ID,
                           "groupID": self.groupID,
                           "domain": self.domain,
                           "domainStatus": self.domain.domainStatus,
                           "properties": {"displaytypeex": 1, "displayname": "Mailing List "+self.listname}})
        self.user.maildir = ""

    def delete(self):
        if self.user:
            self.user.delete()
        if self.listType == self.TYPE_CLASS:
            from .classes import Classes
            Classes.query.filter(Classes.listname == self.listname).update({Classes.listname: None}, synchronize_session=False)
        DB.session.delete(self)

    @validates("associations")
    def validateAssociations(self, key, assoc, *args):
        if self.listType != self.TYPE_NORMAL:
            raise ValueError("Direct user association is only possible for normal mailing lists")
        return assoc

    @validates("specifieds")
    def validateSpecifieds(self, key, spec, *args):
        if self.listPrivilege != self.PRIV_SPECIFIED:
            raise ValueError("Privilege specification requires 'specific' list privilege")
        return spec

    @validates("listType")
    def validateListType(self, key, type):
        if type not in range(4):
            raise ValueError("Invalid list type")
        return type

    @validates("listPrivilege")
    def validateListType(self, key, priv):
        if priv not in range(5):
            raise ValueError("Invalid list privilege")
        return priv
