# -*- coding: utf-8 -*-
"""
Created on Tue Jun 23 11:26:12 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: Grammm GmbH, 2020
"""

import dbus
import psutil
import os

from datetime import datetime
from dbus import DBusException

from flask import jsonify, request

import api
from api.core import API, secure
from api.security import loginUser, refreshToken, checkPermissions
from orm import DB

from . import defaultListHandler, defaultObjectHandler

from tools.config import Config
from tools.systemd import Systemd
from tools.permissions import SystemAdminPermission

if DB is not None:
    from orm.misc import Forwards, MLists, Associations, Classes, Hierarchy, Members, Specifieds

@API.route(api.BaseRoute+"/status", methods=["GET"])
@secure(requireAuth=False)
def chkState():
    """Check status of the API."""
    if DB is None:
        return jsonify(message="Online, but database is not configured")
    return jsonify(message="API is operational")


@API.route(api.BaseRoute+"/about", methods=["GET"])
@secure()
def getAbout(requireAuth=False):
    """Retrieve version information."""
    return jsonify(API=api.apiVersion, backend=api.backendVersion)


@API.route(api.BaseRoute+"/login", methods=["POST"])
@secure(requireAuth=False)
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
@secure(authLevel="user")
def getProfile():
    user = request.auth["user"]
    userData = {"username": user.username, "realName": user.realName}
    capabilities = tuple(user.permissions().capabilities())
    return jsonify(user=userData, capabilities=capabilities)
