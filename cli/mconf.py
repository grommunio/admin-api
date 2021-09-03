# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH


from argparse import ArgumentParser

from . import Cli

_configs = ("authmgr", "ldap")


def _getConfig(cli, name):
    if name not in _configs:
        cli.print(cli.col("Unknown config '{}'".format(name), "red"))
        return None
    from tools import mconf
    if name == "authmgr":
        return mconf.AUTHMGR
    elif name == "ldap":
        return mconf.LDAP


def _cliMconfPrint(args):
    cli = args._cli
    config = _getConfig(cli, args.config)
    if config is None:
        return 1
    import yaml
    data = yaml.dump(config)
    cli.print(data, end="" if data.endswith("\n") else "\n")


def _cliMconfDump(args):
    cli = args._cli
    from tools import mconf
    if args.config == "authmgr":
        mconf.dumpAuthmgr(file=cli.stdout)
    elif args.config == "ldap":
        mconf.dumpLdap(file=cli.stdout)
    else:
        cli = cli.print(cli.col("Invalid config", "red"))
        return 1


def _getValue(args):
    if args.int:
        return int(args.value, 0)
    elif args.bool:
        if args.value.lower() not in ("y", "n", "yes", "no", "true", "false", "1", "0"):
            raise ValueError("invalid boolean value '{}'".format(args.value))
        return args.value.lower() in ("y", "yes", "true", "1")
    else:
        return args.value


def _cliMconfReload(args):
    cli = args._cli
    from tools import mconf
    if args.config == "authmgr":
        error = mconf.loadAuthmgr()
    elif args.config == "ldap":
        error = mconf.loadLdap()
    else:
        cli.print(cli.col("Unknown config '{}'".format(args.config), "red"))
        return 1
    if error:
        cli.print(cli.col("Could not load {} config: {}".format(args.config, error), "yellow"))
        return 2


def _cliMconfSave(args):
    cli = args._cli
    from tools import mconf
    try:
        if args.config == "authmgr":
            error = mconf.dumpAuthmgr(file=cli.open("mconf.authmgrPath", "w", cli.fs is None))
        elif args.config == "ldap":
            error = mconf.dumpLdap(file=cli.open("mconf.ldapPath", "w", cli.fs is None))
        else:
            cli.print(cli.col("Unknown config '{}'".format(args.config), "red"))
            return 1
    except KeyError as err:
        error = err.args[0]
    except Exception as err:
        error = " - ".join((str(arg) for arg in err.args))
    cli.print("Configuration saved" if error is None else cli.col("Failed to save configuration: "+error, "yellow"))


def _cliMconfModify(args):
    cli = args._cli
    config = _getConfig(cli, args.config)
    if config is None:
        return 1
    if "." in args.key:
        path, var = args.key.rsplit(".", 1)
        parent = config
        for level in path.split("."):
            if level not in parent:
                parent[level] = {}
            elif not isinstance(parent[level], dict):
                cli.print(cli.col("'{}': invalid path".format(args.key), "red"))
                return 2
            parent = parent[level]
    else:
        parent, var = config, args.key
    if args.action in ("set", "add", "remove"):
        try:
            value = _getValue(args)
        except ValueError as err:
            cli.print(cli.col(err.args[0], "red"))
            return 3
    if args.action == "set":
        parent[var] = value
    elif args.action == "unset":
        parent.pop(var, None)
    elif args.action == "add":
        target = parent.get(var)
        if target is None:
            parent[var] = target = []
        elif not isinstance(target, list):
            cli.print(cli.col("Cannot add value: '{}' is not an array".format(var), "red"))
            return 4
        target.append(value)
    elif args.action == "remove":
        target = parent.get(var)
        if not isinstance(target, list):
            cli.print(cli.col("Cannot remove value: '{}' is not an array".format(var), "red"))
            return 4
        try:
            target.remove(value)
        except ValueError:
            cli.print(cli.col("Value {} not found in '{}'".format(value, var), "red"))
            return 5
    if not args.defer:
        _cliMconfSave(args)


def _mconfKeyCompleter(prefix, parsed_args, **kwargs):
    from .common import getKey
    config = _getConfig(None, parsed_args.config)
    if config is None:
        return ()
    split = prefix.split(".")
    path, prefix = split[:-1], split[-1]
    parent = getKey(config, path)
    if isinstance(parent, dict):
        path = ".".join(path)+"." if path else ""
        return list(path+key for key in parent.keys()
                    if parsed_args.action not in ("add", "remove") or isinstance(parent[key], (list, dict)))
    return ()


def _setupCliMconfAddValue(parser: ArgumentParser):
    typearg = parser.add_mutually_exclusive_group()
    typearg.add_argument("-i", "--int", action="store_true", help="Cast value to integer")
    typearg.add_argument("-b", "--bool", action="store_true", help="Cast value to boolean")
    parser.add_argument("value")


def _setupCliMconf(subp: ArgumentParser):
    sub = subp.add_subparsers()
    dump = sub.add_parser("dump", help="Dump configuration file to stdout")
    dump.set_defaults(_handle=_cliMconfDump)
    dump.add_argument("config", choices=_configs)
    modify = sub.add_parser("modify", help="Modify configuration")
    modify.set_defaults(_handle=_cliMconfModify)
    modify.add_argument("config", choices=_configs)
    modify.add_argument("-d", "--defer", action="store_true", help="Do not write changes to disk")
    modifysub = modify.add_subparsers()
    modifyadd = modifysub.add_parser("add", help="Add value to configuration list")
    modifyadd.set_defaults(action="add")
    modifyadd.add_argument("key").completer = _mconfKeyCompleter
    _setupCliMconfAddValue(modifyadd)
    modifyremove = modifysub.add_parser("remove", help="Remove value from configuration list")
    modifyremove.set_defaults(action="remove")
    modifyremove.add_argument("key").completer = _mconfKeyCompleter
    _setupCliMconfAddValue(modifyremove)
    modifyset = modifysub.add_parser("set", help="Set configuration value")
    modifyset.set_defaults(action="set")
    modifyset.add_argument("key").completer = _mconfKeyCompleter
    _setupCliMconfAddValue(modifyset)
    modifyunset = modifysub.add_parser("unset", help="Unset configuration value")
    modifyunset.set_defaults(action="unset")
    modifyunset.add_argument("key").completer = _mconfKeyCompleter
    printConf = sub.add_parser("print", help="Show configuration")
    printConf.set_defaults(_handle=_cliMconfPrint)
    printConf.help = "Print current configuration"
    printConf.add_argument("config", choices=_configs)
    reload = sub.add_parser("reload", help="Reload configuration")
    reload.set_defaults(_handle=_cliMconfReload)
    reload.help = "Reload configuration from disk"
    reload.add_argument("config", choices=_configs)
    save = sub.add_parser("save", help="Write configuration to disk")
    save.set_defaults(_handle=_cliMconfSave)
    save.add_argument("config", choices=_configs)


@Cli.command("mconf", _setupCliMconf, help="Managed configurations manipulation")
def cliMconfStub():
    pass
