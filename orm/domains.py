# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH

from . import DB, OptionalC, OptionalNC, NotifyTable
from tools import formats
from tools.DataModel import DataModel, Id, Text, Int, Date, RefProp
from tools.DataModel import InvalidAttributeError, MismatchROError, MissingRequiredAttributeError
from services import Service

import idna
import json

import sqlalchemy
from sqlalchemy import Column, func, inspect, select, ForeignKey
from sqlalchemy.dialects.mysql import DATE, INTEGER, TEXT, TINYINT, VARCHAR
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import column_property, validates, relationship, selectinload
from sqlalchemy.types import TypeDecorator


class Orgs(DataModel, DB.Base):
    __tablename__ = "orgs"

    ID = Column("id", INTEGER(10, unsigned=True), unique=True, primary_key=True, nullable=False)
    name = Column("name", VARCHAR(32), nullable=False)
    description = Column("description", VARCHAR(128))

    domains = relationship("Domains", back_populates="org")

    _dictmapping_ = ((Id(), Text("name", flags="patch")), (Text("description", flags="patch"),),
                     (RefProp("domains", flags="patch"),))

    def fromdict(self, patches, *args, **kwargs):
        domains = patches.pop("domains", None)
        DataModel.fromdict(self, patches, *args, **kwargs)
        if domains is not None:
            if self.ID is not None:
                sync = {"synchronize_session": "fetch"}
                Domains.query.filter(Domains.orgID == self.ID, Domains.ID.notin_(domains)).update({Domains.orgID: 0}, **sync)
                Domains.query.filter(Domains.ID.in_(domains)).update({Domains.orgID: self.ID}, **sync)
            else:
                domains = Domains.query.filter(Domains.ID.in_(domains))
                for domain in domains:
                    domain.org = self

    @validates("name")
    def validateName(self, key, value, *args):
        if Orgs.query.filter(Orgs.ID != self.ID, Orgs.name == value).count():
            raise ValueError("Organization '{}' already exists".format(value))
        return value


# Introduced in n109
class OrgParam(DB.Base):
    __tablename__ = "orgparam"

    orgID = Column("org_id", INTEGER(10, unsigned=True), ForeignKey(Orgs.ID), primary_key=True)
    key = Column("key", VARCHAR(32), nullable=False, primary_key=True)
    value = Column("value", VARCHAR(255))

    def __init__(self, orgID, key, value):
        self.orgID = orgID
        self.key = key
        self.value = value

    @classmethod
    def loadLdap(cls, orgID):
        def _addIfDef(dc, d, sc, s, all=False, type=None):
            def tf(v):
                return v if type is None else type(v)
            if s in sc:
                dc[d] = tf(sc[s]) if not all else [tf(v) for v in sc[s].split(",")]

        entries = cls.query.filter(cls.orgID == orgID, cls.key.like("ldap_%")).with_entities(cls.key, cls.value).all()
        if len(entries) == 0:
            return None
        plain = {entry.key: entry.value for entry in entries}

        config = {"connection": {}, "groups": {}, "users": {}}
        _addIfDef(config, "disabled", plain, "ldap_disabled", type=lambda x: x.lower() in ("true", "yes", "1"))
        _addIfDef(config["connection"], "server", plain, "ldap_uri")
        _addIfDef(config["connection"], "bindUser", plain, "ldap_binddn")
        _addIfDef(config["connection"], "bindPass", plain, "ldap_bindpw")
        _addIfDef(config["connection"], "starttls", plain, "ldap_start_tls", type=lambda x: x.lower() in ("true", "yes", "1"))
        _addIfDef(config["connection"], "connections", plain, "data_connections", type=int)
        _addIfDef(config, "baseDn", plain, "ldap_basedn")
        _addIfDef(config, "objectID", plain, "ldap_object_id")
        _addIfDef(config["users"], "username", plain, "ldap_mail_attr")
        _addIfDef(config["users"], "filter", plain, "ldap_user_filter")
        _addIfDef(config["users"], "contactFilter", plain, "ldap_contact_filter")
        _addIfDef(config["users"], "searchAttributes", plain, "ldap_user_search_attrs", all=True)
        _addIfDef(config["users"], "displayName", plain, "ldap_user_displayname")
        _addIfDef(config["users"], "defaultQuota", plain, "ldap_user_default_quota", type=int)
        _addIfDef(config["users"], "templates", plain, "ldap_user_templates", all=True)
        _addIfDef(config["users"], "aliases", plain, "ldap_user_aliases")
        _addIfDef(config["groups"], "groupaddr", plain, "ldap_group_addr")
        _addIfDef(config["groups"], "groupfilter", plain, "ldap_group_filter")
        _addIfDef(config["groups"], "groupname", plain, "ldap_group_name")
        _addIfDef(config["groups"], "groupMemberAttr", plain, "ldap_group_memberof")
        if "ldap_user_attributes" in plain:
            config["users"]["attributes"] = {entry.split(" ", 1)[0]: entry.split(" ", 1)[1]
                                             for entry in plain.getall("ldap_user_attributes") if " " in entry}
        return config

    @classmethod
    def saveLdap(cls, orgID, config):
        def _addIfDef(dc, d, sc, s):
            if s in sc and sc[s] is not None:
                dc[d] = ",".join(str(x) for x in sc[s]) if isinstance(sc[s], list) else str(sc[s])

        flat = {}
        _addIfDef(flat, "ldap_disabled", config, "disabled")
        if "connection" in config:
            _addIfDef(flat, "ldap_uri", config["connection"], "server")
            _addIfDef(flat, "ldap_binddn", config["connection"], "bindUser")
            _addIfDef(flat, "ldap_bindpw", config["connection"], "bindPass")
            _addIfDef(flat, "ldap_start_tls", config["connection"], "starttls")
        _addIfDef(flat, "ldap_basedn", config, "baseDn")
        _addIfDef(flat, "ldap_object_id", config, "objectID")
        if "users" in config:
            _addIfDef(flat, "ldap_mail_attr", config["users"], "username")
            _addIfDef(flat, "ldap_user_displayname", config["users"], "displayName")
            _addIfDef(flat, "ldap_user_filter", config["users"], "filter")
            _addIfDef(flat, "ldap_contact_filter", config["users"], "contactFilter")
            _addIfDef(flat, "ldap_user_search_attrs", config["users"], "searchAttributes")
            _addIfDef(flat, "ldap_user_default_quota", config["users"], "defaultQuota")
            _addIfDef(flat, "ldap_user_templates", config["users"], "templates")
            _addIfDef(flat, "ldap_user_aliases", config["users"], "aliases")
            if "attributes" in config["users"] and config["users"]["attributes"]:
                flat["ldap_user_attributes"] = ["{} {}".format(key, value)
                                                for key, value in config["users"]["attributes"].items()]
        if "groups" in config:
            _addIfDef(flat, "ldap_group_addr", config["groups"], "groupaddr")
            _addIfDef(flat, "ldap_group_filter", config["groups"], "groupfilter")
            _addIfDef(flat, "ldap_group_name", config["groups"], "groupname")
            _addIfDef(flat, "ldap_group_memberof", config["groups"], "groupMemberAttr")
        cls.query.filter(cls.orgID == orgID).delete(synchronize_session=False)
        for key, value in flat.items():
            DB.session.add(OrgParam(orgID, key, value))
        DB.session.commit()

    @classmethod
    def wipeLdap(cls, orgID):
        cls.query.filter(cls.orgID == orgID, cls.key.like("ldap_%")).delete(synchronize_session=False)
        DB.session.commit()

    @classmethod
    def ldapOrgs(cls):
        return [entry[0] for entry in cls.query.with_entities(cls.orgID.distinct()).filter(cls.key.like("ldap_%"))]


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
    homeserverID = OptionalC(105, "0", Column("homeserver", TINYINT(unsigned=True), nullable=False, server_default="0"))
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

    org = relationship(Orgs, back_populates="domains")
    homeserver = OptionalNC(105, None,
                            relationship("Servers", foreign_keys=homeserverID, primaryjoin="Domains.homeserverID==Servers.ID"))

    _dictmapping_ = ((Id(), Text("domainname", flags="init"), "displayname"),
                     (Id("orgID", flags="patch"),
                      Int("maxUser", flags="patch"),
                      Int("activeUsers"),
                      Int("inactiveUsers"),
                      Int("virtualUsers"),
                      Text("title", flags="patch"),
                      Text("address", flags="patch"),
                      Text("adminName", flags="patch"),
                      Text("tel", flags="patch"),
                      Date("endDay", flags="patch"),
                      Int("domainStatus", flags="patch", filter="set")),
                     ({"attr": "syncPolicy", "flags": "patch"},
                      {"attr": "chat", "flags": "patch"},
                      RefProp("homeserver", "homeserverID", flags="patch", filter="set", qopt=selectinload)),
                     (Text("homedir", match=False, flags="hidden"),
                      Text("chatID", flags="hidden"),
                      Int("homeserverID", flags="hidden")))

    NORMAL = 0
    SUSPENDED = 1
    DELETED = 3

    _team = None

    def __init__(self, props: dict, *args, **kwargs):
        if "password" in props:
            self.password = props.pop("password")
        DataModel.__init__(self, props, args, kwargs)

    def fromdict(self, patches, *args, **kwargs):
        DataModel.fromdict(self, patches, args, kwargs)
        if self.chatID:
            with Service("chat", errors=Service.SUPPRESS_INOP) as chat:
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
            with Service("chat", errors=Service.SUPPRESS_ALL) as grochat:
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
                with Service("redis", errors=Service.SUPPRESS_INOP) as r:
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
        from .misc import DBConf
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
            if printStatus:
                print("Done.")
        nosync = {"synchronize_session": False}
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
        DBConf.query.filter(DBConf.service == "grommunio-admin", DBConf.file == "defaults-domain-"+str(self.ID))\
                    .delete(**nosync)
        DB.session.delete(self)

    @staticmethod
    def create(props, createRole=True, *args, **kwargs):
        def rolename(ID, name):
            maxlen = 32
            base = "Domain Admin ({}/{})"
            sublen = len(str(ID))+len(name)
            if len(base)+sublen-4 > maxlen:
                name = name[:maxlen-sublen-len(base)+3]+"…"
            return base.format(ID, name)

        from .roles import AdminRoles
        from orm.misc import Servers
        from tools.storage import DomainSetup
        from tools.misc import AutoClean
        error = Domains.checkCreateParams(props)
        chat = props.pop("chat", None)
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
                domain.homeserverID, domain.homedir = Servers.allocDomain(domain.ID, props.get("homeserver"))
                with DomainSetup(domain, DB.session) as ds:
                    ds.run()
                if not ds.success:
                    return "Error during domain setup: "+ds.error, ds.errorCode
                if chat:
                    domain.chat = chat
                DB.session.commit()
            domainAdminRoleName = rolename(domain.ID, domain.domainname)
            if createRole and AdminRoles.query.filter(AdminRoles.name == domainAdminRoleName).count() == 0:
                DB.session.add(AdminRoles({"name": domainAdminRoleName,
                                           "description": "Domain administrator for "+domain.domainname,
                                           "permissions": [{"permission": "DomainAdmin", "params": domain.ID}]}))
                DB.session.commit()
            return domain, 201
        except IntegrityError as err:
            return "Object violates database constraints ({})".format(err.orig.args[1]), 400

    @validates("homeserverID")
    def checkHomeserver(self, key, value, *args):
        from tools.config import Config
        if self.homeserverID and value != self.homeserverID and Config["options"].get("serverExplicitMount"):
            raise ValueError("Cannot change homeserver with explicitly mounted home-directories")
        from .misc import Servers
        if value and Servers.query.filter(Servers.ID == value).count() == 0:
            raise ValueError("Invalid homeserver")
        return value or 0

    @classmethod
    def _commit(cls, *args, **kwargs):
        with Service("systemd", errors=Service.SUPPRESS_ALL) as sysd:
            sysd.reloadService("gromox-delivery.service", "gromox-delivery-queue.service",
                               "gromox-http.service")


from .users import Users
from . import misc

if sqlalchemy.__version__.split(".") >= ["1", "4"]:
    inspect(Domains).add_property("activeUsers",
                                  column_property(select(func.count(Users.ID))
                                                  .where(Users.domainID == Domains.ID, Users.addressStatus == Users.NORMAL,
                                                         Users.maildir != "")
                                                  .scalar_subquery()))
    inspect(Domains).add_property("inactiveUsers",
                                  column_property(select(func.count(Users.ID))
                                                  .where(Users.domainID == Domains.ID,
                                                         Users.addressStatus.not_in((Users.NORMAL, Users.SHARED)),
                                                         Users.maildir != "")
                                                  .scalar_subquery()))
    inspect(Domains).add_property("virtualUsers",
                                  column_property(select(func.count(Users.ID))
                                                  .where(Users.domainID == Domains.ID, (Users.addressStatus == Users.SHARED) |
                                                         (Users.maildir == ""))
                                                  .scalar_subquery()))
else:
    inspect(Domains).add_property("activeUsers",
                                  column_property(select([func.count(Users.ID)])
                                                  .where((Users.domainID == Domains.ID) &
                                                         (Users.addressStatus == Users.NORMAL) & (Users.maildir != ""))
                                                  .as_scalar()))
    inspect(Domains).add_property("inactiveUsers",
                                  column_property(select([func.count(Users.ID)])
                                                  .where((Users.domainID == Domains.ID) &
                                                         (Users.addressStatus != Users.NORMAL) &
                                                         (Users.addressStatus != Users.SHARED) & (Users.maildir != ""))
                                                  .as_scalar()))
    inspect(Domains).add_property("virtualUsers",
                                  column_property(select([func.count(Users.ID)])
                                                  .where((Users.domainID == Domains.ID) &
                                                         ((Users.addressStatus == Users.SHARED) | (Users.maildir == "")))
                                                  .as_scalar()))

Domains.NTregister()
