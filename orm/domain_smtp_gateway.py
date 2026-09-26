# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 grommunio GmbH
#
# DomainSmtpGateway – per-domain outbound SMTP relay configuration.
#
# Allows each grommunio domain to specify its own smart-host / SMTP
# gateway (with optional authentication) for outbound mail delivery.
# The MTA (Postfix) evaluates the table with sender-dependent lookups;
# see doc/mta-smart-hosts.rst in gromox for the wiring.
#
# Mirror of the `domain_smtp_gateway` table that gromox's dbop module
# creates (schema version 134, see lib/dbop_mysql.cpp in gromox).
# Any change to the schema here must be reflected there and vice versa.

from . import DB
from tools.DataModel import DataModel, Id, Text, Int, Bool

from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.mysql import INTEGER, TINYINT, VARCHAR


class DomainSmtpGateway(DataModel, DB.Base):
    """Per-domain outbound SMTP gateway / smart-host configuration.

    The MTA evaluates this table live (sender-dependent lookups), so
    changes take effect immediately -- no service restarts needed.
    """

    __tablename__ = "domain_smtp_gateway"

    domainID = Column(
        "domain_id",
        INTEGER(10, unsigned=True),
        ForeignKey("domains.id", ondelete="cascade", onupdate="cascade"),
        primary_key=True,
        nullable=False,
    )
    host = Column("host", VARCHAR(255), nullable=False)
    port = Column("port", INTEGER(11), nullable=False, server_default="25")
    encryption = Column(
        "encryption", VARCHAR(32), nullable=False, server_default="none"
    )
    username = Column("username", VARCHAR(255), nullable=True)
    password = Column("password", VARCHAR(255), nullable=True)
    enabled = Column("enabled", TINYINT(1), nullable=False, server_default="1")
    description = Column("description", VARCHAR(255), nullable=True)

    _dictmapping_ = (
        (Id("domainID", flags="init"),),
        (
            Text("host", flags="patch"),
            Int("port", flags="patch"),
            Text("encryption", flags="patch"),
            Text("username", flags="patch"),
            Text("password", flags="patch"),
            Bool("enabled", flags="patch"),
            Text("description", flags="patch"),
        ),
    )

    VALID_ENCRYPTION = ("none", "starttls", "starttls_unverified", "tls")

    @staticmethod
    def checkCreateParams(data):
        """Validate input. Returns None on success or an error string."""
        if not data.get("host"):
            return "Missing required property 'host'"
        enc = data.get("encryption", "none")
        if enc not in DomainSmtpGateway.VALID_ENCRYPTION:
            return "'{}' is not a valid encryption mode (allowed: {})".format(
                enc, ", ".join(DomainSmtpGateway.VALID_ENCRYPTION)
            )
        port = data.get("port", 25)
        try:
            port = int(port)
            if not (1 <= port <= 65535):
                raise ValueError
        except (TypeError, ValueError):
            return "Port must be an integer between 1 and 65535"
        return None
