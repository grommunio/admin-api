# -*- coding: utf-8 -*-
"""
Created on Tue Jun 23 16:37:38 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: Grammm GmbH, 2020
"""

import api
from api.core import API, secure
from api.security import checkPermissions

from flask import request, jsonify
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from .. import defaultListHandler, defaultObjectHandler, defaultPatch

from tools.misc import AutoClean, createMapping
from tools.storage import UserSetup
from tools.pyexmdb import pyexmdb
from tools.config import Config
from tools.constants import PropTags
from tools.DataModel import InvalidAttributeError, MismatchROError
from tools.permissions import SystemAdminPermission, DomainAdminPermission

import shutil

from orm import DB
if DB is not None:
    from orm.ext import AreaList
    from orm.users import Users, Groups
    from orm.domains import Domains, Aliases
    from orm.misc import Associations, Forwards, Members
    from orm.roles import AdminUserRoleRelation, AdminRoles


@API.route(api.BaseRoute+"/domains/<int:domainID>/users", methods=["GET"])
@secure(requireDB=True)
def userListEndpoint(domainID):
    checkPermissions(DomainAdminPermission(domainID))
    return defaultListHandler(Users, filters=(Users.domainID == domainID,))


@API.route(api.BaseRoute+"/domains/<int:domainID>/users", methods=["POST"])
@secure(requireDB=True)
def createUser(domainID):
    def rollback():
        DB.session.rollback()

    checkPermissions(DomainAdminPermission(domainID))
    data = request.get_json(silent=True) or {}
    areaID = data.get("areaID")
    data["domainID"] = domainID
    user = defaultListHandler(Users, result="object")
    if not isinstance(user, Users):
        return user  # If the return value is not a user, it is an error response
    area = AreaList.query.filter(AreaList.dataType == AreaList.USER, AreaList.ID == areaID).first()
    try:
        with AutoClean(rollback):
            DB.session.add(user)
            DB.session.flush()
            with UserSetup(user, area) as us:
                us.run()
            if not us.success:
                return jsonify(message="Error during user setup", error=us.error),  us.errorCode
            DB.session.commit()
            return jsonify(user.fulldesc()), 201
    except IntegrityError as err:
        return jsonify(message="Object violates database constraints", error=err.orig.args[1]), 400


@API.route(api.BaseRoute+"/domains/<int:domainID>/users/<int:userID>", methods=["GET"])
@secure(requireDB=True)
def userObjectEndpoint(domainID, userID):
    checkPermissions(DomainAdminPermission(domainID))
    return defaultObjectHandler(Users, userID, "User", filters=(Users.domainID == domainID,))


@API.route(api.BaseRoute+"/domains/<int:domainID>/users/<int:userID>", methods=["PATCH"])
@secure(requireDB=True)
def patchUser(domainID, userID):
    checkPermissions(DomainAdminPermission(domainID))
    user = Users.query.filter(Users.domainID == domainID, Users.ID == userID).first()
    if user is None:
        return jsonify(message="User not found"), 404
    if user.addressType != Users.NORMAL:
        return jsonify(message="Cannot edit alias user"), 400
    data = request.get_json(silent=True, cache=True)
    updateSize = user and data and "maxSize" in data and data["maxSize"] != user.maxSize
    aliasUserNames = Aliases.query.filter(Aliases.mainname == user.username).with_entities(Aliases.aliasname).all()
    aliasMatch = [alias[0].split("@")[0]+"@%" for alias in aliasUserNames]+[user.baseName()+"@%"]
    aliasUsers = Users.query.filter(Users.domainID == user.domainID, or_(Users.username.like(am) for am in aliasMatch)).all()
    try:
        defaultPatch(Users, userID, "User", user, (Users.domainID == domainID,), result="precommit")
        for alias in aliasUsers:
            alias.fromdict(data)
    except (InvalidAttributeError, MismatchROError) as err:
        DB.session.rollback()
        return jsonify(message=err.args[0]), 400
    try:
        DB.session.commit()
    except IntegrityError as err:
        DB.session.rollback()
        return jsonify(message="Could not update: invalid data", error=err.orig.args[1]), 400
    if updateSize:
        API.logger.info("Updating exmdb quotas")
        client = pyexmdb.ExmdbQueries("127.0.0.1", 5000, Config["options"]["userPrefix"], True)
        propvals = (pyexmdb.TaggedPropval_u64(PropTags.PROHIBITRECEIVEQUOTA, data["maxSize"]*1024),
                    pyexmdb.TaggedPropval_u64(PropTags.PROHIBITSENDQUOTA, data["maxSize"]*1024))
        status = client.setStoreProperties(user.maildir, 0, propvals)
        if len(status.problems):
            problems = ",\n".join("\t{}: {} - {}".format(problem.index, PropTags.lookup(problem.proptag), problem.err)
                                  for problem in status.problems)
            API.logger.error("Failed to adjust user quota:\n"+problems)
            return jsonify(message="Failed to set user quota"), 500
    return jsonify(user.fulldesc())


@API.route(api.BaseRoute+"/domains/<int:domainID>/users/<int:userID>", methods=["DELETE"])
@secure(requireDB=True)
def deleteUserEndpoint(domainID, userID):
    checkPermissions(DomainAdminPermission(domainID))
    user = Users.query.filter(Users.ID == userID, Users.domainID == domainID).first()
    if user is None:
        return jsonify(message="User #{} not found".format(userID)), 404
    return deleteUser(user)


def deleteUser(user):
    if user.addressType == Users.VIRTUAL:
        return jsonify(message="Cannot delete virtual user"), 400
    if user.ID == 0:
        return jsonify(message="Cannot delete superuser"), 400
    isAlias = user.addressType == Users.ALIAS
    maildir = user.maildir
    domainAliases = Aliases.query.filter(Aliases.mainname == user.domainName()).all()
    delQueries = [Users.query.filter(Users.domainID == user.domainID, Users.username.like(user.baseName()+"@%"))]
    if isAlias:
        delQueries.append(Aliases.query.filter(Aliases.aliasname == user.username))
    else:
        userAliases = Aliases.query.filter(Aliases.mainname == user.username).all()
        delQueries.append(Users.query.filter(Users.domainID == user.domainID,
                                             or_(Users.username.like(alias.aliasname.split("@")[0]+"@%")
                                                 for alias in userAliases)))
        delQueries.append(Aliases.query.filter(Aliases.mainname == user.username))
        Forwards.query.filter(Forwards.username == user.username).delete(synchronize_session=False)
        Members.query.filter(Members.username == user.username).delete(synchronize_session=False)
    Associations.query.filter(Associations.username == user.username).delete(synchronize_session=False)
    for query in delQueries:
        query.delete(synchronize_session=False)
    try:
        DB.session.commit()
    except:
        return jsonify(message="Cannot delete user: Database commit failed."), 500
    if not isAlias:
        try:
            client = pyexmdb.ExmdbQueries("127.0.0.1", 5000, Config["options"]["userPrefix"], True)
            client.unloadStore(maildir)
        except RuntimeError as err:
            API.logger.error("Could not unload exmdb store: "+err.args[0])
    if request.args.get("deleteFiles") == "true":
        shutil.rmtree(maildir, ignore_errors=True)
    return jsonify(message="isded")


@API.route(api.BaseRoute+"/domains/<int:domainID>/users/<int:userID>/password", methods=["PUT"])
@secure(requireDB=True)
def setUserPassword(domainID, userID):
    checkPermissions(DomainAdminPermission(domainID))
    user = Users.query.filter(Users.ID == userID, Users.domainID == domainID).first()
    if user is None:
        return jsonify(message="User not found"), 404
    data = request.get_json(silent=True)
    if data is None or "new" not in data:
        return jsonify(message="Incomplete data"), 400
    user.password = data["new"]
    DB.session.commit()
    return jsonify(message="Success")


@API.route(api.BaseRoute+"/domains/<int:domainID>/users/<int:userID>/aliases", methods=["GET"])
@secure(requireDB=True)
def userAliasListEndpoint(domainID, userID):
    checkPermissions(DomainAdminPermission(domainID))
    user = Users.query.filter(Users.ID == userID, Users.domainID == domainID).first()
    if user is None:
        return jsonify(message="User not found"), 404
    return defaultListHandler(Aliases, filters=(Aliases.mainname == user.username,))


@API.route(api.BaseRoute+"/domains/<int:domainID>/users/<int:userID>/aliases", methods=["POST"])
@secure(requireDB=True)
def createUserAlias(domainID, userID):
    checkPermissions(DomainAdminPermission(domainID))
    data = request.get_json(silent=True)
    if userID == 0:
        return jsonify(message="Cannot alias superuser"), 400
    if data is None or "aliasname" not in data:
        return jsonify("Missing alias name"), 400
    aliasname = data["aliasname"]
    user: Users = Users.query.filter(Users.ID == userID, Users.domainID == domainID).first()
    if user is None:
        return jsonify(message="User not found"), 404
    if user.addressType == Users.VIRTUAL:
        return jsonify(message="Cannot alias virtual user"), 400
    domain: Domains = Domains.query.filter(Domains.ID == domainID).first()
    if Users.query.filter(Users.domainID == domainID, Users.addressType == Users.ALIAS).count() > domain.maxUser:
        return jsonify(message="Maximum number of aliases reached"), 4000
    if "@" in aliasname:
        aliasBase, aliasDomain = aliasname.rsplit("@", 1)
        if aliasDomain != domain.domainname:
            return jsonify(message="Alias domain must match user domain")
    else:
        aliasBase = aliasname
        aliasname += "@"+domain.domainname
    aliasDomains = Aliases.query.filter(Aliases.mainname=="testdomain2")\
                                .join(Domains, Domains.domainname == Aliases.aliasname)\
                                .with_entities(Domains.domainname, Domains.domainStatus).all()
    alias = Aliases({"mainname": user.username, "aliasname": aliasname})
    DB.session.add(alias)
    DB.session.add(user.mkAlias(aliasname))
    for aliasDomain in aliasDomains:
        DB.session.add(user.mkAlias(aliasBase+"@"+aliasDomain.domainname, Users.VIRTUAL, aliasDomain.domainStatus))
    try:
        DB.session.commit()
    except IntegrityError as err:
        DB.session.rollback()
        return jsonify(message="Alias creation failed", error=err.orig.args[1])
    return jsonify(alias.fulldesc()), 201


@API.route(api.BaseRoute+"/domains/<int:domainID>/users/aliases", methods=["GET"])
@secure(requireDB=True)
def getAliasesByUser(domainID):
    checkPermissions(DomainAdminPermission(domainID))
    aliases = Aliases.query.join(Users, Users.username == Aliases.aliasname).filter(Users.domainID==domainID).all()
    return jsonify(data=createMapping(aliases,
                                      lambda alias: alias.mainname,
                                      lambda alias: {"ID": alias.ID, "aliasname": alias.aliasname}))


@API.route(api.BaseRoute+"/domains/<int:domainID>/users/aliases/<int:ID>", methods=["DELETE"])
@secure(requireDB=True)
def deleteUserAlias(domainID, ID):
    checkPermissions(DomainAdminPermission(domainID))
    alias = Aliases.query.filter(Aliases.ID == ID).first()
    if alias is None:
        return jsonify(message="Alias not found"), 404
    if alias is None:
        return jsonify(message="User not found"), 404
    user = Users.query.filter(Users.domainID == domainID, Users.username == alias.aliasname).first()
    return deleteUser(user)


@API.route(api.BaseRoute+"/domains/<int:domainID>/users/<int:userID>/roles", methods=["PATCH"])
@secure(requireDB=True)
def updateUserRoles(domainID, userID):
    checkPermissions(SystemAdminPermission())
    data = request.get_json(silent=True)
    if data is None or "roles" not in data:
        return jsonify(message="Missing roles array"), 400
    roles = {role.roleID for role in AdminUserRoleRelation.query.filter(AdminUserRoleRelation.userID == userID).all()}
    requested = set(data["roles"])
    remove = roles-requested
    add = requested-roles
    AdminUserRoleRelation.query.filter(AdminUserRoleRelation.userID == userID, AdminUserRoleRelation.roleID.in_(remove))\
                               .delete(synchronize_session=False)
    for ID in add:
        DB.session.add(AdminUserRoleRelation(userID, ID))
    try:
        DB.session.commit()
    except IntegrityError as err:
        return jsonify(message="Invalid data", error=err.orig.args[1]), 400
    roles = AdminRoles.query.join(AdminUserRoleRelation).filter(AdminUserRoleRelation.userID == userID).all()
    return jsonify(data=[role.ref() for role in roles])


##############################################################################################################################


@API.route(api.BaseRoute+"/domains/<int:domainID>/groups", methods=["GET"])
@secure(requireDB=True)
def getGroups(domainID):
    checkPermissions(DomainAdminPermission(domainID))
    return defaultListHandler(Groups, filters=(Groups.domainID == domainID,))


@API.route(api.BaseRoute+"/domains/<int:domainID>/groups", methods=["POST"])
@secure(requireDB=True)
def createGroup(domainID):
    checkPermissions(DomainAdminPermission(domainID))
    data = request.get_json(silent=True, cache=True) or {}
    data["domainID"] = domainID
    return defaultListHandler(Groups)


@API.route(api.BaseRoute+"/domains/<int:domainID>/groups/<int:ID>", methods=["DELETE"])
@secure(requireDB=True)
def deleteGroup(domainID, ID):
    checkPermissions(DomainAdminPermission(domainID))
    group = Groups.query.filter(Groups.domainID == domainID, Groups.ID == ID).first()
    if group is None:
        return jsonify(message="Group not found"), 404
    Users.query.filter(Users.groupID == ID).update({Users.groupID: 0,
                                                    Users.privilegeBits: Users.privilegeBits.op("&")(0xFF00FF)+0x00FF00,
                                                    Users.addressStatus: Users.addressStatus.op("&")(0x33)},
                                                   synchronize_session=False)
    DB.session.delete(group)
    DB.session.commit()
    return jsonify(message="Group deleted")


@API.route(api.BaseRoute+"/domains/<int:domainID>/groups/<int:ID>", methods=["GET"])
@secure(requireDB=True)
def getGroup(domainID, ID):
    checkPermissions(DomainAdminPermission(domainID))
    return defaultObjectHandler(Groups, ID, "Group", filters=(Groups.domainID == domainID,))


@API.route(api.BaseRoute+"/domains/<int:domainID>/groups/<int:ID>", methods=["PATCH"])
@secure(requireDB=True)
def updateGroup(domainID, ID):
    checkPermissions(DomainAdminPermission(domainID))
    group = Groups.query.filter(Groups.domainID == domainID, Groups.ID == ID).first()
    oldPrivileges, oldStatus = group.privilegeBits, group.groupStatus
    if group is None:
        return jsonify(message="Group not found"), 404
    patched = defaultPatch(Groups, ID, "Group", group, filters=(Groups.domainID == domainID,), result="precommit")
    if not patched == group:
        return patched
    if group.privilegeBits != oldPrivileges or group.groupStatus != oldStatus:
        Users.query.filter(Users.groupID == ID)\
                   .update({Users.addressStatus: Users.privilegeBits.op("&")(0xFF00FF)+(group.privilegeBits<<8),
                            Users.privilegeBits: Users.privilegeBits.op("&")(0x33)+(group.privilegeBits<<2)},
                           synchronize_session=False)
    try:
        DB.session.commit()
    except IntegrityError as err:
        DB.session.rollback()
        return jsonify(message="Domain update failed", error=err.orig.args[1])
    return jsonify(group.fulldesc())
