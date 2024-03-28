# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grommunio GmbH

import os
import shutil
import subprocess

from .misc import setDirectoryOwner, setDirectoryPermission
from .structures import XID, GUID
from .config import Config
from .constants import PropTags, ConfigIDs, PublicFIDs, PrivateFIDs, Misc
from .rop import ntTime

import traceback

import sqlite3
import time

import logging
logger = logging.getLogger("storage")


def createPath(parent: str, name: str, fileUid=None, fileGid=None):
    """Create storage path.

    Parameters
    ----------
    parent : str
        Parent directory
    name : str
        User or domain name

    Raises
    ------
    OSError
        Directory creation failed.

    Returns
    -------
    path : str
        The full path of the created directory (without trailing slash)
    """
    homepath = list(reversed(name.split('@')))
    leaf = homepath[-1]
    path = os.path.join(parent, *homepath)
    counter = 0
    while os.path.exists(path):
        counter += 1
        homepath[-1] = f"{leaf}~{counter}"
        path = os.path.join(parent, *homepath)
    os.makedirs(path)
    if fileUid is not None or fileGid is not None:
        for h in homepath:
            try:
                parent = os.path.join(parent, h)
                shutil.chown(parent, fileUid, fileGid)
            except Exception:
                logger.warn(f"failed to set ownership on '{path}' to {fileUid}/{fileGid}")
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
                except Exception:
                    pass
        if getattr(self, "exmdb", None) is not None:
            self.exmdb.rollback()

    def createGenericFolder(self, folderID: int, objectID: int):
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
        currentEid = self.lastEid+1
        self.lastEid += Misc.ALLOCATED_EID_RANGE
        self.exmdb.execute("INSERT INTO allocated_eids VALUES (?, ?, ?, 1)", (currentEid, self.lastEid, int(time.time())))
        self.lastCn += 1
        self.lastArt += 1
        ntNow = ntTime()
        xidData = XID.fromDomainID(objectID, self.lastCn).serialize()
        stmt = "INSERT INTO folder_properties VALUES (?, ?, ?)"
        self.exmdb.execute(stmt, (folderID, PropTags.CREATIONTIME, ntNow))
        self.exmdb.execute(stmt, (folderID, PropTags.LASTMODIFICATIONTIME, ntNow))
        self.exmdb.execute(stmt, (folderID, PropTags.LOCALCOMMITTIMEMAX, ntNow))
        self.exmdb.execute(stmt, (folderID, PropTags.HIERREV, ntNow))
        self.exmdb.execute(stmt, (folderID, PropTags.CHANGEKEY, xidData))
        self.exmdb.execute(stmt, (folderID, PropTags.PREDECESSORCHANGELIST, b'\x16'+xidData))

    def mkext(self, command, name):
        """Try to databases with external tools.

        Executes shell command to create database files.
        Fails if the command terminates with non-zero exit code.

        Parameters
        ----------
        command : str
            Command to execute
        name : str
            Name of the entity.

        Returns
        -------
        bool
            True if successful, False otherwise.
        """
        try:
            res = subprocess.run((command, name), stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            if res.returncode:
                logger.warning("{} return non-zero exit code ({}): {}".format(command, res.returncode, res.stdout))
                return False
            if res.stdout:
                logger.debug("{} (stdout): {}".format(command, res.stdout))
            if res.stderr:
                logger.debug("{} (stderr): {}".format(command, res.stderr))
        except Exception as err:
            logger.error("Failed to run {} ({}): {}".format(command, type(err).__name__,
                                                            " - ".join(str(arg) for arg in err.args)))
            return False
        return True


class DomainSetup(SetupContext):
    """Domain initialization context.

    Can be used in a with context to ensure automatic cleanup of created directories if an error occurs.
    Invocation of the run() method creates the complete directory structure required by a domain and
    sets up the initial MS Exchange database.

    If everything went well, the `success` attribute is set to True.
    If any exception occurs it is caught and the stack trace is written to the log. In this case, the `error` attribute
    contains a short error description and the `errorCode` attribute is set to an appropriate HTTP status code.
    """

    def __init__(self, domain, session):
        """Initialize context object

        Parameters
        ----------
        domain : orm.domains.Domains
            Domain to initialize.
        """

        self.lastEid = Misc.ALLOCATED_EID_RANGE
        self.lastCn = Misc.CHANGE_NUMBER_BEGIN
        self.lastArt = 0

        self.domain = domain
        self.session = session

        self.success = False
        self.error = self.errorCode = None

    def run(self):
        """Run domain home directory initialization."""
        try:
            fileUid, fileGid = Config["options"].get("fileUid"), Config["options"].get("fileGid")
            self.createHomedir(fileUid, fileGid)
            self.session.commit()
            self.createExmdb()
            try:
                setDirectoryOwner(self.domain.homedir, fileUid, fileGid)
                setDirectoryPermission(self.domain.homedir, Config["options"].get("filePermissions"))
            except Exception as err:
                logger.warn("Could not set domain directory ownership: "+" - ".join(str(arg) for arg in err.args))
            self.success = True
        except PermissionError as err:
            logger.error(traceback.format_exc())
            self.error = "Could not create home directory ({})".format(err.args[1])
            self.errorCode = 500
            self.domain.homedir = ""
        except FileExistsError:
            logger.error("Failed to create {}: Directory exists.".format(self.domain.homedir))
            self.error = "Could not create home directory: File exists"
            self.errorCode = 500
            self.domain.homedir = ""
        except Exception:
            logger.error(traceback.format_exc())
            self.error = "Unknown error"
            self.errorCode = 500
            self.domain.homedir = ""

    def createHomedir(self, fileUid, fileGid):
        """Set up directory structure for a domain.

        Creates the home directory according to its ID in the prefix specified in the configuration.
        Intermediate directories are created automatically if necessary.

        Additional `cid`, `log` and `tmp` subdirectories are created in the home directory.
        """
        self.domain.homedir = createPath(self.domain.homedir, self.domain.domainname, fileUid, fileGid)
        self._dirs.append(self.domain.homedir)
        os.mkdir(self.domain.homedir+"/exmdb")
        os.mkdir(self.domain.homedir+"/cid")
        os.mkdir(self.domain.homedir+"/log")
        os.mkdir(self.domain.homedir+"/tmp")

    def createExmdb(self):
        """Create exchange SQLite database for domain.

        Database is placed under <homedir>/exmdb/exchange.sqlite3.
        """
        if self.mkext("gromox-mkpublic", self.domain.domainname):
            return
        dbPath = os.path.join(self.domain.homedir, "exmdb", "exchange.sqlite3")
        shutil.copy("res/domain.sqlite3", dbPath)
        self.exmdb = sqlite3.connect(dbPath)
        self.exmdb.execute("INSERT INTO store_properties VALUES (?, ?)", (PropTags.CREATIONTIME, ntTime()))
        self.createGenericFolder(PublicFIDs.ROOT, self.domain.ID)
        self.createGenericFolder(PublicFIDs.IPMSUBTREE, self.domain.ID)
        self.createGenericFolder(PublicFIDs.NONIPMSUBTREE, self.domain.ID)
        self.createGenericFolder(PublicFIDs.EFORMSREGISTRY, self.domain.ID)
        self.exmdb.execute("INSERT INTO configurations VALUES (?, ?)", (ConfigIDs.MAILBOX_GUID, str(GUID.random())))
        self.exmdb.commit()
        self.exmdb.close()
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

    def __init__(self, user, session):
        """Initialize context object.

        Parameters
        ----------
        user : orm.users.Users
            User to initialize.
        """
        self.lastEid = Misc.ALLOCATED_EID_RANGE
        self.lastCn = Misc.CHANGE_NUMBER_BEGIN
        self.lastArt = 0

        self.user = user
        self.session = session

        self.success = False
        self.error = self.errorCode = None

    def run(self):
        """Run user home directory initialization."""
        try:
            fileUid, fileGid = Config["options"].get("fileUid"), Config["options"].get("fileGid")
            self.createHomedir(fileUid, fileGid)
            self.session.commit()
            self.createExmdb()
            self.createMidb()
            try:
                setDirectoryOwner(self.user.maildir, fileUid, fileGid)
                setDirectoryPermission(self.user.maildir, Config["options"].get("filePermissions"))
            except Exception as err:
                logger.warn("Could not set user directory ownership: "+" - ".join(str(arg) for arg in err.args))
            self.success = True
        except PermissionError as err:
            logger.error(traceback.format_exc())
            self.error = "Could not create home directory ({})".format(err.args[1])
            self.errorCode = 500
            self.user.maildir = ""
        except FileExistsError:
            logger.error("Failed to create {}: Directory exists.".format(self.domain.homedir))
            self.error = "Could not create home directory: File exists"
            self.errorCode = 500
            self.user.maildir = ""
        except Exception:
            logger.error(traceback.format_exc())
            self.error = "Unknown error"
            self.errorCode = 500
            self.user.maildir = ""

    def createHomedir(self, fileUid=None, fileGid=None):
        """Set up directory structure for a user.

        Creates the home directory according to its ID in the prefix set in the configuration.
        Intermediate directories are created automatically if necessary.

        Additional `cid`, `config`, `eml`, `ext` and `tmp` subdirectories are created in the home directory.
        """
        self.user.maildir = createPath(self.user.maildir, self.user.username, fileUid, fileGid)
        self._dirs.append(self.user.maildir)
        os.mkdir(self.user.maildir+"/exmdb")
        os.mkdir(self.user.maildir+"/tmp")
        os.mkdir(self.user.maildir+"/tmp/imap.rfc822")
        os.mkdir(self.user.maildir+"/tmp/faststream")
        os.mkdir(self.user.maildir+"/eml")
        os.mkdir(self.user.maildir+"/ext")
        os.mkdir(self.user.maildir+"/cid")
        os.mkdir(self.user.maildir+"/config")
        thumbnailSrc = os.path.join(Config["options"]["dataPath"], Config["options"]["portrait"])
        try:
            shutil.copy(thumbnailSrc, self.user.maildir+"/config/portrait.jpg")
        except FileNotFoundError:
            pass

    def createSearchFolder(self, folderID: int, userID: int):
        """Create exmdb search folder entries."""
        self.lastCn += 1
        self.lastArt += 1
        ntNow = ntTime()
        xidData = XID.fromDomainID(userID, self.lastCn).serialize()
        stmt = "INSERT INTO folder_properties VALUES (?,?,?)"
        self.exmdb.execute(stmt, (folderID, PropTags.CREATIONTIME, ntNow))
        self.exmdb.execute(stmt, (folderID, PropTags.LASTMODIFICATIONTIME, ntNow))
        self.exmdb.execute(stmt, (folderID, PropTags.HIERREV, ntNow))
        self.exmdb.execute(stmt, (folderID, PropTags.LOCALCOMMITTIMEMAX, ntNow))
        self.exmdb.execute(stmt, (folderID, PropTags.CHANGEKEY, xidData))
        self.exmdb.execute(stmt, (folderID, PropTags.PREDECESSORCHANGELIST, b'\x16'+xidData))

    def createExmdb(self):
        """Create exchange SQLite database for user.

        Database is placed under <homedir>/exmdb/exchange.sqlite3.
        """
        if self.mkext("gromox-mkprivate", self.user.username):
            return
        dbPath = os.path.join(self.user.maildir, "exmdb", "exchange.sqlite3")
        shutil.copy("res/user.sqlite3", dbPath)
        self.exmdb = sqlite3.connect(dbPath)
        ntNow = ntTime()
        stmt = "INSERT INTO receive_table VALUES (?, ?, ?)"
        self.exmdb.execute(stmt, ("", PrivateFIDs.INBOX, ntNow))
        self.exmdb.execute(stmt, ("IPC", PrivateFIDs.ROOT, ntNow))
        self.exmdb.execute(stmt, ("IPM", PrivateFIDs.INBOX, ntNow))
        self.exmdb.execute(stmt, ("REPORT.IPM", PrivateFIDs.INBOX, ntNow))
        self.createGenericFolder(PrivateFIDs.ROOT, self.user.ID)
        self.createGenericFolder(PrivateFIDs.IPMSUBTREE, self.user.ID)
        self.createGenericFolder(PrivateFIDs.INBOX, self.user.ID)
        self.createGenericFolder(PrivateFIDs.DRAFT, self.user.ID)
        self.createGenericFolder(PrivateFIDs.OUTBOX, self.user.ID)
        self.createGenericFolder(PrivateFIDs.SENT_ITEMS, self.user.ID)
        self.createGenericFolder(PrivateFIDs.DELETED_ITEMS, self.user.ID)
        self.createGenericFolder(PrivateFIDs.CONTACTS, self.user.ID)
        self.createGenericFolder(PrivateFIDs.CALENDAR, self.user.ID)
        self.createGenericFolder(PrivateFIDs.JOURNAL, self.user.ID)
        self.createGenericFolder(PrivateFIDs.NOTES, self.user.ID)
        self.createGenericFolder(PrivateFIDs.TASKS, self.user.ID)
        self.createGenericFolder(PrivateFIDs.QUICKCONTACTS, self.user.ID)
        self.createGenericFolder(PrivateFIDs.IMCONTACTLIST, self.user.ID)
        self.createGenericFolder(PrivateFIDs.GALCONTACTS, self.user.ID)
        self.createGenericFolder(PrivateFIDs.JUNK, self.user.ID)
        self.createGenericFolder(PrivateFIDs.CONVERSATION_ACTION_SETTINGS, self.user.ID)
        self.createGenericFolder(PrivateFIDs.DEFERRED_ACTION, self.user.ID)
        self.createSearchFolder(PrivateFIDs.SPOOLER_QUEUE, self.user.ID)
        self.createGenericFolder(PrivateFIDs.COMMON_VIEWS, self.user.ID)
        self.createGenericFolder(PrivateFIDs.SCHEDULE, self.user.ID)
        self.createGenericFolder(PrivateFIDs.FINDER, self.user.ID)
        self.createGenericFolder(PrivateFIDs.VIEWS, self.user.ID)
        self.createGenericFolder(PrivateFIDs.SHORTCUTS, self.user.ID)
        self.createGenericFolder(PrivateFIDs.SYNC_ISSUES, self.user.ID)
        self.createGenericFolder(PrivateFIDs.CONFLICTS, self.user.ID)
        self.createGenericFolder(PrivateFIDs.LOCAL_FAILURES, self.user.ID)
        self.createGenericFolder(PrivateFIDs.SERVER_FAILURES, self.user.ID)
        self.createGenericFolder(PrivateFIDs.LOCAL_FREEBUSY, self.user.ID)
        self.exmdb.execute("INSERT INTO configurations VALUES (?, ?)", (ConfigIDs.MAILBOX_GUID, str(GUID.random())))
        self.exmdb.commit()
        self.exmdb.close()
        self.exmdb = None

    def createMidb(self):
        """Create midb SQLite database for user.

        Database is placed under <homedir>/exmdb/midb.sqlite3.
        """
        if self.mkext("gromox-mkmidb", self.user.username):
            return
        dbPath = os.path.join(self.user.maildir, "exmdb", "midb.sqlite3")
        shutil.copy("res/midb.sqlite3", dbPath)
        DB = sqlite3.connect(dbPath)
        DB.execute("INSERT INTO configurations VALUES (1, ?)", (self.user.username,))
        DB.commit()
        DB.close()
