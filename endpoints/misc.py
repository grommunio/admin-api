# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grommunio GmbH

from flask import jsonify, request

import api
import idna

from api.core import API, secure
from api.security import loginUser, refreshToken, getSecurityContext

from orm import DB
from services import Service
from tools import formats


@API.route(api.BaseRoute+"/status", methods=["GET"])
@secure(requireAuth=False)
def chkState():
    """Check status of the API."""
    return jsonify(message="API is operational",
                   database=DB is not None and DB.testConnection() is None,
                   ldap=Service.available("ldap"))


@API.route(api.BaseRoute+"/about", methods=["GET"])
@secure(requireAuth=False)
def getAbout(requireAuth=False):
    """Retrieve version information."""
    return jsonify(API=api.apiVersion, backend=api.backendVersion, schema=DB.version if DB is not None else None)


@API.route(api.BaseRoute+"/login", methods=["POST"])
@secure(requireAuth=False)
def login():
    if "user" not in request.form or "pass" not in request.form:
        refreshed = refreshToken()
        if refreshed is not None:
            return jsonify(grommunioAuthJwt=refreshed)
        return jsonify(message="Incomplete login form"), 400
    success, val = loginUser(request.form["user"], request.form["pass"])
    if not success:
        API.logger.warning("Failed login attempt for user '{}' from '{}': {}"
                           .format(request.form["user"], request.remote_addr, val))
        return jsonify(message="Login failed", error=val), 401
    return jsonify({"grommunioAuthJwt": val})


@API.route(api.BaseRoute+"/profile", methods=["GET"])
@secure(authLevel="user")
def getProfile():
    user = request.auth["user"]
    capabilities = tuple(user.permissions().capabilities())
    return jsonify(user=user.fulldesc(exclude={"fetchmail"}), capabilities=capabilities)


def updatePasswordUnauth(data):
    from orm.users import Users
    user = Users.query.filter(Users.ID != 0, Users.username == data["user"]).first()
    if user is None:
        return jsonify(message="Invalid username or password"), 401
    if user.externID is not None:
        with Service("ldap") as ldap:
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


def chkDomain(domain):
    try:
        domain = idna.encode(domain).decode("ascii")
        if not formats.domain.match(domain):
            return "Domain does not match required format"
        else:
            return None
    except idna.IDNAError as err:
        return err.args[0]
    except Exception as err:
        return "Unknown error ({})".format(type(err).__name__)


def chkEmail(email):
    if email.count("@") != 1:
        return "E-Mail address does not match required format"
    user, domain = email.split("@")
    err = chkDomain(domain)
    if err:
        return err
    email = user+"@"+idna.encode(domain).decode("ascii")
    if not formats.email.match(email):
        return "E-Mail address does not match required format"


@API.route(api.BaseRoute+"/chkFormat", methods=["GET"])
@secure(requireAuth=False)
def validateFormat():
    result = {}
    if "domain" in request.args:
        result["domain"] = chkDomain(request.args["domain"])
    if "email" in request.args:
        result["email"] = chkEmail(request.args["email"])
    return jsonify(result)
