# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH

from argparse import ArgumentParser
from . import Cli
from .common import Table


SUCCESS = 0
ERR_DECLINE = 1  # User declined prompt
ERR_USR_ABRT = 2  # User aborted
ERR_NO_LDAP = 3  # LDAP not available
ERR_GENERIC = 4  # Something went wrong
ERR_NO_USER = 5  # LDAP User not found
ERR_AMBIG = 6  # Request was ambiguous
ERR_DB = 7  # Error occurred when communicating with the database
ERR_CONFLICT = 8  # Target DB user is associated with another LDAP object
ERR_COMMIT = 9  # Error during database commit
ERR_INVALID_DATA = 10  # User data check failed
ERR_SETUP = 11  # Error during user setup
ERR_PARTIAL = 12  # Some users failed to synchronize (batch mode)

_ldapObjectColor = {
    "contact": "blue",
    "group": "cyan",
    "user": "green",
    }


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


def _getUsernameOrg(username):
    if "@" not in username:
        return None
    from orm.domains import Domains
    domain = Domains.query.filter(Domains.domainname == username.split("@", 1)[1]).with_entities(Domains.orgID).first()
    if domain is None:
        return None
    return domain.orgID


def _getOrgID(spec):
    from orm.domains import Orgs
    if spec == "0":
        return 0
    if Orgs.query.filter(Orgs.ID == spec).count() == 1:
        return int(spec)
    org = Orgs.query.filter(Orgs.name == spec).with_entities(Orgs.ID).first()
    if org is None:
        raise ValueError("Organization '{}' not found".format(spec))
    return org.ID


def _getOrgIDs(args):
    from orm.domains import OrgParam
    if "organization" not in args or not args.organization:
        return (0,)
    if "*" in args.organization:
        return [0]+OrgParam.ldapOrgs()
    return tuple(_getOrgID(spec) for spec in args.organization)


def _getOrgName(orgID):
    if orgID == 0:
        return "(no organization)"
    from orm.domains import Orgs
    org = Orgs.query.filter(Orgs.ID == orgID).with_entities(Orgs.name).first()
    if org is None:
        return "(unknown organozation)"
    return org.name


def _isSuccess(code):
    return code//100 == 2


def _userOrgFilter(args, orgIDs=None):
    from orm.users import Users
    return (Users.orgID.in_(orgIDs or _getOrgIDs(args)),)


def cliLdapInfo(args):
    cli = args._cli
    from services import Service
    for orgID in _getOrgIDs(args):
        with Service("ldap", orgID, errors=Service.SUPPRESS_INOP) as ldap:
            cli.print("Successfully connected to {}:{} as {}".format(cli.col(ldap.conn.server.host, attrs=["bold"]),
                                                                     cli.col(ldap.conn.server.port, attrs=["dark"]),
                                                                     ldap._config["connection"].get("bindUser", "<anonymous>")))


def _getCandidate(cli, expr, ldap):
    try:
        candidate = ldap.getUserInfo(ldap.unescapeFilterChars(expr))
        if candidate is not None:
            return candidate
    except Exception:
        pass
    matches = ldap.searchUsers(expr)
    if len(matches) == 0:
        cli.print(cli.col("Could not find LDAP object matching '{}'".format(expr), "red"))
        return None
    if len(matches) == 1:
        return matches[0]
    for match in matches:
        if match.email == expr:
            return match
    cli.print(cli.col(f"'{expr}' is ambiguous: ", "red"))
    cli.print(cli.col("\n  ".join(match.email for match in matches), "yellow"))
    return None


def _getCandidates(expr, ldap):
    candidate = ldap.getUserInfo(ldap.unescapeFilterChars(expr))
    return [candidate] if candidate is not None else ldap.searchUsers(expr)


def _downsync(args, user, externID=None, syncMembers=False, **kwargs):
    from tools.ldap import downsyncGroup, downsyncUser
    cli = args._cli

    cli.print("Synchronizing {}...".format(user.username), end="", flush=True)

    isGroup = user.properties["displaytypeex"] == 1
    if not isGroup:
        message, code = downsyncUser(user, externID)
    else:
        from orm.mlists import MLists
        mlist = MLists.query.filter(MLists.listname == user.username).first()
        mlist.listname = mlist.listname.lower()
        if not mlist:
            cli.print(cli.col(f"Failed to synchronize {user.username}: no such group"))
            return False
        message, code = downsyncGroup(mlist, externID)
    cli.print(cli.col(message, "green" if _isSuccess(code) else "red"))
    if syncMembers and isGroup:
        _syncGroupMembers(args, mlist.user.orgID, mlist.user.externID)
    return _isSuccess(code)


def _importContact(args, candidate, ldap, orgID, syncExisting=False, **kwargs):
    from tools.ldap import importContact
    styleGood = {"color": "green"}
    styleNeutral = {"attrs": ["dark"]}
    styleBad = {"color": "red"}

    cli = args._cli
    cli.print("Importing {}...".format(candidate.email), end="", flush=True)
    synced, imported, errors = importContact(candidate, ldap, orgID, syncExisting)
    cli.print(cli.col(f"{len(synced)} synced", **styleGood if synced else styleNeutral)+", ", end="")
    cli.print(cli.col(f"{len(imported)} imported", **styleGood if imported else styleNeutral)+", ", end="")
    cli.print(cli.col(f"{len(errors)} failed", **styleBad if errors else styleNeutral))
    for error in errors:
        cli.print(cli.col("  "+error[0], "yellow"))
    return len(synced)+len(imported), len(errors)


def _importUser(args, candidate, ldap, **kwargs):
    from tools.ldap import importUser
    cli = args._cli

    cli.print("Importing {} {}...".format(candidate.type, candidate.email), end="", flush=True)
    result, code = importUser(candidate, ldap, args.force, args.lang)
    if not _isSuccess(code):
        cli.print(cli.col(result, "red"))
        return 0, 1
    cli.print(cli.col(f"imported as user #{result.ID}", "green"))
    return 1, 0


def _importGroup(args, candidate, ldap, syncMembers=False, **kwargs):
    from tools.ldap import importGroup
    cli = args._cli

    cli.print("Importing {}...".format(candidate.email), end="", flush=True)
    result, code = importGroup(candidate, ldap, args.force)
    if not _isSuccess(code):
        cli.print(cli.col(result, "red"))
        return 0, 1
    cli.print(cli.col(f"imported as user #{result.user.ID}/group #{result.ID}", "green"))
    if syncMembers:
        _syncGroupMembers(args, result.user.orgID, candidate.ID)
    return 1, 0


def _import(args, candidate, ldap, orgID, **kwargs):
    cli = args._cli
    if candidate.type == "contact":
        return _importContact(args, candidate, ldap, orgID, **kwargs)
    targetOrg = _getUsernameOrg(candidate.email)
    if targetOrg != orgID:
        cli.print(cli.col("Skipping '{}': invalid domain".format(candidate.email), "red"))
        return 0, 1
    if candidate.type == "group":
        return _importGroup(args, candidate, ldap, **kwargs)
    if candidate.type == "user":
        return _importUser(args, candidate, ldap, **kwargs)
    cli.print(cli.col(f"Unknown object type {candidate.type}"))


def _syncGroupMembers(args, orgID, groupID=None):
    from services import Service
    from tools.ldap import syncGroupMembers
    cli = args._cli

    with Service("ldap", orgID) as ldap:
        ldapgroups = [ldap.getUserInfo(groupID)] if groupID else ldap.searchUsers(types=("group",))
        for ldapgroup in ldapgroups:
            cli.print(f"Synchronizing members of group {ldapgroup.email}...", end="", flush=True)
            add, remove = syncGroupMembers(orgID, ldapgroup, ldap)
            if None in (add, remove):
                cli.print(cli.col("group not found", attrs=["dark"]))
            else:
                cli.print(cli.col(f"{add} added, {remove} removed" if add+remove else "no changes", "green"))


def _downsyncOrg(args, orgID, ldap, resCount):
    cli = args._cli
    from orm.domains import Domains
    from orm.users import Users
    domainnames = [d.domainname for d in Domains.query.filter(Domains.orgID == orgID).with_entities(Domains.domainname)]
    if len(domainnames) == 0:
        cli.print(cli.col("Organization '{}' has no domains - skipping.".format(_getOrgName(orgID)), "yellow"))
        return (0, 0)
    synced = set()
    for user in Users.query.filter(Users.orgID == orgID, Users.externID != None):
        result = _downsync(args, user)
        if user.status != Users.CONTACT:
            synced.add(user.externID)
        resCount.success += result
        resCount.failed += not result

    if args.complete:
        from services import Service
        with Service("ldap", orgID) as ldap:
            candidates = [candidate for candidate in ldap.searchUsers() if candidate.ID not in synced]
            for candidate in candidates:
                os, of = _import(args, candidate, ldap, orgID, syncExisting=False)
                resCount.success += os
                resCount.failed += of
    _syncGroupMembers(args, orgID)


def _downsyncSpecific(args, orgIDs, resCount):
    if "user" not in args or not args.user:
        return (0, 0)
    cli = args._cli
    from orm.users import Users
    for username in args.user:
        user = Users.query.filter(Users.username == username).first()
        if user:
            result = _downsync(args, user, syncMembers=True)
            resCount.success += result
            resCount.failed += not result
        else:
            from services import Service
            with Service("ldap", orgIDs[0]) as ldap:
                candidate = _getCandidate(cli, username, ldap)
                if not candidate:
                    resCount.failed += 1
                    continue
                os, of = _import(args, candidate, ldap, orgIDs[0], syncExisting=True, syncMembers=True)
                resCount.success += os
                resCount.failed += of


def cliLdapDownsync(args):
    cli = args._cli
    cli.require("DB")
    from orm.users import Aliases, Users
    from services import Service, ServiceUnavailableError
    from tools.misc import GenericObject
    Aliases.NTactive(False)
    Users.NTactive(False)
    orgIDs = _getOrgIDs(args)
    resCount = GenericObject(success=0, failed=0)
    _downsyncSpecific(args, orgIDs, resCount)
    if not resCount.success+resCount.failed:
        for orgID in orgIDs:
            try:
                with Service("ldap", orgID, errors=Service.SUPPRESS_INOP) as ldap:
                    _downsyncOrg(args, orgID, ldap, resCount)
            except ServiceUnavailableError:
                cli.print(cli.col(f"Failed to synchronize organization #{orgID} - service unavailable"))
    Aliases.NTactive(True)
    Users.NTactive(True)
    cli.print(cli.col("{} synchronized, {} failed".format(resCount.success, resCount.failed), attrs=["dark"]))
    return 0 if not resCount.failed else ERR_PARTIAL


def cliLdapSearch(args):
    def typename(match):
        color = "yellow" if match.error else _ldapObjectColor.get(match.type, "magenta")
        return col(match.type, color)

    def col(text, *pargs, **kwargs):
        return cli.col(text, *pargs, **kwargs) if pretty else text

    cli = args._cli
    pretty = args.format == "pretty"
    from services import Service
    orgIDs = _getOrgIDs(args)
    types = args.types.split(",") if args.types else None
    for orgID in orgIDs:
        with Service("ldap", orgID) as ldap:
            if len(orgIDs) > 1:
                cli.print(cli.col(_getOrgName(orgID), "green"))
            matches = ldap.searchUsers(args.query, limit=args.max_results or None, pageSize=args.page_size,
                                       filterIncomplete=not args.all, types=types)
            hasErr = any(match.error is not None for match in matches)
            data = [(col(ldap.escape_filter_chars(match.ID), attrs=["bold"]), typename(match),
                     match.email if match.email else col("N/A", "red"), match.name,
                     col(match.error or "", "yellow"))
                    for match in matches if match.ID]
            table = Table(data, ("ID", "Type", "E-Mail", "Name", "Note" if hasErr or not pretty else ""),
                          empty=cli.col("(No results)", attrs=["dark"]) if pretty else None)
            table.dump(cli, args.format)
            if len(matches) and not pretty:
                cli.print(cli.col("({} result{})".format(len(matches), "s" if len(matches) != 1 else ""), attrs=["dark"]))


def cliLdapCheck(args):
    cli = args._cli
    cli.require("DB")
    from services import Service, ServiceUnavailableError
    from time import time
    from orm import DB
    from orm.users import Users
    users = Users.query.filter(Users.externID != None, *_userOrgFilter(args))\
                       .with_entities(Users.ID, Users.username, Users.externID, Users.maildir, Users.orgID).all()
    if len(users) == 0:
        cli.print("No imported users found. You can import users using 'ldap downsync <name>' or 'ldap downsync --complete'.")
        return
    cli.print("Checking {} user{}...".format(len(users), "" if len(users) == 1 else "s"))
    count, last = 0, time()
    orphaned = []
    for user in users:
        try:
            with Service("ldap", user.orgID) as ldap:
                if ldap.getUserInfo(user.externID) is None:
                    orphaned.append(user)
                count += 1
                if time()-last > 1:
                    last = time()
                    cli.print("\t{}/{} checked ({:.0f}%), {} orphaned"
                              .format(count, len(users), count/len(users)*100, len(orphaned)))
        except ServiceUnavailableError:
            cli.print(cli.col("\tFailed to check user '"+user.username+"' - LDAP not available", "red"))
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
                homeserver = None
                users = Users.query.filter(Users.ID.in_(orphan.ID for orphan in orphaned)).order_by(Users.homeserverID).all()
                index = 0
                while index < len(users):
                    try:
                        with Service("exmdb") as exmdb:
                            if homeserver != users[index].homeserverID:  # Reuse the exmdb client for users on the same server
                                user = users[index]
                                client = exmdb.ExmdbQueries(exmdb.host if user.homeserverID == 0 else user.homeserver.hostname,
                                                            exmdb.port, user.maildir, True)
                                homeserver = user.homeserverID
                            while index < len(users) and users[index].homeserverID == homeserver:
                                client.unloadStore(users[index].maildir)
                                index += 1
                    except ServiceUnavailableError:
                        cli.print(cli.col("Failed to unload store: exmdb service not available", "yellow"))
                        index += 1
                if args.remove_maildirs:
                    import shutil
                    cli.print("Removing mail directories...")
                    for user in orphaned:
                        shutil.rmtree(user.maildir, ignore_errors=True)
                for user in users:
                    user.delete()
            DB.session.commit()
            cli.print("Deleted {} user{}".format(len(users), "" if len(users) == 1 else "s"))
            return
    return ERR_NO_USER


def cliLdapDump(args):
    cli = args._cli
    ldapArgs = (args.organization,) if args.organization else ()
    from services import Service
    results = 0
    with Service("ldap", *ldapArgs) as ldap:
        for expr in args.user:
            for candidate in _getCandidates(expr, ldap):
                cli.print(cli.col("ID: "+ldap.escape_filter_chars(candidate.ID), attrs=["bold"]))
                cli.print(str(ldap.dumpUser(candidate.ID)))
                results += 1
    cli.print(cli.col("({} result{})".format(results, "s" if results != 1 else ""), attrs=["dark"]))


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
    conf["baseDn"] = _getv(cli, "Search base for user lookup/searches", old.get("baseDn", ""))
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
    conf["users"]["defaultQuota"] = _geti(cli, "Default storage quota for imported users (0=unlimited)",
                                          users.get("defaultQuota", 0))
    conf["users"]["filter"] = _getv(cli, "Enter filter expression for user search", users.get("filter", ""))
    conf["users"]["contactFilter"] = _getv(cli, "Enter filter expression for contact search", users.get("contactFilter", ""))
    conf["users"]["searchAttributes"] = _getl(cli, "Enter attributes used for searching (one per line)",
                                              users.get("searchAttributes", []))
    if not conf["users"]["defaultQuota"]:
        conf["users"].pop("defaultQuota")
    return conf


def _cliLdapGetConf(args):
    if args.organization:
        from orm.domains import OrgParam
        args.organization = _getOrgID(args.organization)
        old = OrgParam.loadLdap(args.organization)
    if not args.organization or not old:
        from tools import mconf
        old = mconf.LDAP
    return old


def cliLdapShowConf(args):
    cli = args._cli
    if args.organization:
        from orm.domains import OrgParam
        args.organization = _getOrgID(args.organization)
        old = OrgParam.loadLdap(args.organization)
    else:
        from tools import mconf
        old = mconf.LDAP
    import json
    output = json.dumps(old, indent=4)
    cli.print(output)


def _cliLdapSaveConf(args, conf):
    if not args.organization:
        from tools import mconf
        return mconf.dumpLdap(conf)
    from orm.domains import OrgParam
    OrgParam.saveLdap(args.organization, conf)


def _cliLdapConfigure(args):
    from services import ServiceHub
    try:
        cli = args._cli
        if args.delete:
            if not args.organization:
                cli.print(cli.col("Cannot delete default configuration"))
                return 2
            orgID = _getOrgID(args)
            from orm.domains import OrgParam
            OrgParam.wipeLdap(orgID)
            cli.print("Configuration deleted.")
            ServiceHub.load("ldap", orgID, force_reload=True)
            return

        from services.ldap import LdapService
        LdapService.init()
        old = _cliLdapGetConf(args)
        while True:
            new = _getConf(cli, old)
            cli.print("Checking new configuration...")
            error = LdapService.testConfig(new)
            if error is None:
                cli.print("Configuration successful.")
                _cliLdapSaveConf(args, new)
                cli.print("Configuration saved" if error is None else ("Failed to save configuration: "+error))
                break
            cli.print(cli.col(error, "yellow"))
            action = _getc(cli, "Restart configuration? (r=Restart, a=Amend, s=Save anyway, q=quit)",
                           "a", ("y", "a", "s", "q"))
            if action == "s":
                _cliLdapSaveConf(args, new)
            if action in "sq":
                break
            if action == "a":
                old = new
    except (KeyboardInterrupt, EOFError):
        cli.print(cli.col("\nAborted."))
        return 1
    except ValueError as err:
        cli.print(cli.col(err.args[0], "red"))
    ldapArgs = (args.organization,) if args.organization else ()
    ServiceHub.load("ldap", *ldapArgs, force_reload=True)


def cliLdapReload(args):
    from services import ServiceHub
    cli = args._cli
    ldapArgs = (args.organization,) if args.organization else ()
    res = ServiceHub.load("ldap", *ldapArgs, force_reload=True)
    cli.print("Reload successful" if res.state == ServiceHub.LOADED else cli.col("Reload failed", "red"))
    return int(res.state != ServiceHub.LOADED)


def _cliOrgspecCompleter(prefix, **kwargs):
    from orm.domains import Orgs
    return (org.name for org in Orgs.query.filter(Orgs.name.ilike(prefix+"%")).with_entities(Orgs.name).all())


def _cliLdapParserSetup(subp: ArgumentParser):
    sub = subp.add_subparsers()
    check = sub.add_parser("check", help="Check LDAP objects of imported users still exist")
    check.set_defaults(_handle=cliLdapCheck)
    check.add_argument("-m", "--remove-maildirs", action="store_true", help="When deleting users, also remove their mail "
                                                                            "directories from disk")
    check.add_argument("-o", "--organization", metavar="ORGSPEC", action="append",
                       help="Use organization specific LDAP connection").completer = _cliOrgspecCompleter
    check.add_argument("-r", "--remove", action="store_true", help="Prompt for user deletion if orphaned users exist")
    check.add_argument("-y", "--yes", action="store_true", help="Do not prompt for user deletion (only with -r)")
    configure = sub.add_parser("configure", help="Run interactive LDAP configuration")
    configure.set_defaults(_handle=_cliLdapConfigure)
    configure.add_argument("-d", "--delete", action="store_true", help="Do not configure anything, but delete configuration")
    configure.add_argument("-o", "--organization", metavar="ORGSPEC", help="Use organization specific LDAP connection")\
        .completer = _cliOrgspecCompleter
    downsync = sub.add_parser("downsync", help="Import or update users from ldap")
    downsync.set_defaults(_handle=cliLdapDownsync)
    downsync.add_argument("user", nargs="*", help="LDAP ID or user search query string. If omitted, all users linked to an "
                                                  "LDAP object are updated.")
    downsync.add_argument("-c", "--complete", action="store_true", help="Import/update all users in the ldap tree")
    downsync.add_argument("-f", "--force", action="store_true", help="Force synchronization of unassociated users")
    downsync.add_argument("-l", "--lang", help="Default language for imported users")
    downsync.add_argument("-o", "--organization", metavar="ORGSPEC", action="append",
                          help="Use organization specific LDAP connection").completer = _cliOrgspecCompleter
    downsync.add_argument("-p", "--page-size", type=int, default=1000, help="Page size when downloading users")
    dump = sub.add_parser("dump", help="Dump LDAP object")
    dump.set_defaults(_handle=cliLdapDump)
    dump.add_argument("-o", "--organization", metavar="ORGSPEC", help="Use organization specific LDAP connection")\
        .completer = _cliOrgspecCompleter
    dump.add_argument("user", nargs="+", help="User ID or search query string")
    info = sub.add_parser("info", help="Check LDAP status")
    info.set_defaults(_handle=cliLdapInfo)
    info.add_argument("-o", "--organization", metavar="ORGSPEC", action="append",
                      help="Use organization specific LDAP connection").completer = _cliOrgspecCompleter
    reload = sub.add_parser("reload", help="Reload LDAP configuration")
    reload.set_defaults(_handle=cliLdapReload)
    reload.add_argument("-o", "--organization", metavar="ORGSPEC", help="Use organization specific LDAP connection")\
        .completer = _cliOrgspecCompleter
    search = sub.add_parser("search", help="Search LDAP tree")
    search.set_defaults(_handle=cliLdapSearch)
    search.add_argument("query", nargs="?", help="Optional search query, omit to return all users")
    search.add_argument("-a", "--all", action="store_true", help="Also show users that cannot be imported")
    search.add_argument("--format", choices=Table.FORMATS, help="Set output format",
                        metavar="FORMAT", default="pretty")
    search.add_argument("-n", "--max-results", type=int, default=0,
                        help="Maximum number of results or 0 to disable limit (default: 0)")
    search.add_argument("-o", "--organization", metavar="ORGSPEC", action="append",
                        help="Use organization specific LDAP connection").completer = _cliOrgspecCompleter
    search.add_argument("-p", "--page-size", type=int, default=1000, help="Page size when downloading users")
    search.add_argument("-t", "--types", help="Comma separated list of results types to search for")
    show = sub.add_parser("show", help="Show current LDAP config")
    show.set_defaults(_handle=cliLdapShowConf)
    show.add_argument("-o", "--organization", metavar="org-name", help="Show organization specific LDAP config") \
        .completer = _cliOrgspecCompleter


@Cli.command("ldap", _cliLdapParserSetup, help="LDAP configuration, diagnostics and synchronization")
def cliLdap(args):
    return cliLdapInfo(args)
