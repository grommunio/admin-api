# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2024 grommunio GmbH

from . import Cli, InvalidUseError
from .common import Table
from argparse import ArgumentParser

_orgAttributes = ("ID", "name", "domainCount", "description")


def _domainCandidate(cli, domainspec):
    from .common import domainCandidates
    domains = domainCandidates(domainspec).all()
    if len(domains) == 0:
        cli.col(f"No domains matching '{domainspec}' - skipped", "yellow")
    elif len(domains) > 1:
        cli.col(f"Domain specification '{domainspec}' is ambiguous - skipped", "yellow")
    else:
        return domains[0]


def _dumpOrg(cli, org):
    cli.print(cli.col("{} ({}):".format(org.name, org.ID), attrs=["bold"]))
    cli.print("  ID: "+str(org.ID))
    cli.print("  name: "+str(org.name))
    cli.print("  description: "+(cli.col("(none)", attrs=["dark"]) if not org.description else org.description))
    cli.print("  domains: " + (cli.col("(none)", attrs=["dark"]) if len(org.domains) == 0 else ""))
    for domain in org.domains:
        cli.print(f"    {domain.displayname}")


def _orgFilter(orgSpec, *filters):
    from orm.domains import Orgs
    from sqlalchemy import and_
    return and_(True if orgSpec is None else
                Orgs.ID == orgSpec if orgSpec.isdigit() else
                Orgs.name.ilike(orgSpec+"%"), *filters)


def _orgQuery(args):
    from orm.domains import Orgs
    query = Orgs.query.filter(_orgFilter(args.orgspec)) if "orgspec" in args else Orgs.query
    if "filter" in args and args.filter is not None:
        query = Orgs.autofilter(query, {f.split("=", 1)[0]: f.split("=", 1)[1] for f in args.filter if "=" in f})
    if "sort" in args and args.sort is not None:
        query = Orgs.autosort(query, args.sort)
    return query


def cliOrgQuery(args):
    cli = args._cli
    cli.require("DB")

    from orm.domains import Orgs
    args.attributes = args.attributes or ("ID", "name", "domainCount")
    query = _orgQuery(args)
    query = Orgs.optimize_query(query, args.attributes)
    orgs = [org.todict(args.attributes) for org in query]
    data = [[org.get(attr) for attr in args.attributes] for org in orgs]
    header = None if len(args.attributes) <= 1 and len(data) <= 1 and args.format == "pretty" else args.attributes
    table = Table(data, header, args.separator, cli.col("(no results)", attrs=["dark"]))
    table.dump(cli, args.format)


def cliOrgShow(args):
    cli = args._cli
    cli.require("DB")
    orgs = _orgQuery(args).all()
    if len(orgs) == 0:
        cli.print(cli.col("No organizations found.", "yellow"))
        return 1
    for org in orgs:
        _dumpOrg(cli, org)


def cliOrgCreate(args):
    cli = args._cli
    cli.require("DB")
    from orm.domains import DB, Orgs
    try:
        org = Orgs({"name": args.name, "description": args.description})
        DB.session.add(org)
        if args.domain is not None:
            for domainspec in args.domain:
                domain = _domainCandidate(cli, domainspec)
                if domain:
                    org.domains.append(domain)
        _dumpOrg(cli, org)
        DB.session.commit()
    except ValueError as err:
        cli.print(cli.col(err.args[0], "red"))
        DB.session.rollback()
        return 1


def cliOrgDelete(args):
    cli = args._cli
    cli.require("DB")
    from orm import DB
    orgs = _orgQuery(args).all()
    if len(orgs) == 0:
        cli.print(cli.col("No organizations found.", "yellow"))
        return 1
    if len(orgs) > 1:
        cli.print(cli.col("'{}' is ambiguous".format(args.orgspec), "yellow"))
        return 2
    org = orgs[0]
    if args.drop or args.deactivate:
        from orm.domains import Domains
        domains = Domains.query.filter(Domains.orgID == org.ID).all()
        for domain in domains:
            if args.deactivate:
                domain.delete()
        Domains.query.filter(Domains.orgID == org.ID).update({Domains.orgID: 0})
    elif len(org.domains) != 0:
        cli.print(cli.col("Cannot delete organization with domains. Specify --drop or --deactivate.", "red"))
        return 3
    DB.session.delete(org)
    DB.session.commit()
    cli.print("Organization deleted.")


def cliOrgModify(args):
    cli = args._cli
    cli.require("DB")
    from orm import DB
    orgs = _orgQuery(args).all()
    if len(orgs) == 0:
        cli.print(cli.col("Organization not found.", "yellow"))
        return 1
    if len(orgs) > 1:
        cli.print(cli.col("'{}' is ambiguous".format(args.orgspec), "yellow"))
        return 2
    org = orgs[0]
    try:
        if args.name:
            org.name = args.name
        if args.description:
            org.description = args.description
        for domainspec in args.domain:
            for domainspec in args.domain:
                domain = _domainCandidate(cli, domainspec)
                if domain:
                    domain.orgID = org.ID
        for domainspec in args.drop_domain:
            domain = _domainCandidate(cli, domainspec)
            if domain:
                if domain.orgID == org.ID:
                    domain.orgID = 0
                else:
                    cli.print(cli.col(f"Domain '{domain.domainname}' is not part of {org.name} - ignored", "yellow"))
        DB.session.commit()
        _dumpOrg(cli, org)
    except ValueError as err:
        cli.print(cli.col("Cannot update organization: "+err.args[0], "red"))
        DB.session.rollback()


def _cliOrgDomainspecAutocomp(prefix, **kwarg):
    from .common import domainCandidates
    from orm.domains import Domains
    return (domain.domainname for domain in domainCandidates(prefix).with_entities(Domains.domainname).all())


def _cliOrgOrgspecAutocomp(prefix, **kwarg):
    from orm.domains import Orgs
    return (org.name for org in _orgQuery(prefix).with_entities(Orgs.name).all())


def _noComp(**kwargs):
    return ()


def _setupCliOrg(subp: ArgumentParser):
    class AttrChoice:
        def __contains__(self, value):
            return value == [] or value in _orgAttributes

        def __getitem__(self, i):
            return _orgAttributes[i]

        def __len__(self):
            return len(_orgAttributes)

    Cli.parser_stub(subp)
    sub = subp.add_subparsers()
    create = sub.add_parser("create", help="Create new organization")
    create.set_defaults(_handle=cliOrgCreate)
    create.add_argument("name", help="Name of the organization")
    create.add_argument("--description", help="Organization description")
    create.add_argument("--domain", action="append", help="Domain ID or prefix to adopt by the organization")\
        .completer = _cliOrgDomainspecAutocomp
    delete = sub.add_parser("delete", help="Delete organization")
    delete.set_defaults(_handle=cliOrgDelete)
    delete.add_argument("orgspec", help="Organization ID or prefix to match name against")\
        .completer = _cliOrgOrgspecAutocomp
    deleteMode = delete.add_mutually_exclusive_group()
    deleteMode.add_argument("--deactivate", action="store_true", help="Drop and soft-delete contained domains")
    deleteMode.add_argument("--drop", action="store_true", help="Move contained domains to default organization")
    modify = sub.add_parser("modify", help="Modify organization")
    modify.set_defaults(_handle=cliOrgModify)
    modify.add_argument("orgspec", help="Organization ID or prefix to match against")\
        .completer = _cliOrgOrgspecAutocomp
    modify.add_argument("--description", help="Organization description")
    modify.add_argument("--name", help="New organization name")
    modify.add_argument("--domain", action="append", help="Adopt domain", default=[]).completer = _cliOrgDomainspecAutocomp
    modify.add_argument("--drop-domain", action="append", help="Drop domain", default=[]).completer = _cliOrgDomainspecAutocomp
    query = sub.add_parser("query", help="Query specific organization attributes", aliases=["list"])
    query.set_defaults(_handle=cliOrgQuery)
    query.add_argument("-f", "--filter", action="append", help="Filter by attribute, e.g. -f ID=42")
    query.add_argument("--format", choices=Table.FORMATS, help="Set output format",
                       metavar="FORMAT", default="pretty")
    query.add_argument("--separator", help="Set column separator")
    query.add_argument("-s", "--sort", action="append", help="Sort by attribute, e.g. -s name,desc")
    query.add_argument("attributes", nargs="*", choices=AttrChoice(), help="Attributes to query", metavar="ATTRIBUTE")
    show = sub.add_parser("show", help="Show detailed information about one or more organizations")
    show.set_defaults(_handle=cliOrgShow)
    show.add_argument("orgspec", help="Domain ID or name").completer = _cliOrgOrgspecAutocomp
    show.add_argument("-f", "--filter", action="append", help="Filter by attribute, e.g. -f ID=42")
    show.add_argument("-s", "--sort", action="append", help="Sort by attribute, e.g. -s domainname,desc")


@Cli.command("org", _setupCliOrg, help="Organization management")
def cliOrgStub(args):
    raise InvalidUseError()
