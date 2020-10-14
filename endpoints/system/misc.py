# -*- coding: utf-8 -*-
"""
Created on Tue Oct 13 18:06:51 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: Grammm GmbH, 2020
"""

import api
from api.core import API, secure
from api.security import checkPermissions

from tools.config import Config
from tools.permissions import SystemAdminPermission
from tools.systemd import Systemd

import os
import psutil
from datetime import datetime
from dbus import DBusException
from flask import jsonify


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
