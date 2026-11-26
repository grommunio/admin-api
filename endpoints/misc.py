# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grommunio GmbH

from flask import jsonify, request

import api
import idna

from api.core import API, secure
from api.security import loginUser, refreshToken, getSecurityContext, mkCSRF, setAuthCookie, clearAuthCookie, \
    revokeToken, checkToken

from . import oidc

from orm import DB
from services import Service, ServiceUnavailableError
from tools import audit, formats
from tools.config import Config
from tools.passwordpolicy import checkPassword, PolicyUnavailableError
from tools.tasq import TasQServer
from tools.permissions import OrgAdminPermission


@API.route(api.BaseRoute+"/status", methods=["GET"])
@secure(requireAuth=False)
def chkState():
    """Check status of the API."""
    return jsonify(message="API is operational",
                   database=DB is not None and DB.testConnection() is None,
                   tasq=TasQServer.running(),
                   oidc=oidc.available())


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
        if refreshed is None:
            return jsonify(message="Incomplete login form"), 400
        return setAuthCookie(jsonify(grommunioAuthJwt=refreshed, csrf=mkCSRF(refreshed)), refreshed)
    success, val = loginUser(request.form["user"], request.form["pass"])
    if not success:
        API.logger.warning("Failed login attempt for user '{}' from '{}': {}"
                           .format(request.form["user"], request.remote_addr, val))
        audit.login(request, request.form["user"], "password", val)
        return jsonify(message="Login failed", error=val), 401
    audit.login(request, request.form["user"], "password")
    return setAuthCookie(jsonify(grommunioAuthJwt=val, csrf=mkCSRF(val)), val)


@API.route(api.BaseRoute+"/logout", methods=["POST"])
@secure(requireAuth=False)
def logout():
    token = request.cookies.get("grommunioAuthJwt")
    if token:
        valid, claims = checkToken(token)
        revokeToken(token)
        if valid:
            audit.log("{} logged out from {}".format(audit.q(claims.get("usr")), audit.esc(request.remote_addr)))
    return clearAuthCookie(jsonify(message="Logged out"))


@API.route(api.BaseRoute+"/profile", methods=["GET"])
@secure(authLevel="user")
def getProfile():
    user = request.auth["user"]
    perms = user.permissions()
    permittedOrgs = [perm.org for perm in perms if isinstance(perm, OrgAdminPermission)]
    permittedOrgs = [o for o in permittedOrgs if o is not None]
    capabilities = tuple(user.permissions().capabilities())
    return jsonify(user=user.fulldesc(exclude={"fetchmail"}), capabilities=capabilities, permittedOrgs=permittedOrgs)


def checkNewPassword(user, data):
    """Check the new password against `options.passwordPolicy`.

    Returns
    -------
    Response tuple if the password is rejected, or None if it is accepted
    """
    try:
        error = checkPassword(data["new"], user.username)
    except PolicyUnavailableError as err:
        return jsonify(message=str(err)), 503
    return (jsonify(message=error), 400) if error else None


def updateLdapPassword(user, data, unauth):
    """Change the password of an LDAP imported user in the directory.

    Enabled by `options.ldapPasswordChange`. The old password is verified by
    binding as the user. The account must be active, the user must have the
    changePassword privilege, and the new password must pass
    `options.passwordPolicy`. The password policy of the directory applies too.
    """
    from services.ldap import InsecureConnectionError

    def check():
        if user.addressStatus != 0:
            return 403, "Account is deactivated"
        if not user.changePassword:
            return 403, "Password change not permitted"
        error = checkPassword(data["new"], user.username)
        return (400, error) if error else None

    try:
        with Service("ldap", user.orgID) as ldap:
            try:
                error = ldap.changePassword(user.externID, data["old"], data["new"], check)
            except InsecureConnectionError as err:
                API.logger.warning("Refusing to change password of '{}': {}".format(user.username, err))
                return jsonify(message="Password change requires an encrypted connection to the directory"), 503
            except PolicyUnavailableError as err:
                return jsonify(message=str(err)), 503
    except ServiceUnavailableError as err:
        if not unauth:
            raise
        API.logger.warning("Cannot change password of '{}': {}".format(user.username, err.args[0]))
        raise ServiceUnavailableError("Authentication service not available")
    if error is None:
        return jsonify(message="Password updated")
    if error[0] == 401 and not unauth:
        return jsonify(message="Old password does not match"), 403
    return jsonify(message=error[1]), error[0]


def updatePasswordUnauth(data):
    from orm.users import Users, Altnames
    user = Users.query.join(Altnames, isouter=True)\
                      .filter(Users.ID != 0, (Users.username == data["user"]) | (Altnames.altname == data["user"]))\
                      .first()
    if user is None:
        return jsonify(message="Invalid username or password"), 401
    if user.externID is not None:
        if Config["options"].get("ldapPasswordChange"):
            return updateLdapPassword(user, data, unauth=True)
        try:
            with Service("ldap") as ldap:
                error = ldap.authUser(user.externID, data["old"])
                if error is not None:
                    return jsonify(message=error), 401
        except ServiceUnavailableError as err:
            API.logger.warning("Cannot authenticate '{}': {}".format(user.username, err.args[0]))
            raise ServiceUnavailableError("Authentication service not available")
        return jsonify(message="Cannot modify LDAP imported user"), 400
    if not user.chkPw(data["old"]):
        return jsonify(message="Invalid username or password"), 401
    error = checkNewPassword(user, data)
    if error:
        return error
    user.password = data["new"]
    DB.session.commit()
    return jsonify(message="Password updated for user '{}'".format(data["user"]))


@API.route(api.BaseRoute+"/passwd", methods=["PUT"])
@secure(requireAuth=False)
def updatePassword():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("new"), str) or not isinstance(data.get("old"), str)\
            or not isinstance(data.get("user", ""), str):
        return jsonify(message="Incomplete data"), 400
    if "user" in data:
        return updatePasswordUnauth(data)
    error = getSecurityContext("user")
    if error:
        return jsonify(message=error), 401
    user = request.auth["user"]
    if user.externID is not None:
        if Config["options"].get("ldapPasswordChange"):
            return updateLdapPassword(user, data, unauth=False)
        return jsonify(message="Cannot modify LDAP imported user"), 400
    if not user.chkPw(data["old"]):
        return jsonify(message="Old password does not match"), 403
    error = checkNewPassword(user, data)
    if error:
        return error
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


@API.route(api.BaseRoute+"/disabledPluginsOfUser", methods=["GET"])
@secure(requireAuth=False, requireDB=133)
def getDisabledPluginsOfUser():
    if "username" not in request.args:
        return jsonify(message="Missing required parameter 'username'"), 400
    username = request.args["username"]
    if "@" not in username:
        return jsonify(message="Invalid username"), 400
    from orm.domains import Domains
    domain = Domains.query.filter(Domains.domainname == username.split("@")[1]).first()
    if domain is None:
        return jsonify(message="Domain not found"), 404
    
    from orm.domains import DisabledPlugins
    disabledPlugins = DisabledPlugins.query.filter(DisabledPlugins.domainID == domain.ID)\
                        .with_entities(DisabledPlugins.plugin).all()
    disabledPlugins = [p[0] for p in disabledPlugins]

    return jsonify({ "data": disabledPlugins })
