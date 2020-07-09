# -*- coding: utf-8 -*-
"""
Created on Tue Jul  7 10:18:55 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: Grammm GmbH, 2020
"""

from sqlalchemy import Column, INTEGER, TEXT, BLOB, ForeignKey, Index

class Common:
    def __init__(self, Schema):
        self._Schema = Schema
        class Configurations(Schema):
            __tablename__ = "configurations"

            ID = Column("config_id", INTEGER, primary_key=True)
            value = Column("config_value", BLOB, nullable=False)

            def __init__(self, ID, value):
                self.ID = ID
                self.value = value if isinstance(value, bytes) else str(value).encode()

        class AllocatedEids(Schema):
            __tablename__ = "allocated_eids"

            begin = Column("range_begin", INTEGER, nullable=False, primary_key=True)
            end = Column("range_end", INTEGER, nullable=False, primary_key=True)
            time = Column("allocate_time", INTEGER, nullable=False, primary_key=True, index=True)
            isSystem = Column("is_system", INTEGER, server_default=None, primary_key=True)

        class NamedProperties(Schema):
            __tablename__ = "named_properties"
            __table_args__ = {"sqlite_autoincrement": True}

            ID = Column("propid", INTEGER, primary_key=True)
            name = Column("name_string", TEXT(collation="nocase"), nullable=False)

        class StoreProperties(Schema):
            __tablename__ = "store_properties"

            tag = Column("proptag", INTEGER, primary_key=True, unique=True, nullable=False)
            value = Column("propval", BLOB, nullable=False)

            def __init__(self, tag, value):
                self.tag = tag
                self.value = value if isinstance(value, bytes) else str(value).encode()

        class FolderProperties(Schema):
            __tablename__ = "folder_properties"

            folderID = Column("folder_id", INTEGER, ForeignKey("folders.folder_id", ondelete="cascade", onupdate="cascade"),
                              primary_key=True, nullable=False, index=True)
            proptag = Column("proptag", INTEGER, primary_key=True, nullable=False)
            propval = Column("propval", BLOB, nullable=False)

            def __init__(self, folderID, proptag, propval):
                self.folderID = folderID
                self.proptag = proptag
                self.propval = propval if isinstance(propval, bytes) else str(propval).encode()

        Index("folder_property_index", FolderProperties.folderID, FolderProperties.proptag, unique=True)

        class Permissions(Schema):
            __tablename__ = "permissions"
            __table_args__ = {"sqlite_autoincrement": True}

            ID = Column("member_id", INTEGER, primary_key=True, nullable=False)
            folderID = Column("folder_id", INTEGER, ForeignKey("folders.folder_id", ondelete="cascade", onupdate="cascade"),
                              nullable=False, index=True)
            username = Column("username", TEXT(collation="nocase"), nullable=False)
            permission = Column("permission", INTEGER, nullable=False)

        Index("folder_username_index", Permissions.folderID, Permissions.username, unique=True)

        class Rules(Schema):
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

        class MessageProperties(Schema):
            __tablename__ = "message_properties"

            messageID = Column("message_id", INTEGER, ForeignKey("messages.message_id", ondelete="cascade", onupdate="cascade"),
                               primary_key=True, nullable=False, index=True)
            proptag = Column("proptag", INTEGER, nullable=False, primary_key=True)
            propval = Column("propval", BLOB, nullable=False)

        Index("message_property_index", MessageProperties.messageID, MessageProperties.proptag, unique=True)
        Index("proptag_propval_index", MessageProperties.proptag, MessageProperties.propval)

        class MessageChanges(Schema):
            __tablename__ = "message_changes"

            messageID = Column("message_id", INTEGER, ForeignKey("messages.message_id", ondelete="cascade", onupdate="cascade"),
                               primary_key=True, nullable=False, index=True)
            changeNum = Column("change_nuamber", INTEGER, nullable=False, primary_key=True)
            indices = Column("indices", BLOB, nullable=False)
            proptags = Column("proptags", BLOB, nullable=False)

        class Recipients(Schema):
            __tablename__ = "recipients"
            __table_args__ = {"sqlite_autoincrement": True}

            ID = Column("recipient_id", INTEGER, primary_key=True)
            messageID = Column("message_id", INTEGER, ForeignKey("messages.message_id", ondelete="cascade", onupdate="cascade"),
                               nullable=False, index=True)

        class RecipientProperties(Schema):
            __tablename__ = "recipients_properties"

            recipientID = Column("recipient_id", INTEGER, ForeignKey(Recipients.ID, ondelete="cascade", onupdate="cascade"),
                               primary_key=True, nullable=False, index=True)
            proptag = Column("proptag", INTEGER, nullable=False, primary_key=True)
            propval = Column("propval", BLOB, nullable=False)

        Index("recipient_property_index", RecipientProperties.recipientID, RecipientProperties.proptag, unique=True)

        class Attachments(Schema):
            __tablename__ = "attachments"
            __table_args__ = {"sqlite_autoincrement": True}

            ID = Column("attachment_id", INTEGER, primary_key=True)
            messageID = Column("message_id", INTEGER, ForeignKey("messages.message_id", ondelete="cascade", onupdate="cascade"),
                               nullable=False, index=True)

        class AttachmentProperties(Schema):
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
