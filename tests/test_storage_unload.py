# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 grommunio GmbH

"""Tests for unloading mailbox stores, no midb or exmdb required.

Run from the source root: python3 -m unittest discover tests
"""

import os
import sys
import types
import unittest

from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import storage

MAILDIR = "/var/lib/gromox/user/example.com/user"
HOMESERVER = ("mail.example.com", 5555)
CONFIGURED = ("::1", 5555)


class _ConnectionError(RuntimeError):
    pass


class _Midb:
    """Stand-in for a connection to midb, which answers with the given lines."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.sent = b""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def makefile(self, mode):
        return self

    def readline(self):
        return self.answers.pop(0)

    def write(self, data):
        self.sent += data

    def flush(self):
        pass


class MidbUnload(unittest.TestCase):
    def setUp(self):
        self.midb = {}
        self.connects = []
        patcher = mock.patch("socket.create_connection", self.connect)
        patcher.start()
        self.addCleanup(patcher.stop)

    def connect(self, target, timeout=None):
        self.connects.append(target)
        if target not in self.midb:
            raise ConnectionRefusedError(111, "Connection refused")
        return self.midb[target]

    def test_targets(self):
        for hostname, targets in ((None, [CONFIGURED]), ("::1", [CONFIGURED]), ("mail.example.com", [HOMESERVER, CONFIGURED])):
            with self.subTest(hostname=hostname), self.assertLogs("storage", "DEBUG"):
                self.connects.clear()
                self.assertFalse(storage.midbUnload(MAILDIR, hostname))
                self.assertEqual(self.connects, targets)

    def test_homeserver(self):
        self.midb[HOMESERVER] = _Midb(b"OK\r\n", b"TRUE 1\r\n")
        self.assertTrue(storage.midbUnload(MAILDIR, "mail.example.com"))
        self.assertEqual(self.midb[HOMESERVER].sent, b"X-UNLD "+MAILDIR.encode()+b"\r\n")
        self.midb[HOMESERVER] = _Midb(b"OK\r\n", b"FALSE 2\r\n")
        self.midb[CONFIGURED] = _Midb(b"OK\r\n", b"TRUE 1\r\n")
        self.assertFalse(storage.midbUnload(MAILDIR, "mail.example.com"))
        self.assertEqual(self.connects, [HOMESERVER, HOMESERVER])

    def test_fallback(self):
        self.midb[HOMESERVER] = _Midb(b"FALSE Access denied")
        self.midb[CONFIGURED] = _Midb(b"OK\r\n", b"TRUE 1\r\n")
        with self.assertLogs("storage", "DEBUG"):
            self.assertTrue(storage.midbUnload(MAILDIR, "mail.example.com"))
        self.assertEqual(self.connects, [HOMESERVER, CONFIGURED])


class UnloadStore(unittest.TestCase):
    def setUp(self):
        self.exmdb = mock.Mock(host="::1", port="5000", ExmdbError=RuntimeError, ConnectionError=_ConnectionError)
        services = types.ModuleType("services")
        services.Service = mock.MagicMock()
        services.Service.return_value.__enter__.return_value = self.exmdb
        patcher = mock.patch.dict(sys.modules, {"services": services})
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(storage, "midbUnload")
        self.midbUnload = patcher.start()
        self.addCleanup(patcher.stop)

    def test_homeserver(self):
        self.assertTrue(storage.unloadStore(MAILDIR, "mail.example.com"))
        self.exmdb.ExmdbQueries.assert_called_once_with("mail.example.com", "5000", MAILDIR, True)
        self.midbUnload.assert_called_once_with(MAILDIR, "mail.example.com")

    def test_unreachable(self):
        self.exmdb.ExmdbQueries.side_effect = _ConnectionError("Connect failed: Connection refused")
        for hostname, host, unloaded in ((None, "::1", True), ("localhost", "::1", True),
                                         ("mail.example.com", "::1", False), (None, "exmdb.example.com", False)):
            with self.subTest(hostname=hostname, host=host), self.assertLogs("storage", "WARNING"):
                self.exmdb.host = host
                self.assertIs(storage.unloadStore(MAILDIR, hostname), unloaded)


if __name__ == "__main__":
    unittest.main()
