# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH

from . import Cli, InvalidUseError

from argparse import ArgumentParser


_commitHelp = "Commit configuration changes to the service. Commit actions can be configured for a service by setting "\
              "`commit_service`, `commit_file`, `commit_key` and `commit_any` parameters in `grommunio-dbconf/<service>`. "


def _autocompService(prefix, **kwargs):
    try:
        from orm.misc import DBConf
        return (entry.service for entry in
                DBConf.query.filter(DBConf.service.like(prefix+"%"))
                .with_entities(DBConf.service).all())
    except:
        return ()

def _autocompFile(prefix, parsed_args, **kwargs):
    try:
        from orm.misc import DBConf
        return (entry.file for entry in
                DBConf.query.filter(DBConf.service == parsed_args.service,
                                    DBConf.file.like(prefix+"%")).all())
    except:
        return ()

def _autocompKey(prefix, parsed_args, **kwargs):
    try:
        from orm.misc import DBConf
        return (entry.key for entry in
                DBConf.query.filter(DBConf.service == parsed_args.service,
                                    DBConf.file == parsed_args.file,
                                    DBConf.key.like(prefix+"%")).all())
    except:
        return ()

def cliDbconfSet(args):
    cli = args._cli
    cli.require("DB")
    from orm.misc import DB, DBConf
    entry = DBConf.query.filter(DBConf.service == args.service, DBConf.file == args.file, DBConf.key == args.key).first()
    if entry is None:
        entry = DBConf(service=args.service, file=args.file, key=args.key, value=args.value)
        DB.session.add(entry)
    else:
        if args.init and args.value != entry.value:
            cli.print(cli.col("Key exists - aborted.", "yellow"))
            return 1
        entry.value = args.value
    DB.session.commit()
    cli.print("{}={}".format(entry.key, entry.value or ""))
    if not args.batch:
        from tools import dbconf
        error = dbconf.commit(args.service, args.file, args.key)
        if error is not None:
            cli.print(cli.col("Commit failed: "+error, "yellow"))
            return 2


def cliDbconfGet(args):
    cli = args._cli
    cli.require("DB")
    from orm.misc import DB, DBConf
    DB.session.rollback()
    query = DBConf.query.filter(DBConf.service == args.service, DBConf.file == args.file)
    if args.key is not None:
        query = query.filter(DBConf.key == args.key)
    entries = query.with_entities(DBConf.key, DBConf.value).all()
    for entry in entries:
        cli.print("{}={}".format(entry.key, entry.value or ""))


def cliDbconfDelete(args):
    cli = args._cli
    cli.require("DB")
    from orm.misc import DB, DBConf
    query = DBConf.query.filter(DBConf.service == args.service)
    if args.file is not None:
        query = query.filter(DBConf.file == args.file)
    if args.key is not None:
        query = query.filter(DBConf.key == args.key)
    deleted = query.delete()
    DB.session.commit()
    cli.print("Deleted {} entr{}".format(deleted, "y" if deleted == 1 else "ies"))


def cliDbconfList(args):
    cli = args._cli
    cli.require("DB")
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
    cli.print(header)
    entries = query.with_entities(target).all()
    if len(entries) == 0:
        cli.print(cli.col("  (no entries)", "yellow"))
    for entry in entries:
        cli.print("  "+entry[0])


def cliDbConfCommit(args):
    cli = args._cli
    cli.require("DB")
    from tools import dbconf
    error = dbconf.commit(args.service, args.file, args.key)
    if error:
        cli.print(cli.col("Commit failed: "+error, "yellow"))
        return 2


def cliDbConfCommands(args):
    def printEntries(macros, commands, prefix):
        for macro, command in macros.items():
            cli.print(prefix+cli.col(macro, attrs=[])+cli.col(" -> "+command, attrs=["dark"]))
        for command in commands:
            cli.print(prefix+cli.col(command, attrs=[]))
        cli.print()

    cli = args._cli
    prefix = "" if args.level else "  "
    from tools import dbconf
    if args.level in (None, "key"):
        if not args.level:
            cli.print(cli.col("key-level commands:", attrs=["underline"]))
        printEntries(dbconf.keyMacros, dbconf.keyCommits, prefix)
    if args.level in (None, "file"):
        if not args.level:
            cli.print(cli.col("file-level commands:", attrs=["underline"]))
        printEntries(dbconf.fileMacros, dbconf.fileCommits, prefix)
    if args.level in (None, "service"):
        if not args.level:
            cli.print(cli.col("service-level commands:", attrs=["underline"]))
        printEntries(dbconf.serviceMacros, dbconf.serviceCommits, prefix)


def _setupCliDbconf(subp: ArgumentParser):
    sub = subp.add_subparsers()
    commands = sub.add_parser("commands", help="Show whitelisted commit commands")
    commands.set_defaults(_handle=cliDbConfCommands)
    commands.add_argument("level", nargs="?", choices=("key", "file", "service"), help="Show only commands for specific level")
    commit = sub.add_parser("commit", description=_commitHelp, help="Run commit function")
    commit.set_defaults(_handle=cliDbConfCommit)
    commit.add_argument("service", help="Service to update").completer = _autocompService
    commit.add_argument("file", nargs="?", help="File to commit. If omittet, commit all files").completer = _autocompFile
    commit.add_argument("key", nargs="?", help="Key to commit. If omittet, commit all keys").completer = _autocompKey
    delete = sub.add_parser("delete", help="Delete service, file or key")
    delete.set_defaults(_handle=cliDbconfDelete)
    delete.add_argument("service", help="Service to delete from").completer = _autocompService
    delete.add_argument("file", nargs="?", help="File to delete from. If omitted, delete all files").completer = _autocompFile
    delete.add_argument("key", nargs="?", help="Configuration entry to delete. If omitted, delete all entries")\
        .completer = _autocompKey
    get = sub.add_parser("get", help="Print file or key")
    get.set_defaults(_handle=cliDbconfGet)
    get.add_argument("service", help="Service get configuration for").completer = _autocompService
    get.add_argument("file", help="File or section. If omitted print all files").completer = _autocompFile
    get.add_argument("key", nargs="?", help="Configuration entry. If omitted, print complete file").completer = _autocompKey
    list = sub.add_parser("list", help="List services, files or keys")
    list.set_defaults(_handle=cliDbconfList)
    list.add_argument("service", nargs="?", help="Service to list files from").completer = _autocompService
    list.add_argument("file", nargs="?", help="File to list keys from").completer = _autocompFile
    set = sub.add_parser("set", help="Set configuration value")
    set.set_defaults(_handle=cliDbconfSet)
    set.add_argument("service", help="Service to configure").completer = _autocompService
    set.add_argument("file", help="File or section").completer = _autocompFile
    set.add_argument("key", help="Configuration entry").completer = _autocompKey
    set.add_argument("value", nargs="?", help="Value to set. If omitted, create an empty entry")
    set.add_argument("-b", "--batch", action="store_true", help="Do not autocommit changes")
    set.add_argument("-i", "--init", action="store_true", help="Only set if value configuration does not exist")


@Cli.command("dbconf", _setupCliDbconf, help="Database-stored configuration management")
def cliDbconfStub(args):
    raise InvalidUseError()
