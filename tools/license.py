# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grommunio GmbH

from cryptography import x509
from cryptography.hazmat.backends import default_backend

from datetime import datetime, MAXYEAR

from .config import Config
from .misc import GenericObject, createMapping

import logging
logger = logging.getLogger("license")


class CertificateError(Exception):
    pass


class GrommunioLicense(GenericObject):
    @staticmethod
    def validate(cert):
        if cert is not None and not cert.not_valid_before <= datetime.now() <= cert.not_valid_after:
            raise CertificateError("Certificate expired")

    @property
    def error(self):
        try:
            self.validate(self.cert)
        except CertificateError as err:
            return err.args[0]


def _defaultLicense():
    return GrommunioLicense(cert=None,
                            file=None,
                            users=5,
                            product="Community",
                            notBefore=datetime(1000, 1, 1),
                            notAfter=datetime(MAXYEAR, 12, 31, 23, 59, 59))


def _processCertificate(data):
    try:
        cert = x509.load_pem_x509_certificate(data, default_backend())
        GrommunioLicense.validate(cert)
        exts = createMapping(cert.extensions, lambda x: x.oid.dotted_string, lambda x: x.value.value)
        lic = GrommunioLicense(cert=cert, file=data)
        lic.users = int(exts.get("1.3.6.1.4.1.56504.1.1"))
        lic.product = exts.get("1.3.6.1.4.1.56504.1.2").decode("utf-8") if "1.3.6.1.4.1.56504.1.2" in exts else None
        lic.notBefore = cert.not_valid_before
        lic.notAfter = cert.not_valid_after
        return True, lic
    except ValueError:
        return False, "Bad certificate"
    except CertificateError as err:
        return False, err.args[0]
    except BaseException as err:
        logger.error(str(err))
        return False, "Unknown error"


def loadCertificate():
    try:
        with open(Config["options"]["licenseFile"], "rb") as file:
            data = file.read()
        success, val = _processCertificate(data)
        if not success:
            logger.error("Failed to load license: "+val)
        else:
            return val
    except KeyError:
        logger.warn("Could not load license: location not configured")
    except FileNotFoundError as err:
        logger.warn("Could not load license: "+err.args[1])


_license = loadCertificate() or _defaultLicense()


def updateCertificate(data):
    success, val = _processCertificate(data)
    if not success:
        return val
    try:
        with open(Config["options"]["licenseFile"], "wb") as file:
            file.write(data)
        global _license
        _license = val
    except KeyError:
        return "Could not load license: location not configured"
    except FileNotFoundError as err:
        return "Could not load license: "
    except PermissionError as err:
        return err.args[1]


def getLicense():
    global _license
    if _license.error:
        _license = _defaultLicense()
    return _license
