# -*- coding: utf-8 -*-
"""
Created on Thu Jun 25 17:07:58 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: Grammm GmbH, 2020
"""

from flask import request, jsonify
from sqlalchemy.exc import IntegrityError

import os

import api
from api import API

from . import defaultListHandler, defaultObjectHandler, defaultCreate

from tools import storage

from orm import DB

from orm import DB
if DB is not None:
    from orm.ext import AreaList


@API.route(api.BaseRoute+"/system/area_list", methods=["GET"])
@api.secure(requireDB=True)
def areaListGet():
    areaList = defaultListHandler(AreaList, result="list")
    return jsonify(user=[area.fulldesc() for area in areaList if area.dataType == AreaList.USER],
                   domain=[area.fulldesc() for area in areaList if area.dataType == AreaList.DOMAIN],
                   independent=[area.fulldesc() for area in areaList if area.dataType == AreaList.INDEPENDENT])


@API.route(api.BaseRoute+"/system/area_list", methods=["POST"])
@api.secure(requireDB=True)
def areaListCreate():
    area = defaultListHandler(AreaList, result="object")
    if not isinstance(area, AreaList):
        return area
    try:
        os.makedirs(area.masterPath)
        os.makedirs(area.slavePath)
        if area.accelPath is not None:
            os.makedirs(area.accelPath)
    except FileExistsError:
        return jsonify(message="Cannot create storage area: Directory exists."), 400
    except OSError as err:
        return jsonify(message="Cannot create storage area: " + " - ".join(str(arg) for arg in err.args))
    DB.session.add(area)
    try:
        DB.session.commit()
    except IntegrityError as err:
        DB.session.rollback()
        return jsonify(message="Object violates database constraints", error=err.orig.args[1]), 400
    return jsonify(area.fulldesc()), 201


@API.route(api.BaseRoute+"/system/area_list/<int:ID>", methods=["GET", "PATCH", "DELETE"])
@api.secure(requireDB=True)
def areaListObjectEndpoint(ID):
    return defaultObjectHandler(AreaList, ID, "List entry")
