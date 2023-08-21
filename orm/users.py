# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020-2021 grommunio GmbH

from . import DB, OptionalC, OptionalNC, NotifyTable, logger
from services import Service
from tools import formats
from tools.constants import PropTags, PropTypes
from tools.DataModel import DataModel, Id, Text, Int, BoolP, RefProp, Bool, Date
from tools.DataModel import InvalidAttributeError, MismatchROError, MissingRequiredAttributeError
from tools.rop import nxTime

from sqlalchemy import Column, ForeignKey, event, func, inspect, select
from sqlalchemy.dialects.mysql import ENUM, INTEGER, TEXT, TIMESTAMP, TINYINT, VARBINARY, VARCHAR
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import column_property, relationship, selectinload, validates

import crypt
import json
import sys

from datetime import datetime

# Was moved in SQLA 1.4
import sqlalchemy
if sqlalchemy.__version__.split(".") >= ["1", "4"]:
    from sqlalchemy.orm import DeclarativeMeta
else:
    from sqlalchemy.ext.declarative.api import DeclarativeMeta


class Users(DataModel, DB.Base, NotifyTable):
    class PropMap():
        def __init__(self, user):
            self.__user = user
            self.__struct = {}
            self.__dict = {}
            for prop in user._properties:
                if PropTypes.ismv(prop.tag):
                    if prop.tag in self.__struct:
                        self.__dict[self._name(prop.tag)].append(prop.val)
                        self.__struct[prop.tag].append(prop)
                    else:
                        self.__dict[self._name(prop.tag)] = [prop.val]
                        self.__struct[prop.tag] = [prop]
                else:
                    self.__dict[self._name(prop.tag)] = prop.val
                    self.__struct[prop.tag] = prop

        @staticmethod
        def _name(key):
            return key.lower() if isinstance(key, str) else PropTags.lookup(key, hex(key)).lower()

        def __contains__(self, o):
            return self._name(o) in self.__dict

        def __getitem__(self, k):
            return self.__dict[self._name(k)]

        def __len__(self):
            return len(self.__dict)

        def __repr__(self):
            return repr(self.__dict)

        def __setitem__(self, k, v):
            tag = PropTags.deriveTag(k)
            name = self._name(k)
            if not PropTypes.ismv(tag):
                if tag in self.__struct:
                    if v is None:
                        DB.session.delete(self.__struct[tag])
                    else:
                        self.__struct[tag].val = v
                elif v is None:
                    return
                else:
                    self.__struct[tag] = UserProperties(tag, v, self.__user)
                    DB.session.add(self.__struct[tag])
                self.__dict[name] = v
                return
            if v is None:
                v = []
            elif not isinstance(v, (list, tuple, set)):
                v = [v]
            values = self.__dict.get(name, ())
            current = self.__struct.get(tag, ())
            next = []
            for value in v:
                if v in current:
                    i = values.index(v)
                    values.pop(i)
                    next.append(current.pop(i))
                else:
                    next.append(UserProperties(tag, value, self.__user))
                    DB.session.add(next[-1])
            for rm in current:
                DB.session.delete(rm)
            order = 1
            for up in next:
                up.orderID = order
                order += 1
            self.__dict[name] = v
            self.__struct[tag] = next

        def get(self, k, d=None):
            return self.__dict.get(self._name(k), d)

        def idmap(self):
            return {tag: [v.val for v in value] if PropTypes.ismv(tag) else value.val for tag, value in self.__struct.items()}

        def namemap(self):
            return self.__dict

        def items(self):
            return self.__dict.items()

        def update(self, data):
            for k, v in data.items():
                self[k] = v

        def rawmap(self):
            def getv(prop):
                return PropTypes.pyType(prop.baseType)(prop.content)
            return {tag: [getv(p) for p in prop] if PropTypes.ismv(tag) else getv(prop)
                    for tag, prop in self.__struct.items()}

    __tablename__ = "users"

    ID = Column("id", INTEGER(10, unsigned=True), nullable=False, primary_key=True, unique=True)
    username = Column("username", VARCHAR(320, charset="ascii"), nullable=False, unique=True)
    altname = OptionalC(111, "NULL", Column("altname", VARCHAR(64), unique=True))
    _password = Column("password", VARCHAR(40), nullable=False, server_default="")
    domainID = Column("domain_id", INTEGER(10, unsigned=True), nullable=False, index=True)
    maildir = Column("maildir", VARCHAR(128), nullable=False, server_default="")
    addressStatus = Column("address_status", TINYINT, nullable=False, server_default="0")
    privilegeBits = Column("privilege_bits", INTEGER(10, unsigned=True), nullable=False, default=0)
    externID = Column("externid", VARBINARY(64))
    chatID = OptionalC(78, "NULL", Column("chat_id", VARCHAR(26)))
    lang = Column("lang", VARCHAR(32), nullable=False, server_default="")
    homeserverID = OptionalC(104, "0", Column("homeserver", TINYINT(unsigned=True), nullable=False, server_default="0"))
    _syncPolicy = OptionalC(76, "NULL", Column("sync_policy", TEXT))
    _deprecated_maxSize = OptionalC(-111, "0", Column("max_size", INTEGER(10), nullable=False, default=0))
    _deprecated_addressType = OptionalC(-86, "NULL", Column("address_type", TINYINT, nullable=False, server_default="0"))
    _deprecated_subType = OptionalC(-85, "NULL", Column("sub_type", TINYINT, nullable=False, server_default="0"))
    _deprecated_groupID = Column("group_id", INTEGER(10, unsigned=True), nullable=False, index=True, default=0)

    domain = relationship("Domains", foreign_keys=domainID, primaryjoin="Users.domainID == Domains.ID")
    roles = relationship("AdminRoles", secondary="admin_user_role_relation", viewonly=True)
    _properties = relationship("UserProperties", cascade="all, delete-orphan", single_parent=True, passive_deletes=True,
                               order_by="UserProperties.orderID", back_populates="user")
    aliases = relationship("Aliases", cascade="all, delete-orphan", single_parent=True, passive_deletes=True,
                           back_populates="main")
    fetchmail = OptionalNC(75, [],
                           relationship("Fetchmail", cascade="all, delete-orphan", single_parent=True,
                                        order_by="Fetchmail.active.desc()", back_populates="user"))
    forward = relationship("Forwards", uselist=False, cascade="all, delete-orphan", back_populates="user")
    homeserver = OptionalNC(104, None,
                            relationship("Servers", foreign_keys=homeserverID, primaryjoin="Users.homeserverID == Servers.ID"))
    mlist = relationship("MLists", back_populates="user", uselist=False)

    _dictmapping_ = ((Id(), Text("username", flags="patch")),
                     (Id("domainID", flags="init"),
                      {"attr": "ldapID", "flags": "patch"},
                      Int("status", flags="patch"),
                      Text("altname", flags="patch")),
                     (Text("lang", match=False, flags="patch"),
                      BoolP("pop3_imap", flags="patch"),
                      BoolP("smtp", flags="patch"),
                      BoolP("changePassword", flags="patch"),
                      BoolP("publicAddress", flags="patch"),
                      BoolP("privChat", flags="patch"),
                      BoolP("privVideo", flags="patch"),
                      BoolP("privFiles", flags="patch"),
                      BoolP("privArchive", flags="patch"),
                      RefProp("aliases", flags="patch, managed", link="aliasname", flat="aliasname", qopt=selectinload),
                      RefProp("fetchmail", flags="managed, patch", link="ID", qopt=selectinload),
                      {"attr": "properties", "flags": "patch", "func": lambda p: p.namemap()},
                      RefProp("roles", qopt=selectinload),
                      RefProp("forward", flags="managed, patch"),
                      RefProp("mlist", filter="set", flat="ID"),
                      {"attr": "syncPolicy", "flags": "patch"},
                      {"attr": "chat", "flags": "patch"},
                      {"attr": "chatAdmin", "flags": "patch"},
                      Int("orgID"),
                      RefProp("homeserver", "homeserverID", flags="patch", filter="set", qopt=selectinload)),
                     ({"attr": "password", "flags": "init, hidden"},
                      Text("maildir", match=False, flags="hidden"),))

    USER_PRIVILEGE_POP3_IMAP = 1 << 0
    USER_PRIVILEGE_SMTP = 1 << 1
    USER_PRIVILEGE_CHGPASSWD = 1 << 2
    USER_PRIVILEGE_PUBADDR = 1 << 3
    USER_PRIVILEGE_CHAT = 1 << 4
    USER_PRIVILEGE_VIDEO = 1 << 5
    USER_PRIVILEGE_FILES = 1 << 6
    USER_PRIVILEGE_ARCHIVE = 1 << 7

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
    SHARED = 4
    CONTACT = 5
    USER_MASK = 0x07
    DOMAIN_MASK = 0x30

    _chatUser = None
    _propcache = None

    @staticmethod
    def checkCreateParams(data):
        from orm.domains import Domains
        from tools.license import getLicense
        if "username" not in data:
            return "Missing username"
        if data.get("status", 0) not in (Users.SHARED, Users.CONTACT) and Users.count() >= getLicense().users:
            return "License user limit exceeded"
        if "domainID" in data:
            domain = Domains.query.filter(Domains.ID == data.get("domainID")).first()
        elif "@" in data["username"]:
            domain = Domains.query.filter(Domains.domainname == data["username"].split("@")[1]).first()
        else:
            domain = None
        if domain is None:
            return "Invalid domain"
        if data.get("status") != Users.CONTACT:
            if "@" in data["username"]:
                dname = data["username"].split("@", 1)[1]
                if domain.domainname != dname and domain.displayname != dname:
                    return "Domain specifications do not match"
            else:
                data["username"] += "@"+domain.domainname
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

    def fromdict(self, patches, syncStore=False, *args, **kwargs):
        isContact = patches.get("status", self.status) != Users.CONTACT
        if "username" in patches and patches["username"] != self.username:
            from orm.domains import Domains
            username = patches.pop("username")
            domain = patches.pop("domain", None) or Domains.query.filter(Domains.ID == self.domainID).first()
            if "@" in username:
                uname, dname = username.split("@", 1)
                if dname != domain.domainname and dname != domain.displayname:
                    raise ValueError("Domain specifications mismatch.")
                self.username = uname+"@"+domain.domainname
            elif not isContact:
                self.username = username+"@"+domain.domainname
            else:
                self.username = username
            if not isContact and not formats.email.match(self.username):
                raise ValueError("'{}' is not a valid e-mail address".format(self.username))
        DataModel.fromdict(self, patches, args, kwargs)
        displaytype = self.properties.get("displaytypeex", 0)
        if displaytype in (0, 1, 7, 8):
            self._deprecated_addressType, self._deprecated_subType = self._decodeDisplayType(displaytype)
        if self.chatID:
            with Service("chat", errors=Service.SUPPRESS_INOP) as chat:
                self._chatUser = chat.updateUser(self, False)
        if syncStore == "always" or (syncStore and "properties" in patches):
            self.syncStore()

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
        # On OpenBSD only blowfish is supported
        if sys.platform.startswith("openbsd"):
            _method = crypt.METHOD_BLOWFISH
        else:
            _method = crypt.METHOD_SHA512
        self._password = crypt.crypt(pw, crypt.mksalt(_method))

    def chkPw(self, pw):
        return crypt.crypt(pw, self.password) == self.password

    @property
    def propmap_id(self):
        if self._propcache is None:
            self._propcache = self.PropMap(self)
        return self._propcache.idmap()

    @property
    def properties(self):
        if self._propcache is None:
            self._propcache = self.PropMap(self)
        return self._propcache

    @properties.setter
    def properties(self, values):
        if self._propcache is None:
            self._propcache = self.PropMap(self)
        self._propcache.update(values)

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
        return self.privilegeBits if isinstance(self, DeclarativeMeta) else bool((self.privilegeBits or 0) & bit)

    @hybrid_property
    def pop3_imap(self):
        return self._getPB(self.USER_PRIVILEGE_POP3_IMAP)

    @pop3_imap.setter
    def pop3_imap(self, val):
        self._setPB(self.USER_PRIVILEGE_POP3_IMAP, val)

    @pop3_imap.expression
    def pop3_imap(cls):
        return cls.privilegeBits.op("&")(cls.USER_PRIVILEGE_POP3_IMAP) != 0

    @hybrid_property
    def smtp(self):
        return self._getPB(self.USER_PRIVILEGE_SMTP)

    @smtp.setter
    def smtp(self, val):
        self._setPB(self.USER_PRIVILEGE_SMTP, val)

    @smtp.expression
    def smtp(cls):
        return cls.privilegeBits.op("&")(cls.USER_PRIVILEGE_SMTP) != 0

    @hybrid_property
    def changePassword(self):
        return self._getPB(self.USER_PRIVILEGE_CHGPASSWD)

    @changePassword.setter
    def changePassword(self, val):
        self._setPB(self.USER_PRIVILEGE_CHGPASSWD, val)

    @changePassword.expression
    def changePassword(cls):
        return cls.privilegeBits.op("&")(cls.USER_PRIVILEGE_CHGPASSWD) != 0

    @hybrid_property
    def publicAddress(self):
        return self._getPB(self.USER_PRIVILEGE_PUBADDR)

    @publicAddress.setter
    def publicAddress(self, val):
        self._setPB(self.USER_PRIVILEGE_PUBADDR, val)

    @publicAddress.expression
    def publicAddress(cls):
        return cls.privilegeBits.op("&")(cls.USER_PRIVILEGE_PUBADDR) != 0

    @hybrid_property
    def privChat(self):
        return self._getPB(self.USER_PRIVILEGE_CHAT)

    @privChat.setter
    def privChat(self, val):
        self._setPB(self.USER_PRIVILEGE_CHAT, val)

    @privChat.expression
    def privChat(cls):
        return cls.privilegeBits.op("&")(cls.USER_PRIVILEGE_CHAT) != 0

    @hybrid_property
    def privVideo(self):
        return self._getPB(self.USER_PRIVILEGE_VIDEO)

    @privVideo.setter
    def privVideo(self, val):
        self._setPB(self.USER_PRIVILEGE_VIDEO, val)

    @privVideo.expression
    def privVideo(cls):
        return cls.privilegeBits.op("&")(cls.USER_PRIVILEGE_VIDEO) != 0

    @hybrid_property
    def privFiles(self):
        return self._getPB(self.USER_PRIVILEGE_FILES)

    @privFiles.setter
    def privFiles(self, val):
        self._setPB(self.USER_PRIVILEGE_FILES, val)

    @privFiles.expression
    def privFiles(cls):
        return cls.privilegeBits.op("&")(cls.USER_PRIVILEGE_FILES) != 0

    @hybrid_property
    def privArchive(self):
        return self._getPB(self.USER_PRIVILEGE_ARCHIVE)

    @privArchive.setter
    def privArchive(self, val):
        self._setPB(self.USER_PRIVILEGE_ARCHIVE, val)

    @privArchive.expression
    def privArchive(cls):
        return cls.privilegeBits.op("&")(cls.USER_PRIVILEGE_ARCHIVE) != 0

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
        return (self.addressStatus or 0) & self.USER_MASK

    @status.setter
    def status(self, val):
        self.addressStatus = ((self.addressStatus or 0) & ~self.USER_MASK) | (val & self.USER_MASK)

    @status.expression
    def status(cls):
        return cls.addressStatus.op("&")(cls.USER_MASK)

    @hybrid_property
    def domainStatus(self):
        return (self.addressStatus & self.DOMAIN_MASK) >> 4

    @domainStatus.setter
    def domainStatus(self, val):
        self.addressStatus = (self.addressStatus & ~self.DOMAIN_MASK) | (val << 4 & self.DOMAIN_MASK)

    @domainStatus.expression
    def domainStatus(cls):
        return cls.addressStatus.op("&")(cls.DOMAIN_MASK).op(">>")(4)

    @property
    def chat(self):
        if not self.chatID:
            return False
        if self._chatUser is None:
            with Service("chat", errors=Service.SUPPRESS_INOP) as chat:
                self._chatUser = chat.getUser(self.chatID)
        return self.domain.chat and self._chatUser["delete_at"] == 0 if self._chatUser else False

    @chat.setter
    def chat(self, value):
        if value == self.chat:
            return
        if not DB.minVersion(78):
            raise ValueError("Cannot activate chat - please upgrade database schema to at least 78")
        if value and self.addressStatus:
            raise ValueError("Cannot activate chat for locked user")
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
            with Service("redis", errors=Service.SUPPRESS_INOP) as r:
                r.delete("grommunio-sync:policycache-"+self.username)
        return value

    @validates("homeserverID")
    def checkHomeserver(self, key, value, *args):
        from tools.config import Config
        if self.homeserverID and value != self.homeserverID and Config["options"].get("serverExplicitMount"):
            raise ValueError("Cannot change homeserver with explicitly mounted home-directories")
        from .misc import Servers
        if value and Servers.query.filter(Servers.ID == value).count() == 0:
            raise ValueError("Invalid homeserver")
        return value or 0

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
                          .filter(Users.ID != 0, Users.maildir != "", Users.status != Users.SHARED, *filters)\
                          .count()

    def delete(self, deleteChatUser=True):
        """Delete user from database.

        Also cleans up entries in forwards and associations tables.

        Parameters
        ----------
        filters : iterable, optional
            Additional filter expressions to use. The default is ().

        Returns
        -------
        str
            Error message or None if successful.
        """
        from .mlists import Associations, MLists
        if self.ID == 0:
            raise ValueError("Cannot delete superuser")
        Forwards.query.filter(Forwards.username == self.username).delete(synchronize_session=False)
        Associations.query.filter(Associations.username == self.username).delete(synchronize_session=False)
        MLists.query.filter(MLists.listname == self.username).delete(synchronize_session=False)
        if self.chatID is not None:
            from services import Service
            with Service("chat", errors=Service.SUPPRESS_ALL) as chat:
                chat.deleteUser(self) if deleteChatUser else chat.activateUser(self, False)
        DB.session.delete(self)

    @staticmethod
    def create(props, externID=None, sync=True, *args, **kwargs):
        from .misc import Servers
        from tools.misc import AutoClean
        from tools.storage import UserSetup
        error = Users.checkCreateParams(props)
        chat = props.pop("chat", None)
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
                user.homeserverID, user.maildir = Servers.allocUser(user.ID, props.get("homeserver"))
                with UserSetup(user, DB.session) as us:
                    us.run()
                if chat:
                    try:
                        user.chat = chat
                    except ValueError as err:
                        logger.error("Failed to activate chat: "+err.args[0])
                DB.session.commit()
                if not us.success:
                    return "Error during user setup: "+us.error, us.errorCode
                if sync:
                    try:
                        user.syncStore()
                    except Exception:
                        pass
                    return user, 201
        except IntegrityError as err:
            return "Object violates database constraints "+err.orig.args[1], 400
        except Exception as err:
            DB.session.rollback()
            return "Failed to create user "+" - ".join(str(arg) for arg in err.args), 500

    @classmethod
    def mkContact(cls, props, externID=None, *args, **kwargs):
        smtpaddress = props.get("username")
        props["status"] = Users.CONTACT
        props["username"] = "temp"
        error = Users.checkCreateParams(props)
        if smtpaddress:
            props["properties"][PropTags.SMTPADDRESS] = smtpaddress
        props["properties"][PropTags.DISPLAYTYPEEX] = Users.REMOTE_MAILUSER
        if error is not None:
            return error, 400
        try:
            user = Users(props)
            user.externID = externID
        except (InvalidAttributeError, MismatchROError, MissingRequiredAttributeError, ValueError) as err:
            return err.args[0], 400
        try:
            DB.session.add(user)
            DB.session.flush()
            user.username = "contact-"+str(user.ID)
            DB.session.commit()
            return user, 201
        except IntegrityError as err:
            return "Object violates database constraints "+err.orig.args[1], 400
        except Exception as err:
            DB.session.rollback()
            return "Failed to create contact"+" - ".join(str(arg) for arg in err.args), 500

    @classmethod
    def _commit(*args, **kwargs):
        with Service("systemd", errors=Service.SUPPRESS_ALL) as sysd:
            sysd.reloadService("gromox-http.service", "gromox-zcore.service")

    @validates("username")
    def validateUsername(self, key, value, *args):
        if not self.username == value and Users.query.filter(Users.altname == value).count():
            raise ValueError("Username is already used as alternative name")
        return value

    @validates("altname")
    def validateAltname(self, key, value, *args):
        if Users.query.filter(Users.username == value).count():
            raise ValueError("Alternative name is already in use")
        return value or None

    def syncStore(self):
        """Write all properties to the exmdb store.

        For users without a store, this function has no effect.
        """
        if not self.maildir:
            return
        with Service("exmdb") as exmdb:
            props = []
            for tag, value in self.properties.rawmap().items():
                try:
                    props.append(exmdb.TaggedPropval(tag, value))
                except Exception:
                    pass
            client = exmdb.user(self)
            client.setStoreProperties(0, props)


class UserProperties(DB.Base):
    __tablename__ = "user_properties"

    supportedTypes = PropTypes.intTypes | PropTypes.floatTypes | {PropTypes.STRING, PropTypes.WSTRING}

    userID = Column("user_id", INTEGER(unsigned=True), ForeignKey(Users.ID, ondelete="cascade", onupdate="cascade"), primary_key=True)
    tag = Column("proptag", INTEGER(unsigned=True), primary_key=True)
    orderID = Column("order_id", INTEGER(unsigned=True), primary_key=True, server_default="1")
    _propvalbin = Column("propval_bin", VARBINARY(4096))
    _propvalstr = Column("propval_str", VARCHAR(4096))

    user = relationship(Users, back_populates="_properties")

    def __init__(self, tag, value, user):
        if tag & 0x0FFF not in self.supportedTypes:
            raise NotImplementedError("Prop type is currently not supported")
        self.tag = tag
        self.val = value
        self.user = user

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
        if tag & 0x0FFF not in self.supportedTypes:
            raise ValueError("{}: Tag type {} is not supported".format(PropTags.lookup(tag), PropTypes.lookup(tag)))
        self.tag = tag

    @property
    def type(self):
        return self.tag & 0xFFFF

    @property
    def baseType(self):
        return self.tag & 0x0FFF

    @property
    def val(self):
        if self.type == PropTypes.BINARY:
            return self._propvalbin
        if self.type == PropTypes.FILETIME:
            return datetime.fromtimestamp(nxTime(int(self._propvalstr))).strftime("%Y-%m-%d %H:%M:%S")
        return PropTypes.pyType(self.type)(self._propvalstr)

    @val.setter
    def val(self, value):
        value = PropTags.convertValue(self.tag, value)
        if self.type == PropTypes.BINARY:
            self._propvalbin = value
        else:
            self._propvalstr = str(value)

    @property
    def content(self):
        return self._propvalbin if self.baseType == PropTypes.BINARY else self._propvalstr


class Aliases(DataModel, DB.Base, NotifyTable):
    __tablename__ = "aliases"

    aliasname = Column("aliasname", VARCHAR(128), nullable=False, unique=True, primary_key=True)
    mainname = Column("mainname", VARCHAR(128), ForeignKey(Users.username, ondelete="cascade", onupdate="cascade"),
                      nullable=False, index=True)

    main = relationship(Users, back_populates="aliases")

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
        with Service("systemd", errors=Service.SUPPRESS_ALL) as sysd:
            sysd.reloadService("gromox-delivery.service", "gromox-http.service", "gromox-zcore.service")


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

    @validates("srcPassword")
    def validatePassword(self, key, value, *args):
        return value.replace("'", "").replace('"', '')

    @validates("srcServer")
    def validateServer(self, key, value, *args):
        if not formats.domain.match(value.split(":", 1)[0]):
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
        if self.fetchall == 0:
            fetchoptions += " no"
        fetchoptions += " fetchall"
        fetchoptions += " keep" if self.keep == 1 else " nokeep"
        if self.extraOptions:
            fetchoptions += " "+self.extraOptions
        server, service = self.srcServer.split(":", 1) if ":" in self.srcServer else (self.srcServer, None)
        service = " service "+service if service else ""
        srcFolder = " folder "+self.srcFolder if self.srcFolder and self.protocol not in ("POP3", "ETRN", "ODMR") else ""
        return "poll {} with proto {}{} user {} there with password '{}' is {} here{} {}\n"\
            .format(server, self.protocol, service, self.srcUser, self.srcPassword, self.mailbox, srcFolder, fetchoptions)


# Available as of n93
class UserDevices(DataModel, DB.Base):
    __tablename__ = "user_devices"

    ID = Column("id", INTEGER(unsigned=True), primary_key=True)
    userID = Column("user_id", INTEGER(unsigned=True), ForeignKey(Users.ID), nullable=False)
    deviceID = Column("device_id", VARCHAR(64), nullable=False)
    status = Column("status", INTEGER(unsigned=True), nullable=False, server_default="0")

    STATUS_NA = 0
    STATUS_OK = 1 << 0
    STATUS_PENDING = 1 << 1
    STATUS_REQUESTED = 1 << 2
    STATUS_WIPED = 1 << 3

    DEFAULT = {"status": STATUS_NA}

    _dictmapping_ = ((Id(), Id("userID", flags="init"), Id("deviceID", flags="init"), Int("status", flags="patch")),)


class UserDeviceHistory(DataModel, DB.Base):
    __tablename__ = "user_device_history"

    ID = Column("id", INTEGER(unsigned=True), primary_key=True)
    userDeviceID = Column("user_device_id", INTEGER(unsigned=True), ForeignKey(UserDevices.ID), nullable=False)
    time = Column("time", TIMESTAMP, nullable=False, server_default="now()")
    remoteIP = Column("remote_ip", VARCHAR(64), nullable=True)
    status = Column("status", INTEGER(unsigned=True), nullable=False, server_default="0")

    _dictmapping_ = ((Id(), Id("userDeviceID", flags="init")),
                     (DataModel.Prop("time", func=lambda date: int(date.timestamp()) if date else None, flags="init,sort"),
                      Text("remoteIP", flags="init"),
                      Int("status", flags="init")))


class UserSecondaryStores(DB.Base):
    __tablename__ = "secondary_store_hints"

    primaryID = Column("primary", INTEGER(unsigned=True), ForeignKey(Users.ID), primary_key=True)
    secondaryID = Column("secondary", INTEGER(unsigned=True), ForeignKey(Users.ID), primary_key=True)


class Forwards(DataModel, DB.Base):
    __tablename__ = "forwards"

    ID = Column("id", INTEGER(10, unsigned=True), nullable=False, primary_key=True)
    username = Column("username", VARCHAR(128), ForeignKey(Users.username), nullable=False, unique=True)
    forwardType = Column("forward_type", TINYINT, nullable=False, server_default="0")
    destination = Column("destination", VARCHAR(128), nullable=False)

    user = relationship(Users)

    _dictmapping_ = ((Text("forwardType", flags="patch"),
                      Text("destination", flags="patch")),
                     (Id(), Text("username", flags="patch")))

    CC = 0
    REDIRECT = 1

    def __init__(self, props, user, *args, **kwargs):
        self.user = user
        self.fromdict(props)

    @validates("destination")
    def validateDestination(self, key, value, *args):
        if not formats.email.match(value):
            raise ValueError("'{}' is not a valid e-mail address".format(value))
        return value


from .domains import Domains
from . import misc, mlists, roles


Users.NTregister()
Aliases.NTregister()

if sqlalchemy.__version__.split(".") >= ["1", "4"]:
    inspect(Users).add_property("orgID", column_property(select(Domains.orgID)
                                                         .where(Domains.ID == Users.domainID).scalar_subquery()))
else:
    inspect(Users).add_property("orgID", column_property(select([Domains.orgID])
                                                         .where(Domains.ID == Users.domainID).as_scalar()))


@event.listens_for(Users, "expire")
def _User_expire(target, *args, **kwargs):
    if target is not None:
        target._propcache = None
