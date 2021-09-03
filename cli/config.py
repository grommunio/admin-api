# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH

from . import Cli, ArgumentParser


class CTrace:
    UNUSED = 0
    USED = 1
    EXTENDED = 2
    SHADOWED = 3
    NOCHANGE = 4

    KEY = 0
    LIST = 1
    DICT = 2

    mark = ("x ", "+ ", "* ", "~ ")
    _style = ({"color": "red"},
              {"color": "green"},
              {"color": "yellow"},
              {"color": "white", "attrs": ["dark"]},
              {"color": "red", "attrs": ["dark"]})

    _fbStyle = {"attrs": ["dark"]}

    def __init__(self, value, filename=None):
        self.state = self.USED
        self.type = self.LIST if isinstance(value, list) else self.DICT if isinstance(value, dict) else self.KEY
        self.value = {key: CTrace(val, filename) for key, val in value.items()} if self.type == self.DICT else\
                     [(val, filename) for val in value] if self.type == self.LIST else value
        self.overwritten = []
        self.overwrites = False
        self.filename = filename

    def __contains__(self, key):
        """Check if trace contains a key (dot-notation supported)."""
        if key is None:
            return True
        if self.type != self.DICT:
            return False
        if "." in key:
            pre, post = key.split(".", 1)
            return pre in self.value and post in self.value[pre]
        return key in self.value

    def __getitem__(self, key):
        """Get trace by key (dot-notation supported)."""
        if key is None:
            return self
        if self.type != self.DICT:
            raise KeyError(key)
        if "." in key:
            pre, post = key.split(".", 1)
            return self.value[pre][post]
        return self.value[key]

    @property
    def style(self):
        """Generate style for file tracing."""
        st = dict(self._style[self.state])
        if self.overwrites:
            st["attrs"] = st.get("attrs", [])+["bold"]
        return st

    def fstyle(self, stylemap):
        """Generate style for key-tracing."""
        return {"attrs": ["bold"]} if self.overwritten and self.type in (self.DICT, self.LIST) else \
               stylemap.get(self.filename, self._fbStyle) if stylemap else self.style

    def update(self, file, entry):
        """Add future update to trace"""
        newstate = self.UNUSED if self.state == self.UNUSED or self.type != entry.type else\
                   self.EXTENDED if self.type in (self.LIST, self.DICT) and self.type == entry.type else\
                   self.SHADOWED if self.value == entry.value else self.UNUSED
        if self.type == self.DICT and self.state != self.UNUSED:
            for key, value in self.value.items():
                if newstate == self.UNUSED:
                    value.invalidate(file)
                elif key in entry.value:
                    value.update(file, entry.value[key])
        self.overwritten.append((file, self.NOCHANGE if self.state == newstate == self.UNUSED else newstate))
        self.state = newstate
        entry.overwrites = True

    def merge(self, entry):
        """Merge another trace into self."""
        file = entry.filename
        oldstate = self.EXTENDED if self.type in (self.LIST, self.DICT) and self.type == entry.type else\
                   self.SHADOWED if self.value == entry.value else self.UNUSED
        self.overwritten.append((self.filename or "default", oldstate))
        self.filename = file
        if self.type == entry.type and self.type in (self.DICT, self.LIST):
            if self.type == self.DICT:
                for key, value in entry.value.items():
                    if key in self.value:
                        self.value[key].merge(value)
                    else:
                        self.value[key] = value
            elif self.type == self.LIST:
                self.value += entry.value
        else:
            self.value = entry.value

    def printval(self, args, hist=0, indent=0, stylemap=None, prefix=0):
        """Print value of a trace."""
        cli = args._cli
        if hist == 0:
            ovstr = ""
        elif stylemap is None:
            ovstr = "["+", ".join(cli.col(ov[0], **self._style[ov[1]]) for ov in self.overwritten)+"]" \
                    if self.state != self.USED else ""
        elif args.show_history or self.type in (self.DICT, self.LIST):
            sfile = cli.col(self.filename, **stylemap.get(self.filename, self._fbStyle))
            if self.overwritten and self.type == self.KEY:
                sfile = cli.col(sfile, attrs=["underline"])
            ovstr = "["+", ".join(cli.col(ov[0], **stylemap.get(ov[0], self._fbStyle)) for ov in self.overwritten) +\
                    (", " if self.overwritten else "")+sfile+"]"
        else:
            ovstr = "["+cli.col(self.filename, **stylemap.get(self.filename, self._fbStyle))+"]"
        if self.type == self.LIST and len(self.value):
            lines = []
            for value, filename in self.value:
                style = stylemap.get(filename, self._fbStyle) if stylemap else\
                        {"color": "red" if self.state == self.UNUSED else "green"}
                data = "\n"+("" if stylemap else self.mark[self.state])+" "*(indent+3)+"- "
                ov = "["+cli.col(filename, **stylemap.get(filename, self._fbStyle))+"]" if stylemap else ""
                if isinstance(value, (dict, list)):
                    import yaml
                    mark = "" if stylemap else self.mark[self.state]
                    data = ["\n"+mark+" "*(indent+5)+rep for rep in yaml.dump(value).split("\n") if rep]
                    lines += [cli.col(line, **style)+" "*(hist-len(line)+1)+ov for line in data]
                else:
                    vstr = str(value)
                    lines.append(cli.col(data+str(value), **style)+(" "*(hist-len(data)-len(vstr)+1)+ov if stylemap else ""))
            return " "*(hist-prefix)+ovstr+"".join(lines)
        res = str(self.value) if self.type == self.KEY else "" if len(self.value) else "{}"
        post = " "*(hist-len(res)-prefix)+ovstr if hist and (self.state != self.USED or stylemap) else ""
        return cli.col(res, **self.fstyle(stylemap))+post

    def printFile(self, args, hist=0, indent=0):
        """Print trace in by-file style."""
        cli = args._cli
        if self.type == self.DICT:
            for key, value in self.value.items():
                base = self.mark[value.state]+" "*(indent+1)+key+": "
                cli.print(cli.col(base, **value.style), end="")
                cli.print(value.printval(args, hist, indent, prefix=len(base)))
                value.printFile(args, hist, indent+2)
        elif indent == 0:
            cli.print(self.printval(args, hist))

    def printConfig(self, args, hist, stylemap, indent=0):
        """Print trace in by-key style."""
        cli = args._cli
        if self.type == self.DICT:
            for key, value in self.value.items():
                base = " "*(indent)+key+": "
                cli.print(cli.col(base, **value.fstyle(stylemap)), end="")
                cli.print(value.printval(args, hist, indent, stylemap, len(base)))
                value.printConfig(args, hist, stylemap, indent+2)
        elif indent == 0:
            cli.print(self.printval(args, hist, 0, stylemap))

    def inlwidth(self):
        """Return inline value print width."""
        return 0 if self.type in (self.LIST, self.DICT) and len(self.value) else len(str(self.value))+1

    def maxwidth(self, indent=0):
        """Return maximum line width when printing."""
        if self.type == self.DICT:
            if len(self.value):
                return max(max(len(key)+1+value.inlwidth() for key, value in self.value.items())+indent,
                           max(value.maxwidth(indent+2) for value in self.value.values()))
        elif self.type == self.LIST and len(self.value):
            import yaml
            return max(len(self.mark[self.state]+" "*(indent+2)+rep) for rep in yaml.dump(self.value).split("\n") if rep)
        return len(str(self.value)) if indent == 0 else 0


def cliConfigCheck(args):
    from tools.config import validate
    cli = args._cli
    result = validate()
    if result is None:
        cli.print("Configuration schema valid")
        return 0
    else:
        cli.print(cli.col(result, "red"))
        return 1


def cliConfigGet(args):
    from tools.config import Config
    from .common import getKey, NotFound
    keyspec = getattr(args, "key", "")
    c = getKey(Config, keyspec.split("."))
    if isinstance(c, NotFound):
        rep = "\n"
    elif isinstance(c, (dict, list)):
        import yaml
        rep = yaml.dump(c)
    else:
        rep = str(c)
    args._cli.print(rep)


def _traceFiles(args):
    import yaml
    from os import scandir
    from tools.config import _defaultConfig
    cli = args._cli
    defaultConfig = _defaultConfig()
    files = [("default", CTrace(defaultConfig))]
    try:
        with open("config.yaml") as file:
            fconf = yaml.load(file, Loader=yaml.SafeLoader)
    except Exception as err:
        cli.print(cli.col("Failed to open main config file: "+" - ".join(str(arg) for arg in err.args), "yellow"))
        return 1
    upd = CTrace(fconf)
    files[0][1].update("./config.yaml", upd)
    files.append(("./config.yaml", upd))
    confdir = fconf.get("confdir")
    if not confdir:
        return files, confdir
    configFiles = sorted([file.path for file in scandir(confdir) if file.name.endswith(".yaml")])
    for configFile in configFiles:
        try:
            with open(configFile) as file:
                fconf = yaml.load(file, Loader=yaml.SafeLoader)
            configFile = configFile.replace(confdir, "$CONFD")
            upd = CTrace(fconf)
            for old in files:
                old[1].update(configFile, upd)
            files.append((configFile, upd))
        except Exception as err:
            cli.print(cli.col("Failed to open '{}' config file: {}"
                              .format(configFile, " - ".join(str(arg) for arg in err.args)), "yellow"))
    return files, confdir


def _traceKeys(args):
    import yaml
    from os import scandir
    from tools.config import _defaultConfig
    cli = args._cli
    config = CTrace(_defaultConfig(), "default")
    try:
        with open("config.yaml") as file:
            fconf = yaml.load(file, Loader=yaml.SafeLoader)
    except Exception as err:
        cli.print(cli.col("Failed to open main config file: "+" - ".join(str(arg) for arg in err.args), "yellow"))
        return 1
    config.merge(CTrace(fconf, "./config.yaml"))
    confdir = fconf.get("confdir")
    if not confdir:
        return config, []
    configFiles = sorted([file.path for file in scandir(confdir) if file.name.endswith(".yaml")])
    for configFile in configFiles:
        try:
            with open(configFile) as file:
                fconf = yaml.load(file, Loader=yaml.SafeLoader)
            configFile = configFile.replace(confdir, "$CONFD")
            upd = CTrace(fconf, configFile)
            config.merge(upd)
        except Exception as err:
            cli.print(cli.col("Failed to open '{}' config file: {}"
                              .format(configFile, " - ".join(str(arg) for arg in err.args)), "yellow"))
    return config, [configFile.replace(confdir, "$CONFD") for configFile in configFiles]


def _printByFile(args):
    cli = args._cli
    files, confdir = _traceFiles(args)
    files = [f for f in files if args.key in f[1]]
    if len(files) == 0:
        cli.print(cli.col("No matching files", "yellow"))
        return
    if any(f[0].startswith("$CONFD") for f in files):
        cli.print("Note: $CONFD evaluates to '{}'\n".format(cli.col(confdir, attrs=["underline"])))
    hist = max(f[1][args.key].maxwidth() for f in files if args.key in f[1])+4 if args.show_history and len(files) else 0
    for file in files:
        cli.print("<"+cli.col(file[0], attrs=["bold"])+">")
        file[1][args.key].printFile(args, hist)
        cli.print()


def _printByKey(args):
    cli = args._cli
    from itertools import cycle, product
    config, files = _traceKeys(args)
    hist = config[args.key].maxwidth()+4 if args.key in config else 0
    colors = ("yellow", "green", "red", "cyan", "magenta")
    attrs = [[("dark", "bold", "underline")[i] for i in (0, 1, 2) if index & (1 << i)] for index in range(8)]
    styles = {filename: {"color": style[1], "attrs": style[0]}
              for filename, style in zip(files, cycle(product(attrs, colors)))}
    styles["default"] = styles["./config.yaml"] = {}
    if len(files):
        cli.print("Configuration resulting from " +
                  ", ".join(cli.col(file, **styles.get(file, {"attrs": ["dark"]})) for file in files)+".\n" +
                  "$CONFD evaluates to '{}'".format(cli.col(config["confdir"].value, attrs=["underline"]))+".\n")
    if args.key in config:
        config[args.key].printConfig(args, hist, styles)
    else:
        cli.print(cli.col("'{}' not found.".format(args.key), "yellow"))


def cliConfigTrace(args):
    return (_printByFile if args.mode == "files" else _printByKey)(args)


def _configKeyspecCompleter(prefix, **kwargs):
    from tools.config import Config
    from .common import getKey
    split = prefix.split(".")
    path, prefix = split[:-1], split[-1]
    parent = getKey(Config, path)
    if isinstance(parent, dict):
        path = ".".join(path)+"." if path else ""
        return list(path+key for key in parent.keys())
    return ()


def _setupCliConfigParser(subp: ArgumentParser):
    sub = subp.add_subparsers()
    check = sub.add_parser("check", help="Check if configuration is valid")
    check.set_defaults(_handle=cliConfigCheck)
    get = sub.add_parser("get", help="Print configuration values to stdout", aliases=["dump"])
    get.set_defaults(_handle=cliConfigGet)
    get.add_argument("key", nargs="?", default="", help="Configuration key to print").completer = _configKeyspecCompleter
    trace = sub.add_parser("trace", help="Analyse where effective configuration values are set")
    trace.set_defaults(_handle=cliConfigTrace)
    trace.add_argument("mode", choices=("files", "values"), help="Display trace by file or by key")
    trace.add_argument("key", nargs="?", help="Only show trace for specific key").completer = _configKeyspecCompleter
    trace.add_argument("-s", "--show-history", action="store_true", help="Show which files overwrite a value")


@Cli.command("config", _setupCliConfigParser, help="Show or check configuration")
def cliConfigStub(args):
    pass
