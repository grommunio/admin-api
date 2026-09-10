# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 grommunio GmbH
#
# DomainSmtpGateway – per-domain outbound SMTP relay configuration.
#
# Allows each grommunio domain to specify its own smart-host / SMTP
# gateway (with optional authentication) for outbound mail delivery.
# gromox reads from the same MySQL table at SMTP delivery time and
# routes outgoing messages per sender's local domain.
#
# Mirror of the `domain_smtp_gateway` table that gromox's dbop module
# creates (schema version 134, see lib/dbop_mysql.cpp in gromox).
# Any change to the schema here must be reflected there and vice versa.

from . import DB
from tools.DataModel import DataModel, Id, Text, Int, BoolP, Bool
from tools.DataModel import InvalidAttributeError, MissingRequiredAttributeError
from services import Service

from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.mysql import INTEGER, TINYINT, VARCHAR
from sqlalchemy.exc import IntegrityError


class DomainSmtpGateway(DataModel, DB.Base):
    """Per-domain outbound SMTP gateway / smart-host configuration.

    gromox reads from the `domain_smtp_gateway` MySQL table at SMTP
    delivery time via the `resolve_smtp_url_for_sender` service
    (registered by libgxs_mysql_adaptor). The admin-api only has to
    keep the table in sync and signal gromox to reload after a
    change. There is no on-disk file in the new design.
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
    fromAddress = Column("from_address", VARCHAR(255), nullable=True)
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
            Text("fromAddress", flags="patch"),
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

    @classmethod
    def reload_gromox(cls):
        """Signal gromox to reload its in-memory cache.

        gromox's `libgxs_mysql_adaptor` re-queries the
        `domain_smtp_gateway` table on every SMTP message (the
        table is small, one row per hosted domain), so a hard
        reload is not strictly required. We still poke
        gromox-delivery so administrators see immediate effect
        after editing the config.

        Returns an error string or None on success.
        """
        try:
            with Service("systemd", errors=Service.SUPPRESS_ALL) as sysd:
                sysd.tryReloadRestartService(
                    "gromox-delivery.service",
                    "gromox-delivery-queue.service",
                )
        except Exception as err:
            return "Could not reload gromox services: {}".format(err)
        return None
