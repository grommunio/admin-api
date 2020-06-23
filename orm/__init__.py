#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jun 23 11:22:02 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: _Placeholder_copyright_
"""

from api import API, Config
from flask_sqlalchemy import SQLAlchemy


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
    host = DBconf["host"] if "host" in DBconf else "localhost"
    port = DBconf["port"] if "port" in DBconf else 3306
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


def printRelation(relation):
    """Pretty print a relationship.

    Parameters
    ----------
    relation : SQLAlechemy relationship
        Relationship to print.

    Returns
    -------
    str
        String representation of the relationship.
    """
    if relation is None:
        return "None"
    if hasattr(relation, "displayName"):
        return "'{}'".format(relation.displayName())
    if hasattr(relation, "name"):
        return "'{}'".format(relation.name)
    return repr(relation)


def printDate(date, time=False):
    """Pretty print date.

    Parameters
    ----------
    date : datetime.datetime
        Date to print
    time : boolean, optional
        Include time information. The default is False.

    Returns
    -------
    str
        String representation of the date (and time, if applicable)
    """
    return date.strftime("%Y-%m-%d %H:%M" if time else "%Y-%m-%d") if date is not None else None
