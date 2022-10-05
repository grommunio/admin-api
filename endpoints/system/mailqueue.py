# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2022 grommunio GmbH

import json
import subprocess

from flask import jsonify, request

import api

from api.core import API, secure
from api.security import checkPermissions
from tools.permissions import SystemAdminROPermission, SystemAdminPermission


@API.route(api.BaseRoute+"/system/mailq", methods=["GET"])
@secure()
def getMailqData():
    checkPermissions(SystemAdminROPermission())
    try:
        postfixMailq = subprocess.run("mailq", stdout=subprocess.PIPE, universal_newlines=True).stdout
    except Exception as err:
        API.logger.error("Failed to run mailq: {} ({})"
                         .format(type(err).__name__, " - ".join(str(arg) for arg in err.args)))
        postfixMailq = "Failed to run mailq."
    try:
        gromoxMailq = subprocess.run("gromox-mailq", stdout=subprocess.PIPE, universal_newlines=True).stdout
    except Exception as err:
        API.logger.error("Failed to run gromox-mailq: {} ({})"
                         .format(type(err).__name__, " - ".join(str(arg) for arg in err.args)))
        gromoxMailq = ""
    try:
        postqueue = subprocess.run(["postqueue", "-j"], stdout=subprocess.PIPE, universal_newlines=True).stdout
        postqueue = [json.loads(line) for line in postqueue.split("\n") if line]
    except Exception as err:
        API.logger.error("Failed to run postqueue: {} ({})"
                         .format(type(err).__name__, " - ".join(str(arg) for arg in err.args)))
        postqueue = []
    return jsonify(postfixMailq=postfixMailq, gromoxMailq=gromoxMailq, postqueue=postqueue)


@API.route(api.BaseRoute+"/system/mailq/flush", methods=["POST"])
@secure()
def flushMailq():
    checkPermissions(SystemAdminPermission())
    if "queue" not in request.args:
        return jsonify(message="Missing queue parameter"), 400
    from subprocess import PIPE
    target = request.args.get("queue")
    result = subprocess.run(["postqueue", "-i", target], stdout=PIPE, stderr=PIPE, universal_newlines=True)
    log = API.logger.warning if result.returncode else API.logger.info
    if result.stdout:
        log("Postqueue (out): "+result.stdout)
    if result.stderr:
        log("Postqueue (err): "+result.stderr)
    if result.returncode:
        return jsonify(message="Call to postqueue failed ({})".format(result.returncode)), 500
    return jsonify(message="Success")


def postsuper(op):
    from subprocess import PIPE
    targets = request.args.get("queue", "ALL").split(",")
    command = ["sudo", "postsuper"]+[t for param in ((op, target) for target in targets) for t in param]
    result = subprocess.run(command, stdout=PIPE, stderr=PIPE, universal_newlines=True)
    log = API.logger.warning if result.returncode else API.logger.info
    if result.stdout:
        log("Postsuper (out): "+result.stdout)
    if result.stderr:
        log("Postsuper (err): "+result.stderr)
    return result


@API.route(api.BaseRoute+"/system/mailq/delete", methods=["POST"])
@secure()
def deleteMailq():
    checkPermissions(SystemAdminPermission())
    result = postsuper("-d")
    if result.returncode:
        return jsonify(message="Call to postsuper failed ({})".format(result.returncode)), 500
    return jsonify(message="Success")


@API.route(api.BaseRoute+"/system/mailq/requeue", methods=["POST"])
@secure()
def requeueMailq():
    checkPermissions(SystemAdminPermission())
    result = postsuper("-r")
    if result.returncode:
        return jsonify(message="Call to postsuper failed ({})".format(result.returncode)), 500
    return jsonify(message="Success")
