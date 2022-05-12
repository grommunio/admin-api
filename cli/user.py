# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH

from . import Cli, InvalidUseError
from .common import proptagCompleter

from argparse import ArgumentParser

_statusMap = {0: "active", 1: "suspended", 2: "out-of-date", 3: "deleted"}
_statusColor = {0: "green", 1: "yellow", 2: "yellow", 3: "red"}


def _mkUserQuery(args):
    from .common import userFilter
    from orm.users import Users
    query = Users.query.filter(userFilter(args.userspec))
    if "filter" in args and args.filter is not None:
        query = Users.autofilter(query, {f.split("=", 1)[0]: f.split("=", 1)[1] for f in args.filter if "=" in f})
    if "sort" in args and args.sort is not None:
        query = Users.autosort(query, args.sort)
    return query


def _mkStatus(cli, status):
    return cli.col(_statusMap.get(status, "unknown"), _statusColor.get(status, "magenta"))


def _dumpUser(cli, user, indent=0):
    def privstr():
        from orm.users import Users
        bits = user.privilegeBits
        privs = []
        if bits & Users.USER_PRIVILEGE_POP3_IMAP:
            privs.append("pop_imap")
        if bits & Users.USER_PRIVILEGE_SMTP:
            privs.append("smtp")
        if bits & Users.USER_PRIVILEGE_CHGPASSWD:
            privs.append("passwd")
        if bits & Users.USER_PRIVILEGE_PUBADDR:
            privs.append("pubaddr")
        if bits & Users.USER_PRIVILEGE_CHAT:
            privs.append("chat")
        if bits & Users.USER_PRIVILEGE_VIDEO:
            privs.append("video")
        if bits & Users.USER_PRIVILEGE_FILES:
            privs.append("files")
        if bits & Users.USER_PRIVILEGE_ARCHIVE:
            privs.append("archive")
        if len(privs) == 0:
            return ""
        return "("+",".join(privs)+")"

    from ldap3.utils.conv import escape_filter_chars
    homeserver = cli.col("(local)", attrs=["dark"]) if user.homeserver is None else \
        "{} ({})".format(user.homeserver.ID, user.homeserver.hostname)
    cli.print("{}ID: {}".format(" "*indent, user.ID))
    cli.print("{}username: {}".format(" "*indent, user.username))
    cli.print("{}domainID: {}".format(" "*indent, user.domainID))
    cli.print("{}homeserver: {}".format(" "*indent, homeserver))
    cli.print("{}maildir: {}".format(" "*indent, user.maildir or cli.col("(not set)", attrs=["dark"])))
    cli.print("{}privilegeBits: {} {}".format(" "*indent, user.privilegeBits, cli.col(privstr(), attrs=["dark"])))
    cli.print("{}addressStatus: {} ({}|{})".format(" "*indent, user.addressStatus,
                                                   _mkStatus(cli, user.domainStatus), _mkStatus(cli, user.status)))
    cli.print(" "*indent+"ldapID: "+(escape_filter_chars(user.externID) if user.externID is not None else
                                       cli.col("(none)", attrs=["dark"])))
    cli.print(" "*indent+"chat: "+(user.chatID if user.chatID else cli.col("(none)", attrs=["dark"])) +
              (" ("+cli.col("inactive", "red")+")" if user.chatID and not user.chat else ""))
    if user.chat:
        cli.print(" "*indent+"chatAdmin: "+(cli.col("yes", "yellow") if user.chatAdmin else "no"))
    cli.print(" "*indent+"aliases:"+(cli.col(" (none)", attrs=["dark"]) if len(user.aliases) == 0 else ""))
    for alias in user.aliases:
        cli.print(" "*indent+"  "+alias.aliasname)
    cli.print(" "*indent+"roles:"+(cli.col(" (none)", attrs=["dark"]) if len(user.roles) == 0 else ""))
    for role in user.roles:
        cli.print(" "*indent+"  "+role.name)
    cli.print(" "*indent+"fetchmail:"+(cli.col(" (none)", attrs=["dark"]) if len(user.fetchmail) == 0 else ""))
    for fml in user.fetchmail:
        cli.print("{}  {}@{}/{} ({})".format(" "*indent, fml.srcUser, fml.srcServer, fml.srcFolder,
                                             cli.col("active", "green") if fml.active == 1 else cli.col("inactive", "red")))
    cli.print(" "*indent+"properties:"+(cli.col(" (none)", attrs=["dark"]) if len(user.properties) == 0 else ""))
    for key, value in user.properties.items():
        cli.print("{}  {}: {}".format(" "*indent, key, value))


def _getUser(args):
    cli = args._cli
    users = _mkUserQuery(args).all()
    if len(users) == 0:
        cli.print(cli.col("No user matching '{}'.".format(args.userspec), "yellow"))
        return 1, None
    if len(users) > 1:
        cli.print("'{}' is ambiguous. Candidates are:".format(args.userspec))
        for user in users:
            cli.print("  {}:\t{}".format(user.ID, user.username))
        return 2, None
    return 0, users[0]


def _splitData(args):
    cliargs = {"_handle", "_cli", "userspec", "no_defaults"}
    data = {}
    attributes = data["attributes"] = {key: value for key, value in args.items() if value is not None and key not in cliargs}
    data["aliases"] = attributes.pop("alias", None) or ()
    data["aliases_rm"] = attributes.pop("remove_alias", None) or ()
    data["props"] = attributes.pop("property", None) or []
    data["props_rm"] = attributes.pop("remove_property", None) or []
    data["storeprops"] = attributes.pop("storeprop", None) or []
    data["storeprops_rm"] = attributes.pop("remove_storeprop", None) or []
    data["noldap"] = attributes.pop("no_ldap", False)
    return data


def _updateStoreprops(cli, user, props, props_rm=()):
    if not (props or props_rm):
        return
    from tools.constants import PropTags, ExchangeErrors
    import pyexmdb
    add, remove = [], []
    for pv in props:
        prop, val = pv.split("=", 1)
        try:
            prop, val = PropTags.normalize(prop, val)
            add.append(pyexmdb.TaggedPropval(prop, val))
        except ValueError as err:
            cli.print(cli.col("Failed to set store property '{}': {}".format(prop, err.args[0]), "yellow"))
        except TypeError:
            cli.print(cli.col("Failed to set store property '{}': Tag type not supported"), "yellow")
    for p in props_rm:
        try:
            prop = PropTags.deriveTag(p)
            remove.append(prop)
        except ValueError as err:
            cli.print(cli.col("Failed to set store property '{}': {}".format(prop, err.args[0]), "yellow"))
    if not (add or remove):
        return
    from services import Service, ServiceUnavailableError
    try:
        with Service("exmdb") as exmdb:
            client = exmdb.user(user)
            if len(remove):
                client.removeStoreProperties(remove)
            if len(add):
                problems = client.setStoreProperties(0, add)
                if problems:
                    problems = [(PropTags.lookup(entry.proptag, hex(entry.proptag)).lower(),
                                 ExchangeErrors.lookup(entry.err, hex(entry.err)))
                                for entry in problems]
                    cli.print(cli.col("Problems where encountered setting the following tags:\n\t" +
                                      "\n\t".join("{} ({})".format(tag, err) for tag, err in problems), "yellow"))
    except (pyexmdb.ExmdbError, ServiceUnavailableError) as err:
        cli.print(cli.col("Failed to set store properties: "+err.args[0], "yellow"))


def cliUserShow(args):
    cli = args._cli
    cli.require("DB")
    users = _mkUserQuery(args).all()
    if len(users) == 0:
        cli.print(cli.col("No users found.", "yellow"))
        return 1
    for user in users:
        cli.print(cli.col("{} ({}):".format(user.username, user.ID), attrs=["bold"]))
        _dumpUser(cli, user, 2)


def cliUserList(args):
    cli = args._cli
    cli.require("DB")
    users = _mkUserQuery(args).all()
    if len(users) == 0:
        cli.print(cli.col("No users found.", "yellow"))
        return 1
    maxNameLen = max(len(user.username) for user in users)
    for user in users:
        if user.domainName() is not None:
            printName = "{}@{}".format(cli.col(user.baseName(), attrs=["bold"]), user.domainName())
        else:
            printName = cli.col(user.username, attrs=["bold"])
        cli.print("{}:\t{}{}({}|{})".format(user.ID, printName, " "*(maxNameLen-len(user.username)+4),
                                            _mkStatus(cli, user.domainStatus), _mkStatus(cli, user.status)))
    cli.print("({} users total)".format(len(users)))


def cliUserCreate(args):
    cli = args._cli
    cli.require("DB")
    from orm.domains import Domains
    from orm.misc import DBConf
    from orm.users import DB, Users
    from tools.misc import RecursiveDict
    if args.no_defaults:
        props = {}
    else:
        props = DBConf.getFile("grommunio-admin", "defaults-system", True).get("user", RecursiveDict())
        if "@" in args.username:
            domain = Domains.query.filter(Domains.domainname == args.username.split("@", 1)[1]).with_entities(Domains.ID).first()
            if domain is not None:
                props.update(DBConf.getFile("grommunio-admin", "defaults-domain-"+str(domain.ID), True).get("user", {}))
    data = _splitData(args.__dict__)
    props.update(data["attributes"])
    props["username"] = args.username
    props["aliases"] = data["aliases"]
    properties = data["properties"] = {}
    for pv in data["props"]+data["storeprops"]:
        if "=" in pv:
            prop, val = pv.split("=", 1)
            properties[prop] = val
    props["properties"] = properties
    result, code = Users.create(props)
    if code != 201:
        cli.print(cli.col("Could not create user: "+result, "red"))
        return 1
    DB.session.commit()
    _updateStoreprops(cli, result, data["storeprops"])
    _dumpUser(cli, result)


def cliUserDelete(args):
    cli = args._cli
    cli.require("DB")
    from orm import DB
    from tools.misc import GenericObject
    ret, user = _getUser(args)
    if ret:
        return ret
    userdata = GenericObject(maildir=user.maildir, homeserver=user.homeserver)
    if not args.yes:
        if cli.confirm("Delete user '{}' ({})? [y/N]: ".format(user.username, user.ID)) != Cli.SUCCESS:
            return 3
    else:
        cli.print("Deleting user '{}' ({})".format(user.username, user.ID))
    user.delete()
    DB.session.commit()
    cli.print("User deleted.")
    if userdata.maildir == "":
        cli.print("No user files to delete.")
        return 0
    cli.print("Unloading store...", end="", flush=True)

    from services import Service
    with Service("exmdb", Service.SUPPRESS_INOP) as exmdb:
        client = exmdb.user(user)
        client.unloadStore()
        cli.print("Done.", end="")
    cli.print("")
    if args.keep_files or (not args.yes and cli.confirm("Delete user directory from disk? [y/N]: ") != Cli.SUCCESS):
        cli.print(cli.col("Files remain in "+userdata.maildir, attrs=["bold"]))
        return 0
    cli.print("Deleting user files...", end="")
    import shutil
    shutil.rmtree(userdata.maildir, ignore_errors=True)
    cli.print("Done.")


def cliUserModify(args):
    cli = args._cli
    cli.require("DB")
    from orm import DB
    from orm.users import Aliases
    ret, user = _getUser(args)
    if ret:
        return ret
    data = _splitData(args.__dict__)
    if data["noldap"]:
        user.externID = None
    try:
        user.fromdict(data["attributes"])
        if data["aliases"]:
            existing = {a.aliasname for a in user.aliases}
            user.aliases += [Aliases(alias, user) for alias in data["aliases"] if alias not in existing]
        if data["aliases_rm"]:
            user.aliases = [alias for alias in user.aliases if alias.aliasname not in data["aliases_rm"]]
        for pv in data["props"]+data["storeprops"]:
            try:
                prop, val = pv.split("=", 1)
                user.properties[prop] = val
            except (KeyError, ValueError) as err:
                cli.print(cli.col("Failed to set property '{}': {}".format(prop, err.args[0]), "yellow"))
        for prop in data["props_rm"]+data["storeprops_rm"]:
            try:
                user.properties[prop] = None
            except KeyError:
                cli.print(cli.col("Failed to remove property '{}'".format(prop), "yellow"))
    except ValueError as err:
        cli.print(cli.col("Failed to update user: "+err.args[0], "red"))
        return 1
    DB.session.commit()
    _updateStoreprops(cli, user, data["storeprops"], data["storeprops_rm"])
    _dumpUser(cli, user)


def _cliUserspecCompleter(prefix, **kwargs):
    from orm.users import Users
    return (user.username for user in Users.query.filter(Users.username.ilike(prefix+"%"))
                                                 .with_entities(Users.username).all())


def _cliParseStatus(value):
    try:
        return int(value)
    except Exception:
        pass
    from orm.users import Users
    value = value.lower()
    if value == "normal":
        return Users.NORMAL
    if value == "suspended":
        return Users.SUSPENDED
    if value in ("outofdate", "out-of-date"):
        return Users.OUTOFDATE
    if value == "deleted":
        return Users.DELETED
    if value == "shared":
        return Users.SHARED
    raise ValueError("Unknown user status '{}'".format(value))


def _cliAddUserAttributes(parser: ArgumentParser):
    def getBool(val):
        if not val.isdigit() and val.lower() not in ("yes", "no", "true", "false", "y", "n"):
            raise ValueError("'{}' cannot be interpreted as boolean.".format(val))
        return bool(int(val)) if val.isdigit() else val in ("yes", "true", "y")

    def optBool(val):
        if not val.isdigit() and val.lower() not in ("yes", "no", "true", "false", "y", "n"):
            return val
        return bool(int(val)) if val.isdigit() else val in ("yes", "true", "y")

    def assignment(arg):
        if "=" not in arg:
            raise ValueError("'{}' is not an assignment".format(arg))
        return arg

    def proptagAssignCompleter(*args, **kwargs):
        return proptagCompleter(*args, **kwargs, addSuffix="=")

    parser.add_argument("--changePassword", type=getBool, metavar="<bool>", help="Whether the user can change the password")
    parser.add_argument("--chat", type=optBool, metavar="<bool>", help="Whether to create a chat user")
    parser.add_argument("--chatAdmin", type=getBool, metavar="<bool>", help="Whether the user has chat admin privileges")
    parser.add_argument("--homeserver", type=int, metavar="ID", help="ID of the home server or 0 for local user")
    parser.add_argument("--lang", help="User store language")
    parser.add_argument("--ldapID", help="Identifier of the LDAP object linked to the user")
    parser.add_argument("--pop3-imap", type=getBool, metavar="<bool>", help="Whether the user has the POP3/IMAP privilege")
    parser.add_argument("--privArchive", type=getBool, metavar="<bool>", help="Whether the user has the archiving privilege")
    parser.add_argument("--privChat", type=getBool, metavar="<bool>", help="Whether the user has the chat privilege")
    parser.add_argument("--privFiles", type=getBool, metavar="<bool>", help="Whether the user has the files privilege")
    parser.add_argument("--privVideo", type=getBool, metavar="<bool>", help="Whether the user has the video privilege")
    parser.add_argument("--public-address", type=getBool, metavar="<bool>",
                        help="Whether the user has the public address privilege")
    parser.add_argument("--smtp", type=getBool, metavar="<bool>", help="Whether the user has the SMTP privilege")
    parser.add_argument("--status", type=_cliParseStatus, help="User address status")

    parser.add_argument("--alias", action="append", help="Add alias")
    parser.add_argument("--property", action="append", type=assignment, metavar="propspec=value",
                        help="Set property defined by propspec to value").completer = proptagAssignCompleter
    parser.add_argument("--storeprop", action="append", type=assignment, metavar="propspec=value",
                        help="Set store property defined by propspec to value").completer = proptagAssignCompleter


def _setupCliUser(subp: ArgumentParser):
    sub = subp.add_subparsers()
    create = sub.add_parser("create",  help="Create user")
    create.add_argument("username", help="E-Mail address of the user")
    create.add_argument("--no-defaults", action="store_true", help="Do not apply configured default values")
    create.set_defaults(_handle=cliUserCreate)
    _cliAddUserAttributes(create)
    delete = sub.add_parser("delete", help="Delete user")
    delete.set_defaults(_handle=cliUserDelete)
    delete.add_argument("userspec", help="User ID or name").completer = _cliUserspecCompleter
    delete.add_argument("-k", "--keep-files", action="store_true", help="Do not delete files on disk")
    delete.add_argument("-y", "--yes", action="store_true", help="Do not ask for confirmation")
    list = sub.add_parser("list", help="List users")
    list.set_defaults(_handle=cliUserList)
    list.add_argument("userspec", nargs="?", help="User ID or name prefix")
    list.add_argument("-f", "--filter", nargs="*", help="Filter by attribute, e.g. -f ID=42")
    list.add_argument("-s", "--sort", nargs="*", help="Sort by attribute, e.g. -s username,desc")
    modify = sub.add_parser("modify",  help="Modify user")
    modify.set_defaults(_handle=cliUserModify)
    modify.add_argument("userspec", help="User ID or name prefix").completer = _cliUserspecCompleter
    _cliAddUserAttributes(modify)
    modify.add_argument("--no-ldap", action="store_true", help="Unlink user from ldap object")
    modify.add_argument("--remove-alias", metavar="ALIAS", action="append", help="Remove alias")
    modify.add_argument("--remove-property", action="append", metavar="propspec", help="Remove property from user")
    modify.add_argument("--remove-storeprop", action="append", metavar="propspec", help="Remove property from user's store")
    show = sub.add_parser("show", help="Show detailed information about user")
    show.set_defaults(_handle=cliUserShow)
    show.add_argument("userspec", help="User ID or name").completer = _cliUserspecCompleter
    show.add_argument("-f", "--filter", nargs="*", help="Filter by attribute, e.g. -f ID=42")
    show.add_argument("-s", "--sort", nargs="*", help="Sort by attribute, e.g. -s username,desc")


@Cli.command("user", _setupCliUser, help="User management")
def cliUserStub(args):
    raise InvalidUseError()
