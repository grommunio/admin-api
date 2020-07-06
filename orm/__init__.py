# -*- coding: utf-8 -*-
"""
Created on Tue Jun 23 11:22:02 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: _Placeholder_copyright_
"""

__all__ = ["misc", "orgs", "users"]

from api import API
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
