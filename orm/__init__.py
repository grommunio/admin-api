# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grommunio GmbH

__all__ = ["domains", "misc", "users", "ext"]

from sqlalchemy import create_engine, event, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker, class_mapper, Query, column_property

from tools.config import Config

import logging
logger = logging.getLogger("mysql")


class DBConn:
    def __init__(self, URI):
        self.engine = create_engine(URI)
        self.session = scoped_session(sessionmaker(self.engine))
        self.__version = None
        self.__maxversion = 0
        self.initVersion()

    def __reinit(self):
        outerself = self

        class QueryProperty:
            def __get__(self, obj, type):
                mapper = class_mapper(type)
                return Query(mapper, session=outerself.session()) if mapper is not None else None

        class Model:
            query = QueryProperty()

        self.Base = declarative_base(cls=Model)

    def enableFlask(self, API):
        from flask import _app_ctx_stack
        self.session = scoped_session(sessionmaker(self.engine), _app_ctx_stack.__ident_func__)

        @API.teardown_appcontext
        def removeSession(*args, **kwargs):
            self.session.remove()

    def testConnection(self, verbose=False):
        try:
            self.session.execute("SELECT 1 FROM DUAL")
        except OperationalError as err:
            self.session.remove()
            return "Database connection failed with error {}: {}".format(err.orig.args[0], err.orig.args[1])
        self.session.remove()

    def _fetchVersion(self, verbose=False):
        """Try to fetch schema version from database.

        Parameters
        ----------
        verbose : bool, optional
            Print status information to log. The default is False.

        Returns
        -------
        version : int
            Version number or None on failure
        """
        try:
            version = int(self.session.execute("SELECT `value` FROM `options` WHERE `key` = 'schemaversion'").fetchone()[0])
            if verbose:
                logger.info("Detected database schema version n"+str(version))
            return version
        except Exception:
            if verbose:
                logger.warning("Failed to detect schema version, assuming up-to-date schema")

    def initVersion(self):
        self.__version = self._fetchVersion(True)
        self.__reinit()

    def requireReload(self):
        """Check if a schema version update is available.

        Only queries the database if current version is undefined or is lower
        than the highest known version (i.e. an update would have an actual effect).

        Returns
        -------
        bool
            Whether an update is available and the schema should be reloaded
        """
        return (self.__version is None or self.__version < self.__maxversion) and self._fetchVersion(False) != self.__version

    @property
    def version(self):
        """Get schema version currently in use.

        Returns
        -------
        int
            Schema version number or None if undefined
        """
        return self.__version

    def minVersion(self, v):
        """Check if schema version is at least `v`.

        If the schema version could not be determined, the most recent version
        is assumed and the check always passes.

        Parameters
        ----------
        v : int
            Required version

        Returns
        -------
        bool
            Whether the required version is satisfied
        """
        self.__maxversion = max(v, self.__maxversion)
        return self.__version is not None and self.__version >= v


def _loadDBConfig():
    """Load database parameters from configuration.

    Outputs error messages to log stream if mandatory parameters are missing.

    Returns
    -------
    str
        Database URI including connection and credentials

    """
    if "DB" not in Config:
        logger.error("No database configuration found")
        return None
    DBconf = Config["DB"]
    if "user" not in DBconf or "pass" not in DBconf:
        logger.error("Database user or password missing")
        return None
    if "database" not in DBconf:
        logger.error("No database specified.")
        return None
    if "host" not in DBconf and "port" not in DBconf:
        logger.info("Database connection not specified. Using default '127.0.0.1:3306'")
    host = DBconf.get("host", "127.0.0.1")
    port = DBconf.get("port", 3306)
    return "mysql+mysqldb://{user}:{password}@{host}:{port}/{db}".format(user=DBconf["user"],
                                                                         password=DBconf["pass"],
                                                                         host=host,
                                                                         port=port,
                                                                         db=DBconf["database"])


if Config["options"]["disableDB"]:
    DB = None
    logger.warning("Database disabled in configuration")
else:
    DB_uri = _loadDBConfig()
    if DB_uri is not None:
        DB = DBConn(DB_uri)
        err = DB.testConnection(verbose=True)
        if err is not None:
            logger.warning(err)
    else:
        logger.warning("Database configuration failed. No data will be available")
        DB = None


class Stub:
    def __init__(self, value):
        self.__value__ = value
    def __get__(self, *args):
        return self.__value__
    def __set__(self, *args):
        pass


def OptionalNC(version, default, column):
    """Non-column optional attribute wrapper.

    If the specified version is not reached, a Stub is generated that always
    returns the default value and cannot be modified.

    Parameters
    ----------
    version : int
        Minimum schema version
    default : Any
        Default attribute value to return if version check fails
    column : Any
        Column definition to return if version check passes
    """
    return column if DB.minVersion(version) else Stub(default)


def OptionalC(version, default, column):
    """Column optional attribute wrapper.

    If the specified version is not reached, a column_property is created that
    returns the default value and will not emit any SQL when changed and
    committed.
    In contrast to the non-column version `OptionalNC`, the stub can be used
    like an actual column.

    Parameters
    ----------
    version : int
        Minimum schema version
    default : str
        Default SQL expression to use if version check fails
    column : Any
        Column definition to return if version check passes
    """
    return column if DB.minVersion(version) else column_property(select([text(default)]).as_scalar())



class NotifyTable:
    """Helper class tracking inserts and deletes.

    Automatically calls derived classes `_commit` method to react accordingly"""
    __changed = False
    __active = True

    @classmethod
    def NTtouch(cls, *args, **kwargs):
        """Mark table as changed."""
        cls.__changed = True

    @classmethod
    def NTclear(cls, *args, **kwargs):
        """Mark table as unchanged."""
        cls.__changed = False

    @classmethod
    def NTcommit(cls, *args, **kwargs):
        """Call `_commit` if tbale was changed and tracking is active."""
        if cls.__active and cls.__changed and hasattr(cls, "_commit"):
            cls._commit(*args, **kwargs)
            cls.__changed = False

    @classmethod
    def NTregister(cls):
        """Register SQLAlchemy event handlers."""
        event.listen(cls, "after_delete", cls.NTtouch)
        event.listen(cls, "after_insert", cls.NTtouch)
        event.listen(DB.session, "after_commit", cls.NTcommit)
        event.listen(DB.session, "after_rollback", cls.NTclear)

    @classmethod
    def NTactive(cls, state, clear=False):
        """(De-)activate tracking, optionally clearing state."""
        cls.__active = state
        if clear:
            cls.NTclear()
