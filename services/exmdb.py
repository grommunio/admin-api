# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH

from . import ServiceHub


def exmdbHandleException(service, error):
    if isinstance(error, ExmdbService.ConnectionError):
        return ServiceHub.UNAVAILABLE, error.args[0]


@ServiceHub.register("exmdb", exmdbHandleException)
class ExmdbService:
    class _BoundClient:
        def __init__(self, exmdb, host, port, homedir, isPrivate):
            self.__homedir = homedir
            self.__client = exmdb.ExmdbQueries(host, port, homedir, isPrivate)

        def __getattr__(self, attr):
            target = getattr(self.__client, attr)
            if callable(target):
                return lambda *args, **kwargs: target(self.__homedir, *args, **kwargs)
            return target

    __loaded = False
    __symbols = ("ConnectionError", "ExmdbError", "ExmdbProtocolError", "SerializationError", "ExmdbQueries", "Folder",
                 "Restriction")
    __methods = ("TaggedPropval", "FolderList", "FolderMemberList")

    def __init__(self):
        self._loadPyexmdb()
        for method in self.__methods:
            setattr(self, method, getattr(self.pyexmdb, method))

    @classmethod
    def _loadPyexmdb(cls):
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

    def client(self, homedir, isPrivate):
        """Shortcut for creating a client.

        Parameters
        ----------
        homedir : str
            Home directory of the user or domain.
        isPrivate : bool
            Whether it is a user (True) or domain (False) database

        Returns
        -------
        pyexmdb.ExmdbQueries
            Exmdb client
        """
        return self.ExmdbQueries(self.host, self.port, homedir, isPrivate)

    def user(self, user):
        """Create client for user.

        Connect to the users homeserver if specified, otherwise connect to configured exmdbHost.
        Connection is always established using the exmdbPort from the configuration.

        Parameters
        ----------
        user : orm.users.Users
            User object providing homeserver and maildir.

        Returns
        -------
        services.exmdb.ExmdbService._BoundClient
            Exmdb client bound to the specific user
        """
        host = user.homeserver.hostname if user.homeserver is not None else self.host
        return self._BoundClient(self, host, self.port, user.maildir, True)

    def domain(self, domain):
        """Create client for domain.

        Connect to the domains homeserver if specified, otherwise connect to configured exmdbHost.
        Connection is always established using the exmdbPort from the configuration.

        Parameters
        ----------
        domain : orm.domains.Domain
            Domain object providing homeserver and homedir.

        Returns
        -------
        services.exmdb.ExmdbService._BoundClient
            Exmdb client bound to the specific domain
        """
        host = domain.homeserver.hostname if domain.homeserver is not None else self.host
        return self._BoundClient(self, host, self.port, domain.homedir, False)
