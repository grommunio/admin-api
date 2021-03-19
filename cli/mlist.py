# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grammm GmbH

from . import Cli
from argparse import ArgumentParser

_typemap = {"normal": 0, "domain": 2, "class": 3}
_typenames = tuple(_typemap.keys())
_privmap = {"all": 0, "internal": 1, "domain": 2, "specific": 3, "outgoing": 4}
_privnames = tuple(_privmap.keys())


def _getDomainFilter(spec):
    if spec is None:
        return True
    from orm.domains import Domains
    from orm.users import Users


def _getMlistFilter(mspec, dspec, args=None):
    from orm.mlists import MLists
    from sqlalchemy import and_, or_
    if mspec is None:
        return _getDomainFilter(dspec)
    try:
        ID = int(mspec, 0)
    except:
        ID = None
    if args is not None and "id" in args and args.id is True:
        return and_(MLists.ID == ID, _getDomainFilter(dspec))
    return and_(or_(MLists.ID == ID, MLists.listname.ilike("%"+mspec+"%")), _getDomainFilter(dspec))


def _mkMlistQuery(args):
    from orm.mlists import MLists
    query = MLists.query.filter(_getMlistFilter(args.mlistspec, args.domain))
    if "filter" in args and args.filter is not None:
        query = MLists.autofilter(query, {f.split("=", 1)[0]: f.split("=", 1)[1] for f in args.filter if "=" in f})
    if "sort" in args and args.sort is not None:
        query = MLists.autosort(query, args.sort)
    return query


def cliMlistCreate(args):
    Cli.require("DB")
    from orm import DB
    from orm.mlists import MLists
    data = dict(listname=args.name,
                listType=_typemap.get(args.type, 0),
                listPrivilege= _privmap.get(args.privilege, 0),
                associations=args.recipient,
                specifieds=args.sender)
    if args.class_:
        from orm.classes import Classes
        from sqlalchemy import or_
        try:
            ID = int(args.class_, 0)
        except:
            ID = None
        classes = Classes.query.filter(or_(Classes.ID == ID, Classes.classname.ilike("%"+args.class_+"%"))).all()
        if len(classes) == 0:
            print(Cli.col("No class matching '{}' found".format(args.class_), "yellow"))
            return 1
        if len(classes) > 1:
            print(Cli.col("Class specification '{}' is ambiguous:", "yellow"))
            for c in classes:
                print(Cli.col("  {}:\t{}".format(c.ID, c.classname), "yellow"))
            return 2
        data["class"] = classes[0].ID
    error = MLists.checkCreateParams(data)
    if error is not None:
        print(Cli.col("Cannot create mlist: "+error, "red"))
        return 3
    try:
        mlist = MLists(data)
        DB.session.add(mlist)
        DB.session.commit()
        print("Mailing list '{}' created with ID {}.".format(mlist.listname, mlist.ID))
    except ValueError as err:
        print(Cli.col("Cannot create mlist: "+err.args[0], "red"))
        DB.session.rollback()


def _dumpMlist(mlist, indent=0):
    print("{}ID: {}".format(" "*indent, mlist.ID))
    print("{}listname: {}".format(" "*indent, mlist.listname))
    print("{}listType: {} ({})".format(" "*indent, mlist.listType, _typenames[mlist.listType]))
    print("{}listPrivilege: {} ({})".format(" "*indent, mlist.listPrivilege, _privnames[mlist.listPrivilege]))
    print("{}userID: {}".format(" "*indent, "(not found)" if mlist.user is None else mlist.user.ID))
    if mlist.listType == 0:
        print(" "*indent+"recipients: "+("(none)" if len(mlist.associations) == 0 else ""))
        for assoc in mlist.associations:
            print(" "*indent+"  "+assoc.username)
    if mlist.listPrivilege == 3:
        print(" "*indent+"senders: "+("(none)" if len(mlist.specifieds) == 0 else ""))
        for spec in mlist.specifieds:
            print(" "*indent+"  "+spec.username)


def cliMlistShow(args):
    Cli.require("DB")
    from orm import DB
    if args.id:
        from orm.mlists import MLists
        mlists = MLists.query.filter(MLists.ID == args.mlistspec).all()
    else:
        mlists = _mkMlistQuery(args).all()
    if len(mlists) == 0:
        print(Cli.col("No mailing lists found.", "yellow"))
        return 1
    for mlist in mlists:
        print(Cli.col("{} ({}):".format(mlist.listname, mlist.ID), attrs=["bold"]))
        _dumpMlist(mlist, 2)
    DB.session.rollback()


def cliMlistList(args):
    Cli.require("DB")
    from orm import DB
    from orm.mlists import MLists
    mlists = _mkMlistQuery(args).all()
    if len(mlists) == 0:
        print(Cli.col("No mailing lists found.", "yellow"))
        return 1
    for mlist in mlists:
        print("{}:\t{}".format(mlist.ID, mlist.listname))
    DB.session.rollback()


def cliMlistDelete(args):
    Cli.require("DB")
    from orm import DB
    mlists = _mkMlistQuery(args).all()
    if len(mlists) == 0:
        print(Cli.col("No mailing lists found.", "yellow"))
        return 1
    if len(mlists) > 1:
        print("'{}' is ambiguous. Candidates are:".format(args.mlistspec))
        for mlist in mlists:
            print("  {}:\t{}".format(mlist.ID, mlist.listname))
        return 2
    mlist = mlists[0]
    if not args.yes:
        if Cli.confirm("Delete mailing list '{}' ({})? [y/N]: ".format(mlist.listname, mlist.ID)) != Cli.SUCCESS:
            return 3
    else:
        print("Deleting mlist '{}' ({})".format(mlist.listname, mlist.ID))
    mlist.delete()
    DB.session.commit()
    print("Done.")


def cliMlistModify(args):
    Cli.require("DB")
    from orm import DB
    mlists = _mkMlistQuery(args).all()
    if len(mlists) == 0:
        print(Cli.col("No mailing lists found.", "yellow"))
        return 1
    if len(mlists) > 1:
        print("'{}' is ambiguous. Candidates are:".format(args.mlistspec))
        for mlist in mlists:
            print("  {}:\t{}".format(mlist.ID, mlist.listname))
        return 2
    mlist = mlists[0]
    attr = mlist.specifieds if args.attribute == "sender" else mlist.associations
    if args.command == "remove":
        for element in attr:
            if element.username == args.entry:
                attr.remove(element)
                break
        else:
            print(Cli.col("Entry '{}' not found".format(args.entry)))
            return 0
        print("Removed '{}' as {} from {}.".format(args.entry, args.attribute, mlist.listname))
    elif args.command == "add":
        if sum((1 for element in attr if element.username == args.entry)):
            print(Cli.col("'{}' already exists as {} {}".format(args.entry, args.attribute, mlist.listname), "yellow"))
            return 0
        try:
            from orm.mlists import Associations, Specifieds
            attr.append((Specifieds if args.attribute == "sender" else Associations)(args.entry))
            print("Added '{}' as {} to {}".format(args.entry, args.attribute, mlist.listname))
        except ValueError as err:
            print(Cli.col(err.args[0], "red"))
            DB.session.rollback()
            return 1
    DB.session.commit()


def _cliListspecCompleter(prefix, **kwargs):
    if Cli.rlAvail:
        from orm.mlists import MLists
        return (mlist.listname for mlist in MLists.query.filter(MLists.listname.ilike(prefix+"%"))
                                                        .with_entities(MLists.listname).all())
    return ()


def _setupCliMlist(subp: ArgumentParser):
    subp.add_argument("-d", "--domain", help="Restrict operations to domain.")
    sub = subp.add_subparsers()
    create = sub.add_parser("create")
    create.set_defaults(_handle=cliMlistCreate)
    create.add_argument("name", help="Name of the mailing list")
    create.add_argument("-p", "--privilege", choices=_privnames, default="all", help="List privilege type")
    create.add_argument("-s", "--sender", action="append", default=[],
                        help="Users allowed to send to the list (only for privilege 'specific')")
    create.add_argument("-t", "--type", choices=_typenames, default="normal", help="Mailing list type")
    create.add_argument("-r", "--recipient", action="append", default=[], help="Users to associate with normal lists")
    create.add_argument("-c", "--class", help="ID or name of the class to use for class lists", dest="class_")
    show = sub.add_parser("show")
    show.set_defaults(_handle=cliMlistShow)
    show.add_argument("mlistspec", help="Mlist ID or name").completer = _cliListspecCompleter
    show.add_argument("-i", "--id", action="store_true", help="Only match list by ID")
    show.add_argument("-s", "--sort", nargs="*", help="Sort by attribute, e.g. -s listname,desc")
    show.add_argument("-f", "--filter", nargs="*", help="Filter by attribute, e.g. -f ID=42")
    list = sub.add_parser("list")
    list.set_defaults(_handle=cliMlistList)
    list.add_argument("mlistspec", nargs="?", help="List ID or substring to match listname against")
    list.add_argument("-s", "--sort", nargs="*", help="Sort by attribute, e.g. -s listname,desc")
    list.add_argument("-f", "--filter", nargs="*", help="Filter by attribute, e.g. -f ID=42")
    delete = sub.add_parser("delete")
    delete.set_defaults(_handle=cliMlistDelete)
    delete.add_argument("mlistspec", help="Mlist ID or name").completer = _cliListspecCompleter
    delete.add_argument("-i", "--id", action="store_true", help="Only match list by ID")
    delete.add_argument("-y", "--yes", action="store_true", help="Do not ask for confirmation")
    modify = sub.add_parser("modify")
    modify.set_defaults(_handle=cliMlistModify)
    modify.add_argument("-i", "--id", action="store_true", help="Only match list by ID")
    modify.add_argument("mlistspec", help="Mlist ID or name").completer = _cliListspecCompleter
    modify.add_argument("command", choices=("add", "remove"), help="Modification to perform")
    modify.add_argument("attribute", choices=("recipient", "sender"), help="Attribute to modify")
    modify.add_argument("entry", help="Which entry to add/remove")


@Cli.command("mlist", _setupCliMlist)
def cliMlistStub():
    pass
