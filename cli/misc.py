# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grammm GmbH

from . import Cli, ArgumentParser


def _runParserSetup(subp: ArgumentParser):
    subp.add_argument("--ip", "-i", default="0.0.0.0", type=str, help="Host address to bind to")
    subp.add_argument("--port", "-p", default=5001, type=int, help="Host port to bind to")
    subp.add_argument("--debug", "-d", action="store_true", help="Run in debug mode")
    subp.add_argument("--no-config-check", action="store_true", help="Skip configuration check")


@Cli.command("run", _runParserSetup)
def cliRun(args):
    if not args.no_config_check:
        from tools import config
        error = config.validate()
        if error:
            print("Invalid configuration found: "+error)
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


@Cli.command("version", _versionParserSetup)
def cliVersion(args):
    from api import backendVersion, apiVersion
    if args.api:
        print(apiVersion)
    if args.backend:
        print(backendVersion)
    if args.combined or not any((args.api, args.backend, args.combined)):
        vdiff = int(backendVersion.rsplit(".", 1)[1])-int(apiVersion.rsplit(".", 1)[1])
        if vdiff == 0:
            print(apiVersion)
        else:
            print("{}{:+}".format(apiVersion, vdiff))


def _cliConfigCheck(args):
    from tools.config import validate
    result = validate()
    if result is None:
        print("Configuration schema valid")
        return 0
    else:
        print("Error: "+result)
        return 1


def _cliConfigDump(args):
    from tools.config import Config
    import yaml
    print(yaml.dump(Config))


def _setupCliConfigParser(subp: ArgumentParser):
    sub = subp.add_subparsers()
    check = sub.add_parser("check")
    check.set_defaults(_handle=_cliConfigCheck)
    dump = sub.add_parser("dump")
    dump.set_defaults(_handle=_cliConfigDump)


@Cli.command("config", _setupCliConfigParser)
def cliConfigStub(args):
    pass


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


@Cli.command("taginfo", _setupTaginfo)
def cliTaginfo(args):
    from tools.constants import PropTags, PropTypes
    for tagid in args.tagID:
        try:
            ID = int(tagid, 0)
        except:
            ID = getattr(PropTags, tagid.upper(), None)
            if ID is None or type(ID) != int:
                print("Unknown tag '{}'".format(tagid))
                continue
        propname = PropTags.lookup(ID, "unknown")
        proptype = PropTypes.lookup(ID, "unknown")
        print("0x{:x} ({}): {}, type {}".format(ID, ID, propname, proptype))


def _setupCliShell(subp: ArgumentParser):
    subp.description = "Start shell to process multiple CLI calls in a single session"
    subp.add_argument("-x", "--exit", action="store_true", help="Exit on error")


@Cli.command("shell", _setupCliShell)
def cliShell(args):
    def rlEnable(state):
        if Cli.rlAvail:
            readline.set_completer(completer.rl_complete if state else lambda *args: None)
            readline.set_auto_history(state)

    import shlex
    import sys
    Cli.interactive = sys.stdin.isatty()
    if Cli.interactive:
        print("\x1b]2;grammm-admin\x07", end="")
        print("grammm-admin shell. Type exit or press CTRL+D to exit.")
        try:
            import readline
            import argcomplete
            completer = argcomplete.CompletionFinder(Cli.parser, always_complete_options=False)
            readline.set_completer_delims("")
            readline.set_completer(completer.rl_complete)
            readline.parse_and_bind("tab: complete")
            readline.set_history_length(100)
            Cli.rlAvail = True
        except:
            print("Install readline module to enable autocompletion")
    try:
        while True:
            rlEnable(True)
            try:
                command = input(Cli.col("grammm-admin", "cyan", attrs=["dark", "bold"])+"> " if Cli.interactive else "").strip()
            except KeyboardInterrupt:
                print("^C")
                continue
            if command == "":
                continue
            elif command == "exit":
                break
            try:
                rlEnable(False)
                result = Cli.execute(shlex.split(command)) or 0
                if result != 0 and args.exit:
                    return result
            except SystemExit:
                pass
            except AttributeError as err:
                print(Cli.col("Caught AttributeError: "+"-".join(str(arg) for arg in err.args), "blue", attrs=["dark"]))
            except BaseException as err:
                print(Cli.col("An exception occured ({}): {}".format(sys.last_type, "-".join(str(arg) for arg in err.args)),
                              "red"))
    except EOFError:
        print()


@Cli.command("moo")
def cliMoo(args):
    print('                 (__)\n'
          '                 (oo)\n'
          '           /------\\/\n'
          '          / |    ||\\\n'
          '         *  /\\---/\\\n'
          '            ~~   ~~\n'
          '..."Have you mooed today?"...')
