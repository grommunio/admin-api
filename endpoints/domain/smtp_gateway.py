# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 grommunio GmbH
#
# REST endpoints for per-domain SMTP gateway configuration.
#
# Routes:
#   GET    /api/v1/domains/<int:domainID>/smtpGateway
#   PUT    /api/v1/domains/<int:domainID>/smtpGateway
#   DELETE /api/v1/domains/<int:domainID>/smtpGateway
#
# GET    – Return the current gateway config (password is censored).
# PUT    – Create or update the gateway config for the given domain.
#          Body: JSON with fields host, port, encryption, username,
#                password, enabled, description.
# DELETE – Remove the gateway config for the given domain (falls back
#          to the global /etc/gromox/gromox.cfg outgoing_smtp_url).
#
# All routes require the DomainAdmin permission on the domain (write) or
# DomainAdminRO (read-only).

import api
from api.core import API, secure
from api.security import checkPermissions

from flask import request, jsonify
from tools.permissions import DomainAdminROPermission, DomainAdminPermission

from orm.domains import Domains
from orm.domain_smtp_gateway import DomainSmtpGateway


def _mask_password(gw):
    """Return a dict representation with the password field masked."""
    if gw is None:
        return None
    data = gw.todict(1)
    if data.get("password"):
        data["password"] = ""
        data["passwordSet"] = True
    else:
        data["passwordSet"] = False
    return data


@API.route(api.BaseRoute + "/domains/<int:domainID>/smtpGateway", methods=["GET"])
@secure(requireDB=True)
def getDomainSmtpGateway(domainID):
    domain = Domains.query.filter(Domains.ID == domainID).first()
    if domain is None:
        return jsonify(message="Domain not found"), 404
    checkPermissions(DomainAdminROPermission(domainID))

    gw = DomainSmtpGateway.query.filter(
        DomainSmtpGateway.domainID == domainID
    ).first()
    if gw is None:
        return jsonify(message="No SMTP gateway configured for this domain"), 404
    return jsonify(data=_mask_password(gw))


@API.route(api.BaseRoute + "/domains/<int:domainID>/smtpGateway", methods=["PUT"])
@secure(requireDB=True)
def setDomainSmtpGateway(domainID):
    domain = Domains.query.filter(Domains.ID == domainID).first()
    if domain is None:
        return jsonify(message="Domain not found"), 404
    checkPermissions(DomainAdminPermission(domainID))

    data = request.get_json(silent=True) or {}
    error = DomainSmtpGateway.checkCreateParams(data)
    if error is not None:
        return jsonify(message=error), 400

    gw = DomainSmtpGateway.query.filter(
        DomainSmtpGateway.domainID == domainID
    ).first()
    # The frontend sends a derived `passwordSet` flag that the ORM does
    # not know about; drop it before constructing the model so we don't
    # trip DataModel's strict fromdict validation.
    data = {k: v for k, v in data.items() if k != "passwordSet"}
    if gw is None:
        data_with_id = {"domainID": domainID}
        data_with_id.update({k: v for k, v in data.items() if v is not None})
        try:
            gw = DomainSmtpGateway(data_with_id)
        except (ValueError, TypeError) as err:
            return jsonify(message=str(err)), 400
    else:
        if not data.get("password"):
            # Keep the existing password if the form submits an empty
            # field (common UX for password fields).
            data.pop("password", None)
        gw.fromdict(data)

    from orm import DB
    try:
        if gw not in DB.session:
            DB.session.add(gw)
        DB.session.commit()
    except Exception as err:
        DB.session.rollback()
        return jsonify(message="Database error: {}".format(err)), 500

    err = DomainSmtpGateway.reload_gromox()
    if err is not None:
        # The DB write succeeded, but the daemon reload failed.
        # The configuration is durable in the database, so we
        # still return success but with a warning.
        return jsonify(message="Saved, but: {}".format(err),
                       data=_mask_password(gw),
                       warning=True)
    return jsonify(message="Success!", data=_mask_password(gw))


@API.route(api.BaseRoute + "/domains/<int:domainID>/smtpGateway", methods=["DELETE"])
@secure(requireDB=True)
def deleteDomainSmtpGateway(domainID):
    domain = Domains.query.filter(Domains.ID == domainID).first()
    if domain is None:
        return jsonify(message="Domain not found"), 404
    checkPermissions(DomainAdminPermission(domainID))

    gw = DomainSmtpGateway.query.filter(
        DomainSmtpGateway.domainID == domainID
    ).first()
    if gw is None:
        return jsonify(message="No SMTP gateway configured for this domain"), 404
    from orm import DB
    DB.session.delete(gw)
    DB.session.commit()
    err = DomainSmtpGateway.reload_gromox()
    if err is not None:
        return jsonify(message="Deleted, but: {}".format(err), warning=True)
    return jsonify(message="Success!")
