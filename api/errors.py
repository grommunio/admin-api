# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grammm GmbH

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
