# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grammm GmbH

# Mapping of sqlite3_midb.txt

from sqlalchemy import Column, INTEGER, TEXT, BLOB, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base

Schema = declarative_base()

class Configurations(Schema):
    __tablename__ = "configurations"

    ID = Column("config_id", INTEGER, primary_key=True)
    value = Column("config_value", BLOB, nullable=False)

    def __init__(self, ID, value):
        self.ID = ID
        self.value = value if isinstance(value, bytes) else str(value).encode()


class Folders(Schema):
    __tablename__ = "folders"

    ID = Column("folder_id", INTEGER, primary_key=True)
    parentFID = Column("parent_fid", INTEGER, nullable=False, index=True)
    commitMax = Column("commit_max", INTEGER, nullable=False)
    name = Column("name", TEXT, nullable=False, unique=True)
    uidNext = Column("uidnext", INTEGER, server_default="0")
    unsub = Column("unsub", INTEGER, server_default="0")
    sortField = Column("sort_field", INTEGER, server_default="0")


class Messages(Schema):
    __tablename__ = "messages"

    ID = Column("message_id", INTEGER, primary_key=True)
    folderID = Column("folder_id", INTEGER, ForeignKey(Folders.ID, ondelete="cascade", onupdate="cascade"),
                      nullable=True, index=True)
    midString = Column("mid_string", TEXT, nullable=False, unique=True)
    idx = Column("idx", INTEGER, index=True)
    modTime = Column("mod_time", INTEGER, server_default="0")
    uid = Column("uid", INTEGER, nullable=False)
    unsent = Column("unsent", INTEGER, server_default="0")
    recent = Column("recent", INTEGER, server_default="1")
    read = Column("read", INTEGER, server_default="0")
    flagged = Column("flagged", INTEGER, server_default="0")
    replied = Column("replied", INTEGER, server_default="0")
    forwarded = Column("forwarded", INTEGER, server_default="0")
    deleted = Column("deleted", INTEGER, server_default="0")
    subject = Column("subject", TEXT, nullable=False)
    sender = Column("sender", TEXT, nullable=False)
    rcpt = Column("rcpt", TEXT, nullable=False)
    size = Column("size", INTEGER, nullable=False)
    ext = Column("ext", TEXT)
    received = Column("received", INTEGER, nullable=False)


Index("fid_recent_index", Messages.folderID, Messages.recent)
Index("fid_read_index", Messages.folderID, Messages.read)
Index("fid_received_index", Messages.folderID, Messages.received)
Index("fid_uid_index", Messages.folderID, Messages.uid)
Index("fid_flagged_index", Messages.folderID, Messages.flagged)
Index("fid_subject_index", Messages.folderID, Messages.subject)
Index("fid_from_index", Messages.folderID, Messages.sender)
Index("fid_rcpt_index", Messages.folderID, Messages.rcpt)
Index("fid_size_index", Messages.folderID, Messages.size)


class Mapping(Schema):
    __tablename__ = "mapping"

    messageID = Column("message_id", INTEGER, primary_key=True)
    midString = Column("mid_string", TEXT, nullable=False)
    flagString = Column("flag_string", TEXT)
