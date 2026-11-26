# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 grommunio GmbH

"""Tests for the login while LDAP is not available, no database or services required.

Run from the source root: python3 -m unittest discover tests
"""

import importlib
import os
import sys
import tempfile
import types
import unittest

from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REASON = "Service 'ldap@Example Corp' is currently not available"
MESSAGE = {"message": "Authentication service not available"}


class ServiceUnavailableError(Exception):
    pass


class _Service:
    """Stand-in for services.Service, handing out an LDAP service that is not available."""

    def __init__(self, name, *args):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def authUser(self, ID, password):
        raise ServiceUnavailableError(REASON)

    def changePassword(self, ID, oldPassword, newPassword, check=None):
        raise ServiceUnavailableError(REASON)


class Unauthenticated(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.config import Config
        services = types.ModuleType("services")
        services.Service = _Service
        services.ServiceUnavailableError = ServiceUnavailableError
        services.ServiceDisabledError = type("ServiceDisabledError", (Exception,), {})
        services.ldap = types.ModuleType("services.ldap")
        services.ldap.InsecureConnectionError = type("InsecureConnectionError", (Exception,), {})
        orm = types.ModuleType("orm")
        orm.DB = None
        orm.users = types.ModuleType("orm.users")
        orm.users.Users, orm.users.Altnames = mock.MagicMock(), mock.MagicMock()
        orm.users.Users.query.join.return_value.filter.return_value.first.return_value = \
            types.SimpleNamespace(username="user@example.com", externID=b"ID", orgID=1)
        cls.tempdir = tempfile.TemporaryDirectory()
        keys = {"jwtPrivateKeyFile": os.path.join(cls.tempdir.name, "private.pem"),
                "jwtPublicKeyFile": os.path.join(cls.tempdir.name, "public.pem")}
        for path in keys.values():  # Keys are generated and saved if the files are missing
            open(path, "wb").close()
        cls.config = mock.patch.dict(Config["security"], keys)
        cls.config.start()
        cls.loaded = set(sys.modules)
        sys.modules.update({"services": services, "services.ldap": services.ldap, "orm": orm, "orm.users": orm.users})
        cls.API = importlib.import_module("endpoints.misc").API

    @classmethod
    def tearDownClass(cls):
        # What was imported refers to the stand-ins
        for name in set(sys.modules)-cls.loaded:
            if name.split(".")[0] in ("api", "endpoints", "orm", "services", "tools"):
                del sys.modules[name]
        cls.config.stop()
        cls.tempdir.cleanup()

    def test_login(self):
        with self.assertLogs("security", "WARNING") as logs, self.assertLogs(self.API.logger, "WARNING"):
            response = self.API.test_client().post("/api/v1/login", data={"user": "user@example.com", "pass": "secret"})
        self.assertEqual((response.status_code, response.get_json()), (503, MESSAGE))
        self.assertIn(REASON, logs.output[0])

    def test_passwd(self):
        with self.assertLogs(self.API.logger, "WARNING") as logs:
            response = self.API.test_client().put("/api/v1/passwd", json={"user": "user@example.com", "old": "secret",
                                                                          "new": "new"})
        self.assertEqual((response.status_code, response.get_json()), (503, MESSAGE))
        self.assertIn(REASON, logs.output[0])

    def test_passwd_ldap_password_change(self):
        from tools.config import Config
        with mock.patch.dict(Config["options"], {"ldapPasswordChange": True}), \
                self.assertLogs(self.API.logger, "WARNING") as logs:
            response = self.API.test_client().put("/api/v1/passwd", json={"user": "user@example.com", "old": "secret",
                                                                          "new": "new"})
        self.assertEqual((response.status_code, response.get_json()), (503, MESSAGE))
        self.assertIn(REASON, logs.output[0])


if __name__ == "__main__":
    unittest.main()
