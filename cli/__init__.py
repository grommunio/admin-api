# -*- coding: utf-8 -*-
"""
Created on Thu Sep 17 11:32:57 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: Grammm GmbH, 2020
"""

from argparse import ArgumentParser

class Cli:
    parser = ArgumentParser(description="Grammm admin backend")
    subparsers = parser.add_subparsers()

    @classmethod
    def execute(cls, args=None):
        """Execute commands as specified by args.

        If no args are passed, sys.args is used instead.

        Parameters
        ----------
        args : list of strings, optional
            Command line arguments to execute. The default is None.
        """
        dispatch = cls.parser.parse_args(args)
        if hasattr(dispatch, "_handle"):
            dispatch._handle(dispatch)
        else:
            cls.parser.print_help()
            exit(2)

    @classmethod
    def register(cls, name, handler) -> ArgumentParser:
        """Register a new sub-command.

        The parsed arguments are passed to the handler function.

        Parameters
        ----------
        name : str
            Name of the sub-command
        handler : Callable
            Function that executes the sub-command.

        Returns
        -------
        ArgumentParser
            Sub-parser that can be customized with sub-command specific arguments
        """
        subp = cls.subparsers.add_parser(name)
        subp.set_defaults(_handle=handler)
        return subp

    @classmethod
    def command(cls, name, parserSetup=lambda subp: None):
        """Decorator for sub-command handlers.

        Can be used instead of calling register().

        Parameters
        ----------
        name : str
            Name of the subcommand
        parserSetup : Callable, optional
            Function that sets up the sub-command parser. By default not further initialization is done.
        """
        def inner(func):
            subp = cls.register(name, func)
            parserSetup(subp)
            return func
        return inner


def _runParserSetup(subp: ArgumentParser):
    subp.add_argument("--ip", "-i", default="0.0.0.0", type=str, help="Host address to bind to")
    subp.add_argument("--port", "-p", default=5001, type=int, help="Host port to bind to")
    subp.add_argument("--debug", "-d", action="store_true", help="Run in debug mode")


@Cli.command("run", _runParserSetup)
def cliRun(args):
    from api import API
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
    exit(0)

@Cli.command("chkconfig")
def cliChkConfig(args):
    from tools.config import validate
    result = validate()
    if result is None:
        print("Configuration schema valid")
        exit(0)
    else:
        print("Error: "+result)
        exit(1)

from . import dbtools
