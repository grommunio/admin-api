# -*- coding: utf-8 -*-
"""
Created on Tue Jun 23 11:20:26 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: _Placeholder_copyright_
"""

from api import API
from flask import jsonify, request


@API.errorhandler(404)
def not_found(error):
    """Return JSON object with 404 message."""
    return jsonify(message="Resource not found"), 404


@API.errorhandler(405)
def method_not_allowed(error):
    """Return JSON object with 405 message."""
    return jsonify(message="Method '{}' not allowed on this endpoint".format(request.method)), 405
