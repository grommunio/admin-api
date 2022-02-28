# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grommunio GmbH

from . import DB, logger

from tools.DataModel import DataModel, Id, Date, Int, Text

from sqlalchemy import Column, func, select
from sqlalchemy.dialects.mysql import INTEGER, TINYINT, VARCHAR, TEXT, TIMESTAMP
from sqlalchemy.ext.hybrid import hybrid_property

import json


class DBConf(DB.Base):
    __tablename__ = "configs"

    ID = Column("id", INTEGER(10, unsigned=True), nullable=False, primary_key=True)
    service = Column("service", VARCHAR(200), nullable=False, index=True)
    file = Column("file", VARCHAR(200), nullable=False, index=True)
    key = Column("key", VARCHAR(200), nullable=False)
    value = Column("value", VARCHAR(200), nullable=False, default="")

    @staticmethod
    def getValue(service, file, key, default=None):
        entry = DBConf.query.filter(DBConf.service == service, DBConf.file == file, DBConf.key == key)\
                            .with_entities(DBConf.value).first()
        return default if entry is None else entry.value


class TasQ(DataModel, DB.Base):
    __tablename__ = "tasq"

    ID = Column("id", INTEGER(10, unsigned=True), primary_key=True)
    command = Column("command", VARCHAR(16))
    state = Column("state", TINYINT(unsigned=True), server_default="0")
    created = Column("created", TIMESTAMP, server_default="now()")
    updated = Column("updated", TIMESTAMP, server_default="now()")
    message = Column("message", VARCHAR(160), server_default="")
    _params = Column("params", TEXT, nullable=True, default="{}")
    access = Column("access", TEXT, nullable=True)

    _dictmapping_ = ((Id(), Text("command", flags="init")),
                     (Id("state"),
                      Date("created", time=True),
                      Date("updated", time=True),
                      Text("message")),
                     ({"attr": "params", "flags": "patch"},))

    @property
    def params(self):
        return json.loads(self._params) if self._params is not None else {}

    @params.setter
    def params(self, value):
        self._params = json.dumps(value, separators=(',', ':'))

    @property
    def permission(self):
        from tools.permissions import Permissions
        return Permissions.load(self.access)

    @permission.setter
    def permission(self, perm):
        from tools.permissions import Permissions
        self.access = Permissions.dump(perm)


class Servers(DataModel, DB.Base):
    __tablename__ = "servers"

    ID = Column("id", TINYINT(unsigned=True), primary_key=True)
    hostname = Column("hostname", VARCHAR(255), nullable=False, unique=True)
    extname = Column("extname", VARCHAR(255), nullable=False, unique=True)

    _dictmapping_ = ((Id(), Text("hostname", flags="patch")),
                     (Text("extname", flags="patch"),),
                     (Int("users"),
                      Int("domains")))

    # Defined as hybrid_property instead of column_property to break cyclical import dependency
    # Domains -> Users -> Servers -> Domains
    @hybrid_property
    def users(self):
        from .users import Users
        return Users.query.filter(Users.homeserverID == self.ID).count()

    @users.expression
    def users(cls):
        from .users import Users
        return select([func.count(Users.ID)]).where(Users.homeserverID == cls.ID).as_scalar()

    @hybrid_property
    def domains(self):
        from .domains import Domains
        return Domains.query.filter(Domains.homeserverID == self.ID).count()

    @domains.expression
    def domains(cls):
        from .domains import Domains
        return select([func.count(Domains.ID)]).where(Domains.homeserverID == cls.ID).as_scalar()

    @staticmethod
    def _getServer(objID, serverID=None):
        """Select a server for an object

        Parameters
        ----------
        objID : int
            ID of the object
        serverID : int, optional
            ID of the server or None to select automatically. The default is None.

        Raises
        ------
        ValueError
            Server with specified ID could not be found.

        Returns
        -------
        Servers
            Selected server object or None if no servers are configured (i.e. single server setup)
        """
        if not DB.minVersion(105):
            return None
        from tools.config import Config
        if serverID:
            server = Servers.query.filter(Servers.ID == serverID).first()
            if server is None:
                raise ValueError("Requested server #{} not found".format(serverID))
            return server
        servers = Servers.query.count()
        if servers == 0:
            return None
        policy = DBConf.getValue("grommunio-admin", "multi-server", "policy", default="round-robin")
        if policy == "balanced":
            return Servers.query.order_by(Servers.users.asc()).first()
        elif policy == "first":
            index = 0
        elif policy == "last":
            index = servers-1
        elif policy == "random":
            import random
            index = random.randint(0, servers-1)
        else:  # default (policy == "round-robin")
            if policy != "round-robin":
                logger.warning("Unknown multi-server policy '{}'. Defaulting to round-robin.".format(policy))
            index = objID % servers
        return Servers.query.order_by(Servers.ID).offset(index).first()

    @staticmethod
    def allocUser(userID, serverID=None):
        """Select a server to store new user on.

        Parameters
        ----------
        userID : int
            ID of the new user
        serverID : int, optional
            Server to use or None for automatic selection. The default is None.

        Returns
        -------
        tuple(int, str)
            2-tuple containing the server ID and path
        """
        from tools.config import Config
        from os import path
        server = Servers._getServer(userID, serverID)
        serverMount = server is not None and Config["options"].get("serverExplicitMount")
        targetPath = Config["options"]["userPrefix"]
        targetPath = path.join(targetPath, server.hostname) if serverMount else targetPath
        return (0 if server is None else server.ID, targetPath)

    @staticmethod
    def allocDomain(domainID, serverID=None):
        """Select a server to store new domain on.

        Parameters
        ----------
        domainID : int
            ID of the new domain
        serverID : int, optional
            Server to use or None for automatic selection. The default is None.

        Returns
        -------
        tuple(int, str)
            2-tuple containing the server ID and path
        """
        from tools.config import Config
        from os import path
        server = Servers._getServer(domainID, serverID)
        serverMount = server is not None and Config["options"].get("serverExplicitMount")
        targetPath = Config["options"]["domainPrefix"]
        targetPath = path.join(targetPath, server.hostname) if serverMount else targetPath
        return (0 if server is None else server.ID, targetPath)
