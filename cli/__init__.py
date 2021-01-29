# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grammm GmbH

import argcomplete
from argparse import ArgumentParser

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
            return dispatch._handle(dispatch) or 0
        else:
            cls.parser.print_help()
            return 2

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


from . import dbtools, ldap, mconf, misc, mlist, user
