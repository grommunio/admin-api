# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grammm GmbH

__all__ = ["domains", "misc", "users", "ext"]

from api.core import API
from flask_sqlalchemy import SQLAlchemy

from tools.config import Config


def _loadDBConfig():
    """Load database parameters from configuration.

    Outputs error messages to log stream if mandatory parameters are missing.

    Returns
    -------
    str
        Database URI including connection and credentials

    """
    if "DB" not in Config:
        API.logger.error("No database configuration found")
        return None
    DBconf = Config["DB"]
    if "user" not in DBconf or "pass" not in DBconf:
        API.logger.error("No user and password provided")
        return None
    if "database" not in DBconf:
        API.logger.error("No database specified.")
        return None
    if "host" not in DBconf and "port" not in DBconf:
        API.logger.info("Database connection not specified. Using default '127.0.0.1:3306'")
    host = DBconf.get("host", "127.0.0.1")
    port = DBconf.get("port", "3306")
    return "mysql+mysqldb://{user}:{password}@{host}:{port}/{db}".format(user=DBconf["user"],
                                                                         password=DBconf["pass"],
                                                                         host=host,
                                                                         port=port,
                                                                         db=DBconf["database"])


if Config["options"]["disableDB"]:
    DB = None
    API.logger.warn("Database disabled in configuration")
else:
    DB_uri = _loadDBConfig()
    if DB_uri is not None:
        API.config["SQLALCHEMY_DATABASE_URI"] = DB_uri
        API.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        DB = SQLAlchemy(API)
    else:
        API.logger.warn("Database configuration failed. No data will be available")
        DB = None

    del DB_uri
