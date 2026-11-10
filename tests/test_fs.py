# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 grommunio GmbH

"""Tests for the cleanup of mailbox directories, no database required.

Run from the source root: python3 -m unittest discover tests
"""

import importlib
import os
import sys
import tempfile
import types
import unittest

from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# Without the other commands, which need the services
cli = types.ModuleType("cli")
cli.__path__ = [os.path.join(ROOT, "cli")]
cli.Cli = mock.Mock(**{"command.return_value": lambda function: function})
cli.InvalidUseError = Exception
with mock.patch.dict(sys.modules, {"cli": cli}):
    fs = importlib.import_module("cli.fs")


class Clean(unittest.TestCase):
    def setUp(self):
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        self.root = tempdir.name

    def mkdirs(self, *paths):
        for path in paths:
            os.makedirs(os.path.join(self.root, path))

    def clean(self, prefix, used, levels, servers=()):
        """Clean up below `prefix` and return the leaf directories that are left."""
        fs._clean(mock.Mock(), os.path.join(self.root, prefix), {os.path.join(self.root, path) for path in used},
                  servers, levels)
        return sorted(os.path.relpath(path, self.root) for path, dirs, files in os.walk(self.root) if not dirs)

    def test_levels(self):
        options = {"domainStorageLevels": 1, "userStorageLevels": 2}
        self.assertEqual((fs._levels(options, "domain"), fs._levels(options, "user")), (1, 2))
        options["serverExplicitMount"] = True
        self.assertEqual((fs._levels(options, "domain"), fs._levels(options, "user")), (2, 3))

    def test_ancestors(self):
        self.mkdirs("user/mail.example.com/example.com/a", "user/mail.example.com/example.com/b",
                    "user/mail.example.com/example.org/c")
        used = ("user/mail.example.com/example.com/a",)
        self.assertEqual(self.clean("user", used, 2),
                         ["user/mail.example.com/example.com/a", "user/mail.example.com/example.com/b"])
        self.assertEqual(self.clean("user", used, 3), ["user/mail.example.com/example.com/a"])

    def test_nested(self):
        self.mkdirs("data/example.com/exmdb", "data/example.com/a", "data/example.com/b", "data/example.org/c")
        used = ("data/example.com", "data/example.com/a")
        left = ["data/example.com/a", "data/example.com/b", "data/example.com/exmdb"]
        self.assertEqual(self.clean("data", used, 2), left)
        self.mkdirs("data/example.net/exmdb")
        self.assertEqual(self.clean("data", used, 1), left)
        self.assertEqual(self.clean("data", used, 3), left)

    def test_servers(self):
        self.mkdirs("domain/a.example.com/example.com", "domain/b.example.com", "domain/c.example.com")
        self.assertEqual(self.clean("domain", ("domain/a.example.com/example.com",), 2, ("a.example.com", "b.example.com")),
                         ["domain/a.example.com/example.com", "domain/b.example.com"])

    def test_lost_found(self):
        self.mkdirs("domain/lost+found", "domain/example.com", "user/mail.example.com/lost+found/#1",
                    "user/mail.example.com/example.com")
        self.assertEqual(self.clean("domain", (), 1), ["domain/lost+found", "user/mail.example.com/example.com",
                                                       "user/mail.example.com/lost+found/#1"])
        self.assertEqual(self.clean("user", (), 3, ("mail.example.com",)),
                         ["domain/lost+found", "user/mail.example.com/lost+found/#1"])

    def test_trailing_slash(self):
        self.mkdirs("domain/example.com/exmdb", "domain/example.org/exmdb")
        self.assertEqual(self.clean("domain/", ("domain/example.com/",), 1), ["domain/example.com/exmdb"])


if __name__ == "__main__":
    unittest.main()
