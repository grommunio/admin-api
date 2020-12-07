# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grammm GmbH

from . import Cli, ArgumentParser


def _runParserSetup(subp: ArgumentParser):
    subp.add_argument("--ip", "-i", default="0.0.0.0", type=str, help="Host address to bind to")
    subp.add_argument("--port", "-p", default=5001, type=int, help="Host port to bind to")
    subp.add_argument("--debug", "-d", action="store_true", help="Run in debug mode")


@Cli.command("run", _runParserSetup)
def cliRun(args):
    from api.core import API
    import endpoints
    import importlib
    for group in endpoints.__all__:
        importlib.import_module("endpoints."+group)
    API.run(host=args.ip, port=args.port, debug=args.debug)


def _versionParserSetup(subp: ArgumentParser):
    components = subp.add_mutually_exclusive_group()
    components.add_argument("--api", "-a", action="store_true", help="Print API version")
    components.add_argument("--backend", "-b", action="store_true", help="Print Backend version")
    components.add_argument("--combined", "-c", action="store_true", help="Print combined version")

@Cli.command("version", _versionParserSetup)
def cliVersion(args):
    from api import backendVersion, apiVersion
    if args.backend:
        print(backendVersion)
    elif args.combined:
        vdiff = int(backendVersion.rsplit(".", 1)[1])-int(apiVersion.rsplit(".", 1)[1])
        if vdiff == 0:
            print(apiVersion)
        else:
            print("{}{:+}".format(apiVersion, vdiff))
    else:
        print(apiVersion)

@Cli.command("chkconfig")
def cliChkConfig(args):
    from tools.config import validate
    result = validate()
    if result is None:
        print("Configuration schema valid")
        return 0
    else:
        print("Error: "+result)
        return 1


def _setupTaginfo(subp: ArgumentParser):
    subp.add_argument("tagID", nargs="+", help="Numeric tag ID in decimal or hexadecimal")


@Cli.command("taginfo", _setupTaginfo)
def cliTaginfo(args):
    from tools.constants import PropTags, PropTypes
    for tagid in args.tagID:
        try:
            ID = int(tagid, 0)
        except:
            print(tagid+": not a valid number")
            continue
        propname = PropTags.lookup(ID, "unknown")
        proptype = PropTypes.lookup(ID, "unknown")
        print("0x{:x}: {}, type {}".format(ID, propname, proptype))
