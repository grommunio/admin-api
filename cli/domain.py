# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH

from . import Cli
from argparse import ArgumentParser

_statusMap = {0: "active", 1: "suspended", 2: "out-of-date", 3: "deleted"}
_statusColor = {0: "green", 1: "yellow", 2: "yellow", 3: "red"}


def _domainStatus(cli, status):
    return cli.col(_statusMap.get(status, "unknown"), _statusColor.get(status, "magenta"))


def _domainQuery(args):
    from .common import domainCandidates
    from orm.domains import Domains
    query = domainCandidates(args.domainspec)
    if "filter" in args and args.filter is not None:
        query = Domains.autofilter(query, {f.split("=", 1)[0]: f.split("=", 1)[1] for f in args.filter if "=" in f})
    if "sort" in args and args.sort is not None:
        query = Domains.autosort(query, args.sort)
    return query


def _dumpDomain(cli, domain):
    displayname = domain.displayname if domain.displayname != domain.domainname else None
    cli.print(cli.col("{} ({}):".format(domain.domainname, domain.ID), attrs=["bold"]))
    cli.print("  ID: "+str(domain.ID))
    cli.print("  orgID: "+str(domain.orgID))
    cli.print("  domainname: "+domain.domainname+(" ({})".format(cli.col(displayname, attrs=["dark"])) if displayname else ""))
    cli.print("  domainStatus: {} ({})".format(domain.domainStatus, _domainStatus(cli, domain.domainStatus)))
    cli.print("  activeUsers: "+str(domain.activeUsers))
    cli.print("  inactiveUsers: "+str(domain.inactiveUsers))
    cli.print("  maxUser: "+str(domain.maxUser))
    cli.print("  homedir: "+domain.homedir)
    cli.print("  chatID: "+(domain.chatID or cli.col("(none)", attrs=["dark"]))+
              (" ("+cli.col("inactive", "red")+")" if domain.chatID and not domain.chat else ""))
    cli.print("  endDay: "+str(domain.endDay))
    cli.print("  title: "+domain.title)
    cli.print("  address: "+domain.address)
    cli.print("  adminName: "+domain.adminName)
    cli.print("  tel: "+domain.tel)


def _sanitizeData(data):
    cliargs = {"_handle", "_cli", "domainspec", "skip_adaptor_reload"}
    return {key: value for key, value in data.items() if value is not None and key not in cliargs}


def cliDomainList(args):
    cli = args._cli
    cli.require("DB")
    domains = _domainQuery(args).all()
    if len(domains) == 0:
        cli.print(cli.col("No domains found.", "yellow"))
        return 1
    for domain in domains:
        dname = " ({})".format(cli.col(domain.displayname, attrs=["dark"])) if domain.displayname != domain.domainname else ""
        cli.print("{}: {}{} ({})".format(domain.ID, domain.domainname, dname, _domainStatus(cli, domain.domainStatus)))


def cliDomainShow(args):
    cli = args._cli
    cli.require("DB")
    domains = _domainQuery(args).all()
    if len(domains) == 0:
        cli.print(cli.col("No domains found.", "yellow"))
        return 1
    for domain in domains:
        _dumpDomain(cli, domain)


def cliDomainCreate(args):
    cli = args._cli
    cli.require("DB")
    from orm.domains import Domains
    data = _sanitizeData(args.__dict__)
    result, code = Domains.create(data, createRole=data.pop("create_role", False))
    if code != 201:
        cli.print(cli.col("Could not create domain: "+result, "red"))
        return 1
    _dumpDomain(cli, result)


def cliDomainDelete(args):
    cli = args._cli
    cli.require("DB")
    from orm import DB
    from .common import domainCandidates
    domains = domainCandidates(args.domainspec).all()
    if len(domains) == 0:
        cli.print(cli.col("No domains found.", "yellow"))
        return 1
    if len(domains) > 1:
        cli.print(cli.col("'{}' is ambiguous".format(args.domainspec), "yellow"))
        return 2
    domain = domains[0]
    domain.delete()
    DB.session.commit()
    _dumpDomain(cli, domain)


def cliDomainRecover(args):
    cli = args._cli
    cli.require("DB")
    from orm import DB
    from .common import domainCandidates
    domains = domainCandidates(args.domainspec).all()
    if len(domains) == 0:
        cli.print(cli.col("No domains found.", "yellow"))
        return 1
    if len(domains) > 1:
        cli.print(cli.col("'{}' is ambiguous".format(args.domainspec), "yellow"))
        return 2
    domain = domains[0]
    domain.recover()
    DB.session.commit()
    _dumpDomain(cli, domain)


def cliDomainPurge(args):
    cli = args._cli
    cli.require("DB")
    from orm import DB
    from .common import domainCandidates
    domains = domainCandidates(args.domainspec).all()
    if len(domains) == 0:
        cli.print(cli.col("No domains found.", "yellow"))
        return 1
    if len(domains) > 1:
        cli.print(cli.col("'{}' is ambiguous".format(args.domainspec), "yellow"))
        return 2
    domain = domains[0]
    if not args.yes:
        if cli.confirm("Permanently delete domain "+
                       cli.col(domain.domainname, "red", attrs=["bold"])+
                       (" and all associated files" if args.files else "")+"? [y/N]: "):
            return 1
    domain.purge(deleteFiles=args.files, printStatus=True)
    cli.print("Removing database entries...", end="")
    DB.session.commit()
    cli.print("Done\nDomain removed.")


def cliDomainModify(args):
    cli = args._cli
    cli.require("DB")
    from orm import DB
    from .common import domainCandidates
    domains = domainCandidates(args.domainspec).all()
    if len(domains) == 0:
        cli.print(cli.col("No domains found.", "yellow"))
        return 1
    if len(domains) > 1:
        cli.print(cli.col("'{}' is ambiguous".format(args.domainspec), "yellow"))
        return 2
    domain = domains[0]
    data = _sanitizeData(args.__dict__)
    try:
        domain.fromdict(data)
        DB.session.commit()
    except ValueError as err:
        cli.print(cli.col("Cannot update domain: "+err.args[0]))
        DB.session.rollback()
    _dumpDomain(cli, domain)


def _cliDomainDomainspecAutocomp(prefix, **kwarg):
    from .common import domainCandidates
    from orm.domains import Domains
    return (domain.domainname for domain in domainCandidates(prefix).with_entities(Domains.domainname).all())


def _noComp(**kwargs):
    return ()

def _setupCliDomain(subp : ArgumentParser):
    def addProperties(parser, init):
        parser.add_argument("-u", "--maxUser", required=init, type=int, help="Maximum number of users")
        parser.add_argument("--address", help="Domain contact address")
        parser.add_argument("--adminName", help="Name of the domain admin")
        parser.add_argument("--endDay", help="Domain expiry date in YYYY-MM-DD format")
        parser.add_argument("--orgID", type=int, help="ID of the organization")
        parser.add_argument("--tel", help="Domain contact telephone number")
        parser.add_argument("--title", help="Domain title")
    sub = subp.add_subparsers()
    create = sub.add_parser("create", help="Create new domain")
    create.set_defaults(_handle=cliDomainCreate)
    create.add_argument("domainname", help="Name of the domain")
    create.add_argument("--create-role", action="store_true", help="Create domain administrator role for new domain")
    create.add_argument("--skip-adaptor-reload", action="store_true", help="Do not reload gromox-adaptor service")
    addProperties(create, True)
    delete = sub.add_parser("delete", help="Soft delete domain",
                            description="Set domain status to deleted and deactivate users")
    delete.set_defaults(_handle=cliDomainDelete)
    delete.add_argument("domainspec", nargs="?", help="Domain ID or prefix to match domainname against")\
        .completer = _cliDomainDomainspecAutocomp
    list = sub.add_parser("list", help="List domains")
    list.set_defaults(_handle=cliDomainList)
    list.add_argument("domainspec", nargs="?", help="Domain ID or prefix to match domainname against")
    list.add_argument("-s", "--sort", nargs="*", help="Sort by attribute, e.g. -s domainname,desc")
    list.add_argument("-f", "--filter", nargs="*", help="Filter by attribute, e.g. -f ID=42")
    modify = sub.add_parser("modify", help="Modify domain")
    modify.set_defaults(_handle=cliDomainModify)
    modify.add_argument("domainspec", help="Domain ID or prefix to match domainname against")\
        .completer = _cliDomainDomainspecAutocomp
    addProperties(modify, False)
    purge = sub.add_parser("purge", help="Permanently delete domain")
    purge.set_defaults(_handle=cliDomainPurge)
    purge.add_argument("domainspec", nargs="?", help="Domain ID or prefix to match domainname against").completer = _noComp
    purge.add_argument("-f", "--files", action="store_true", help="Delete domain and user files on disk")
    purge.add_argument("-y", "--yes", action="store_true", help="Do not question the elevated one")
    recover = sub.add_parser("recover", help="Recover soft-deleted domain")
    recover.set_defaults(_handle=cliDomainRecover)
    recover.add_argument("domainspec", help="Domain ID or prefix to match domainname against")\
        .completer = _cliDomainDomainspecAutocomp
    show = sub.add_parser("show", help="Show detailed information about one or more domains")
    show.set_defaults(_handle=cliDomainShow)
    show.add_argument("domainspec", help="Domain ID or name").completer = _cliDomainDomainspecAutocomp
    show.add_argument("-s", "--sort", nargs="*", help="Sort by attribute, e.g. -s domainname,desc")
    show.add_argument("-f", "--filter", nargs="*", help="Filter by attribute, e.g. -f ID=42")

@Cli.command("domain", _setupCliDomain, help="Domain management")
def cliDomainStub(args):
    pass
