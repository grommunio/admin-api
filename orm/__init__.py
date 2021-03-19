# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grammm GmbH

__all__ = ["domains", "misc", "users", "ext"]

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker
from urllib.parse import quote_plus

from tools.config import Config

import logging


class DBConn:
    def __init__(self, URI):
        self.engine = create_engine(URI)
        self.session = scoped_session(sessionmaker(self.engine))
        outerself = self
        class Model:
            query = outerself.session.query_property()
        self.Base = declarative_base(cls=Model)

    def enableFlask(self, API):
        from flask import _app_ctx_stack
        self.session = scoped_session(sessionmaker(self.engine), _app_ctx_stack.__ident_func__)

        @API.teardown_appcontext
        def removeSession(*args, **kwargs):
            self.session.remove()


def _loadDBConfig():
    """Load database parameters from configuration.

    Outputs error messages to log stream if mandatory parameters are missing.

    Returns
    -------
    str
        Database URI including connection and credentials

    """
    if "DB" not in Config:
        logging.error("No database configuration found")
        return None
    DBconf = Config["DB"]
    if "user" not in DBconf or "pass" not in DBconf:
        logging.error("Database user or password missing")
        return None
    if "database" not in DBconf:
        logging.error("No database specified.")
        return None
    if "host" not in DBconf and "port" not in DBconf:
        logging.info("Database connection not specified. Using default '127.0.0.1:3306'")
    host = DBconf.get("host", "127.0.0.1")
    port = DBconf.get("port", 3306)
    return "mysql+mysqldb://{user}:{password}@{host}:{port}/{db}".format(user=quote_plus(DBconf["user"]),
                                                                         password=quote_plus(DBconf["pass"]),
                                                                         host=quote_plus(host),
                                                                         port=port,
                                                                         db=quote_plus(DBconf["database"]))


if Config["options"]["disableDB"]:
    DB = None
    logging.warn("Database disabled in configuration")
else:
    DB_uri = _loadDBConfig()
    if DB_uri is not None:
        DB = DBConn(DB_uri)
        try:
            DB.session.execute("SELECT 1 FROM DUAL")
            DB.session.remove()
        except OperationalError as err:
            DB = None
            logging.error("Database connection failed with error {}: {}".format(err.orig.args[0], err.orig.args[1]))
    else:
        logging.warn("Database configuration failed. No data will be available")
        DB = None
