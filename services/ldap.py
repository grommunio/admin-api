# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH

from . import ServiceHub, ServiceDisabledError, ServiceUnavailableError

import ldap3
import ldap3.core.exceptions as ldapexc
import re
import yaml

from ldap3.utils.conv import escape_filter_chars
from tools.misc import GenericObject

import logging
logger = logging.getLogger("ldap")


def handleLdapError(service, error):
    if isinstance(error,
                  (ldapexc.LDAPSocketOpenError, ldapexc.LDAPSocketSendError, ldapexc.LDAPSessionTerminatedByServerError)):
        return ServiceHub.SUSPENDED


@ServiceHub.register("ldap", handleLdapError, maxreloads=3)
class LdapService:
    __initialized = False
    _templates = {}
    _unescapeRe = re.compile(rb"\\(?P<value>[a-fA-F0-9]{2})")

    _configMap = {"baseDn": "ldap_search_base",
                  "objectID": "ldap_object_id",
                  "users": "ldap_mail_attr",
                  "connection": "ldap_host",
                  "username": "ldap_mail_attr",
                  "searchAttributes": "ldap_user_search_attrs",
                  "displayName": "ldap_user_displayname"}

    @classmethod
    def init(cls):
        if cls.__initialized:
            return
        ldap3.set_config_parameter("POOLING_LOOP_TIMEOUT", 1)
        try:
            with open("res/ldapTemplates.yaml") as file:
                cls._templates = yaml.load(file, Loader=yaml.SafeLoader)
        except Exception:
            pass
        cls.__initialized = True

    def __init__(self, config=None):
        from tools import mconf
        self.init()
        self._config = config or mconf.LDAP
        self._userAttributes = self._checkConfig(self._config)
        if self._config.get("disabled"):
            raise ServiceDisabledError("Service disabled by configuration")
        try:
            self.conn = self.testConnection(self._config)
        except Exception as err:
            msg = " - ".join(str(arg) for arg in err.args) or type(err).__name__
            raise ServiceUnavailableError("Failed to connect to server: "+msg)
        if "defaultQuota" in self._config["users"]:
            self._defaultProps = {prop: self._config["users"]["defaultQuota"] for prop in
                                  ("storagequotalimit", "prohibitsendquota", "prohibitreceivequota")}
        else:
            self._defaultProps = {}

    @classmethod
    def _checkConfig(cls, config):
        for required in ("baseDn", "objectID", "users", "connection"):
            if required not in config or config[required] is None or len(config[required]) == 0:
                raise KeyError("Missing required config value '{}'".format(cls._configMap.get(required, required)))
        if "server" not in config["connection"] or config["connection"]["server"] is None or\
           len(config["connection"]["server"]) == 0:
            raise KeyError("Missing required config value 'ldap_host'")
        for required in ("username", "searchAttributes", "displayName"):
            if required not in config["users"] or config["users"][required] is None or len(config["users"][required]) == 0:
                raise KeyError("Missing required config value '{}'".format(cls._configMap.get(required, "user."+required)))
        _templatesEnabled = config["users"].get("templates", [])
        userAttributes = {}
        if "filter" in config["users"]:
            f = config["users"]["filter"]
            if f is not None and len(f) != 0 and f[0] != "(" and f[-1] != ")":
                config["users"]["filter"] = "("+f+")"
        for _template in _templatesEnabled:
            if _template not in cls._templates:
                raise ValueError("Unknown template '{}'".format(_template))
            userAttributes.update(cls._templates.get(_template, {}))
        userAttributes.update(config["users"].get("attributes", {}))
        userAttributes[config["users"]["displayName"]] = "displayname"
        return userAttributes

    def _matchFilters(self, ID):
        """Generate match filters string.

        Includes a filter for each entry in ldap.users.filters and adds ID filter.

        Parameters
        ----------
        ID : str or bytes
            Object ID of the LDAP person

        Returns
        -------
        str
            A string containing LDAP match filter expression.
        """
        filters = ")(".join(f for f in self._config["users"].get("filters", ()))
        return "(&({}={}){}{})".format(self._config["objectID"],
                                       self.escape_filter_chars(ID),
                                       ("("+filters+")") if len(filters) else "",
                                       self._config["users"].get("filter", ""))

    def _matchFiltersMulti(self, IDs):
        """Generate match filters string for multiple IDs.

        Includes a filter for each entry in ldap.users.filters and adds ID filters.

        Parameters
        ----------
        IDs : list of bytes or str
            List of IDs to match

        Returns
        -------
        str
            A string containing LDAP match filter expression.
        """
        filters = self._config["users"].get("filters", ())
        filters = ("("+")(".join(filters) + ")") if len(filters) > 0 else ""
        IDfilters = "(|{})".format("".join("({}={})".format(self._config["objectID"], self.escape_filter_chars(ID))
                                           for ID in IDs))
        return "(&{}{}{})".format(filters, IDfilters, self._config["users"].get("filter", ""))

    @property
    def _sbase(self):
        return self._searchBase(self._config)

    @classmethod
    def _searchBase(cls, conf):
        """Generate directory name to search.

        If configured, adds the ldap.users.subtree path to ldap.baseDn. Otherwise only ldap.baseDn is returned.

        Returns
        -------
        str
            LDAP directory to search for users.
        """
        if "users" in conf and "subtree" in conf["users"]:
            return conf["users"]["subtree"]+","+conf["baseDn"]
        return conf["baseDn"]

    @classmethod
    def _searchFilters(cls, query, userconf, domains=None):
        """Generate search filters string.

        Includes a filter for each entry in ldap.users.filters and adds substring filters for all attributes in
        ldap.users.searchAttributes.
        Optionally, an additional list of permitted domains can be used to further restrict matches.

        Parameters
        ----------
        query : str
            Username to search for.

        Returns
        -------
        str
            A string including all search filters.
        """
        username = userconf["username"]
        filterexpr = "".join("("+f+")" for f in userconf.get("filters", ()))
        domainexpr = "(|{})".format("".join("({}=*@{})".format(username, d) for d in domains)) if domains is not None else ""
        if query is not None:
            query = cls.escape_filter_chars(query)
            searchexpr = "(|{})".format("".join(("("+sattr+"=*"+query+"*)" for sattr in userconf["searchAttributes"])))
        else:
            searchexpr = ""
        return "(&{}{}{}{})".format(filterexpr, searchexpr, domainexpr, userconf.get("filter", ""))

    def _userComplete(self, user, required=None):
        """Check if LDAP object provides all required fields.

        If no required fields are specified, the default `objectID`,
        `users.username` and `users.displayname` config values are used.

        Parameters
        ----------
        user : LDAP object
            Ldap object to check
        required : iterable, optional
            List of field names. The default is None.

        Returns
        -------
        bool
            True if all required fields are present, False otherwise

        """
        props = required or (self._config["users"]["username"], self._config["users"]["displayName"], self._config["objectID"])
        res = all(prop in user and user[prop].value is not None for prop in props)
        return res

    def authUser(self, ID, password):
        """Attempt ldap bind for user with given ID and password

        Parameters
        ----------
        ID : str or bytes
            ID of the LDAP object representing the user
        password : str
            User password.

        Returns
        -------
        str
            Error message if authentication failed or None if successful
        """
        self.conn.search(self._sbase, self._matchFilters(ID))
        if len(self.conn.response) == 0:
            return "Invalid Username or password"
        if len(self.conn.response) > 1:
            return "Multiple entries found - please contact your administrator"
        userDN = self.conn.response[0]["dn"]
        try:
            ldap3.Connection(self._config["connection"].get("server"), user=userDN, password=password, auto_bind=True)
        except ldapexc.LDAPBindError:
            return "Invalid username or Password"

    def downsyncUser(self, ID, props=None):
        """Create dictionary representation of the user from LDAP data.

        The dictionary can be used to create or update a orm.users.Users object.

        Parameters
        ----------
        ID : str
            LDAP ID of the user object
        props : dict, optional
            UserProperties as dictionary. The default is a dictionary containing storagequotalimit property.

        Raises
        ------
        RuntimeError
            LDAP query failed

        Returns
        -------
        userdata : dict
            Dictionary representation of the LDAP user
        """
        try:
            self.conn.search(self._sbase, self._matchFilters(ID), attributes=["*", self._config["objectID"]])
        except Exception:
            return None
        if len(self.conn.entries) == 0:
            return None
        if len(self.conn.entries) > 1:
            raise RuntimeError("Multiple entries found - aborting")
        ldapuser = self.conn.entries[0]
        if not self._userComplete(ldapuser, (self._config["users"]["username"],)):
            return None
        userdata = dict(username=ldapuser[self._config["users"]["username"]].value)
        userdata["properties"] = props or self._defaultProps.copy()
        userdata["properties"].update({prop: ldapuser[attr].value
                                       for attr, prop in self._userAttributes.items() if attr in ldapuser})
        if self._config["users"].get("aliases"):
            aliasattr = self._config["users"]["aliases"]
            if aliasattr in ldapuser and ldapuser[aliasattr].value is not None:
                aliases = ldapuser[aliasattr].value
                userdata["aliases"] = aliases if isinstance(aliases, list) else [aliases]
                userdata["aliases"] = [alias[5:] if alias.lower().startswith("smtp:") else alias
                                       for alias in userdata["aliases"]]
            else:
                userdata["aliases"] = []
        return userdata

    def dumpUser(self, ID):
        """Download complete user description.

        Parameters
        ----------
        ID : str ot bytes
            LDAP object ID of the user

        Returns
        -------
        ldap3.abstract.entry.Entry
            LDAP object or None if not found or ambiguous
        """
        self.conn.search(self._sbase, self._matchFilters(ID), attributes=["*", self._config["objectID"]])
        return self.conn.entries[0] if len(self.conn.entries) == 1 else None

    @staticmethod
    def escape_filter_chars(text, encoding=None):
        return escape_filter_chars(text, encoding)

    def getAll(self, IDs):
        """Get user information for each ID.

        Queries the same information as getUserInfo.

        Parameters
        ----------
        IDs : list of bytes or str
            IDs o search

        Returns
        -------
        list
            List of GenericObjects with information about found users
        """
        users = self._config["users"]
        username, name = users["username"], users["displayName"]
        self.conn.search(self._sbase, self._matchFiltersMulti(IDs), attributes=[username, name, self._config["objectID"]])
        return [GenericObject(ID=entry[self._config["objectID"]].raw_values[0],
                              username=entry[username].value,
                              name=entry[name].value,
                              email=entry[username].value)
                for entry in self.conn.entries if self._userComplete(entry)]

    def getUserInfo(self, ID):
        """Get e-mail address of an ldap user.

        Parameters
        ----------
        ID : str or bytes
            Object ID of the LDAP user
        Returns
        -------
        GenericObject
            Object containing LDAP ID, username and display name of the user
        """
        users = self._config["users"]
        username, name = users["username"], users["displayName"]
        try:
            self.conn.search(self._sbase, self._matchFilters(ID), attributes=[username, name, self._config["objectID"]])
        except ldapexc.LDAPInvalidValueError:
            return None
        if len(self.conn.entries) != 1 or not self._userComplete(self.conn.entries[0]):
            return None
        entry = self.conn.entries[0]
        return GenericObject(ID=entry[self._config["objectID"]].raw_values[0],
                             username=entry[username].value,
                             name=entry[name].value,
                             email=entry[username].value)

    def searchUsers(self, query, domains=None, limit=25):
        """Search for ldap users matchig the query.

        Parameters
        ----------
        query : str
            String to match
        domains : list of str, optional
            Optional domain filter. The default is None.

        Returns
        -------
        list
            List of user objects containing ID, e-mail and name
        """
        IDattr = self._config["objectID"]
        name, email = self._config["users"]["displayName"], self._config["users"]["username"]
        try:
            exact = self.getUserInfo(self.unescapeFilterChars(query))
            exact = [] if exact is None or not self._userComplete(exact) else [exact]
        except Exception:
            exact = []
        self.conn.search(self._sbase,
                         self._searchFilters(query, self._config["users"], domains),
                         attributes=[IDattr, name, email],
                         paged_size=limit)
        return exact+[GenericObject(ID=result[IDattr].raw_values[0],
                                    email=result[email].value,
                                    name=result[name].value)
                      for result in self.conn.entries if self._userComplete(result)]

    @classmethod
    def testConfig(cls, config):
        cls.init()
        try:
            cls._checkConfig(config)
            cls.testConnection(config)
        except KeyError as err:
            return "Incomplete LDAP configuration: "+err.args[0]
        except ValueError as err:
            return "Invalid LDAP configuration: "+err.args[0]
        except Exception as err:
            return "Could not connect to LDAP server: "+" - ".join(str(v) for v in err.args)

    @classmethod
    def testConnection(cls, config, active=True):
        servers = config["connection"]["server"].split()
        pool = ldap3.ServerPool(servers, "FIRST", active=1)
        conn = ldap3.Connection(pool, user=config["connection"].get("bindUser"), password=config["connection"].get("bindPass"))
        if config["connection"].get("starttls") and not conn.start_tls():
            logger.warning("Failed to initiate StartTLS connection")
        if not conn.bind():
            raise ldapexc.LDAPBindError("LDAP bind failed ({}): {}".format(conn.result["description"], conn.result["message"]))
        if active:
            conn.search(cls._searchBase(config), cls._searchFilters(" ", userconf=config["users"]),
                        attributes=[], paged_size=0)
        return conn

    @classmethod
    def unescapeFilterChars(cls, text):
        """Reverse escape_filter_chars function.

        In contrast to ldap3.utils.conv.unescape_filter_chars, this function also processes arbitrary byte escapes.

        Parameters
        ----------
        text : str
            String generated by ldap3.utils.conv.escape_filter_chars


        Returns
        -------
        bytes
            bytes object containing unescaped data
        """
        raw = bytes(text, "utf-8")
        last = 0
        unescaped = bytes()
        for match in cls._unescapeRe.finditer(raw):
            unescaped += raw[last:match.start()]+bytes((int(match.group("value"), 16),))
            last = match.end()
        return unescaped if last != 0 else raw
