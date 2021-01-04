# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grammm GmbH

import ldap3
from ldap3.core.exceptions import LDAPBindError, LDAPSocketOpenError, LDAPSocketSendError
from ldap3.utils.conv import escape_filter_chars

import logging

from .config import Config


class LDAPGuard:
    """LDAP connection proxy class."""

    def __init__(self, Base, *args, **kwargs):
        self.__base = Base
        self.__args = args
        self.__kwargs = kwargs
        self.__error = None
        self.__obj = None
        self.__connect()

    def __getattr__(self, name):
        if not self.__connect():
            raise self.__error
        attr = getattr(self.__obj, name)
        if callable(attr):
            def proxyfunc(*args, **kwargs):
                try:
                    return attr(*args, **kwargs)
                except (LDAPSocketOpenError, LDAPSocketSendError):
                    logging.warn("LDAP socket error - reconnecting")
                    if not self.__connect(True):
                        raise self.__error
                    nattr = getattr(self.__obj, name)
                    return nattr(*args, **kwargs)
            return proxyfunc
        return attr

    def __connect(self, reconnect=False):
        if self.__obj is not None and not reconnect:
            return True
        try:
            self.__obj = self.__base(*self.__args, **self.__kwargs)
            return True
        except LDAPBindError as err:
            logging.error("Could not connect to ldap server: bind failed")
            self.__error = err
        except LDAPSocketOpenError as err:
            logging.error("Could not connect to ldap server: " + err.args[0])
            self.__error = err
        return False


def _searchFilters(uid):
    """Generate search filters string.

    Includes a filter for each entry in ldap.users.filters and adds uid filter.

    Parameters
    ----------
    uid : str
        Username to search for.

    Returns
    -------
    str
        A string including all search filters.
    """
    ldapconf = Config["ldap"]
    filters = ")(".join(f for f in ldapconf.get("users", {}).get("filters", ()))
    return "(&({}={}){})".format(ldapconf["users"].get("uid", "uid"),
                                 escape_filter_chars(uid),
                                 ("("+filters+")") if len(filters) else "")


def _searchBase():
    """Generate directory name to search.

    If configured, adds the ldap.users.subtree path to ldap.baseDn. Otherwise only ldap.baseDn is returned.

    Returns
    -------
    str
        LDAP directory to search for users.
    """
    if "users" in ldapconf and "subtree" in ldapconf["users"]:
        return ldapconf["users"]["subtree"]+","+ldapconf["baseDn"]
    return ldapconf["baseDn"]


def authUser(uid, password):
    if not LDAP_available:
        return False, "LDAP not configured"
    LDAPConn.search(_searchBase(), _searchFilters(uid))
    if len(LDAPConn.response) == 0:
        return False, "Invalid Username or password"
    if len(LDAPConn.response) > 1:
        return False, "Multiple entries found - please contact your administrator"
    userDN = LDAPConn.response[0]["dn"]
    try:
        ldap3.Connection(ldapconf["connection"].get("server"), user=userDN, password=password, auto_bind=True)
    except LDAPBindError:
        return False, "Invalid username or Password"
    return True, {"uid": uid}


if "connection" in Config["ldap"]:
    ldapconf = Config["ldap"]
    LDAPConn = LDAPGuard(ldap3.Connection,
                         ldapconf["connection"].get("server"),
                         user=ldapconf["connection"].get("bindUser"),
                         password=ldapconf["connection"].get("bindPass"),
                         auto_bind=True)
    LDAP_available = True
else:
    LDAP_available = False
