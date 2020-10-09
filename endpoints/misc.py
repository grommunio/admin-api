# -*- coding: utf-8 -*-
"""
Created on Tue Jun 23 11:26:12 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: _Placeholder_copyright_
"""

import dbus
import psutil
import os

from datetime import datetime
from dbus import DBusException

from flask import jsonify, request

from api import API
from api.security import loginUser, refreshToken, checkPermissions
import api
from orm import DB

from . import defaultListHandler, defaultObjectHandler

from tools.config import Config
from tools.systemd import Systemd
from tools.permissions import SystemAdminPermission

if DB is not None:
    from orm.misc import Forwards, MLists, Associations, Classes, Hierarchy, Members, Specifieds

@API.route(api.BaseRoute+"/status", methods=["GET"])
@api.secure(requireAuth=False)
def chkState():
    """Check status of the API."""
    if DB is None:
        return jsonify(message="Online, but database is not configured")
    return jsonify(message="API is operational")


@API.route(api.BaseRoute+"/about", methods=["GET"])
@api.secure()
def getAbout(requireAuth=False):
    """Retrieve version information."""
    return jsonify(API=api.apiVersion, backend=api.backendVersion)


@API.route(api.BaseRoute+"/forwards", methods=["GET", "POST"])
@api.secure(requireDB=True)
def forwardListEndpoint():
    return defaultListHandler(Forwards)


@API.route(api.BaseRoute+"/forwards/<int:ID>", methods=["GET", "PATCH", "DELETE"])
@api.secure(requireDB=True)
def forwardObjectEndpoint(ID):
    return defaultObjectHandler(Forwards, ID, "Forward")


@API.route(api.BaseRoute+"/mlists", methods=["GET", "POST"])
@api.secure(requireDB=True)
def mlistListEndpoint():
    return defaultListHandler(MLists)


@API.route(api.BaseRoute+"/mlists/<int:ID>", methods=["GET", "PATCH", "DELETE"])
@api.secure(requireDB=True)
def mlistObjectEndpoint(ID):
    return defaultObjectHandler(MLists, ID, "MList")


@API.route(api.BaseRoute+"/associations", methods=["GET", "POST"])
@api.secure(requireDB=True)
def associationListEndpoint():
    return defaultListHandler(Associations)


@API.route(api.BaseRoute+"/association/<int:ID>", methods=["GET", "PATCH", "DELETE"])
@api.secure(requireDB=True)
def associationObjectEndpoint(ID):
    return defaultObjectHandler(Associations, ID, "Association")


@API.route(api.BaseRoute+"/classes", methods=["GET", "POST"])
@api.secure(requireDB=True)
def classListEndpoint():
    return defaultListHandler(Classes)


@API.route(api.BaseRoute+"/classes/<int:ID>", methods=["GET", "PATCH", "DELETE"])
@api.secure(requireDB=True)
def classObjectEndpoint(ID):
    return defaultObjectHandler(Classes, ID, "Class")


@API.route(api.BaseRoute+"/hierarchy", methods=["GET", "POST"])
@api.secure(requireDB=True)
def hierarchyListEndpoint():
    return defaultListHandler(Hierarchy)


@API.route(api.BaseRoute+"/hierarchy/<int:ID>", methods=["GET", "PATCH", "DELETE"])
@api.secure(requireDB=True)
def hierarchyObjectEndpoint(ID):
    return defaultObjectHandler(Hierarchy, ID, "Hierarchy")


@API.route(api.BaseRoute+"/members", methods=["GET", "POST"])
@api.secure(requireDB=True)
def memberListEndpoint():
    return defaultListHandler(Members)


@API.route(api.BaseRoute+"/members/<int:ID>", methods=["GET", "PATCH", "DELETE"])
@api.secure(requireDB=True)
def memberObjectEndpoint(ID):
    return defaultObjectHandler(Members, ID, "Members")


@API.route(api.BaseRoute+"/specifieds", methods=["GET", "POST"])
@api.secure(requireDB=True)
def specifiedListEndpoint():
    return defaultListHandler(Specifieds)


@API.route(api.BaseRoute+"/specifieds/<int:ID>", methods=["GET", "PATCH", "DELETE"])
@api.secure(requireDB=True)
def speciedObjectEndpoint(ID):
    return defaultObjectHandler(Specifieds, ID, "Specified")


@API.route(api.BaseRoute+"/system/dashboard", methods=["GET"])
@api.secure()
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
@api.secure()
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
@api.secure()
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
@api.secure()
def signalDashboardService(unit, action):
    checkPermissions(SystemAdminPermission())
    if action == "start":
        command = Systemd.startService
    elif action == "stop":
        command = Systemd.stopService
    elif action == "restart":
        command = Systemd.restartService
    else:
        return jsonify(message="Invalid action"), 400
    if unit not in (service["unit"] for service in Config["options"]["dashboard"]["services"]):
        return jsonify(message="Unknown unit '{}'".format(unit)), 400
    sysd = Systemd(system=True)
    try:
        result = command(sysd, unit)
    except dbus.DBusException as exc:
        errMsg = exc.args[0] if len(exc.args) > 0 else "Unknown "
        return jsonify(message="Could not {} unit '{}': {}".format(action, unit, )), 500
    return jsonify(message=result), 201 if result == "done" else 500


@API.route(api.BaseRoute+"/login", methods=["POST"])
@api.secure(requireAuth=False)
def login():
    if "user" not in request.form or "pass" not in request.form:
        refreshed = refreshToken()
        if refreshed is not None:
            return jsonify(grammmAuthJwt=refreshed.decode("ascii"))
        return jsonify(message="Incomplete login form"), 400
    success, val = loginUser(request.form["user"], request.form["pass"])
    if not success:
        return jsonify(message="Login failed", error=val), 401
    return jsonify({"grammmAuthJwt": val.decode("ascii")})


@API.route(api.BaseRoute+"/profile", methods=["GET"])
@api.secure(authLevel="user")
def getProfile():
    user = request.auth["user"]
    userData = {"username": user.username, "realName": user.realName}
    capabilities = tuple(user.permissions().capabilities())
    return jsonify(user=userData, capabilities=capabilities)
