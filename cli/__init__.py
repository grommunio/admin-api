# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grammm GmbH

import argcomplete
from argparse import ArgumentParser

class CliError(BaseException):
    pass

class Cli:
    parser = ArgumentParser(description="Grammm admin backend")
    subparsers = parser.add_subparsers()
    interactive = False
    rlAvail = False
    col = lambda text, *args, **kwargs: text

    @classmethod
    def execute(cls, args=None):
        """Execute commands as specified by args.

        If no args are passed, sys.args is used instead.

        Parameters
        ----------
        args : list of strings, optional
            Command line arguments to execute. The default is None.
        """
        argcomplete.autocomplete(cls.parser)
        cls.enableColor()
        dispatch = cls.parser.parse_args(args)
        if hasattr(dispatch, "_handle"):
            try:
                return dispatch._handle(dispatch) or 0
            except CliError as err:
                print(cls.col(err.args[0], "red"))
                return 1
        else:
            cls.parser.print_help()
            return 2

    @classmethod
    def register(cls, name, handler, **kwargs) -> ArgumentParser:
        """Register a new sub-command.

        The parsed arguments are passed to the handler function.

        Parameters
        ----------
        name : str
            Name of the sub-command
        handler : Callable
            Function that executes the sub-command.
        kwargs : any
            Arguments passed to the add_parser function

        Returns
        -------
        ArgumentParser
            Sub-parser that can be customized with sub-command specific arguments
        """
        subp = cls.subparsers.add_parser(name, **kwargs)
        subp.set_defaults(_handle=handler)
        return subp

    @classmethod
    def command(cls, name, parserSetup=lambda subp: None, **kwargs):
        """Decorator for sub-command handlers.

        Can be used instead of calling register().

        Parameters
        ----------
        name : str
            Name of the subcommand
        parserSetup : Callable, optional
            Function that sets up the sub-command parser. By default no further initialization is done.
        kwargs : any
            Arguments passed to the add_parser function
        """
        def inner(func):
            subp = cls.register(name, func, **kwargs)
            parserSetup(subp)
            return func
        return inner

    @classmethod
    def enableColor(cls):
        try:
            import termcolor
            from sys import stdout
            if stdout.isatty():
                cls.col = lambda *args, **kwargs: termcolor.colored(*args, **kwargs)
        except:
            pass

    SUCCESS = 0
    ERR_DECLINE = 1
    ERR_USR_ABRT = 2

    @staticmethod
    def confirm(prompt=""):
        """Display confirmation dialogue.

        Parameters
        ----------
        prompt : string, optional
            Prompt to display. The default is "".

        Returns
        -------
        int
            SUCCESS if user input was "y", ERR_USR_ABRT if user aborted, ERR_DECLINE otherwise
        """
        try:
            return Cli.SUCCESS if input(prompt).lower() == "y" else Cli.ERR_DECLINE
        except:
            return Cli.ERR_USR_ABRT

    @staticmethod
    def require(*args):
        """Check component availability.

        Each argument as a string containing the component name.
        If a component is not available, a CliError is raised, which is automatically caught by the Cli.
        Known components are:
            - DB: The MySQL database
            - LDAP: A connection to the LDAP server

        Parameters
        ----------
        *args : string
            Component names. Unknown components are ignored.
        """
        if "DB" in args:
            from orm import DB
            if DB is None:
                raise CliError("Database not available")
        if "LDAP" in args:
            from tools.ldap import LDAP_available
            if not LDAP_available:
                raise CliError("LDAP not available")

from . import dbconf, dbtools, domain, fs, ldap, mconf, misc, mlist, user
