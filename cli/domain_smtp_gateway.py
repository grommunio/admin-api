# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 grommunio GmbH
#
# grommunio-admin domain smtp-gateway …
#
#   set <DOMAIN> --host HOST [--port 587] [--encryption starttls]
#                  [--username USER] [--password PASS] [--from ADDR]
#                  [--disable] [--description "…"]
#       Create or update the per-domain SMTP gateway config.
#
#   show <DOMAIN>
#       Print the current configuration (password is masked).
#
#   delete <DOMAIN>
#       Remove the per-domain gateway config and fall back to the
#       global /etc/gromox/gromox.cfg outgoing_smtp_url.
#
#   list
#       List all configured gateways.

from . import Cli, InvalidUseError
from .common import domainCandidates
from argparse import ArgumentParser

_parsers = []


def _register(sub):
    """Register the smtp-gateway subcommand."""
    p = sub.add_parser("smtp-gateway", help="Manage per-domain SMTP gateway")
    sp = p.add_subparsers(dest="_action", metavar="action", required=True)

    p_set = sp.add_parser("set", help="Create or update SMTP gateway for a domain")
    p_set.add_argument("domainspec", help="Domain name or ID")
    p_set.add_argument("--host", required=True, help="SMTP server hostname or IP")
    p_set.add_argument("--port", type=int, default=25,
                       help="SMTP server port (default 25)")
    p_set.add_argument("--encryption", default="none",
                       choices=("none", "starttls", "starttls_unverified", "tls"),
                       help="Encryption mode (default none)")
    p_set.add_argument("--username", help="SMTP authentication username")
    p_set.add_argument("--password", help="SMTP authentication password")
    p_set.add_argument("--from", dest="from_address",
                       help="Override envelope From address")
    p_set.add_argument("--disable", action="store_true",
                       help="Store the config but mark it as disabled")
    p_set.add_argument("--description", help="Free-form description")
    p_set.set_defaults(_handle=cliDomainSmtpGateway)
    _parsers.append(p_set)

    p_show = sp.add_parser("show", help="Show SMTP gateway config for a domain")
    p_show.add_argument("domainspec", help="Domain name or ID")
    p_show.set_defaults(_handle=cliDomainSmtpGateway)
    _parsers.append(p_show)

    p_del = sp.add_parser("delete", help="Remove SMTP gateway config for a domain")
    p_del.add_argument("domainspec", help="Domain name or ID")
    p_del.set_defaults(_handle=cliDomainSmtpGateway)
    _parsers.append(p_del)

    p_list = sp.add_parser("list", help="List all configured SMTP gateways")
    p_list.set_defaults(_handle=cliDomainSmtpGateway)
    _parsers.append(p_list)
    return p


def cliDomainSmtpGateway(args):
    cli = args._cli
    cli.require("DB")
    action = args._action
    if action == "set":
        return _do_set(cli, args)
    if action == "show":
        return _do_show(cli, args)
    if action == "delete":
        return _do_delete(cli, args)
    if action == "list":
        return _do_list(cli, args)
    raise InvalidUseError("Unknown smtp-gateway action: {}".format(action))


def _do_set(cli, args):
    from orm.domains import Domains
    from orm.domain_smtp_gateway import DomainSmtpGateway
    from orm import DB

    domains = domainCandidates(args.domainspec).all()
    if len(domains) != 1:
        cli.print(cli.col("Domain not found or ambiguous: {}".format(args.domainspec), "red"))
        return 1
    domain = domains[0]

    gw = DomainSmtpGateway.query.filter(DomainSmtpGateway.domainID == domain.ID).first()
    if gw is None:
        gw = DomainSmtpGateway({"domainID": domain.ID, "host": args.host})
    else:
        gw.host = args.host
    gw.port = args.port
    gw.encryption = args.encryption
    if args.username is not None:
        gw.username = args.username
    if args.password is not None:
        gw.password = args.password
    if args.from_address is not None:
        gw.fromAddress = args.from_address
    gw.enabled = 0 if args.disable else 1
    if args.description is not None:
        gw.description = args.description

    if gw not in DB.session:
        DB.session.add(gw)
    DB.session.commit()

    err = DomainSmtpGateway.reload_gromox()
    if err is not None:
        cli.print(cli.col("Saved, but: {}".format(err), "yellow"))
        return 0
    cli.print(cli.col("SMTP gateway for {} saved and gromox reloaded.".format(domain.domainname), "green"))
    return 0


def _do_show(cli, args):
    from orm.domains import Domains
    from orm.domain_smtp_gateway import DomainSmtpGateway
    domains = domainCandidates(args.domainspec).all()
    if len(domains) != 1:
        cli.print(cli.col("Domain not found or ambiguous", "red"))
        return 1
    domain = domains[0]
    gw = DomainSmtpGateway.query.filter(DomainSmtpGateway.domainID == domain.ID).first()
    if gw is None:
        cli.print(cli.col("No SMTP gateway configured for {}".format(domain.domainname), "yellow"))
        return 0
    cli.print(cli.col("SMTP gateway for {}:".format(domain.domainname), attrs=["bold"]))
    cli.print("  host:        {}".format(gw.host))
    cli.print("  port:        {}".format(gw.port))
    cli.print("  encryption:  {}".format(gw.encryption))
    cli.print("  username:    {}".format(gw.username or ""))
    cli.print("  password:    {}".format("***" if gw.password else "(not set)"))
    cli.print("  fromAddress: {}".format(gw.fromAddress or ""))
    cli.print("  enabled:     {}".format(bool(gw.enabled)))
    cli.print("  description: {}".format(gw.description or ""))
    return 0


def _do_delete(cli, args):
    from orm.domains import Domains
    from orm.domain_smtp_gateway import DomainSmtpGateway
    from orm import DB
    domains = domainCandidates(args.domainspec).all()
    if len(domains) != 1:
        cli.print(cli.col("Domain not found or ambiguous", "red"))
        return 1
    domain = domains[0]
    gw = DomainSmtpGateway.query.filter(DomainSmtpGateway.domainID == domain.ID).first()
    if gw is None:
        cli.print(cli.col("No SMTP gateway configured for {}".format(domain.domainname), "yellow"))
        return 0
    DB.session.delete(gw)
    DB.session.commit()
    err = DomainSmtpGateway.reload_gromox()
    if err is not None:
        cli.print(cli.col("Deleted, but: {}".format(err), "yellow"))
        return 0
    cli.print(cli.col("SMTP gateway for {} removed.".format(domain.domainname), "green"))
    return 0


def _do_list(cli, args):
    from orm.domain_smtp_gateway import DomainSmtpGateway
    from orm.domains import Domains
    from orm import DB
    rows = (DB.session.query(DomainSmtpGateway, Domains.domainname)
            .join(Domains, Domains.ID == DomainSmtpGateway.domainID)
            .order_by(Domains.domainname).all())
    if not rows:
        cli.print(cli.col("No per-domain SMTP gateways configured.", "yellow"))
        return 0
    cli.print("{:<6} {:<30} {:<25} {:<6} {:<10} {}".format(
        "ID", "Domain", "Host", "Port", "Encryption", "Enabled"))
    for gw, dname in rows:
        cli.print("{:<6} {:<30} {:<25} {:<6} {:<10} {}".format(
            gw.domainID, dname, gw.host, gw.port, gw.encryption,
            "yes" if gw.enabled else "NO"))
    return 0
