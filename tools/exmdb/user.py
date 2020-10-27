# -*- coding: utf-8 -*-
"""
Created on Tue Jul  7 14:25:50 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: Grammm GmbH, 2020
"""


from sqlalchemy import Column, BLOB, INTEGER, TEXT, ForeignKey, Index

from .common import Common
from tools.constants import PropTags

# Mapping of

class User(Common):
    def __init__(self, Schema=None):
        super().__init__(Schema)

        class Folders(self._Schema):
            __tablename__ = "folders"

            ID = Column("folder_id", INTEGER, primary_key=True)
            parentID = Column("parent_id", INTEGER, ForeignKey("folders.folder_id", onupdate="cascade", ondelete="cascade"))
            changeNum = Column("change_number", INTEGER, unique=True, nullable=False)
            isSearch = Column("is_search", INTEGER, server_default="0", index=True)
            isDeleted = Column("is_deleted", INTEGER, server_default="0")
            searchFlags = Column("search_flags", INTEGER)
            searchCriteria = Column("search_criteria", BLOB)
            currentEid = Column("cur_eid", INTEGER, nullable=False)
            maxEid = Column("max_eid", INTEGER, nullable=False)

        Index("folder_delete_index", Folders.parentID, Folders.isDeleted)

        class Messages(self._Schema):
            __tablename__ = "messages"

            ID = Column("message_id", INTEGER, primary_key=True)
            parentFID = Column("parent_fid", INTEGER, ForeignKey(Folders.ID, ondelete="cascade", onupdate="cascade"), index=True)
            parentAttID = Column("parent_attid", INTEGER, ForeignKey(self.Attachments.ID, ondelete="cascade", onupdate="cascade"), index=True)
            isAssociated = Column("is_associated", INTEGER, index=True)
            changeNum = Column("change_number", INTEGER, unique=True, nullable=False)
            readCn = Column("read_cn", INTEGER, unique=True)
            readState = Column("read_state", INTEGER, server_default="0")
            isDeleted = Column("is_deleted", INTEGER, server_default="0")
            messageSize = Column("message_size", INTEGER, nullable=False)
            groupID = Column("group_id", INTEGER)
            timerID = Column("timer_id", INTEGER)
            midString = Column("mid_string", TEXT)

        Index("parent_assoc_index", Messages.parentFID, Messages.isAssociated)
        Index("parent_read_assoc_index", Messages.parentFID, Messages.readState, Messages.isAssociated)
        Index("parent_assoc_delete_index", Messages.parentFID, Messages.isAssociated, Messages.isDeleted)

        class ReceiveTable(self._Schema):
            __tablename__ = "receive_table"

            cls = Column("class", TEXT(collation="nocase"), unique=True, nullable=False, primary_key=True)
            folderID = Column("folder_id", INTEGER, ForeignKey(Folders.ID, ondelete="cascade", onupdate="cascade"),
                              nullable=False, index=True)
            modified = Column("modified_time", INTEGER, nullable=False)

        class SearchScopes(self._Schema):
            __tablename__ = "search_scopes"

            folderID = Column("folder_id", INTEGER, ForeignKey(Folders.ID, ondelete="cascade", onupdate="cascade"),
                              nullable=False, primary_key=True, index=True)
            includedFID = Column("included_fid", INTEGER, ForeignKey(Folders.ID, ondelete="cascade", onupdate="cascade"),
                                 nullable=False, primary_key=True, index=True)

        class SearchResult(self._Schema):
            __tablename__ = "search_result"

            folderID = Column("folder_id", INTEGER, ForeignKey(Folders.ID, ondelete="cascade", onupdate="cascade"),
                              nullable=False, primary_key=True, index=True)
            messageID = Column("message_id", INTEGER, ForeignKey(Messages.ID, ondelete="cascade", onupdate="cascade"),
                               nullable=False, primary_key=True, index=True)

        Index("search_message_index", SearchResult.folderID, SearchResult.messageID, unique=True)

        self.Folders = Folders
        self.Messages = Messages
        self.ReceiveTable = ReceiveTable
        self.SearchScopes = SearchScopes
        self.SearchResult = SearchResult

    def createGenericFolder(self, ctx, folderID: int, parentID: int, domainID: int, displayName: str, containerClass: str, hidden: bool):
        Common.createGenericFolder(self, ctx, folderID, parentID, domainID, displayName, containerClass)
        if hidden:
            ctx.exmdb.add(self.FolderProperties(folderID=folderID, proptag=PropTags.ATTRIBUTEHIDDEN, propval=1))
