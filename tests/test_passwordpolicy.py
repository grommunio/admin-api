# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 grommunio GmbH

"""Tests for tools.passwordpolicy, no database required.

Run from the source root: python3 -m unittest discover tests
"""

import os
import sys
import tempfile
import unittest

from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import passwordpolicy
from tools.passwordpolicy import checkPassword, PolicyUnavailableError


class PasswordPolicyTest(unittest.TestCase):
    def setPolicy(self, **policy):
        patcher = mock.patch.object(passwordpolicy, "Config", {"options": {"passwordPolicy": policy}})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_defaults_accept_all(self):
        patcher = mock.patch.object(passwordpolicy, "Config", {"options": {}})
        patcher.start()
        self.addCleanup(patcher.stop)
        for password in ("", "a", "user@example.com", "user"):
            with self.subTest(password=password):
                self.assertIsNone(checkPassword(password, "user@example.com"))

    def test_min_length(self):
        self.setPolicy(minLength=5)
        self.assertIsNotNone(checkPassword("abcd"))
        self.assertIsNone(checkPassword("abcde"))

    def test_min_char_classes(self):
        self.setPolicy(minCharClasses=3)
        for password, accepted in (("abcdef", False), ("abcDEF", False), ("abcDE1", True), ("ab-12", True),
                                   ("aB1-", True)):
            with self.subTest(password=password):
                self.assertEqual(checkPassword(password) is None, accepted)

    def test_username_off_by_default(self):
        self.setPolicy()
        self.assertIsNone(checkPassword("User@Example.com", "user@example.com"))

    def test_forbid_username(self):
        self.setPolicy(forbidUsername=True)
        for password in ("user@example.com", "USER@example.com", "user", "User"):
            with self.subTest(password=password):
                self.assertIsNotNone(checkPassword(password, "user@example.com"))
        self.assertIsNone(checkPassword("user1", "user@example.com"))

    def test_blocklist(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as file:
            file.write("# comment\n\n  Summer2026  \nletmein\n")
        self.addCleanup(os.unlink, file.name)
        self.setPolicy(blocklist=file.name)
        for password, accepted in (("summer2026", False), (" SUMMER2026 ", False), ("letmein", False),
                                   ("letmein!", True), ("summer", True), ("# comment", True), ("", True)):
            with self.subTest(password=password):
                self.assertEqual(checkPassword(password) is None, accepted)

    def test_blocklist_unreadable(self):
        with tempfile.TemporaryDirectory() as directory:
            self.setPolicy(blocklist=os.path.join(directory, "missing.txt"))
            with self.assertLogs("passwordpolicy", "ERROR"), self.assertRaises(PolicyUnavailableError):
                checkPassword("anything")


if __name__ == "__main__":
    unittest.main()
