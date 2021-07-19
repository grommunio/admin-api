# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH

from . import DB
from .users import Users
from tools.DataModel import DataModel, Id, Int, RefProp, Text

from sqlalchemy import Column
from sqlalchemy.dialects.mysql import INTEGER, TINYINT, VARCHAR
from sqlalchemy.orm import relationship, selectinload, validates


class Associations(DataModel, DB.Base):
    __tablename__ = "associations"

    ID = Column("id", INTEGER(10, unsigned=True), nullable=False, primary_key=True)
    username = Column("username", VARCHAR(128), nullable=False, unique=True)
    listID = Column("list_id", INTEGER(10), nullable=False, index=True)

    _dictmapping_ = ((Id(), Text("username", flags="init")),
                     (Id("listID", flags="init"),))

    def fromdict(self, username, *args, **kwargs):
        self.username = username
        return self


class Specifieds(DataModel, DB.Base):
    __tablename__ = "specifieds"

    ID = Column("id", INTEGER(10, unsigned=True), nullable=False, primary_key=True)
    username = Column("username", VARCHAR(128), nullable=False)
    listID = Column("list_id", INTEGER(10), nullable=False, index=True)

    _dictmapping_ = ((Id(),  Text("username", flags="patch")),
                     (Id("listID", flags="patch"),))

    def fromdict(self, username, *args, **kwargs):
        self.username = username
        return self


class MLists(DataModel, DB.Base):
    __tablename__ = "mlists"

    ID = Column("id", INTEGER(10, unsigned=True), nullable=False, primary_key=True)
    listname = Column("listname", VARCHAR(128), nullable=False, unique=True)
    domainID = Column("domain_id", INTEGER(10, unsigned=True), index=True)
    listType = Column("list_type", TINYINT, nullable=False)
    listPrivilege = Column("list_privilege", TINYINT, nullable=False, server_default="0")

    _dictmapping_ = ((Id(), Text("listname", flags="init"), Int("listType", flags="patch", filter="set")),
                     (Id("domainID", flags="init"),
                      Int("listPrivilege", flags="patch", filter="set")),
                     (RefProp("associations", flags="patch, managed", link="username", flat="username", qopt=selectinload),
                      RefProp("specifieds", flags="patch, managed", link="username", flat="username", qopt=selectinload),
                      RefProp("class_", alias="class", flags="patch")))

    user = relationship(Users, primaryjoin=listname == Users.username, foreign_keys=listname, cascade="all, delete-orphan", single_parent=True)
    associations = relationship(Associations, primaryjoin=ID == Associations.listID, foreign_keys=Associations.listID, cascade="all, delete-orphan", single_parent=True)
    specifieds = relationship(Specifieds, primaryjoin=ID == Specifieds.listID, foreign_keys=Specifieds.listID, cascade="all, delete-orphan", single_parent=True)
    class_ = relationship("Classes", primaryjoin="MLists.listname == Classes.listname", foreign_keys="Classes.listname", uselist=False)

    TYPE_NORMAL = 0
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
        from .users import Users
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
        elif data["listType"] not in (cls.TYPE_NORMAL, cls.TYPE_DOMAIN,  cls.TYPE_CLASS):
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
        self.listType = props.pop("listType", 0)
        self.listPrivilege = props.pop("listPrivilege", 0)
        self.fromdict(props, *args, **kwargs)
        self.user = Users({"username": self.listname,
                           "domainID": self.domain.ID,
                           "domain": self.domain,
                           "domainStatus": self.domain.domainStatus,
                           "properties": {"displaytypeex": 1, "displayname": "Mailing List "+self.listname}})
        self.user.maildir = ""

    def fromdict(self, data, *args, **kwargs):
        classID = data.pop("class", None)
        DataModel.fromdict(self, data, *args, **kwargs)
        if classID is not None:
            if self.listType != self.TYPE_CLASS:
                raise ValueError("Cannot associate non-class mailing list with class")
            from orm.classes import Classes
            class_ = Classes.query.filter(Classes.ID == classID).first()
            if class_ is None:
                raise ValueError("Invalid class")
            if class_.listname is not None and (self.class_ is None or self.class_.listname != class_.listname):
                raise ValueError("{} is associated with another list ({})".format(class_.classname, class_.listname))
            self.class_ = class_
        elif self.listType == self.TYPE_CLASS and self.class_ is None:
            raise ValueError("Missing class ID")
        return self

    def delete(self):
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
            raise ValueError("Sender specification requires 'specific' list privilege")
        return spec

    @validates("listType")
    def validateListType(self, key, type):
        if type not in range(4):
            raise ValueError("Invalid list type")
        return type

    @validates("listPrivilege")
    def validateListPrivilege(self, key, priv):
        if priv not in range(5):
            raise ValueError("Invalid list privilege")
        return priv


from . import classes
