# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH

from . import ServiceHub


def exmdbHandleException(service, error):
    if isinstance(error, ExmdbService.ExmdbError):
        return 0, error.args[0]
    elif isinstance(error, RuntimeError):
        return ServiceHub.UNAVAILABLE


@ServiceHub.register("exmdb", exmdbHandleException)
class ExmdbService:
    __loaded = False
    __symbols = ("ExmdbError", "ExmdbQueries", "Folder", )
    __methods = ("TaggedPropval", "FolderList", "FolderOwnerList")

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
            import pyexmdb
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
