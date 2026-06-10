# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grommunio GmbH

from .. import defaultListHandler

import api
from api.core import API, secure
from api.security import checkPermissions

from tools.permissions import SystemAdminPermission, DomainAdminROPermission, OrgAdminPermission, DomainAdminPermission
from tools.dnsHealth import fullDNSCheck, generateDkimKeys

from flask import request, jsonify
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


@API.route(api.BaseRoute+"/domains/<int:domainID>/dnsCheck", methods=["GET"])
@secure(requireDB=True)
def checkDomainDNS(domainID):
    checkPermissions(DomainAdminROPermission(domainID))
    from orm.domains import Domains
    domain = Domains.query.filter(Domains.ID == domainID).with_entities(Domains.domainname).first()
    if domain is None:
        return jsonify(message="Domain not found"), 404
    dnsCheck, error = fullDNSCheck(domain.domainname)
    if error is not None:
        return jsonify(message=error), 500
    return jsonify(dnsCheck)


@API.route(api.BaseRoute+"/domains/<int:domainID>/generateDkimKeys", methods=["POST"])
@secure(requireDB=True)
def generateDomainDkimKeys(domainID):
    checkPermissions(DomainAdminPermission(domainID))
    from orm.domains import Domains
    domain = Domains.query.filter(Domains.ID == domainID).with_entities(Domains.domainname).first()
    if domain is None:
        return jsonify(message="Domain not found"), 404
    data = request.get_json(silent=True)
    dnsCheck, error = generateDkimKeys(domain.domainname, **data)
    if error is not None:
        return jsonify(message=error), 500
    return jsonify(dnsCheck)
