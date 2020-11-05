# -*- coding: utf-8 -*-
"""
Created on Tue Jun 23 17:02:02 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: Grammm GmbH, 2020
"""

from flask import request, jsonify
from sqlalchemy.exc import IntegrityError

from .. import defaultListHandler, defaultObjectHandler, defaultPatch

import api
from api.core import API, secure
from api.security import checkPermissions

from tools.misc import AutoClean, createMapping
from tools.storage import DomainSetup
from tools.permissions import SystemAdminPermission

from orm import DB
if DB is not None:
    from orm.domains import Domains
    from orm.ext import AreaList
    from orm.users import Users, Groups
    from orm.roles import AdminRoles


@API.route(api.BaseRoute+"/system/domains", methods=["GET"])
@secure(requireDB=True)
def domainListEndpoint():
    checkPermissions(SystemAdminPermission())
    return defaultListHandler(Domains)


@API.route(api.BaseRoute+"/system/domains", methods=["POST"])
@secure(requireDB=True)
def domainCreate():
    checkPermissions(SystemAdminPermission())
    def rollback():
        DB.session.rollback()
    data = request.get_json(silent=True) or {}
    areaID = data.get("areaID")
    domain = defaultListHandler(Domains, result="object")
    if not isinstance(domain, Domains):
        return domain  # If the return value is not a domain, it is an error response
    area = AreaList.query.filter(AreaList.dataType == AreaList.DOMAIN, AreaList.ID == areaID).first()
    try:
        with AutoClean(rollback):
            DB.session.add(domain)
            DB.session.flush()
            with DomainSetup(domain, area) as ds:
                ds.run()
            if not ds.success:
                return jsonify(message="Error during domain setup", error=ds.error),  ds.errorCode
            DB.session.commit()
        domainAdminRoleName = "Domain Admin ({})".format(domain.domainname)
        if AdminRoles.query.filter(AdminRoles.name == domainAdminRoleName).count() == 0:
            DB.session.add(AdminRoles({"name": domainAdminRoleName,
                                       "description": "Domain administrator for "+domain.domainname,
                                       "permissions": [{"permission": "DomainAdmin", "params": domain.ID}]}))
            DB.session.commit()
        return jsonify(domain.fulldesc()), 201
    except IntegrityError as err:
        return jsonify(message="Object violates database constraints", error=err.orig.args[1]), 400


@API.route(api.BaseRoute+"/system/domains/<int:domainID>", methods=["GET"])
@secure(requireDB=True)
def getDomain(domainID):
    checkPermissions(SystemAdminPermission())
    return defaultObjectHandler(Domains, domainID, "Domain")


@API.route(api.BaseRoute+"/system/domains/<int:domainID>", methods=["PATCH"])
@secure(requireDB=True)
def updateDomain(domainID):
    checkPermissions(SystemAdminPermission())
    domain: Domains = Domains.query.filter(Domains.ID == domainID).first()
    if domain is None:
        return jsonify(message="Domain not found"), 404
    data = request.get_json(silent=True, cache=True)
    oldStatus = domain.domainStatus
    patched = defaultPatch(Domains, domainID, "Domain", obj=domain, result="precommit")
    if isinstance(patched, tuple):  # Return value is not the domain, but an error response
        return patched
    if oldStatus != domain.domainStatus:
        Users.query.filter(Users.domainID == domainID)\
                   .update({Users.addressStatus: Users.addressStatus.op("&")(0xF)+(domain.domainStatus << 4)},
                           synchronize_session=False)
        Groups.query.filter(Groups.domainID == domain.ID)\
                    .update({Groups.groupStatus: Groups.groupStatus.op("&")(0x3) + (domain.domainStatus << 2)},
                            synchronize_session=False)
    data.pop("ID", None)
    data.pop("domainname", None)
    try:
        DB.session.commit()
    except IntegrityError as err:
        DB.session.rollback()
        return jsonify(message="Domain update failed", error=err.orig.args[1])
    return jsonify(domain.fulldesc())


@API.route(api.BaseRoute+"/system/domains/<int:domainID>", methods=["DELETE"])
@secure(requireDB=True)
def deleteDomain(domainID):
    checkPermissions(SystemAdminPermission())
    domain = Domains.query.filter(Domains.ID == domainID).first()
    if domain is None:
        return jsonify(message="Domain not found"), 404
    domain.domainStatus = Domains.DELETED
    Users.query.filter(Users.domainID == domainID)\
               .update({Users.addressStatus: Users.addressStatus.op("&")(0xF) + (Domains.DELETED << 4)},
                       synchronize_session=False)
    Groups.query.filter(Groups.domainID == domain.ID)\
                .update({Groups.groupStatus: Groups.groupStatus.op("&")(0x3) + (Domains.DELETED << 2)},
                        synchronize_session=False)
    DB.session.commit()
    return jsonify(message="k.")
