# -*- coding: utf-8 -*-
"""
Created on Fri Jul  3 13:31:17 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: Grammm GmbH, 2020
"""

from random import SystemRandom
from .constants import SERIAL_ENDIAN

class GUID:
    rndEng = SystemRandom()

    def __init__(self):
        pass

    @staticmethod
    def fromDomainID(domainID : int):
        guid = GUID()
        guid.timeLow: int = domainID
        guid.timeMid: int = 0xafb
        guid.timeHiAndVersion: int = 0x7df6
        guid.clockSeq: tuple = (0x91, 0x92)
        guid.node: tuple = (0x49, 0x88, 0x6a, 0xa7, 0x38, 0xce)
        return guid

    @staticmethod
    def random():
        guid = GUID()
        guid.timeLow: int = GUID.rndEng.getrandbits(32)
        guid.timeMid: int = GUID.rndEng.getrandbits(16)
        guid.timeHiAndVersion: int = GUID.rndEng.getrandbits(16) & 0x0FFF | 0x4000
        guid.clockSeq: tuple = (GUID.rndEng.getrandbits(8) & 0x3f | 0x80, GUID.rndEng.getrandbits(8))
        guid.node: tuple = tuple(GUID.rndEng.getrandbits(8) for _ in range(6))
        return guid

    def serialize(self) -> bytes:
        return self.timeLow.to_bytes(4, SERIAL_ENDIAN)+\
               self.timeMid.to_bytes(2, SERIAL_ENDIAN)+\
               self.timeLow.to_bytes(2, SERIAL_ENDIAN)+\
               bytes(self.clockSeq)+bytes(self.node)

    def __str__(self):
        return "{:08x}-{:04x}-{:04x}-{:02x}{:02x}-{:02x}{:02x}{:02x}{:02x}{:02x}{:02x}".format(self.timeLow,
                                                                                               self.timeMid,
                                                                                               self.timeHiAndVersion,
                                                                                               *self.clockSeq,
                                                                                               *self.node)

class XID:
    def __init__(self):
        pass

    @staticmethod
    def fromDomainID(domainID: int, changeID: int):
        xid = XID()
        xid.guid = GUID.fromDomainID(domainID)
        xid.localID = tuple(i for i in changeID.to_bytes(6, "big"))
        return xid

    def serialize(self) -> bytes:
        return self.guid.serialize()+bytes(self.localID);
