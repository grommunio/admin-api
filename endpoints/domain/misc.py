# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grammm GmbH

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
