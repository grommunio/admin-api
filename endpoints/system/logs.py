# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH

import api
from api.core import API, secure
from api.security import checkPermissions

from datetime import datetime
from flask import jsonify, request
import psutil

from tools.config import Config
from tools.logs import LogReader
from tools.permissions import SystemAdminROPermission


@API.route(api.BaseRoute+"/system/logs", methods=["GET"])
@secure()
def getLogs():
    checkPermissions(SystemAdminROPermission())
    return jsonify(data=sorted(Config["logs"]))


@API.route(api.BaseRoute+"/system/logs/<file>", methods=["GET"])
@secure()
def getLog(file):
    checkPermissions(SystemAdminROPermission())
    log = Config["logs"].get(file)
    if log is None:
        return jsonify(message="Log file not found"), 404
    n = int(request.args.get("n", 10))
    skip = int(request.args.get("skip", 0))
    after = datetime.strptime(request.args["after"], "%Y-%m-%d %H:%M:%S.%f") if "after" in request.args else None
    return jsonify(data=LogReader.tail(log.get("format", "journald"), log["source"], n, skip, after))


@API.route(api.BaseRoute+"/system/updateLog/<int:pid>", methods=["GET"])
@secure()
def getUpdateLog(pid):
    checkPermissions(SystemAdminROPermission())
    log = []
    try:
        with open(Config["options"]["updateLogPath"], 'r') as file:
            log = [line.rstrip() for line in file]
    except Exception as err:
        log = ["Failed to check for updates."]
        API.logger.error("Failed to get update log:"+type(err).__name__+": "+" - ".join(str(arg) for arg in err.args))
    try:
        # Process exists
        proc = psutil.Process(pid)
        processRunning = proc.status() != psutil.STATUS_ZOMBIE
        if not processRunning:
            proc.wait()  # Retrieve process result to prevent zombie apocalypse
        return jsonify({"data": log, "processRunning": processRunning})
    except Exception:
        # Process doesn't exist
        return jsonify({"data": log, "processRunning": False})
