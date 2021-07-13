# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grammm GmbH

from .. import defaultListHandler

import api
from api.core import API, secure

from tools.permissions import SystemAdminPermission, DomainAdminROPermission, OrgAdminPermission

from flask import request
from sqlalchemy import or_

@API.route(api.BaseRoute+"/domains", methods=["GET"])
@secure(requireDB=True, authLevel="user")
def getAvailableDomains():
    from orm.domains import Domains
    permissions = request.auth["user"].permissions()
    if SystemAdminPermission() in permissions:
        domainFilters = ()
    else:
        domainIDs = {permission.domainID for permission in permissions if isinstance(permission, DomainAdminROPermission)}
        orgIDs = {permission.orgID for permission in permissions if isinstance(permission, OrgAdminPermission)}
        domainFilters = () if "*" in domainIDs or "*" in orgIDs else \
                        (or_(Domains.ID.in_(domainIDs), Domains.orgID.in_(orgIDs)),)
    return defaultListHandler(Domains, filters=domainFilters)
