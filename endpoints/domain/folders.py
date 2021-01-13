# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020-2021 grammm GmbH

import api
from api.core import API, secure
from api.security import checkPermissions

from flask import request, jsonify
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from tools.config import Config
from tools.constants import Permissions, ExmdbCodes
from tools.permissions import DomainAdminPermission
from tools.pyexmdb import pyexmdb
from tools.rop import nxTime

from datetime import datetime

from orm import DB
if DB is not None:
    from orm.domains import Domains


@API.route(api.BaseRoute+"/domains/<int:domainID>/folders", methods=["GET"])
@secure(requireDB=True)
def getPublicFoldersList(domainID):
    checkPermissions(DomainAdminPermission(domainID))
    domain = Domains.query.filter(Domains.ID == domainID).first()
    if domain is None:
        return jsonify(message="Domain not found"), 404
    options = Config["options"]
    try:
        client = pyexmdb.ExmdbQueries(options["exmdbHost"], options["exmdbPort"], options["domainPrefix"], False)
        response = pyexmdb.FolderListResponse(client.getFolderList(domain.homedir))
    except pyexmdb.ExmdbError as err:
        return jsonify(message="exmdb query failed with code "+ExmdbCodes.lookup(err.code, hex(err.code))), 500
    folders = [{"folderid": entry.folderId,
                "displayname": entry.displayName,
                "comment": entry.comment,
                "creationtime": datetime.fromtimestamp(nxTime(entry.creationTime)).strftime("%Y-%m-%d %H:%M:%S")}
               for entry in response.folders]
    return jsonify(data=folders)


@API.route(api.BaseRoute+"/domains/<int:domainID>/folders", methods=["POST"])
@secure(requireDB=True)
def createPublicFolder(domainID):
    checkPermissions(DomainAdminPermission(domainID))
    options = Config["options"]
    domain = Domains.query.filter(Domains.ID == domainID).first()
    if domain is None:
        return jsonify(message="Domain not found"), 404
    data = request.json
    try:
        client = pyexmdb.ExmdbQueries(options["exmdbHost"], options["exmdbPort"], options["domainPrefix"], False)
        response = client.createPublicFolder(domain.homedir, domain.ID, data["displayname"], data["container"], data["comment"])
    except pyexmdb.ExmdbError as err:
        return jsonify(message="exmdb query failed with code "+ExmdbCodes.lookup(err.code, hex(err.code))), 500
    if response.folderId == 0:
        return jsonify(message="Folder creation failed"), 500
    return jsonify(folderid=response.folderId,
                   displayname=data["displayname"],
                   comment=data["comment"],
                   creationtime=datetime.now().strftime("%Y-%m-%d %H:%M:%S")), 201


@API.route(api.BaseRoute+"/domains/<int:domainID>/folders/<int:folderID>", methods=["DELETE"])
@secure(requireDB=True)
def deletePublicFolder(domainID, folderID):
    checkPermissions(DomainAdminPermission(domainID))
    options = Config["options"]
    domain = Domains.query.filter(Domains.ID == domainID).first()
    if domain is None:
        return jsonify(message="Domain not found"), 404
    try:
        client = pyexmdb.ExmdbQueries(options["exmdbHost"], options["exmdbPort"], options["domainPrefix"], False)
        response = client.deletePublicFolder(domain.homedir, folderID)
    except pyexmdb.ExmdbError as err:
        return jsonify(message="exmdb query failed with code "+ExmdbCodes.lookup(err.code, hex(err.code))), 500
    if not response.success:
        return jsonify(message="Folder deletion failed"), 500
    return jsonify(message="Success")


@API.route(api.BaseRoute+"/domains/<int:domainID>/folders/<int:folderID>/owners", methods=["GET"])
@secure(requireDB=True)
def getPublicFolderOwnerList(domainID, folderID):
    checkPermissions(DomainAdminPermission(domainID))
    options = Config["options"]
    domain = Domains.query.filter(Domains.ID == domainID).first()
    if domain is None:
        return jsonify(message="Domain not found"), 404
    try:
        client = pyexmdb.ExmdbQueries(options["exmdbHost"], options["exmdbPort"], options["domainPrefix"], False)
        response = pyexmdb.FolderOwnerListResponse(client.getPublicFolderOwnerList(domain.homedir, folderID))
    except pyexmdb.ExmdbError as err:
        return jsonify(message="exmdb query failed with code "+ExmdbCodes.lookup(err.code, hex(err.code))), 500
    owners = [{"memberID": owner.memberId, "displayName": owner.memberName}
              for owner in response.owners
              if owner.memberRights & Permissions.FOLDEROWNER and owner.memberId not in (0, 0xFFFFFFFFFFFFFFFF)]
    return jsonify(data=owners)


@API.route(api.BaseRoute+"/domains/<int:domainID>/folders/<int:folderID>/owners", methods=["POST"])
@secure(requireDB=True)
def addPublicFolderOwner(domainID, folderID):
    checkPermissions(DomainAdminPermission(domainID))
    options = Config["options"]
    data = request.get_json(silent=True)
    if data is None or "username" not in data:
        return jsonify(message="Missing required parameter 'username'"), 400
    domain = Domains.query.filter(Domains.ID == domainID).first()
    if domain is None:
        return jsonify(message="Domain not found"), 404
    try:
        client = pyexmdb.ExmdbQueries(options["exmdbHost"], options["exmdbPort"], options["domainPrefix"], False)
        response = client.addFolderOwner(domain.homedir, folderID, data["username"])
    except pyexmdb.ExmdbError as err:
        return jsonify(message="exmdb query failed with code "+ExmdbCodes.lookup(err.code, hex(err.code))), 500
    return jsonify(message="Success"), 201


@API.route(api.BaseRoute+"/domains/<int:domainID>/folders/<int:folderID>/owners/<int:memberID>", methods=["DELETE"])
@secure(requireDB=True)
def deletePublicFolderOwner(domainID, folderID, memberID):
    checkPermissions(DomainAdminPermission(domainID))
    options = Config["options"]
    domain = Domains.query.filter(Domains.ID == domainID).first()
    if domain is None:
        return jsonify(message="Domain not found"), 404
    try:
        client = pyexmdb.ExmdbQueries(options["exmdbHost"], options["exmdbPort"], options["domainPrefix"], False)
        response = client.deleteFolderOwner(domain.homedir, folderID, memberID)
    except pyexmdb.ExmdbError as err:
        return jsonify(message="exmdb query failed with code "+ExmdbCodes.lookup(err.code, hex(err.code))), 500
    return jsonify(message="Success"), 200
