# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grammm GmbH

from flask import request
import time
import jwt

from tools import ldap
from tools.config import Config

try:
    with open(Config["security"]["jwtPrivateKeyFile"], "rb") as file:  # Private key for JWT signing
        jwtPrivkey = file.read()
    with open(Config["security"]["jwtPublicKeyFile"], "rb") as file:  # Public key for JWT signature verification
        jwtPubkey = file.read()
except:
    import logging
    logging.error("Could not load JWT RSA keys, authentication will not work")
    jwtPrivkey = jwtPubkey = None


def getUser():
    """Load currently logged in user from database.

    Returns
    -------
    str
        Error message or None if successful.
    """
    if "user" in request.auth:
        return
    from orm.users import Users
    try:
        user = Users.query.filter(Users.username == request.auth["claims"]["usr"]).first()
    except:
        return "Database error"
    if user is None:
        return "Invalid user"
    request.auth["user"] = user


def getSecurityContext(authLevel):
    """Create security context for the request.

    Check for `jwt` cookie in the request and try to decode it. If token is valid, the claims are saved in `request.auth`

    If authentication is disabled in the configuration (security.requireAuth=False), the default security context is used
    (security.defaultContext).

    Returns
    -------
    str
        Error message or None if successful

    """
    cookie = request.cookies.get("grammmAuthJwt")
    if cookie is None:
        return "No token provided"
    success, val = checkToken(cookie)
    if not success:
        return val
    request.auth = {"claims": val}
    if authLevel == "user":
        return getUser()


def mkJWT(claims):
    """Generate signed JWT.

    `exp` field is automatically added if not present. Token expiration can be configured by security.jwtExpiresAfter
    (in seconds), default is one week.

    Parameters
    ----------
    claims : dict
        Claims included in the JWT

    Returns
    -------
    bytes
        Signed JWT token
    """
    from tools.config import Config
    if "exp" not in claims:
        claims["exp"] = int(time.mktime(time.gmtime())+Config["security"].get("jwtExpiresAfter", 7*24*60*60))
    return jwt.encode(claims, jwtPrivkey, "RS256")


def checkToken(token):
    """Check jwt validity.

    Parameters
    ----------
    token : str
        JWT to check

    Returns
    -------
    bool
        True if valid, false otherwise
    dict / str
        Dict containing the JWT claims if successful, error message otherwise

    """
    try:
        claims = jwt.decode(token, jwtPubkey, algorithms=["RS256"])
    except jwt.ExpiredSignatureError:
        return False, "Token has expired"
    except jwt.InvalidSignatureError:
        return False, "Invalid token signature"
    except:
        return False, "invalid token"
    return True, claims


def userLoginAllowed(user):
    from orm.roles import AdminUserRoleRelation
    return user.ID == 0 or AdminUserRoleRelation.query.filter(AdminUserRoleRelation.userID == user.ID).count() != 0


def refreshToken():
    """Refresh user token.

    Check if the current token is valid and if the current user is still in the authorized group.
    """
    from orm.users import Users
    if "grammmAuthJwt" not in request.cookies:
        return
    success, claims = checkToken(request.cookies["grammmAuthJwt"])
    if not success:
        return
    user = Users.query.filter(Users.username == claims["usr"]).first()
    if not user or not userLoginAllowed(user):
        return
    if "exp" in claims:
        claims.pop("exp")
    return mkJWT(claims)


def loginUser(username, password):
    from orm.users import Users
    user: Users = Users.query.filter(Users.username == username).first()
    if user is None:
        return False, "Invalid username or password"
    if user.ldapImported:
        success, error = ldap.authUser(username, password)
        if not success:
            return False, error
    elif not user.chkPw(password):
        return False, "Invalid username or password"
    if not userLoginAllowed(user):
        return False, "Access denied"
    return True, mkJWT({"usr": user.username})


def checkPermissions(*requested):
    """Check if current user has requested permissions.

    Parameters
    ----------
    *requested : PermissionBase
        Permissions the user needs

    Raises
    ------
    InsufficientPermissions
        At least one permission check failed

    Returns
    -------
    None.
    """
    from .errors import InsufficientPermissions
    if getUser() is not None:
        raise InsufficientPermissions()
    permissions = request.auth["user"].permissions()
    if not all(permission in permissions for permission in requested):
        raise InsufficientPermissions()
