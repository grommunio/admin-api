# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH

from . import ServiceHub, ServiceDisabledError, ServiceUnavailableError, InstanceDefault

import ldap3
import ldap3.core.exceptions as ldapexc
import ldap3.utils.config as ldap3_conf
import re
import threading
import yaml

from ldap3.utils.conv import escape_filter_chars
import logging
logger = logging.getLogger("ldap")

# Reduce block time when LDAP server is not reachable
ldap3_conf.set_config_parameter("RESTARTABLE_SLEEPTIME", 1)
ldap3_conf.set_config_parameter("RESTARTABLE_TRIES", 2)


def handleLdapError(service, error):
    if isinstance(error,
                  (ldapexc.LDAPSocketOpenError, ldapexc.LDAPSocketSendError, ldapexc.LDAPSessionTerminatedByServerError,
                   ldapexc.LDAPMaximumRetriesError)):
        return ServiceHub.SUSPENDED


def argname(orgID=None):
    if orgID is not None:
        from orm.domains import Orgs
        org = Orgs.query.filter(Orgs.ID == orgID).with_entities(Orgs.name).first()
        return org.name if org else None


def orgid(orgspec):
    if orgspec is None:
        return 0
    try:
        return int(orgspec)
    except ValueError:
        from orm.domains import Orgs
        org = Orgs.query.filter(Orgs.name == orgspec).with_entities(Orgs.ID).first()
        if org is None:
            raise
        return org.ID


class SearchResult:
    def __init__(self, ldap, resultType, data):
        self._ldap = ldap
        userconf = ldap._config["users"]
        self.ID = data["raw_attributes"][ldap._config["objectID"]][0]
        self.data = data["attributes"]
        self.name = data["attributes"].get(userconf["displayName"]) or ""
        self.type = resultType
        self.error = None
        if resultType == "user":
            if userconf["username"] in data["attributes"] and data["attributes"][userconf["username"]]:
                self.email = self.username = self._reduce(data["attributes"][userconf["username"]])
            else:
                self.email = self.username = None
                self.error = "Missing username"
        elif resultType == "contact":
            self.username = None
            if userconf["contactname"] in data["attributes"]:
                self.email = self._reduce(data["attributes"][userconf["contactname"]])
            else:
                self.email = None
                self.error = "Missing e-mail address"
        else:
            self.error = "Unknown type"

    def __repr__(self):
        return "<{} {}>".format(self.type, self.email)

    def _chkConvert(self, requested):
        if self.error:
            raise ValueError("Cannot create {} data: {}".format(requested, self.error))
        if self.type != requested:
            raise TypeError("Cannot create {} data from {} object".format(requested, self.type))

    @staticmethod
    def _reduce(value, tail=False):
        """Reduce potentially multi-valued attribute to scalar.

        Parameters
        ----------
        value : Any
            Value to reduce
        tail : bool, optional
            Return additional elements in second return value. The default is False.

        Returns
        -------
        Any
            Scalar value (tail=False) or two-tuple containing the scalar and additional elements (tail=True).
        """
        res = (value[0], value[1:]) if isinstance(value, (list, tuple)) else (value, [])
        return res if tail else res[0]

    def userdata(self, props=None):
        if self.type == "contact":
            return self.contactdata(props)
        self._chkConvert("user")
        ldap = self._ldap
        ldapuser = self.data
        username, aliases = self._reduce(ldapuser[ldap._config["users"]["username"]], tail=True)
        userdata = dict(username=username.lower(), aliases=aliases)
        userdata["properties"] = props or ldap._defaultProps.copy()
        userdata["properties"].update({prop: " ".join(str(a) for a in ldapuser[attr]) if isinstance(ldapuser[attr], list)
                                       else ldapuser[attr] for attr, prop in ldap._userAttributes.items() if attr in ldapuser})
        if ldap._config["users"].get("aliases"):
            aliasattr = ldap._config["users"]["aliases"]
            if ldapuser.get(aliasattr) is not None:
                from tools import formats
                aliases = ldapuser[aliasattr]
                aliases = aliases if isinstance(aliases, list) else [aliases]
                aliases = [alias[5:] if alias.lower().startswith("smtp:") else alias for alias in aliases]
                userdata["aliases"] += [alias for alias in aliases if formats.email.match(alias)]
        return userdata

    def contactdata(self, props=None):
        self._chkConvert("contact")
        ldap = self._ldap
        ldapuser = self.data
        userdata = {}
        userdata["properties"] = props or ldap._defaultProps.copy()
        userdata["properties"].update({prop: " ".join(str(a) for a in ldapuser[attr]) if isinstance(ldapuser[attr], list)
                                       else ldapuser[attr] for attr, prop in ldap._userAttributes.items() if attr in ldapuser})
        return userdata


@ServiceHub.register("ldap", handleLdapError, maxreloads=3, argspec=((), (orgid,)), argname=argname)
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
            with open("res/ldapTemplates.yaml", encoding="utf-8") as file:
                cls._templates = yaml.load(file, Loader=yaml.SafeLoader)
        except Exception:
            pass
        cls.__initialized = True

    def __init__(self, orgID=None):
        from tools import mconf
        self.init()
        if orgID is None:
            self._config = mconf.LDAP
        else:
            self._config = self._loadOrgConfig(orgID)
        self._userAttributes = self._checkConfig(self._config)
        self.lock = threading.Lock()
        if self._config.get("disabled"):
            raise ServiceDisabledError("Service disabled by configuration")
        try:
            self.conn = self.testConnection(self._config)
        except ldap3.core.exceptions.LDAPInvalidDnError:
            raise ServiceUnavailableError("Invalid base DN")
        except Exception as err:
            msg = str(err.args[0]) if len(err.args) else type(err).__name__
            raise ServiceUnavailableError("Failed to connect to server: "+msg, *err.args[1:])
        if "defaultQuota" in self._config["users"]:
            self._defaultProps = {prop: self._config["users"]["defaultQuota"] for prop in
                                  ("storagequotalimit", "prohibitsendquota", "prohibitreceivequota")}
        else:
            self._defaultProps = {}

    def _attrSet(self, name, mode="user"):
        if isinstance(name, (list, tuple)):
            return name
        common = (self._config["objectID"],)
        if name == "idonly":
            return common
        if name == "all":
            return common+("*",)
        userconf = self._config["users"]
        common += (userconf["displayName"],)
        if mode == "user":
            return common+(userconf["username"],)
        return (common+(userconf["contactname"],)) if self._config["enableContacts"] else common

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
        for key, value in userAttributes.items():
            if value == "smtpaddress":
                config["users"]["contactname"] = key
                break
        config["enableContacts"] = bool(config["users"].get("contactFilter") and config["users"].get("contactname"))
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
        return "({}={})".format(self._config["objectID"], self.escape_filter_chars(ID))

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
        return "(|{})".format("".join("({}={})".format(self._config["objectID"], self.escape_filter_chars(ID)) for ID in IDs))

    @property
    def _sbase(self):
        return self._searchBase(self._config)

    def _search(self, baseFilter, *args, attributes=None, domains=None, filterIncomplete=True, limit=25, userconf=None,
                **kwargs):
        """Perform async search query.

        Parameters
        ----------
        *args : Any
            Arguments forwarded to conn.search
        **kwargs : Any
            Keyword arguments forwarded to conn.search

        Returns
        -------
        list
            Search result list
        """
        def filtered(results):
            return list(filter(lambda r: r.error is None, results)) if filterIncomplete else list(results)

        def searchPaged(typeFilter, type, *args, **kwargs):
            filterExpr = "(&{}{})".format(baseFilter, typeFilter) if baseFilter and typeFilter else baseFilter or typeFilter
            if not self.conn.search(self._sbase, filterExpr, *args, **kwargs):
                return []
            results = filtered(SearchResult(self, type, result) for result in self.conn.response)
            cookie = self.conn.result.get("controls", {}).get("1.2.840.113556.1.4.319", {}).get("value", {}).get("cookie")
            while cookie and (not limit or len(results) < limit) and \
                  self.conn.search(self._sbase, filterExpr, *args, **kwargs, paged_cookie=cookie):
                results += filtered(SearchResult(self, type, result) for result in self.conn.response)
                cookie = self.conn.result.get("controls", {}).get("1.2.840.113556.1.4.319", {}).get("value", {}).get("cookie")
            return results[:limit] if limit and len(results) > limit else results

        if limit:
            kwargs["paged_size"] = min(limit, kwargs.get("paged_size") or limit)
        userconf = userconf or self._config["users"]
        username = userconf["username"]
        domainexpr = "(|{})".format("".join("({}=*@{})".format(username, d) for d in domains)) if domains is not None else ""
        filterexpr = "".join("("+f+")" for f in userconf.get("filters", ()))
        userFilter = "(&{}{}{})".format(filterexpr, userconf.get("filter", ""), domainexpr)
        with self.lock:
            results = searchPaged(userFilter, "user", *args, attributes=self._attrSet(attributes, "user"), **kwargs)
            if limit:
                limit -= len(results)
            if self._config["enableContacts"] and (limit is None or limit > 0):
                results += searchPaged(self._config["users"]["contactFilter"], "contact", *args,
                                       attributes=self._attrSet(attributes, "contact"), **kwargs)
        return results

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
        if query:
            query = cls.escape_filter_chars(query)
            searchexpr = "(|{})".format("".join(("("+sattr+"=*"+query+"*)" for sattr in userconf["searchAttributes"])))
        else:
            searchexpr = ""
        return "{}".format(searchexpr) if searchexpr else ""

    @classmethod
    def _loadOrgConfig(cls, orgID):
        from orm.domains import OrgParam
        config = OrgParam.loadLdap(orgID)
        if config is None:
            raise InstanceDefault()
        return config

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
        response = self._search(self._matchFilters(ID), attributes="idonly")
        if len(response) == 0:
            return "Invalid Username or password"
        if len(response) > 1:
            return "Multiple entries found - please contact your administrator"
        userDN = response[0].data["dn"]
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
            response = self._search(self._matchFilters(ID), attributes="all")
        except Exception:
            return None
        if len(response) == 0:
            return None
        if len(response) > 1:
            raise RuntimeError("Multiple entries found - aborting")
        return response[0].userdata()

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
        res = self._search(self._matchFilters(ID), attributes="all")
        if len(res) != 1:
            return None
        res = res[0].data
        return yaml.dump({"DN": res["dn"]})+yaml.dump({"attributes": dict(res["attributes"])})

    @staticmethod
    def escape_filter_chars(text, encoding=None):
        return escape_filter_chars(text, encoding)

    def getAll(self, IDs):
        """Get user information for each ID.

        Queries the same information as getUserInfo.

        Parameters
        ----------
        IDs : list of bytes or str
            IDs to search

        Returns
        -------
        list
            List of GenericObjects with information about found users
        """
        return self._search(self._matchFiltersMulti(IDs))

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
        try:
            response = self._search(self._matchFilters(ID))
        except ldapexc.LDAPInvalidValueError:
            return None
        if len(response) != 1:
            return None
        return response[0]

    def searchUsers(self, query=None, domains=None, limit=25, pageSize=1000, filterIncomplete=True):
        """Search for ldap users matching the query.

        Parameters
        ----------
        query : str
            String to match
        domains : list of str, optional
            Optional domain filter. The default is None.
        limit : int, optional
            Maximum number of results to return or None for no limit. Default is 25.
        pageSize : int, optional
            Perform a paged search with given page size. Default is None.

        Returns
        -------
        list
            List of user objects containing ID, e-mail and name
        """
        try:
            exact = self.getUserInfo(self.unescapeFilterChars(query))
            exact = [] if exact is None else [exact]
        except Exception:
            exact = []
        response = self._search(self._searchFilters(query, self._config["users"], domains),
                                domains=domains,
                                paged_size=pageSize,
                                limit=limit,
                                filterIncomplete=filterIncomplete)
        return exact+response

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
        servers = [s[:-1] if s.endswith("/") else s for s in config["connection"]["server"].split()]
        pool = servers[0] if len(servers) == 1 else ldap3.ServerPool(servers, "FIRST", active=1)
        user = config["connection"].get("bindUser")
        password = config["connection"].get("bindPass")
        starttls = config["connection"].get("starttls")
        conn = ldap3.Connection(pool, user=user, password=password, client_strategy=ldap3.RESTARTABLE)
        if starttls and not conn.start_tls():
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
