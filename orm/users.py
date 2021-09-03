# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020-2021 grommunio GmbH

from . import DB, OptionalC, OptionalNC, NotifyTable, logger
from services import Service
from tools import formats
from tools.constants import PropTags, PropTypes
from tools.DataModel import DataModel, Id, Text, Int, BoolP, RefProp, Bool, Date
from tools.DataModel import InvalidAttributeError, MismatchROError, MissingRequiredAttributeError
from tools.rop import ntTime, nxTime

from sqlalchemy import Column, ForeignKey, func
from sqlalchemy.dialects.mysql import ENUM, INTEGER, TEXT, TIMESTAMP, TINYINT, VARBINARY, VARCHAR
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.declarative.api import DeclarativeMeta
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship, selectinload, validates
from sqlalchemy.orm.collections import attribute_mapped_collection

import crypt
import json
import time
from datetime import datetime


class Users(DataModel, DB.Base, NotifyTable):
    __tablename__ = "users"

    ID = Column("id", INTEGER(10, unsigned=True), nullable=False, primary_key=True, unique=True)
    username = Column("username", VARCHAR(128), nullable=False, unique=True)
    _password = Column("password", VARCHAR(40), nullable=False, server_default="")
    domainID = Column("domain_id", INTEGER(10, unsigned=True), nullable=False, index=True)
    maildir = Column("maildir", VARCHAR(128), nullable=False, server_default="")
    addressStatus = Column("address_status", TINYINT, nullable=False, server_default="0")
    privilegeBits = Column("privilege_bits", INTEGER(10, unsigned=True), nullable=False, default=0)
    externID = Column("externid", VARBINARY(64))
    chatID = OptionalC(78, "NULL", Column("chat_id", VARCHAR(26)))
    _syncPolicy = OptionalC(76, "NULL", Column("sync_policy", TEXT))
    _deprecated_maxSize = Column("max_size", INTEGER(10), nullable=False, default=0)
    _deprecated_addressType = Column("address_type", TINYINT, nullable=False, server_default="0")
    _deprecated_subType = Column("sub_type", TINYINT, nullable=False, server_default="0")
    _deprecated_groupID = Column("group_id", INTEGER(10, unsigned=True), nullable=False, index=True, default=0)

    domain = relationship("Domains", foreign_keys=domainID, primaryjoin="Users.domainID == Domains.ID")
    roles = relationship("AdminRoles", secondary="admin_user_role_relation")
    properties = relationship("UserProperties", cascade="all, delete-orphan", single_parent=True,
                              collection_class=attribute_mapped_collection("name"), passive_deletes=True)
    aliases = relationship("Aliases", cascade="all, delete-orphan", single_parent=True, passive_deletes=True)
    fetchmail = OptionalNC(75, [],
                           relationship("Fetchmail", cascade="all, delete-orphan", single_parent=True, order_by="Fetchmail.active.desc()"))

    _dictmapping_ = ((Id(), Text("username", flags="init")),
                     (Id("domainID", flags="init"),
                      {"attr": "ldapID", "flags": "patch"}),
                     (Int("status", flags="patch"),
                      BoolP("pop3_imap", flags="patch"),
                      BoolP("smtp", flags="patch"),
                      BoolP("changePassword", flags="patch"),
                      BoolP("publicAddress", flags="patch"),
                      RefProp("aliases", flags="patch, managed", link="aliasname", flat="aliasname", qopt=selectinload),
                      RefProp("fetchmail", flags="managed, patch", link="ID", qopt=selectinload),
                      RefProp("properties", flags="patch, managed", link="name", flat="val", qopt=selectinload),
                      RefProp("roles", qopt=selectinload),
                      {"attr": "syncPolicy", "flags": "patch"},
                      {"attr": "chat", "flags": "patch"},
                      {"attr": "chatAdmin", "flags": "patch"}),
                     ({"attr": "password", "flags": "init, hidden"},))

    POP3_IMAP = 1 << 0
    SMTP = 1 << 1
    CHGPASSWD = 1 << 2
    PUBADDR = 1 << 3

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

    NORMAL = 0
    SUSPENDED = 1
    OUTOFDATE = 2
    DELETED = 3

    _chatUser = None

    @staticmethod
    def checkCreateParams(data):
        from orm.domains import Domains
        from tools.license import getLicense
        if Users.count() >= getLicense().users:
            return "License user limit exceeded"
        if "domainID" in data:
            domain = Domains.query.filter(Domains.ID == data.get("domainID")).first()
        elif "@" in data["username"]:
            domain = Domains.query.filter(Domains.domainname == data["username"].split("@")[1]).first()
        else:
            domain = None
        if domain is None:
            return "Invalid domain"
        if "@" in data["username"]:
            dname = data["username"].split("@", 1)[1]
            if domain.domainname != dname and domain.displayname != dname:
                return "Domain specifications do not match"
        data["domain"] = domain
        data["domainID"] = domain.ID
        domainUsers = Users.count(Users.domainID == domain.ID)
        if domain.maxUser <= domainUsers:
            return "Maximum number of domain users reached"
        data["domainStatus"] = domain.domainStatus
        if "properties" not in data:
            data["properties"] = {}
        properties = data["properties"]
        properties["creationtime"] = datetime.now()
        if "displaytypeex" not in properties:
            properties["displaytypeex"] = 0

    def __init__(self, props, *args, **kwargs):
        self._permissions = None
        if props is None:
            return
        status = props.pop("domainStatus") << 4
        self.fromdict(props, *args, **kwargs)
        self.addressStatus = (self.addressStatus or 0) | status

    def fromdict(self, patches, *args, **kwargs):
        if "username" in patches and patches["username"] != self.username:
            from orm.domains import Domains
            username = patches.pop("username")
            domain = patches.pop("domain", None) or Domains.query.filter(Domains.ID == self.domainID).first()
            if "@" in username:
                uname, dname = username.split("@",1)
                if dname != domain.domainname and dname != domain.displayname:
                    raise ValueError("Domain specifications mismatch.")
                self.username = uname+"@"+domain.domainname
            else:
                self.username = username+"@"+domain.domainname
            if not formats.email.match(self.username):
                raise ValueError("'{}' is not a valid e-mail address".format(self.username))
        DataModel.fromdict(self, patches, args, kwargs)
        displaytype = self.propmap.get("displaytypeex", 0)
        if displaytype in (0, 1, 7, 8):
            self._deprecated_addressType, self._deprecated_subType = self._decodeDisplayType(displaytype)
        if self.chatID:
            with Service("chat", Service.SUPPRESS_INOP) as chat:
                chat.updateUser(self, False)

    @staticmethod
    def _decodeDisplayType(displaytype):
        if displaytype == 0:
            return 0, 0
        elif displaytype == 1:
            return 2, 0
        elif displaytype == 7:
            return 0, 1
        elif displaytype == 8:
            return 0, 2
        raise ValueError("Unknown display type "+str(displaytype))


    def baseName(self):
        return self.username.rsplit("@", 1)[0]

    def domainName(self):
        return self.username.rsplit("@", 1)[1] if "@" in self.username else None

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

    def getProp(self, name):
        return self.properties[name].val if name in self.properties else None

    @property
    def password(self):
        return self._password

    @password.setter
    def password(self, pw):
        self._password = crypt.crypt(pw, crypt.mksalt(crypt.METHOD_MD5))

    def chkPw(self, pw):
        return crypt.crypt(pw, self.password) == self.password

    @property
    def propmap(self):
        return {k: v.val for k, v in self.properties.items()}

    @property
    def propmap_id(self):
        return {p.tag: p.val for p in self.properties.values()}

    @property
    def syncPolicy(self):
        try:
            return json.loads(self._syncPolicy)
        except Exception:
            return None

    @syncPolicy.setter
    def syncPolicy(self, value):
        self._syncPolicy = json.dumps(value, separators=(",", ":")) if value is not None else None

    def _setPB(self, bit, val):
        self.privilegeBits = (self.privilegeBits or 0) | bit if val else (self.privilegeBits or 0) & ~bit

    def _getPB(self, bit):
        return (self.privilegeBits) if isinstance(self, DeclarativeMeta) else bool((self.privilegeBits or 0) & bit)

    @hybrid_property
    def pop3_imap(self):
        return self._getPB(self.POP3_IMAP)

    @pop3_imap.setter
    def pop3_imap(self, val):
        self._setPB(self.POP3_IMAP, val)

    @pop3_imap.expression
    def pop3_imap(cls):
        return cls.privilegeBits.op("&")(cls.POP3_IMAP) != 0

    @hybrid_property
    def smtp(self):
        return self._getPB(self.SMTP)

    @smtp.setter
    def smtp(self, val):
        self._setPB(self.SMTP, val)

    @smtp.expression
    def smtp(cls):
        return cls.privilegeBits.op("&")(cls.SMTP) != 0

    @hybrid_property
    def changePassword(self):
        return self._getPB(self.CHGPASSWD)

    @changePassword.setter
    def changePassword(self, val):
        self._setPB(self.CHGPASSWD, val)

    @changePassword.expression
    def changePassword(cls):
        return cls.privilegeBits.op("&")(cls.CHGPASSWD) != 0

    @hybrid_property
    def publicAddress(self):
        return self._getPB(self.PUBADDR)

    @publicAddress.setter
    def publicAddress(self, val):
        self._setPB(self.PUBADDR, val)

    @publicAddress.expression
    def publicAddress(cls):
        return cls.privilegeBits.op("&")(cls.PUBADDR) != 0

    @property
    def ldapID(self):
        from services.ldap import LdapService
        return None if self.externID is None else LdapService.escape_filter_chars(self.externID)

    @ldapID.setter
    def ldapID(self, value):
        from services.ldap import LdapService
        self.externID = None if value is None else LdapService.unescapeFilterChars(value)

    @hybrid_property
    def status(self):
        return self.addressStatus & 0x3

    @status.setter
    def status(self, val):
        self.addressStatus = (self.addressStatus & ~0x3) | (val & 0x3)

    @status.expression
    def status(cls):
        return cls.addressStatus.op("&")(0x3)

    @hybrid_property
    def domainStatus(self):
        return self.addressStatus >> 4 & 0x3

    @status.setter
    def status(self, val):
        self.addressStatus = (self.addressStatus & ~0x30) | (val << 4 & 0x30)

    @property
    def chat(self):
        if not self.chatID:
            return False
        if self._chatUser is None:
            with Service("chat", Service.SUPPRESS_INOP) as chat:
                self._chatUser = chat.getUser(self.chatID)
        return self.domain.chat and self._chatUser["delete_at"] == 0 if self._chatUser else False

    @chat.setter
    def chat(self, value):
        if value == self.chat or not DB.minVersion(78):
            return
        err_prefix = "Could not enable chat for user '{}': ".format(self.username)
        if not self.domain.chat:
            logger.warning(err_prefix+"chat is not enabled for domain")
            return
        with Service("chat") as chat:
            if isinstance(value, str):
                tmp = chat.getUser(value)
                if tmp is None:
                    logger.warning(err_prefix+"chat user not found")
                    return
                self.chatID = value
                self._chatUser = tmp
                return
            if self._chatUser:
                tmp = chat.activateUser(self, value)
                if tmp:
                    self._chatUser["delete_at"] = not value
                err = "Failed to "+("" if value else "de")+"activate chat user"
            else:
                tmp = chat.createUser(self)
                if tmp:
                    self._chatUser = tmp
                err = err_prefix+"Failed to create user"
            if tmp is None:
                logger.warning(err)

    @property
    def chatAdmin(self):
        return self.chat and "system_admin" in self._chatUser["roles"].split(" ")

    @chatAdmin.setter
    def chatAdmin(self, value):
        if not self.chat or self.chatAdmin == bool(value):
            return
        if value:
            tmpRoles = " ".join(self._chatUser["roles"].split(" ")+["system_admin"])
        else:
            tmpRoles = " ".join(role for role in self._chatUser["roles"].split(" ") if role != "system_admin")
        with Service("chat") as chat:
            tmp = chat.setUserRoles(self.chatID, tmpRoles)
        if tmp is None:
            logger.warning("Failed to update chat user")
        self._chatUser["roles"] = tmpRoles

    @validates("_syncPolicy")
    def triggerSyncPolicyUpdate(self, key, value, *args):
        if value != self._syncPolicy:
            with Service("redis", Service.SUPPRESS_INOP) as r:
                r.delete("grommunio-sync:policycache-"+self.username)
        return value

    @staticmethod
    def count(*filters):
        """Count users.

        Applies filters to only count real users (DISPLAYTYPEEX == 0) and ignore the admin user (ID == 0).

        Parameters
        ----------
        filters : iterable, optional
            Additional filter expressions to use. The default is ().

        Returns
        -------
        int
            Number of users
        """
        return Users.query.with_entities(Users.ID)\
                          .filter(Users.ID != 0, Users.maildir != "", *filters)\
                          .count()

    def delete(self):
        """Delete user from database.

        Also cleans up entries in forwards, members and associations tables.

        Returns
        -------
        str
            Error message or None if successful.
        """
        from .mlists import Associations
        from .misc import Forwards
        from .classes import Members
        if self.ID == 0:
            raise ValueError("Cannot delete superuser")
        Forwards.query.filter(Forwards.username == self.username).delete(synchronize_session=False)
        Members.query.filter(Members.username == self.username).delete(synchronize_session=False)
        Associations.query.filter(Associations.username == self.username).delete(synchronize_session=False)
        DB.session.delete(self)

    @staticmethod
    def create(props, reloadGromoxHttp=True, externID=None, *args, **kwargs):
        from tools.misc import AutoClean
        from tools.storage import UserSetup
        error = Users.checkCreateParams(props)
        if error is not None:
            return error, 400
        try:
            user = Users(props)
            user.externID = externID
        except (InvalidAttributeError, MismatchROError, MissingRequiredAttributeError, ValueError) as err:
            return err.args[0], 400
        try:
            with AutoClean(lambda: DB.session.rollback()):
                DB.session.add(user)
                DB.session.flush()
                with UserSetup(user) as us:
                    us.run()
                if not us.success:
                    return "Error during user setup: "+us.error, us.errorCode
                DB.session.commit()
                return user, 201
        except IntegrityError as err:
            return "Object violates database constraints "+err.orig.args[1], 400

    @classmethod
    def _commit(*args, **kwargs):
        with Service("systemd", Service.SUPPRESS_ALL) as sysd:
            sysd.reloadService("gromox-http.service")


class UserProperties(DataModel, DB.Base):
    __tablename__ = "user_properties"

    supportedTypes = PropTypes.intTypes | PropTypes.floatTypes | {PropTypes.STRING, PropTypes.WSTRING}

    userID = Column("user_id", INTEGER(unsigned=True), ForeignKey(Users.ID, ondelete="cascade", onupdate="cascade"), primary_key=True)
    tag = Column("proptag", INTEGER(unsigned=True), primary_key=True, index=True)
    _propvalbin = Column("propval_bin", VARBINARY(4096))
    _propvalstr = Column("propval_str", VARCHAR(4096))

    user = relationship(Users)

    _dictmapping_ = (({"attr": "name", "flags": "init"}, {"attr": "val", "flags": "patch"}), (Int("userID"),))

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
            raise ValueError("{}: Tag type {} is not supported".format(PropTags.lookup(tag), PropTypes.lookup(tag)))
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
            raise ValueError("Type of value {} does not match type of tag {} ({})".format(value, self.name,
                                                                                          PropTypes.lookup(self.tag)))
        if self.type == PropTypes.BINARY:
            self._propvalbin = value
        else:
            self._propvalstr = str(value)


class Aliases(DataModel, DB.Base, NotifyTable):
    __tablename__ = "aliases"

    aliasname = Column("aliasname", VARCHAR(128), nullable=False, unique=True, primary_key=True)
    mainname = Column("mainname", VARCHAR(128), ForeignKey(Users.username, ondelete="cascade", onupdate="cascade"),
                      nullable=False, index=True)

    main = relationship(Users)

    _dictmapping_ = ((Text("aliasname", flags="init"),),
                     (Text("mainname", flags="init"),))

    def __init__(self, aliasname, main, *args, **kwargs):
        if main.ID == 0:
            raise ValueError("Cannot alias superuser")
        self.main = main
        self.fromdict(aliasname)

    def fromdict(self, aliasname, *args, **kwargs):
        if not formats.email.match(aliasname):
            raise ValueError("'{}' is not a valid email address".format(aliasname))
        self.aliasname = aliasname
        return self

    @classmethod
    def _commit(*args, **kwargs):
        with Service("systemd", Service.SUPPRESS_ALL) as sysd:
            sysd.reloadService("gromox-http.service")


class Fetchmail(DataModel, DB.Base):
    __tablename__ = "fetchmail"

    _sa = ("password", "kerberos_v5", "kerberos", "kerberos_v4", "gssapi", "cram-md5", "otp", "ntlm", "msn", "ssh", "any")

    ID = Column("id", INTEGER(10, unsigned=True), nullable=False, primary_key=True)
    userID = Column("user_id", INTEGER(10, unsigned=True), ForeignKey(Users.ID), nullable=False)
    mailbox = Column("mailbox", VARCHAR(255), nullable=False)
    active = Column("active", TINYINT(1, unsigned=True), nullable=False, server_default="1")
    srcServer = Column("src_server", VARCHAR(255), nullable=False)
    srcAuth = Column("src_auth", ENUM(*_sa), nullable=False, server_default="password")
    srcUser = Column("src_user", VARCHAR(255), nullable=False)
    srcPassword = Column("src_password", VARCHAR(255), nullable=False)
    srcFolder = Column("src_folder", VARCHAR(255), nullable=False, default="")
    fetchall = Column("fetchall", TINYINT(1, unsigned=True), nullable=False, server_default="0")
    keep = Column("keep", TINYINT(1, unsigned=True), nullable=False, server_default="1")
    protocol = Column("protocol", ENUM("POP3", "IMAP", "POP2", "ETRN", "AUTO"), nullable=False, server_default='IMAP')
    useSSL = Column("usessl", TINYINT(1, unsigned=True), nullable=False, server_default="1")
    sslCertCheck = Column("sslcertck", TINYINT(1, unsigned=True), nullable=False, server_default="0")
    sslCertPath = Column("sslcertpath", VARCHAR(255, charset="utf8"))
    sslFingerprint = Column("sslfingerprint", VARCHAR(255, charset="latin1"))
    extraOptions = Column("extra_options", TEXT)
    date = Column("date", TIMESTAMP, nullable=False, server_default="current_timestamp()", onupdate=func.current_timestamp())

    user = relationship(Users)

    _dictmapping_ = ((Id(), Text("mailbox", flags="patch"),
                      Bool("active", flags="patch"),
                      Text("srcServer", flags="patch"),
                      Text("srcUser", flags="patch"),
                      Date("date", time=True),
                      Text("srcAuth", flags="patch"),
                      Text("srcPassword", flags="patch"),
                      Text("srcFolder", flags="patch"),
                      Bool("fetchall", flags="patch"),
                      Bool("keep", flags="patch"),
                      Text("protocol", flags="patch"),
                      Bool("useSSL", flags="patch"),
                      Bool("sslCertCheck", flags="patch"),
                      Text("sslCertPath", flags="patch"),
                      Text("sslFingerprint", flags="patch"),
                      Text("extraOptions", flags="patch")),
                     (Id("userID", flags="hidden"),))

    def __init__(self, props, user, *args, **kwargs):
        self.user = user
        if "mailbox" not in props:
            self.mailbox = user.username
        self.fromdict(props)

    @validates("mailbox")
    def validateMailbox(self, key, value, *args):
        if not formats.email.match(value):
            raise ValueError("'{}' is not a valid e-mail address".format(value))
        return value

    @validates("srcServer")
    def validateServer(self, key, value, *args):
        if not formats.domain.match(value):
            raise ValueError("'{}' is not a valid domain".format(value))
        return value

    def __str__(self):
        fetchoptions = "options"
        if self.useSSL == 1:
            fetchoptions += " ssl"
            if self.sslFingerprint:
                fetchoptions = " sslfingerprint '{}'".format(self.sslFingerprint)
            if self.sslCertCheck == 1:
                fetchoptions += " sslCertCheck"
            if self.sslCertPath:
                fetchoptions += "sslcertpath "+self.sslCertPath
        if self.fetchall == 1:
            fetchoptions += " fetchall"
        fetchoptions += " keep" if self.keep == 1 else " nokeep"
        if self.extraOptions:
            fetchoptions += self.extraOptions
        srcFolder = " folder "+self.srcFolder if self.srcFolder and self.protocol not in ("POP3", "ETRN", "ODMR") else ""
        return "poll {} with proto {} user {}{} there with password {} is {} here {}\n"\
            .format(self.srcServer, self.protocol, self.srcUser, srcFolder, self.srcPassword, self.mailbox, fetchoptions)

from . import domains, roles

Users.NTregister()
Aliases.NTregister()
