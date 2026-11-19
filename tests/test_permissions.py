# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 grommunio GmbH

"""Permission matrix tests, no database required.

Run from the source root: python3 -m unittest discover tests
"""

import os
import sys
import types
import unittest

from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.permissions import Permissions, SystemAdminPermission, SystemAdminROPermission, DomainAdminPermission, \
    DomainAdminROPermission, OrgAdminPermission, ResetPasswdPermission, DomainPurgePermission

ORG_DOMAINS = {1: (4, 5), 2: (6,)}


class _OrgID:
    def __eq__(self, orgID):
        return (orgID,)

    def in_(self, orgIDs):
        return tuple(orgIDs)


class _Query:
    def __init__(self, orgIDs=()):
        self.orgIDs = orgIDs

    def filter(self, orgIDs):
        return _Query(orgIDs)

    def with_entities(self, *args):
        return self

    def all(self):
        return [types.SimpleNamespace(ID=ID) for orgID in self.orgIDs for ID in ORG_DOMAINS.get(orgID, ())]


class _Domains:
    """Stand-in for orm.domains.Domains, as used by OrgAdminPermission."""
    ID = None
    orgID = _OrgID()
    query = _Query()


HOLDERS = {
    "SystemAdmin": SystemAdminPermission(),
    "SystemAdminRO": SystemAdminROPermission(),
    "DomainAdmin(5)": DomainAdminPermission(5),
    "DomainAdmin(*)": DomainAdminPermission("*"),
    "DomainAdminRO(5)": DomainAdminROPermission(5),
    "OrgAdmin(1)": OrgAdminPermission(1),
    "OrgAdmin(*)": OrgAdminPermission("*"),
    "ResetPasswd": ResetPasswdPermission(),
    "DomainPurge": DomainPurgePermission(),
}


class PermissionMatrix(unittest.TestCase):
    def setUp(self):
        orm = types.ModuleType("orm")
        orm.domains = types.ModuleType("orm.domains")
        orm.domains.Domains = _Domains
        patcher = mock.patch.dict(sys.modules, {"orm": orm, "orm.domains": orm.domains})
        patcher.start()
        self.addCleanup(patcher.stop)

    def assertHolders(self, requested, expected):
        """Check that exactly the `expected` holders have the `requested` permission."""
        for name, permission in HOLDERS.items():
            with self.subTest(holder=name, requested=requested):
                self.assertEqual(requested in Permissions(permission), name in expected)

    def test_reset_passwd(self):
        self.assertHolders(ResetPasswdPermission(), {"SystemAdmin", "ResetPasswd"})

    def test_reset_passwd_combined(self):
        permissions = Permissions(DomainAdminPermission(5), OrgAdminPermission(1), DomainPurgePermission())
        self.assertNotIn(ResetPasswdPermission(), permissions)
        self.assertIn(ResetPasswdPermission(), Permissions(DomainAdminPermission(5), ResetPasswdPermission()))

    def test_reset_passwd_domains(self):
        def domains(*permissions):
            return Permissions(*permissions).resetPasswdDomains()

        for name in ("SystemAdmin", "ResetPasswd", "DomainAdmin(*)", "OrgAdmin(*)"):
            with self.subTest(holder=name):
                self.assertIsNone(domains(HOLDERS[name]))
                self.assertIsNone(domains(DomainAdminPermission(5), HOLDERS[name], OrgAdminPermission(1)))
        for name in ("SystemAdminRO", "DomainAdminRO(5)", "DomainPurge"):
            with self.subTest(holder=name):
                self.assertEqual(domains(HOLDERS[name]), set())
                self.assertEqual(domains(HOLDERS[name], DomainAdminPermission(7)), {7})
        self.assertEqual(domains(), set())
        self.assertEqual(domains(DomainAdminPermission(5)), {5})
        self.assertEqual(domains(DomainAdminPermission(5), DomainAdminPermission(7)), {5, 7})
        self.assertEqual(domains(OrgAdminPermission(1)), {4, 5})
        self.assertEqual(domains(OrgAdminPermission(2)), {6})
        self.assertEqual(domains(OrgAdminPermission(3)), set())  # No domains
        self.assertEqual(domains(OrgAdminPermission(1), OrgAdminPermission(2), DomainAdminPermission(7)), {4, 5, 6, 7})

    def test_any_domain_write(self):
        self.assertHolders(DomainAdminPermission("*"),
                           {"SystemAdmin", "DomainAdmin(5)", "DomainAdmin(*)", "OrgAdmin(1)", "OrgAdmin(*)"})

    def test_domain_write(self):
        self.assertHolders(DomainAdminPermission(5),
                           {"SystemAdmin", "DomainAdmin(5)", "DomainAdmin(*)", "OrgAdmin(1)", "OrgAdmin(*)"})
        self.assertHolders(DomainAdminPermission(6), {"SystemAdmin", "DomainAdmin(*)", "OrgAdmin(*)"})

    def test_domain_read(self):
        self.assertHolders(DomainAdminROPermission(5), {"SystemAdmin", "SystemAdminRO", "DomainAdmin(5)", "DomainAdmin(*)",
                                                        "DomainAdminRO(5)", "OrgAdmin(1)", "OrgAdmin(*)"})
        self.assertHolders(DomainAdminROPermission(6), {"SystemAdmin", "SystemAdminRO", "DomainAdmin(*)", "OrgAdmin(*)"})

    def test_org_admin(self):
        self.assertHolders(OrgAdminPermission(1), {"SystemAdmin", "OrgAdmin(1)", "OrgAdmin(*)"})
        self.assertHolders(OrgAdminPermission(2), {"SystemAdmin", "OrgAdmin(*)"})

    def test_system_admin(self):
        self.assertHolders(SystemAdminPermission(), {"SystemAdmin"})

    def test_capabilities(self):
        self.assertEqual(DomainAdminPermission(5).capabilities(), {"DomainAdminRead", "DomainAdminWrite"})
        self.assertEqual(OrgAdminPermission(1).capabilities(), {"DomainAdminRead", "DomainAdminWrite", "OrgAdmin"})
        self.assertEqual(ResetPasswdPermission().capabilities(), {"ResetPasswd"})
        self.assertIn("ResetPasswd", SystemAdminPermission().capabilities())

    def test_from_db(self):
        roles = [types.SimpleNamespace(permission="DomainAdmin", params=5),
                 types.SimpleNamespace(permission="OrgAdmin", params=2)]
        permissions = Permissions.fromDB(roles)
        self.assertNotIn(ResetPasswdPermission(), permissions)
        self.assertIn(DomainAdminPermission(6), permissions)
        self.assertNotIn(DomainAdminPermission(4), permissions)
        self.assertNotIn("ResetPasswd", permissions.capabilities())
        roles.append(types.SimpleNamespace(permission="ResetPasswd", params=None))
        self.assertIn(ResetPasswdPermission(), Permissions.fromDB(roles))


if __name__ == "__main__":
    unittest.main()
