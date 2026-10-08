# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2023 grommunio GmbH

from dns import resolver, reversename
import logging
import re
import socket
import subprocess
from .config import Config
from services import Service

logger = logging.getLogger("dnsHealth")

_DKIM_PEM_RE = re.compile(r"-----BEGIN [A-Z ]+-----.*?-----END [A-Z ]+-----", re.DOTALL)


class ExternalResolver:
    resolver = None

    @classmethod
    def get(cls):
        if cls.resolver is None:
            try:
                cls.resolver = resolver.Resolver()
                cls.resolver.nameservers = Config["dns"]["externalResolvers"]
            except Exception:
                pass
        return cls.resolver


def getHostByName(domain):
    try:
        # If host can be resolved
        socket.getaddrinfo(domain, None)
        return True
    except Exception:
        pass
    # Host could not be resolved
    return False


def getLocalIp():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0)
    try:
        s.connect((Config["dns"]["dudIP"], 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    s.close()
    return IP


def fullDNSCheck(domain: str):
    if Config["dns"]["disabled"]:
        return None, "DNS check disabled by configuration"
        
    externalResolver = ExternalResolver.get()
    if externalResolver is None:
        return None, "DNS resolver initialization failed"

    localIp = getLocalIp()
    externalIp = checkMyIP()
    mxRecords = checkMX(domain)
    autodiscover = checkAutodiscover(domain)
    autodiscoverSRV = checkAutodiscoverSRV(domain)
    autoconfig = checkAutoconfig(domain)
    txt = checkTXT(domain)
    dkim = checkDKIM(domain)
    dmarc = checkDMARC(domain)
    srv = checkAllSRV(domain)
    caldavTXT = checkCaldavTxt(domain)
    carddavTXT = checkCarddavTxt(domain)
    return {
        "localIp": localIp,
        "externalIp": externalIp,
        "mxRecords": mxRecords,
        "autodiscover": autodiscover,
        "autodiscoverSRV": autodiscoverSRV,
        "autoconfig": autoconfig,
        "txt": txt,
        "dkim": dkim,
        "dmarc": dmarc,
        "caldavTXT": caldavTXT,
        "carddavTXT": carddavTXT,
        **srv
    }, None


def checkMyIP():
    res = None
    try:
        customResolver = resolver.Resolver()
        customResolver.nameservers = ["208.67.222.222", "208.67.220.220", "208.67.222.220"]
        dnsAnswer = customResolver.query("myip.opendns.com")
        res = ", ".join([str(a) for a in dnsAnswer])
    except Exception:
        pass
    return res


def ip(domain: str):
    res = None
    try:
        dnsAnswer = resolver.query(domain)
        res = ", ".join([str(a) for a in dnsAnswer])
    except Exception:
        pass
    return res


def checkMX(domain: str):
    res = {
        "internalDNS": None,
        "externalDNS": None,
        "reverseLookup": None,
        "mxDomain": None,
    }

    externalResolver = ExternalResolver.get()
    if externalResolver is None:
        return res
    
    try:
        mxRecords = sorted(resolver.query(domain, "MX"), key=lambda r: (r.preference, str(r.exchange)))
        mxDomain = mxRecords[0].exchange # Mail-domain of domain
        res["mxDomain"] = str(mxDomain)
        try:
            mxResolved = externalResolver.query(mxDomain, "A") # IP of mail-domain
            res["externalDNS"] = ", ".join([str(r) for r in mxResolved])

            # Reverse lookup
            addresses = [reversename.from_address(str(r)) for r in mxResolved]
            res["reverseLookup"] = str(resolver.query(addresses[0], "PTR")[0])
        except Exception:
            pass
        try:
            mxResolved = resolver.query(mxDomain, "A")
            res["internalDNS"] = ", ".join([str(r) for r in mxResolved])
        except Exception:
            pass
    except Exception:
        pass
    return res


def checkAutodiscover(domain: str):
    return defaultDNSQuery("autodiscover.", domain)


def checkAutoconfig(domain: str):
    return defaultDNSQuery("autoconfig.", domain)


def checkAllSRV(domain: str):
    res = {f"{subdomain}SRV": defaultDNSQuery(f"_{subdomain}._tcp.", domain, recordType="SRV")
           for subdomain in ["submission", "imap", "imaps", "pop3", "pop3s", "caldav", "caldavs", "carddav", "carddavs"]}
    return res


def checkAutodiscoverSRV(domain: str):
    res = None
    resExternal = None
    adIp = None
    try:
        records = resolver.query("_autodiscover._tcp." + domain, "SRV")
        res = ", ".join([str(r) for r in records])
    except Exception:
        pass

    externalResolver = ExternalResolver.get()
    if externalResolver is not None:
        try:
            records = externalResolver.query("_autodiscover._tcp." + domain, "SRV")
            resExternal = ", ".join([str(r) for r in records])
            adIp = ip(str(records[0]).split(" ")[3])
        except Exception:
            pass
    return {"internalDNS": res, "externalDNS": resExternal, "ip": adIp }


def checkTXT(domain: str):
    res = None
    resExternal = None
    try:
        txtRecords = resolver.query(domain, "TXT")
        res = ", ".join([str(r) for r in txtRecords if str(r).startswith('"v=spf1')])
    except Exception:
        pass

    externalResolver = ExternalResolver.get()
    if externalResolver is not None:
        try:
            txtRecordsExternal = externalResolver.query(domain, "TXT")
            resExternal = ", ".join([str(r) for r in txtRecordsExternal if str(r).startswith('"v=spf1')])
        except Exception:
            pass
    return {"internalDNS": res, "externalDNS": resExternal}


def checkDKIM(domain: str):
    return defaultDNSQuery("dkim._domainkey.", domain, recordType="TXT")


def checkDMARC(domain: str):
    return defaultDNSQuery("_dmarc.", domain, recordType="TXT")


def checkCaldavTxt(domain: str):
    return defaultDNSQuery("_caldavs._tcp.", domain, recordType="TXT")


def checkCarddavTxt(domain: str):
    return defaultDNSQuery("_carddavs._tcp.", domain, recordType="TXT")


def defaultDNSQuery(subdomain: str, domain: str, recordType="A", path=""):
    res = None
    resExternal = None
    try:
        records = resolver.query(subdomain + domain + path, recordType)
        res = ", ".join([str(r) for r in records])
    except Exception:
        pass
    
    externalResolver = ExternalResolver.get()
    if externalResolver is not None:
        try:
            records = externalResolver.query(subdomain + domain + path, recordType)
            resExternal = ", ".join([str(r) for r in records])
        except Exception:
            pass
    return {"internalDNS": res, "externalDNS": resExternal}



LEGACY_KEY_DIR = "/var/lib/grommunio-admin-api"
LEGACY_KEY_SUFFIX = ".dkim.key"
IMPORT_MARKER = ("grommunio-admin", "dkim", "legacyFileImport")


def _storeDkimKeyInRedis_(domain, selector, privateKey):
    """Push a DKIM private key into the local Redis keystore.

    rspamd (grommunio-antispam) reads keys from these hashes when
    dkim_signing is configured with use_redis (key_prefix/selector_prefix
    as configured in grommunio-setup).

    Returns (stored, error); error is an error string if the push failed,
    None otherwise.
    """
    if not Config.get("dkimRedis", {}).get("enabled", False):
        return False, "DKIM keystore is disabled (dkimRedis.enabled)"
    try:
        with Service("dkimredis", errors=Service.SUPPRESS_INOP) as redis:
            pipe = redis.pipeline()
            pipe.hset("DKIM_PRIV_KEYS", "{}.{}".format(selector, domain), privateKey.strip())
            pipe.hset("DKIM_SELECTORS", domain, selector)
            pipe.execute()
            return True, None
    except Exception as err:
        return False, str(err)


def loadDkimKeys():
    """Load all DKIM keys from the database (the source of truth).

    Returns
    -------
    list
        (domainname, selector, privateKey) tuples, or None if the database
        schema does not carry the dkim_keys table yet.
    """
    from orm import DB
    if not DB.minVersion(135):
        return None
    from orm.dkim import DkimKeys
    from orm.domains import Domains
    return (DB.session.query(Domains.domainname, DkimKeys.selector, DkimKeys.privateKey)
            .join(DkimKeys, DkimKeys.domainID == Domains.ID).all())


def syncDkimKeysToRedis():
    """Replicate the DKIM keys of the database into the local keystore.

    The database is the source of truth; this pushes its rows into the
    local Redis keystore that rspamd reads (use_redis). Run by
    `grommunio-admin dkim sync` (grommunio-admin-dkim-sync.timer) and on
    API startup, so failed pushes are retried until they succeed.

    Returns (pushed, failed).
    """
    rows = loadDkimKeys()
    if rows is None:
        return 0, 0
    pushed = failed = 0
    for domainname, selector, privateKey in rows:
        stored, error = _storeDkimKeyInRedis_(domainname, selector, privateKey)
        if stored:
            pushed += 1
        else:
            failed += 1
            logger.error("Failed to push DKIM key %s.%s into the keystore: %s",
                         selector, domainname, error)
    return pushed, failed


def importLegacyDkimFiles():
    """Import DKIM key files of previous versions into the database.

    Files named <domain>.dkim.key in the admin-api data directory are read,
    stored in the database (selector "dkim", as before) and deleted - the
    database is the only storage, there is no fallback to files. The import
    runs once per node, guarded by the dbconf marker
    grommunio-admin/dkim/legacyFileImport (comma separated list of host
    names that completed the import). A node retries on its next start only
    if the import failed before.

    Returns None on success, an error string otherwise.
    """
    import glob
    import os
    import socket

    from orm import DB
    from orm.dkim import DkimKeys
    from orm.domains import Domains
    from orm.misc import DBConf

    if not DB.minVersion(135):
        return "Database schema too old for DKIM key storage (GX-135 required)"

    hostname = socket.gethostname()
    done = [entry for entry in (DBConf.getValue(*IMPORT_MARKER) or "").split(",") if entry]
    if hostname in done:
        return None
    error = None
    try:
        for path in sorted(glob.glob(os.path.join(LEGACY_KEY_DIR, "*" + LEGACY_KEY_SUFFIX))):
            domainname = os.path.basename(path)[:-len(LEGACY_KEY_SUFFIX)]
            try:
                with open(path, encoding="ascii") as f:
                    pem = f.read().strip()
                domain = Domains.query.filter(Domains.domainname == domainname).first()
                if domain is None:
                    raise LookupError("domain '{}' does not exist".format(domainname))
                DkimKeys.upsert(domain.ID, "dkim", pem)
                os.remove(path)
                for suffix in (".pub", ".old", ".pub.old"):
                    if os.path.exists(path + suffix):
                        os.remove(path + suffix)
                logger.info("Imported DKIM key for domain '%s' from %s", domainname, path)
            except Exception as err:
                error = str(err)
                logger.error("Failed to import DKIM key file %s: %s", path, err)
        if error is None and hostname not in done:
            done.append(hostname)
        DBConf.setFile(IMPORT_MARKER[0], IMPORT_MARKER[1], {IMPORT_MARKER[2]: ",".join(done)})
        DB.session.commit()
    except Exception as err:
        DB.session.rollback()
        return str(err)
    return error


def _removeLegacyKeyFiles_(domain):
    """Remove plaintext key remains of previous versions of a domain."""
    import os
    base = os.path.join(LEGACY_KEY_DIR, domain + LEGACY_KEY_SUFFIX)
    for suffix in ("", ".pub", ".old", ".pub.old"):
        try:
            if os.path.exists(base + suffix):
                os.remove(base + suffix)
        except Exception as err:
            logger.warning("Failed to remove legacy DKIM key file %s: %s", base + suffix, err)


def _parseDkimKeygenOutput_(out, mode):
    """Split rspamadm dkim_keygen stdout into (privateKey, pubKey).

    Without -k, rspamadm prints the private key to stdout first (a PEM
    block for RSA, a bare base64 line for ed25519) followed by the public
    key in the requested output format.
    """
    pem = _DKIM_PEM_RE.search(out)
    if pem is not None:
        return pem.group(0), out[pem.end():].strip()
    lines = [line for line in out.splitlines() if line.strip()]
    if not lines:
        return None, None
    if mode == "plain":
        # Both parts are bare base64 lines, the private key comes first.
        return lines[0], lines[-1]
    marker = out.find("v=DKIM1;") if mode == "dnskey" else out.find("_domainkey")
    if marker <= 0:
        return None, None
    return out[:marker].strip(), out[marker:].strip()


def generateDkimKeys(domain, type="rsa", mode="dns", selector="dkim"):
    """Generate a DKIM keypair, store the private key in the database and
    replicate it into the local Redis keystore.

    rspamadm prints the private key to stdout, so nothing is written to
    disk: the key goes straight into the database, which is its only
    storage. Plaintext key files of previous versions are removed once
    the key is stored there (no fallback). The public key is returned
    for the DNS TXT record; failed keystore pushes are retried by
    `grommunio-admin dkim sync`.

    Returns ({pubKey, dbStored, redisStored, redisError}, error).
    """
    from orm import DB
    from orm.dkim import DkimKeys
    from orm.domains import Domains

    if not DB.minVersion(135):
        return None, "Database schema too old for DKIM key storage (GX-135 required)"

    domainEntry = Domains.query.filter(Domains.domainname == domain).first()
    if domainEntry is None:
        return None, "Domain not found"

    proc = subprocess.run(("rspamadm", "dkim_keygen",
                           "-s", selector,
                           "-b", "2048",
                           "-d", domain,
                           "-t", type,
                           "-o", mode),
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          universal_newlines=True)
    if proc.returncode != 0:
        return None, "Key generation failed (rspamadm dkim_keygen): {}".format(proc.stderr.strip())
    privateKey, pubKey = _parseDkimKeygenOutput_(proc.stdout, mode)
    if not privateKey or not pubKey:
        return None, "Key generation failed (unexpected rspamadm output)"

    try:
        DkimKeys.upsert(domainEntry.ID, selector, privateKey)
    except Exception as err:
        DB.session.rollback()
        return None, "Failed to store key in database: {}".format(err)
    _removeLegacyKeyFiles_(domain)

    redisStored, redisError = _storeDkimKeyInRedis_(domain, selector, privateKey)
    return {"pubKey": pubKey, "dbStored": True, "redisStored": redisStored,
            "redisError": redisError}, None
