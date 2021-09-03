# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH

from . import ServiceHub


def exmdbHandleException(service, error):
    if isinstance(error, RuntimeError):
        return ServiceHub.UNAVAILABLE
    elif isinstance(error, ExmdbService.ExmdbError):
        from tools.constants import ExmdbCodes
        return 0, "exmdb query failed with code "+ExmdbCodes.lookup(error.code, hex(error.code))


@ServiceHub.register("exmdb", exmdbHandleException)
class ExmdbService:
    __loaded = False
    __symbols = ("ExmdbError", "ExmdbQueries", "Folder", "FolderListResponse", "FolderOwnerListResponse")
    __methods = ("TaggedPropval_u64", "TaggedPropval_str")

    def __init__(self):
        self.loadPyexmdb()
        for method in self.__methods:
            setattr(self, method, getattr(self.pyexmdb, method))

    @classmethod
    def loadPyexmdb(cls):
        if cls.__loaded:
            return
        try:
            from tools.config import Config
            from tools.pyexmdb import pyexmdb
            for symbol in cls.__symbols:
                setattr(cls, symbol, getattr(pyexmdb, symbol))
        except Exception:
            for symbol in cls.__symbols:
                setattr(cls, symbol, type(None))
            raise

        cls.host = Config["options"].get("exmdbHost", "::1")
        cls.port = Config["options"].get("exmdbPort", "5000")
        cls.pyexmdb = pyexmdb
        cls.loaded = True
