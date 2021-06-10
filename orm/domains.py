# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grammm GmbH

from . import DB
from tools import formats
from tools.DataModel import DataModel, Id, Text, Int, Date

import idna

from sqlalchemy import Column, func, select
from sqlalchemy.dialects.mysql import DATE, INTEGER, TINYINT, VARCHAR
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import column_property
from sqlalchemy.types import TypeDecorator

from .users import Users

class Orgs(DataModel, DB.Base):
    __tablename__ = "orgs"

    ID = Column("id", INTEGER(10, unsigned=True), unique=True, primary_key=True, nullable=False)
    name = Column("name", VARCHAR(32), nullable=False)
    description = Column("description", VARCHAR(128))

    _dictmapping_ = ((Id(), Text("name", flags="patch")), (Text("description", flags="patch"),))


class Domains(DataModel, DB.Base):
    class DomainName(TypeDecorator):
        """Custom column type to allow comparisons to work with unicode names."""
        impl = VARCHAR
        cache_ok = True

        def process_bind_param(self, value, dialect):
            try:
                xfix = "%" if value[0] == "%" else "", "%" if value[-1] == "%" else ""
                return xfix[0]+idna.encode(value.strip("%")).decode("ascii")+xfix[1]
            except:
                try:
                    return value.encode("ascii")
                except:
                    return None

    __tablename__ = "domains"

    ID = Column("id", INTEGER(10, unsigned=True), unique=True, primary_key=True, nullable=False)
    orgID = Column("org_id", INTEGER(10, unsigned=True), nullable=False, server_default="0", index=True)
    _domainname = Column("domainname", DomainName(64), nullable=False)
    homedir = Column("homedir", VARCHAR(128), nullable=False, server_default="")
    maxUser = Column("max_user", INTEGER(10, unsigned=True), nullable=False)
    title = Column("title", VARCHAR(128), nullable=False, server_default="")
    address = Column("address", VARCHAR(128), nullable=False, server_default="")
    adminName = Column("admin_name", VARCHAR(32), nullable=False, server_default="")
    tel = Column("tel", VARCHAR(64), nullable=False, server_default="")
    endDay = Column("end_day", DATE, nullable=False, default="3333-03-03")
    domainStatus = Column("domain_status", TINYINT, nullable=False, server_default="0")

    activeUsers = column_property(select([func.count(Users.ID)]).where((Users.domainID == ID) & (Users.addressStatus == 0)).as_scalar())
    inactiveUsers = column_property(select([func.count(Users.ID)]).where((Users.domainID == ID) & (Users.addressStatus != 0)).as_scalar())

    _dictmapping_ = ((Id(), Text("domainname", flags="init"), "displayname"),
                     (Id("orgID", flags="patch"),
                      Int("maxUser", flags="patch"),
                      Int("activeUsers"),
                      Int("inactiveUsers"),
                      Text("title", flags="patch"),
                      Text("address", flags="patch"),
                      Text("adminName", flags="patch"),
                      Text("tel", flags="patch"),
                      Date("endDay", flags="patch"),
                      Int("domainStatus", flags="patch", filter="set")))

    NORMAL = 0
    SUSPENDED = 1
    OUTOFDATE = 2
    DELETED = 3

    def __init__(self, props: dict, *args, **kwargs):
        if "password" in props:
            self.password = props.pop("password")
        DataModel.__init__(self, props, args, kwargs)

    @hybrid_property
    def domainname(self):
        return self._domainname

    @domainname.setter
    def domainname(self, value):
        try:
            idn = idna.encode(value).decode("ascii")
        except:
            idn = value
        if not formats.domain.match(idn):
            raise ValueError("'{}' is not a valid domain name".format(idn))
        self._domainname = idn

    @property
    def displayname(self):
        return idna.decode(self._domainname)

    @staticmethod
    def checkCreateParams(data):
        if "maxUser" not in data:
            return "Missing required property maxUser"

    def delete(self):
        from .users import Users
        self.domainStatus = self.DELETED
        Users.query.filter(Users.domainID == self.ID)\
                   .update({Users.addressStatus: Users.addressStatus.op("&")(0xF) + (self.DELETED << 4)},
                           synchronize_session=False)

    def recover(self):
        from .users import Users
        self.domainStatus = self.NORMAL
        Users.query.filter(Users.domainID == self.ID)\
                   .update({Users.addressStatus: Users.addressStatus.op("&")(0xF) + (self.NORMAL << 4)},
                           synchronize_session=False)


    def purge(self, deleteFiles=False, printStatus=False):
        from .classes import Classes, Hierarchy, Members
        from .mlists import MLists, Associations, Specifieds
        from .users import Users, Aliases
        users = Users.query.filter(Users.domainID == self.ID)
        if deleteFiles:
            from shutil import rmtree
            us = users.with_entities(Users.maildir).all()
            if printStatus:
                print("Deleting user directories...", end="")
            for user in us:
                if user.maildir != "":
                    rmtree(user.maildir, True)
            if printStatus:
                print("Done.\nDeleting domain directory...", end="")
            rmtree(self.homedir, True)
            print("Done.")
        nosync = {"synchronize_session": False}
        classes = Classes.query.filter(Classes.domainID == self.ID).with_entities(Classes.ID)
        Hierarchy.query.filter(Hierarchy.childID.in_(classes) | Hierarchy.classID.in_(classes)).delete(**nosync)
        Members.query.filter(Members.classID.in_(classes)).delete(**nosync)
        classes.delete(**nosync)
        mlists = MLists.query.filter(MLists.domainID == self.ID)
        Specifieds.query.filter(Specifieds.listID.in_(mlists.with_entities(MLists.ID))).delete(**nosync)
        Associations.query.filter(Associations.listID.in_(mlists.with_entities(MLists.ID))).delete(**nosync)
        mlists.delete(**nosync)
        Aliases.query.filter(Aliases.mainname.in_(users.with_entities(Users.username))).delete(**nosync)
        users.delete(**nosync)
        DB.session.delete(self)
