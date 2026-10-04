# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grommunio GmbH

import os
import shutil
import subprocess

from .misc import GenericObject, setDirectoryOwner, setDirectoryPermission
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



def midbUnload(maildir):
    """Ask the local midb to drop its cache of a mailbox.

    midb keeps a notification subscription on every mailbox it has loaded
    (i.e. after IMAP or POP3 access) for up to midb_cache_interval, which keeps
    exmdb from unloading the store.

    Parameters
    ----------
    maildir : str
        Mailbox directory

    Returns
    -------
    bool
        Whether midb unloaded the mailbox.
    """
    import socket
    host = Config["options"].get("midbHost", "::1")
    port = int(Config["options"].get("midbPort", 5555))
    try:
        with socket.create_connection((host, port), timeout=2) as sock, sock.makefile("rwb") as conn:
            if not conn.readline().startswith(b"OK"):
                return False
            conn.write(b"X-UNLD "+maildir.encode()+b"\r\n")
            conn.flush()
            return conn.readline().startswith(b"TRUE")
    except OSError as err:
        logger.debug(f"midb unload of '{maildir}' failed: {err}")
        return False


def unloadStore(maildir, hostname=None, attempts=3, delay=1):
    """Unload a mailbox store from exmdb.

    exmdb refuses to unload a store while clients still hold it (open tables,
    notification subscriptions), reporting a "Dispatch error". The unload is
    therefore retried a few times, asking midb to release the store first.

    If the local exmdb cannot be reached, it cannot hold the store either and
    the store is considered unloaded. An unreachable remote exmdb might still
    hold it.

    Parameters
    ----------
    maildir : str
        Directory of the store, must belong to an existing user
    hostname : str, optional
        exmdb host. The default is None, using the configured exmdbHost.
    attempts : int, optional
        Number of unload attempts. The default is 3.
    delay : float, optional
        Seconds to wait between attempts. The default is 1.

    Returns
    -------
    bool
        False if the store is (possibly) still in use, True otherwise.
    """
    from services import Service
    for attempt in range(attempts):
        if attempt:
            time.sleep(delay)
        midbUnload(maildir)
        with Service("exmdb", errors=Service.SUPPRESS_INOP) as exmdb:
            try:
                exmdb.ExmdbQueries(hostname or exmdb.host, exmdb.port, maildir, True).unloadStore(maildir)
                return True
            except exmdb.ConnectionError as err:
                logger.warning(f"Could not unload store '{maildir}': {err}")
                return hostname is None
            except exmdb.ExmdbError as err:
                logger.info(f"Failed to unload store '{maildir}' ({attempt+1}/{attempts}): {err}")
                continue
        logger.warning(f"Could not unload store '{maildir}': exmdb service not available")
        return hostname is None
    return False


class StoreInUseError(Exception):
    """The mailbox store of a user cannot be unloaded and the deletion cannot be deferred."""


def _removeSkeleton(path):
    """Remove `path` if it only contains empty directories.

    exmdb recreates <maildir>/exmdb when trying to open a store whose directory
    has been moved away.
    """
    try:
        for root, dirs, files in os.walk(path, topdown=False):
            if files:
                return False
            os.rmdir(root)
    except OSError:
        return not os.path.exists(path)
    return True


def _restoreTrash(maildir, trash):
    """Move a mailbox directory back from the trash location."""
    if os.path.exists(maildir) and not _removeSkeleton(maildir):
        raise OSError(f"Cannot restore '{trash}': '{maildir}' exists")
    os.rename(trash, maildir)


def _recoverTrash(maildir, trash):
    """Handle a trash directory left over from an interrupted deletion.

    If the mailbox directory is missing, the deletion of this user was interrupted
    and the directory is moved back. Otherwise the trash belongs to an earlier
    user with the same path and is moved aside.
    """
    if not os.path.exists(maildir) or _removeSkeleton(maildir):
        os.rename(trash, maildir)
        return
    stale = f"{trash}.{int(time.time())}"
    counter = 0
    while os.path.exists(stale):
        counter += 1
        stale = f"{trash}.{int(time.time())}~{counter}"
    logger.warning(f"Moving stale '{trash}' to '{stale}'")
    os.rename(trash, stale)


def tryRemoveUser(userID, deleteFiles=False, deleteChatUser=True, attempts=3, status=None, check=None):
    """Delete a user if its mailbox store can be unloaded.

    The store must be unloaded while the user still exists: exmdb only accepts
    connections for directories found in the `users` table, and gromox clients
    cannot release their hold on a store (notification subscriptions) once the
    user is gone, pinning it until gromox-http is restarted.

    Before removing the files, the directory is moved away and the store
    unloaded again, so that a client reopening the store in the meantime does
    not leave exmdb serving a deleted mailbox at a path that may be reused.
    Once moved, the store cannot be reopened as its database file is missing.

    The user row is locked for the duration, serializing concurrent deletions.

    Parameters
    ----------
    userID : int
        ID of the user to delete
    deleteFiles : bool, optional
        Whether to remove the mailbox directory. The default is False.
    deleteChatUser : bool, optional
        Whether to permanently delete the chat user. The default is True.
    attempts : int, optional
        Number of unload attempts. The default is 3.
    status : int, optional
        Only delete the user if it has this status. The default is None.
    check : callable, optional
        Called after locking the user, the user is only deleted if it returns True. The default is None.

    Returns
    -------
    bool
        True if the user was deleted (or does not exist anymore), False if the store is still in use
        or the user does not have the requested status.
    """
    from orm import DB
    from orm.users import Users
    DB.session.rollback()  # Fresh snapshot, a locking read of a row changed since the last read fails otherwise
    user = Users.query.filter(Users.ID == userID).with_for_update().populate_existing().first()
    if user is None:
        DB.session.rollback()
        return True
    if status is not None and user.status != status or check is not None and not check():
        DB.session.rollback()
        return False
    maildir = user.maildir.rstrip("/") if user.status != Users.CONTACT else ""
    hostname = user.homeserver.hostname if user.homeserver is not None else None
    trash = f"{maildir}@deleting"  # Cannot collide with paths from createPath, which splits names at '@'
    moved = False
    try:
        if maildir:
            if os.path.isdir(trash):
                _recoverTrash(maildir, trash)
            if not unloadStore(maildir, hostname, attempts):
                DB.session.rollback()
                return False
            if deleteFiles and os.path.isdir(maildir):
                try:
                    os.rename(maildir, trash)
                    moved = True
                except OSError as err:
                    logger.warning(f"Could not move '{maildir}' for removal: {err}")
                if moved and not unloadStore(maildir, hostname, 1):
                    _restoreTrash(maildir, trash)
                    DB.session.rollback()
                    return False
        user.delete(deleteChatUser)
        DB.session.commit()
    except Exception:
        DB.session.rollback()
        if moved:
            _restoreTrash(maildir, trash)
        raise
    if moved:
        shutil.rmtree(trash, ignore_errors=True)
        _removeSkeleton(maildir)
    elif deleteFiles and maildir:
        shutil.rmtree(maildir, ignore_errors=True)
    return True


def removeUser(userID, deleteFiles=False, deleteChatUser=True, attempts=3, permission=None):
    """Delete a user, deferring the deletion while its mailbox store is in use.

    If the store cannot be unloaded, the user is marked as deleted, which stops
    logins and mail delivery, and a background task completes the deletion
    once the clients have released the store.

    Parameters
    ----------
    userID : int
        ID of the user to delete
    deleteFiles : bool, optional
        Whether to remove the mailbox directory. The default is False.
    deleteChatUser : bool, optional
        Whether to permanently delete the chat user. The default is True.
    attempts : int, optional
        Number of unload attempts. The default is 3.
    permission : PermissionBase, optional
        Permission required to access the background task. The default is None.

    Raises
    ------
    StoreInUseError
        The store is in use and no background task can be created.

    Returns
    -------
    tools.tasq.Task
        Background task completing the deletion, or None if the user was deleted.
    """
    if tryRemoveUser(userID, deleteFiles, deleteChatUser, attempts):
        return None
    from orm import DB
    from orm.users import Users
    from services import Service
    from .tasq import TasQServer, Worker
    if Config["tasq"].get("disabled", False) or not TasQServer.online():
        raise StoreInUseError("Mailbox store is in use, try again later")
    DB.session.rollback()
    user = Users.query.filter(Users.ID == userID).with_for_update().first()
    if user is None:
        DB.session.rollback()
        return None
    cancelled = TasQServer.cancelUserDeletion(userID, "Superseded by a new deletion")
    try:
        chatActive = any(params.get("chatActive") for params in cancelled) or user.chat
    except Exception:
        chatActive = False
    chatUser = GenericObject(chatID=user.chatID)
    user.status = Users.DELETED  # Committed together with the task
    try:
        task = TasQServer.create("delUser", dict(userID=userID, deleteFiles=deleteFiles, deleteChatUser=deleteChatUser,
                                                 chatActive=chatActive,
                                                 notBefore=time.time()+Worker._deleteUserRetryDelays[0]),
                                 permission=permission, inline=False)
    except Exception:
        DB.session.rollback()
        raise
    if task.ID <= 0:
        DB.session.rollback()
        raise StoreInUseError("Mailbox store is in use, try again later")
    if chatActive:
        with Service("chat", errors=Service.SUPPRESS_ALL) as chat:
            chat.activateUser(chatUser, False)
    return task
