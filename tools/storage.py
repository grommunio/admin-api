# -*- coding: utf-8 -*-
"""
Created on Tue Jun 30 10:50:14 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: Grammm GmbH, 2020
"""

from math import ceil
import os
import shutil
import time

from .misc import AutoClean
from .structures import XID, GUID

from tools.exmdb import midb
from tools.exmdb.domain import Domain as DomainExmdb
from tools.exmdb.user import User as UserExmdb

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tools.config import Config
from tools.constants import PropTags, ConfigIDs, PublicFIDs, PrivateFIDs, Permissions, Misc, FolderNames
from tools.rop import ntTime

import logging
import traceback


def genPath(index: int, depth: int):
    """Generate minimum width unique path for index.

    Parameters
    ----------
    index : int
        Index of the file
    depth : int
        Number of levels.

    Returns
    -------
    list of int
        Indices of each directory
    """
    def minSplits(num: int, depth: int):
        """Calculate minimum number of splits for `num` items in a tree with `depth` levels.

        Parameters
        ----------
        num : int
            Number of items in the tree.
        depth : int
            Depth of the tree

        Returns
        -------
        int
            Minimal required splits at any level.
        """
        return ceil(num**(1/depth))

    diridx = [0]*depth  # Path
    ms = minSplits(index+1, depth)  # Minimum required splits
    splitidx = index - (ms-1)**depth  # Index within current split level
    subprev = index  # Only required for depth == 1
    created = False  # Whether in a new branch (otherwise filling an old one)
    for level in range(depth-1):  # Traverse tree down to leaves
        subcap = ms**(depth-level-1)  # Capacity of each sub tree
        subprev = (ms-1)**(depth-level-1)  # Sub tree capacity at previous split level
        subnew = subcap if created else subcap-subprev  # Number of new elements that can be placed in each sub tree
        diridx[level] = min(splitidx//subnew, ms-1)  # Choose split number according to capacity
        splitidx -= diridx[level]*subnew  # Calculate local index for subtree
        created |= diridx[level] == ms-1  # Set sticky fresh-branch flag
    diridx[-1] = splitidx if created else splitidx+subprev  # Set leaf index
    return diridx


def createPath(parent: str, index: int, depth: int):
    """Create storage path.

    Parameters
    ----------
    parent : str
        Parent directory
    index : int
        Index of the element to store
    depth : int
        Number of levels to create

    Raises
    ------
    OSError
        Directory creation failed.

    Returns
    -------
    path : str
        The full path of the created directory (without trailing slash)
    """
    path = os.path.join(parent, *("{:X}".format(i) for i in genPath(index, depth)))
    os.makedirs(path)
    return path

class SetupContext:
    def __enter__(self):
        """Enter context."""
        self._dirs = []
        self.success = False
        return self

    def __exit__(self, *args):
        """Exit context.

        If success is not set to True, any directories created are removed.
        """
        if not self.success:
            for d in self._dirs:
                try:
                    shutil.rmtree(d)
                except:
                    pass
        if getattr(self, "exmdb", None) is not None:
            self.exmdb.rollback()


class DomainSetup(SetupContext):
    """Domain initialization context.

    Can be used in a with context to ensure automatic cleanup of created directories if an error occurs.
    Invocation of the run() method creates the complete directory structure required by a domain and
    sets up the initial MS Exchange database.

    If everything went well, the `success` attribute is set to True.
    If any exception occurs it is caught and the stack trace is written to the log. In this case, the `error` attribute
    contains a short error description and the `errorCode` attribute is set to an appropriate HTTP status code.
    """

    schema = DomainExmdb()

    def __init__(self, domain, area):
        """Initialize context object

        Parameters
        ----------
        domain : orm.domains.Domains
            Domain to initialize.
        area : orm.ext.AreaList
            Storage area to place domain in.
        """

        self.lastEid = Misc.ALLOCATED_EID_RANGE
        self.lastCn = Misc.CHANGE_NUMBER_BEGIN
        self.lastArt = 0

        self.domain = domain
        self.area = area

        self.success = False
        self.error = self.errorCode = None

    def run(self):
        """Run domain home directory initialization."""
        try:
            self.createHomedir()
            self.createExmdb()
            self.success = True
        except:
            logging.error(traceback.format_exc())
            self.error = "Unknown error"
            self.errorCode = 500

    def createHomedir(self):
        """Set up directory structure for a domain.

        Creates the home directory according to its ID in the master directory of the storage area.
        Intermediate directories are created automatically if necessary.

        If the storage area has an acceleration path configured, an exmdb path is created and symlinked accordingly.

        Additional `cid`, `log` and `tmp` subdirectories are created in the home directory.
        """
        self.domain.homedir = createPath(self.area.masterPath, self.domain.ID, self.area.storeLevels)
        self._dirs.append(self.domain.homedir)
        if self.area.accelPath is not None:
            dbPath = createPath(self.area.accelPath, self.domain.ID, self.area.storeLevels)
            self._dirs.append(dbPath)
            os.symlink(dbPath, self.domain.homedir+"/exmdb")
        else:
            os.mkdir(self.domain.homedir+"/exmdb")
        os.mkdir(self.domain.homedir+"/cid")
        os.mkdir(self.domain.homedir+"/log")
        os.mkdir(self.domain.homedir+"/tmp")

    def createExmdb(self):
        """Create exchange SQLite database for domain.

        Database is placed under <homedir>/exmdb/exchange.sqlite3.

        Propnames are filled automatically if the file `dataPath`/`propnames` file is found.
        """
        dbPath = os.path.join(self.domain.homedir, "exmdb", "exchange.sqlite3")
        engine = create_engine("sqlite:///"+dbPath)
        sizeFactor = 1024*1024/Config["options"]["domainStoreRatio"]
        self.schema._Schema.metadata.create_all(engine)
        self.exmdb = sessionmaker(bind=engine)()
        self.exmdb.execute("PRAGMA journal_mode = WAL;")
        try:
            dataPath = os.path.join(Config["options"]["dataPath"], Config["options"]["propnames"])
            with open(dataPath) as file:
                propid = 0x8001
                for line in file:
                    self.exmdb.add(self.schema.NamedProperties(ID=propid, name=line.strip()))
                    propid += 1
        except FileNotFoundError:
            logging.warn("Could not open {} - skipping.".format(dataPath))
        self.exmdb.add(self.schema.StoreProperties(tag=PropTags.CREATIONTIME, value=ntTime()))
        self.exmdb.add(self.schema.StoreProperties(tag=PropTags.PROHIBITRECEIVEQUOTA, value=self.domain.maxSize*sizeFactor))
        self.exmdb.add(self.schema.StoreProperties(tag=PropTags.PROHIBITSENDQUOTA, value=self.domain.maxSize*sizeFactor))
        self.exmdb.add(self.schema.StoreProperties(tag=PropTags.STORAGEQUOTALIMIT, value=self.domain.maxSize*sizeFactor))
        self.exmdb.add(self.schema.StoreProperties(tag=PropTags.MESSAGESIZEEXTENDED, value=0))
        self.exmdb.add(self.schema.StoreProperties(tag=PropTags.ASSOCMESSAGESIZEEXTENDED, value=0))
        self.exmdb.add(self.schema.StoreProperties(tag=PropTags.NORMALMESSAGESIZEEXTENDED, value=0))
        self.schema.createGenericFolder(self, PublicFIDs.ROOT, None, self.domain.ID, "Root Container")
        self.schema.createGenericFolder(self, PublicFIDs.IPMSUBTREE, PublicFIDs.ROOT, self.domain.ID, "IPM_SUBTREE")
        self.schema.createGenericFolder(self, PublicFIDs.NONIPMSUBTREE, PublicFIDs.ROOT, self.domain.ID, "NON_IPM_SUBTREE")
        self.schema.createGenericFolder(self, PublicFIDs.EFORMSREGISTRY, PublicFIDs.NONIPMSUBTREE, self.domain.ID, "EFORMS_REGISTRY")
        self.exmdb.add(self.schema.Configurations(ID=ConfigIDs.MAILBOX_GUID, value=str(GUID.random())))
        self.exmdb.add(self.schema.Configurations(ID=ConfigIDs.CURRENT_EID, value=0x100))
        self.exmdb.add(self.schema.Configurations(ID=ConfigIDs.MAXIMUM_EID, value=Misc.ALLOCATED_EID_RANGE))
        self.exmdb.add(self.schema.Configurations(ID=ConfigIDs.LAST_CHANGE_NUMBER, value=self.lastCn))
        self.exmdb.add(self.schema.Configurations(ID=ConfigIDs.LAST_CID, value=0))
        self.exmdb.add(self.schema.Configurations(ID=ConfigIDs.LAST_ARTICLE_NUMBER, value=self.lastArt))
        self.exmdb.add(self.schema.Configurations(ID=ConfigIDs.SEARCH_STATE, value=0))
        self.exmdb.add(self.schema.Configurations(ID=ConfigIDs.DEFAULT_PERMISSION, value=Permissions.domainDefault()))
        self.exmdb.add(self.schema.Configurations(ID=ConfigIDs.ANONYMOUS_PERMISSION, value=0))
        self.exmdb.commit()
        self.exmdb = None


class UserSetup(SetupContext):
    """User initialization context.

    Can be used in a with context to ensure automatic cleanup of created directories if an error occurs.
    Invocation of the run() method creates the complete directory structure required by a user and
    sets up the initial MS Exchange databases (exchange.sqlite3 and midb.sqlite3).

    If everything went well, the `success` attribute is set to True.
    If any exception occurs it is caught and the stack trace is written to the log. In this case, the `error` attribute
    contains a short error description and the `errorCode` attribute is set to an appropriate HTTP status code.
    """

    schema = UserExmdb()

    def __init__(self, user, area):
        """Initialize context object.

        Parameters
        ----------
        user : orm.users.Users
            User to initialize.
        area : orm.ext.AreaList
            Storage area to place user in.
        """
        self.lastEid = Misc.ALLOCATED_EID_RANGE
        self.lastCn = Misc.CHANGE_NUMBER_BEGIN
        self.lastArt = 0

        self.user = user
        self.area = area

        self.success = False
        self.error = self.errorCode = None

    def run(self):
        """Run user home directory initialization."""
        try:
            self.createHomedir()
            self.createExmdb()
            self.createMidb()
            self.success = True
        except:
            logging.error(traceback.format_exc())
            self.error = "Unknown error"
            self.errorCode = 500

    def createHomedir(self):
        """Set up directory structure for a user.

        Creates the home directory according to its ID in the master directory of the storage area.
        Intermediate directories are created automatically if necessary.

        If the storage area has an acceleration path configured, an exmdb path is created and symlinked accordingly.

        Additional `cid`, `config`, `disk`, `eml`, `ext` and `tmp` subdirectories are created in the home directory.
        """
        self.user.maildir = createPath(self.area.masterPath, self.user.ID, self.area.storeLevels)
        self._dirs.append(self.user.maildir)
        if self.area.accelPath is not None:
            dbPath = createPath(self.area.accelPath, self.user.ID, self.area.storeLevels)
            self._dirs.append(dbPath)
            os.symlink(dbPath, self.user.maildir+"/exmdb")
        else:
            os.mkdir(self.user.maildir+"/exmdb")
        os.mkdir(self.user.maildir+"/tmp")
        os.mkdir(self.user.maildir+"/tmp/imap.rfc822")
        os.mkdir(self.user.maildir+"/tmp/faststream")
        os.mkdir(self.user.maildir+"/eml")
        os.mkdir(self.user.maildir+"/ext")
        os.mkdir(self.user.maildir+"/cid")
        os.mkdir(self.user.maildir+"/disk")
        os.mkdir(self.user.maildir+"/config")
        with open(self.user.maildir+"/disk/index", "w") as file:
            file.write('{"size":0,"files":0}'+' '*492)
        thumbnailSrc = os.path.join(Config["options"]["dataPath"], Config["options"]["portrait"])
        try:
            shutil.copy(thumbnailSrc, self.user.maildir+"/config/portrait.jpg")
        except FileNotFoundError:
            pass

    def createSearchFolder(self, folderID: int, parentID: int, userID: int, displayName: str, containerClass: str):
        """Create exmdb search folder entries."""
        self.lastCn += 1
        self.exmdb.add(self.schema.Folders(ID=folderID, parentID=parentID, changeNum=self.lastCn, isSearch=1, currentEid=0, maxEid=0))
        self.lastArt += 1
        ntNow = ntTime()
        xidData = XID.fromDomainID(userID, self.lastCn).serialize()
        if containerClass is not None:
            self.exmdb.add(self.schema.FolderProperties(folderID=folderID, proptag=PropTags.CONTAINERCLASS, propval=containerClass))
        self.exmdb.add(self.schema.FolderProperties(folderID=folderID, proptag=PropTags.DELETEDCOUNTTOTAL, propval=0))
        self.exmdb.add(self.schema.FolderProperties(folderID=folderID, proptag=PropTags.DELETEDFOLDERTOTAL, propval=0))
        self.exmdb.add(self.schema.FolderProperties(folderID=folderID, proptag=PropTags.HIERARCHYCHANGENUMBER, propval=0))
        self.exmdb.add(self.schema.FolderProperties(folderID=folderID, proptag=PropTags.INTERNETARTICLENUMBER, propval=self.lastArt))
        self.exmdb.add(self.schema.FolderProperties(folderID=folderID, proptag=PropTags.ARTICLENUMBERNEXT, propval=1))
        self.exmdb.add(self.schema.FolderProperties(folderID=folderID, proptag=PropTags.DISPLAYNAME, propval=displayName))
        self.exmdb.add(self.schema.FolderProperties(folderID=folderID, proptag=PropTags.COMMENT, propval=""))
        self.exmdb.add(self.schema.FolderProperties(folderID=folderID, proptag=PropTags.CREATIONTIME, propval=ntNow))
        self.exmdb.add(self.schema.FolderProperties(folderID=folderID, proptag=PropTags.LASTMODIFICATIONTIME, propval=ntNow))
        self.exmdb.add(self.schema.FolderProperties(folderID=folderID, proptag=PropTags.HIERREV, propval=ntNow))
        self.exmdb.add(self.schema.FolderProperties(folderID=folderID, proptag=PropTags.LOCALCOMMITTIMEMAX, propval=ntNow))
        self.exmdb.add(self.schema.FolderProperties(folderID=folderID, proptag=PropTags.CHANGEKEY, propval=xidData))
        self.exmdb.add(self.schema.FolderProperties(folderID=folderID, proptag=PropTags.PREDECESSORCHANGELIST, propval=b'\x16'+xidData))

    def createExmdb(self):
        """Create exchange SQLite database for user.

        Database is placed under <homedir>/exmdb/exchange.sqlite3.

        Propnames are filled automatically if the file `dataPath`/`propnames` file is found.
        """
        dbPath = os.path.join(self.user.maildir, "exmdb", "exchange.sqlite3")
        engine = create_engine("sqlite:///"+dbPath)
        self.schema._Schema.metadata.create_all(engine)
        self.exmdb = sessionmaker(bind=engine)()
        self.exmdb.execute("PRAGMA journal_mode = WAL;")
        try:
            dataPath = os.path.join(Config["options"]["dataPath"], Config["options"]["propnames"])
            with open(dataPath) as file:
                propid = 0x8001
                for line in file:
                    self.exmdb.add(self.schema.NamedProperties(ID=propid, name=line.strip()))
                    propid += 1
        except FileNotFoundError:
            logging.warn("Could not open {} - skipping.".format(dataPath))
        ntNow = ntTime()
        lang = None
        self.exmdb.add(self.schema.ReceiveTable(cls="", folderID=PrivateFIDs.INBOX, modified=ntNow))
        self.exmdb.add(self.schema.ReceiveTable(cls="IPC", folderID=PrivateFIDs.ROOT, modified=ntNow))
        self.exmdb.add(self.schema.ReceiveTable(cls="IPM", folderID=PrivateFIDs.INBOX, modified=ntNow))
        self.exmdb.add(self.schema.ReceiveTable(cls="REPORT.IPM", folderID=PrivateFIDs.INBOX, modified=ntNow))
        self.exmdb.add(self.schema.StoreProperties(tag=PropTags.CREATIONTIME, value=ntNow))
        self.exmdb.add(self.schema.StoreProperties(tag=PropTags.PROHIBITRECEIVEQUOTA, value=self.user.propmap["prohibitreceivequota"]))
        self.exmdb.add(self.schema.StoreProperties(tag=PropTags.PROHIBITSENDQUOTA, value=self.user.propmap["prohibitsendquota"]))
        self.exmdb.add(self.schema.StoreProperties(tag=PropTags.STORAGEQUOTALIMIT, value=self.user.propmap["storagequotalimit"]))
        self.exmdb.add(self.schema.StoreProperties(tag=PropTags.OUTOFOFFICESTATE, value=0))
        self.exmdb.add(self.schema.StoreProperties(tag=PropTags.MESSAGESIZEEXTENDED, value=0))
        self.exmdb.add(self.schema.StoreProperties(tag=PropTags.ASSOCMESSAGESIZEEXTENDED, value=0))
        self.exmdb.add(self.schema.StoreProperties(tag=PropTags.NORMALMESSAGESIZEEXTENDED, value=0))
        self.schema.createGenericFolder(self, PrivateFIDs.ROOT, None, self.user.ID, "Root Container", None, False)
        self.schema.createGenericFolder(self, PrivateFIDs.IPMSUBTREE, PrivateFIDs.ROOT, self.user.ID, FolderNames.get("IPM", lang), None, False)
        self.schema.createGenericFolder(self, PrivateFIDs.INBOX, PrivateFIDs.IPMSUBTREE, self.user.ID, FolderNames.get("INBOX", lang), "IPF.Note", False)
        self.schema.createGenericFolder(self, PrivateFIDs.DRAFT, PrivateFIDs.IPMSUBTREE, self.user.ID, FolderNames.get("DRAFT", lang), "IPF.Note", False)
        self.schema.createGenericFolder(self, PrivateFIDs.OUTBOX, PrivateFIDs.IPMSUBTREE, self.user.ID, FolderNames.get("OUTBOX", lang), "IPF.Note", False)
        self.schema.createGenericFolder(self, PrivateFIDs.SENT_ITEMS, PrivateFIDs.IPMSUBTREE, self.user.ID, FolderNames.get("SENT", lang), "IPF.Note", False)
        self.schema.createGenericFolder(self, PrivateFIDs.DELETED_ITEMS, PrivateFIDs.IPMSUBTREE, self.user.ID, FolderNames.get("DELETED", lang), "IPF.Note", False)
        self.schema.createGenericFolder(self, PrivateFIDs.CONTACTS, PrivateFIDs.IPMSUBTREE, self.user.ID, FolderNames.get("CONTACTS", lang), "IPF.Contact", False)
        self.schema.createGenericFolder(self, PrivateFIDs.CALENDAR, PrivateFIDs.IPMSUBTREE, self.user.ID, FolderNames.get("CALENDAR", lang), "IPF.Appointment", False)
        self.schema.createGenericFolder(self, PrivateFIDs.JOURNAL, PrivateFIDs.IPMSUBTREE, self.user.ID, FolderNames.get("JOURNAL", lang), "IPF.Journal", False)
        self.schema.createGenericFolder(self, PrivateFIDs.NOTES, PrivateFIDs.IPMSUBTREE, self.user.ID, FolderNames.get("NOTES", lang), "IPF.StickyNote", False)
        self.schema.createGenericFolder(self, PrivateFIDs.TASKS, PrivateFIDs.IPMSUBTREE, self.user.ID, FolderNames.get("TASKS", lang), "IPF.Task", False)
        self.schema.createGenericFolder(self, PrivateFIDs.QUICKCONTACTS, PrivateFIDs.CONTACTS, self.user.ID, "Quick Contacts", "IPF.Contact.MOC.QuickContacts", True)
        self.schema.createGenericFolder(self, PrivateFIDs.IMCONTACTLIST, PrivateFIDs.CONTACTS, self.user.ID, "IM Contacts List", "IPF.Contact.MOC.ImContactList", True)
        self.schema.createGenericFolder(self, PrivateFIDs.GALCONTACTS, PrivateFIDs.CONTACTS, self.user.ID, "GAL Contacts", "IPF.Contact.GalContacts", True)
        self.schema.createGenericFolder(self, PrivateFIDs.JUNK, PrivateFIDs.IPMSUBTREE, self.user.ID, FolderNames.get("JUNK", lang), "IPF.Note", False)
        self.schema.createGenericFolder(self, PrivateFIDs.CONVERSATION_ACTION_SETTINGS, PrivateFIDs.IPMSUBTREE, self.user.ID, "Conversation Action Settings", "IPF.Configuration", True)
        self.schema.createGenericFolder(self, PrivateFIDs.DEFERRED_ACTION, PrivateFIDs.ROOT, self.user.ID, "Deferred Action", None, False)
        self.createSearchFolder(PrivateFIDs.SPOOLER_QUEUE, PrivateFIDs.ROOT, self.user.ID, "Spooler Queue", "IPF.Note")
        self.schema.createGenericFolder(self, PrivateFIDs.COMMON_VIEWS, PrivateFIDs.ROOT, self.user.ID, "Common Views", None, False)
        self.schema.createGenericFolder(self, PrivateFIDs.SCHEDULE, PrivateFIDs.ROOT, self.user.ID, "Schedule", None, False)
        self.schema.createGenericFolder(self, PrivateFIDs.FINDER, PrivateFIDs.ROOT, self.user.ID, "Finder", None, False)
        self.schema.createGenericFolder(self, PrivateFIDs.VIEWS, PrivateFIDs.ROOT, self.user.ID, "Views", None, False)
        self.schema.createGenericFolder(self, PrivateFIDs.SHORTCUTS, PrivateFIDs.ROOT, self.user.ID, "Shortcuts", None, False)
        self.schema.createGenericFolder(self, PrivateFIDs.SYNC_ISSUES, PrivateFIDs.IPMSUBTREE, self.user.ID, FolderNames.get("SYNC", lang), "IPF.Note", False)
        self.schema.createGenericFolder(self, PrivateFIDs.CONFLICTS, PrivateFIDs.SYNC_ISSUES, self.user.ID, FolderNames.get("CONFLICT", lang), "IPF.Note", False)
        self.schema.createGenericFolder(self, PrivateFIDs.LOCAL_FAILURES, PrivateFIDs.SYNC_ISSUES, self.user.ID, FolderNames.get("LOCAL", lang), "IPF.Note", False)
        self.schema.createGenericFolder(self, PrivateFIDs.SERVER_FAILURES, PrivateFIDs.SYNC_ISSUES, self.user.ID, FolderNames.get("SERVER", lang), "IPF.Note", False)
        self.schema.createGenericFolder(self, PrivateFIDs.LOCAL_FREEBUSY, PrivateFIDs.ROOT, self.user.ID, "Freebusy Data", None, False)
        self.exmdb.add(self.schema.Permissions(folderID=PrivateFIDs.CALENDAR, username="default", permission=Permissions.FREEBUSYSIMPLE))
        self.exmdb.add(self.schema.Permissions(folderID=PrivateFIDs.LOCAL_FREEBUSY, username="default", permission=Permissions.FREEBUSYSIMPLE))
        self.exmdb.add(self.schema.Configurations(ID=ConfigIDs.MAILBOX_GUID, value=str(GUID.random())))
        self.exmdb.add(self.schema.Configurations(ID=ConfigIDs.CURRENT_EID, value=0x100))
        self.exmdb.add(self.schema.Configurations(ID=ConfigIDs.MAXIMUM_EID, value=Misc.ALLOCATED_EID_RANGE))
        self.exmdb.add(self.schema.Configurations(ID=ConfigIDs.LAST_CHANGE_NUMBER, value=self.lastCn))
        self.exmdb.add(self.schema.Configurations(ID=ConfigIDs.LAST_CID, value=0))
        self.exmdb.add(self.schema.Configurations(ID=ConfigIDs.LAST_ARTICLE_NUMBER, value=self.lastArt))
        self.exmdb.add(self.schema.Configurations(ID=ConfigIDs.SEARCH_STATE, value=0))
        self.exmdb.add(self.schema.Configurations(ID=ConfigIDs.DEFAULT_PERMISSION, value=0))
        self.exmdb.add(self.schema.Configurations(ID=ConfigIDs.ANONYMOUS_PERMISSION, value=0))
        self.exmdb.commit()
        self.exmdb = None

    def createMidb(self):
        """Create midb SQLite database for user.

        Database is placed under <homedir>/exmdb/midb.sqlite3.
        """
        dbPath = os.path.join(self.user.maildir, "exmdb", "midb.sqlite3")
        engine = create_engine("sqlite:///"+dbPath)
        midb.Schema.metadata.create_all(engine)
        DB = sessionmaker(bind=engine)()
        DB.execute("PRAGMA journal_mode = WAL;")
        DB.add(midb.Configurations(ID=1, value=self.user.username))
        DB.commit()
