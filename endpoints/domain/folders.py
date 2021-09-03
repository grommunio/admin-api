# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020-2021 grommunio GmbH

import api
from api.core import API, secure
from api.security import checkPermissions

from flask import request, jsonify

from services import Service

from tools.constants import Permissions, PropTags, EcErrors
from tools.permissions import DomainAdminPermission, DomainAdminROPermission
from tools.rop import nxTime

from datetime import datetime


@API.route(api.BaseRoute+"/domains/<int:domainID>/folders", methods=["GET"])
@secure(requireDB=True)
def getPublicFoldersList(domainID):
    checkPermissions(DomainAdminROPermission(domainID))
    from orm.domains import Domains
    domain = Domains.query.filter(Domains.ID == domainID).first()
    if domain is None:
        return jsonify(message="Domain not found"), 404
    with Service("exmdb") as exmdb:
        client = exmdb.ExmdbQueries(exmdb.host, exmdb.port, domain.homedir, False)
        response = exmdb.FolderListResponse(client.getFolderList(domain.homedir))
    folders = [{"folderid": str(entry.folderId),
                "displayname": entry.displayName,
                "comment": entry.comment,
                "creationtime": datetime.fromtimestamp(nxTime(entry.creationTime)).strftime("%Y-%m-%d %H:%M:%S"),
                "container": entry.container}
               for entry in response.folders]
    return jsonify(data=folders)


@API.route(api.BaseRoute+"/domains/<int:domainID>/folders", methods=["POST"])
@secure(requireDB=True)
def createPublicFolder(domainID):
    checkPermissions(DomainAdminPermission(domainID))
    from orm.domains import Domains
    domain = Domains.query.filter(Domains.ID == domainID).first()
    if domain is None:
        return jsonify(message="Domain not found"), 404
    data = request.json
    with Service("exmdb") as exmdb:
        client = exmdb.ExmdbQueries(exmdb.host, exmdb.port, domain.homedir, False)
        response = client.createFolder(domain.homedir, domain.ID, data["displayname"], data["container"], data["comment"])
    if response.folderId == 0:
        return jsonify(message="Folder creation failed"), 500
    return jsonify(folderid=str(response.folderId),
                   displayname=data["displayname"],
                   comment=data["comment"],
                   creationtime=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                   container=data["container"]), 201


@API.route(api.BaseRoute+"/domains/<int:domainID>/folders/<int:folderID>", methods=["GET"])
@secure(requireDB=True)
def getPublicFolder(domainID, folderID):
    checkPermissions(DomainAdminROPermission(domainID))
    from orm.domains import Domains
    domain = Domains.query.filter(Domains.ID == domainID).first()
    if domain is None:
        return jsonify(message="Domain not found"), 404
    with Service("exmdb") as exmdb:
        client = exmdb.ExmdbQueries(exmdb.host, exmdb.port, domain.homedir, False)
        response = exmdb.Folder(client.getFolderProperties(domain.homedir, 0, folderID))
    return jsonify({"folderid": str(response.folderId),
                    "displayname": response.displayName,
                    "comment": response.comment,
                    "creationtime": datetime.fromtimestamp(nxTime(response.creationTime)).strftime("%Y-%m-%d %H:%M:%S"),
                    "container": response.container})


@API.route(api.BaseRoute+"/domains/<int:domainID>/folders/<int:folderID>", methods=["PATCH"])
@secure(requireDB=True)
def updatePublicFolder(domainID, folderID):
    checkPermissions(DomainAdminPermission(domainID))
    from orm.domains import Domains
    domain = Domains.query.filter(Domains.ID == domainID).first()
    if domain is None:
        return jsonify(message="Domain not found"), 404
    data = request.get_json(silent=True) or {}
    supported = ((PropTags.COMMENT, "comment"), (PropTags.DISPLAYNAME, "displayname"), (PropTags.CONTAINERCLASS, "container"))
    with Service("exmdb") as exmdb:
        proptags = [exmdb.TaggedPropval_str(tag, data[tagname]) for tag, tagname in supported if tagname in data]
        if not len(proptags):
            return jsonify(message="Nothing to do")
        client = exmdb.ExmdbQueries(exmdb.host, exmdb.port, domain.homedir, False)
        response = client.setFolderProperties(domain.homedir, 0, folderID, proptags)
        if len(response.problems):
            errors = ["{} ({})".format(PropTags.lookup(problem.proptag, hex(problem.proptag)).lower(),
                                       EcErrors.lookup(problem.err, hex(problem.err))) for problem in response.problems]
            return jsonify(message="Update failed for tag{} {}".format("" if len(errors) == 1 else "s",
                                                                       ", ".join(errors))), 500
    return jsonify(message="Success.")


@API.route(api.BaseRoute+"/domains/<int:domainID>/folders/<int:folderID>", methods=["DELETE"])
@secure(requireDB=True)
def deletePublicFolder(domainID, folderID):
    checkPermissions(DomainAdminPermission(domainID))
    from orm.domains import Domains
    domain = Domains.query.filter(Domains.ID == domainID).first()
    if domain is None:
        return jsonify(message="Domain not found"), 404
    with Service("exmdb") as exmdb:
        client = exmdb.ExmdbQueries(exmdb.host, exmdb.port, domain.homedir, False)
        response = client.deleteFolder(domain.homedir, folderID)
    if not response.success:
        return jsonify(message="Folder deletion failed"), 500
    return jsonify(message="Success")


@API.route(api.BaseRoute+"/domains/<int:domainID>/folders/<int:folderID>/owners", methods=["GET"])
@secure(requireDB=True)
def getPublicFolderOwnerList(domainID, folderID):
    checkPermissions(DomainAdminROPermission(domainID))
    from orm.domains import Domains
    domain = Domains.query.filter(Domains.ID == domainID).first()
    if domain is None:
        return jsonify(message="Domain not found"), 404
    with Service("exmdb") as exmdb:
        client = exmdb.ExmdbQueries(exmdb.host, exmdb.port, domain.homedir, False)
        response = exmdb.FolderOwnerListResponse(client.getFolderOwnerList(domain.homedir, folderID))
    owners = [{"memberID": owner.memberId, "displayName": owner.memberName}
              for owner in response.owners
              if owner.memberRights & Permissions.FOLDEROWNER and owner.memberId not in (0, 0xFFFFFFFFFFFFFFFF)]
    return jsonify(data=owners)


@API.route(api.BaseRoute+"/domains/<int:domainID>/folders/<int:folderID>/owners", methods=["POST"])
@secure(requireDB=True)
def addPublicFolderOwner(domainID, folderID):
    checkPermissions(DomainAdminPermission(domainID))
    from orm.domains import Domains
    data = request.get_json(silent=True)
    if data is None or "username" not in data:
        return jsonify(message="Missing required parameter 'username'"), 400
    domain = Domains.query.filter(Domains.ID == domainID).first()
    if domain is None:
        return jsonify(message="Domain not found"), 404
    with Service("exmdb") as exmdb:
        client = exmdb.ExmdbQueries(exmdb.host, exmdb.port, domain.homedir, False)
        client.addFolderOwner(domain.homedir, folderID, data["username"])
    return jsonify(message="Success"), 201


@API.route(api.BaseRoute+"/domains/<int:domainID>/folders/<int:folderID>/owners/<int:memberID>", methods=["DELETE"])
@secure(requireDB=True)
def deletePublicFolderOwner(domainID, folderID, memberID):
    checkPermissions(DomainAdminPermission(domainID))
    from orm.domains import Domains
    domain = Domains.query.filter(Domains.ID == domainID).first()
    if domain is None:
        return jsonify(message="Domain not found"), 404
    with Service("exmdb") as exmdb:
        client = exmdb.ExmdbQueries(exmdb.host, exmdb.port, domain.homedir, False)
        client.deleteFolderOwner(domain.homedir, folderID, memberID)
    return jsonify(message="Success"), 200
