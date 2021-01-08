# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grammm GmbH

from flask import jsonify, request

import api
from api.core import API, secure
from api.security import loginUser, refreshToken
from orm import DB


@API.route(api.BaseRoute+"/status", methods=["GET"])
@secure(requireAuth=False)
def chkState():
    """Check status of the API."""
    if DB is None:
        return jsonify(message="Online, but database is not configured")
    return jsonify(message="API is operational")


@API.route(api.BaseRoute+"/about", methods=["GET"])
@secure(requireAuth=False)
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
    capabilities = tuple(user.permissions().capabilities())
    return jsonify(user=user.fulldesc(), capabilities=capabilities)


@API.route(api.BaseRoute+"/passwd", methods=["PUT"])
@secure(authLevel="user")
def updatePassword():
    user = request.auth["user"]
    if user.ldapImported:
        return jsonify(message="Cannot modify LDAP imported user"), 400
    data = request.get_json(silent=True)
    if data is None or "new" not in data or "old" not in data:
        return jsonify(message="Incomplete data"), 400
    if not user.chkPw(data["old"]):
        return jsonify(message="Old password does not match"), 403
    user.password = data["new"]
    DB.session.commit()
    return jsonify(message="Password updated")
