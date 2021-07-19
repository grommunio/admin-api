# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH

from flask import request, jsonify

import api
from api.core import API, secure
from api.security import checkPermissions

from tools import dbconf
from tools.permissions import SystemAdminPermission, SystemAdminROPermission

from orm import DB

@API.route(api.BaseRoute+"/system/dbconf/", methods=["GET"])
@secure(requireDB=True)
def getDbconfServices():
    checkPermissions(SystemAdminROPermission())
    from orm.misc import DBConf
    data = [entry[0] for entry in DBConf.query.with_entities(DBConf.service.distinct()).order_by(DBConf.service)]
    return jsonify(data=data)


@API.route(api.BaseRoute+"/system/dbconf/<service>/", methods=["GET"])
@secure(requireDB=True)
def getDbconfFiles(service):
    checkPermissions(SystemAdminROPermission())
    from orm.misc import DBConf
    data = [entry[0] for entry in DBConf.query.filter(DBConf.service == service)
                                              .with_entities(DBConf.file.distinct())
                                              .order_by(DBConf.file)]
    return jsonify(data=data)


@API.route(api.BaseRoute+"/system/dbconf/<service>/", methods=["PATCH"])
@secure(requireDB=True)
def renameDbconfService(service):
    checkPermissions(SystemAdminPermission())
    from orm.misc import DBConf
    data = request.get_json(silent=True)
    if data is None or "name" not in data:
        return jsonify(message="Missing or incomplete data"), 400
    count = DBConf.query.filter(DBConf.service == service).update({DBConf.service: data["name"]})
    if count == 0:
        DB.session.rollback()
        return jsonify(message="Service not found"), 404
    DB.session.commit()
    return jsonify(message="Success.")


@API.route(api.BaseRoute+"/system/dbconf/<service>/", methods=["DELETE"])
@secure(requireDB=True)
def deleteDbconfService(service):
    checkPermissions(SystemAdminPermission())
    from orm.misc import DBConf
    count = DBConf.query.filter(DBConf.service == service).delete()
    if count == 0:
        DB.session.rollback()
        return jsonify(message="Service not found"), 404
    DB.session.commit()
    return jsonify(message="Service deleted")


@API.route(api.BaseRoute+"/system/dbconf/<service>/<file>/", methods=["PUT", "PATCH"])
@secure(requireDB=True)
def updateDbconfFile(service, file):
    checkPermissions(SystemAdminPermission())
    from orm.misc import DBConf
    data = request.get_json(silent=True)
    if data is None:
        return jsonify(message="Missing data"), 400
    if "data" in data:
        conf = data["data"]
        if request.method == "PUT":
            DBConf.query.filter(DBConf.service == service, DBConf.file == file).delete()
        else:
            existing = DBConf.query.filter(DBConf.service == service, DBConf.file == file, DBConf.key.in_(conf)).all()
            for entry in existing:
                entry.value = conf.pop(entry.key)
        DB.session.add_all(DBConf(service=service, file=file, key=key, value=value) for key, value in conf.items())
    if "name" in data:
        count = DBConf.query.filter(DBConf.service == service, DBConf.file == file).update({DBConf.file: data["name"]})
        if count == 0:
            DB.session.rollback()
            return jsonify(message="File not found"), 404
    DB.session.commit()
    error = dbconf.commit(service, file)
    if error is None:
        return jsonify(message="Success.")
    return jsonify(message="Configuration updated but commit failed ({})".format(error))


@API.route(api.BaseRoute+"/system/dbconf/<service>/<file>/", methods=["DELETE"])
@secure(requireDB=True)
def deleteDbconfFile(service, file):
    checkPermissions(SystemAdminPermission())
    from orm.misc import DBConf
    count = DBConf.query.filter(DBConf.service == service, DBConf.file == file).delete()
    if count == 0:
        return jsonify(message="File not found"), 404
    DB.session.commit()
    return jsonify(message="File deleted")


@API.route(api.BaseRoute+"/system/dbconf/<service>/<file>/", methods=["GET"])
@secure(requireDB=True)
def getDbconfFile(service, file):
    checkPermissions(SystemAdminROPermission())
    from orm.misc import DBConf
    data = {entry.key: entry.value for entry in DBConf.query.filter(DBConf.service == service, DBConf.file == file)}
    return jsonify(data=data)


@API.route(api.BaseRoute+"/system/dbconf/commands", methods=["GET"])
@secure()
def getDbconfCommands():
    checkPermissions(SystemAdminROPermission())
    return jsonify(key=list(dbconf.keyCommits), file=list(dbconf.fileCommits), service=list(dbconf.serviceCommits))
