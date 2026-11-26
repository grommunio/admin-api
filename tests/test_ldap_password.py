# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 grommunio GmbH

"""Tests for the LDAP password change, no LDAP server required.

Run from the source root: python3 -m unittest discover tests
"""

import importlib.util
import os
import sys
import types
import unittest

from unittest import mock

try:
    import ldap3  # noqa: F401
except ImportError:
    raise unittest.SkipTest("ldap3 is not installed")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def loadLdapModule():
    """Load services/ldap.py without the other services (chat, exmdb, ...)."""
    services = types.ModuleType("services")
    services.__path__ = []
    for name in ("ServiceDisabledError", "ServiceUnavailableError", "InstanceDefault"):
        setattr(services, name, type(name, (Exception,), {}))
    services.ServiceHub = types.SimpleNamespace(register=lambda *args, **kwargs: lambda cls: cls)
    with mock.patch.dict(sys.modules, {"services": services}):
        spec = importlib.util.spec_from_file_location("services.ldap", os.path.join(ROOT, "services", "ldap.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


ldap = loadLdapModule()
DN = "uid=user,ou=people,dc=example,dc=com"


class FakeConnection:
    """Stand-in for ldap3.Connection."""
    instances = []

    def __init__(self, server, user=None, password=None, client_strategy=None):
        self.server = server if hasattr(server, "ssl") else server.servers[0]
        self.user, self.password, self.strategy = user, password, client_strategy
        self.tls_started = False
        self.opened = self.bound = self.unbound = False
        self.result = {"result": 0, "description": "success", "message": ""}
        self.extend = mock.MagicMock()
        FakeConnection.instances.append(self)

    def open(self):
        self.opened = True

    def start_tls(self):
        self.tls_started = True
        return True

    def bind(self):
        self.bound = True
        return True

    def unbind(self):
        self.unbound = True


class GetConnectionTest(unittest.TestCase):
    def setUp(self):
        FakeConnection.instances = []
        patcher = mock.patch.object(ldap.ldap3, "Connection", FakeConnection)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.verify = True
        patcher = mock.patch.object(ldap, "tlsSettings", lambda: (self.verify, None, None))
        patcher.start()
        self.addCleanup(patcher.stop)

    def connect(self, server, starttls=False):
        return ldap.LdapService._getConnection(server, DN, "secret", starttls, requireTLS=True)

    def test_refuses_without_verification(self):
        self.verify = False
        with self.assertRaises(ldap.InsecureConnectionError):
            self.connect("ldaps://ldap.example.com")
        self.assertEqual(FakeConnection.instances, [])

    def test_refuses_plain_ldap(self):
        for server in ("ldap://ldap.example.com", "ldaps://ldap1.example.com ldap://ldap2.example.com"):
            with self.subTest(server=server), self.assertRaises(ldap.InsecureConnectionError):
                self.connect(server)
        self.assertEqual(FakeConnection.instances, [])

    def test_accepts_ldaps_and_starttls(self):
        for server, starttls in (("ldaps://ldap.example.com", False), ("ldap://ldap.example.com", True),
                                 ("ldaps://ldap1.example.com ldaps://ldap2.example.com", False)):
            with self.subTest(server=server):
                conn = self.connect(server, starttls)
                self.assertTrue(conn.bound)
                self.assertEqual(conn.strategy, ldap.ldap3.SYNC)

    def test_failed_bind_closes_connection(self):
        patcher = mock.patch.object(FakeConnection, "bind", lambda conn: False)
        patcher.start()
        self.addCleanup(patcher.stop)
        with self.assertRaises(ldap.ldapexc.LDAPBindError):
            self.connect("ldaps://ldap.example.com")
        self.assertTrue(FakeConnection.instances[-1].unbound)

    def test_failed_starttls(self):
        patcher = mock.patch.object(FakeConnection, "start_tls", lambda conn: False)
        patcher.start()
        self.addCleanup(patcher.stop)
        with self.assertRaises(ldap.ldapexc.LDAPStartTLSError):
            self.connect("ldap://ldap.example.com", starttls=True)
        conn = FakeConnection.instances[-1]
        self.assertFalse(conn.bound)
        self.assertTrue(conn.unbound)

    def test_without_require_tls_unchanged(self):
        conn = ldap.LdapService._getConnection("ldap://ldap.example.com", DN, "secret")
        self.assertTrue(conn.bound)
        self.assertEqual(conn.strategy, ldap.ldap3.RESTARTABLE)


class ChangePasswordTest(unittest.TestCase):
    def setUp(self):
        self.service = object.__new__(ldap.LdapService)
        self.service._config = {"objectID": "entryUUID", "users": {"username": "mail", "templates": []},
                                "connection": {"server": "ldaps://ldap.example.com"}}
        self.service._matchFilters = lambda ID: "(entryUUID=x)"
        self.service._search = lambda *args, **kwargs: [types.SimpleNamespace(DN=DN)]
        self.conn = FakeConnection(ldap.ldap3.Server("ldaps://ldap.example.com"))
        patcher = mock.patch.object(ldap.LdapService, "_getConnection", return_value=self.conn)
        self.getConnection = patcher.start()
        self.addCleanup(patcher.stop)

    def test_rfc3062(self):
        self.assertIsNone(self.service.changePassword("x", "old", "new"))
        self.conn.extend.standard.modify_password.assert_called_once_with(DN, "old", "new")
        self.assertTrue(self.conn.unbound)
        self.assertEqual(self.getConnection.call_args.kwargs.get("requireTLS"), True)

    def test_active_directory(self):
        self.service._config["users"]["templates"] = ["ActiveDirectory"]
        self.assertIsNone(self.service.changePassword("x", "old", "new"))
        self.conn.extend.microsoft.modify_password.assert_called_once_with(DN, "new", "old")

    def test_empty_old_password(self):
        self.assertEqual(self.service.changePassword("x", "", "new")[0], 401)
        self.getConnection.assert_not_called()

    def test_wrong_old_password(self):
        self.getConnection.side_effect = ldap.ldapexc.LDAPBindError("invalid")
        self.assertEqual(self.service.changePassword("x", "bad", "new")[0], 401)

    def test_check_stops_before_change(self):
        error = self.service.changePassword("x", "old", "new", check=lambda: (403, "no"))
        self.assertEqual(error, (403, "no"))
        self.conn.extend.standard.modify_password.assert_not_called()
        self.assertTrue(self.conn.unbound)

    def test_unbind_on_exception(self):
        def check():
            raise RuntimeError("policy")
        with self.assertRaises(RuntimeError):
            self.service.changePassword("x", "old", "new", check=check)
        self.assertTrue(self.conn.unbound)

    def test_result_mapping(self):
        for code, status in ((19, 400), (53, 400), (50, 403), (80, 500)):
            with self.subTest(code=code):
                self.conn.result = {"result": code, "description": "x", "message": "m"}
                with self.assertLogs("ldap", "INFO"):
                    self.assertEqual(self.service.changePassword("x", "old", "new")[0], status)


if __name__ == "__main__":
    unittest.main()
