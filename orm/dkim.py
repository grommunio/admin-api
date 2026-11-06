# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Alexander Gott

from . import DB

from sqlalchemy import Column, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.mysql import INTEGER, TEXT, TIMESTAMP, VARCHAR


class DkimKeys(DB.Base):
    """Private DKIM keys, one row per (domain, selector).

    The central database is the source of truth in multi-server setups; each
    node replicates rows into its local Redis keystore for rspamd (cf.
    tools.dnsHealth.syncDkimKeysToRedis). Table layout is owned by gromox
    (schema GX-135, lib/dbop_mysql.cpp).
    """
    __tablename__ = "dkim_keys"

    ID = Column("id", INTEGER(10, unsigned=True), primary_key=True)
    domainID = Column("domain_id", INTEGER(10, unsigned=True),
                      ForeignKey("domains.id", ondelete="CASCADE", onupdate="CASCADE"),
                      nullable=False, index=True)
    selector = Column("selector", VARCHAR(63), nullable=False)
    privateKey = Column("private_key", TEXT, nullable=False)
    created = Column("created", TIMESTAMP, server_default="now()")
    updated = Column("updated", TIMESTAMP, server_default="now()")

    __table_args__ = (UniqueConstraint("domain_id", "selector", name="domain_selector"),)

    @classmethod
    def upsert(cls, domainID, selector, privateKey):
        """Store a private key, replacing the entry for (domain, selector).

        Returns
        -------
        DkimKeys
            The stored entry.
        """
        entry = cls.query.filter(cls.domainID == domainID, cls.selector == selector).first()
        if entry is None:
            entry = cls(domainID=domainID, selector=selector)
            DB.session.add(entry)
        entry.privateKey = privateKey
        DB.session.commit()
        return entry
