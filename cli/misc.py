# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH

from . import Cli, CliError, ArgumentParser
from .common import proptagCompleter
import locale
import termios


def _runParserSetup(subp: ArgumentParser):
    subp.add_argument("--debug", "-d", action="store_true", help="Run in debug mode")
    subp.add_argument("--ip", "-i", default="::", type=str, help="Host address to bind to")
    subp.add_argument("--no-config-check", action="store_true", help="Skip configuration check")
    subp.add_argument("--port", "-p", default=5001, type=int, help="Host port to bind to")
    subp.add_argument("--tasq", "-t", action="store_true", help="Start TasQ server")


@Cli.command("run", _runParserSetup, help="Run the REST API")
def cliRun(args):
    cli = args._cli
    if cli.mode == "adhoc":
        raise CliError("Cannot run in adhoc mode")
    from tools import config
    error = config.validate()
    if error:
        cli.print(cli.col("Invalid configuration found: "+error, "yellow" if args.no_config_check else "red"))
        if not args.no_config_check:
            return 1
    from tools.tasq import TasQServer
    if args.tasq:
        TasQServer.start()
    from api.core import API
    import endpoints
    import importlib
    for group in endpoints.__all__:
        importlib.import_module("endpoints."+group)
    API.run(host=args.ip, port=args.port, debug=args.debug)
    TasQServer.stop()


def _versionParserSetup(subp: ArgumentParser):
    subp.add_argument("--api", "-a", action="store_true", help="Print API version")
    subp.add_argument("--backend", "-b", action="store_true", help="Print Backend version")
    subp.add_argument("--combined", "-c", action="store_true", help="Print combined version")


@Cli.command("version", _versionParserSetup, help="Show version information")
def cliVersion(args):
    from api import backendVersion, apiVersion
    cli = args._cli
    if args.api:
        cli.print(apiVersion)
    if args.backend:
        cli.print(backendVersion)
    if args.combined or not any((args.api, args.backend, args.combined)):
        vdiff = int(backendVersion.rsplit(".", 1)[1])-int(apiVersion.rsplit(".", 1)[1])
        if vdiff == 0:
            cli.print(apiVersion)
        else:
            cli.print("{}{:+}".format(apiVersion, vdiff))


def _setupTaginfo(subp: ArgumentParser):
    tagID = subp.add_argument("tagID", nargs="+", help="Numeric tag ID in decimal or hexadecimal or tag name glob")
    tagID.completer = proptagCompleter


@Cli.command("taginfo", _setupTaginfo, help="Print information about proptags")
def cliTaginfo(args):
    def printTag(ID):
        propname = PropTags.lookup(ID, "unknown")
        typename = PropTypes.lookup(ID, "unknown")
        proptype = cli.col("{:04x}".format(ID % (1 << 16)), attrs=["dark"])
        cli.print("0x{:04x}{} ({}): {}, type {}".format(ID >> 16, proptype, ID, propname, typename))

    cli = args._cli
    from tools.constants import PropTags, PropTypes
    PropTags.lookup(0)
    for tagid in args.tagID:
        if "*" in tagid or "?" in tagid:
            import fnmatch
            import re
            pattern = re.compile(fnmatch.translate(tagid.upper()))
            for ID, name in PropTags._lookup.items():
                if isinstance(ID, int) and pattern.match(name):
                    printTag(ID)
            continue
        try:
            ID = int(tagid, 0)
        except Exception:
            ID = getattr(PropTags, tagid.upper(), None)
            if ID is None or type(ID) != int:
                cli.print("Unknown tag '{}'".format(tagid))
                continue
        printTag(ID)


def _setupCliShell(subp: ArgumentParser):
    subp.description = "Start shell to process multiple CLI calls in a single session"
    subp.add_argument("-d", "--debug", action="store_true", help="Print more information")
    subp.add_argument("-x", "--exit", action="store_true", help="Exit on error")
    subp.add_argument("-n", "--no-history", action="store_true", help="Disable typed history")


def _historyDir():
    import os
    filePath = os.environ.get("XDG_CONFIG_HOME") or os.environ.get("HOME")+"/.config"
    return filePath+"/grommunio-admin"


def _loadHistory(args):
    cli = args._cli
    import os
    import readline
    if not args.no_history:
        filePath = os.path.expanduser("~/.grommunio-admin.history")
        try:
            readline.read_history_file(filePath)
            if args.debug:
                cli.print(cli.col("Loaded {} history entries".format(readline.get_current_history_length()), attrs=["dark"]))
            os.unlink(filePath)
            return
        except Exception as err:
            if args.debug:
                cli.print(cli.col("Failed to read legacy history file '{}': {}"
                                  .format(filePath, type(err).__name__ + " - ".join(str(arg) for arg in err.args)),
                                  attrs=["dark"]))
        filePath = _historyDir()+"/history"
        try:
            readline.read_history_file(filePath)
            if args.debug:
                cli.print(cli.col("Loaded {} history entries".format(readline.get_current_history_length()), attrs=["dark"]))
        except Exception as err:
            if args.debug:
                cli.print(cli.col("Failed to read history file '{}': {}"
                                  .format(filePath, type(err).__name__ + " - ".join(str(arg) for arg in err.args)),
                                  attrs=["dark"]))

def eof_instructions(fd):
	try:
		key = termios.tcgetattr(fd)[6][termios.VEOF]
		if ord(key) == 0:
			return ""
		if ord(key) < 32:
			return " or press CTRL+" + chr(ord(key) + ord('@'))
		return " or press '" + key.decode(locale.getpreferredencoding()) + "'"
	except:
		return ""

@Cli.command("shell", _setupCliShell, help="Start interactive shell")
def cliShell(args):
    cli = args._cli

    def rlEnable(state):
        if rlAvail:
            readline.set_completer(cli.complete if state else lambda *args: None)
            readline.set_auto_history(state)

    if cli.stdin is None:
        cli.print(cli.col("No input available - aborting", "red"))
        return -1

    import shlex
    import sys
    from services import ServiceUnavailableError
    rlAvail = False
    interactive = cli.stdin.isatty()
    if interactive:
        cli.print("\x1b]2;grommunio-admin\x07", end="")
        if cli.host is None:
            cli.print("grommunio-admin shell. Type `exit`" + eof_instructions(cli.stdin) + " to exit.")
        else:
            cli.print("Starting remote admin shell. Type `exit`" + eof_instructions(cli.stdin) + " to exit.")
        try:
            import readline
            readline.set_completer_delims("")
            readline.parse_and_bind("tab: complete")
            readline.set_history_length(1000)
            _loadHistory(args)
            rlAvail = True
        except Exception as err:
            if args.debug:
                cli.print(cli.col("Failed to initialize readline: "+type(err).__name__ +
                                  " - ".join(str(arg) for arg in err.args), attrs=["dark"]))
            cli.print("Install readline module to enable autocompletion")
    elif cli.mode == "standalone":
        cli.print(cli.col("WARNING: The CLI is still under development and subject to changes."
                          " Be careful when using scripts.\n", "yellow"), file=sys.stderr)
    try:
        while True:
            rlEnable(True)
            try:
                prompt = ""
                if interactive:
                    prompt += cli.col("grommunio-admin", "cyan", attrs=["bold", "dark"])
                    prompt += "@"+cli.col(cli.host, "red", attrs=["bold", "dark"]) if cli.host is not None else ""
                    prompt += "> "
                command = cli.input(prompt).strip()
            except KeyboardInterrupt:
                cli.print("^C")
                continue
            if command == "":
                continue
            elif command == "exit":
                break
            try:
                rlEnable(False)
                result = cli.execute(shlex.split(command), secure=False) or 0
                if result != 0 and args.exit:
                    return result
            except SystemExit:
                pass
            except KeyboardInterrupt:
                cli.print("^C")
                continue
            except EOFError:
                raise
            except ServiceUnavailableError as err:
                cli.print(cli.col(err.args[0], "red"))
            except BaseException as err:
                if isinstance(err, AttributeError) and "_argcomplete_namespace" in err.args[0]:
                    continue
                if args.debug:
                    import traceback
                    cli.print(cli.col(traceback.format_exc(), attrs=["dark"]))
                cli.print(cli.col("An exception occurred ({}): {}".format(type(err).__name__,
                                                                         " - ".join(str(arg) for arg in err.args)),
                                  "red"))
    except EOFError:
        cli.print()
    if rlAvail and not args.no_history:
        try:
            import os
            filePath = _historyDir()
            os.makedirs(filePath, exist_ok=True)
            readline.write_history_file(filePath+"/history")
        except Exception as err:
            if args.debug:
                cli.print(cli.col("Failed to write history file: "+type(err).__name__ +
                                  " - ".join(str(arg) for arg in err.args), attrs=["dark"]))


@Cli.command("shrek")
def cliShrek(args):
    cli = args._cli
    cli.print(cli.col("⢀⡴⠑⡄⠀⠀⠀⠀⠀⠀⠀⣀⣀⣤⣤⣤⣀⡀\n"
                      "⠸⡇⠀⠿⡀⠀⠀⠀⣀⡴⢿⣿⣿⣿⣿⣿⣿⣿⣷⣦⡀\n"
                      "⠀⠀⠀⠀⠑⢄⣠⠾⠁⣀⣄⡈⠙⣿⣿⣿⣿⣿⣿⣿⣿⣆\n"
                      "⠀⠀⠀⠀⢀⡀⠁⠀⠀⠈⠙⠛⠂⠈⣿⣿⣿⣿⣿⠿⡿⢿⣆\n"
                      "⠀⠀⠀⢀⡾⣁⣀⠀⠴⠂⠙⣗⡀⠀⢻⣿⣿⠭⢤⣴⣦⣤⣹⠀⠀⠀⢀⢴⣶⣆\n"
                      "⠀⠀⢀⣾⣿⣿⣿⣷⣮⣽⣾⣿⣥⣴⣿⣿⡿⢂⠔⢚⡿⢿⣿⣦⣴⣾⠁⠸⣼⡿\n"
                      "⠀⢀⡞⠁⠙⠻⠿⠟⠉⠀⠛⢹⣿⣿⣿⣿⣿⣌⢤⣼⣿⣾⣿⡟⠉\n"
                      "⠀⣾⣷⣶⠇⠀⠀⣤⣄⣀⡀⠈⠻⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇\n"
                      "⠀⠉⠈⠉⠀⠀⢦⡈⢻⣿⣿⣿⣶⣶⣶⣶⣤⣽⡹⣿⣿⣿⣿⡇\n"
                      "⠀⠀⠀⠀⠀⠀⠀⠉⠲⣽⡻⢿⣿⣿⣿⣿⣿⣿⣷⣜⣿⣿⣿⡇\n"
                      "⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⣷⣶⣮⣭⣽⣿⣿⣿⣿⣿⣿⣿\n"
                      "⠀⠀⠀⠀⠀⠀⣀⣀⣈⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠇\n"
                      "⠀⠀⠀⠀⠀⠀⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠃\n"
                      "⠀⠀⠀⠀⠀⠀⠀⠹⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠟⠁\n"
                      "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠛⠻⠿⠿⠿⠿⠛⠉", "green"))
