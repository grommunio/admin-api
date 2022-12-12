# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020-2021 grommunio GmbH

import api
from api.core import API, secure
from api.security import checkPermissions

from flask import request, jsonify

from services import Service

from tools.constants import PropTags, PropTypes, ExchangeErrors, PublicFIDs
from tools.permissions import DomainAdminPermission, DomainAdminROPermission
from tools.rop import nxTime, makeEidEx
from tools.tasq import TasQServer

from datetime import datetime


def folderToDict(folder):
    return {"folderid": str(folder.folderId),
            "displayname": folder.displayName,
            "comment": folder.comment,
            "creationtime": datetime.fromtimestamp(nxTime(folder.creationTime)).strftime("%Y-%m-%d %H:%M:%S"),
            "container": folder.container,
            "syncMobile": folder.syncToMobile}


def setPublicFolderMobileSync(exmdb, client, domainname, folderId, value):
    synctomobile = client.resolveNamedProperties(True, [exmdb.PropertyName(exmdb.GUID.PSETID_GROMOX, "synctomobile")])[0]
    synctomobile = (synctomobile << 16) | PropTypes.BYTE
    if not synctomobile:
        return
    problems = client.setFolderProperties(0, folderId, [exmdb.TaggedPropval(synctomobile, value)])
    with Service("redis") as redis:
        redis.delete("grommunio-sync:sharedfolders-"+domainname)
    return problems


@API.route(api.BaseRoute+"/domains/<int:domainID>/folders", methods=["GET"])
@secure(requireDB=True)
def getPublicFoldersList(domainID):
    checkPermissions(DomainAdminROPermission(domainID))
    from orm.domains import Domains
    domain = Domains.query.filter(Domains.ID == domainID).first()
    if domain is None:
        return jsonify(message="Domain not found"), 404
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))
    parent = int(request.args.get("parentID", makeEidEx(1, PublicFIDs.IPMSUBTREE)))
    with Service("exmdb") as exmdb:
        if "match" in request.args:
            fuzzyLevel = exmdb.Restriction.FL_SUBSTRING | exmdb.Restriction.FL_IGNORECASE
            match = request.args["match"]
            restriction = exmdb.Restriction.OR([
                exmdb.Restriction.CONTENT(fuzzyLevel, 0, exmdb.TaggedPropval(PropTags.DISPLAYNAME, match)),
                exmdb.Restriction.CONTENT(fuzzyLevel, 0, exmdb.TaggedPropval(PropTags.COMMENT, match))])
        else:
            restriction = exmdb.Restriction.NULL()
        client = exmdb.domain(domain)
        synctomobile = client.resolveNamedProperties(True, [exmdb.PropertyName(exmdb.GUID.PSETID_GROMOX, "synctomobile")])[0]
        synctomobile = (synctomobile << 16) | PropTypes.BYTE
        response = exmdb.FolderList(client.listFolders(parent, limit=limit, offset=offset, restriction=restriction,
                                                       proptags=client.defaultFolderProps+[synctomobile]), synctomobile)
    folders = [folderToDict(entry) for entry in response.folders]
    return jsonify(data=folders)


@API.route(api.BaseRoute+"/domains/<int:domainID>/folders/tree", methods=["GET"])
@secure(requireDB=True)
def getFolderTree(domainID):
    checkPermissions(DomainAdminROPermission(domainID))
    from orm.domains import Domains
    domain = Domains.query.filter(Domains.ID == domainID).first()
    if domain is None:
        return jsonify(message="Domain not found"), 404
    parentID = int(request.args.get("folderID", makeEidEx(1, PublicFIDs.IPMSUBTREE)))
    tags = (PropTags.FOLDERID, PropTags.PARENTFOLDERID, PropTags.DISPLAYNAME, PropTags.CONTAINERCLASS)
    with Service("exmdb") as exmdb:
        client = exmdb.domain(domain)
        parent = exmdb.Folder(client.getFolderProperties(0, parentID, tags))
        folders = exmdb.FolderList(client.listFolders(parentID, True, tags))
    idmap = {folder.folderId: {"folderid": str(folder.folderId), "name": folder.displayName, "container": folder.container}
             for folder in folders.folders}
    idmap[parentID] = {"folderid": str(parent.folderId), "name": parent.displayName}
    for folder in folders.folders:
        parentFolder = idmap[folder.parentId]
        if "children" not in parentFolder:
            parentFolder["children"] = []
        parentFolder["children"].append(idmap[folder.folderId])
    return jsonify(idmap[parentID])


@API.route(api.BaseRoute+"/domains/<int:domainID>/folders", methods=["POST"])
@secure(requireDB=True)
def createPublicFolder(domainID):
    checkPermissions(DomainAdminPermission(domainID))
    from orm.domains import Domains
    domain = Domains.query.filter(Domains.ID == domainID).first()
    if domain is None:
        return jsonify(message="Domain not found"), 404
    data = request.json
    parentID = int(data.get("parentID") or makeEidEx(1, PublicFIDs.IPMSUBTREE))
    with Service("exmdb") as exmdb:
        client = exmdb.domain(domain)
        folderId = client.createFolder(domain.ID, data["displayname"], data["container"], data["comment"], parentID)
        if folderId == 0:
            return jsonify(message="Folder creation failed"), 500
        if "syncMobile" in data:
            setPublicFolderMobileSync(exmdb, client, domain.domainname, folderId, data["syncMobile"])
    return jsonify(folderid=str(folderId),
                   displayname=data["displayname"],
                   comment=data["comment"],
                   creationtime=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                   container=data["container"],
                   syncMobile=data.get("syncMobile")), 201


@API.route(api.BaseRoute+"/domains/<int:domainID>/folders/<int:folderID>", methods=["GET"])
@secure(requireDB=True)
def getPublicFolder(domainID, folderID):
    checkPermissions(DomainAdminROPermission(domainID))
    from orm.domains import Domains
    domain = Domains.query.filter(Domains.ID == domainID).first()
    if domain is None:
        return jsonify(message="Domain not found"), 404
    with Service("exmdb") as exmdb:
        client = exmdb.domain(domain)
        synctomobile = client.resolveNamedProperties(True, [exmdb.PropertyName(exmdb.GUID.PSETID_GROMOX, "synctomobile")])[0]
        synctomobile = (synctomobile << 16) | PropTypes.BYTE
        response = exmdb.Folder(client.getFolderProperties(0, folderID, client.defaultFolderProps+[synctomobile]),
                                synctomobile)
    return jsonify(folderToDict(response))


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
        proptags = [exmdb.TaggedPropval(tag, data[tagname]) for tag, tagname in supported if tagname in data]
        if not len(proptags) and "syncMobile" not in data:
            return jsonify(message="Nothing to do")
        client = exmdb.domain(domain)
        problems = client.setFolderProperties(0, folderID, proptags)
        if "syncMobile" in data:
            problems += setPublicFolderMobileSync(exmdb, client, domain.domainname, folderID, data["syncMobile"])
        if len(problems):
            errors = ["{} ({})".format(PropTags.lookup(problem.proptag, hex(problem.proptag)).lower(),
                                       ExchangeErrors.lookup(problem.err, hex(problem.err))) for problem in problems]
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
    task = TasQServer.mktask.deleteFolder(domain.homedir, folderID, False, request.args.get("clear") == "true",
                                          DomainAdminROPermission(domainID), domain.homeserver)
    timeout = float(request.args.get("timeout", 1))
    if timeout > 0:
        TasQServer.wait(task.ID, timeout)
    if not task.done:
        return jsonify(message="Created background task #"+str(task.ID), taskID=task.ID), 202
    if task.state == task.COMPLETED:
        return jsonify(message="Success")
    return jsonify(message="Folder deletion failed: "+task.message), 500


@API.route(api.BaseRoute+"/domains/<int:domainID>/folders/<int:folderID>/owners", methods=["GET"])
@secure(requireDB=True)
def getPublicFolderOwnerList(domainID, folderID):
    checkPermissions(DomainAdminROPermission(domainID))
    from orm.domains import Domains
    domain = Domains.query.filter(Domains.ID == domainID).first()
    if domain is None:
        return jsonify(message="Domain not found"), 404
    with Service("exmdb") as exmdb:
        client = exmdb.domain(domain)
        response = exmdb.FolderMemberList(client.getFolderMemberList(folderID))
    owners = [{"memberID": member.id, "displayName": member.name, "username": member.mail, "permissions": member.rights}
              for member in response.members if not member.special]
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
        client = client = exmdb.domain(domain)
        client.setFolderMember(folderID, data["username"], data.get("permissions", client.ownerRights))
    with Service("redis") as redis:
        redis.delete("grommunio-sync:sharedfolders-"+domain.domainname)
    return jsonify(message="Success"), 201


@API.route(api.BaseRoute+"/domains/<int:domainID>/folders/<int:folderID>/owners/<int:memberID>", methods=["PUT"])
@secure(requireDB=True)
def updatePublicFolderOwner(domainID, folderID, memberID):
    checkPermissions(DomainAdminPermission(domainID))
    from orm.domains import Domains
    domain = Domains.query.filter(Domains.ID == domainID).first()
    if domain is None:
        return jsonify(message="Domain not found"), 404
    data = request.get_json(silent=True)
    if data is None or "permissions" not in data:
        return jsonify(message="Missing required data parameter 'permissions'"), 400
    with Service("exmdb") as exmdb:
        client = exmdb.domain(domain)
        client.setFolderMember(folderID, memberID, data["permissions"], client.SET)
    with Service("redis") as redis:
        redis.delete("grommunio-sync:sharedfolders-"+domain.domainname)
    return jsonify(message="Success")


@API.route(api.BaseRoute+"/domains/<int:domainID>/folders/<int:folderID>/owners/<int:memberID>", methods=["DELETE"])
@secure(requireDB=True)
def deletePublicFolderOwner(domainID, folderID, memberID):
    checkPermissions(DomainAdminPermission(domainID))
    from orm.domains import Domains
    domain = Domains.query.filter(Domains.ID == domainID).first()
    if domain is None:
        return jsonify(message="Domain not found"), 404
    with Service("exmdb") as exmdb:
        client = exmdb.domain(domain)
        client.setFolderMember(folderID, memberID, 0xFFFFFFFF, client.REMOVE)
    with Service("redis") as redis:
        redis.delete("grommunio-sync:sharedfolders-"+domain.domainname)
    return jsonify(message="Success"), 200
