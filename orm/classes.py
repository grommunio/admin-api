# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grammm GmbH

from . import DB
from .users import Groups
from .mlists import MLists

from tools.classfilters import ClassFilter
from tools.constants import PropTags
from tools.DataModel import DataModel, Id, RefProp, Text

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.mysql import INTEGER
from sqlalchemy.orm import relationship, validates

import json


class Hierarchy(DataModel, DB.Model):
    __tablename__ = "hierarchy"

    ID = DB.Column("id", INTEGER(10, unsigned=True), nullable=False, primary_key=True)
    childID = DB.Column("child_id", INTEGER(10, unsigned=True), nullable=False, index=True)
    classID = DB.Column("class_id", INTEGER(10, unsigned=True), nullable=False, index=True)
    groupID = DB.Column("group_id", INTEGER(10, unsigned=True), nullable=False, index=True)

    cParent = relationship("Classes", foreign_keys=classID, primaryjoin="Hierarchy.classID == Classes.ID")
    gParent = relationship(Groups, foreign_keys=groupID, primaryjoin=groupID == Groups.ID)
    child = relationship("Classes", foreign_keys=childID, primaryjoin="Hierarchy.childID == Classes.ID")

    _dictmapping_ = ((RefProp("cParent", "classID"), RefProp("gParent", "groupID"), RefProp("child")),)

    def __init__(self, type, ID, childclass, *args, **kwargs):
        self.classID = self.groupID = 0
        if type == "child":
            self.childID = ID
            self.cParent = childclass
            return
        self.child = childclass
        if type == "class":
            self.classID = ID
        elif type == "group":
            self.groupID = ID

    def fromdict(self, *args, **kwargs):
        return self


class Members(DataModel, DB.Model):
    __tablename__ = "members"

    ID = DB.Column("id", INTEGER(10, unsigned=True), nullable=False, primary_key=True)
    username = DB.Column("username", DB.VARCHAR(128), nullable=False, index=True)
    classID = DB.Column("class_id", INTEGER(10, unsigned=True), nullable=False, index=True)

    _dictmapping_ = ((Id(),
                      Text("username", flags="patch"),
                      Id("classID", flags="patch")),)

    def __init__(self, username, *args):
        self.username = username

    def fromdict(self, username):
        self.username = username
        return self


class Classes(DataModel, DB.Model):
    __tablename__ = "classes"

    ID = DB.Column("id", INTEGER(10, unsigned=True), nullable=False, primary_key=True)
    classname = DB.Column("classname", DB.VARCHAR(128), nullable=False)
    listname = DB.Column("listname", DB.VARCHAR(128), nullable=False, index=True)
    domainID = DB.Column("domain_id", INTEGER(10, unsigned=True), ForeignKey("domains.id"), nullable=False)
    _filters = DB.Column("filters", DB.TEXT)

    cParents = relationship(Hierarchy,
                            primaryjoin=(ID == Hierarchy.childID) & (Hierarchy.classID != 0),
                            foreign_keys=Hierarchy.childID)
    children = relationship(Hierarchy,
                            primaryjoin=(ID == Hierarchy.classID),
                            foreign_keys=Hierarchy.classID)

    members = relationship(Members, primaryjoin=ID == Members.classID, foreign_keys=Members.classID,
                           cascade="all, delete-orphan", single_parent=True, lazy="selectin")
    mlist = relationship(MLists, primaryjoin=listname == MLists.listname, foreign_keys=listname, cascade="all, delete-orphan", single_parent=True)

    _dictmapping_ = ((Id(), Text("classname", flags="patch")),
                     (Text("listname"),),
                     (RefProp("cParents", alias="parentClasses", link="classID", flat="cParent"),
                      RefProp("members", flags="patch, managed", link="classID", flat="username"),
                      RefProp("children", flat="child"),
                      {"attr": "filters", "flags": "patch"}))


    def _updateCParents(self, requested):
        cIDs = {parent.classID for parent in self.cParents}
        self.cParents = [parent for parent in self.cParents if parent.classID in requested] +\
                        [Hierarchy("class", ID, self) for ID in requested if ID not in cIDs]

    def __init__(self, props, *args, **kwargs):
        self.domainID = props.pop("domainID")
        self.fromdict(props, *args, **kwargs)

    def fromdict(self, patches, *args, **kwargs):
        if "parentClasses" in patches:
            self._updateCParents(patches.pop("parentClasses"))
        return DataModel.fromdict(self, patches, *args, **kwargs)

    @staticmethod
    def checkCreateParams(data):
        if "domainID" not in data:
            return "Missing domain ID"
        from .domains import Domains
        if Domains.query.filter(Domains.ID == data["domainID"]).count() == 0:
            return "Invalid domain ID"

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
            raise ValueError("Parent class must belong to the same domain")
        if self.checkCycle(self, h.classID):
            raise ValueError("Adding class #{} as parent would create a cycle".format(h.classID))
        return h

    @staticmethod
    def refTree(domainID):
        hierarchy = Hierarchy.query.join(Classes, Hierarchy.classID == Classes.ID)\
                                   .filter(Hierarchy.classID != 0, Classes.domainID == domainID)\
                                   .with_entities(Hierarchy.classID, Hierarchy.childID).all()
        classes = Classes.query.filter(Classes.domainID == domainID).with_entities(Classes.ID, Classes.classname).all()
        classMap = {c.ID: {"ID": c.ID, "classname": c.classname, "children": []} for c in classes}
        toplevel = dict(classMap)
        for h in hierarchy:
            classMap[h.classID]["children"].append(classMap[h.childID])
            toplevel.pop(h.childID, None)
        return list(toplevel.values())

    @validates("members")
    def validateMembers(self, key, member, *args):
        if self._filters is not None:
            raise ValueError("Cannot explicitely add member to filter defined class")
        return member

    @property
    def filters(self):
        try:
            data = json.loads(self._filters)
        except:
            return None
        for disj in data:
            for expr in disj:
                if "p" in expr:
                    expr["p"] = PropTags.lookup(expr["p"], hex(expr["p"])).lower()
        return data

    @filters.setter
    def filters(self, data):
        if data is None or len(data) == 0:
            self._filters = None
            return
        if len(self.members) != 0:
            raise ValueError("Cannot specify filter and members at the same time")
        for disj in data:
            for expr in disj:
                if "p" in expr:
                    expr["p"] = getattr(PropTags, expr["p"].upper(), None)
        ClassFilter(data)
        self._filters = json.dumps(data, separators=(",", ":"))
