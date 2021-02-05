# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grammm GmbH

from flask import jsonify, request

import api
from api.core import API, secure
from api.security import loginUser, refreshToken, getSecurityContext
from orm import DB

from tools import ldap


@API.route(api.BaseRoute+"/status", methods=["GET"])
@secure(requireAuth=False)
def chkState():
    """Check status of the API."""
    return jsonify(message="API is operational",
                   database=DB is not None,
                   ldap=ldap.LDAP_available)



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


def updatePasswordUnauth(data):
    from orm.users import Users
    from tools import ldap
    user = Users.query.filter(Users.ID != 0, Users.username == data["user"]).first()
    if user is None:
        return jsonify(message="Invalid username or password"), 401
    if user.externID is not None:
        error = ldap.authUser(user.externID, data["old"])
        if error is not None:
            return jsonify(message=error), 401
        return jsonify(message="Cannot modify LDAP imported user"), 400
    if not user.chkPw(data["old"]):
        return jsonify(message="Invalid username or password"), 401
    user.password = data["new"]
    DB.session.commit()
    return jsonify(message="Password updated for user '{}'".format(data["user"]))


@API.route(api.BaseRoute+"/passwd", methods=["PUT"])
@secure(requireAuth=False)
def updatePassword():
    data = request.get_json(silent=True)
    if data is None or "new" not in data or "old" not in data:
        return jsonify(message="Incomplete data"), 400
    if "user" in data:
        return updatePasswordUnauth(data)
    error = getSecurityContext("user")
    if error:
        return jsonify(message=error), 401
    user = request.auth["user"]
    if user.externID is not None:
        return jsonify(message="Cannot modify LDAP imported user"), 400
    if not user.chkPw(data["old"]):
        return jsonify(message="Old password does not match"), 403
    user.password = data["new"]
    DB.session.commit()
    return jsonify(message="Password updated")
