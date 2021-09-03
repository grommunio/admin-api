# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH

from argparse import ArgumentParser

from . import Cli

SUCCESS = 0
ERR_DECLINE = 1  # User declined prompt
ERR_USR_ABRT = 2  # User aborted
ERR_NO_LDAP = 3  # LDAP not available
ERR_GENERIC = 4  # Something went wrong
ERR_NO_USER = 5  # LDAP User not found
ERR_AMBIG = 6  # Request was ambiguous
ERR_DB = 7  # Error occured when communicating with the database
ERR_CONFLICT = 8  # Target DB user is associated with another LDAP object
ERR_COMMIT = 9  # Error during database commit
ERR_INVALID_DATA = 10  # User data check failed
ERR_SETUP = 11  # Error during user setup


def _getv(cli, prompt="", default="", secret=False):
    from getpass import getpass
    v = (getpass if secret else cli.input)("{}{}: ".format(prompt, " ["+str(default)+"]" if default is not None else ""))
    return default if v == "" else v


def _geti(cli, prompt="", default=0):
    res = None
    while res is None:
        res = _getv(cli, prompt, default)
        try:
            res = int(res)
        except:
            res = None
    return res


def _getc(cli, prompt="", default="", choices=(), getter=_getv):
    res = None
    while res is None:
        res = getter(cli, prompt, default)
        if res in choices:
            return res


def _getl(cli, prompt="", defaults=[]):
    cli.print(prompt+":")
    values = []
    defiter = (d for d in defaults)
    try:
        while True:
            val = _getv(cli, "", next(defiter, ""))
            if val == "":
                raise EOFError
            values.append(val)
    except EOFError:
        cli.print("[Done]")
    return values


def _reloadGromoxHttp(cli):
    from services import Service
    with Service("systemd", Service.SUPPRESS_ALL) as sysd:
        sysd.reloadService("gromox-http.service")


def cliLdapInfo(args):
    cli = args._cli
    cli.require("LDAP")
    from services import Service
    with Service("ldap", Service.SUPPRESS_INOP) as ldap:
        cli.print("Successfully connected to {}:{} as {}".format(cli.col(ldap.conn.server.host, attrs=["bold"]),
                                                                 cli.col(ldap.conn.server.port, attrs=["dark"]),
                                                                 ldap._config["connection"].get("bindUser", "<anonymous>")))


def _getCandidate(cli, expr, auto):
    from services import Service
    with Service("ldap") as ldap:
        try:
            candidate = ldap.getUserInfo(ldap.unescapeFilterChars(expr))
        except Exception:
            candidate = None
        if candidate is None:
            matches = ldap.searchUsers(expr)
            if len(matches) == 0:
                cli.print(cli.col("Could not find user matching '{}'".format(expr), "red"))
                return ERR_NO_USER
            if len(matches) == 1:
                candidate = matches[0]
            else:
                if auto:
                    cli.print(cli.col("Multiple candidates for '{}' found - aborting".format(expr), "red"))
                    return ERR_AMBIG
                cli.print("Found {} users matching '{}':".format(len(matches), expr))
                for i in range(len(matches)):
                    cli.print("{: 2d}: {} ({})".format(i+1, matches[i].name, matches[i].email))
                candidate = None
                while candidate is None:
                    try:
                        selected = _getc(cli, "Choose index of user (1-{}) or CTRL+C to exit".format(len(matches)),
                                         choices=range(len(matches)), getter=_geti)
                        index = int(selected)-1
                        if not 0 <= index < len(matches):
                            continue
                        candidate = matches[index]
                    except (EOFError, KeyboardInterrupt):
                        cli.print("k bye.")
                        return ERR_USR_ABRT
                    except ValueError:
                        continue
        return candidate


def _getCandidates(expr):
    from services import Service
    with Service("ldap") as ldap:
        try:
            candidate = ldap.getUserInfo(ldap.unescapeFilterChars(expr))
            return [candidate]
        except Exception:
            ldap.searchUsers(expr)


def _downsyncUser(cli, candidate, yes, auto, force, reloadHttp=True):
    from services import Service
    if yes or auto:
        cli.print("Synchronizing user '{}' ({})".format(candidate.name, candidate.email))
    else:
        result = cli.confirm("Synchronize user '{}' ({})? [y/N]: ".format(candidate.name, candidate.email))
        if result != Cli.SUCCESS:
            if result == Cli.ERR_USR_ABRT:
                cli.print("\nAborted.")
            return result

    from orm import DB
    if DB is None:
        cli.print("Database not configured")
        return ERR_DB
    from orm.domains import Domains
    from orm.users import Users
    from tools.DataModel import MismatchROError, InvalidAttributeError

    if "@" not in candidate.email:
        cli.print(cli.col("Cannot derive domain from e-mail address, aborting.", "red"))
        return ERR_INVALID_DATA
    domain = Domains.query.filter(Domains.domainname == candidate.email.split("@")[1]).with_entities(Domains.ID).first()
    if domain is None:
        cli.print(cli.col("Cannot import user: Domain not found", "red"))
        return ERR_INVALID_DATA
    user = Users.query.filter(Users.externID == candidate.ID).first() or\
        Users.query.filter(Users.username == candidate.email).first()
    if user is not None:
        if user.externID != candidate.ID and not force:
            if auto:
                cli.print(cli.col("Cannot import user: User exists " +
                          ("locally" if user.externID is None else "and is associated with another LDAP object"), "red"))
                return ERR_CONFLICT
            else:
                result = cli.confirm("Force update "+("local only user" if user.externID is None else
                                                      "user linked to different LDAP object")+"? [y/N]: ")
                if result != Cli.SUCCESS:
                    if result == Cli.ERR_USR_ABRT:
                        cli.print("Aborted.")
                    return result
        with Service("ldap") as ldap:
            userdata = ldap.downsyncUser(candidate.ID, user.propmap)
        try:
            user.fromdict(userdata)
            user.externID = candidate.ID
            DB.session.commit()
            cli.print("User updated.")
            return SUCCESS
        except (InvalidAttributeError, MismatchROError, ValueError) as err:
            DB.session.rollback()
            cli.print(cli.col("Failed to update user: "+err.args[0], "red"))
            return ERR_COMMIT

    with Service("ldap") as ldap:
        userdata = ldap.downsyncUser(candidate.ID)
    if userdata is None:
        cli.print(cli.col("Error retrieving user", "red"))
        return ERR_NO_USER
    result, code = Users.create(userdata, reloadGromoxHttp=False, externID=candidate.ID)
    if code != 201:
        cli.print(cli.col("Failed to create user: "+result, "red"))
        return ERR_COMMIT
    cli.print("User '{}' created with ID {}.".format(cli.col(result.username, attrs=["bold"]),
                                                     cli.col(result.ID, attrs=["bold"])))
    if reloadHttp:
        Users.NTcommit()
    return SUCCESS


def cliLdapDownsync(args):
    cli = args._cli
    cli.require("DB", "LDAP")
    from services import Service
    from orm.users import Aliases, Users
    error = False
    if args.user is not None and len(args.user) != 0:
        for expr in args.user:
            candidate = _getCandidate(cli, expr, args.auto)
            if isinstance(candidate, int):
                error = True
                if candidate == ERR_USR_ABRT:
                    break
                continue
            result = _downsyncUser(cli, candidate, args.yes, args.auto, args.force)
            if result == ERR_USR_ABRT:
                break
            error = error or result != SUCCESS
        return ERR_GENERIC if error else SUCCESS
    elif args.complete:
        with Service("ldap") as ldap:
            candidates = ldap.searchUsers(None, limit=None)
        if len(candidates) == 0:
            cli.print(cli.col("No LDAP users found.", "yellow"))
            return SUCCESS
        cli.print("Synchronizing {} user{}...".format(len(candidates), "" if len(candidates) == 1 else "s"))
        error = False
        Aliases.NTactive(False)
        Users.NTactive(False)
        for candidate in candidates:
            result = _downsyncUser(cli, candidate, args.yes, args.auto, args.force, False)
            error = error or result != SUCCESS
            if result == ERR_USR_ABRT:
                break
        Aliases.NTactive(True, True)
        Users.NTactive(True, True)
        _reloadGromoxHttp(cli)
        return ERR_GENERIC if error else SUCCESS
    from orm.users import Users
    users = Users.query.filter(Users.externID != None).with_entities(Users.externID).all()
    if len(users) == 0:
        cli.print(cli.col("No imported users found", "yellow"))
        return SUCCESS
    with Service("ldap") as ldap:
        candidates = ldap.getAll(user.externID for user in users)
    if len(candidates) != len(users):
        cli.print(cli.col("Some ldap references seem to be broken - please run ldap check", "yellow"))
    if len(candidates) == 0:
        cli.print("No users to synchronize")
        return SUCCESS
    error = False
    cli.print("Synchronizing {} user{}...".format(len(candidates), "" if len(candidates) == 1 else "s"))
    Aliases.NTactive(False)
    Users.NTactive(False)
    for candidate in candidates:
        result = _downsyncUser(cli, candidate, args.yes, args.auto, args.force, False)
        error = error or result != SUCCESS
        if result == ERR_USR_ABRT:
            break
    Aliases.NTactive(True, True)
    Users.NTactive(True, True)
    _reloadGromoxHttp(cli)
    return ERR_GENERIC if error else SUCCESS


def cliLdapSearch(args):
    cli = args._cli
    cli.require("LDAP")
    from services import Service
    with Service("ldap") as ldap:
        matches = ldap.searchUsers(args.query, limit=args.max_results or None)
        if len(matches) == 0:
            cli.print(cli.col("No "+("matches" if args.query else "entries"), "yellow"))
            return ERR_NO_USER
        for match in matches:
            cli.print("{}: {} ({})".format(cli.col(ldap.escape_filter_chars(match.ID), attrs=["bold"]), match.name,
                                           match.email if match.email else cli.col("N/A", "red")))
        cli.print("({} match{})".format(len(matches), "" if len(matches) == 1 else "es"))


def cliLdapCheck(args):
    cli = args._cli
    cli.require("DB", "LDAP")
    from services import Service
    from time import time
    from orm import DB
    from orm.users import Users
    users = Users.query.filter(Users.externID != None).with_entities(Users.ID, Users.username, Users.externID, Users.maildir)\
                       .all()
    if len(users) == 0:
        cli.print("No imported users found. You can import users using 'ldap downsync <name>' or 'ldap downsync --complete'.")
        return
    cli.print("Checking {} user{}...".format(len(users), "" if len(users) == 1 else "s"))
    count, last = 0, time()
    orphaned = []
    with Service("ldap") as ldap:
        for user in users:
            if ldap.getUserInfo(user.externID) is None:
                orphaned.append(user)
            count += 1
            if time()-last > 1:
                last = time()
                cli.print("\t{}/{} checked ({:.0f}%), {} orphaned"
                          .format(count, len(users), count/len(users)*100, len(orphaned)))
    if len(orphaned) == 0:
        cli.print("Everything is ok")
        return
    cli.print("LDAP entries of the following users could not be found:")
    for user in orphaned:
        cli.print("\t"+user.username)
    if args.remove:
        if args.yes or cli.confirm("Delete all orphaned users? [y/N]: ") == Cli.SUCCESS:
            cli.print("Unloading exmdb stores...")
            if len(orphaned):
                with Service("exmdb", Service.SUPPRESS_INOP) as exmdb:
                    client = exmdb.ExmdbQueries(exmdb.host, exmdb.port, orphaned[0].maildir, True)
                    for user in orphaned:
                        client.unloadStore(user.maildir)
            if args.remove_maildirs:
                import shutil
                cli.print("Removing mail directories...")
                for user in orphaned:
                    shutil.rmtree(user.maildir, ignore_errors=True)
            deleted = Users.query.filter(Users.ID.in_(user.ID for user in orphaned)).delete(synchronize_session=False)
            DB.session.commit()
            cli.print("Deleted {} user{}".format(deleted, "" if deleted == 1 else "s"))
    return ERR_NO_USER


def cliLdapDump(args):
    cli = args._cli
    cli.require("LDAP")
    from services import Service
    with Service("ldap") as ldap:
        for expr in args.user:
            for candidate in _getCandidates(expr):
                cli.print(cli.col("ID: "+ldap.escape_filter_chars(candidate.ID), attrs=["bold"]))
                cli.print(str(ldap.dumpUser(candidate.ID)))


def _applyTemplate(index, conf):
    conf["users"] = conf.get("users", {})
    if index == 1:  # AD
        conf["objectID"] = "objectGUID"
        conf["users"]["aliases"] = "proxyAddresses"
        conf["users"]["displayName"] = "displayName"
        conf["users"]["username"] = "mail"
    elif index == 2:  # OpenLDAP
        conf["objectID"] = "entryUUID"
        conf["users"]["aliases"] = "mailAlternativeAddress"
        conf["users"]["displayName"] = "displayname"
        conf["users"]["username"] = "mailPrimaryAddress"


def _checkConn(cli, connfig):
    cli.print(cli.col("Checking connectivity...", attrs=["dark"]), end="", flush=True)
    from services.ldap import LdapService
    try:
        LdapService.testConnection({"connection": connfig}, active=False)
    except Exception as exc:
        cli.print(cli.col("\nConnection check failed: "+" - ".join(str(arg) for arg in exc.args), "red"))
        res = cli.choice("(a)bort, (c)ontinue anyway, (e)dit configuration? [e]: ", "ace", "e")
        if res in (None, "a"):
            raise KeyboardInterrupt
        return res == "c"
    cli.print(cli.col("success!", "green", attrs=["dark"]))
    return True


def _getConf(cli, old):
    conf = {"connection": {}, "users": {"filters": [], "searchAttributes": []}}
    connected = False
    connfig = old.get("connection", {}).copy()
    while not connected:
        oldpw = "[***]" if connfig.get("bindPass") else "[]"
        connfig["server"] = _getv(cli, "URL of the LDAP server(s)", connfig.get("server", ""))
        connfig["bindUser"] = _getv(cli, "Username for access", connfig.get("bindUser"), )
        connfig["bindPass"] = _getv(cli, "Password for access "+oldpw, None, True) or connfig.get("bindPass")
        connfig["starttls"] = _getc(cli, "Use StartTLS connection",
                                    "y" if connfig.get("starttls") else "n", ("y", "n")) == "y"
        connected = _checkConn(cli, connfig)
    conf["connection"] = connfig
    conf["baseDn"] = _getv(cli, "DN for user lookup/searches", old.get("baseDn", ""))
    users = old.get("users", {})
    oldtempl = users.get("templates", ())
    res = _getc(cli, "Choose a template:\n 0: No template\n 1: ActiveDirectory\n 2: OpenLDAP\n",
                1 if "ActiveDirectory" in oldtempl else 2 if "OpenLDAP" in oldtempl else 0, range(2), _geti)
    conf["users"]["templates"] = [] if res == 0 else ["common", "ActiveDirectory" if res == 1 else "OpenLDAP"]
    if res != 0 and cli.confirm("Apply default template parameters? [y/N]: ") == Cli.SUCCESS:
        _applyTemplate(res, old)
        users = old.get("users", {})
    conf["objectID"] = _getv(cli, "Attribute containing unique object ID", old.get("objectID"))
    conf["users"]["username"] = _getv(cli, "Attribute containing e-mail address of a user", users.get("username", ""))
    conf["users"]["displayName"] = _getv(cli, "Attribute containing name of a user", users.get("displayName", ""))
    conf["users"]["aliases"] = _getv(cli, "Attribute containing alternative e-mail addresses", users.get("aliases", ""))
    conf["users"]["defaultQuota"] = _geti(cli, "Default storage quota for imported users (0=unlimited)", users.get("defaultQuota", 0))
    conf["users"]["filter"] = _getv(cli, "Enter filter expression for user search", users.get("filter", ""))
    conf["users"]["searchAttributes"] = _getl(cli, "Enter attributes used for searching (one per line)",
                                              users.get("searchAttributes", []))
    if not conf["users"]["defaultQuota"]:
        conf["users"].pop("defaultQuota")
    return conf


def _cliLdapConfigure(args):
    cli = args._cli
    try:
        from services.ldap import LdapService
        from tools import mconf
        LdapService.init()
        old = mconf.LDAP
        while True:
            new = _getConf(cli, old)
            cli.print("Checking new configuration...")
            error = LdapService.testConfig(new)
            if error is None:
                cli.print("Configuration successful.")
                error = mconf.dumpLdap(new)
                cli.print("Configuration saved" if error is None else ("Failed to save configuration: "+error))
                break
            cli.print(cli.col(error, "yellow"))
            action = _getc(cli, "Restart configuration? (r=Restart, a=Amend, s=Save anyway, q=quit)", "a", ("y", "a", "s", "q"))
            if action == "s":
                error = mconf.dumpLdap(new)
                cli.print("Configuration saved" if error is None else ("Failed to save configuration: "+error))
            if action in "sq":
                break
            if action == "a":
                old = new
            if action == "r":
                old = mconf.LDAP
    except (KeyboardInterrupt, EOFError):
        cli.print(cli.col("\nAborted."))
        return 1
    from services import ServiceHub
    ServiceHub.load("ldap", force_reload=True)


def cliLdapReload(args):
    cli = args._cli
    from services import ServiceHub
    ServiceHub.load("ldap", force_reload=True)
    cli.print("Reload successful" if ServiceHub["ldap"].state == ServiceHub.LOADED else cli.col("Reload failed", "red"))
    return int(ServiceHub["ldap"].state != ServiceHub.LOADED)


def _cliLdapParserSetup(subp: ArgumentParser):
    sub = subp.add_subparsers()
    check = sub.add_parser("check", help="Check LDAP objects of imported users still exist")
    check.set_defaults(_handle=cliLdapCheck)
    check.add_argument("-y", "--yes", action="store_true", help="Do not prompt for user deletion (only with -r)")
    check.add_argument("-r", "--remove", action="store_true", help="Prompt for user deletion if orphaned users exist")
    check.add_argument("-m", "--remove-maildirs", action="store_true", help="When deleting users, also remove their mail "\
                                                                            "directories from disk")
    configure = sub.add_parser("configure", help="Run interactive LDAP configuration")
    configure.set_defaults(_handle=_cliLdapConfigure)
    downsync = sub.add_parser("downsync", help="Import or update users from ldap")
    downsync.set_defaults(_handle=cliLdapDownsync)
    downsync.add_argument("user", nargs="*", help="LDAP ID or user search query string. If omitted, all users linked to an "\
                                                  "LDAP object are updated.")
    downsync.add_argument("-a", "--auto", action="store_true", help="Do not prompt, exit with error instead. Implies -y.")
    downsync.add_argument("-c", "--complete", action="store_true", help="Import/update all users in the ldap tree")
    downsync.add_argument("-f", "--force", action="store_true", help="Force synchronization of unassociated users")
    downsync.add_argument("-y", "--yes", action="store_true", help="Proceed automatically if target is unambiguous")
    dump = sub.add_parser("dump", help="Dump LDAP object")
    dump.set_defaults(_handle=cliLdapDump)
    dump.add_argument("user", nargs="+", help="User ID or search query string")
    info = sub.add_parser("info", help="Check LDAP status")
    info.set_defaults(_handle=cliLdapInfo)
    reload = sub.add_parser("reload", help="Reload LDAP configuration")
    reload.set_defaults(_handle=cliLdapReload)
    search = sub.add_parser("search", help="Search LDAP tree")
    search.set_defaults(_handle=cliLdapSearch)
    search.add_argument("query", nargs="?", help="Optional search query, omit to return all users")
    search.add_argument("-n", "--max-results", type=int, default=25,
                        help="Maximum number of results or 0 to disable limit (default: 25)")


@Cli.command("ldap", _cliLdapParserSetup, help="LDAP configuration, diagnostics and synchronization")
def cliLdap(args):
    if hasattr(args, "_handle") and args._handle != cliLdap:
        return args._handle(args) or 0
    else:
        return cliLdapInfo(args)
