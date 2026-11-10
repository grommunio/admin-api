# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 grommunio GmbH

"""Human-readable audit log, modeled after gromox-audit.

Disabled unless `audit.enabled` is set. Lines go to syslog (facility authpriv,
identifier grommunio-admin) and start with "admin-audit:".
"""

import logging
import logging.handlers
import os
import pwd
import re
import unicodedata

from .config import Config

logger = logging.getLogger("audit")
logger.propagate = False

WRITE = ("POST", "PUT", "PATCH", "DELETE")

_secret = re.compile(r"pass|secret|token|cred", re.I)
_maxlen = 200


def enabled():
    return bool(Config.get("audit", {}).get("enabled"))


def _setup():
    if logger.handlers:
        return
    try:
        handler = logging.handlers.SysLogHandler("/dev/log", logging.handlers.SysLogHandler.LOG_AUTHPRIV)
        handler.ident = "grommunio-admin: "
    except OSError:
        handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def esc(value):
    """Escape like gromox txt2cstr, so no input can start a new log line."""
    value = str(value)
    if len(value) > _maxlen:
        value = value[:_maxlen]+"..."
    out = []
    for c in value:
        if c in '"\\':
            out.append("\\"+c)
        elif unicodedata.category(c) in ("Cc", "Zl", "Zp"):
            out.append("\\x{:02x}".format(ord(c)) if ord(c) < 0x100 else "\\u{:04x}".format(ord(c)))
        else:
            out.append(c)
    return "".join(out)


def q(value):
    return '"'+esc(value)+'"'


def log(msg):
    if not enabled():
        return
    try:
        _setup()
        # Bypass level filtering: only audit.enabled decides
        logger.handle(logger.makeRecord(logger.name, logging.INFO, __file__, 0, "admin-audit: "+msg, None, None))
    except Exception as err:
        logging.getLogger("config").error("Failed to write audit log: "+repr(err))


def _value(value):
    if isinstance(value, (list, tuple)):
        return "["+", ".join(_value(v) for v in value)+"]"
    if isinstance(value, (bool, int, float)):
        return str(value)
    return q(value)


def _fields(data, values=()):
    """Describe request data: field names only, values for the keys listed in `values`."""
    if isinstance(data, list):
        return "{} entries".format(len(data)) if "*" not in values else _value(data)
    if not isinstance(data, dict):
        return ""
    parts = []
    for key in sorted(data):
        if key in values and not _secret.search(key):
            value = _roleNames(data[key]) if key == "roles" else data[key]
            parts.append("{}={}".format(esc(key), _value(value)))
        else:
            parts.append(esc(key))
    return ", ".join(parts)


# API actions: (method, rule) -> (infinitive, past tense, target, logged values)
_routes = {
    ("POST", "/domains/<int:domainID>/users"): ("create", "created", "user {body:username} in {domain}", ("status",)),
    ("PATCH", "/domains/<int:domainID>/users/<int:userID>"): ("modify", "modified", "{user}", ("lang", "status")),
    ("DELETE", "/domains/<int:domainID>/users/<int:userID>"): ("delete", "deleted", "{user}", ()),
    ("PUT", "/domains/<int:domainID>/users/<int:userID>/password"): ("set", "set", "password of {user}", ()),
    ("PATCH", "/domains/<int:domainID>/users/<int:userID>/roles"): ("set", "set", "admin roles of {user}", ("roles",)),
    ("PUT", "/domains/<int:domainID>/users/<int:userID>/delegates"): ("set", "set", "delegates of {user}", ("*",)),
    ("PUT", "/domains/<int:domainID>/users/<int:userID>/sendas"):
        ("set", "set", "send-as permissions of {user}", ("*",)),
    ("PUT", "/domains/<int:domainID>/users/<int:userID>/storeAccess"): ("set", "set", "store access to {user}", ("*",)),
    ("POST", "/domains/<int:domainID>/users/<int:userID>/storeAccess"):
        ("grant", "granted", "store access to {user}", ("username", "user")),
    ("PATCH", "/domains/<int:domainID>/users/<int:userID>/storeAccess"):
        ("modify", "modified", "store access to {user}", ("username", "user")),
    ("DELETE", "/domains/<int:domainID>/users/<int:userID>/storeAccess/<username>"):
        ("revoke", "revoked", "store access of {username} to {user}", ()),
    ("PATCH", "/domains/<int:domainID>/users/<int:userID>/storeProps"):
        ("modify", "modified", "store properties of {user}", ()),
    ("DELETE", "/domains/<int:domainID>/users/<int:userID>/storeProps"):
        ("delete", "deleted", "store properties of {user}", ()),
    ("PUT", "/domains/<int:domainID>/users/<int:userID>/oof"): ("set", "set", "out-of-office of {user}", ("state",)),
    ("PUT", "/domains/<int:domainID>/users/<int:userID>/downsync"): ("sync", "synced", "{user} from LDAP", ()),
    ("DELETE", "/domains/<int:domainID>/users/<int:userID>/sync"): ("remove", "removed", "all devices of {user}", ()),
    ("DELETE", "/domains/<int:domainID>/users/<int:userID>/sync/<deviceID>"):
        ("remove", "removed", "device {deviceID} of {user}", ()),
    ("POST", "/domains/<int:domainID>/users/<int:userID>/sync/<deviceID>/wipe"):
        ("request", "requested", "wipe of device {deviceID} of {user}", ("status",)),
    ("DELETE", "/domains/<int:domainID>/users/<int:userID>/sync/<deviceID>/wipe"):
        ("cancel", "cancelled", "wipe of device {deviceID} of {user}", ()),
    ("PUT", "/domains/<int:domainID>/users/<int:userID>/sync/<deviceID>/resync"):
        ("resync", "resynced", "device {deviceID} of {user}", ()),
    ("POST", "/domains/<int:domainID>/mlists"): ("create", "created", "mailing list {body:listname} in {domain}", ()),
    ("PATCH", "/domains/<int:domainID>/mlists/<int:ID>"): ("modify", "modified", "{mlist}", ()),
    ("DELETE", "/domains/<int:domainID>/mlists/<int:ID>"): ("delete", "deleted", "{mlist}", ()),
    ("POST", "/domains/<int:domainID>/folders"):
        ("create", "created", "public folder {body:displayname} in {domain}", ()),
    ("PATCH", "/domains/<int:domainID>/folders/<int:folderID>"):
        ("modify", "modified", "public folder {folderID} in {domain}", ()),
    ("DELETE", "/domains/<int:domainID>/folders/<int:folderID>"):
        ("delete", "deleted", "public folder {folderID} in {domain}", ()),
    ("POST", "/domains/<int:domainID>/folders/<int:folderID>/owners"):
        ("add", "added", "owner to public folder {folderID} in {domain}", ("username", "permissions")),
    ("PUT", "/domains/<int:domainID>/folders/<int:folderID>/owners/<int:memberID>"):
        ("modify", "modified", "owner {member} of public folder {folderID} in {domain}", ("permissions",)),
    ("DELETE", "/domains/<int:domainID>/folders/<int:folderID>/owners/<int:memberID>"):
        ("remove", "removed", "owner {member} from public folder {folderID} in {domain}", ()),
    ("PUT", "/domains/<int:domainID>/disabledPlugins"): ("set", "set", "disabled plugins of {domain}", ("*",)),
    ("POST", "/domains/<int:domainID>/generateDkimKeys"): ("generate", "generated", "DKIM keys for {domain}", ()),
    ("POST", "/domains/<int:domainID>/ldap/downsync"): ("sync", "synced", "users of {domain} from LDAP", ()),
    ("POST", "/domains/ldap/downsync"): ("sync", "synced", "users from LDAP", ()),
    ("POST", "/domains/ldap/importUser"): ("import", "imported", "user from LDAP", ()),
    ("DELETE", "/domains/ldap/check"): ("delete", "deleted", "orphaned LDAP users", ()),
    ("PATCH", "/defaults/createParams"): ("modify", "modified", "default create parameters", ()),
    ("PUT", "/defaults/createParams"): ("set", "set", "default create parameters", ()),
    ("PATCH", "/defaults/createParams/<int:domainID>"): ("modify", "modified", "create parameters of {domain}", ()),
    ("PUT", "/defaults/createParams/<int:domainID>"): ("set", "set", "create parameters of {domain}", ()),
    ("PUT", "/passwd"): ("change", "changed", "own password", ()),
    ("PUT", "/passwd/<username>"): ("reset", "reset", "password of user {username}", ()),
    ("POST", "/service/wipe/<username>"): ("set", "set", "device wipe status of user {username}", ("status",)),
    ("POST", "/system/domains"): ("create", "created", "domain {body:domainname}", ("orgID", "domainStatus")),
    ("PATCH", "/system/domains/<int:domainID>"): ("modify", "modified", "{domain}", ("orgID", "domainStatus", "chat")),
    ("DELETE", "/system/domains/<int:domainID>"): ("delete", "deleted", "{domain}", ()),
    ("POST", "/system/orgs"): ("create", "created", "organization {body:name}", ()),
    ("PATCH", "/system/orgs/<int:ID>"): ("modify", "modified", "{org}", ()),
    ("DELETE", "/system/orgs/<int:ID>"): ("delete", "deleted", "{org}", ()),
    ("PUT", "/system/orgs/<int:ID>/ldap"): ("set", "set", "LDAP configuration of {org}", ()),
    ("DELETE", "/system/orgs/<int:ID>/ldap"): ("delete", "deleted", "LDAP configuration of {org}", ()),
    ("POST", "/system/orgs/<int:ID>/ldap/downsync"): ("sync", "synced", "users of {org} from LDAP", ()),
    ("POST", "/system/roles"): ("create", "created", "admin role {body:name}", ()),
    ("PATCH", "/system/roles/<int:ID>"): ("modify", "modified", "{role}", ()),
    ("DELETE", "/system/roles/<int:ID>"): ("delete", "deleted", "{role}", ()),
    ("POST", "/system/servers"): ("create", "created", "server {body:hostname}", ()),
    ("PATCH", "/system/servers/<int:ID>"): ("modify", "modified", "{server}", ()),
    ("DELETE", "/system/servers/<int:ID>"): ("delete", "deleted", "{server}", ()),
    ("POST", "/system/exmdb/<string:username>/folders/<int:fid>/permissions"):
        ("grant", "granted", "permissions on folder {fid} of {username}", ("username", "permissions")),
    ("PATCH", "/system/exmdb/<string:username>/folders/<int:fid>/permissions/<string:permittedUser>"):
        ("set", "set", "permissions of {permittedUser} on folder {fid} of {username}", ("permissions",)),
    ("DELETE", "/system/exmdb/<string:username>/folders/<int:fid>/permissions"):
        ("revoke", "revoked", "permissions on folder {fid} of {username}", ()),
    ("PUT", "/system/dbconf/<service>/<file>/"): ("set", "set", "configuration {service}/{file}", ()),
    ("PATCH", "/system/dbconf/<service>/<file>/"): ("modify", "modified", "configuration {service}/{file}", ()),
    ("DELETE", "/system/dbconf/<service>/<file>/"): ("delete", "deleted", "configuration {service}/{file}", ()),
    ("PATCH", "/system/dbconf/<service>/"): ("modify", "modified", "configuration of {service}", ()),
    ("DELETE", "/system/dbconf/<service>/"): ("delete", "deleted", "configuration of {service}", ()),
    ("PUT", "/system/mconf/ldap"): ("set", "set", "LDAP configuration", ()),
    ("DELETE", "/system/mconf/ldap"): ("delete", "deleted", "LDAP configuration", ()),
    ("PUT", "/system/mconf/authmgr"): ("set", "set", "authmgr configuration", ("authBackendSelection",)),
    ("DELETE", "/system/mconf/authmgr"): ("delete", "deleted", "authmgr configuration", ()),
    ("PUT", "/system/license"): ("upload", "uploaded", "license", ()),
    ("PUT", "/system/license/creds"): ("set", "set", "license credentials", ()),
    ("POST", "/system/mailq/delete"): ("delete", "deleted", "mail queue entries", ("queue",)),
    ("POST", "/system/mailq/flush"): ("flush", "flushed", "mail queue", ()),
    ("POST", "/system/mailq/requeue"): ("requeue", "requeued", "mail queue entries", ("queue",)),
    ("POST", "/system/dashboard/services/<unit>/<action>"): ("run", "ran", "{action} on service {unit}", ()),
    ("POST", "/system/updates/<string:command>"): ("run", "ran", "system update command {command}", ()),
    ("POST", "/tasq/notify"): ("notify", "notified", "task queue", ()),
    ("POST", "/tasq/start"): ("start", "started", "task queue", ()),
    ("POST", "/tasq/stop"): ("stop", "stopped", "task queue", ()),
    ("POST", "/tasq/tasks/<int:ID>/cancel"): ("cancel", "cancelled", "task {ID}", ()),
    ("DELETE", "/tasq/tasks/<int:ID>"): ("delete", "deleted", "task {ID}", ()),
}

_skip = {"/login", "/logout"}  # audited by the endpoint
_selfAudited = {"/system/cli"}  # success audited by the CLI


def _roleNames(IDs):
    try:
        from orm.roles import AdminRoles
        names = dict(AdminRoles.query.filter(AdminRoles.ID.in_(IDs)).with_entities(AdminRoles.ID, AdminRoles.name))
        return [names.get(ID, ID) for ID in IDs]
    except Exception:
        return IDs


def _lookup(kind, ID):
    from orm.domains import Domains, Orgs
    from orm.misc import Servers
    from orm.mlists import MLists
    from orm.roles import AdminRoles
    from orm.users import Users
    model, attr, label = {"domain": (Domains, "domainname", "domain"),
                          "user": (Users, "username", "user"),
                          "member": (Users, "username", "user"),
                          "org": (Orgs, "name", "organization"),
                          "role": (AdminRoles, "name", "admin role"),
                          "server": (Servers, "hostname", "server"),
                          "mlist": (MLists, "listname", "mailing list")}[kind]
    try:
        obj = model.query.filter(model.ID == ID).first()
        if obj is not None:
            return "{} {}".format(label, q(getattr(obj, attr)))
    except Exception:
        pass
    return "{} #{}".format(label, ID)


def _target(template, args, body):
    idkeys = {"domain": "domainID", "user": "userID", "member": "memberID", "org": "ID", "role": "ID",
              "server": "ID", "mlist": "ID"}

    def sub(match):
        key = match.group(1)
        if key.startswith("body:"):
            value = body.get(key[5:]) if isinstance(body, dict) else None
            return q(value) if value is not None else "(unnamed)"
        if key in idkeys:
            return _lookup(key, args.get(idkeys[key]))
        return q(args.get(key, ""))
    return re.sub(r"\{([^}]+)\}", sub, template)


def apiBegin(request):
    """Collect what the request is about, before the endpoint runs (and possibly deletes it)."""
    from api import BaseRoute
    rule = request.url_rule.rule[len(BaseRoute):] if request.url_rule else request.path
    body = request.get_json(silent=True)
    if body is None and request.form:
        body = {key: None for key in request.form}
    action = _routes.get((request.method, rule))
    if action:
        inf, past, template, values = action
        target = _target(template, request.view_args or {}, body)
    else:
        inf = past = request.method
        target, values = q(request.path), ()
    details = _fields(body, values) if body is not None else ""
    params = ", ".join(esc(key) if _secret.search(key) else "{}={}".format(esc(key), q(value))
                       for key, value in request.args.items())
    details = ", ".join(part for part in (details, params) if part)
    return dict(rule=rule, inf=inf, past=past, target=target, details=details, body=body)


def apiActor(request, body=None):
    auth = getattr(request, "auth", None) or {}
    user = (auth.get("claims") or {}).get("usr")
    if user is None and isinstance(body, dict) and isinstance(body.get("user"), str):
        user = body["user"]
    return "{} from {}".format(q(user) if user else "anonymous", esc(request.remote_addr))


def apiEnd(request, ctx, response):
    status = response.status_code
    if ctx["rule"] in _skip or status < 400 and ctx["rule"] in _selfAudited:
        return
    actor = apiActor(request, ctx["body"])
    details = " ({})".format(ctx["details"]) if ctx["details"] else ""
    if status < 400:
        log("{} {} {}{}".format(actor, ctx["past"], ctx["target"], details))
        return
    message = (response.get_json(silent=True) or {}).get("message", "") if response.is_json else ""
    reason = "access denied" if status in (401, 403) else "HTTP {}".format(status)
    log("{} tried to {} {}{}: {}{}".format(actor, ctx["inf"], ctx["target"], details, reason,
                                         " ({})".format(q(message)) if message else ""))


def login(request, user, method, error=None):
    who = q(user) if user else "unknown user"
    if error is None:
        log("{} logged in from {} via {}".format(who, esc(request.remote_addr), method))
    else:
        log("failed {} login for {} from {}: {}".format(method, who, esc(request.remote_addr), q(error)))


def _cliActor():
    try:
        name = pwd.getpwuid(os.getuid()).pw_name
    except KeyError:
        name = "uid {}".format(os.getuid())
    sudo = os.environ.get("SUDO_USER")
    return q("{} as {}".format(sudo, name) if sudo and sudo != name else name)


_readonly = {"check", "commands", "connect", "du", "dump", "find", "get", "info", "list", "permissions", "print",
             "query", "run", "search", "shell", "show", "shrek", "status", "taginfo", "trace", "version"}


def cliCommand(parser, args):
    """Return (command path, parsers) or (None, None) for read-only commands."""
    import argparse
    path, parsers = [], [parser]
    for tok in args:
        subs = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
        if not subs:
            break
        if tok in subs[0].choices:
            path.append(tok)
            parser = subs[0].choices[tok]
            parsers.append(parser)
    if not path or path[-1] in _readonly:
        return None, None
    return " ".join(path), parsers


def cliArgs(parsers, ns):
    """Arguments that differ from their defaults, secrets redacted."""
    parts = []
    for action in (action for parser in parsers for action in parser._actions):
        dest = action.dest
        if dest in ("help", "==SUPPRESS==") or dest.startswith("_") or not hasattr(ns, dest):
            continue
        value = getattr(ns, dest)
        if value == action.default or value is None:
            continue
        secret = _secret.search(dest) or (dest == "value" and _secret.search(str(getattr(ns, "key", ""))))
        parts.append("{}={}".format(esc(dest), "***" if secret else _value(value)))
    return ", ".join(parts)


def cli(cli, path, parsers, ns, code):
    if cli.mode == "adhoc":
        from flask import request
        actor = apiActor(request)+" via remote CLI"
    else:
        actor = _cliActor()+" via CLI"
    args = cliArgs(parsers, ns)
    details = " ({})".format(args) if args else ""
    if code == 0:
        log("{} ran {}{}".format(actor, q(path), details))
    else:
        log("{} ran {}{}: failed ({})".format(actor, q(path), details,
                                             "exit code {}".format(code) if code is not None else "error"))
