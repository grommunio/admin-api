# -*- coding: utf-8 -*-
"""
Created on Tue Aug 11 11:29:54 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: Grammm GmbH, 2020
"""

from collections.abc import Iterable
from itertools import islice
import struct

from .constants import CallIDs, PropTypes
from .exc import MapiError


def _bin(data, size: int = 1):
    """Generate bytes representation of intrinsic types.

    Parameters
    ----------
    data : Any
        Data to serialize
    size : int, optional
        Number of bytes used for integers. The default is 1.

    Returns
    -------
    bytes
        Byte representation of data
    """
    if isinstance(data, str):
        return bytes(data, "utf8") + b"\0"
    elif isinstance(data, int):
        return data.to_bytes(size, "little")
    elif isinstance(data, Iterable):
        return b"".join(_bin(element, size) for element in data)
    elif hasattr(data, "serialize"):
        return data.serialize()


def _opt(data, size=1):
    """Serialize optional parameter.

    Optional parameters are prefixed with an additional byte indicating presence of optional data.

    Parameters
    ----------
    data : Any
        Data to serialize.
    size : int, optional
        Number of bytes used for integers. The default is 1.

    Returns
    -------
    TYPE
        DESCRIPTION.

    """
    return _bin(0) if data is None else _bin(1)+_bin(data, size)


class GenericObject:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __setattr__(self, name, value):
        self.__dict__[name] = value

    def __repr__(self):
        return "GenericObject({})".format(", ".join("{}={}".format(key, value)
                                                    for key, value in self.__dict__.items() if not key.startswith("_")))


class Buffer:
    def __init__(self, data: bytes = b"", wstringUtf16 = False):
        self.data = data
        self.rpos = 0
        self.wstringUtf16 = wstringUtf16

    def read(self, count: int = None) -> bytes:
        data = self.data[self.rpos:(self.rpos+count if count is not None else None)]
        self.rpos = self.rpos+count if count is not None else len(self.data)
        return data

    def readInt(self, count: int, byteorder: str = "little") -> int:
        value = int.from_bytes(self.data[self.rpos:self.rpos+count], byteorder)
        self.rpos += count
        return value

    def readString(self):
        for i in range(self.rpos, len(self.data)):
            if self.data[i] == 0:
                break
        else:
            raise BufferError("Reached end of buffer while reading string")
        data = self.data[self.rpos:i]
        self.rpos = i+1
        return data.decode("ascii")

    def readWString(self):
        if not self.wstringUtf16:
            return self.readString()
        for i in range(self.rpos, len(self.data), 2):
            if self.data[i] == 0 and self.data[i+1] == 0:
                break
        else:
            raise BufferError("Reached end of buffer while reading wstring")
        data = self.data[self.rpos:i]
        self.rpos = i+2
        return data.decode("utf16")

    def getOne(self, fmt):
        dType = struct.Struct(fmt)
        value = struct.unpack_from(fmt, self.data, self.rpos)[0]
        self.rpos += dType.size
        return value

    def write(self, data: bytes):
        self.data += data


class ConnectRequest:
    def Response(self, data):
        if data is None or len(data) != 0:
            raise MapiError("ConnectRequest: invalid response data")

    def __init__(self, prefix: str, sessionID: str, private: bool):
        self.prefix: str = prefix
        self.sessionID: str = sessionID
        self.private: bool = private

    def serialize(self):
        buffer = _bin(CallIDs.CONNECT)+_bin(self.prefix)+_bin(self.sessionID)+_bin(self.private)
        return _bin(len(buffer), 4)+buffer


class LoadHierarchyTableRequest:
    class Response:
        def __init__(self, data):
            if len(data) != 8:
                raise MapiError("LoadHierarchyTableRequest: invalid response data")
            self.tableId = int.from_bytes(data[0:4], "little")
            self.rowCount = int.from_bytes(data[4:8], "little")

        def __repr__(self):
            return "LoadHierarchyTableRequest.Response(tableId={}, rowCount={})".format(self.tableId, self.rowCount)

    def __init__(self, homedir, folderId, tableFlags, username=None, restriction=None):
        self.homedir = homedir
        self.folderId = folderId
        self.username = username
        self.tableFlags = tableFlags
        self.restriction = restriction

    def serialize(self):
        buffer = _bin(CallIDs.LOAD_HIERARCHY_TABLE) + \
                 _bin(self.homedir) + \
                 _bin(self.folderId, 8) + \
                 _opt(self.username) + \
                 _bin(self.tableFlags) + \
                 _opt(self.restriction)
        return _bin(len(buffer), 4)+buffer


class QueryTableRequest:
    class Response:
        def __init__(self, data):
            if len(data) < 4:
                raise MapiError("QueryTableRequest: invalid response data")
            buffer = Buffer(data)
            count = buffer.readInt(4)
            self.entries = [self.getEntries(buffer) for _ in range(count)]

        def getEntries(self, buffer):
            count = buffer.readInt(2)
            tpv = [self.getTPV(buffer) for _ in range(count)]
            return tpv

        def getTPV(self, buffer):
            prop = GenericObject()
            prop.tag = buffer.readInt(4)
            prop.type = prop.tag & 0xFFFF
            self.getPropval(buffer, prop)
            return prop

        def getPropval(self, buffer, prop):
            prop.type = prop.type & ~0x3000 if (0x3000 == prop.type&0x3000) else prop.type
            if prop.type == PropTypes.UNSPECIFIED:
                prop.type = buffer.readInt(2)
            if prop.type == PropTypes.SHORT:
                prop.value = buffer.readInt(2)
            elif prop.type in (PropTypes.LONG, PropTypes.ERROR):
                prop.value = buffer.readInt(4)
            elif prop.type == PropTypes.FLOAT:
                prop.value = buffer.getOne("f")
            elif prop.type in (PropTypes.DOUBLE, PropTypes.FLOATINGTIME):
                prop.value = buffer.getOne("d")
            elif prop.type == PropTypes.BYTE:
                prop.value = buffer.readInt(1)
            elif prop.type in (PropTypes.CURRENCY, PropTypes.LONGLONG, PropTypes.FILETIME):
                prop.value = buffer.readInt(8)
            elif prop.type == PropTypes.STRING:
                prop.value = buffer.readString()
            elif prop.type == PropTypes.WSTRING:
                prop.value = buffer.readWString()
            else:
                raise NotImplementedError("De-serialization of type {} is not supported".format(prop.type))

        def __repr__(self):
            return "QueryTableRequest.Response(entries={})".format(self.entries)



    def __init__(self, homedir: str, cpid: int, tableId: int, proptags: list, startPos: int, rowNeeded: int,
                 username: str = None):
        self.homedir = homedir
        self.username = username
        self.cpid = cpid
        self.tableId = tableId
        self.proptags = proptags
        self.startPos = startPos
        self.rowNeeded = rowNeeded

    def serialize(self):
        buffer = _bin(CallIDs.QUERY_TABLE) + \
                 _bin(self.homedir) + \
                 _opt(self.username) + \
                 _bin(self.cpid, 4) + \
                 _bin(self.tableId, 4) + \
                 _bin(len(self.proptags), 2) + \
                 _bin(self.proptags, 4) + \
                 _bin(self.startPos, 4) + \
                 _bin(self.rowNeeded, 4)
        return _bin(len(buffer), 4)+buffer


class UnloadTableRequest:
    def Response(self, data):
        if data is None or len(data) != 0:
            raise MapiError("ConnectRequest: invalid response data")

    def __init__(self, homedir: str, tableId: int):
        self.homedir = homedir
        self.tableId = tableId

    def serialize(self):
        buffer = _bin(CallIDs.UNLOAD_TABLE) + \
                 _bin(self.homedir) + \
                 _bin(self.tableId, 4)
        return _bin(len(buffer), 4)+buffer
