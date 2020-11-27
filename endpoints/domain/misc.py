# -*- coding: utf-8 -*-
"""
Created on Tue Oct 13 18:38:27 2020

@copyright: grammm GmbH, 2020
"""

from .. import defaultListHandler

import api
from api.core import API, secure

from tools.permissions import SystemAdminPermission, DomainAdminPermission

from flask import request, jsonify

from orm import DB
if DB is not None:
    from orm.domains import Domains


@API.route(api.BaseRoute+"/domains", methods=["GET"])
@secure(requireDB=True, authLevel="user")
def getAvailableDomains():
    permissions = request.auth["user"].permissions()
    if SystemAdminPermission() in permissions:
        domainFilters = ()
    else:
        domainIDs = {permission.domainID for permission in permissions if isinstance(permission, DomainAdminPermission)}
        if len(domainIDs) == 0:
            return jsonify(data=[])
        domainFilters = () if "*" in domainIDs else (Domains.ID.in_(domainIDs),)
    return defaultListHandler(Domains, filters=domainFilters)
