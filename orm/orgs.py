# -*- coding: utf-8 -*-
"""
Created on Tue Jun 23 12:21:35 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: Grammm GmbH, 2020
"""

from . import DB
from .DataModel import DataModel, Id, Text, Int, Date, BoolP
from .ext import AreaList

from sqlalchemy.dialects.mysql import INTEGER, TINYINT

import crypt
from datetime import datetime


class Orgs(DataModel, DB.Model):
    __tablename__ = "orgs"

    ID = DB.Column("id", INTEGER(10, unsigned=True), unique=True, primary_key=True, nullable=False)
    memo = DB.Column("memo", DB.VARCHAR(128), nullable=False, server_default="")

    _dictmapping_ = ((Id(), Text("memo", flags="patch")),)


class Domains(DataModel, DB.Model):
    __tablename__ = "domains"

    ID = DB.Column("id", INTEGER(10, unsigned=True), unique=True, primary_key=True, nullable=False)
    orgID = DB.Column("org_id", INTEGER(10, unsigned=True), nullable=False, server_default="0", index=True)
    domainname = DB.Column("domainname", DB.VARCHAR(64), nullable=False)
    _password = DB.Column("password", DB.VARCHAR(40), nullable=False, server_default="")
    homedir = DB.Column("homedir", DB.VARCHAR(128), nullable=False, server_default="")
    media = DB.Column("media", DB.VARCHAR(64), nullable=False, server_default="")
    maxSize = DB.Column("max_size", INTEGER(10, unsigned=True), nullable=False)
    maxUser = DB.Column("max_user", INTEGER(10, unsigned=True), nullable=False)
    title = DB.Column("title", DB.VARCHAR(128), nullable=False, server_default="")
    address = DB.Column("address", DB.VARCHAR(128), nullable=False, server_default="")
    adminName = DB.Column("admin_name", DB.VARCHAR(32), nullable=False, server_default="")
    tel = DB.Column("tel", DB.VARCHAR(64), nullable=False, server_default="")
    createDay = DB.Column("create_day", DB.DATE , nullable=False)
    endDay = DB.Column("end_day", DB.DATE, nullable=False)
    privilegeBits = DB.Column("privilege_bits", INTEGER(10, unsigned=True), nullable=False, default=0)
    domainStatus = DB.Column("domain_status", TINYINT, nullable=False, server_default="0")
    domainType = DB.Column("domain_type", TINYINT, nullable=False, server_default="0")

    _dictmapping_ = ((Id(),),
                     (Id("orgID", flags="patch"),
                      Text("domainname", flags="patch"),
                      Text("homedir"),
                      Text("media", flags="patch"),
                      Int("maxSize", flags="patch"),
                      Int("maxUser", flags="patch"),
                      Text("title", flags="patch"),
                      Text("address", flags="patch"),
                      Text("adminName", flags="patch"),
                      Text("tel", flags="patch"),
                      Date("createDay", flags="patch"),
                      Date("endDay", flags="patch"),
                      Int("domainStatus", flags="patch"),
                      Int("domainType", flags="patch"),
                      BoolP("mailBackup", flags="patch"),
                      BoolP("mailMonitor", flags="patch"),
                      BoolP("ignoreCheckingUser", flags="patch"),
                      BoolP("mailSubSystem", flags="patch"),
                      BoolP("netDisk", flags="patch")))

    BACKUP = 1 << 0
    MONITOR = 1 << 1
    UNCHECKUSR = 1 << 2
    SUBSYSTEM = 1 << 3
    NETDISK = 1 << 4
    EXTPASSWD = 1 << 5

    NORMAL = 0
    ALIAS = 1

    def __init__(self, props: dict, *args, **kwargs):
        props.pop("areaID")
        if "password" in props:
            self.password = props.pop("password")
        DataModel.__init__(self, props, args, kwargs)

    @staticmethod
    def checkCreateParams(data):
        if "areaID" not in data:
            return "Missing required property areaID"
        elif AreaList.query.filter(AreaList.dataType == AreaList.DOMAIN, AreaList.ID == data["areaID"]).count() == 0:
            return "Invalid area ID"
        if data.get("createDay") is None:
            data["createDay"] = datetime.now()

    def _setFlag(self, flag, val):
        self.privilegeBits = (self.privilegeBits or 0) | flag if val else (self.privilegeBits or 0) & ~flag

    def _getFlag(self, flag):
        return bool(self.privilegeBits or 0 & flag)

    @property
    def mailBackup(self):
        return self._getFlag(self.BACKUP)

    @mailBackup.setter
    def mailBackup(self, val):
        self._setFlag(self.BACKUP, val)

    @property
    def mailMonitor(self):
        return self._getFlag(self.MONITOR)

    @mailMonitor.setter
    def mailMonitor(self, val):
        self._setFlag(self.MONITOR, val)

    @property
    def ignoreCheckingUser(self):
        return self._getFlag(self.UNCHECKUSR)

    @ignoreCheckingUser.setter
    def ignoreCheckingUser(self, val):
        self._setFlag(self.UNCHECKUSR, val)

    @property
    def mailSubSystem(self):
        return self._getFlag(self.SUBSYSTEM)

    @mailSubSystem.setter
    def mailSubSystem(self, val):
        self._setFlag(self.SUBSYSTEM, val)

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


DB.Index(Domains.homedir, Domains.domainType)


class Aliases(DataModel, DB.Model):
    __tablename__ = "aliases"

    ID = DB.Column("id", INTEGER(10, unsigned=True), unique=True, primary_key=True, nullable=False)
    aliasname = DB.Column("aliasname", DB.VARCHAR(128), nullable=False, unique=True)
    mainname = DB.Column("mainname", DB.VARCHAR(128), nullable=False, index=True)

    _dictmapping_ = ((Id(), Text("aliasname", flags="patch"), Text("mainname", flags="patch")),)
