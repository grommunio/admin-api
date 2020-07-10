# -*- coding: utf-8 -*-
"""
Created on Tue Jun 23 13:59:32 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: Grammm GmbH, 2020
"""

from . import DB
from .DataModel import DataModel, Id, Text, Int, Date, BoolP
from .ext import AreaList

from sqlalchemy import func
from sqlalchemy.dialects.mysql import INTEGER, TINYINT

import crypt


class Groups(DataModel, DB.Model):
    __tablename__ = "groups"

    ID = DB.Column("id", INTEGER(10, unsigned=True), nullable=False, primary_key=True, unique=True)
    groupname = DB.Column("groupname", DB.VARCHAR(128), nullable=False, unique=True)
    password = DB.Column("password", DB.VARCHAR(40), nullable=False, server_default="")
    domainID = DB.Column("domain_id", INTEGER(10, unsigned=True), nullable=False, index=True)
    maxSize = DB.Column("max_size", INTEGER(10, unsigned=True), nullable=False)
    maxUser = DB.Column("max_user", INTEGER(10, unsigned=True), nullable=False)
    title = DB.Column("title", DB.VARCHAR(128), nullable=False)
    createDay = DB.Column("create_day", DB.DATE, nullable=False)
    privilegeBits = DB.Column("privilege_bits", INTEGER(10, unsigned=True), nullable=False)
    groupStatus = DB.Column("group_status", TINYINT, nullable=False, server_default="0")

    _dictmapping_ = ((Id(), Text("groupname", flags="patch")),
                     (Text("password", flags="patch"),
                      Id("domainID", flags="patch"),
                      Int("maxSize", flags="patch"),
                      Int("maxUser", flags="patch"),
                      Text("title", flags="patch"),
                      Date("createDay", flags="patch"),
                      Int("privilegeBits", flags="patch"),
                      Int("groupStatus", flags="patch"),
                      BoolP("backup", flags="patch"),
                      BoolP("monitor", flags="patch"),
                      BoolP("log", flags="patch"),
                      BoolP("account", flags="patch")))

    BACKUP = 1 << 0
    MONITOR = 1 << 1
    LOG = 1 << 2
    ACCOUNT = 1 << 3
    DOMAIN_BACKUP = 1 << 8
    DOMAIN_MONITOR = 1 << 9

    def _setFlag(self, flag, val):
        self.privilegeBits = (self.privilegeBits or 0) | flag if val else (self.privilegeBits or 0) & ~flag

    def _getFlag(self, flag):
        return bool(self.privilegeBits or 0 & flag)

    @property
    def backup(self):
        return self._getFlag(self.BACKUP)

    @backup.setter
    def backup(self, val):
        self._setFlag(self.BACKUP, val)

    @property
    def monitor(self):
        return self._getFlag(self.MONITOR)

    @monitor.setter
    def monitor(self, val):
        self._setFlag(self.MONITOR, val)

    @property
    def log(self):
        return self._getFlag(self.LOG)

    @log.setter
    def log(self, val):
        self._setFlag(self.LOG, val)

    @property
    def account(self):
        return self._getFlag(self.ACCOUNT)

    @account.setter
    def account(self, val):
        self._setFlag(self.ACCOUNT, val)

    @property
    def domainBackup(self):
        return self._getFlag(self.DOMAIN_BACKUP)

    @domainBackup.setter
    def domainBackup(self, val):
        self._setFlag(self.DOMAIN_BACKUP, val)

    @property
    def domainMonitor(self):
        return self._getFlag(self.DOMAIN_MONITOR)

    @domainMonitor.setter
    def domainMonitor(self, val):
        self._setFlag(self.DOMAIN_MONITOR, val)


class Users(DataModel, DB.Model):
    __tablename__ = "users"

    ID = DB.Column("id", INTEGER(10, unsigned=True), nullable=False, primary_key=True, unique=True)
    username = DB.Column("username", DB.VARCHAR(128), nullable=False, unique=True)
    _password = DB.Column("password", DB.VARCHAR(40), nullable=False, server_default="")
    realName = DB.Column("real_name", DB.VARCHAR(32), nullable=False, server_default="")
    title = DB.Column("title", DB.VARCHAR(128), nullable=False, server_default="")
    memo = DB.Column("memo", DB.VARCHAR(128), nullable=False, server_default="")
    domainID = DB.Column("domain_id", INTEGER(10, unsigned=True), nullable=False, index=True)
    groupID = DB.Column("group_id", INTEGER(10, unsigned=True), nullable=False, index=True)
    maildir = DB.Column("maildir", DB.VARCHAR(128), nullable=False, server_default="")
    maxSize = DB.Column("max_size", INTEGER(10, unsigned=True), nullable=False)
    maxFile = DB.Column("max_file", INTEGER(10, unsigned=True), nullable=False)
    createDay = DB.Column("create_day", DB.DATE, nullable=False)
    lang = DB.Column("lang", DB.VARCHAR(32), nullable=False, server_default="")
    timezone = DB.Column("timezone", DB.VARCHAR(64), nullable=False, server_default="")
    mobilePhone = DB.Column("mobile_phone", DB.VARCHAR(20), nullable=False, server_default="")
    privilegeBits = DB.Column("privilege_bits", INTEGER(10, unsigned=True), nullable=False)
    subType = DB.Column("sub_type", TINYINT, nullable=False, server_default='0')
    addressStatus = DB.Column("address_status", TINYINT, nullable=False, server_default="0")
    addressType = DB.Column("address_type", TINYINT, nullable=False, server_default="0")
    cell = DB.Column("cell", DB.VARCHAR(20), nullable=False, server_default="")
    tel = DB.Column("tel", DB.VARCHAR(20), nullable=False, server_default="")
    nickname = DB.Column("nickname", DB.VARCHAR(32), nullable=False, server_default="")
    homeaddress = DB.Column("homeaddress", DB.VARCHAR(128), nullable=False, server_default="")

    _dictmapping_ = ((Id(), Text("username", flags="patch")),
                     (Text("realName", flags="patch"),
                      Text("title", flags="patch"),
                      Text("memo", flags="patch"),
                      Id("domainID", flags="patch"),
                      Id("groupID", flags="patch"),
                      Text("maildir"),
                      Int("maxSize", flags="patch"),
                      Int("maxFile", flags="patch"),
                      Date("createDay", flags="patch"),
                      Text("lang", flags="patch"),
                      Text("timezone", flags="patch"),
                      Text("mobilePhone", flags="patch"),
                      Int("subType", flags="patch"),
                      Int("addressStatus", flags="init"),
                      Text("cell", flags="patch"),
                      Text("tel", flags="patch"),
                      Text("nickname", flags="patch"),
                      Text("homeaddress", flags="patch"),
                      BoolP("pop3_imap", flags="patch"),
                      BoolP("smtp", flags="patch"),
                      BoolP("changePassword", flags="patch"),
                      BoolP("publicAddress", flags="patch"),
                      BoolP("netDisk", flags="patch")))

    POP3_IMAP = 1 << 0
    SMTP = 1 << 1
    CHGPASSWD = 1 << 2
    PUBADDR = 1 << 3
    NETDISK = 1 << 4

    def _setFlag(self, flag, val):
        self.privilegeBits = (self.privilegeBits or 0) | flag if val else (self.privilegeBits or 0) & ~flag

    def _getFlag(self, flag):
        return bool(self.privilegeBits or 0 & flag)

    @property
    def pop3_imap(self):
        return self._getFlag(self.POP3_IMAP)

    @pop3_imap.setter
    def pop3_imap(self, val):
        self._setFlag(self.POP3_IMAP, val)

    @property
    def smtp(self):
        return self._getFlag(self.SMTP)

    @smtp.setter
    def smtp(self, val):
        self._setFlag(self.SMTP, val)

    @property
    def changePassword(self):
        return self._getFlag(self.CHGPASSWD)

    @changePassword.setter
    def changePassword(self, val):
        self._setFlag(self.CHGPASSWD, val)

    @property
    def publicAddress(self):
        return self._getFlag(self.PUBADDR)

    @publicAddress.setter
    def publicAddress(self, val):
        self._setFlag(self.PUBADDR, val)

    @property
    def netDisk(self):
        return self._getFlag(self.NETDISK)

    @netDisk.setter
    def netDisk(self, val):
        self._setFlag(self.NETDISK, val)

    @property
    def password(self):
        return self._password

    @password.setter
    def password(self, pw):
        self._password = crypt.crypt(pw, crypt.mksalt(crypt.METHOD_MD5))

    def chkPw(self, pw):
        return crypt.crypt(pw, self.password) == self.password

    @staticmethod
    def checkCreateParams(data):
        from orm.orgs import Domains, Aliases
        domain = Domains.query.filter(Domains.ID == data.get("domainID")).first()
        if not domain:
            return "Invalid domain"
        if domain.domainType != Domains.NORMAL:
            return "Domain must not be alias"
        domainUsers = Users.query.with_entities(func.count().label("count"), func.sum(Users.maxSize).label("size"))\
                                 .filter(Users.domainID == domain.ID).first()
        if domain.maxUser <= domainUsers.count:
            return "Maximum number of domain users reached"
        if domain.maxSize < (domainUsers.size or 0)+data.get("maxSize"):
            return "Maximum domain size reached"
        if data.get("groupID"):
            group = Groups.query.filter(Groups.ID == data.get("groupID")).first()
            if group is None:
                return "Invalid group"
            if group.domainID != domain.ID:
                return "Group must be in the same domain"
            groupUsers = Users.query.with_entities(func.count().label("count"), func.sum(Users.maxSize).label("size"))\
                                    .filter(Users.groupID == group.ID).first()
            if group.maxUser <= groupUsers.count:
                return "Maximum number of group users reached"
            if group.maxSize < groupUsers.size+data.get("maxSize"):
                return "Maximum group size reached"
            data["groupPrivileges"] = group.privilegeBits
            data["groupStatus"] =  group.groupStatus
        data["domainPrivileges"] = domain.privilegeBits
        data["domainStatus"] = domain.domainStatus
        data["aliases"] = [alias.aliasname for alias in Aliases.query.filter(Aliases.mainname == domain.domainname).all()]
        if "areaID" not in data:
            return "Missing required property areaID"
        if AreaList.query.filter(AreaList.dataType == AreaList.USER, AreaList.ID == data["areaID"]).count() == 0:
            return "Invalid area ID"
        if "@" in data["username"]:
            if data["username"].split("@",1)[1] != domain.domainname:
                return "Domain specifications mismatch."
        else:
            data["username"] += "@"+domain.domainname

    def __init__(self, props, isAlias=False, privileges=None, status=None, *args, **kwargs):
        aliases = props.pop("aliases", [])
        privileges = privileges or props.pop("groupPrivileges", 0xFF) << 8 | props.pop("domainPrivileges", 0) << 16
        status = status or props.pop("groupStatus", 0) << 2 | props.pop("domainStatus") << 4
        props.pop("areaID")
        if "password" in props:
            self.password = props.pop("password")
        for alias in aliases:
            DB.session.add(Users(props, True, privileges, status, *args, **kwargs))
        self.fromdict(props, *args, **kwargs)
        self.privilegeBits = (self.privilegeBits or 0) | privileges
        self.addressStatus = (self.addressStatus or 0) | status
        self.addressType = 3 if isAlias else 0


DB.Index(Users.domainID, Users.username, unique=True)
DB.Index(Users.groupID, Users.username, unique=True)
DB.Index(Users.maildir, Users.addressType)