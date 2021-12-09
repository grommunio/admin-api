# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH

import api
from api.core import API, secure
from api.security import checkPermissions

from . import defaultListQuery

from flask import jsonify, request

from tools.permissions import DomainAdminROPermission, SystemAdminPermission, SystemAdminROPermission
from tools.tasq import TasQServer


@API.route(api.BaseRoute+"/tasq/status", methods=["GET"])
@secure(requireAuth=False)
def getTasQStatus():
    return jsonify(running=TasQServer.running(),
                   queued=TasQServer.queued(),
                   workers=TasQServer.workers())


@API.route(api.BaseRoute+"/tasq/start", methods=["POST"])
@secure()
def startTasQ():
    checkPermissions(SystemAdminPermission())
    TasQServer.start(int(request.args["procs"]) if "procs" in request.args else None)
    return jsonify(message="TasQ server started")


@API.route(api.BaseRoute+"/tasq/stop", methods=["POST"])
@secure()
def stopTasQ():
    checkPermissions(SystemAdminPermission())
    TasQServer.stop(float(request.args["timeout"]) if "timeout" in request.args else None)
    return jsonify(message="TasQ server stopped")


@API.route(api.BaseRoute+"/tasq/tasks", methods=["GET"])
@secure(requireDB=102, authLevel="user")
def getTasQTasks():
    from orm.misc import TasQ
    tasks = defaultListQuery(TasQ, result="list")
    userPerms = request.auth["user"].permissions()
    nofilter = SystemAdminROPermission() in userPerms
    verbosity = int(request.args.get("level", 1))
    data = [task.todict(verbosity) for task in tasks if nofilter or task.permission in userPerms]
    return jsonify(data=data)


@API.route(api.BaseRoute+"/tasq/tasks/<int:ID>", methods=["GET"])
@secure(requireDB=102, authLevel="user")
def getTasQTask(ID):
    from orm.misc import TasQ
    task = TasQ.query.filter(TasQ.ID == ID).first()
    if task is None:
        return jsonify(message="Task not found"), 404
    checkPermissions(task.permission)
    return jsonify(task.todict(int(request.args.get("level", 2))))


@API.route(api.BaseRoute+"/tasq/notify", methods=["POST"])
@secure(requireAuth=False)
def notifyTasQ():
    pulled = TasQServer.pull()
    return jsonify(message="Pulled {} task{} from the database".format(pulled, "" if pulled == 1 else "s"))
