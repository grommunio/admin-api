# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH

from . import Cli
from argparse import ArgumentParser

_typemap = {"normal": 0, "domain": 2, "class": 3}
_typenames = {value: key for key, value in _typemap.items()}
_privmap = {"all": 0, "internal": 1, "domain": 2, "specific": 3, "outgoing": 4}
_privnames = {value: ky for ky, value in _privmap.items()}


def _mkMlistQuery(args):
    from orm.mlists import MLists
    mspec = args.mlistspec
    query = MLists.query
    if mspec is not None:
        query = query.filter(MLists.ID == mspec if mspec.isdigit() else MLists.listname.ilike(mspec+"%"))
    if "filter" in args and args.filter is not None:
        query = MLists.autofilter(query, {f.split("=", 1)[0]: f.split("=", 1)[1] for f in args.filter if "=" in f})
    if "sort" in args and args.sort is not None:
        query = MLists.autosort(query, args.sort)
    return query


def cliMlistCreate(args):
    cli = args._cli
    cli.require("DB")
    from orm import DB
    from orm.mlists import MLists
    data = dict(listname=args.name,
                listType=_typemap.get(args.type or "normal", 0),
                listPrivilege= _privmap.get(args.privilege or "all", 0),
                associations=args.recipient or [],
                specifieds=args.sender or [])
    if args.class_:
        from orm.classes import Classes
        from sqlalchemy import or_
        try:
            ID = int(args.class_, 0)
        except:
            ID = None
        classes = Classes.query.filter(or_(Classes.ID == ID, Classes.classname.ilike("%"+args.class_+"%"))).all()
        if len(classes) == 0:
            cli.print(cli.col("No class matching '{}' found".format(args.class_), "yellow"))
            return 1
        if len(classes) > 1:
            cli.print(cli.col("Class specification '{}' is ambiguous:", "yellow"))
            for c in classes:
                cli.print(cli.col("  {}:\t{}".format(c.ID, c.classname), "yellow"))
            return 2
        data["class"] = classes[0].ID
    error = MLists.checkCreateParams(data)
    if error is not None:
        cli.print(cli.col("Cannot create mlist: "+error, "red"))
        return 3
    try:
        mlist = MLists(data)
        DB.session.add(mlist)
        DB.session.commit()
        cli.print(cli.col("{} ({}):".format(mlist.listname, mlist.ID), attrs=["bold"]))
        _dumpMlist(cli, mlist, 2)
    except ValueError as err:
        cli.print(cli.col("Cannot create mlist: "+err.args[0], "red"))
        DB.session.rollback()


def _dumpMlist(cli, mlist, indent=0):
    cli.print("{}ID: {}".format(" "*indent, mlist.ID))
    cli.print("{}listname: {}".format(" "*indent, mlist.listname))
    col, attr = (None, ["dark"]) if mlist.listType in _typenames else ("red", None)
    cli.print("{}listType: {} ({})".format(" "*indent, mlist.listType,
                                           cli.col(_typenames.get(mlist.listType, "unknown"), col, attrs=attr)))
    col, attr = (None, ["dark"]) if mlist.listPrivilege in _privnames else ("red", None)
    cli.print("{}listPrivilege: {} ({})".format(" "*indent, mlist.listPrivilege,
                                                cli.col(_privnames.get(mlist.listPrivilege, "unknown"), col, attrs=attr)))
    cli.print("{}userID: {}".format(" "*indent, "(not found)" if mlist.user is None else mlist.user.ID))
    if mlist.listType == 0:
        cli.print(" "*indent+"recipients: "+(cli.col("(none)", attrs=["dark"]) if len(mlist.associations) == 0 else ""))
        for assoc in mlist.associations:
            cli.print(" "*indent+"  "+assoc.username)
    if mlist.listPrivilege == 3:
        cli.print(" "*indent+"senders: "+(cli.col("(none)", attrs=["dark"]) if len(mlist.specifieds) == 0 else ""))
        for spec in mlist.specifieds:
            cli.print(" "*indent+"  "+spec.username)


def cliMlistShow(args):
    cli = args._cli
    cli.require("DB")
    from orm import DB
    mlists = _mkMlistQuery(args).all()
    if len(mlists) == 0:
        cli.print(cli.col("No mailing lists found.", "yellow"))
        return 1
    for mlist in mlists:
        cli.print(cli.col("{} ({}):".format(mlist.listname, mlist.ID), attrs=["bold"]))
        _dumpMlist(cli, mlist, 2)
    DB.session.rollback()


def cliMlistList(args):
    cli = args._cli
    cli.require("DB")
    mlists = _mkMlistQuery(args).all()
    if len(mlists) == 0:
        cli.print(cli.col("No mailing lists found.", "yellow"))
        return 1
    for mlist in mlists:
        cli.print("{}:\t{}".format(mlist.ID, mlist.listname))


def cliMlistDelete(args):
    cli = args._cli
    cli.require("DB")
    from orm import DB
    mlists = _mkMlistQuery(args).all()
    if len(mlists) == 0:
        cli.print(cli.col("No mailing lists found.", "yellow"))
        return 1
    if len(mlists) > 1:
        cli.print(cli.col("'{}' is ambiguous".format(args.mlistspec), "yellow"))
        return 2
    mlist = mlists[0]
    if not args.yes:
        if cli.confirm("Delete mailing list '{}' ({})? [y/N]: ".format(cli.col(mlist.listname, attrs=["bold"]), mlist.ID))\
            != Cli.SUCCESS:
            return 3
    else:
        cli.print("Deleting mlist '{}' ({})".format(mlist.listname, mlist.ID))
    mlist.delete()
    DB.session.commit()
    cli.print("Done.")


def cliMlistAr(args):
    cli = args._cli
    cli.require("DB")
    from orm import DB
    mlists = _mkMlistQuery(args).all()
    if len(mlists) == 0:
        cli.print(cli.col("No mailing lists found.", "yellow"))
        return 1
    if len(mlists) > 1:
        cli.print("'{}' is ambiguous. Candidates are:".format(args.mlistspec))
        for mlist in mlists:
            cli.print("  {}:\t{}".format(mlist.ID, mlist.listname))
        return 2
    mlist = mlists[0]
    attr = mlist.specifieds if args.attribute == "sender" else mlist.associations
    if args.__command == "remove":
        for element in attr:
            if element.username == args.entry:
                attr.remove(element)
                break
        else:
            cli.print(cli.col("Entry '{}' not found".format(args.entry)))
            return 0
        cli.print("Removed '{}' as {} from {}.".format(args.entry, args.attribute, mlist.listname))
    elif args.__command == "add":
        if sum((1 for element in attr if element.username == args.entry)):
            cli.print(cli.col("'{}' already exists as {} {}".format(args.entry, args.attribute, mlist.listname), "yellow"))
            return 0
        try:
            from orm.mlists import Associations, Specifieds
            attr.append((Specifieds if args.attribute == "sender" else Associations)(args.entry))
            cli.print("Added '{}' as {} to {}".format(args.entry, args.attribute, mlist.listname))
        except ValueError as err:
            cli.print(cli.col(err.args[0], "red"))
            DB.session.rollback()
            return 1
    DB.session.commit()


def cliMlistModify(args):
    cli = args._cli
    cli.require("DB")
    from orm import DB
    mlists = _mkMlistQuery(args).all()
    if len(mlists) == 0:
        cli.print(cli.col("No mailing lists found.", "yellow"))
        return 1
    if len(mlists) > 1:
        cli.print("'{}' is ambiguous. Candidates are:".format(args.mlistspec))
        for mlist in mlists:
            cli.print("  {}:\t{}".format(mlist.ID, mlist.listname))
        return 2
    mlist = mlists[0]
    attrs = dict()
    if args.class_ is not None:
        attrs["class"] = args.class_
    if args.privilege is not None:
        attrs["listPrivilege"] = _privmap[args.privilege]
    if args.type is not None:
        attrs["listType"] = _typemap[args.type]
    try:
        mlist.fromdict(attrs)
        DB.session.commit()
    except ValueError as err:
        cli.print(cli.col(err.args[0], "red"))
        DB.session.rollback()
        return 1
    _dumpMlist(cli, mlist)


def _cliListspecCompleter(prefix, **kwargs):
    from orm.mlists import MLists
    return (mlist.listname for mlist in MLists.query.filter(MLists.listname.ilike(prefix+"%"))
                                                    .with_entities(MLists.listname).all())


def _setupCliMlist(subp: ArgumentParser):
    def arArgs(ar, command):
        ar.set_defaults(_handle=cliMlistAr, __command=command)
        ar.add_argument("mlistspec", help="Mlist ID or name").completer = _cliListspecCompleter
        ar.add_argument("attribute", choices=("recipient", "sender"), help="Attribute to modify")
        ar.add_argument("entry", help="Which entry to "+command)

    sub = subp.add_subparsers()
    add = sub.add_parser("add", help="Add recipient or sender")
    arArgs(add, "add")
    create = sub.add_parser("create", help="Create new list")
    create.set_defaults(_handle=cliMlistCreate)
    create.add_argument("name", help="Name of the mailing list")
    create.add_argument("-c", "--class", help="ID or name of the class to use for class lists", dest="class_", metavar="class")
    create.add_argument("-p", "--privilege", choices=_privmap, default="all", help="List privilege type")
    create.add_argument("-r", "--recipient", action="append", help="Users to associate with normal lists")
    create.add_argument("-s", "--sender", action="append",
                        help="Users allowed to send to the list ('specific' privilege only)")
    create.add_argument("-t", "--type", choices=_typemap, help="Mailing list type")
    delete = sub.add_parser("delete", help="Delete list")
    delete.set_defaults(_handle=cliMlistDelete)
    delete.add_argument("mlistspec", help="List ID or name prefix").completer = _cliListspecCompleter
    delete.add_argument("-y", "--yes", action="store_true", help="Do not ask for confirmation")
    list = sub.add_parser("list", help="List existing lists")
    list.set_defaults(_handle=cliMlistList)
    list.add_argument("mlistspec", nargs="?", help="List ID or name prefix")
    list.add_argument("-s", "--sort", nargs="*", help="Sort by attribute, e.g. -s listname,desc")
    list.add_argument("-f", "--filter", nargs="*", help="Filter by attribute, e.g. -f ID=42")
    modify = sub.add_parser("modify", help="Modify list")
    modify.set_defaults(_handle=cliMlistModify)
    modify.add_argument("mlistspec", help="List ID or name prefix").completer = _cliListspecCompleter
    modify.add_argument("-c", "--class", help="ID or name of the class to use for class lists", dest="class_", metavar="class")
    modify.add_argument("-p", "--privilege", choices=_privmap, help="List privilege type")
    modify.add_argument("-t", "--type", choices=_typemap, help="Mailing list type")
    remove = sub.add_parser("remove", help="Remove recipient or sender")
    arArgs(remove, "remove")
    show = sub.add_parser("show", help="Show detailed information about list")
    show.set_defaults(_handle=cliMlistShow)
    show.add_argument("mlistspec", help="Mlist ID or name").completer = _cliListspecCompleter
    show.add_argument("-s", "--sort", nargs="*", help="Sort by attribute, e.g. -s listname,desc")
    show.add_argument("-f", "--filter", nargs="*", help="Filter by attribute, e.g. -f ID=42")


@Cli.command("mlist", _setupCliMlist, help="Mailing/distribution list management")
def cliMlistStub():
    pass
