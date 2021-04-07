# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grammm GmbH

import api
from api.core import API, secure
from api.security import checkPermissions

from tools.config import Config
from tools.license import getLicense, updateCertificate
from tools.permissions import SystemAdminPermission
from tools.systemd import Systemd

import os
import psutil
import requests
from datetime import datetime
from dbus import DBusException
from flask import jsonify, make_response, request

from orm import DB
if DB is not None:
    from orm.users import Users


@API.route(api.BaseRoute+"/system/dashboard", methods=["GET"])
@secure()
def getDashboard():
    checkPermissions(SystemAdminPermission())
    disks = []
    for disk in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(disk.mountpoint)
            stat = {"percent": usage.percent, "total": usage.total, "used": usage.used, "free": usage.free}
            stat["device"] = disk.device
            stat["mountpoint"] = disk.mountpoint
            stat["filesystem"] = disk.fstype
            disks.append(stat)
        except:
            pass
    cpu = psutil.cpu_times_percent()
    cpuPercent = dict(user=cpu.user, system=cpu.system, io=cpu.iowait, interrupt=cpu.irq+cpu.softirq, steal=cpu.steal,
                      idle=cpu.idle)
    vm = psutil.virtual_memory()
    memory = dict(percent=vm.percent, total=vm.total, used=vm.used, buffer=vm.buffers, cache=vm.cached, free=vm.free,
                  available=vm.available)
    sm = psutil.swap_memory()
    swap = dict(percent=sm.percent, total=sm.total, used=sm.used, free=sm.free)
    return jsonify(disks=disks,
                   load=os.getloadavg(),
                   cpuPercent=cpuPercent,
                   memory=memory,
                   swap=swap,
                   booted=datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S"))


@API.route(api.BaseRoute+"/system/dashboard/services", methods=["GET"])
@secure()
def getDashboardServices():
    checkPermissions(SystemAdminPermission())
    if len(Config["options"]["dashboard"]["services"]) == 0:
        return jsonify(services=[])
    sysd = Systemd(system=True)
    services = []
    for service in Config["options"]["dashboard"]["services"]:
        try:
            unit = sysd.getService(service["unit"])
        except DBusException as err:
            API.logger.error("Could not retrieve info about '{}': {}".format(service["unit"], err.args[0]))
            unit = {"state": "error", "substate": "dbus error", "description": None, "since": None}
        unit["name"] = service.get("name", service["unit"].replace(".service", ""))
        unit["unit"] = service["unit"]
        services.append(unit)
    return jsonify(services=services)


@API.route(api.BaseRoute+"/system/dashboard/services/<unit>", methods=["GET"])
@secure()
def getDashboardService(unit):
    checkPermissions(SystemAdminPermission())
    for service in Config["options"]["dashboard"]["services"]:
        if service["unit"] == unit:
            break
    else:
        return jsonify(message="Unknown unit '{}'".format(unit)), 400
    sysd = Systemd(system=True)
    try:
        unit = sysd.getService(service["unit"])
    except DBusException as err:
        API.logger.error("Could not retrieve info about '{}': {}".format(service["unit"], err.args[0]))
        unit = {"state": "error", "substate": "dbus error", "description": None, "since": None}
    unit["name"] = service.get("name", service["unit"].replace(".service", ""))
    unit["unit"] = service["unit"]
    return jsonify(unit)


@API.route(api.BaseRoute+"/system/dashboard/services/<unit>/<action>", methods=["POST"])
@secure()
def signalDashboardService(unit, action):
    checkPermissions(SystemAdminPermission())
    if action == "start":
        command = Systemd.startService
    elif action == "stop":
        command = Systemd.stopService
    elif action == "restart":
        command = Systemd.restartService
    elif action == "reload":
        command = Systemd.reloadService
    else:
        return jsonify(message="Invalid action"), 400
    if unit not in (service["unit"] for service in Config["options"]["dashboard"]["services"]):
        return jsonify(message="Unknown unit '{}'".format(unit)), 400
    sysd = Systemd(system=True)
    try:
        result = command(sysd, unit)
    except DBusException as exc:
        errMsg = exc.args[0] if len(exc.args) > 0 else "Unknown "
        return jsonify(message="Could not {} unit '{}': {}".format(action, unit, )), 500
    return jsonify(message=result), 201 if result == "done" else 500


def dumpLicense():
    License = getLicense()
    return jsonify(product=License.product,
                   maxUsers=License.users,
                   notBefore=License.notBefore.strftime("%Y-%m-%d %H:%M:%S"),
                   notAfter=License.notAfter.strftime("%Y-%m-%d %H:%M:%S"),
                   currentUsers=Users.query.count(),
                   certificate="/api/v1/system/license/certificate.pem" if License.cert is not None else None)

@API.route(api.BaseRoute+"/system/license", methods=["GET"])
@secure()
def getLicenseInfo():
    checkPermissions(SystemAdminPermission())
    return dumpLicense()


@API.route(api.BaseRoute+"/system/license/certificate.pem", methods=["GET"])
@secure()
def getLicenseFile():
    checkPermissions(SystemAdminPermission())
    License = getLicense()
    if License.file is None:
        return jsonify(message="No license installed"), 404
    response = make_response(License.file)
    response.headers.set("Content-Type", "application/x-pem-file")
    return response


@API.route(api.BaseRoute+"/system/license", methods=["PUT"])
@secure()
def updateLicense():
    checkPermissions(SystemAdminPermission())
    error = updateCertificate(request.get_data())
    if error:
        return jsonify(message=error), 400
    return dumpLicense()


@API.route(api.BaseRoute+"/system/antispam/<path:path>", methods=["GET"])
@secure()
def rspamdProxy(path):
    checkPermissions(SystemAdminPermission())
    conf = Config["options"]
    if path not in conf.get("antispamEndpoints", ("stat", "graph", "errors")):
        return jsonify(message="Endpoint not allowed"), 403
    try:
        res = requests.get(conf.get("antispamUrl", "http://127.0.0.1:11334")+"/"+path, request.args, stream=True)
    except BaseException as err:
        API.logger.error(type(err).__name__+": "+" - ".join(str(arg) for arg in err.args))
        return jsonify(message="Failed to connect to antispam"), 503
    return res.raw.read(), res.status_code, res.headers.items()
