# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grammm GmbH

from . import Cli

from argparse import ArgumentParser


def _getDomainFilter(spec):
    if spec is None:
        return True
    from orm.domains import Domains
    from orm.users import Users
    from sqlalchemy import or_
    try:
        ID = int(spec, 0)
    except:
        ID = None
    return Users.domainID.in_(Domains.query.filter(or_(Domains.ID == ID, Domains.domainname.ilike("%"+spec+"%")))
                              .with_entities(Domains.ID))


def _getUserFilter(uspec, dspec):
    from orm.users import Users
    from sqlalchemy import and_, or_
    if uspec is None:
        return _getDomainFilter(dspec)
    try:
        ID = int(uspec, 0)
    except:
        ID = None
    return and_(or_(Users.ID == ID, Users.username.ilike("%"+uspec+"%")), _getDomainFilter(dspec))


def _mkUserQuery(args):
    from orm.users import Users
    query = Users.query.filter(_getUserFilter(args.userspec, args.domain))
    if "filter" in args and args.filter is not None:
        query = Users.autofilter(query, {f.split("=", 1)[0]: f.split("=", 1)[1] for f in args.filter if "=" in f})
    if "sort" in args and args.sort is not None:
        query = Users.autosort(query, args.sort)
    return query


def _dumpUser(user, indent=0):
    from ldap3.utils.conv import escape_filter_chars
    from orm import DB
    for attr in ("ID", "username", "groupID", "domainID", "maildir", "addressStatus", "privilegeBits"):
        v = getattr(user, attr, None)
        print("{}{}: {}".format(" "*indent, attr, v if v is not None else ""))
    print(" "*indent+"externID: "+escape_filter_chars(user.externID))
    print(" "*indent+"aliases:"+(" (none)" if len(user.aliases) == 0 else ""))
    for alias in user.aliases:
        print(" "*indent+"  "+alias.aliasname)
    print(" "*indent+"roles:"+(" (none)" if len(user.roles) == 0 else ""))
    for role in user.roles:
        print(" "*indent+"  "+role.name)
    print(" "*indent+"properties:"+(" (none)" if len(user.properties) == 0 else ""))
    for key, value in user.propmap.items():
        print("{}  {}: {}".format(" "*indent, key, value))
    DB.session.rollback()


def _cliUserShow(args):
    from orm import DB
    if args.id:
        from orm.users import Users
        users = Users.query.filter(Users.ID == args.userspec).all()
    else:
        users = _mkUserQuery(args).all()
    if len(users) == 0:
        print(Cli.col("No users found.", "yellow"))
        return 1
    for user in users:
        print(Cli.col("{} ({}):".format(user.username, user.ID), attrs=["bold"]))
        _dumpUser(user, 2)
    DB.session.rollback()


def _cliUserList(args):
    from orm import DB
    users = _mkUserQuery(args).all()
    if len(users) == 0:
        print(Cli.col("No users found.", "yellow"))
        return 1
    for user in users:
        print("{}:\t{}".format(user.ID, user.username))
    DB.session.rollback()


def _cliUserDelete(args):
    from orm import DB
    users = _mkUserQuery(args).all()
    if len(users) == 0:
        print(Cli.col("No users found.", "yellow"))
        return 1
    if len(users) > 1:
        print("'{}' is ambiguous. Candidates are:".format(args.userspec))
        for user in users:
            print("  {}:\t{}".format(user.ID, user.username))
        return 2
    user = users[0]
    maildir = user.maildir
    if not args.yes:
        if Cli.confirm("Delete user '{}' ({})? [y/N]: ".format(user.username, user.ID)) != Cli.SUCCESS:
            return 3
    else:
        print("Deleting user '{}' ({})".format(user.username, user.ID))
    user.delete()
    DB.session.commit()
    print("User deleted.")
    if maildir == "":
        print("No user files to delete.")
        return 0
    print("Unloading store...", end="")
    try:
        from tools.config import Config
        from tools.constants import ExmdbCodes
        from tools.pyexmdb import pyexmdb
        options = Config["options"]
        client = pyexmdb.ExmdbQueries(options["exmdbHost"], options["exmdbPort"], options["userPrefix"], True)
        client.unloadStore(maildir)
        print("Done.")
    except pyexmdb.ExmdbError as err:
        print(Cli.col("Failed.\n  Exmdb query failed with code "+ExmdbCodes.lookup(err.code, hex(err.code)), "yellow"))
    except RuntimeError as err:
        print(Cli.col("Failed.\n  "+err.args[0],"yellow"))
    if args.keep_files or (not args.yes and Cli.confirm("Delete user directory from disk? [y/N]: ") != Cli.SUCCESS):
        print(Cli.col("Files remain in "+maildir, attrs=["bold"]))
        return 0
    print("Deleting user files...", end="")
    import shutil
    shutil.rmtree(maildir, ignore_errors=True)
    print("Done.")


def _cliUserspecCompleter(prefix, **kwargs):
    if Cli.rlAvail:
        from orm.users import Users
        return (user.username for user in Users.query.filter(Users.username.ilike(prefix+"%"))
                                                     .with_entities(Users.username).all())
    return ()


def _setupCliUser(subp: ArgumentParser):
    subp.add_argument("-d", "--domain", help="Restrict operations to domain.")
    sub = subp.add_subparsers()
    show = sub.add_parser("show")
    show.set_defaults(_handle=_cliUserShow)
    show.add_argument("userspec", help="User ID or name").completer = _cliUserspecCompleter
    show.add_argument("-i", "--id", action="store_true", help="Only match user by ID")
    show.add_argument("-s", "--sort", nargs="*", help="Sort by attribute, e.g. -s username,desc")
    show.add_argument("-f", "--filter", nargs="*", help="Filter by attribute, e.g. -f ID=42")
    list = sub.add_parser("list")
    list.set_defaults(_handle=_cliUserList)
    list.add_argument("userspec", nargs="?", help="userspecession to match username against")
    list.add_argument("-s", "--sort", nargs="*", help="Sort by attribute, e.g. -s username,desc")
    list.add_argument("-f", "--filter", nargs="*", help="Filter by attribute, e.g. -f ID=42")
    delete = sub.add_parser("delete")
    delete.set_defaults(_handle=_cliUserDelete)
    delete.add_argument("userspec", help="User ID or name")
    delete.add_argument("-k", "--keep-files", action="store_true", help="Do not delete files on disk")
    delete.add_argument("-y", "--yes", action="store_true", help="Do not ask for confirmation")


@Cli.command("user", _setupCliUser)
def cliUserStub(args):
    pass
