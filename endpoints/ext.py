# -*- coding: utf-8 -*-
"""
Created on Thu Jun 25 17:07:58 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: Grammm GmbH, 2020
"""

from flask import request, jsonify

import api
from api import API

from . import defaultListHandler, defaultObjectHandler

from orm import DB
if DB is not None:
    from orm.ext import AreaList


@API.route(api.BaseRoute+"/area_list", methods=["GET", "POST"])
@api.secure(requireDB=True)
def areaListListEndpoint():
    if request.method == "GET":
        areaList = defaultListHandler(AreaList, result="list")
        return jsonify(user=[area.fulldesc() for area in areaList if area.dataType == AreaList.USER],
                       domain=[area.fulldesc() for area in areaList if area.dataType == AreaList.DOMAIN],
                       independent=[area.fulldesc() for area in areaList if area.dataType == AreaList.INDEPENDENT])
    else:
        return defaultListHandler(AreaList)

@API.route(api.BaseRoute+"/area_list/<int:ID>", methods=["GET", "PATCH", "DELETE"])
@api.secure(requireDB=True)
def areaListObjectEndpoint(ID):
    return defaultObjectHandler(AreaList, ID, "List entry")
