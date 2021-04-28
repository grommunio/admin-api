# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grammm GmbH

import api
from api.core import API, secure
from api.security import checkPermissions

from datetime import datetime
from flask import jsonify, request

from tools.config import Config
from tools.logs import LogReader
from tools.permissions import SystemAdminPermission

@API.route(api.BaseRoute+"/system/logs", methods=["GET"])
@secure()
def getLogs():
    checkPermissions(SystemAdminPermission())
    return jsonify(data=sorted(Config["logs"]))


@API.route(api.BaseRoute+"/system/logs/<file>", methods=["GET"])
@secure()
def getLog(file):
    checkPermissions(SystemAdminPermission())
    log = Config["logs"].get(file)
    if log is None:
        return jsonify(message="Log file not found"), 404
    n = int(request.args.get("n", 10))
    skip = int(request.args.get("skip", 0))
    after = datetime.strptime(request.args["after"], "%Y-%m-%d %H:%M:%S.%f") if "after" in request.args else None
    return jsonify(data=LogReader.tail(log.get("format", "journald"), log["source"], n, skip, after))
