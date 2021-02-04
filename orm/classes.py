# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grammm GmbH

from . import DB
from .users import Groups
from .domains import Domains
from .mlists import MLists

from tools.DataModel import DataModel, Id, RefProp, Text

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.mysql import INTEGER
from sqlalchemy.orm import relationship, validates


class Hierarchy(DataModel, DB.Model):
    __tablename__ = "hierarchy"

    ID = DB.Column("id", INTEGER(10, unsigned=True), nullable=False, primary_key=True)
    classID = DB.Column("class_id", INTEGER(10, unsigned=True), nullable=False, index=True)
    childID = DB.Column("child_id", INTEGER(10, unsigned=True), nullable=False, index=True)
    domainID = DB.Column("domain_id", INTEGER(10, unsigned=True), nullable=False, index=True)
    groupID = DB.Column("group_id", INTEGER(10, unsigned=True), nullable=False, index=True)

    cParent = relationship("Classes", foreign_keys=classID, primaryjoin="Hierarchy.classID == Classes.ID")
    gParent = relationship(Groups, foreign_keys=groupID, primaryjoin=groupID == Groups.ID)
    dParent = relationship(Domains, foreign_keys=domainID, primaryjoin=domainID == Domains.ID)
    child = relationship("Classes", foreign_keys=childID, primaryjoin="Hierarchy.childID == Classes.ID")


    _dictmapping_ = ((RefProp("cParent", "classID"), RefProp("gParent", "groupID"), RefProp("dParent", "domainID")),)


    def __init__(self, data, childclass, *args, **kwargs):
        self.classID = 0
        self.groupID = childclass.groupID
        self.domainID = childclass.domainID
        self.child = childclass
        if data["type"] == "class":
            self.classID = data["classID"]
        elif data["type"] == "group":
            self.groupID = data["groupID"]

    def fromdict(self, *args, **kwargs):
        return self


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

    def __init__(self, username, class_):
        self.username = username
        self.domainID = class_.domainID
        self.groupID = class_.groupID

    def fromdict(self, username):
        self.username = username
        return self


class Classes(DataModel, DB.Model):
    __tablename__ = "classes"

    ID = DB.Column("id", INTEGER(10, unsigned=True), nullable=False, primary_key=True)
    classname = DB.Column("classname", DB.VARCHAR(128), nullable=False)
    listname = DB.Column("listname", DB.VARCHAR(128), nullable=False, index=True)
    domainID = DB.Column("domain_id", INTEGER(10, unsigned=True), index=True)
    groupID = DB.Column("group_id", INTEGER(10, unsigned=True), index=True)

    cParents = relationship(Hierarchy,
                            primaryjoin=(ID == Hierarchy.childID) & (Hierarchy.classID != 0),
                            foreign_keys=Hierarchy.childID)
    dParents = relationship(Hierarchy,
                            primaryjoin=(ID == Hierarchy.childID) & (Hierarchy.classID == 0) & (Hierarchy.groupID == 0),
                            foreign_keys=Hierarchy.childID)
    gParents = relationship(Hierarchy,
                            primaryjoin=(ID == Hierarchy.childID) & (Hierarchy.classID == 0) & (Hierarchy.groupID != 0),
                            foreign_keys=Hierarchy.childID)

    members = relationship(Members, primaryjoin=ID == Members.classID, foreign_keys=Members.classID, cascade="all, delete-orphan", single_parent=True)
    mlist = relationship(MLists, primaryjoin=listname == MLists.listname, foreign_keys=listname)


    _dictmapping_ = ((Id(), Text("classname", flags="patch")),
                     (Id("domainID", flags="init"),
                      Id("groupID", flags="patch")),
                     (RefProp("cParents", alias="parentClasses", flags="patch, managed", link="classID", flat="cParent"),
                      RefProp("gParents", alias="parentGroups", flags="patch, managed", link="groupID", flat="gParent"),
                      RefProp("members", flags="patch, managed", link="classID", flat="username")))


    def __init__(self, data, *args, **kwargs):
        DataModel.fromdict(self, data, *args, **kwargs)
        self.dParents = [Hierarchy({"type": "domain"}, self, *args, **kwargs)]

    @staticmethod
    def checkCreateParams(data):
        if data.get("domainID", 0) == 0:
            return "Missing domain ID"
        if Domains.query.filter(Domains.ID == data["domainID"]).count() == 0:
            return "Invalid domain ID"
        if data.get("groupID", 0) != 0:
            if Groups.query.filter(Groups.ID == data["groupID"]).count() == 0:
                return "Invalid group ID"
        else:
            data["groupID"] = 0

    def fromdict(self, patches, *args, **kwargs):
        self.groupID = patches.get("groupID", self.groupID)
        if "parentClasses" in patches:
            patches["parentClasses"] = [{"classID": ID, "type": "class"} for ID in patches["parentClasses"]]
        if "parentGroups" in patches:
            patches["parentGroups"] = [{"groupID": ID, "type": "group"} for ID in patches["parentGroups"]]
        if "parentDomains" in patches:
            patches["parentDomains"] = [{"domainID": ID, "type": "domain"} for ID in patches["parentDomains"]]
        return DataModel.fromdict(self, patches, *args, **kwargs)


    @staticmethod
    def checkCycle(base, targetID):
        if base.ID is None:
            return False
        new = {targetID}
        collected = set()
        while len(new) != 0:
            parents = Hierarchy.query.filter(Hierarchy.childID.in_(new), Hierarchy.classID != 0)\
                                     .with_entities(Hierarchy.classID).all()
            new = {h.classID for h in parents}
            new -= collected
            collected |= new
            if base.ID in new:
                return True
        return False

    @validates("cParents")
    def validateParentClass(self, key, h, *args):
        parent = Classes.query.filter(Classes.ID == h.classID).with_entities(Classes.domainID).first()
        if parent is None:
            raise ValueError("Parent class does not exist")
        if parent.domainID != self.domainID:
            raise  ValueError("Parent class must be in same domain")
        if self.checkCycle(self, parent.classID):
            raise ValueError("Adding class #{} as parent would result in a cycle".format(parent.classID))
        return parent
