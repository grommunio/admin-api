# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grommunio GmbH

from flask import Flask, jsonify, request, make_response
from functools import wraps

from orm import DB
from services import Service
from tools.config import Config

from . import apiSpec


class OpenApiCompat:
    def __init__(self, apiSpec):
        import openapi_core
        self.version = [int(part) for part in openapi_core.__version__.split(".")]
        if self.version < [0, 13, 0]:
            from openapi_core.wrappers.flask import FlaskOpenAPIRequest, FlaskOpenAPIResponse
        else:
            from openapi_core.contrib.flask import FlaskOpenAPIRequest, FlaskOpenAPIResponse
        if self.version < [0, 15, 0]:
            from openapi_core import create_spec
        elif self.version < [0, 19, 0]:
            from openapi_core.spec.shortcuts import create_spec
        else:
            from jsonschema_path import SchemaPath
        if self.version < [0, 18, 0]:
            self.spec = create_spec(apiSpec)
        elif self.version < [0, 19, 0]:
            self.spec = openapi_core.Spec.from_dict(apiSpec)
        else:
            self.spec = SchemaPath.from_dict(apiSpec)
        if self.version < [0, 15, 0]:
            from openapi_core.shortcuts import RequestValidator, ResponseValidator
            self.requestValidator = RequestValidator(self.spec)
            self.responseValidator = ResponseValidator(self.spec)
            self.validateRequest = lambda request: self.requestValidator.validate(FlaskOpenAPIRequest(request))
            self.validateResponse = lambda request, response: \
                self.responseValidator.validate(FlaskOpenAPIRequest(request), FlaskOpenAPIResponse(response)).errors
        elif self.version < [0, 17, 0]:
            self.FlaskOpenAPIRequest, self.FlaskOpenAPIResponse = FlaskOpenAPIRequest, FlaskOpenAPIResponse
            self.validateRequest = self._validateRequest_15_0
            self.validateResponse = self._validateResponse_15_0
        else:
            from openapi_core.unmarshalling.request import V30RequestUnmarshaller
            from openapi_core.unmarshalling.response import V30ResponseUnmarshaller
            self.FlaskOpenAPIRequest, self.FlaskOpenAPIResponse = FlaskOpenAPIRequest, FlaskOpenAPIResponse
            self.ReqUnmarshaller = V30RequestUnmarshaller(self.spec)
            self.ResUnmarshaller = V30ResponseUnmarshaller(self.spec)
            self.validateRequest = self._validateRequest_17_0
            self.validateResponse = self._validateResponse_17_0

    @staticmethod
    def _suppressError(exc):
        def matchBuggedError(err):
            return isinstance(err, ValidationError) and err.message == "None for not nullable" and "$ref" in err.schema
        from openapi_core.unmarshalling.schemas.exceptions import InvalidSchemaValue
        from jsonschema.exceptions import ValidationError
        if not isinstance(exc, InvalidSchemaValue):
            return False
        return all(matchBuggedError(err) for err in exc.schema_errors)

    def _validateRequest_15_0(self, request):
        from openapi_core.validation.request import openapi_request_validator as reqval
        result = reqval.validate(self.spec, self.FlaskOpenAPIRequest(request))
        return result

    def _validateResponse_15_0(self, request, response):
        from openapi_core.validation.response import openapi_response_validator as resval
        result = resval.validate(self.spec, self.FlaskOpenAPIRequest(request), self.FlaskOpenAPIResponse(response))
        return [error for error in result.errors if not self._suppressError(error)]

    def _validateRequest_17_0(self, request):
        result = self.ReqUnmarshaller.unmarshal(self.FlaskOpenAPIRequest(request))
        if result.errors:
            result.errors = [getattr(error, "__cause__", error) for error in result.errors]
        return result

    def _validateResponse_17_0(self, request, response):
        result = self.ResUnmarshaller.unmarshal(self.FlaskOpenAPIRequest(request), self.FlaskOpenAPIResponse(response))
        return [str(error) for error in result.errors]


if "servers" in Config["openapi"]:
    apiSpec["servers"] += Config["openapi"]["servers"]

validator = OpenApiCompat(apiSpec)

API = Flask("grommunio Admin API")  # Core API object
API.config["JSON_SORT_KEYS"] = False  # Do not sort response fields. Crashes when returning lists...
if DB is not None:
    DB.enableFlask(API)

if not Config["openapi"]["validateRequest"]:
    API.logger.warning("Request validation is disabled!")
if not Config["openapi"]["validateResponse"]:
    API.logger.warning("Response validation is disabled!")


def validateRequest(flask_request):
    """Validate the request

    Parameters
    ----------
    flask_request: flask.request
        The request sent by flask

    Returns
    -------
    Boolean
        True if the request is valid, False otherwise
    string
        Error message if validation failed, None otherwise"""
    result = validator.validateRequest(flask_request)
    if result.errors:
        return False, jsonify(message="Bad Request", errors=[str(error) for error in result.errors]), result.errors
    return True, None, None


def reloadORM():
    """Reload all active orm modules."""
    import importlib
    import sys
    API.logger.warn("Database schema version updated detected - reloading ORM")
    DB.initVersion()
    for name, module in [(name, module) for name, module in sys.modules.items() if name.startswith("orm.")]:
        importlib.reload(module)


def secure(requireDB=False, requireAuth=True, authLevel="basic", service=None, validateCSRF=None):
    """Decorator securing API functions.

       Arguments:
           - requireDB (boolean or int)
               Whether the database is needed for the call. If set to True and the database is not configured,
               and error message is returned without invoking the endpoint. If given as an integer, marks the minimum required
               schema version.
           - requireAuth (boolean or "optional")
               Whether authentication is required to use this endpoint. When set to False, no login context is created
               and user information is not available, even if logged in.
           - authLevel ("basic" or "user")
               Create login context with user object ("user") or only with information from token ("basic").
               User information can be loaded later if necessary.
           - service (string)
               Execute this endpoint in a service context. The service object is passed to the endpoint function
               as the last (unnamed) parameter.
           - validateCSRF (bool or None)
               Validate CSRF token. None will enable validation for non-GET methods.

       Automatically validates the request using the OpenAPI specification and returns a HTTP 400 to the client if validation
       fails. Also validates the response generated by the endpoint and returns a HTTP 500 on error. This behavior can be
       deactivated in the configuration.

       If an exception is raised during execution, a HTTP 500 message is returned to the client and a short description of the
       error is sent in the 'error' field of the response.
       """
    from .security import getSecurityContext

    def inner(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            def call():
                if service:
                    with Service(service) as srv:
                        ret = func(*args, srv, **kwargs)
                else:
                    ret = func(*args, **kwargs)
                response = make_response(ret)
                try:
                    result = validator.validateResponse(request, response)
                except AttributeError:
                    result = None
                if result:
                    if Config["openapi"]["validateResponse"]:
                        API.logger.error("Response validation failed: "+str(result))
                        return jsonify(message="The server generated an invalid response."), 500
                    else:
                        API.logger.warn("Response validation failed: "+str(result))
                return ret

            if requireAuth:
                checkCSRF = False if Config["security"].get("disableCSRF") else validateCSRF
                error = getSecurityContext(authLevel, checkCSRF)
                if error is not None and requireAuth != "optional":
                    return jsonify(message="Access denied", error=error), 401
            valid, message, errors = validateRequest(request)
            if not valid:
                if Config["openapi"]["validateRequest"]:
                    API.logger.info("Request validation failed: {}".format(errors))
                    return message, 400
                else:
                    API.logger.warn("Request validation failed: {}".format(errors))

            if requireDB or requireAuth:
                if DB is None:
                    return jsonify(message="Database not available."), 503
                if DB.requireReload():
                    reloadORM()
                if isinstance(requireDB, int) and not isinstance(requireDB, bool) and not DB.minVersion(requireDB):
                    return jsonify(message="Database schema version too old. Please update to at least n{}."
                                   .format(requireDB)), 500
            return call()
        return wrapper
    return inner


@API.after_request
def noCache(response):
    """Add no-cache headers to the response"""
    response.cache_control.no_cache = True
    response.cache_control.no_store = True
    response.cache_control.max_age = 1
    return response


from . import errors as _
