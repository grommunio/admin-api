# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grommunio GmbH

import api
from api.core import API, secure
from api.security import checkPermissions

from .. import defaultListHandler, defaultObjectHandler

from cli import Cli

from services import Service

from tools.config import Config
from tools.license import getLicense, updateCertificate
from tools.permissions import SystemAdminPermission, SystemAdminROPermission
from tools.dnsHealth import getHostByName
from tools.misc import callUpdateScript

import json
import os
import psutil
import requests
import shlex
import time

from datetime import datetime
from flask import jsonify, make_response, request
from io import StringIO


@API.route(api.BaseRoute+"/system/dashboard", methods=["GET"])
@secure()
def getDashboard():
    checkPermissions(SystemAdminROPermission())
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
    checkPermissions(SystemAdminROPermission())
    known = {service["unit"]: service for service in Config["options"]["dashboard"]["services"]}
    if len(known) == 0:
        return jsonify(services=[])
    with Service("systemd") as sysd:
        units = [{"name": known.get("unit", {}).get("name") or unit["unit"].replace(".service", ""), **unit}
                 for unit in sysd.getServices(*known).values()]
        return jsonify(services=units)


@API.route(api.BaseRoute+"/system/dashboard/services/<unit>", methods=["GET"])
@secure()
def getDashboardService(unit):
    checkPermissions(SystemAdminROPermission())
    for service in Config["options"]["dashboard"]["services"]:
        if service["unit"] == unit:
            break
    else:
        return jsonify(message="Unknown unit '{}'".format(unit)), 400
    with Service("systemd") as sysd:
        unit = sysd.getServices(service["unit"])[service["unit"]]
        unit["name"] = service.get("name", service["unit"].replace(".service", ""))
        unit["unit"] = service["unit"]
        return jsonify(unit)


@API.route(api.BaseRoute+"/system/dashboard/services/<unit>/<action>", methods=["POST"])
@secure()
def signalDashboardService(unit, action):
    checkPermissions(SystemAdminPermission())
    if action not in ("start", "stop", "restart", "reload", "enable", "disable"):
        return jsonify(message="Invalid action"), 400
    if unit not in (service["unit"] for service in Config["options"]["dashboard"]["services"]):
        return jsonify(message="Unknown unit '{}'".format(unit)), 400
    with Service("systemd") as sysd:
        _, msg = sysd.run(action, unit)
        return jsonify(message=msg or "Success"), 500 if msg else 201


def dumpLicense():
    License = getLicense()
    try:
        from orm.users import Users
        currentUsers = Users.count()
    except:
        currentUsers = None
    return jsonify(product=License.product,
                   maxUsers=License.users,
                   notBefore=License.notBefore.strftime("%Y-%m-%d %H:%M:%S"),
                   notAfter=License.notAfter.strftime("%Y-%m-%d %H:%M:%S"),
                   currentUsers=currentUsers,
                   certificate="/api/v1/system/license/certificate.pem" if License.cert is not None else None)


@API.route(api.BaseRoute+"/system/license", methods=["GET"])
@secure()
def getLicenseInfo():
    checkPermissions(SystemAdminROPermission())
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


@API.route(api.BaseRoute+"/system/license/creds", methods=["GET"])
@secure()
def getLicenseSubscription():
    checkPermissions(SystemAdminPermission())
    try:
        with open(Config["options"]["subscriptionFile"]) as file:
            creds = file.readline()
        username, password = creds.split(":")
        return jsonify(username=username, password=password)
    except KeyError:
        return jsonify(message="Subscription detail storage path not configured"), 503
    except Exception:
        return jsonify(username=None, password=None)


@API.route(api.BaseRoute+"/system/license/creds", methods=["PUT"])
@secure()
def setLicenseSubscription():
    checkPermissions(SystemAdminPermission())
    data = request.get_json(silent=True)
    if data is None or "username" not in data or "password" not in data:
        return jsonify(message="Incomplete data"), 400
    try:
        with open(Config["options"]["subscriptionFile"], "w") as file:
            file.write(":".join((data["username"], data["password"])))

        # Fetch license from partner portal
        url = "https://portal.grommunio.com/api/v1/licenses/user/"
        body = { "password": data["password"] }
        response = requests.post(url + data["username"], json=body)
        updateCertificate(response.content)

        return jsonify(message="okidoki")
    except KeyError:
        return jsonify(message="Subscription detail storage path not configured"), 503
    except PermissionError as err:
        return jsonify(message="Could not save credentials: "+err.args[1]), 500
    except FileNotFoundError:
        return jsonify(message="Could not save credentials: no such file or directory"), 500
    except Exception as err:
        API.logger.error("Could not save credentials:"+type(err).__name__+": "+" - ".join(str(arg) for arg in err.args))
        return jsonify(message="Could not save credentials"), 500


@API.route(api.BaseRoute+"/system/antispam/<path:path>", methods=["GET"])
@secure()
def rspamdProxy(path):
    checkPermissions(SystemAdminROPermission())
    conf = Config["options"]
    if path not in conf["antispamEndpoints"]:
        return jsonify(message="Endpoint not allowed"), 403
    try:
        res = requests.get(conf["antispamUrl"]+"/"+path, request.args, stream=True)
    except BaseException as err:
        API.logger.error(type(err).__name__+": "+" - ".join(str(arg) for arg in err.args))
        return jsonify(message="Failed to connect to antispam"), 503
    return res.raw.read(), res.status_code, res.headers.items()


@API.route(api.BaseRoute+"/system/vhostStatus", methods=["GET"])
@secure()
def vhostStatusList():
    checkPermissions(SystemAdminROPermission())
    return jsonify(data=list(Config["options"].get("vhosts", {}).keys()))


@API.route(api.BaseRoute+"/system/vhostStatus/<path:host>", methods=["GET"])
@secure()
def vhostStatus(host):
    checkPermissions(SystemAdminROPermission())
    conf = Config["options"].get("vhosts", {})
    if host not in conf:
        return jsonify(message="VHost not found"), 404
    try:
        res = requests.get(conf[host], stream=True)
    except BaseException as err:
        API.logger.error(type(err).__name__+": "+" - ".join(str(arg) for arg in err.args))
        return jsonify(message="Failed to connect to vhost"), 503
    return res.raw.read(), res.status_code, res.headers.items()


@API.route(api.BaseRoute+"/system/cli", methods=["POST"])
@secure()
def cliOverRest():
    checkPermissions(SystemAdminPermission())
    if Config["options"].get("disableRemoteCli"):
        return jsonify(message="Remote CLI disabled by config"), 400
    params = request.get_json(silent=True)
    if params is None:
        return jsonify(message="Missing parameters"), 400
    if "command" not in params:
        return jsonify(message="Missing command"), 400
    mode = params.get("mode", "exec")
    stdout = StringIO()
    fs = params.get("fs")
    cli = Cli(mode="adhoc", stdin=None, stdout=stdout, color=params.get("color", False), fs=fs)
    if mode == "complete":
        return jsonify(completions=cli.complete(params["command"]))
    API.logger.info("Executing CLI command '{}'".format(params["command"]))
    result = 0
    try:
        result = cli.execute(shlex.split(params["command"]), secure=False)
    except SystemExit:
        pass
    except Exception as err:
        return jsonify(message="{} ({})".format(type(err).__name__, " - ".join(str(arg) for arg in err.args))), 500
    cli.closeFiles()
    return jsonify(code=result, stdout=stdout.getvalue(), fs=cli.fs)


@API.route(api.BaseRoute+"/system/sync/top", methods=["GET"])
@secure()
def syncTop():
    checkPermissions(SystemAdminROPermission())
    sync = Config["sync"]
    expUpd = sync.get("topExpireUpdate", 120)
    expEnd = sync.get("topExpireEnded", 20)
    fupd = int(request.args.get("filterUpdated", expUpd))
    fend = int(request.args.get("filterEnded", expEnd))
    now = int(time.mktime(time.localtime()))
    with Service("redis") as r:
        r.set(sync.get("topTimestampKey", "grommunio-sync:topenabledat"), now)
        hdata = r.hgetall(sync.get("topdataKey", "grommunio-sync:topdata"))
        if hdata is None:
            return jsonify(data=[], maxUpdated=expUpd, maxEnded=expEnd)
        data = []
        remove = []
        for key, value in hdata.items():
            try:
                value = json.loads(value)
                if (value["ended"] != 0 and now-value["ended"] > expEnd) or \
                   now-value["update"] > expUpd:
                    remove.append(key)
                elif not (value["ended"] != 0 and now-value["ended"] > fend or now-value["update"] > fupd):
                    data.append(value)
            except Exception as err:
                API.logger.warning(type(err).__name__+": "+str(err.args))
        if len(remove) > 0:
            r.hdel(sync.get("topdataKey", "grommunio-sync:topdata"), *remove)
    return jsonify(data=data)


@API.route(api.BaseRoute+"/system/servers", methods=["GET", "POST"])
@secure(requireDB=105)
def getServersList():
    checkPermissions(SystemAdminROPermission() if request.method == "GET" else SystemAdminPermission())
    from orm.misc import Servers
    return defaultListHandler(Servers)


@API.route(api.BaseRoute+"/system/servers/<int:ID>", methods=["GET", "PATCH", "DELETE"])
@secure(requireDB=105)
def getServerObject(ID):
    checkPermissions(SystemAdminROPermission() if request.method == "GET" else SystemAdminPermission())
    from orm.misc import Servers
    if request.method == "DELETE":
        server = Servers.query.filter(Servers.ID == ID).first()
        if server is not None and server.users+server.domains != 0:
            return jsonify(message="Cannot delete server with users or domains"), 400
    return defaultObjectHandler(Servers, ID, "")


@API.route(api.BaseRoute+"/system/servers/dnsCheck", methods=["GET"])
@secure(requireDB=105)
def getServersDNSChecks():
    checkPermissions(SystemAdminROPermission())
    from orm.misc import Servers
    objects = Servers.query.all()
    uniqueHostnames = [o.hostname for o in objects]
    uniqueExternalNames = set(o.extname for o in objects)

    hostsDNSCheck = {hostname: getHostByName(hostname) for hostname in uniqueHostnames}
    extDNSCheck = {extname: getHostByName(extname) for extname in uniqueExternalNames}

    return jsonify({"host": hostsDNSCheck, "ext": extDNSCheck})


@API.route(api.BaseRoute+"/system/updates/<string:command>", methods=["POST"])
@secure()
def checkForUpdates(command):
    repo = request.args["repo"] if "repo" in request.args else "supported"
    checkPermissions(SystemAdminPermission())
    pid = callUpdateScript(command or "check", repo)
    return jsonify({"pid": pid})
