# -*- coding: utf-8 -*-
"""
Created on Tue Jun 23 17:02:02 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: _Placeholder_copyright_
"""


from flask import request, jsonify
from sqlalchemy.exc import IntegrityError


from . import defaultListHandler, defaultObjectHandler, defaultPatch

import api
from api import API
from api.security import checkPermissions

from tools.misc import AutoClean, createMapping
from tools.storage import DomainSetup
from tools.permissions import SystemAdminPermission

from orm import DB
if DB is not None:
    from orm.orgs import Orgs, Domains, Aliases
    from orm.ext import AreaList
    from orm.users import Users, Groups


@API.route(api.BaseRoute+"/orgs", methods=["GET", "POST"])
@api.secure(requireDB=True)
def orgListEndpoint():
    return defaultListHandler(Orgs)


@API.route(api.BaseRoute+"/orgs/<int:ID>", methods=["GET", "PATCH", "DELETE"])
@api.secure(requireDB=True)
def orgObjectEndpoint(ID):
    return defaultObjectHandler(Orgs, ID, "Org")


@API.route(api.BaseRoute+"/system/domains", methods=["GET"])
@api.secure(requireDB=True)
def domainListEndpoint():
    checkPermissions(SystemAdminPermission())
    return defaultListHandler(Domains)


@API.route(api.BaseRoute+"/system/domains", methods=["POST"])
@api.secure(requireDB=True)
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
            return jsonify(domain.fulldesc()), 201
    except IntegrityError as err:
        return jsonify(message="Object violates database constraints", error=err.orig.args[1]), 400


@API.route(api.BaseRoute+"/system/domains/<int:domainID>", methods=["GET"])
@api.secure(requireDB=True)
def getDomain(domainID):
    checkPermissions(SystemAdminPermission())
    return defaultObjectHandler(Domains, domainID, "Domain")


@API.route(api.BaseRoute+"/system/domains/<int:domainID>", methods=["PATCH"])
@api.secure(requireDB=True)
def updateDomain(domainID):
    checkPermissions(SystemAdminPermission())
    domain: Domains = Domains.query.filter(Domains.ID == domainID).first()
    if domain is None:
        return jsonify(message="Domain not found"), 404
    if domain.domainType == Domains.ALIAS:
        return jsonify(message="Cannot edit alias domain"), 400
    data = request.get_json(silent=True, cache=True)
    oldPrivileges, oldStatus = domain.privilegeBits, domain.domainStatus
    patched = defaultPatch(Domains, domainID, "Domain", obj=domain, result="precommit")
    if isinstance(domain, tuple):  # Return value is not the domain, but an error response
        return domain
    if domain.privilegeBits != oldPrivileges or oldStatus != domain.domainStatus:
        Users.query.filter(Users.domainID == domainID)\
                   .update({Users.privilegeBits: Users.privilegeBits.op("&")(0xFFFF) + (domain.privilegeBits << 16)},
                           synchronize_session=False)
        Groups.query.filter(Groups.domainID == domain.ID)\
                    .update({Groups.privilegeBits: Groups.privilegeBits.op("&")(0xFF) + (domain.privilegeBits << 8)},
                            synchronize_session=False)
    data.pop("ID", None)
    data.pop("domainname", None)
    aliasDomainNames = Aliases.query.filter(Aliases.mainname == domain.domainname).with_entities(Aliases.aliasname)
    aliasDomains = Domains.query.join(Aliases, Aliases.mainname == Domains.domainname)\
                                .filter(Aliases.aliasname == domain.domainname).all()
    for aliasDomain in aliasDomains:
        aliasDomain.fromdict(data)
    try:
        DB.session.commit()
    except IntegrityError as err:
        DB.session.rollback()
        return jsonify(message="Domain update failed", error=err.orig.args[1])
    return jsonify(domain.fulldesc())


@API.route(api.BaseRoute+"/system/domains/<int:domainID>", methods=["DELETE"])
@api.secure(requireDB=True)
def deleteDomain(domainID):
    checkPermissions(SystemAdminPermission())
    domain = Domains.query.filter(Domains.ID == domainID).first()
    if domain is None:
        return jsonify(message="Domain not found"), 404
    if domain.domainType == Domains.ALIAS:
        return deleteAliasDomain(aliasDomain=domain)
    domain.domainStatus = Domains.DELETED
    Users.query.filter(Users.domainID == domainID)\
               .update({Users.addressStatus: Users.addressStatus.op("&")(0xF) + (Domains.DELETED << 4)},
                       synchronize_session=False)
    Groups.query.filter(Groups.domainID == domain.ID)\
                .update({Groups.groupStatus: Groups.groupStatus.op("&")(0x3) + (Domains.DELETED << 2)},
                        synchronize_session=False)
    aliasNames = Aliases.query.filter(Aliases.mainname == domain.domainname).with_entities(Aliases.aliasname)
    Domains.query.filter(Domains.domainname == aliasNames)\
                 .update({Domains.domainStatus: Domains.DELETED}, synchronize_session=False)
    if domain.domainType == Domains.ALIAS:
        Aliases.query.filter(Aliases.aliasname == domain.domainname).delete()
    DB.session.commit()
    return jsonify(message="k.")


@API.route(api.BaseRoute+"/system/domains/<int:domainID>/password", methods=["PUT"])
@api.secure(requireDB=True)
def setDomainPassword(domainID):
    checkPermissions(SystemAdminPermission())
    domain = Domains.query.filter(Domains.ID == domainID).first()
    if domain is None:
        return jsonify(message="Domain not found"), 404
    data = request.get_json(silent=True)
    if data is None or "new" not in data:
        return jsonify(message="Incomplete data"), 400
    domain.password = data["new"]
    DB.session.commit()
    return jsonify(message="Success")


@API.route(api.BaseRoute+"/system/domains/<int:domainID>/aliases", methods=["GET"])
@api.secure(requireDB=True)
def domainAliasListEndpoint(domainID):
    checkPermissions(SystemAdminPermission())
    domain = Domains.query.filter(Domains.ID == domainID).first()
    if domain is None:
        return jsonify(message="Domain not found"), 404
    return defaultListHandler(Aliases, filters=(Aliases.mainname == domain.domainname,))


@API.route(api.BaseRoute+"/system/domains/<int:domainID>/aliases", methods=["POST"])
@api.secure(requireDB=True)
def createDomainAlias(domainID):
    checkPermissions(SystemAdminPermission())
    data = request.get_json(silent=True)
    if data is None or "aliasname" not in data:
        return jsonify("Missing alias name"), 400
    aliasname = data["aliasname"]
    domain = Domains.query.filter(Domains.ID == domainID).first()
    if domain is None:
        return jsonify(message="Domain not found"), 404
    alias = Aliases({"mainname": domain.domainname, "aliasname": aliasname})
    DB.make_transient(domain)
    domain.ID = None
    domain.domainname = aliasname
    domain.domainType = Domains.ALIAS
    for user in Users.query.filter(Users.domainID == domainID, Users.addressType != Users.VIRTUAL).all():
        DB.make_transient(user)
        user.ID = None
        user.username = user.baseName()+"@"+aliasname
        user.addressType = Users.VIRTUAL
        DB.session.add(user)
    DB.session.add(domain)
    DB.session.add(alias)
    try:
        DB.session.commit()
    except IntegrityError as err:
        DB.session.rollback()
        return jsonify(message="Alias creation failed", error=err.orig.args[1]), 500
    return jsonify(alias.fulldesc()), 201


@API.route(api.BaseRoute+"/system/domains/aliases", methods=["GET"])
@api.secure(requireDB=True)
def getAliasesByDomain():
    checkPermissions(SystemAdminPermission())
    aliases = Aliases.query.join(Domains, Domains.domainname == Aliases.aliasname)\
                           .with_entities(Aliases.ID, Aliases.mainname, Aliases.aliasname, Domains.domainStatus).all()
    return jsonify(data=createMapping(aliases,
                                      lambda alias: alias.mainname,
                                      lambda alias: {"ID": alias.ID, "aliasname": alias.aliasname, "domainStatus": alias.domainStatus}))


@API.route(api.BaseRoute+"/system/domains/aliases/<int:ID>", methods=["DELETE"])
@api.secure(requireDB=True)
def deleteDomainAlias(ID):
    checkPermissions(SystemAdminPermission())
    alias = Aliases.query.filter(Aliases.ID == ID).first()
    if alias is None:
        return jsonify(message="Alias not found"), 404
    return deleteAliasDomain(alias=alias)


def deleteAliasDomain(aliasDomain=None, alias=None, domain=None):
    """Delete alias domain.

    Sets an alias domain status and all its users to DELETED.

    At least one of `aliasDomain` and `alias` must be set, other values can be deduced automatically.

    Parameters
    ----------
    aliasDomain : Domains, optional
        Alias domain to delete. The default is None.
    alias : Aliases, optional
        Alias to delete. The default is None.
    domain : Domains, optional
        Aliased domain. The default is None.

    Returns
    -------
    response
        The flask response to return
    """
    checkPermissions(SystemAdminPermission())
    if aliasDomain is None and alias is None:
        return jsonify(message="Get out of here, stalker."), 500
    if aliasDomain is None:
        aliasDomain = Domains.query.filter(Domains.domainname == alias.aliasname).first()
    if alias is None:
        alias = Aliases.query.filter(Aliases.aliasname == aliasDomain.domainname).first()
    if domain is None:
        domain = Domains.query.filter(Domains.domainname == alias.mainname).first()
    if None in (aliasDomain, alias, domain):
        return jsonify(message="Incomplete data"), 500
    aliasDomain.domainStatus = Domains.DELETED
    Users.query.filter(Users.domainID == domain.ID, Users.addressType == Users.VIRTUAL,
                       Users.username.like("%@"+aliasDomain.domainname))\
               .update({Users.addressStatus: Users.addressStatus.op("&")(0xF) + (Domains.DELETED << 4)},
                       synchronize_session=False)
    DB.session.commit()
    return jsonify(message="Alias deleted")
