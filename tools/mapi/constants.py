# -*- coding: utf-8 -*-
"""
Created on Tue Aug 11 12:12:52 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: Grammm GmbH, 2020
"""

class _ReverseLookup:
    @classmethod
    def lookup(cls, value, default=None):
        if not hasattr(cls, "_lookup"):
            cls._lookup = {getattr(cls, key): key for key in dir(cls) if not key.startswith("_")}
        return cls._lookup.get(value, default)


class CallIDs(_ReverseLookup):
    CONNECT = 0x00
    CREATE_FOLDER_BY_PROPERTIES = 0x15
    DELETE_FOLDER = 0x1a
    LOAD_HIERARCHY_TABLE = 0x26
    LOAD_PERMISSION_TABLE = 0x29
    UNLOAD_TABLE = 0x2b
    QUERY_TABLE = 0x2d
    ALLOCATE_CN = 0x5c
    UPDATE_FOLDER_PERMISSION = 0x6a


class ResponseCodes(_ReverseLookup):
    SUCCESS = 0x00
    ACCESS_DENY = 0x01
    MAX_REACHED = 0x02
    LACK_MEMORY = 0x03
    MISCONFIG_PREFIX = 0x04
    MISCONFIG_MODE = 0x05
    CONNECT_UNCOMPLETE = 0x06
    PULL_ERROR = 0x07
    DISPATCH_ERROR = 0x08
    PUSH_ERROR = 0x09


class PropTypes(_ReverseLookup):
    UNSPECIFIED = 0x0000
    SHORT = 0x0002
    LONG = 0x0003
    FLOAT = 0x0004
    DOUBLE = 0x0005
    CURRENCY = 0x0006
    FLOATINGTIME = 0x0007
    ERROR = 0x000a
    BYTE = 0x000b
    OBJECT = 0x000d
    LONGLONG = 0x0014
    STRING = 0x001e
    WSTRING = 0x001f
    FILETIME = 0x0040
    GUID = 0x0048
    SVREID = 0x00fb
    RESTRICTION = 0x00fd
    RULE = 0x00fe
    BINARY = 0x0102
    SHORT_ARRAY = 0x1002
    LONG_ARRAY = 0x1003
    LONGLONG_ARRAY = 0x1014
    STRING_ARRAY = 0x101e
    WSTRING_ARRAY = 0x101f
    GUID_ARRAY = 0x1048
    BINARY_ARRAY = 0x1102
