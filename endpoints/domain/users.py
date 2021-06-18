# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020-2021 grammm GmbH

import api

from api.core import API, secure
from api.security import checkPermissions
from datetime import datetime
from flask import request, jsonify
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased

from .. import defaultListHandler, defaultObjectHandler

from tools.misc import createMapping
from tools.pyexmdb import pyexmdb
from tools.config import Config
from tools.constants import PropTags, PropTypes, ExchangeErrors, ExmdbCodes
from tools.permissions import SystemAdminPermission, DomainAdminPermission
from tools.rop import nxTime

import shutil

from orm import DB
if DB is not None:
    from orm.users import Users, UserProperties
    from orm.roles import AdminUserRoleRelation, AdminRoles


@API.route(api.BaseRoute+"/domains/<int:domainID>/users", methods=["GET"])
@secure(requireDB=True)
def getUsers(domainID):
    checkPermissions(DomainAdminPermission(domainID))
    verbosity = int(request.args.get("level", 1))
    query, limit, offset, count = defaultListHandler(Users, filters=(Users.domainID == domainID,), result="query")
    sorts = request.args.getlist("sort")
    for s in sorts:
        sprop, sorder = s.split(",", 1) if "," in s else (s, "asc")
        if hasattr(PropTags, sprop.upper()):
            up = aliased(UserProperties)
            query = query.join(up, (up.userID == Users.ID) & (up.tag == getattr(PropTags, sprop.upper())))\
                         .order_by(up._propvalstr.desc() if sorder == "desc" else up._propvalstr.asc())
    data = [user.todict(verbosity) for user in query.limit(limit).offset(offset).all()]
    if verbosity < 2 and "properties" in request.args:
        tags = [getattr(PropTags, prop.upper(), None) for prop in request.args["properties"].split(",")]
        for user in data:
            user["properties"] = {}
        usermap = createMapping(data, lambda x: x["ID"])
        properties = UserProperties.query.filter(UserProperties.userID.in_(usermap.keys()), UserProperties.tag.in_(tags)).all()
        for prop in properties:
            usermap[prop.userID]["properties"][prop.name] = prop.val
    return jsonify(count=count, data=data)


@API.route(api.BaseRoute+"/domains/<int:domainID>/users", methods=["POST"])
@secure(requireDB=True)
def createUser(domainID):
    checkPermissions(DomainAdminPermission(domainID))
    data = request.get_json(silent=True) or {}
    data["domainID"] = domainID
    result, code = Users.create(data, reloadGromoxHttp=True)
    if code != 201:
        return jsonify(message=result), code
    return jsonify(result.fulldesc()), 201


@API.route(api.BaseRoute+"/domains/<int:domainID>/users/<int:userID>", methods=["GET", "PATCH"])
@secure(requireDB=True)
def userObjectEndpoint(domainID, userID):
    checkPermissions(DomainAdminPermission(domainID))
    return defaultObjectHandler(Users, userID, "User", filters=(Users.domainID == domainID,))


@API.route(api.BaseRoute+"/domains/<int:domainID>/users/<int:userID>", methods=["DELETE"])
@secure(requireDB=True)
def deleteUserEndpoint(domainID, userID):
    checkPermissions(DomainAdminPermission(domainID))
    user = Users.query.filter(Users.ID == userID, Users.domainID == domainID).first()
    if user is None:
        return jsonify(message="User #{} not found".format(userID)), 404
    return deleteUser(user)


def deleteUser(user):
    if user.ID == 0:
        return jsonify(message="Cannot delete superuser"), 400
    maildir = user.maildir
    user.delete()
    try:
        DB.session.commit()
    except:
        return jsonify(message="Cannot delete user: Database commit failed."), 500
    try:
        options = Config["options"]
        client = pyexmdb.ExmdbQueries(options["exmdbHost"], options["exmdbPort"], options["domainPrefix"], True)
        client.unloadStore(maildir)
    except pyexmdb.ExmdbError as err:
        API.logger.error("Could not unload exmdb store: "+ExmdbCodes.lookup(err.code, hex(err.code)))
    except RuntimeError as err:
        API.logger.error("Could not unload exmdb store: "+err.args[0])
    if request.args.get("deleteFiles") == "true":
        shutil.rmtree(maildir, ignore_errors=True)
    return jsonify(message="isded")


@API.route(api.BaseRoute+"/domains/<int:domainID>/users/<int:userID>/password", methods=["PUT"])
@secure(requireDB=True, authLevel="user")
def setUserPassword(domainID, userID):
    checkPermissions(DomainAdminPermission(domainID))
    if userID == request.auth["user"].ID:
        return jsonify(message="Cannot reset own password, use '/passwd' endpoint instead"), 400
    user = Users.query.filter(Users.ID == userID, Users.domainID == domainID).first()
    if user is None:
        return jsonify(message="User not found"), 404
    if user.externID is not None:
        return jsonify(message="Cannot modify LDAP imported user"), 400
    data = request.get_json(silent=True)
    if data is None or "new" not in data:
        return jsonify(message="Incomplete data"), 400
    user.password = data["new"]
    DB.session.commit()
    return jsonify(message="Success")


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


@API.route(api.BaseRoute+"/domains/<int:domainID>/users/<int:userID>/storeProps", methods=["GET", "DELETE"])
@secure(requireDB=True)
def rdUserStoreProps(domainID, userID):
    checkPermissions(DomainAdminPermission(domainID))
    user = Users.query.filter(Users.ID == userID, Users.domainID == domainID).with_entities(Users.maildir).first()
    if user is None:
        return jsonify(message="User not found"), 404
    props = [prop for prop in request.args.get("properties", "").split(",") if prop != ""]
    if len(props) == 0:
        return jsonify(data={})
    for i in range(len(props)):
        if not hasattr(PropTags, props[i].upper()) or not isinstance(getattr(PropTags, props[i].upper()), int):
            return jsonify(message="Unknown property '{}'".format(props[i])), 400
        props[i] = getattr(PropTags, props[i].upper())
    try:
        options = Config["options"]
        client = pyexmdb.ExmdbQueries(options["exmdbHost"], options["exmdbPort"], options["userPrefix"], True)
        if request.method == "DELETE":
            client.removeStoreProperties(user.maildir, props)
            return jsonify(message="Success.")
        response = client.getStoreProperties(user.maildir, 0, props)
    except pyexmdb.ExmdbError as err:
        return jsonify(message="exmdb query failed with code "+ExmdbCodes.lookup(err.code, hex(err.code))), 500
    except RuntimeError as err:
        return jsonify(message="exmdb query failed: "+err.args[0]), 500
    respData = {}
    for propval in response.propvals:
        propname = PropTags.lookup(propval.tag).lower()
        if propval.tag & 0xFFFF == PropTypes.FILETIME:
            respData[propname] = datetime.fromtimestamp(nxTime(int(propval.toString()))).strftime("%Y-%m-%d %H:%M:%S")
        else:
            respData[propname] = PropTypes.pyType(propval.tag)(propval.toString())
    return jsonify(data=respData)


@API.route(api.BaseRoute+"/domains/<int:domainID>/users/<int:userID>/storeProps", methods=["PATCH"])
@secure(requireDB=True)
def setUserStoreProps(domainID, userID):
    checkPermissions(DomainAdminPermission(domainID))
    user = Users.query.filter(Users.ID == userID, Users.domainID == domainID).with_entities(Users.maildir).first()
    data = request.get_json(silent=True)
    if data is None or len(data) == 0:
        return jsonify(message="Missing data"), 400
    if user is None:
        return jsonify(message="User not found"), 404
    if not user.maildir:
        return jsonify(message="User has no store"), 400
    errors = {}
    propvals = []
    for prop, val in data.items():
        tag = getattr(PropTags, prop.upper(), None)
        if tag is None:
            errors[prop] = "Unknown tag"
            continue
        tagtype = tag & 0xFFFF
        if not isinstance(val, PropTypes.pyType(tagtype)):
                errors[prop] = "Invalid type"
                continue
        if tagtype in (PropTypes.STRING, PropTypes.WSTRING):
            propvals.append(pyexmdb.TaggedPropval_str(tag, val))
        elif tagtype in PropTypes.intTypes:
            propvals.append(pyexmdb.TaggedPropval_u64(tag, val))
        else:
            errors[prop] = "Unsupported type"
    try:
        options = Config["options"]
        client = pyexmdb.ExmdbQueries(options["exmdbHost"], options["exmdbPort"], user.maildir, True)
        result = client.setStoreProperties(user.maildir, 0, propvals)
        for entry in result.problems:
            tag = PropTags.lookup(entry.proptag, hex(entry.proptag)).lower()
            err = ExchangeErrors.lookup(entry.err, hex(entry.err))
            errors[tag] = err
        if len(errors) != 0:
            API.logger.warn("Failed to set proptags: "+", ".join("{} ({})".format(tag, err) for tag, err in errors.items()))
        return jsonify(message="Great success!" if len(errors) == 0 else "Some tags could not be set", errors=errors)
    except pyexmdb.ExmdbError as err:
        return jsonify(message="exmdb query failed with code "+ExmdbCodes.lookup(err.code, hex(err.code))), 500
    except RuntimeError as err:
        return jsonify(message="exmdb query failed: "+err.args[0]), 500
