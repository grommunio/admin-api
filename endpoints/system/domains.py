# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grammm GmbH

from dbus import DBusException
from flask import request, jsonify
from sqlalchemy.exc import IntegrityError

from .. import defaultListHandler, defaultObjectHandler, defaultPatch

import api
from api.core import API, secure
from api.security import checkPermissions


from tools.misc import AutoClean
from tools.permissions import SystemAdminPermission, DomainAdminPermission, OrgAdminPermission, DomainPurgePermission
from tools.storage import DomainSetup
from tools.systemd import Systemd

from orm import DB
if DB is not None:
    from orm.domains import Domains, Orgs
    from orm.users import Users
    from orm.roles import AdminRoles


@API.route(api.BaseRoute+"/system/orgs", methods=["GET", "POST"])
@secure(requireDB=True)
def orgListEndpoint():
    checkPermissions(SystemAdminPermission())
    return defaultListHandler(Orgs)


@API.route(api.BaseRoute+"/system/orgs/<int:ID>", methods=["GET", "PATCH"])
@secure(requireDB=True)
def orgObjectEndpoint(ID):
    checkPermissions(SystemAdminPermission())
    return defaultObjectHandler(Orgs, ID, "Organization")


@API.route(api.BaseRoute+"/system/orgs/<int:ID>", methods=["DELETE"])
@secure(requireDB=True)
def orgDeleteEndpoint(ID):
    checkPermissions(SystemAdminPermission())
    Domains.query.filter(Domains.orgID == ID).update({Domains.orgID: 0}, synchronize_session=False)
    return defaultObjectHandler(Orgs, ID, "Organization")


###################################################################################################


@API.route(api.BaseRoute+"/system/domains", methods=["GET"])
@secure(requireDB=True)
def domainListEndpoint():
    checkPermissions(SystemAdminPermission())
    return defaultListHandler(Domains)


@API.route(api.BaseRoute+"/system/domains", methods=["POST"])
@secure(requireDB=True)
def domainCreate():
    checkPermissions(SystemAdminPermission())
    data = request.get_json(silent=True)
    if data is None:
        return jsonify(message="Missing data"), 400
    result, code = Domains.create(data, request.args.get("createRole", "false") == "true")
    if code != 201:
        return jsonify(message=result), code
    return jsonify(result.fulldesc()), 201


@API.route(api.BaseRoute+"/system/domains/<int:domainID>", methods=["GET"])
@secure(requireDB=True)
def getDomain(domainID):
    checkPermissions(DomainAdminPermission(domainID))
    return defaultObjectHandler(Domains, domainID, "Domain")


@API.route(api.BaseRoute+"/system/domains/<int:domainID>", methods=["PATCH"])
@secure(requireDB=True)
def updateDomain(domainID):
    checkPermissions(OrgAdminPermission("*"))
    domain: Domains = Domains.query.filter(Domains.ID == domainID).first()
    if domain is None:
        return jsonify(message="Domain not found"), 404
    checkPermissions(OrgAdminPermission(domain.orgID))
    oldStatus = domain.domainStatus
    patched = defaultPatch(Domains, domainID, "Domain", obj=domain, result="precommit")
    if isinstance(patched, tuple):  # Return value is not the domain, but an error response
        return patched
    if oldStatus != domain.domainStatus:
        Users.query.filter(Users.domainID == domainID)\
                   .update({Users.addressStatus: Users.addressStatus.op("&")(0xF)+(domain.domainStatus << 4)},
                           synchronize_session=False)
    try:
        DB.session.commit()
    except IntegrityError as err:
        DB.session.rollback()
        return jsonify(message="Domain update failed", error=err.orig.args[1])
    return jsonify(domain.fulldesc())


@API.route(api.BaseRoute+"/system/domains/<int:domainID>", methods=["DELETE"])
@secure(requireDB=True)
def deleteDomain(domainID):
    checkPermissions(OrgAdminPermission("*"))
    domain = Domains.query.filter(Domains.ID == domainID).first()
    if domain is None:
        return jsonify(message="Domain not found"), 404
    checkPermissions(OrgAdminPermission(domain.orgID))
    if request.args.get("purge") == "true":
        checkPermissions(DomainPurgePermission())
        domain.purge(request.args.get("deleteFiles") == "true")
        msg = "removed."
    else:
        domain.delete()
        msg = "marked as deleted."
    DB.session.commit()
    return jsonify(message="Domain "+msg)
