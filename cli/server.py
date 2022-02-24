# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2022 grommunio GmbH

from . import Cli, InvalidUseError, ArgumentParser


def _dumpServer(cli, server):
    cli.print(cli.col("{} ({})".format(server.hostname, server.ID), attrs=["bold"]))
    cli.print("  ID: "+str(server.ID))
    cli.print("  hostname: "+server.hostname)
    cli.print("  extname: "+server.extname)
    cli.print("  domains: "+str(server.domains))
    cli.print("  users: "+str(server.users))


def _sanitizeData(data):
    cliargs = {"_handle", "_cli", "serverspec"}
    return {key: value for key, value in data.items() if value is not None and key not in cliargs}


def _serverCandidates(serverspec):
    from orm.misc import Servers
    if serverspec is None:
        return Servers.query
    filter = Servers.ID == serverspec if serverspec.isdigit() else Servers.hostname == serverspec
    return Servers.query.filter(filter)


def cliServersCreate(args):
    cli = args._cli
    cli.require("DB")
    from orm.misc import DB, Servers
    data = _sanitizeData(args.__dict__)
    error = Servers.checkCreateParams(data)
    if error:
        cli.print(cli.col("Could not create server: "+error, "red"))
        return 1
    server = Servers(data)
    DB.session.add(server)
    DB.session.commit()
    _dumpServer(cli, server)


def cliServersDelete(args):
    cli = args._cli
    cli.require("DB")
    from orm import DB
    servers = _serverCandidates(args.serverspec).all()
    if len(servers) == 0:
        cli.print(cli.col("Server not found", "yellow"))
        return 1
    if len(servers) > 1:
        cli.print(cli.col("'{}' is ambiguous".format(args.serverspec), "yellow"))
        return 2
    server = servers[0]
    if server.users+server.domains:
        cli.print(cli.col("Cannot delete server with users or domains", "red"))
        return 3
    DB.session.delete(servers[0])
    DB.session.commit()
    cli.print("Server deleted.")


def cliServersList(args):
    cli = args._cli
    cli.require("DB")
    from orm.misc import Servers
    query = _serverCandidates(args.serverspec)
    if "filter" in args and args.filter is not None:
        query = Servers.autofilter(query, {f.split("=", 1)[0]: f.split("=", 1)[1] for f in args.filter if "=" in f})
    if "sort" in args and args.sort is not None:
        query = Servers.autosort(query, args.sort)
    servers = query.all()
    for server in servers:
        cli.print("{}: {} ({})".format(server.ID, cli.col(server.hostname, attrs=["bold"]), server.extname))
    cli.print(cli.col("({} result{})".format(len(servers), "" if len(servers) == 1 else "s"), attrs=["dark"]))


def cliServersModify(args):
    cli = args._cli
    cli.require("DB")
    from orm import DB
    servers = _serverCandidates(args.serverspec).all()
    if len(servers) == 0:
        cli.print(cli.col("Server not found", "yellow"))
        return 1
    if len(servers) > 1:
        cli.print(cli.col("'{}' is ambiguous".format(args.serverspec), "yellow"))
        return 2
    server = servers[0]
    data = _sanitizeData(args.__dict__)
    server.fromdict(data)
    DB.session.commit()
    _dumpServer(cli, server)


def cliServersShow(args):
    cli = args._cli
    cli.require("DB")
    servers = _serverCandidates(args.serverspec).all()
    if len(servers) == 0:
        cli.print(cli.col("No servers found.", "yellow"))
        return 1
    for server in servers:
        _dumpServer(cli, server)


def _cliServerServerspecAutocomp(prefix, **kwargs):
    from orm.misc import Servers
    return (server.hostname for server in Servers.query.filter(Servers.hostname.ilike(prefix+"%")).all())


def _setupCliServersParser(subp: ArgumentParser):
    def addProperties(parser, init):
        parser.add_argument("-e", "--extname", required=init, help="External host name")
        parser.add_argument("-H", "--hostname", required=init, help="Internal host name")
    sub = subp.add_subparsers()
    create = sub.add_parser("create", help="Create new server entry")
    create.set_defaults(_handle=cliServersCreate)
    addProperties(create, True)
    delete = sub.add_parser("delete", help="Remove server")
    delete.set_defaults(_handle=cliServersDelete)
    delete.add_argument("serverspec", help="Server ID or host name").completer = _cliServerServerspecAutocomp
    list = sub.add_parser("list", help="List servers")
    list.set_defaults(_handle=cliServersList)
    list.add_argument("serverspec", nargs="?", help="Server ID or prefix to match host name against")
    list.add_argument("-f", "--filter", nargs="*", help="Filter by attribute, e.g. -f ID=42")
    list.add_argument("-s", "--sort", nargs="*", help="Sort by attribute, e.g. -s hostname,desc")
    modify = sub.add_parser("modify", help="Modify server entry")
    modify.set_defaults(_handle=cliServersModify)
    modify.add_argument("serverspec", help="server ID or host name").completer = _cliServerServerspecAutocomp
    addProperties(modify, False)
    show = sub.add_parser("show", help="Show detailed information about a server")
    show.set_defaults(_handle=cliServersShow)
    show.add_argument("serverspec", help="Server ID or host name").completer = _cliServerServerspecAutocomp


@Cli.command("server", _setupCliServersParser, help="Multi-server management")
def cliServersStub(args):
    raise InvalidUseError()
