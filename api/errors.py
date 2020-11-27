# -*- coding: utf-8 -*-
"""
Created on Tue Jun 23 11:20:26 2020

@copyright: grammm GmbH, 2020
"""

from api.core import API
from flask import jsonify, request


class InsufficientPermissions(RuntimeError):
    pass


@API.errorhandler(InsufficientPermissions)
def insufficient_permissions(error):
    return jsonify(message="Insufficient permissions for this operation"), 403


@API.errorhandler(404)
def not_found(error):
    """Return JSON object with 404 message."""
    return jsonify(message="Resource not found"), 404


@API.errorhandler(405)
def method_not_allowed(error):
    """Return JSON object with 405 message."""
    return jsonify(message="Method '{}' not allowed on this endpoint".format(request.method)), 405
