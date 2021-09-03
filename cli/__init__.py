# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH

import argcomplete
import logging
from argparse import ArgumentParser, _SubParsersAction


class CliError(BaseException):
    pass


class Cli:
    class Formatter(logging.Formatter):
        levelstyles = {"DEBUG": {"attrs": ["dark"]},
                       "WARNING": {"color": "yellow"},
                       "ERROR": {"color": "red"},
                       "CRITICAL": {"color": "red", "attrs": ["bold"]}}

        def __init__(self, format, col):
            super().__init__(format)
            self.__col = col

        def format(self, record):
            record.msg = self.__col(record.msg, **self.levelstyles.get(record.levelname, {}))
            return logging.Formatter.format(self, record)

    funcs = []

    def __init__(self, mode="standalone", **kwargs):
        """Create cli object

        Parameters
        ----------
        mode : str, optional
            Cli execution mode. Applies some global adjustments if set to "standalone".
            No other setting currently has an effect.
            The default is "standalone".

        Keyword Arguments
        -----------------

        color : bool, optional
            Force color mode.
            Default is to auto-detect if color is available.
        completer : object, optional
            Object providing a `rl_complete(prefix, state)` function used for command completion.
            Default argcomplete.Completer()
        fs : dict, optional
            If set, use as base for emulated filesystem.
            May contain name -> content mapping to emulate readable files.
            `closeFiles` will automatically remove readable files and store written files along with their write mode as dicts.
            Default is None (write directly to disk)
        host : str, optional
            Host string to display next to the command prompt. Default is None.
        stdin : file-like, optional
            If set, use this file as stdin.
            Defaults to `sys.stdin`
        stdout : file-like, optional
            If set, use this file as stdout
            Defaults to `sys.stdout`

        **kwargs : any
            Further keyword arguments
        """
        self._createParser()
        if mode == "standalone":
            argcomplete.autocomplete(self.parser)
        import sys
        self.mode = mode
        self.stdout = kwargs.get("stdout", sys.stdout)
        self.stdin = kwargs.get("stdin", sys.stdin)
        self.host = kwargs.get("host")
        self.completer = kwargs.get("completer")
        self.__completing = True
        self.colored = self.detectcolor(self.stdout, kwargs.get("color"))
        self.col = self.colorfunc(self.colored)
        self.fs = None
        if "fs" in kwargs and isinstance(kwargs["fs"], dict):
            self.fs = kwargs["fs"]
            import io
            for file, content in self.fs.items():
                self.fs[file] = dict(mode="r",
                                     stream=(io.BytesIO if isinstance(content, bytes) else io.StringIO)(content))
        if mode == "standalone":
            self.initLogging(self.stdout, color=self.colored)

    def execute(self, args=None, secure=True):
        """Execute commands as specified by args.

        If no args are passed, sys.args is used instead.

        Parameters
        ----------
        args : list of strings, optional
            Command line arguments to execute. The default is None.
        """
        self.__completing = False
        dispatch = self.parser.parse_args(args)
        self.__completing = True
        dispatch._cli = self
        if hasattr(dispatch, "_handle"):
            try:
                return dispatch._handle(dispatch) or 0
            except CliError as err:
                self.print(self.col(err.args[0], "red"))
                return 1
            except:
                if not secure:
                    raise
                return -1
        else:
            self.parser.print_help()
            return 2

    @classmethod
    def register(cls, name, handler, setup, **kwargs) -> ArgumentParser:
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
        cls.funcs.append((name, handler, setup, kwargs))

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
            cls.register(name, func, parserSetup, **kwargs)
            return func
        return inner

    @staticmethod
    def colorfunc(col):
        if col:
            import termcolor
            return termcolor.colored
        else:
            return lambda text, *args, **kwargs: text

    @staticmethod
    def detectcolor(stdout, preset=None):
        try:
            import termcolor
            if preset is not None:
                return preset
            return stdout.isatty()
        except Exception:
            return False

    @staticmethod
    def initLogging(stdout=None, color=None):
        """Initialize stand-alone mode."""
        if stdout is None:
            import sys
            stdout = sys.stdout
        color = Cli.detectcolor(stdout, color)
        fmt = "(%(name)s) %(message)s"
        if not color:
            fmt = "[%(levelname)s] "+fmt
        handler = logging.StreamHandler()
        handler.setFormatter(Cli.Formatter(fmt, Cli.colorfunc(color)))
        logging.root.handlers = [handler]
        from tools.config import initLoggers
        try:
            initLoggers()
        except Exception as err:
            logging.getLogger("config").error("Failed to initialize loggers: "+" - ".join(str(arg) for arg in err.args))

    def _createParser(self):
        """Create parser from registered functions."""
        def redirect(parser):
            def perr(msg):
                if not self.__completing:
                    parser.print_usage(self.stdout)
                    self.print(msg)
                raise SystemExit(1)

            print_help = parser.print_help
            parser.print_help = lambda: print_help(self.stdout)
            parser.error = perr
            if parser._subparsers:
                for subparser in (p for a in parser._subparsers._actions if isinstance(a, _SubParsersAction)
                                  for p in a.choices.values()):
                    redirect(subparser)

        self.parser = ArgumentParser(description="grommunio admin cli")
        subparsers = self.parser.add_subparsers()
        for name, handler, parserSetup, kwargs in self.funcs:
            subp = subparsers.add_parser(name, **kwargs)
            parserSetup(subp)
            subp.set_defaults(_handle=handler)
        redirect(self.parser)

    SUCCESS = 0
    ERR_DECLINE = 1
    ERR_USR_ABRT = 2

    def confirm(self, prompt=""):
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
            return Cli.SUCCESS if self.input(prompt).lower() == "y" else Cli.ERR_DECLINE
        except CliError:
            raise
        except:
            return Cli.ERR_USR_ABRT

    def choice(self, prompt="", choices=(), default=None):
        """Display choice dialogue.

        If a default value is set, it is returned on empty input, otherwise

        Parameters
        ----------
        prompt : str, optional
            Prompt to display. The default is "".
        choices : list-like, optional
            Calid choices. The default is ().
        default : str, optional
            Default value. The default is None.

        Returns
        -------
        TYPE
            DESCRIPTION.
        """
        while True:
            try:
                res = self.input(prompt)
            except KeyboardInterrupt:
                return None
            if default is not None and res == "":
                return default
            if res not in choices:
                continue
            return res

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
            DB.session.rollback()
            err = DB.testConnection()
            if err is not None:
                raise CliError(err)
        if "LDAP" in args:
            from services import ServiceHub
            if not ServiceHub.get("ldap").available:
                raise CliError("LDAP not available")

    def input(self, prompt="", secret=False):
        """Display input prompt.

        If stdin is redirected from sys.stdin, the prompt is printed and stdin.readline is called.
        The result is automatically echoed to stdout if stdin is not a tty.

        If stdin is disabled, a CliError is raised.

        Parameters
        ----------
        prompt : str, optional
            Prompt to display. The default is "".
        secret : bool, optional
            Perform secret input (use getpass if available). The default is False.

        Raises
        ------
        CliError
            Input is not available (disabled)

        Returns
        -------
        str
            User input
        """
        if self.stdin is None:
            raise CliError("Input required but not available.")
        import sys
        if self.stdin == sys.stdin:
            if not secret:
                if self.stdout != sys.stdout:
                    self.print(prompt, end="")
                v = input(prompt if self.stdout == sys.stdout else "")
                if not self.stdin.isatty():
                    self.print(v)
                return v
            else:
                from getpass import getpass
                return getpass(prompt, self.stdout)
        else:
            self.print(prompt, end="")
            v = self.stdin.readline()
            if v.endswith("\n"):
                v = v[:-1]
            if not self.stdin.isatty() and not secret:
                self.print(v)
            return v

    def print(self, msg="", *args, **kwargs):
        """Print message to stdout.

        Provides abstraction layer for redirected stdout.

        Parameters
        ----------
        msg : str, optional
            Message to print. The default is "".
        *args : any
            Arguments forwarded to print
        **kwargs : any
            Keyword arguments forwarded to print
        """
        print(msg, *args, file=kwargs.pop("file", self.stdout), **kwargs)

    def open(self, file, mode="r", conf=False):
        """Open file.

        Provides abstraction layer for emulated filesystem. Can be used as context like builtin open function.

        If filesystem emulation is not active, the call is forwarded to builtin open().

        On emulated file systems, opening a file for reading will return the associated StringIO/BytesIO object
        if the file is provided in the emulated filesystem, otherwise a FileNotFoundError is raised.
        Opening a file for writing will create a filesystem entry and return a StringIO or BytesIO object, depending on
        whether the mode contains a 'b'.
        Closing a file on an emulated filesystem will store the content in the filesystem entry and remove the file object.

        If `conf` is set to True, the filename is interpreted as a config value containing the path.
        If the config value does not contain a path, a key error is raised.

        Parameters
        ----------
        file : str
            Name of the file
        mode : str, optional
            File open mode. The default is "r".
        conf : bool, optional
            Filename is a config value. The default is False.

        Raises
        ------
        KeyError
            `conf` is True but `file` is not a valid config value.
        FileNotFoundError
            File is opened for reading but does not exist

        Returns
        -------
        file-like
            Object providing IO interface
        """
        if conf:
            from tools.config import Config
            path = Config
            for part in file.split("."):
                path = path.get(part)
            if not isinstance(path, str):
                raise KeyError("Config value '{}' not set".format(file))
            conf = file
            file = path
        if self.fs is None:
            return open(file, mode)
        if "r" in mode:
            if file not in self.fs:
                raise FileNotFoundError(2, "No such file or directory in emulated filesystem")
        elif "w" in mode:
            import io
            stream = io.BytesIO() if "b" in mode else io.StringIO()
            stream.close = self._closebuf(file)
            self.fs[file] = dict(stream=stream, mode=mode, conf=conf or None)
        return self.fs[file]["stream"]

    def _closebuf(self, file):
        """Close buffer and store contents."""
        def close():
            self.fs[file]["content"] = self.fs[file].pop("stream").getvalue()
        return close

    def closeFiles(self):
        """Close all files on emulated filesystem.

        Closes all open files and stores their content.
        Files opened in read mode are deleted.

        Does not have any effect if filesystem emulation is not active and for files in write mode that are already closed.
        """
        if self.fs is None:
            return
        for file, state in self.fs.items():
            if "stream" in state and "w" in state["mode"]:
                state["content"] = state.pop("stream").getvalue()
        readonly = tuple(file for file, state in self.fs.items() if "w" not in state["mode"])
        for f in readonly:
            self.fs.pop(f)

    def complete(self, text, state=None, maxCompletions=20):
        """Provide completions for given prefix.

        Parameters
        ----------
        text : str
            Input prefix.
        state : int, optional
            If set, provide the `state`th completion (readline mode). The default is None.
        maxCompletions : int, optional
            Maximum number of completions to return (complete mode). The default is 20.

        Returns
        -------
        str or list
            Completion or None (readline mode), or list of completions (complete mode)
        """
        self.__completing = True
        if self.completer is None:
            self.completer = argcomplete.CompletionFinder(self.parser, always_complete_options=False)
        if state is not None:
            res = self.completer.rl_complete(text, state)
            self.__completing = False
            return res
        completions = []
        for i in range(maxCompletions):
            completion = self.completer.rl_complete(text, i)
            if completion is None:
                break
            completions.append(completion)
        self.__completing = False
        return completions


from . import config, dbconf, dbtools, domain, fetchmail, fs, ldap, mconf, misc, mlist, remote, services, user
