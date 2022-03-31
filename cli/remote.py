# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH


from cli import Cli, ArgumentParser


def _tryConnect(args, target):
    import requests
    cli = args._cli
    if args.verbose >= 1:
        cli.print("Trying '{}'...".format(target), end="")
    try:
        response = requests.get(target+"/api/v1/status", **args._cparm)
        if response.status_code != 200:
            if args.verbose >= 1:
                cli.print()
            return "Received unexpected response code {} from '{}', check if server is ok..."\
                .format(response.status_code, target)
        else:
            if args.verbose >= 1:
                cli.print(cli.col("success.", "green"))
            return 0
    except Exception as err:
        if args.verbose >= 1:
            cli.print(cli.col("connect failed ({})".format(type(err).__name__), "yellow"))
        return 1


def _getConnection(args):
    import re
    urlre = re.compile(r"^(?P<proto>https?://)?(?P<host>(([\w\.-]+)|(\[[:\da-fA-F]+\])))(:(?P<port>\d{1,5}))?$")
    url = urlre.match(args.host or "localhost")
    if url is None:
        return False, "Invalid host"
    host = url["host"]
    port = url["port"]
    if url["proto"] is None:
        for proto, defaultPort in (("https://", 8443), ("http://", 8080)):
            target = "{}{}:{}".format(proto, host, port or defaultPort)
            res = _tryConnect(args, target)
            if res == 0:
                port = port or defaultPort
                break
            elif res == 1:
                pass
            else:
                return False, res
        else:
            return False, "Failed to connect to server"
    else:
        proto = url["proto"]
        port = port or (8443 if proto == "https://" else 8080)
        target = "{}{}:{}".format(proto, host, port)
        res = _tryConnect(args, target)
        if res == 0:
            pass
        elif res == 1:
            return False, "Failed to connect to server"
        else:
            return False, res
    target = "{}{}:{}/api/v1/".format(proto, host, port)
    return True, (target, host, proto)


def _login(target, host, args):
    def debugout(*argv, **kwargs):
        if args.verbose >= 1:
            cli.print(*argv, **kwargs)

    import requests
    import urllib
    cli = args._cli
    user = args.user or "admin"
    if not args.password and host == "localhost" and not args.passwd:
        from api.security import mkJWT
        debugout("Attempting passwordless login...", end="", flush=True)
        try:
            token = mkJWT({"usr": user})
            code, response = _remoteExec(None, target, token, "version", cparm=args._cparm)
            if code == 200:
                debugout(cli.col("success.", "green"))
                return True, token
            debugout(cli.col("failed.", "yellow"))
        except Exception:
            debugout(cli.col("error.", "red"))
    try:
        passwd = args.passwd or cli.input("Password: ", secret=True)
        data = urllib.parse.urlencode({"user": user, "pass": passwd})
        response = requests.post(target+"login", data, headers={"Content-Type": "application/x-www-form-urlencoded"},
                                 **args._cparm)
        data = response.json() or {}
        if response.status_code != 200:
            return False, "{}{}".format(data.get("message", "Login failed"), ": "+data["error"] if "error" in data else "")
        if "grommunioAuthJwt" not in data:
            return False, "Login failed: invalid response"
        token = data["grommunioAuthJwt"]
        code, response = _remoteExec(None, target, token, "version", cparm=args._cparm)
        if code is None:
            return False, response
        if code == 404:
            return False, "Remote CLI not available on server"
        if code in (401, 403):
            return False, "Insufficient permissions to use remote CLI"
        if code != 200:
            if "message" in response:
                return False, "Remote execution failed: "+response["message"]
            return False, "Remote execution failed with code "+str(code)
        return True, token
    except Exception as err:
        return False, "Login failed ({})".format(type(err).__name__)


def _getPath(root, path):
    for part in path.split("."):
        root = root.get(part, {})
    return root if isinstance(root, str) else None

def _remoteExec(cli, target, token, command, mode="exec", redirectFs=False, cparm={}):
    import requests
    try:
        colored = cli.colored if cli is not None else False
        data = {"command": command, "mode": mode, "color": colored, "fs": {} if redirectFs else None}
        headers = {"Content-Type": "application/json"}
        response = requests.post(target+"system/cli", json=data, cookies={"grommunioAuthJwt": token}, headers=headers, **cparm)
        return response.status_code, response.json()
    except Exception as err:
        return None, "Remote execution failed ({})".format(type(err).__name__)


class RemoteCompleter:
    def __init__(self, cli, target, token):
        self.cli = cli
        self.target = target
        self.token = token
        self.cached = None
        self.completions = ()


    def rl_complete(self, text, state):
        """Provide completions from remote shell.

        Caches completions for the last query for consecutive calls with different states.

        Parameters
        ----------
        text : str
            Prefix to complete
        state : int
            Index of completion

        Returns
        -------
        str
            Completion according to state or None if completions are exhausted
        """
        if text != self.cached:
            code, data = _remoteExec(self.cli, self.target, self.token, text, mode="complete")
            self.completions = () if code != 200 or data is None or "completions" not in data else data["completions"]
            self.cached = text
        return None if state >= len(self.completions) else self.completions[state]


class RemoteCli(Cli):
    actionMap = {"discard": "d", "local": "s", "print": "V", "remote": "r"}

    def __init__(self, parent, target, token, host, redirectFs, autoSave, cparm):
        super().__init__("remote", fs=parent.fs, stdin=parent.stdin, stdout=parent.stdout, host=host, color=parent.colored)
        self.completer = RemoteCompleter(self, target, token)
        self.__target = target
        self.__token = token
        self.__parent = parent
        self.__cparm = cparm
        self.__redirectFs = redirectFs
        self.__autoSave = autoSave

    def _receiveFiles(self, fs):
        if fs is None:
            return
        for path, file in fs.items():
            mode = file.get("mode", "w")
            conf = file.get("conf")
            content = file.get("content", b"" if "b" in mode else "")
            while True:
                self.print("Received {}file {}".format("binary " if "b" in mode else "", self.col(path, attrs=["bold"])))
                if conf is not None:
                    from tools.config import Config
                    local = _getPath(Config, conf) or path
                else:
                    local = path
                if self.__autoSave is None or self.__autoSave not in self.actionMap:
                    choices = ["s", "d", "w"]
                    if local != path:
                        self.print("Remote path was '{}', but local path would be '{}' (according to {})"\
                                   .format(self.col(path, "red"), self.col(local, "yellow"), conf))
                        prompt = "{}, {}, (d)iscard, (v)iew, (w)rite to custom path"\
                                  .format(self.col("(s)ave to local path", "green"), self.col("save to (r)emote path", "yellow"))
                        choices.append("r")
                    else:
                        prompt = "(s)ave, (d)iscard, (w)rite to custom path"
                    if "b" not in mode:
                        prompt += ", (v)iew"
                        choices.append("v")
                    action = self.choice(prompt+"? [d]: ", choices, default="d")
                else:
                    action = self.actionMap[self.__autoSave]
                if action is None:
                    return
                if action == "s":
                    writePath = local
                elif action == "d":
                    self.print("File discarded")
                    break
                elif action == "w":
                    try:
                        writePath = self.input("Write file to: ")
                    except KeyboardInterrupt:
                        self.print("File discarded")
                        break
                elif action in ("v", "V"):
                    self.print(self.col(content, attrs=["bold"]))
                    if action == "V":
                        break
                    continue
                elif action == "r":
                    writePath = path
                if action in ("s", "w", "r"):
                    try:
                        with self.open(writePath, mode) as outfile:
                            outfile.write(file.get("content", ""))
                        self.print("File saved")
                        break
                    except Exception as err:
                        self.print(self.col("Failed to write file: "+" - ".join(str(arg) for arg in err.args), "yellow"))

    def _execute(self, command):
        code, data = _remoteExec(self, self.__target, self.__token, command, redirectFs=self.__redirectFs, cparm=self.__cparm)
        if code is None:
            self.print(self.col(data, "red"))
            return 100
        if not isinstance(data, dict):
            data = {}
        if code != 200:
            self.print(self.col("Remote execution failed: "+data.get("message", "unknown error "+str(code)), "red"))
            return 101
        if "code" not in data or "stdout" not in data:
            self.print(self.col("The server returned an invalid response"))
            return 102
        self.print(data["stdout"], end="")
        self._receiveFiles(data.get("fs"))
        return data["code"]

    def execute(self, args, **kwargs):
        """Remote CLI execution override

        Forwards the command to the remote CLI and parses the response.

        Parameters
        ----------
        args : string or iterable
            Command line arguments, either as single string or split into individual parts
        **kwargs : any
            ignored.

        Returns
        -------
        int
            Execution return code
        """
        import shlex
        args = args if isinstance(args, str) else " ".join(shlex.quote(arg) for arg in args)
        return self._execute(args)

    def shell(self):
        """Alias for original Cli.execute(["shell"]).

        Returns
        -------
        int
            Return code of shell execution
        """
        return super().execute(["shell"])


def _cliRemoteSetupParser(subp: ArgumentParser):
    subp.add_argument("host", nargs="?", help="Host to connect to (default 'localhost')")
    subp.add_argument("user", nargs="?", help="User to connect with (default 'admin')")
    subp.add_argument("passwd", nargs="?", help="User password (default is to prompt)")
    subp.add_argument("--auto-save", choices=("local", "remote", "discard", "print"),
                      help="Automatically perform selected action when receiving files, instead of prompting")
    subp.add_argument("-c", "--command", help="Run command and exit (instead of starting shell)")
    subp.add_argument("--no-verify", action="store_true", help="Skip certificate verification")
    subp.add_argument("-p", "--password", action="store_true", help="Prompt for password even when connecting to localhost")
    subp.add_argument("--redirect-fs", action="store_true", help="Emulate CLI initiated read/write operations")
    subp.add_argument("-v", "--verbose", default=0, action="count", help="Print more information")


@Cli.command("connect", _cliRemoteSetupParser, help="Connect to a remote shell")
def cliRemote(args):
    cli = args._cli
    args._cparm = {}
    if args.no_verify:
        import urllib3
        import warnings
        warnings.filterwarnings("ignore", "", urllib3.exceptions.InsecureRequestWarning, "", 0)
        args._cparm["verify"] = False
    success, result = _getConnection(args)
    if not success:
        cli.print(cli.col(result, "red"))
        return 1
    target, host, proto = result
    if proto == "http://":
        cli.print(cli.col("Using insecure HTTP connection", "yellow"))
    success, result = _login(target, host, args)
    if not success:
        cli.print(cli.col(result, "red"))
        return 2
    token = result

    remoteCli = RemoteCli(cli, target, token, host, args.redirect_fs, args.auto_save, args._cparm)
    if args.command:
        return remoteCli.execute(args.command)
    return remoteCli.shell()
