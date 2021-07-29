# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH

import subprocess
import time

from datetime import datetime

class Systemd:
    valmap = {"ActiveState": "state",
              "SubState": "substate",
              "UnitFileState": "autostart",
              "Description": "description",
              "ActiveEnterTimestampMonotonic": "sa",
              "InactiveEnterTimestampMonotonic": "si",
              "Names": "unit"}

    def __init__(self, system=False):
        self.__system = system

    @property
    def __mode(self):
        return "--system" if self.__system else "--user"

    def getServices(self, *services):
        args = ("systemctl", self.__mode, "show",
                "--property="+",".join(self.valmap), *services)
        print(args)
        result = subprocess.run(args, stdout=subprocess.PIPE, universal_newlines=True)
        split = [[line.split("=", 1) for line in block.split("\n") if "=" in line] for block in result.stdout.split("\n\n")]
        units = [{self.valmap[key]: value for key, value in block if key in self.valmap} for block in split]
        for unit in units:
            since = unit["sa"] if unit["state"] == "active" else unit["si"]
            try:
                since = time.clock_gettime(time.CLOCK_REALTIME)-time.clock_gettime(time.CLOCK_MONOTONIC)+int(since)/1000000
                since = datetime.fromtimestamp(int(since)).strftime("%Y-%m-%d %H:%M:%S") if since != 0 else None
            except Exception as err:
                print(type(err).__name__, " - ".join(str(arg) for arg in err.args))
                since = None
            unit["since"] = since
            unit.pop("sa", None), unit.pop("si", None)
        return {unit["unit"]: unit for unit in units if "unit" in unit}

    def run(self, command, *targets):
        try:
            result = subprocess.run(("systemctl", self.__mode, command, *targets),
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
            return result.returncode, result.stdout
        except Exception as err:
            return -1, type(err).__name__+" - ".join(str(arg) for arg in err)

    def startService(self, *services):
        return self.run("start", *services)

    def stopService(self, *services):
        return self.run("stop", *services)

    def restartService(self, *services):
        return self.run("restart", *services)

    def reloadService(self, *services):
        return self.run("reload", *services)

    def tryReloadRestartService(self, *services):
        return self.run("try-reload-or-restart", *services)

    def enableService(self, *services):
        return self.run("enable", *services)

    def disableService(self, *services):
        return self.run("disable", *services)
