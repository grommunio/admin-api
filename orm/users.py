# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grammm GmbH

from . import DB
from tools.constants import PropTags, PropTypes
from tools.rop import ntTime, nxTime
from tools.DataModel import DataModel, Id, Text, Int, Date, BoolP, RefProp
from tools.misc import createMapping

from sqlalchemy import func, ForeignKey
from sqlalchemy.dialects.mysql import INTEGER, TINYINT
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship, selectinload

import crypt
import re
import time
from datetime import datetime


class Groups(DataModel, DB.Model):
    __tablename__ = "groups"

    ID = DB.Column("id", INTEGER(10, unsigned=True), nullable=False, primary_key=True, unique=True)
    groupname = DB.Column("groupname", DB.VARCHAR(128), nullable=False, unique=True)
    domainID = DB.Column("domain_id", INTEGER(10, unsigned=True), nullable=False, index=True)
    maxUser = DB.Column("max_user", INTEGER(10, unsigned=True), nullable=False)
    title = DB.Column("title", DB.VARCHAR(128), nullable=False)
    createDay = DB.Column("create_day", DB.DATE, nullable=False)
    groupStatus = DB.Column("group_status", TINYINT, nullable=False, server_default="0")

    _dictmapping_ = ((Id(), Text("title", flags="patch"), Text("groupname", flags="init")),
                     (Id("domainID", flags="init"),
                      Int("maxSize", flags="patch"),
                      Int("maxUser", flags="patch"),
                      Date("createDay", flags="init")),
                     (Int("groupStatus", flags="init"),))


    NORMAL = 0
    SUSPEND = 1

    @staticmethod
    def checkCreateParams(data):
        from orm.domains import Domains
        domain = Domains.query.filter(Domains.ID == data.get("domainID")).first()
        if domain is None:
            return "Invalid domain"
        if domain.domainType != Domains.NORMAL:
            return "Domain cannot be alias"
        if "groupname" not in data:
            return "Missing required property 'groupname'"
        if "@" in data["groupname"] and data["groupname"].split("@")[1] != domain.domainname:
            return "Domain specifications mismatch."
        data["groupStatus"] = data.get("groupStatus", 0) + (domain.domainStatus << 2)
        data["createDay"] = datetime.now()

    def __init__(self, props, *args, **kwargs):
        self.fromdict(props)


class Users(DataModel, DB.Model):
    __tablename__ = "users"

    ID = DB.Column("id", INTEGER(10, unsigned=True), nullable=False, primary_key=True, unique=True)
    username = DB.Column("username", DB.VARCHAR(128), nullable=False, unique=True)
    _password = DB.Column("password", DB.VARCHAR(40), nullable=False, server_default="")
    groupID = DB.Column("group_id", INTEGER(10, unsigned=True), nullable=False, index=True, default=0)
    domainID = DB.Column("domain_id", INTEGER(10, unsigned=True), nullable=False, index=True)
    maildir = DB.Column("maildir", DB.VARCHAR(128), nullable=False, server_default="")
    addressStatus = DB.Column("address_status", TINYINT, nullable=False, server_default="0")
    privilegeBits = DB.Column("privilege_bits", INTEGER(10, unsigned=True), nullable=False, default=0)
    _deprecated_maxSize = DB.Column("max_size", INTEGER(10), nullable=False, default=0)
    _deprecated_maxFile = DB.Column("max_file", INTEGER(10), nullable=False, default=0)

    roles = relationship("AdminRoles", secondary="admin_user_role_relation", cascade="all, delete")
    properties = relationship("UserProperties", cascade="all, delete-orphan", single_parent=True)
    aliases = relationship("Aliases", cascade="all, delete-orphan", single_parent=True)

    _dictmapping_ = ((Id(), Text("username", flags="init")),
                     (Id("domainID", flags="init"),
                      Id("groupID", flags="patch")),
                     (RefProp("roles", qopt=selectinload),
                      RefProp("properties", flags="patch, managed", link="name", qopt=selectinload),
                      RefProp("aliases", flags="patch, managed", link="aliasname", flat="aliasname", qopt=selectinload),
                      BoolP("pop3_imap", flags="patch"),
                      BoolP("smtp", flags="patch"),
                      BoolP("changePassword", flags="patch"),
                      BoolP("publicAddress", flags="patch"),
                      BoolP("netDisk", flags="patch")),
                     ({"attr": "password", "flags": "init, hidden"},))

    POP3_IMAP = 1 << 0
    SMTP = 1 << 1
    CHGPASSWD = 1 << 2
    PUBADDR = 1 << 3
    NETDISK = 1 << 4

    MAILUSER = 0x0
    DISTLIST = 0x1
    FORUM = 0x2
    AGENT = 0x3
    ORGANIZATION = 0x4
    PRIVATE_DISTLIST = 0x5
    REMOTE_MAILUSER = 0x6
    ROOM = 0x7
    EQUIPMENT = 0x8
    SEC_DISTLIST = 0x9
    CONTAINER = 0x100
    TEMPLATE = 0x101
    ADDRESS_TEMPLATE = 0x102
    SEARCH = 0x200

    @staticmethod
    def checkCreateParams(data):
        from orm.domains import Domains
        from tools.license import getLicense
        if Users.query.count() >= getLicense().users:
            return "License user limit exceeded"
        domain = Domains.query.filter(Domains.ID == data.get("domainID")).first()
        if not domain:
            return "Invalid domain"
        data["domain"] = domain
        domainUsers = Users.query.with_entities(func.count().label("count")).filter(Users.domainID == domain.ID).first()
        if domain.maxUser <= domainUsers.count:
            return "Maximum number of domain users reached"
        if data.get("groupID"):
            group = Groups.query.filter(Groups.ID == data.get("groupID"), Groups.domainID == domain.ID).first()
            if group is None:
                return "Invalid group"
            groupUsers = Users.query.with_entities(func.count().label("count")).filter(Users.groupID == group.ID).first()
            if group.maxUser <= groupUsers.count:
                return "Maximum number of group users reached"
            data["groupStatus"] =  group.groupStatus
        else:
            data["groupID"] = 0
        data["domainStatus"] = domain.domainStatus
        if "properties" not in data:
            return "Missing required attribute 'properties'"
        propmap = createMapping(data["properties"], lambda x: x["name"], lambda x: x)
        if "storagequotalimit" not in propmap:
            return "Missing required property 'storagequotalimit'"
        for prop in ("prohibitreceivequota", "prohibitsendquota"):
            if prop not in propmap:
                data["properties"].append({"name": prop, "val": propmap["storagequotalimit"]["val"]})
        if "creationtime" not in propmap:
            data["properties"].append({"name": "creationtime", "val": datetime.now()})
        else:
            propmap["creationtime"]["val"] = datetime.now()
        if "displaytypeex" not in propmap:
            data["properties"].append({"name": "displaytypeex", "val": 0})


    def __init__(self, props, *args, **kwargs):
        self._permissions = None
        if props is None:
            return
        status = props.pop("groupStatus", 0) << 2 | props.pop("domainStatus") << 4
        self.fromdict(props, *args, **kwargs)
        self.addressStatus = (self.addressStatus or 0) | status
        self.addressType = 0

    def fromdict(self, patches, *args, **kwargs):
        if "username" in patches:
            from orm.domains import Domains
            username = patches.pop("username")
            domain = patches.pop("domain", None) or Domains.query.filter(Domains.ID == self.domainID).first()
            if "@" in username:
                if username.split("@",1)[1] != domain.domainname:
                    raise ValueError("Domain specifications mismatch.")
                self.username = username
            else:
                self.username = username+"@"+domain.domainname
        DataModel.fromdict(self, patches, args, kwargs)

    def baseName(self):
        return self.username.rsplit("@", 1)[0]

    def domainName(self):
        return self.username.rsplit("@", 1)[0] if "@" in self.username else None

    def permissions(self):
        if self.ID == 0:
            from tools.permissions import Permissions
            return Permissions.sysadmin()
        if not hasattr(self, "_permissions") or self._permissions is None:
            from .roles import AdminUserRoleRelation as AURR, AdminRolePermissionRelation as ARPR, AdminRoles as AR
            from tools.permissions import Permissions
            perms = ARPR.query.filter(AURR.userID == self.ID).join(AR).join(AURR).all()
            self._permissions = Permissions.fromDB(perms)
        return self._permissions

    @property
    def password(self):
        return self._password

    @password.setter
    def password(self, pw):
        self._password = crypt.crypt(pw, crypt.mksalt(crypt.METHOD_MD5))

    def chkPw(self, pw):
        return crypt.crypt(pw, self.password) == self.password

    @property
    def propmap(self, refresh=False):
        if refresh or not hasattr(self, "_propmap"):
            self._propmap = createMapping(self.properties, lambda x: x.name, lambda x: x.val)
        return self._propmap

    def _setPB(self, bit, val):
        self.privilegeBits = (self.privilegeBits or 0) | bit if val else (self.privilegeBits or 0) & ~bit

    def _getPB(self, bit):
        return bool((self.privilegeBits or 0) & bit) if isinstance(self, Users) else self.privilegeBits

    @hybrid_property
    def pop3_imap(self):
        return self._getPB(self.POP3_IMAP)

    @pop3_imap.setter
    def pop3_imap(self, val):
        self._setPB(self.POP3_IMAP, val)

    @pop3_imap.expression
    def pop3_imap(cls):
        return cls.privilegeBits.op("&")(cls.POP3_IMAP)

    @hybrid_property
    def smtp(self):
        return self._getPB(self.SMTP)

    @smtp.setter
    def smtp(self, val):
        self._setPB(self.SMTP, val)

    @smtp.expression
    def smtp(cls):
        return cls.privilegeBits.op("&")(cls.SMTP)

    @hybrid_property
    def changePassword(self):
        return self._getPB(self.CHGPASSWD)

    @changePassword.setter
    def changePassword(self, val):
        self._setPB(self.CHGPASSWD, val)

    @changePassword.expression
    def changePassword(cls):
        return cls.privilegeBits.op("&")(cls.CHGPASSWD)

    @hybrid_property
    def publicAddress(self):
        return self._getPB(self.PUBADDR)

    @publicAddress.setter
    def publicAddress(self, val):
        self._setPB(self.PUBADDR, val)

    @publicAddress.expression
    def publicAddress(cls):
        return cls.privilegeBits.op("&")(cls.PUBADDR)

    @hybrid_property
    def netDisk(self):
        return self._getPB(self.NETDISK)

    @netDisk.setter
    def netDisk(self, val):
        self._setPB(self.NETDISK, val)

    @netDisk.expression
    def netDisk(cls):
        return cls.privilegeBits.op("&")(cls.NETDISK)


class UserProperties(DataModel, DB.Model):
    __tablename__ = "user_properties"

    supportedTypes = PropTypes.intTypes | PropTypes.floatTypes | {PropTypes.STRING, PropTypes.WSTRING, PropTypes.BINARY}

    userID = DB.Column("user_id", INTEGER(unsigned=True), ForeignKey(Users.ID), primary_key=True)
    tag = DB.Column("proptag", INTEGER(unsigned=True), primary_key=True, index=True)
    _propvalbin = DB.Column("propval_bin", DB.VARBINARY(4096))
    _propvalstr = DB.Column("propval_str", DB.VARCHAR(4096))

    user = relationship(Users)

    _dictmapping_ = (({"attr": "name", "flags": "init"},{ "attr": "val", "flags": "patch"}), (Int("userID"),))

    def __init__(self, props, user, *args, **kwargs):
        self.user = user
        if "tag" in props and props["tag"] & 0xFFFF not in self.supportedTypes:
            raise NotImplementedError("Prop type is currently not supported")
        self.fromdict(props, *args, **kwargs)

    @property
    def name(self):
        if self.tag is None:
            return None
        tagname = PropTags.lookup(self.tag, None)
        return tagname.lower() if tagname else "<unknown>"

    @name.setter
    def name(self, value):
        tag = getattr(PropTags, value.upper(), None)
        if tag is None:
            raise ValueError("Unknown PropTag '{}'".format(value))
        if tag & 0xFFFF not in self.supportedTypes:
            raise ValueError("This tag type is not supported")
        self.tag = tag

    @property
    def type(self):
        return self.tag & 0xFFFF

    @property
    def val(self):
        if self.type == PropTypes.BINARY:
            return self._propvalbin
        if self.type == PropTypes.FILETIME:
            return datetime.fromtimestamp(nxTime(int(self._propvalstr))).strftime("%Y-%m-%d %H:%M:%S")
        return PropTypes.pyType(self.type)(self._propvalstr)

    @val.setter
    def val(self, value):
        if self.type == PropTypes.FILETIME:
            if not isinstance(value, datetime):
                try:
                    value = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
                except TypeError:
                    raise ValueError("Invalid date '{}'".format(value))
            value = ntTime(time.mktime(value.timetuple()))
        if type(value) != PropTypes.pyType(self.type):
            raise ValueError("Value type does not match tag type")
        if self.type == PropTypes.BINARY:
            self._propvalbin = value
        else:
            self._propvalstr = str(value)


DB.Index("uq_domain_id_username", Users.domainID, Users.username, unique=True)
DB.Index("uq_group_id_username", Users.groupID, Users.username, unique=True)


class Aliases(DataModel, DB.Model):
    __tablename__ = "aliases"

    emailRe = re.compile(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)")

    aliasname = DB.Column("aliasname", DB.VARCHAR(128), nullable=False, unique=True, primary_key=True)
    mainname = DB.Column("mainname", DB.VARCHAR(128), ForeignKey(Users.username, ondelete="cascade", onupdate="cascade"),
                         nullable=False, index=True)

    main = relationship(Users)

    _dictmapping_ = ((Text("aliasname", flags="init"),),
                     (Text("mainname", flags="init"),))

    def __init__(self, aliasname, main, *args, **kwargs):
        if main.ID == 0:
            raise ValueError("Cannot alias superuser")
        if not self.emailRe.match(aliasname):
            raise ValueError("'{}' is not a valid email address".format(aliasname))
        self.aliasname = aliasname
        self.main = main
