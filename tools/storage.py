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

import exmdb.domain as DomainDB

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tools.config import Config
from tools.constants import PropTags, ConfigIDs, PublicFIDs, Permissions
from tools.misc import ntTime

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

class DomainSetup:
    """Domain initialization context.

    Can be used in a with context to ensure automatic cleanup of created directories if an error occurs.
    Invocation of the run() method creates the complete directory structure required by a domain and
    sets up the initial MS Exchange database.

    If everything went well, the `success` attribute is set to True.
    If any exception occurs it is caught and the stack trace is written to the log. In this case, the `error` attribute
    contains a short error description and the `errorCode` attribute is set to an appropriate HTTP status code.
    """
    ALLOCATED_EID_RANGE = 0x10000
    CHANGE_NUMBER_BEGIN = 0x800000000000

    def __init__(self, domain, area):
        """Initialize context object

        Parameters
        ----------
        domain : orm.orgs.Domains
            Domain to initialize.
        area : orm.ext.AreaList
            Storage area to place domain in.
        """
        self._dirs = []
        self._lastEid = self.ALLOCATED_EID_RANGE
        self._lastCn = self.CHANGE_NUMBER_BEGIN
        self._lastArt = 0

        self.domain = domain
        self.area = area

        self.success = False
        self.error = self.errorCode = None

    def __enter__(self):
        """Enter context."""
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

        If an error occurs (e.g. a directory cannot be created), all directories that were created are automatically deleted
        (though intermediates may remain). Related exceptions are not handled.

        Parameters
        ----------
        domain : orm.orgs.Domains
            Domain to create the directory for
        area : orm.ext.AreaList
            Storage area to place the files in
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

    def createGenericFolder(self, folderID: int, parentID: int, domainID: int, displayName: str, containerClass: str = None):
        """Create a generic MS Exchange folder.

        Parameters
        ----------
        folderID : int
            ID of the new folder.
        parentID : int
            ID of the parent folder (or `None` to create root folder).
        domainID : int
            ID of the domain to create the folder for.
        displayName : str
            Name of the folder.
        containerClass : str, optional
            Container class of the folder. The default is None.
        """
        currentEid = self._lastEid+1
        self._lastEid += self.ALLOCATED_EID_RANGE
        maxEid = self._lastEid
        self._exmdb.add(DomainDB.AllocatedEids(begin=currentEid, end=maxEid, time=int(time.time()), isSystem=1))
        self._lastCn += 1
        changeNum = self._lastCn
        self._exmdb.add(DomainDB.Folders(ID=folderID, parentID=parentID, changeNum=changeNum, currentEid=currentEid, maxEid=maxEid))
        self._lastArt += 1
        ntNow = ntTime()
        xidData = XID.fromDomainID(domainID, changeNum).serialize()
        if containerClass is not None:
            self._exmdb.add(DomainDB.FolderProperties(folderID=folderID, proptag=PropTags.CONTAINERCLASS, propval=containerClass))
        self._exmdb.add(DomainDB.FolderProperties(folderID=folderID, proptag=PropTags.DELETEDCOUNTTOTAL, propval=0))
        self._exmdb.add(DomainDB.FolderProperties(folderID=folderID, proptag=PropTags.DELETEDFOLDERTOTAL, propval=0))
        self._exmdb.add(DomainDB.FolderProperties(folderID=folderID, proptag=PropTags.HIERARCHYCHANGENUMBER, propval=0))
        self._exmdb.add(DomainDB.FolderProperties(folderID=folderID, proptag=PropTags.INTERNETARTICLENUMBER, propval=self._lastArt))
        self._exmdb.add(DomainDB.FolderProperties(folderID=folderID, proptag=PropTags.ARTICLENUMBERNEXT, propval=1))
        self._exmdb.add(DomainDB.FolderProperties(folderID=folderID, proptag=PropTags.DISPLAYNAME, propval=displayName))
        self._exmdb.add(DomainDB.FolderProperties(folderID=folderID, proptag=PropTags.COMMENT, propval=""))
        self._exmdb.add(DomainDB.FolderProperties(folderID=folderID, proptag=PropTags.CREATIONTIME, propval=ntNow))
        self._exmdb.add(DomainDB.FolderProperties(folderID=folderID, proptag=PropTags.LASTMODIFICATIONTIME, propval=ntNow))
        self._exmdb.add(DomainDB.FolderProperties(folderID=folderID, proptag=PropTags.LOCALCOMMITTIMEMAX, propval=ntNow))
        self._exmdb.add(DomainDB.FolderProperties(folderID=folderID, proptag=PropTags.HIERREV, propval=ntNow))
        self._exmdb.add(DomainDB.FolderProperties(folderID=folderID, proptag=PropTags.CHANGEKEY, propval=xidData))
        self._exmdb.add(DomainDB.FolderProperties(folderID=folderID, proptag=PropTags.PREDECESSORCHANGELIST, propval=xidData))

    def createExmdb(self):
        """Create exchange SQLite database for domain.

        Database is placed under <homedir>/exmdb/exchange.sqlite3.

        Propnames are filled automatically if the file `dataPath`/`serverAdminDir`/propnames.txt is found.
        """
        dbPath = os.path.join(self.domain.homedir, "exmdb", "exchange.sqlite3")
        engine = create_engine("sqlite:///"+dbPath)
        DomainDB.Schema.metadata.create_all(engine)
        self._exmdb = sessionmaker(bind=engine)()
        self._exmdb.execute("PRAGMA journal_mode = WAL;")
        try:
            dataPath = os.path.join(Config["options"]["dataPath"], Config["options"]["systemAdminDir"], "propnames.txt")
            with open(dataPath) as file:
                propid = 0x8001
                for line in file:
                    self._exmdb.add(DomainDB.NamedProperties(ID=propid, name=line.strip()))
                    propid += 1
        except FileNotFoundError:
            logging.warn("Could not open {} - skipping.".format(dataPath))
        self._exmdb.add(DomainDB.StoreProperties(tag=PropTags.CREATIONTIME, value=ntTime()))
        self._exmdb.add(DomainDB.StoreProperties(tag=PropTags.PROHIBITRECEIVEQUOTA, value=self.domain.maxSize))
        self._exmdb.add(DomainDB.StoreProperties(tag=PropTags.PROHIBITSENDQUOTA, value=self.domain.maxSize))
        self._exmdb.add(DomainDB.StoreProperties(tag=PropTags.STORAGEQUOTALIMIT, value=self.domain.maxSize))
        self._exmdb.add(DomainDB.StoreProperties(tag=PropTags.MESSAGESIZEEXTENDED, value=0))
        self._exmdb.add(DomainDB.StoreProperties(tag=PropTags.ASSOCMESSAGESIZEEXTENDED, value=0))
        self._exmdb.add(DomainDB.StoreProperties(tag=PropTags.NORMALMESSAGESIZEEXTENDED, value=0))
        self.createGenericFolder(PublicFIDs.ROOT, None, self.domain.ID, "Root Container")
        self.createGenericFolder(PublicFIDs.IPMSUBTREE, PublicFIDs.ROOT, self.domain.ID, "IPM_SUBTREE")
        self.createGenericFolder(PublicFIDs.NONIPMSUBTREE, PublicFIDs.ROOT, self.domain.ID, "NON_IPM_SUBTREE")
        self.createGenericFolder(PublicFIDs.EFORMSREGISTRY, PublicFIDs.NONIPMSUBTREE, self.domain.ID, "EFORMS_REGISTRY")
        self._exmdb.add(DomainDB.Configurations(ID=ConfigIDs.MAILBOX_GUID, value=str(GUID.random())))
        self._exmdb.add(DomainDB.Configurations(ID=ConfigIDs.CURRENT_EID, value=0x100))
        self._exmdb.add(DomainDB.Configurations(ID=ConfigIDs.MAXIMUM_EID, value=self.ALLOCATED_EID_RANGE))
        self._exmdb.add(DomainDB.Configurations(ID=ConfigIDs.LAST_CHANGE_NUMBER, value=self._lastCn))
        self._exmdb.add(DomainDB.Configurations(ID=ConfigIDs.LAST_CID, value=0))
        self._exmdb.add(DomainDB.Configurations(ID=ConfigIDs.LAST_ARTICLE_NUMBER, value=self._lastArt))
        self._exmdb.add(DomainDB.Configurations(ID=ConfigIDs.SEARCH_STATE, value=0))
        self._exmdb.add(DomainDB.Configurations(ID=ConfigIDs.DEFAULT_PERMISSION, value=Permissions.domainDefault()))
        self._exmdb.add(DomainDB.Configurations(ID=ConfigIDs.ANONYMOUS_PERMISSION, value=0))
        self._exmdb.commit()


def mkdirFailsafe(path: str):
    """Try to create directory.

    Creates intermediate directories if needed. If an exception is raised, it is caught and logged.

    Parameters
    ----------
    path : str
        Path to create
    """
    if path is None:
        return
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as err:
        logging.warn("Could not create directory '{}': {}".format(path, " - ".join((str(arg) for arg in err.args))))
    except BaseException as err:
        logging.error("Could not create directory '{}': Unknown error {}".format(path, str(err)))
