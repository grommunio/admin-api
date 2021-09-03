# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH

from . import Cli, ArgumentParser

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
    return " ("+" - ".join(str(arg) for arg in service.exc.args)+")"


def _sname(service):
    return _states.get(service.state, ("UNKNOWN",))[0]


def _sstyle(service):
    return _states.get(service.state, (None, {"color": "magenta"}))[1]


def _printService(cli, service, maxlen=0, verbose=False):
    pad = " "*(maxlen-len(service.name))
    cli.print(cli.col(service.name, attrs=["bold"])+"  "+pad+cli.col(_sname(service), **_sstyle(service)) +
              _counts(cli, service)+_excinfo(service, verbose))


def cliServiceDisable(args):
    from services import ServiceHub
    if len(args.services) == 0:
        args.services = [service.name for service in ServiceHub]
    for service in args.services:
        if service in ServiceHub:
            ServiceHub[service].disable()
        else:
            args.services.remove(service)
    maxlen = max(len(service) for service in args.services)
    for service in args.services:
        _printService(args._cli, ServiceHub[service], maxlen)


def cliServiceLoad(args):
    from services import ServiceHub
    ServiceHub.load(*args.services, force_reload=args.reload)
    if len(args.services) == 0:
        args.services = [service.name for service in ServiceHub]
    maxlen = max(len(service) for service in args.services)
    for service in args.services:
        if service in ServiceHub:
            _printService(args._cli, ServiceHub[service], maxlen)


def cliServiceStatus(args):
    from services import ServiceHub
    cli = args._cli
    maxlen = max(len(service.name) for service in ServiceHub)
    for service in ServiceHub:
        _printService(cli, service, maxlen, args.verbose)


def _serviceCompleter(prefix, parsed_args, **kwargs):
    from services import ServiceHub
    available = set(service.name for service in ServiceHub)
    for service in parsed_args.services:
        available.discard(service)
    return available


def _cliSetupServiceParser(subp: ArgumentParser):
    sub = subp.add_subparsers()
    disable = sub.add_parser("disable", help="Manually disable service")
    disable.set_defaults(_handle=cliServiceDisable)
    disable.add_argument("services", nargs="*", help="Service to disable").completer = _serviceCompleter
    load = sub.add_parser("load", help="(Re)load service(s)")
    load.set_defaults(_handle=cliServiceLoad)
    load.add_argument("-r", "--reload", action="store_true", help="Force reloading")
    load.add_argument("services", nargs="*", help="Service(s) to (re)load").completer = _serviceCompleter
    status = sub.add_parser("status", help="List services")
    status.set_defaults(_handle=cliServiceStatus)
    status.add_argument("-v", "--verbose", action="count", help="Show more information")


@Cli.command("service", _cliSetupServiceParser)
def cliServices(args):
    pass
