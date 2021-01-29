# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grammm GmbH


from argparse import ArgumentParser

from . import Cli


_configs = ("ldap", )

def _getConfig(name):
    if name not in _configs:
        print("Unknown config '{}'".format(name))
        return None
    from tools import mconf
    if name == "ldap":
        return mconf.LDAP


def _cliMconfPrint(args):
    import yaml
    config = _getConfig(args.config)
    if config is None:
        return 1
    print(yaml.dump(config))


def _cliMconfDump(args):
    import sys
    from tools import mconf
    if args.config == "ldap":
        mconf.dumpLdap(file=sys.stdout)
    else:
        print("Invalid config")
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


def _cliMconfSave(args):
    from tools import mconf
    if args.config == "ldap":
        error = mconf.dumpLdap()
    else:
        print("Unknown config '{}'".format(args.config))
        return 1
    print("Configuration saved" if error is None else "Failed to save configuration: "+error)


def _cliMconfModify(args):
    config = _getConfig(args.config)
    if config is None:
        return 1
    if "." in args.key:
        path, var = args.key.rsplit(".", 1)
        parent = config
        for level in path.split("."):
            if level not in parent:
                parent[level] = {}
            elif not isinstance(parent[level], dict):
                print("'{}': invalid path".format(args.key))
                return 2
            parent = parent[level]
    else:
        parent, var = config, args.key
    if args.action in ("set", "add", "remove"):
        try:
            value = _getValue(args)
        except ValueError as err:
            print(err.args[0])
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
            print("Cannot add value: '{}' is not an array".format(var))
            return 4
        target.append(value)
    elif args.action == "remove":
        target = parent.get(var)
        if not isinstance(target, list):
            print("Cannot remove value: '{}' is not an array".format(var))
            return 4
        try:
            target.remove(value)
        except ValueError:
            print("Value {} not found in '{}'".format(value, var))
            return 5
    if not args.defer:
        _cliMconfSave(args)


def _setupCliMconfAddValue(parser: ArgumentParser):
    typearg = parser.add_mutually_exclusive_group()
    typearg.add_argument("-i", "--int", action="store_true", help="Cast value to integer")
    typearg.add_argument("-b", "--bool", action="store_true", help="Cast value to boolean")
    parser.add_argument("value")


def _setupCliMconf(subp: ArgumentParser):
    sub = subp.add_subparsers()
    printConf = sub.add_parser("print")
    printConf.set_defaults(_handle=_cliMconfPrint)
    printConf.help = "Print current configuration"
    printConf.add_argument("config", choices=_configs)
    dump = sub.add_parser("dump")
    dump.set_defaults(_handle=_cliMconfDump)
    dump.help = "Dump configuration file to stdout"
    dump.add_argument("config", choices=_configs)
    modify = sub.add_parser("modify")
    modify.set_defaults(_handle=_cliMconfModify)
    modify.add_argument("config", choices=_configs)
    modify.add_argument("-d", "--defer", action="store_true", help="Do not write changes to disk")
    modifysub = modify.add_subparsers()
    modifyset = modifysub.add_parser("set")
    modifyset.set_defaults(action="set")
    modifyset.add_argument("key")
    _setupCliMconfAddValue(modifyset)
    modifyunset = modifysub.add_parser("unset")
    modifyunset.set_defaults(action="unset")
    modifyunset.add_argument("key")
    modifyadd = modifysub.add_parser("add")
    modifyadd.set_defaults(action="add")
    modifyadd.add_argument("key")
    _setupCliMconfAddValue(modifyadd)
    modifyremove = modifysub.add_parser("remove")
    modifyremove.set_defaults(action="remove")
    modifyremove.add_argument("key")
    _setupCliMconfAddValue(modifyremove)
    save = sub.add_parser("save")
    save.set_defaults(_handle=_cliMconfSave)
    save.add_argument("config")


@Cli.command("mconf", _setupCliMconf)
def cliMconfStub():
    pass
