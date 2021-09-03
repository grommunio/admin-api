# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH

from . import Cli

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
    from ldap3.utils.conv import escape_filter_chars
    for attr in ("ID", "username", "domainID", "maildir", "privilegeBits"):
        v = getattr(user, attr, None)
        cli.print("{}{}: {}".format(" "*indent, attr, v if v is not None else ""))
    cli.print("{}addressStatus: {} ({}|{})".format(" "*indent, user.addressStatus,
                                                   _mkStatus(cli, user.domainStatus), _mkStatus(cli, user.status)))
    cli.print(" "*indent+"externID: "+(escape_filter_chars(user.externID) if user.externID is not None else
                                       cli.col("(none)", attrs=["dark"])))
    cli.print(" "*indent+"chatID: "+(user.chatID if user.chatID else cli.col("(none)", attrs=["dark"]))+
              (" ("+cli.col("inactive", "red")+")" if user.chatID and not user.chat else ""))
    if user.chat:
        cli.print(" "*indent+"chatAdmin: "+(cli.col("yes", "yellow") if user.chatAdmin else "no"))
    cli.print(" "*indent+"aliases:"+(cli.col(" (none)", attrs=["dark"]) if len(user.aliases) == 0 else ""))
    for alias in user.aliases:
        cli.print(" "*indent+"  "+alias.aliasname)
    cli.print(" "*indent+"roles:"+(cli.col(" (none)", attrs=["dark"]) if len(user.roles) == 0 else ""))
    for role in user.roles:
        cli.print(" "*indent+"  "+role.name)
    cli.print(" "*indent+"fetchmail:"+ (cli.col(" (none)", attrs=["dark"]) if len(user.fetchmail) == 0 else ""))
    for fml in user.fetchmail:
        cli.print("{}  {}@{}/{} ({})".format(" "*indent, fml.srcUser, fml.srcServer, fml.srcFolder,
                                             cli.col("active", "green") if fml.active == 1 else cli.col("inactive", "red")))
    cli.print(" "*indent+"properties:"+(cli.col(" (none)", attrs=["dark"]) if len(user.properties) == 0 else ""))
    for key, value in user.propmap.items():
        cli.print("{}  {}: {}".format(" "*indent, key, value))


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


def cliUserDelete(args):
    cli = args._cli
    cli.require("DB")
    from orm import DB
    users = _mkUserQuery(args).all()
    if len(users) == 0:
        cli.print(cli.col("No users found.", "yellow"))
        return 1
    if len(users) > 1:
        cli.print("'{}' is ambiguous. Candidates are:".format(args.userspec))
        for user in users:
            cli.print("  {}:\t{}".format(user.ID, user.username))
        return 2
    user = users[0]
    maildir = user.maildir
    if not args.yes:
        if cli.confirm("Delete user '{}' ({})? [y/N]: ".format(user.username, user.ID)) != Cli.SUCCESS:
            return 3
    else:
        cli.print("Deleting user '{}' ({})".format(user.username, user.ID))
    user.delete()
    DB.session.commit()
    cli.print("User deleted.")
    if maildir == "":
        cli.print("No user files to delete.")
        return 0
    cli.print("Unloading store...", end="", flush=True)

    from services import Service
    with Service("exmdb") as exmdb:
        client = exmdb.ExmdbQueries(exmdb.host, exmdb.port, maildir, True)
        client.unloadStore(maildir)
        cli.print("Done.")
    if args.keep_files or (not args.yes and cli.confirm("Delete user directory from disk? [y/N]: ") != Cli.SUCCESS):
        cli.print(cli.col("Files remain in "+maildir, attrs=["bold"]))
        return 0
    cli.print("Deleting user files...", end="")
    import shutil
    shutil.rmtree(maildir, ignore_errors=True)
    cli.print("Done.")


def _cliUserspecCompleter(prefix, **kwargs):
    from orm.users import Users
    return (user.username for user in Users.query.filter(Users.username.ilike(prefix+"%"))
                                                 .with_entities(Users.username).all())


def _setupCliUser(subp: ArgumentParser):
    sub = subp.add_subparsers()
    delete = sub.add_parser("delete", help="Delete user")
    delete.set_defaults(_handle=cliUserDelete)
    delete.add_argument("userspec", help="User ID or name").completer = _cliUserspecCompleter
    delete.add_argument("-k", "--keep-files", action="store_true", help="Do not delete files on disk")
    delete.add_argument("-y", "--yes", action="store_true", help="Do not ask for confirmation")
    list = sub.add_parser("list", help="List users")
    list.set_defaults(_handle=cliUserList)
    list.add_argument("userspec", nargs="?", help="User ID or substring to match username against")
    list.add_argument("-s", "--sort", nargs="*", help="Sort by attribute, e.g. -s username,desc")
    list.add_argument("-f", "--filter", nargs="*", help="Filter by attribute, e.g. -f ID=42")
    show = sub.add_parser("show", help="Show detailed information about user")
    show.set_defaults(_handle=cliUserShow)
    show.add_argument("userspec", help="User ID or name").completer = _cliUserspecCompleter
    show.add_argument("-s", "--sort", nargs="*", help="Sort by attribute, e.g. -s username,desc")
    show.add_argument("-f", "--filter", nargs="*", help="Filter by attribute, e.g. -f ID=42")


@Cli.command("user", _setupCliUser, help="User management")
def cliUserStub(args):
    pass
