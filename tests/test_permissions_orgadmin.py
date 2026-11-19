# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 grommunio GmbH

"""Tests for the scope of the organization admin permission, no database required.

Run from the source root: python3 -m unittest discover tests
"""

import os
import sys
import types
import unittest

from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.permissions import Permissions, SystemAdminPermission, SystemAdminROPermission, DomainAdminPermission, \
    DomainAdminROPermission, OrgAdminPermission, DomainPurgePermission

ORG_DOMAINS = {1: (4, 5), 2: (6,)}


class _OrgID:
    def __eq__(self, orgID):
        return orgID


class _Query:
    def __init__(self, orgID=None):
        self.orgID = orgID

    def filter(self, orgID):
        return _Query(orgID)

    def with_entities(self, *args):
        return self

    def all(self):
        return [types.SimpleNamespace(ID=ID) for ID in ORG_DOMAINS.get(self.orgID, ())]


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
    "DomainAdminRO(*)": DomainAdminROPermission("*"),
    "OrgAdmin(1)": OrgAdminPermission(1),
    "OrgAdmin(2)": OrgAdminPermission(2),
    "OrgAdmin(*)": OrgAdminPermission("*"),
    "DomainPurge": DomainPurgePermission(),
}


class OrgAdminScope(unittest.TestCase):
    def setUp(self):
        orm = types.ModuleType("orm")
        orm.domains = types.ModuleType("orm.domains")
        orm.domains.Domains = _Domains
        patcher = mock.patch.dict(sys.modules, {"orm": orm, "orm.domains": orm.domains})
        patcher.start()
        self.addCleanup(patcher.stop)

    def assertHolders(self, requested, expected):
        """Check that exactly the `expected` holders have the `requested` permission."""
        self.assertLessEqual(set(expected), set(HOLDERS))
        for name, permission in HOLDERS.items():
            with self.subTest(holder=name, requested=requested):
                self.assertEqual(requested in Permissions(permission), name in expected)

    def test_system_read(self):
        self.assertHolders(SystemAdminROPermission(), {"SystemAdmin", "SystemAdminRO"})

    def test_system_read_combined(self):
        permissions = Permissions(OrgAdminPermission(1), OrgAdminPermission("*"), DomainAdminPermission("*"),
                                  DomainAdminROPermission("*"), DomainPurgePermission())
        self.assertNotIn(SystemAdminROPermission(), permissions)
        self.assertNotIn(SystemAdminPermission(), permissions)
        self.assertIn(SystemAdminROPermission(), Permissions(OrgAdminPermission(1), SystemAdminROPermission()))

    def test_system_write(self):
        self.assertHolders(SystemAdminPermission(), {"SystemAdmin"})

    def test_org_admin(self):
        self.assertHolders(OrgAdminPermission(1), {"SystemAdmin", "OrgAdmin(1)", "OrgAdmin(*)"})
        self.assertHolders(OrgAdminPermission(2), {"SystemAdmin", "OrgAdmin(2)", "OrgAdmin(*)"})
        self.assertHolders(OrgAdminPermission(3), {"SystemAdmin", "OrgAdmin(*)"})
        self.assertHolders(OrgAdminPermission("*"), {"SystemAdmin", "OrgAdmin(1)", "OrgAdmin(2)", "OrgAdmin(*)"})

    def test_domain_write(self):
        self.assertHolders(DomainAdminPermission(5),
                           {"SystemAdmin", "DomainAdmin(5)", "DomainAdmin(*)", "OrgAdmin(1)", "OrgAdmin(*)"})
        self.assertHolders(DomainAdminPermission(6), {"SystemAdmin", "DomainAdmin(*)", "OrgAdmin(2)", "OrgAdmin(*)"})
        self.assertHolders(DomainAdminPermission(7), {"SystemAdmin", "DomainAdmin(*)", "OrgAdmin(*)"})
        self.assertHolders(DomainAdminPermission("*"), {"SystemAdmin", "DomainAdmin(5)", "DomainAdmin(*)", "OrgAdmin(1)",
                                                        "OrgAdmin(2)", "OrgAdmin(*)"})

    def test_domain_read(self):
        self.assertHolders(DomainAdminROPermission(5),
                           {"SystemAdmin", "SystemAdminRO", "DomainAdmin(5)", "DomainAdmin(*)", "DomainAdminRO(5)",
                            "DomainAdminRO(*)", "OrgAdmin(1)", "OrgAdmin(*)"})
        self.assertHolders(DomainAdminROPermission(6), {"SystemAdmin", "SystemAdminRO", "DomainAdmin(*)", "DomainAdminRO(*)",
                                                        "OrgAdmin(2)", "OrgAdmin(*)"})
        self.assertHolders(DomainAdminROPermission(7),
                           {"SystemAdmin", "SystemAdminRO", "DomainAdmin(*)", "DomainAdminRO(*)", "OrgAdmin(*)"})
        self.assertHolders(DomainAdminROPermission("*"), set(HOLDERS)-{"DomainPurge"})

    def test_capabilities(self):
        for name in ("OrgAdmin(1)", "OrgAdmin(*)"):
            with self.subTest(holder=name):
                capabilities = Permissions(HOLDERS[name]).capabilities()
                self.assertLessEqual({"DomainAdminRead", "DomainAdminWrite", "OrgAdmin"}, capabilities)
                self.assertNotIn("SystemAdminRead", capabilities)
                self.assertNotIn("SystemAdminWrite", capabilities)
        self.assertIn("SystemAdminRead", Permissions(SystemAdminROPermission()).capabilities())

    def test_from_db(self):
        roles = [types.SimpleNamespace(permission="OrgAdmin", params=1),
                 types.SimpleNamespace(permission="DomainAdmin", params=6)]
        permissions = Permissions.fromDB(roles)
        self.assertNotIn(SystemAdminROPermission(), permissions)
        self.assertIn(DomainAdminROPermission(4), permissions)
        self.assertIn(DomainAdminPermission(6), permissions)
        self.assertNotIn(DomainAdminROPermission(7), permissions)
        roles.append(types.SimpleNamespace(permission="SystemAdminRO", params=None))
        self.assertIn(SystemAdminROPermission(), Permissions.fromDB(roles))


if __name__ == "__main__":
    unittest.main()
