# -*- coding: utf-8 -*-
"""
Created on Tue Jun 23 17:02:02 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: _Placeholder_copyright_
"""

import api
from api import API

from . import defaultListHandler, defaultObjectHandler

from orm import DB
if DB is not None:
    from orm.orgs import Orgs, Domains, Aliases


@API.route(api.BaseRoute+"/orgs", methods=["GET", "POST"])
@api.secure(requireDB=True)
def orgListEndpoint():
    return defaultListHandler(Orgs)


@API.route(api.BaseRoute+"/orgs/<int:ID>", methods=["GET", "PATCH", "DELETE"])
@api.secure(requireDB=True)
def orgObjectEndpoint(ID):
    return defaultObjectHandler(Orgs, ID, "Org")


@API.route(api.BaseRoute+"/domains", methods=["GET", "POST"])
@api.secure(requireDB=True)
def domainListEndpoint():
    return defaultListHandler(Domains)


@API.route(api.BaseRoute+"/domains/<int:ID>", methods=["GET", "PATCH", "DELETE"])
@api.secure(requireDB=True)
def domainObjectEndpoint(ID):
    return defaultObjectHandler(Domains, ID, "Domain")


@API.route(api.BaseRoute+"/aliases", methods=["GET", "POST"])
@api.secure(requireDB=True)
def aliasListEndpoint():
    return defaultListHandler(Aliases)


@API.route(api.BaseRoute+"/aliases/<int:ID>", methods=["GET", "PATCH", "DELETE"])
@api.secure(requireDB=True)
def aliasObjectEndpoint(ID):
    return defaultObjectHandler(Aliases, ID, "Alias")
