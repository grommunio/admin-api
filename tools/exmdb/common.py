# -*- coding: utf-8 -*-
"""
Created on Tue Jul  7 10:18:55 2020

@copyright: grammm GmbH, 2020
"""

from sqlalchemy import Column, INTEGER, TEXT, BLOB, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base

from tools.constants import PropTags, Misc
from tools.DataModel import DataModel, Int, Text
from tools.rop import ntTime
from tools.structures import XID

import time

class Common:
    class Model:
        class classproperty(object):
            def __init__(self, f):
                self.f = f
            def __get__(self, obj, owner):
                return self.f(owner)
        @classproperty
        def query(self):
            return self._session.query(self)

    def __init__(self, Schema, session=None):
        self._Schema = Schema or declarative_base(cls=self.Model)

        class Configurations(self._Schema):
            __tablename__ = "configurations"

            ID = Column("config_id", INTEGER, primary_key=True)
            value = Column("config_value", BLOB, nullable=False)

            def __init__(self, ID, value):
                self.ID = ID
                self.value = value if isinstance(value, bytes) else str(value).encode()

        class AllocatedEids(self._Schema):
            __tablename__ = "allocated_eids"

            begin = Column("range_begin", INTEGER, nullable=False, primary_key=True)
            end = Column("range_end", INTEGER, nullable=False, primary_key=True)
            time = Column("allocate_time", INTEGER, nullable=False, primary_key=True, index=True)
            isSystem = Column("is_system", INTEGER, server_default=None, primary_key=True)

        class NamedProperties(self._Schema):
            __tablename__ = "named_properties"
            __table_args__ = {"sqlite_autoincrement": True}

            ID = Column("propid", INTEGER, primary_key=True)
            name = Column("name_string", TEXT(collation="nocase"), nullable=False)

        class StoreProperties(self._Schema):
            __tablename__ = "store_properties"

            tag = Column("proptag", INTEGER, primary_key=True, unique=True, nullable=False)
            value = Column("propval", BLOB, nullable=False)

            def __init__(self, tag, value):
                self.tag = tag
                self.value = value if isinstance(value, bytes) else str(value).encode()

        class FolderProperties(DataModel, self._Schema):
            __tablename__ = "folder_properties"

            folderID = Column("folder_id", INTEGER, ForeignKey("folders.folder_id", ondelete="cascade", onupdate="cascade"),
                              primary_key=True, nullable=False, index=True)
            proptag = Column("proptag", INTEGER, primary_key=True, nullable=False)
            _propval = Column("propval", BLOB, nullable=False)

            def __init__(self, props={}, **kwargs):
                self.augment(props, kwargs)
                self.fromdict(props, **kwargs)

            _dictmapping_ = ((Int("folderID", flags="init"), Int("proptag", flags="init"), Text("propval", flags="patch")),)

            @property
            def propval(self):
                return self._propval

            @propval.setter
            def propval(self, value):
                self._propval = value if isinstance(value, bytes) else str(value).encode()

        Index("folder_property_index", FolderProperties.folderID, FolderProperties.proptag, unique=True)

        class Permissions(self._Schema):
            __tablename__ = "permissions"
            __table_args__ = {"sqlite_autoincrement": True}

            ID = Column("member_id", INTEGER, primary_key=True, nullable=False)
            folderID = Column("folder_id", INTEGER, ForeignKey("folders.folder_id", ondelete="cascade", onupdate="cascade"),
                              nullable=False, index=True)
            username = Column("username", TEXT(collation="nocase"), nullable=False)
            permission = Column("permission", INTEGER, nullable=False)

        Index("folder_username_index", Permissions.folderID, Permissions.username, unique=True)

        class Rules(self._Schema):
            __tablename__ = "rules"
            __table_args__ = {"sqlite_autoincrement": True}

            ID = Column("rule_id", INTEGER, primary_key=True)
            name = Column("name", TEXT(collation="nocase"))
            provider = Column("provider", TEXT(collation="nocase"), nullable=False)
            sequence = Column("sequence", INTEGER, nullable=False)
            state = Column("state", INTEGER, nullable=False)
            level = Column("level", INTEGER)
            user_flags = Column("user_flags", INTEGER)
            provider_data = Column("provider_data", BLOB)
            condition = Column("condition", BLOB, nullable=False)
            actions = Column("actions", BLOB, nullable=False)
            folderID = Column("folder_id", INTEGER, ForeignKey("folders.folder_id", ondelete="cascade", onupdate="cascade"),
                              nullable=False, index=True)

        class MessageProperties(self._Schema):
            __tablename__ = "message_properties"

            messageID = Column("message_id", INTEGER, ForeignKey("messages.message_id", ondelete="cascade", onupdate="cascade"),
                               primary_key=True, nullable=False, index=True)
            proptag = Column("proptag", INTEGER, nullable=False, primary_key=True)
            propval = Column("propval", BLOB, nullable=False)

        Index("message_property_index", MessageProperties.messageID, MessageProperties.proptag, unique=True)
        Index("proptag_propval_index", MessageProperties.proptag, MessageProperties.propval)

        class MessageChanges(self._Schema):
            __tablename__ = "message_changes"

            messageID = Column("message_id", INTEGER, ForeignKey("messages.message_id", ondelete="cascade", onupdate="cascade"),
                               primary_key=True, nullable=False, index=True)
            changeNum = Column("change_nuamber", INTEGER, nullable=False, primary_key=True)
            indices = Column("indices", BLOB, nullable=False)
            proptags = Column("proptags", BLOB, nullable=False)

        class Recipients(self._Schema):
            __tablename__ = "recipients"
            __table_args__ = {"sqlite_autoincrement": True}

            ID = Column("recipient_id", INTEGER, primary_key=True)
            messageID = Column("message_id", INTEGER, ForeignKey("messages.message_id", ondelete="cascade", onupdate="cascade"),
                               nullable=False, index=True)

        class RecipientProperties(self._Schema):
            __tablename__ = "recipients_properties"

            recipientID = Column("recipient_id", INTEGER, ForeignKey(Recipients.ID, ondelete="cascade", onupdate="cascade"),
                               primary_key=True, nullable=False, index=True)
            proptag = Column("proptag", INTEGER, nullable=False, primary_key=True)
            propval = Column("propval", BLOB, nullable=False)

        Index("recipient_property_index", RecipientProperties.recipientID, RecipientProperties.proptag, unique=True)

        class Attachments(self._Schema):
            __tablename__ = "attachments"
            __table_args__ = {"sqlite_autoincrement": True}

            ID = Column("attachment_id", INTEGER, primary_key=True)
            messageID = Column("message_id", INTEGER, ForeignKey("messages.message_id", ondelete="cascade", onupdate="cascade"),
                               nullable=False, index=True)

        class AttachmentProperties(self._Schema):
            __tablename__ = "attachment_properties"

            attachmentID = Column("attachment_id", INTEGER, ForeignKey(Attachments.ID, ondelete="cascade", onupdate="cascade"),
                                  primary_key=True, nullable=False, index=True)
            proptag = Column("proptag", INTEGER, nullable=False, primary_key=True)
            propval = Column("propval", BLOB, nullable=False)

        Index("attachment_property_index", AttachmentProperties.attachmentID, AttachmentProperties.proptag, unique=True)

        self.Configurations = Configurations
        self.AllocatedEids = AllocatedEids
        self.NamedProperties = NamedProperties
        self.StoreProperties = StoreProperties
        self.FolderProperties = FolderProperties
        self.Permissions = Permissions
        self.Rules = Rules
        self.MessageProperties = MessageProperties
        self.MessageChanges = MessageChanges
        self.Recipients = Recipients
        self.RecipientProperties = RecipientProperties
        self.Attachments = Attachments
        self.AttachmentProperties = AttachmentProperties

    def createGenericFolder(self, ctx, folderID: int, parentID: int, objectID: int, displayName: str, containerClass: str):
        """Create a generic MS Exchange folder.

        Parameters
        ----------
        folderID : int
            ID of the new folder.
        parentID : int
            ID of the parent folder (or `None` to create root folder).
        objectID : int
            ID of the domain to create the folder for.
        displayName : str
            Name of the folder.
        containerClass : str, optional
            Container class of the folder. The default is None.
        """
        currentEid = ctx.lastEid+1
        ctx.lastEid += Misc.ALLOCATED_EID_RANGE
        ctx.lastEid
        ctx.exmdb.add(self.AllocatedEids(begin=currentEid, end=ctx.lastEid, time=int(time.time()), isSystem=1))
        ctx.lastCn += 1
        ctx.exmdb.add(self.Folders(ID=folderID, parentID=parentID, changeNum=ctx.lastCn, currentEid=currentEid, maxEid=ctx.lastEid))
        ctx.lastArt += 1
        ntNow = ntTime()
        xidData = XID.fromDomainID(objectID, ctx.lastCn).serialize()
        if containerClass is not None:
            ctx.exmdb.add(self.FolderProperties(folderID=folderID, proptag=PropTags.CONTAINERCLASS, propval=containerClass))
        ctx.exmdb.add(self.FolderProperties(folderID=folderID, proptag=PropTags.DELETEDCOUNTTOTAL, propval=0))
        ctx.exmdb.add(self.FolderProperties(folderID=folderID, proptag=PropTags.DELETEDFOLDERTOTAL, propval=0))
        ctx.exmdb.add(self.FolderProperties(folderID=folderID, proptag=PropTags.HIERARCHYCHANGENUMBER, propval=0))
        ctx.exmdb.add(self.FolderProperties(folderID=folderID, proptag=PropTags.INTERNETARTICLENUMBER, propval=ctx.lastArt))
        ctx.exmdb.add(self.FolderProperties(folderID=folderID, proptag=PropTags.DISPLAYNAME, propval=displayName))
        ctx.exmdb.add(self.FolderProperties(folderID=folderID, proptag=PropTags.COMMENT, propval=""))
        ctx.exmdb.add(self.FolderProperties(folderID=folderID, proptag=PropTags.CREATIONTIME, propval=ntNow))
        ctx.exmdb.add(self.FolderProperties(folderID=folderID, proptag=PropTags.LASTMODIFICATIONTIME, propval=ntNow))
        ctx.exmdb.add(self.FolderProperties(folderID=folderID, proptag=PropTags.LOCALCOMMITTIMEMAX, propval=ntNow))
        ctx.exmdb.add(self.FolderProperties(folderID=folderID, proptag=PropTags.HIERREV, propval=ntNow))
        ctx.exmdb.add(self.FolderProperties(folderID=folderID, proptag=PropTags.CHANGEKEY, propval=xidData))
        ctx.exmdb.add(self.FolderProperties(folderID=folderID, proptag=PropTags.PREDECESSORCHANGELIST, propval=b'\x16'+xidData))

    @classmethod
    def connect(cls, path):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        engine = create_engine("sqlite:///"+path)
        obj = cls(session=sessionmaker(bind=engine)())
        return obj
