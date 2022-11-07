# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH

from . import Cli, ArgumentParser, InvalidUseError

_states = {-1: ("UNLOADED", {"attrs": ["dark"]}),
           0: ("LOADED", {"color": "green"}),
           1: ("UNAVAILABLE", {"color": "yellow"}),
           2: ("SUSPENDED", {"color": "yellow"}),
           3: ("ERROR", {"color": "red"}),
           4: ("DISABLED", {"color": "red", "attrs": ["dark"]})}


def _counts(cli, service):
    from services import ServiceHub
    if service.state == ServiceHub.UNAVAILABLE:
        return cli.col(" ({}/{})".format(service.failures, service.maxfailures or "\u221e"), **_sstyle(service))
    elif service.state == ServiceHub.SUSPENDED:
        return cli.col(" ({}/{})".format(service.reloads, service.maxreloads), **_sstyle(service))
    elif service.state == ServiceHub.ERROR:
        if service.maxreloads:
            return cli.col(" ({}/{})".format(service.reloads, service.maxreloads), **_sstyle(service))
        elif service.maxfailures:
            return cli.col(" ({}/{})".format(service.failures, service.maxfailures or "\u221e", **_sstyle(service)))
    return ""


def _excinfo(service, verbose):
    if not all((verbose, service.exc, service.state >= 1)):
        return ""
    if verbose > 1:
        return " ("+" - ".join(str(arg) for arg in service.exc.args)+")"
    return " ("+(str(service.exc.args[0]) if len(service.exc.args) else type(service.exc).__name__)+")"


def _sname(service):
    return _states.get(service.state, ("UNKNOWN",))[0]


def _sstyle(service):
    return _states.get(service.state, (None, {"color": "magenta"}))[1]


def _printService(cli, service):
    cli.print(cli.col(service.name, attrs=["bold"])+"  "+cli.col(_sname(service), **_sstyle(service)) +
              _counts(cli, service)+_excinfo(service, 2))


def cliServiceLoad(args):
    cli = args._cli
    from services import ServiceHub
    try:
        service = ServiceHub.load(args.service, *args.args, force_reload=args.reload)
        _printService(cli, service)
    except ValueError as err:
        cli.print(cli.col("Failed to load service: "+err.args[0], "red"))


def cliServiceStatus(args):
    from .common import Table
    from services import ServiceHub
    cli = args._cli

    data = []
    services = args.services or ServiceHub.services()
    for service in services:
        instances = ServiceHub.instances(service)
        data.append((cli.col(service, attrs=["bold"]),
                     cli.col("({} instance{})".format(len(instances), "" if len(instances) == 1 else "s"), attrs=["dark"])))
        default = None
        for instance in instances:
            if not instance[0]:
                default = instance[1]
        for instance in instances:
            if instance[0] and instance[1] is default:
                state = cli.col("-> "+instance[1].name, "magenta")
            else:
                state = cli.col(_sname(instance[1]), **_sstyle(instance[1]))+_counts(cli, instance[1])
            data.append(("  "+ServiceHub.servicename(service, *instance[0]), state, _excinfo(instance[1], args.verbose)))
    Table(data).print(cli)


def _serviceCompleter(prefix, parsed_args, **kwargs):
    from services import ServiceHub
    available = set(ServiceHub.services())
    for service in parsed_args.services:
        available.discard(service)
    return available


def _cliSetupServiceParser(subp: ArgumentParser):
    Cli.parser_stub(subp)
    sub = subp.add_subparsers()
    load = sub.add_parser("load", help="(Re)load service(s)")
    load.set_defaults(_handle=cliServiceLoad)
    load.add_argument("-r", "--reload", action="store_true", help="Force reloading")
    load.add_argument("service", help="Service to (re)load").completer = _serviceCompleter
    load.add_argument("args", nargs="*", help="Service parameters")
    status = sub.add_parser("status", help="List services")
    status.set_defaults(_handle=cliServiceStatus)
    status.add_argument("-v", "--verbose", action="count", help="Show more information")
    status.add_argument("services", nargs="*", help="Only show status of specified service(s)").completer = _serviceCompleter


@Cli.command("service", _cliSetupServiceParser)
def cliServices(args):
    raise InvalidUseError()
