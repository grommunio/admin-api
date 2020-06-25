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

from . import defaultListHandler, defaultObjectHandler

if DB is not None:
    from orm.misc import Forwards, MLists, Associations, Classes, Hierarchy, Members, Specifieds

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


@API.route(api.BaseRoute+"/forwards", methods=["GET", "POST"])
@api.secure(requireDB=True)
def forwardListEndpoint():
    return defaultListHandler(Forwards)


@API.route(api.BaseRoute+"/forwards/<int:ID>", methods=["GET", "PATCH", "DELETE"])
@api.secure(requireDB=True)
def forwardObjectEndpoint(ID):
    return defaultObjectHandler(Forwards, ID, "Forward")


@API.route(api.BaseRoute+"/mlists", methods=["GET", "POST"])
@api.secure(requireDB=True)
def mlistListEndpoint():
    return defaultListHandler(MLists)


@API.route(api.BaseRoute+"/mlists/<int:ID>", methods=["GET", "PATCH", "DELETE"])
@api.secure(requireDB=True)
def mlistObjectEndpoint(ID):
    return defaultObjectHandler(MLists, ID, "MList")


@API.route(api.BaseRoute+"/associations", methods=["GET", "POST"])
@api.secure(requireDB=True)
def associationListEndpoint():
    return defaultListHandler(Associations)


@API.route(api.BaseRoute+"/association/<int:ID>", methods=["GET", "PATCH", "DELETE"])
@api.secure(requireDB=True)
def associationObjectEndpoint(ID):
    return defaultObjectHandler(Associations, ID, "Association")


@API.route(api.BaseRoute+"/classes", methods=["GET", "POST"])
@api.secure(requireDB=True)
def classListEndpoint():
    return defaultListHandler(Classes)


@API.route(api.BaseRoute+"/classes/<int:ID>", methods=["GET", "PATCH", "DELETE"])
@api.secure(requireDB=True)
def classObjectEndpoint(ID):
    return defaultObjectHandler(Classes, ID, "Class")


@API.route(api.BaseRoute+"/hierarchy", methods=["GET", "POST"])
@api.secure(requireDB=True)
def hierarchyListEndpoint():
    return defaultListHandler(Hierarchy)


@API.route(api.BaseRoute+"/hierarchy/<int:ID>", methods=["GET", "PATCH", "DELETE"])
@api.secure(requireDB=True)
def hierarchyObjectEndpoint(ID):
    return defaultObjectHandler(Hierarchy, ID, "Hierarchy")


@API.route(api.BaseRoute+"/members", methods=["GET", "POST"])
@api.secure(requireDB=True)
def memberListEndpoint():
    return defaultListHandler(Members)


@API.route(api.BaseRoute+"/members/<int:ID>", methods=["GET", "PATCH", "DELETE"])
@api.secure(requireDB=True)
def memberObjectEndpoint(ID):
    return defaultObjectHandler(Members, ID, "Members")


@API.route(api.BaseRoute+"/specifieds", methods=["GET", "POST"])
@api.secure(requireDB=True)
def specifiedListEndpoint():
    return defaultListHandler(Specifieds)


@API.route(api.BaseRoute+"/specifieds/<int:ID>", methods=["GET", "PATCH", "DELETE"])
@api.secure(requireDB=True)
def speciedObjectEndpoint(ID):
    return defaultObjectHandler(Specifieds, ID, "Specified")
