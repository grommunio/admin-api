# -*- coding: utf-8 -*-
"""
Created on Wed Aug 12 12:33:26 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: Grammm GmbH, 2020
"""

from .constants import PropTypes
from .exc import MapiError

class SvrEid:
    def __init__(self, buffer):
        length = buffer.readInt(2)
        ours = buffer.readInt(1)
        if ours == 0:
            self.folderId = 0
            self.messageId = 0
            self.instance = 0
            data = buffer.read(length-1)
        if length != 21:
            raise MapiError("Could not decode SvrEid: Invalid data length", found=length, expected=21)
        self.data = None
        self.folderId = buffer.readInt(8)
        self.messageID = buffer.readInt(8)
        self.instance = buffer.readInt(4)


class Proptag:
    def __init__(self, buffer):
        self.tag = buffer.readInt(4)
        self.type = self.tag & 0xFFFF
        self.value = self.deserializeValue(buffer)

    def _deserializeValue(self, buffer):
        self.type = self.type & ~0x3000 if (0x3000 == self.type&0x3000) else self.type
        if self.type == PropTypes.UNSPECIFIED:
            self.type = buffer.readInt(2)
        if self.type == PropTypes.SHORT:
            self.value = buffer.readInt(2)
        elif self.type in (PropTypes.LONG, PropTypes.ERROR):
            self.value = buffer.readInt(4)
        elif self.type == PropTypes.FLOAT:
            self.value = buffer.getOne("f")
        elif self.type in (PropTypes.DOUBLE, PropTypes.FLOATINGTIME):
            self.value = buffer.getOne("d")
        elif self.type == PropTypes.BYTE:
            self.value = buffer.readInt(1)
        elif self.type in (PropTypes.CURRENCY, PropTypes.LONGLONG, PropTypes.FILETIME):
            self.value = buffer.readInt(8)
        elif self.type == PropTypes.STRING:
            self.value = buffer.readString()
        elif self.type == PropTypes.WSTRING:
            self.value = buffer.readWString()
        elif self.type == PropTypes.SVREID:
            self.value = SvrEid(buffer)
        else:
            raise NotImplementedError("Deserialization of this proptag is currently not implemented")

    def __repr__(self):


