# -*- coding: utf-8 -*-
"""
Created on Tue Jun 23 18:57:07 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: _Placeholder_copyright_
"""

from .DataModel import BoolP

class PrivilegeBits:
    """Helper class providing property access to privilege bits"""

    BACKUP = 1 << 0
    MONITOR = 1 << 1
    UNCHECKUSR = 1 << 2
    SUBSYSTEM = 1 << 3
    NETDISK = 1 << 4
    EXTPASSWD = 1 << 5

    def _setFlag(self, flag, val):
        self.privilegeBits = (self.privilegeBits or 0) | flag if val else (self.privilegeBits or 0) & ~flag

    def _getFlag(self, flag):
        return bool(self.privilegeBits or 0 & flag)

    @property
    def mailBackup(self):
        return self._getFlag(self.BACKUP)

    @mailBackup.setter()
    def mailBackup(self, val):
        self._setFlag(self.BACKUP, val)

    @property
    def mailMonitor(self):
        return self._getFlag(self.MONITOR)

    @mailMonitor.setter()
    def mailMonitor(self, val):
        self._setFlag(self.MONITOR, val)

    @property
    def ignoreCheckingUser(self):
        return self._getFlag(self.UNCHECKUSR)

    @ignoreCheckingUser.setter()
    def ignoreCheckingUser(self, val):
        self._setFlag(self.UNCHECKUSR, val)

    @property
    def mailSubSystem(self):
        return self._getFlag(self.SUBSYSTEM)

    @mailSubSystem.setter()
    def mailSubSystem(self, val):
        self._setFlag(self.SUBSYSTEM, val)

    @property
    def netDisk(self):
        return self._getFlag(self.NETDISK)

    @netDisk.setter()
    def netDisk(self, val):
        self._setFlag(self.NETDISK, val)

    privilegeProps= (BoolP("mailBackup"),
                     BoolP("mailMonitor"),
                     BoolP("ignoreCheckingUser"),
                     BoolP("mailSubSystem"),
                     BoolP("netDisk"))
