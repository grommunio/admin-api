# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH

from . import Cli, CliError, ArgumentParser


def _runParserSetup(subp: ArgumentParser):
    subp.add_argument("--ip", "-i", default="0.0.0.0", type=str, help="Host address to bind to")
    subp.add_argument("--port", "-p", default=5001, type=int, help="Host port to bind to")
    subp.add_argument("--debug", "-d", action="store_true", help="Run in debug mode")
    subp.add_argument("--no-config-check", action="store_true", help="Skip configuration check")


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
    from api.core import API
    import endpoints
    import importlib
    for group in endpoints.__all__:
        importlib.import_module("endpoints."+group)
    API.run(host=args.ip, port=args.port, debug=args.debug)


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


def _cliTaginfoCompleter(prefix, **kwargs):
    from tools.constants import PropTags
    PropTags.lookup(None)
    c = []
    if prefix == "" or prefix[0].islower():
        c += [tag.lower() for value, tag in PropTags._lookup.items() if isinstance(value, int)]
    if prefix == "" or prefix[0].isupper():
        c += [tag.upper() for value, tag in PropTags._lookup.items() if isinstance(value, int)]
    if prefix == "" or prefix[0] == "0" and (len(prefix) <= 2 or not prefix[2:].isupper()):
        c += ["0x{:08x}".format(value) for value in PropTags._lookup.keys() if isinstance(value, int)]
    if prefix == "" or prefix[0] == "0" and (len(prefix) <= 2 or not prefix[2:].islower()):
        c += ["0x{:08X}".format(value) for value in PropTags._lookup.keys() if isinstance(value, int)]
    if prefix == "" or prefix.isnumeric():
        c += [str(value) for value in PropTags._lookup.keys() if isinstance(value, int)]
    return c


def _setupTaginfo(subp: ArgumentParser):
    tagID = subp.add_argument("tagID", nargs="+", help="Numeric tag ID in decimal or hexadecimal or tag name")
    tagID.completer = _cliTaginfoCompleter


@Cli.command("taginfo", _setupTaginfo, help="Print information about proptags")
def cliTaginfo(args):
    cli = args._cli
    from tools.constants import PropTags, PropTypes
    for tagid in args.tagID:
        try:
            ID = int(tagid, 0)
        except:
            ID = getattr(PropTags, tagid.upper(), None)
            if ID is None or type(ID) != int:
                cli.print("Unknown tag '{}'".format(tagid))
                continue
        propname = PropTags.lookup(ID, "unknown")
        typename = PropTypes.lookup(ID, "unknown")
        proptype = cli.col("{:04x}".format(ID%(1<<16)), attrs=["dark"])
        cli.print("0x{:04x}{} ({}): {}, type {}".format(ID>>16, proptype, ID, propname, typename))


def _setupCliShell(subp: ArgumentParser):
    subp.description = "Start shell to process multiple CLI calls in a single session"
    subp.add_argument("-d", "--debug", action="store_true", help="Print more information")
    subp.add_argument("-n", "--no-history", action="store_true", help="Disable typed history")
    subp.add_argument("-x", "--exit", action="store_true", help="Exit on error")


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
            cli.print("grommunio-admin shell. Type exit or press CTRL+D to exit.")
        else:
            cli.print("Starting remote admin shell. Type exit or press CTRL+D to exit.")
        try:
            import readline
            readline.set_completer_delims("")
            readline.parse_and_bind("tab: complete")
            readline.set_history_length(1000)
            if not args.no_history:
                try:
                    import os
                    readline.read_history_file(os.path.expanduser("~/.grommunio-admin.history"))
                    if args.debug:
                        cli.print(cli.col("Loaded {} history entries".format(readline.get_current_history_length()), attrs=["dark"]))
                except Exception as err:
                    if args.debug:
                        cli.print(cli.col("Failed to read history file: "+type(err).__name__+
                                          " - ".join(str(arg) for arg in err.args), attrs=["dark"]))
            rlAvail = True
        except Exception as err:
            if args.debug:
                cli.print(cli.col("Failed to initialize readline: "+type(err).__name__+
                                  " - ".join(str(arg) for arg in err.args), attrs=["dark"]))
            cli.print("Install readline module to enable autocompletion")
    elif cli.mode == "standalone":
        cli.print(cli.col("WARNING: The CLI is still under development and subject to changes. Be careful when using scripts.\n",
                          "yellow"), file=sys.stderr)
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
                if args.debug:
                    import traceback
                    cli.print(cli.col(traceback.format_exc(), attrs=["dark"]))
                cli.print(cli.col("An exception occured ({}): {}".format(type(err).__name__,
                                                                         " - ".join(str(arg) for arg in err.args)),
                                  "red"))
    except EOFError:
        cli.print()
    if rlAvail and not args.no_history:
        try:
            import os
            readline.write_history_file(os.path.expanduser("~/.grommunio-admin.history"))
        except Exception as err:
            if args.debug:
                cli.print(cli.col("Failed to write history file: "+type(err).__name__+
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
