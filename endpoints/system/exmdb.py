# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 grommunio GmbH

from flask import jsonify, request

import api
from api.core import API, secure

from services import Service, ServiceUnavailableError
from tools.constants import PrivateFIDs, _permsAll
from tools.rop import makeEidEx
from tools.exmdb import getClient, _FolderNode, exmdbFolderPermissionString


@API.route(api.BaseRoute+"/system/exmdb/<string:username>/folders", methods=["GET"])
@secure(requireDB=True)
def userFolders(username):
    fid = PrivateFIDs.IPMSUBTREE
    fid = makeEidEx(1, fid)
    try:
        with Service("exmdb") as exmdb:
            ret, client = getClient(username, exmdb)
            if ret:
                return ret
            root = exmdb.Folder(client.getFolderProperties(0, fid))
            subfolders = exmdb.FolderList(client.listFolders(fid, True)).folders
            folder = _FolderNode(root, subfolders)
            folderDict = folder._toDict()
            return jsonify(folderDict)
    except ServiceUnavailableError as err:
        return jsonify(message=str(err)), 500
        

@API.route(api.BaseRoute+"/system/exmdb/<string:username>/folders/<int:fid>", methods=["GET"])
@secure(requireDB=True)
def userFolder(username, fid):
    fid = makeEidEx(1, fid)
    with Service("exmdb") as exmdb:
        ret, client = getClient(username, exmdb)
        if ret:
            return ret
        members = exmdb.FolderMemberList(client.getFolderMemberList(fid)).members
        members = [{
            "name": member.mail,
            "rights": member.rights,
            "rightsName": exmdbFolderPermissionString(member.rights)
        } for member in members]
        return jsonify(members=members)


@API.route(api.BaseRoute+"/system/exmdb/<string:username>/folders/<int:fid>/permissions", methods=["POST", "DELETE"])
@secure(requireDB=True)
def userFolderPermissionsGrant(username, fid):
    from functools import reduce
    args = request.get_json(silent=True) or {}
    recursive = args["recursive"] if "recursive" in args else False
    permissions = args["permissions"] if "permissions" in args else []
    permittedUser = args["username"] if "username" in args else "anonymous"

    fid = makeEidEx(1, fid)
    perms = reduce(lambda x, y: x | y, permissions, 0) if permissions else 0
    with Service("exmdb") as exmdb:
        ret, client = getClient(username, exmdb)
        if ret:
            return jsonify(message="Error getting client data"), 500
        fids = (fid,)
        folders = [exmdb.Folder(client.getFolderProperties(0, fid))]
        if recursive:
            folders += exmdb.FolderList(client.listFolders(fid, True)).folders
            fids += tuple(folder.folderId for folder in folders)

        perms = [client.setFolderMember(fid,
                                        permittedUser,
                                        perms if request.method == "POST" else _permsAll,
                                        client.ADD if request.method == "POST" else client.REMOVE
                                        )
                    for fid in fids]
        return jsonify(message="Success"), 201 if request.method == "POST" else 200
    