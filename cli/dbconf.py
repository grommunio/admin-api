# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grammm GmbH

from . import Cli

from argparse import ArgumentParser


_commitHelp = "Commit configuration changes to the service. Commit actions can be configured for a service by setting "\
              "`commit_service`, `commit_file`, `commit_key` and `commit_any` parameters in `grammm-dbconf/<service>`. "


def _autocompService(prefix, **kwargs):
    if Cli.rlAvail:
        from orm.misc import DBConf
        return (entry.service for entry in
                DBConf.query.filter(DBConf.service.like(prefix+"%"))
                .with_entities(DBConf.service).all())
    return ()


def _autocompFile(prefix, parsed_args, **kwargs):
    if Cli.rlAvail:
        from orm.misc import DBConf
        return (entry.file for entry in
                DBConf.query.filter(DBConf.service == parsed_args.service,
                                    DBConf.file.like(prefix+"%")).all())
    return ()


def _autocompKey(prefix, parsed_args, **kwargs):
    if Cli.rlAvail:
        from orm.misc import DBConf
        return (entry.key for entry in
                DBConf.query.filter(DBConf.service == parsed_args.service,
                                    DBConf.file == parsed_args.file,
                                    DBConf.key.like(prefix+"%")).all())
    return ()


def cliDbconfSet(args):
    Cli.require("DB")
    from orm.misc import DB, DBConf
    entry = DBConf.query.filter(DBConf.service == args.service, DBConf.file == args.file, DBConf.key == args.key).first()
    if entry is None:
        entry = DBConf(service=args.service, file=args.file, key=args.key, value=args.value)
        DB.session.add(entry)
    else:
        if args.init and args.value != entry.value:
            print(Cli.col("Key exists - aborted.", "yellow"))
            return 1
        entry.value = args.value
    DB.session.commit()
    print("{}={}".format(entry.key, entry.value or ""))
    if not args.batch:
        from tools import dbconf
        print("Committing change...")
        error = dbconf.commit(args.service, args.file, args.key)
        if error is not None:
            print("Commit failed: "+error)
            return 2
        print("Success.")


def cliDbconfGet(args):
    Cli.require("DB")
    from orm.misc import DB, DBConf
    DB.session.rollback()
    query = DBConf.query.filter(DBConf.service == args.service, DBConf.file == args.file)
    if args.key is not None:
        query = query.filter(DBConf.key == args.key)
    entries = query.with_entities(DBConf.key, DBConf.value).all()
    for entry in entries:
        print("{}={}".format(entry.key, entry.value or ""))


def cliDbconfDelete(args):
    Cli.require("DB")
    from orm.misc import DB, DBConf
    query = DBConf.query.filter(DBConf.service == args.service)
    if args.file is not None:
        query = query.filter(DBConf.file == args.file)
    if args.key is not None:
        query = query.filter(DBConf.key == args.key)
    deleted = query.delete()
    DB.session.commit()
    print("Deleted {} entr{}".format(deleted, "y" if deleted == 1 else "ies"))


def cliDbconfList(args):
    Cli.require("DB")
    from orm.misc import DB, DBConf
    DB.session.rollback()
    query = DBConf.query
    if args.service is None:
        header = "Services:"
        target = DBConf.service.distinct()
    else:
        header = "Files in "+args.service
        target = DBConf.file.distinct()
        query = query.filter(DBConf.service == args.service)
    if args.file is not None:
        header = "Keys in {}/{}:".format(args.service, args.file)
        target = DBConf.key.distinct()
        query = query.filter(DBConf.file == args.file)
    print(header)
    entries = query.with_entities(target).all()
    if len(entries) == 0:
        print(Cli.col("  (no entires)", "yellow"))
    for entry in entries:
        print("  "+entry[0])


def cliDbConfCommit(args):
    pass


def _setupCliDbconf(subp: ArgumentParser):
    sub = subp.add_subparsers()
    set = sub.add_parser("set")
    set.set_defaults(_handle=cliDbconfSet)
    set.add_argument("service", help="Service to configure").completer = _autocompService
    set.add_argument("file", help="File or section").completer = _autocompFile
    set.add_argument("key", help="Configuration entry").completer = _autocompKey
    set.add_argument("value", nargs="?", help="Value to set. If omitted, create an empty entry")
    set.add_argument("-b", "--batch", action="store_true", help="Do not autocommit changes")
    set.add_argument("-i", "--init", action="store_true", help="Only set if value configuration does not exist")
    get = sub.add_parser("get")
    get.set_defaults(_handle=cliDbconfGet)
    get.add_argument("service", help="Service get configuration for").completer = _autocompService
    get.add_argument("file", nargs="?", help="File or section. If omitted print all files").completer = _autocompFile
    get.add_argument("key", nargs="?", help="Configuration entry. If omitted, print complete file").completer = _autocompKey
    delete = sub.add_parser("delete")
    delete.set_defaults(_handle=cliDbconfDelete)
    delete.add_argument("service", help="Service to delete from").completer = _autocompService
    delete.add_argument("file", nargs="?", help="File to delete from. If omitted, delete all files").completer = _autocompFile
    delete.add_argument("key", nargs="?", help="Configuration entry to delete. If omitted, delete all entries")\
        .completer = _autocompKey
    list = sub.add_parser("list")
    list.set_defaults(_handle=cliDbconfList)
    list.add_argument("service", nargs="?", help="Service to list files from").completer = _autocompService
    list.add_argument("file", nargs="?", help="File to list keys from").completer = _autocompFile
    commit = sub.add_parser("commit", description=_commitHelp)
    commit.set_defaults(_handle=cliDbConfCommit)
    commit.add_argument("service", help="Service to update")
    commit.add_argument("file", nargs="?", help="File to commit. If omittet, commit all files")
    commit.add_argument("key", nargs="?", help="Key to commit. If omittet, commit all keys")


@Cli.command("dbconf", _setupCliDbconf)
def cliDbconfStub(args):
    pass