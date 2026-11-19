# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 grommunio GmbH

"""Tests for Permissions.covers(), no database required.

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


class _Query:
    """Stand-in for Domains.query, as used by OrgAdminPermission."""
    count = 0

    def __init__(self, orgID=None):
        self.orgID = orgID

    def filter(self, orgID):
        return _Query(orgID)

    def with_entities(self, *args):
        return self

    def all(self):
        _Query.count += 1
        return [types.SimpleNamespace(ID=ID) for ID in ORG_DOMAINS.get(self.orgID, ())]


class _OrgID:
    def __eq__(self, orgID):
        return orgID


class _Domains:
    ID = None
    orgID = _OrgID()
    query = _Query()


SA, SARO = SystemAdminPermission, SystemAdminROPermission
DA, DARO, OA = DomainAdminPermission, DomainAdminROPermission, OrgAdminPermission
RP, DP = ResetPasswdPermission, DomainPurgePermission

SYSTEM = ((SA(),), (SARO(),), (DA("*"),), (DARO("*"),), (OA("*"),), (DA(5), SA()), (DA(5), DA("*")))


class PermissionsCovers(unittest.TestCase):
    def setUp(self):
        orm = types.ModuleType("orm")
        orm.domains = types.ModuleType("orm.domains")
        orm.domains.Domains = _Domains
        patcher = mock.patch.dict(sys.modules, {"orm": orm, "orm.domains": orm.domains})
        patcher.start()
        self.addCleanup(patcher.stop)
        _Query.count = 0

    def assertCovers(self, holder, covered=(), uncovered=()):
        holder = Permissions(*holder)
        for expected, targets in ((True, covered), (False, uncovered)):
            for target in targets:
                with self.subTest(holder=holder.permissions, target=target):
                    self.assertIs(holder.covers(Permissions(*target)), expected)

    def test_no_roles(self):
        for holder in ((), (DA(5),), (OA(1),), (RP(),), (SA(),)):
            self.assertCovers(holder, covered=((),))
        self.assertEqual(_Query.count, 0)

    def test_system_admin(self):
        self.assertCovers((SA(),), covered=SYSTEM+((DA(5),), (OA(1), DP()), (RP(),)))
        self.assertCovers((DA(5), SA()), covered=SYSTEM)
        self.assertTrue(Permissions.sysadmin().covers(Permissions.sysadmin()))
        self.assertEqual(_Query.count, 0)

    def test_system_wide_targets(self):
        for holder in ((DA(5),), (DA("*"),), (OA(1),), (OA("*"),), (SARO(),), (RP(),), (DA("*"), OA("*"), SARO(), RP(), DP())):
            self.assertCovers(holder, uncovered=SYSTEM)

    def test_domain_admin(self):
        self.assertCovers((DA(5),),
                          covered=((DA(5),), (DARO(5),), (DA(5), DARO(5))),
                          uncovered=((DA(6),), (DARO(6),), (DA(5), DA(6)), (OA(1),), (DP(),), (DA(5), DP())))
        self.assertCovers((DA(5), DA(6)), covered=((DA(6), DA(5)),), uncovered=((DA(5), DA(7)),))
        self.assertCovers((DA("*"),), covered=((DA(5),), (DARO(7),), (DA(5), DA(6))), uncovered=((OA(1),),))
        self.assertCovers((DARO(5),), covered=((DARO(5),),), uncovered=((DA(5),),))

    def test_org_admin(self):
        self.assertCovers((OA(1),),
                          covered=((DA(4),), (DA(5),), (DARO(5),), (OA(1),), (DA(4), DA(5), OA(1))),
                          uncovered=((DA(6),), (DARO(6),), (OA(2),), (DA(5), DA(6)), (DP(),), (OA(1), DP())))
        self.assertCovers((OA("*"),), covered=((DA(5),), (DA(6),), (OA(1),), (OA(2),)), uncovered=((DP(),),))
        self.assertCovers((OA(1), DP()), covered=((DA(5), DP()),))

    def test_reset_passwd(self):
        self.assertCovers((RP(),), covered=((RP(),),), uncovered=((DA(5),), (DARO(5),), (OA(1),), (DP(),), (RP(), DA(5))))
        self.assertCovers((DA(5), RP()), covered=((RP(), DA(5)),))
        # Follows whether domain and organization admins hold ResetPasswd
        for holder in (DA(5), OA(1)):
            self.assertIs(Permissions(holder).covers(Permissions(RP())), RP() in Permissions(holder))


if __name__ == "__main__":
    unittest.main()
