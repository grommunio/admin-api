# -*- coding: utf-8 -*-
"""
Created on Wed Jul  1 14:43:23 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: Grammm GmbH, 2020
"""

from sqlalchemy import Column, INTEGER, TEXT, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base

from .common import Common

# Mapping of sqlite3_common.txt


class Domain(Common):
    def __init__(self, Schema=None):
        Schema = Schema or declarative_base()
        super().__init__(Schema)

        class Folders(Schema):
            __tablename__ = "folders"

            ID = Column("folder_id", INTEGER, primary_key=True)
            parentID = Column("parent_id", INTEGER, ForeignKey("folders.folder_id", ondelete="cascade", onupdate="cascade"))
            changeNum = Column("change_number", INTEGER, unique=True, nullable=False)
            isDeleted = Column("is_deleted", INTEGER, server_default="0")
            currentEid = Column("cur_eid", INTEGER, nullable=False)
            maxEid = Column("max_eid", INTEGER, nullable=False)

        Index("folder_delete_index", Folders.parentID, Folders.isDeleted)

        class Messages(Schema):
            __tablename__ = "messages"

            ID = Column("message_id", INTEGER, primary_key=True)
            parentFID = Column("parent_fid", INTEGER, ForeignKey(Folders.ID, ondelete="cascade", onupdate="cascade"),
                               index=True)
            parentAttID = Column("parent_attid", INTEGER,
                                 ForeignKey(self.Attachments.ID, ondelete="cascade", onupdate="cascade"), index=True)
            isDeleted = Column("is_deleted", INTEGER, server_default="0")
            isAssociated = Column("is_associated", INTEGER, index=True)
            changeNum = Column("change_number", INTEGER, unique=True, nullable=False)
            size = Column("message_size", INTEGER, nullable=False)
            groupID = Column("group_id", INTEGER, server_default=None)

        Index("parent_assoc_delete_index", Messages.parentFID, Messages.isAssociated, Messages.isDeleted)

        class ReadStates(Schema):
            __tablename__ = "read_states"

            messageID = Column("message_id", INTEGER, ForeignKey(Messages.ID, ondelete="cascade", onupdate="cascade"),
                               nullable=False, index=True, primary_key=True)
            username = Column("username", TEXT(collation="nocase"), nullable=False, primary_key=True)

        Index("state_username_index", ReadStates.messageID, ReadStates.username, unique=True)

        class ReadCns(Schema):
            __tablename__ = "read_cns"

            messageID = Column("message_id", INTEGER, ForeignKey(Messages.ID, ondelete="cascade", onupdate="cascade"),
                               nullable=False, index=True, primary_key=True)
            username = Column("username", TEXT(collation="nocase"), nullable=False, primary_key=True)
            readCn = Column("read_cn", INTEGER, unique=True, nullable=False, primary_key=True)

        Index("readcn_username_index", ReadCns.messageID, ReadCns.username, unique=True)

        class ReplcaMapping(Schema):
            __tablename__ = "replca_mapping"
            __table_args__ = {"sqlite_autoincrement": True}

            ID = Column("replid", INTEGER, primary_key=True)
            GUID = Column("replguid", TEXT(collation="nocase"), unique=True, nullable=False)

        self.Folders = Folders
        self.Messages = Messages
        self.ReadStates = ReadStates
        self.ReadCns = ReadCns
        self.ReplcaMapping = ReplcaMapping
