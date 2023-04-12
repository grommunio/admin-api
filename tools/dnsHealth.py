# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2023 grommunio GmbH

from dns import resolver, reversename
import socket

from .config import Config


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


externalResolver = resolver.Resolver()
externalResolver.nameservers = Config["dns"]["externalResolvers"]


def fullDNSCheck(domain: str):
    localIp = getLocalIp()
    externalIp = checkMyIP()
    mxRecords = checkMX(domain)
    autodiscover = checkAutodiscover(domain)
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
        "autoconfig": autoconfig,
        "txt": txt,
        "dkim": dkim,
        "dmarc": dmarc,
        "caldavTXT": caldavTXT,
        "carddavTXT": carddavTXT,
        **srv
    }


def checkMyIP():
    customResolver = resolver.Resolver()
    customResolver.nameservers = ["208.67.222.222", "208.67.220.220", "208.67.222.220"]
    res = None
    try:
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
    try:
        mxRecords = resolver.query(domain, "MX")
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
           for subdomain in ["autodiscover", "submission", "imap", "imaps", "pop3", "pop3s", "caldav", "caldavs", "carddav", "carddavs"]}
    return res


def checkAutodiscoverSRV(domain: str):
    return defaultDNSQuery("_autodiscover._tcp.", domain, recordType="SRV")


def checkTXT(domain: str):
    res = None
    resExternal = None
    try:
        txtRecords = resolver.query(domain, "TXT")
        res = ", ".join([str(r) for r in txtRecords if str(r).startswith('"v=spf1')])
    except Exception:
        pass

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
    return defaultDNSQuery("_caldavs._tcp", domain, recordType="TXT", path="/dav")


def checkCarddavTxt(domain: str):
    return defaultDNSQuery("_carddavs._tcp", domain, recordType="TXT", path="/dav")


def defaultDNSQuery(subdomain: str, domain: str, recordType="A", path=""):
    res = None
    resExternal = None
    try:
        records = resolver.query(subdomain + domain + path, recordType)
        res = ", ".join([str(r) for r in records])
    except Exception:
        pass

    try:
        records = externalResolver.query(subdomain + domain + path, recordType)
        resExternal = ", ".join([str(r) for r in records])
    except Exception:
        pass
    return {"internalDNS": res, "externalDNS": resExternal}
