# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 grommunio GmbH
"""Single sign-on via OpenID Connect (authorization code flow).

The provider is configured in the `oidc` section (see conf.d/README.md), typically written by grommunio-auth.
Endpoints and signing keys are taken from the provider's discovery document, which is cached in-process.
"""

import jwt
import requests
import secrets
import time

from flask import jsonify, redirect, request
from urllib.parse import urlencode, urlparse

import api

from api.core import API, secure
from api.security import mkJWT, userLoginAllowed
from tools.config import Config

STATE_COOKIE = "grommunioOidcState"
OIDC_PATH = api.BaseRoute+"/login/oidc"
DISCOVERY_TTL = 3600

_discovery = {}  # Cached discovery document and JWKS client


def enabled():
    """Check whether single sign-on is enabled and configured."""
    conf = Config.get("oidc", {})
    return bool(conf.get("enabled") and conf.get("issuer") and conf.get("clientId") and conf.get("clientSecret"))


def available():
    """Check whether single sign-on can be offered to the current request.

    The state and session cookies are marked Secure and only reach the callback if the login starts on the origin
    of the registered redirect URI.
    """
    if not enabled() or not request.is_secure:
        return False
    redirectUri = Config["oidc"].get("redirectUri")
    return not redirectUri or urlparse(redirectUri).netloc.lower() == request.host.lower()


def _discover():
    """Get the provider's discovery document, refreshing the cached copy after DISCOVERY_TTL seconds.

    Returns
    -------
    dict
        Cache entry with keys `doc` (discovery document) and `jwks` (jwt.PyJWKClient)
    """
    issuer = Config["oidc"]["issuer"].rstrip("/")
    if _discovery.get("issuer") != issuer or _discovery.get("expires", 0) < time.time():
        res = requests.get(issuer+"/.well-known/openid-configuration", timeout=10)
        res.raise_for_status()
        doc = res.json()
        _discovery.update(issuer=issuer, expires=time.time()+DISCOVERY_TTL, doc=doc, jwks=jwt.PyJWKClient(doc["jwks_uri"]))
    return _discovery


def _redirectUri():
    """Get the callback URL registered with the provider."""
    return Config["oidc"].get("redirectUri") or "https://{}{}/callback".format(request.host, OIDC_PATH)


def _fail(code, reason):
    """Log a failed login attempt and send the browser back to the login page.

    Parameters
    ----------
    code : str
        Short error code passed to the login page as `sso_error` parameter
    reason : str
        Description for the log

    Returns
    -------
    Response
        Redirect to the login page
    """
    API.logger.warning("Single sign-on login from '{}' failed: {}".format(request.remote_addr, reason))
    response = redirect("/login?sso_error="+code)
    response.delete_cookie(STATE_COOKIE, path=OIDC_PATH)
    return response


@API.route(api.BaseRoute+"/login/oidc", methods=["GET"])
@secure(requireAuth=False)
def oidcLogin():
    """Start the login by redirecting to the provider's authorization endpoint."""
    if not available():
        return jsonify(message="Single sign-on is not available"), 404
    conf = Config["oidc"]
    try:
        doc = _discover()["doc"]
    except Exception as err:
        return _fail("discovery_failed", "could not load provider configuration ({})".format(err))
    state = secrets.token_hex(16)
    params = dict(client_id=conf["clientId"], response_type="code", scope=conf.get("scope", "openid email profile"),
                  redirect_uri=_redirectUri(), state=state)
    response = redirect(doc["authorization_endpoint"]+"?"+urlencode(params))
    response.set_cookie(STATE_COOKIE, state, max_age=600, path=OIDC_PATH, secure=True, httponly=True, samesite="Lax")
    return response


@API.route(api.BaseRoute+"/login/oidc/callback", methods=["GET"])
@secure(requireAuth=False, requireDB=True)
def oidcCallback():
    """Exchange the authorization code, verify the ID token and log the user in.

    On success the API token is set as `grommunioAuthJwt` cookie and the browser is redirected to the login page,
    which picks up the session.
    """
    from orm.users import Users, Altnames
    if not enabled():
        return jsonify(message="Single sign-on is not enabled"), 404
    conf = Config["oidc"]
    if "error" in request.args:
        return _fail("access_denied", request.args.get("error_description") or request.args["error"])
    state = request.cookies.get(STATE_COOKIE)
    if "code" not in request.args or not state or request.args.get("state") != state:
        return _fail("invalid_state", "missing or mismatched state")
    try:
        discovery = _discover()
        doc = discovery["doc"]
        res = requests.post(doc["token_endpoint"], timeout=10,
                            data=dict(grant_type="authorization_code", code=request.args["code"],
                                      redirect_uri=_redirectUri(), client_id=conf["clientId"],
                                      client_secret=conf["clientSecret"]))
        tokens = res.json()
        if res.status_code != 200 or "id_token" not in tokens:
            return _fail("exchange_failed", tokens.get("error_description") or tokens.get("error") or
                         "HTTP {}".format(res.status_code))
    except Exception as err:
        return _fail("exchange_failed", "token request failed ({})".format(err))
    try:
        key = discovery["jwks"].get_signing_key_from_jwt(tokens["id_token"])
        claims = jwt.decode(tokens["id_token"], key.key, algorithms=["RS256"], audience=conf["clientId"],
                            issuer=doc["issuer"])
    except Exception as err:
        return _fail("invalid_token", "ID token verification failed ({})".format(err))
    username = claims.get(conf.get("usernameClaim", "preferred_username"))
    if not username:
        return _fail("unknown_user", "ID token contains no username")
    user = Users.query.join(Altnames, isouter=True)\
                      .filter((Users.username == username) | (Altnames.altname == username)).first()
    if user is None:
        return _fail("unknown_user", "user '{}' not found".format(username))
    if not userLoginAllowed(user):
        return _fail("access_denied", "user '{}' is not allowed to log in".format(username))
    response = redirect("/login?sso=1")
    response.set_cookie("grommunioAuthJwt", mkJWT({"usr": user.username}), path="/", secure=True, samesite="Lax")
    response.delete_cookie(STATE_COOKIE, path=OIDC_PATH)
    return response
