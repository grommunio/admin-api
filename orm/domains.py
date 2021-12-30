# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH

from . import DB, OptionalC, NotifyTable
from tools import formats
from tools.DataModel import DataModel, Id, Text, Int, Date, RefProp
from tools.DataModel import InvalidAttributeError, MismatchROError, MissingRequiredAttributeError
from services import Service

import idna
import json

from sqlalchemy import Column, func, select, ForeignKey
from sqlalchemy.dialects.mysql import DATE, INTEGER, TEXT, TINYINT, VARCHAR
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import column_property, validates, relationship
from sqlalchemy.types import TypeDecorator

from .users import Users


class Orgs(DataModel, DB.Base):
    __tablename__ = "orgs"

    ID = Column("id", INTEGER(10, unsigned=True), unique=True, primary_key=True, nullable=False)
    name = Column("name", VARCHAR(32), nullable=False)
    description = Column("description", VARCHAR(128))

    domains = relationship("Domains")

    _dictmapping_ = ((Id(), Text("name", flags="patch")), (Text("description", flags="patch"),),
                     (RefProp("domains", flags="patch"),))

    def fromdict(self, patches, *args, **kwargs):
        domains = patches.pop("domains", None)
        if domains is not None:
            if self.ID is not None:
                sync = {"synchronize_session": "fetch"}
                Domains.query.filter(Domains.orgID == self.ID, Domains.ID.notin_(domains)).update({Domains.orgID: 0}, **sync)
                Domains.query.filter(Domains.ID.in_(domains)).update({Domains.orgID: self.ID}, **sync)
            else:
                domains = Domains.query.filter(Domains.ID.in_(domains))
                for domain in domains:
                    domain.org = self
        DataModel.fromdict(self, patches, *args, **kwargs)


class Domains(DataModel, DB.Base, NotifyTable):
    class DomainName(TypeDecorator):
        """Custom column type to allow comparisons to work with unicode names."""
        impl = VARCHAR
        cache_ok = True

        def process_bind_param(self, value, dialect):
            try:
                xfix = "%" if value[0] == "%" else "", "%" if value[-1] == "%" else ""
                return xfix[0]+idna.encode(value.strip("%")).decode("ascii")+xfix[1]
            except Exception:
                try:
                    return value.encode("ascii")
                except Exception:
                    return None

    __tablename__ = "domains"

    ID = Column("id", INTEGER(10, unsigned=True), unique=True, primary_key=True, nullable=False)
    orgID = Column("org_id", INTEGER(10, unsigned=True), ForeignKey(Orgs.ID), nullable=False, server_default="0", index=True)
    _domainname = Column("domainname", DomainName(64), nullable=False)
    homedir = Column("homedir", VARCHAR(128), nullable=False, server_default="")
    maxUser = Column("max_user", INTEGER(10, unsigned=True), nullable=False)
    title = Column("title", VARCHAR(128), nullable=False, server_default="")
    address = Column("address", VARCHAR(128), nullable=False, server_default="")
    adminName = Column("admin_name", VARCHAR(32), nullable=False, server_default="")
    tel = Column("tel", VARCHAR(64), nullable=False, server_default="")
    endDay = Column("end_day", DATE, nullable=False, default="3333-03-03")
    domainStatus = Column("domain_status", TINYINT, nullable=False, server_default="0")
    chatID = OptionalC(79, "NULL", Column("chat_id", VARCHAR(26)))
    _syncPolicy = OptionalC(77, "NULL", Column("sync_policy", TEXT))

    activeUsers = column_property(select([func.count(Users.ID)]).where((Users.domainID == ID) & (Users.addressStatus == 0)).as_scalar())
    inactiveUsers = column_property(select([func.count(Users.ID)]).where((Users.domainID == ID) & (Users.addressStatus != 0)).as_scalar())
    org = relationship(Orgs)

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
                      Int("domainStatus", flags="patch", filter="set")),
                     ({"attr": "syncPolicy", "flags": "patch"},
                      {"attr": "chat", "flags": "patch"}))

    NORMAL = 0
    SUSPENDED = 1
    OUTOFDATE = 2
    DELETED = 3

    _team = None

    def __init__(self, props: dict, *args, **kwargs):
        if "password" in props:
            self.password = props.pop("password")
        DataModel.__init__(self, props, args, kwargs)

    def fromdict(self, patches, *args, **kwargs):
        DataModel.fromdict(self, patches, args, kwargs)
        if self.chatID:
            with Service("chat", Service.SUPPRESS_INOP) as chat:
                self._team = chat.updateTeam(self)

    @property
    def syncPolicy(self):
        try:
            return json.loads(self._syncPolicy)
        except Exception:
            return None

    @syncPolicy.setter
    def syncPolicy(self, value):
        self._syncPolicy = json.dumps(value, separators=(",", ":")) if value is not None else None

    @hybrid_property
    def domainname(self):
        return self._domainname

    @domainname.setter
    def domainname(self, value):
        try:
            idn = idna.encode(value).decode("ascii")
        except Exception:
            idn = value
        if not formats.domain.match(idn):
            raise ValueError("'{}' is not a valid domain name".format(idn))
        self._domainname = idn

    @property
    def chat(self):
        if not self.chatID:
            return False
        if self._team is None:
            with Service("chat", Service.SUPPRESS_ALL) as grochat:
                self._team = grochat.getTeam(self.chatID)
        return self._team["delete_at"] == 0 if self._team else False

    @chat.setter
    def chat(self, value):
        if value == self.chat:
            return
        if not DB.minVersion(79):
            raise ValueError("Cannot activate chat - please upgrade database schema to at least 79")
        if value and self.domainStatus:
            raise ValueError("Cannot activate chat for deactivated domain")
        with Service("chat") as chat:
            if isinstance(value, str):
                tmp = chat.getTeam(value)
                self.chatID = value
                self._team = tmp
            if self._team:
                tmp = chat.activateTeam(self, value)
                if tmp:
                    self._team["delete_at"] = not value
            else:
                tmp = chat.createTeam(self)
                if tmp:
                    self._team = tmp

    @property
    def displayname(self):
        return idna.decode(self._domainname)

    @validates("_syncPolicy")
    def triggerSyncPolicyUpdate(self, key, value, *args):
        if value != self._syncPolicy:
            users = ["grommunio-sync:policycache-"+user.username
                     for user in Users.query.with_entities(Users.username).filter(Users.domainID == self.ID)]
            if len(users) > 0:
                with Service("redis", Service.SUPPRESS_INOP) as r:
                    r.delete(*users)
        return value

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
        from .roles import AdminRoles as AR, AdminRolePermissionRelation as ARPR
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
        permissions = ARPR.query.filter(ARPR.permission == "DomainAdmin", ARPR._params == self.ID)
        roles = []
        for permission in permissions:
            DB.session.delete(permission)
            roles.append(permission.roleID)
        roles = AR.query.filter(AR.ID.in_(roles))
        for role in roles:
            if len(role.permissions) == 0:
                DB.session.delete(role)
        DB.session.delete(self)

    @staticmethod
    def create(props, createRole=True, *args, **kwargs):
        from .roles import AdminRoles
        from tools.storage import DomainSetup
        from tools.misc import AutoClean
        error = Domains.checkCreateParams(props)
        if error is not None:
            return error, 400
        try:
            domain = Domains(props, *args, **kwargs)
        except (MissingRequiredAttributeError, InvalidAttributeError, MismatchROError, ValueError) as err:
            return err.args[0], 400
        try:
            with AutoClean(lambda: DB.session.rollback()):
                DB.session.add(domain)
                DB.session.flush()
                with DomainSetup(domain) as ds:
                    ds.run()
                if not ds.success:
                    return "Error during domain setup: "+ds.error, ds.errorCode
                DB.session.commit()
            domainAdminRoleName = "Domain Admin ({})".format(domain.domainname)
            if createRole and AdminRoles.query.filter(AdminRoles.name == domainAdminRoleName).count() == 0:
                DB.session.add(AdminRoles({"name": domainAdminRoleName,
                                           "description": "Domain administrator for "+domain.domainname,
                                           "permissions": [{"permission": "DomainAdmin", "params": domain.ID}]}))
                DB.session.commit()
            return domain, 201
        except IntegrityError as err:
            return "Object violates database constraints ({})".format(err.orig.args[1]), 400

    @classmethod
    def _commit(cls, *args, **kwargs):
        with Service("systemd", Service.SUPPRESS_ALL) as sysd:
            sysd.reloadService("gromox-delivery.service", "gromox-delivery-queue.service",
                               "gromox-http.service")


Domains.NTregister()
