# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 grommunio GmbH

from flask import jsonify, request

import api
from api.core import API, secure
from api.security import checkPermissions

from services import Service, ServiceUnavailableError
from tools.constants import PrivateFIDs, _permsAll, _perms
from tools.permissions import DomainAdminPermission, DomainAdminROPermission
from tools.rop import makeEidEx
from tools.exmdb import getClient, _FolderNode, exmdbFolderPermissionString


def checkMailboxPermissions(username, write):
    """Check whether the current user may access the mailbox of `username`.

    The endpoints are keyed on a plain user name, so the target has to be resolved before the
    domain level permissions can be checked.

    Parameters
    ----------
    username : str
        Name of the mailbox owner
    write : bool
        Whether the operation modifies the mailbox

    Returns
    -------
    Error response if the user does not exist, None otherwise
    """
    from orm.users import Users
    user = Users.query.filter(Users.username == username).first()
    if user is None:
        return jsonify(message="User not found"), 404
    checkPermissions(DomainAdminPermission(user.domainID) if write else DomainAdminROPermission(user.domainID))


@API.route(api.BaseRoute+"/system/exmdb/<string:username>/folders", methods=["GET"])
@secure(requireDB=True)
def userFolders(username):
    error = checkMailboxPermissions(username, False)
    if error:
        return error
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
    error = checkMailboxPermissions(username, False)
    if error:
        return error
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


def grantPermissions(username, fid, permittedUser):
    args = request.get_json(silent=True) or {}
    recursive = args["recursive"] if "recursive" in args else False
    perms = args["permissions"] if "permissions" in args else 0

    fid = makeEidEx(1, fid)
    with Service("exmdb") as exmdb:
        ret, client = getClient(username, exmdb)
        if ret:
            return jsonify(message="Error getting client data"), 500
        fids = (fid,)
        rootFolder = exmdb.Folder(client.getFolderProperties(0, fid))

        # Prevent free-busy permissions on non-calendar folders
        if(rootFolder.container != "IPF.Appointment" and (perms & _perms["freebusysimple"] or perms & _perms["freebusydetailed"])):
            return jsonify(message="Can't set free-busy permissions: '{}' isn't a calendar folder".format(rootFolder.displayName)), 400

        folders = [rootFolder]
        if recursive:
            folders += exmdb.FolderList(client.listFolders(fid, True)).folders
            fids += tuple(folder.folderId for folder in folders)

        perms = [client.setFolderMember(fid, permittedUser, perms, client.SET)
                    for fid in fids]
        return jsonify(message="Success"), 201 if request.method == "POST" else 200


@API.route(api.BaseRoute+"/system/exmdb/<string:username>/folders/<int:fid>/permissions", methods=["POST", "DELETE"])
@secure(requireDB=True)
def userFolderPermissionsGrant(username, fid):
    error = checkMailboxPermissions(username, True)
    if error:
        return error
    args = request.get_json(silent=True) or {}
    permittedUser = args["username"] if "username" in args else "anonymous"
    return grantPermissions(username, fid, permittedUser)


@API.route(api.BaseRoute+"/system/exmdb/<string:username>/folders/<int:fid>/permissions/<string:permittedUser>", methods=["PATCH"])
@secure(requireDB=True)
def userFolderPermissionsUpdate(username, fid, permittedUser):
    error = checkMailboxPermissions(username, True)
    if error:
        return error
    return grantPermissions(username, fid, permittedUser)
    