#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jun 23 11:26:12 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: _Placeholder_copyright_
"""

from flask import jsonify

from api import API
import api
from orm import DB


@API.route(api.BaseRoute+"/status", methods=["GET"])
@api.secure(requireAuth=False)
def chkState():
    """Check status of the API."""
    if DB is None:
        return jsonify(message="Online, but database is not configured")
    return jsonify(message="API is operational")


@API.route(api.BaseRoute+"/about", methods=["GET"])
@api.secure()
def getAbout(requireAuth=False):
    """Retrieve version information."""
    return jsonify(API=api.apiVersion, backend=api.backendVersion)
