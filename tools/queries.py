# -*- coding: utf-8 -*-
"""
Created on Wed Aug 12 16:11:04 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: Grammm GmbH, 2020
"""

from tools.mapi.client import MapiClient
from tools.mapi.requests import LoadHierarchyTableRequest, QueryTableRequest, UnloadTableRequest
from tools.constants import PropTags, PublicFIDs
from tools import rop


def getFolderListQuery(homedir):
    with MapiClient(prefix="/d-data/", private=False) as client:
        folderID = rop.makeEidEx(1, PublicFIDs.IPMSUBTREE)
        hTable = client.send(LoadHierarchyTableRequest(homedir, folderID, 0))
        propTags = [PropTags.FOLDERID, PropTags.DISPLAYNAME, PropTags.COMMENT, PropTags.CREATIONTIME]
        table = client.send(QueryTableRequest(homedir, 0, hTable.tableId, propTags, 0, hTable.rowCount))
        client.send(UnloadTableRequest(homedir, hTable.tableId))
    return table
