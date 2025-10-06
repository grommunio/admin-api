# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH

from . import Cli, InvalidUseError
from .common import proptagCompleter, Table

from argparse import ArgumentParser
from tools.deviceutils import retrieve_lastconnecttime

_statusMap = {0: "active", 1: "suspended", 3: "deleted", 4: "shared", 5: "contact"}
_statusColor = {0: "green", 1: "yellow", 3: "red", 4: "cyan", 5: "blue"}
_userAttributes = ("ID", "aliases", "changePassword", "chat", "chatAdmin", "domainID", "forward", "homeserverID", "lang",
                   "ldapID", "maildir", "pop3_imap", "privArchive", "privChat", "privFiles", "privVideo", "privWeb", "privDav",
                   "privEas", "publicAddress", "smtp", "status", "username")
_deviceStatus = {0: "unknown", 1: "ok", 2: "pending", 4: "requested", 8: "wiped", 16: "pending (account)",
                 32: "requested (account)", 64: "wiped (account)"}
_deviceStatusStyle = {0: {"attrs": ["dark"]},
                      1: {"color": "green"},
                      2: {"color": "yellow"},
                      4: {"color": "red"},
                      8: {"color": "light_red"},
                      16: {"color": "yellow"},
                      32: {"color": "red"},
                      64: {"color": "light_red"}}


def _mkUserQuery(args):
    from .common import userFilter
    from orm.users import Users
    query = Users.query
    if "userspec" in args:
        query = query.filter(userFilter(args.userspec))
    if "filter" in args and args.filter is not None:
        query = Users.autofilter(query, {f.split("=", 1)[0]: f.split("=", 1)[1] for f in args.filter if "=" in f})
    if "sort" in args and args.sort is not None:
        query = Users.autosort(query, args.sort)
    return query


def _mkStatus(cli, status):
    return cli.col(_statusMap.get(status, "unknown"), _statusColor.get(status, "magenta"))


def _dumpUser(cli, user, indent=0):
    def privstr():
        from orm.users import Users
        bits = user.privilegeBits
        privs = []
        if bits & Users.USER_PRIVILEGE_POP3_IMAP:
            privs.append("pop_imap")
        if bits & Users.USER_PRIVILEGE_SMTP:
            privs.append("smtp")
        if bits & Users.USER_PRIVILEGE_CHGPASSWD:
            privs.append("passwd")
        if bits & Users.USER_PRIVILEGE_PUBADDR:
            privs.append("pubaddr")
        if bits & Users.USER_PRIVILEGE_CHAT:
            privs.append("chat")
        if bits & Users.USER_PRIVILEGE_VIDEO:
            privs.append("video")
        if bits & Users.USER_PRIVILEGE_FILES:
            privs.append("files")
        if bits & Users.USER_PRIVILEGE_ARCHIVE:
            privs.append("archive")
        if bits & (Users.USER_PRIVILEGE_WEB | Users.USER_PRIVILEGE_DETAIL1) != Users.USER_PRIVILEGE_DETAIL1:
            privs.append("web")
        if bits & (Users.USER_PRIVILEGE_DAV | Users.USER_PRIVILEGE_DETAIL1) != Users.USER_PRIVILEGE_DETAIL1:
            privs.append("dav")
        if bits & (Users.USER_PRIVILEGE_EAS | Users.USER_PRIVILEGE_DETAIL1) != Users.USER_PRIVILEGE_DETAIL1:
            privs.append("eas")
        if len(privs) == 0:
            return ""
        return "("+",".join(privs)+")"

    from ldap3.utils.conv import escape_filter_chars
    user.embedStoreProperties()
    homeserver = cli.col("(local)", attrs=["dark"]) if user.homeserver is None else \
        "{} ({})".format(user.homeserver.ID, user.homeserver.hostname)
    cli.print("{}ID: {}".format(" "*indent, user.ID))
    cli.print("{}username: {}".format(" "*indent, user.username))
    cli.print("{}domainID: {}".format(" "*indent, user.domainID))
    cli.print("{}homeserver: {}".format(" "*indent, homeserver))
    cli.print("{}lang: {}".format(" "*indent, user.lang or cli.col("(not set)", attrs=["dark"])))
    cli.print("{}maildir: {}".format(" "*indent, user.maildir or cli.col("(not set)", attrs=["dark"])))
    cli.print("{}privilegeBits: {} {}".format(" "*indent, user.privilegeBits, cli.col(privstr(), attrs=["dark"])))
    cli.print("{}addressStatus: {} ({}|{})".format(" "*indent, user.addressStatus,
                                                   _mkStatus(cli, user.domainStatus), _mkStatus(cli, user.status)))
    cli.print(" "*indent+"ldapID: "+(escape_filter_chars(user.externID) if user.externID is not None else
                                     cli.col("(none)", attrs=["dark"])))
    cli.print(" "*indent+"chat: "+(user.chatID if user.chatID else cli.col("(none)", attrs=["dark"])) +
              (" ("+cli.col("inactive", "red")+")" if user.chatID and not user.chat else ""))
    if user.chat:
        cli.print(" "*indent+"chatAdmin: "+(cli.col("yes", "yellow") if user.chatAdmin else "no"))
    cli.print(" "*indent+"aliases:"+(cli.col(" (none)", attrs=["dark"]) if len(user.aliases) == 0 else ""))
    for alias in user.aliases:
        cli.print(" "*indent+"  "+alias.aliasname)
    cli.print(" "*indent+"altnames:"+(cli.col(" (none)", attrs=["dark"]) if len(user.altnames) == 0 else ""))
    for altname in user.altnames:
        cli.print(" "*indent+"  "+altname.altname)
    cli.print(" "*indent+"roles:"+(cli.col(" (none)", attrs=["dark"]) if len(user.roles) == 0 else ""))
    for role in user.roles:
        cli.print(" "*indent+"  "+role.name)
    cli.print(" "*indent+"fetchmail:"+(cli.col(" (none)", attrs=["dark"]) if len(user.fetchmail) == 0 else ""))
    for fml in user.fetchmail:
        cli.print("{}  {}@{}/{} ({})".format(" "*indent, fml.srcUser, fml.srcServer, fml.srcFolder,
                                             cli.col("active", "green") if fml.active == 1 else cli.col("inactive", "red")))
    cli.print(" "*indent+"properties:"+(cli.col(" (none)", attrs=["dark"]) if len(user.properties) == 0 else ""))
    for key, value in user.properties.items():
        cli.print("{}  {}: {}".format(" "*indent, key, value))


def _getUser(args, requireMailbox=False):
    cli = args._cli
    users = _mkUserQuery(args).all()
    if len(users) == 0:
        cli.print(cli.col("No user matching '{}'.".format(args.userspec), "yellow"))
        return 1, None
    if len(users) > 1:
        cli.print("'{}' is ambiguous. Candidates are:".format(args.userspec))
        for user in users:
            cli.print("  {}:\t{}".format(user.ID, user.username))
        return 2, None
    if requireMailbox and not users[0].maildir:
        cli.print(cli.col(f"User '{users[0].username}' has no mailbox", "red"))
        return 3, None
    return 0, users[0]


def _splitData(args):
    cli = args["_cli"]
    cliargs = {"_handle", "_cli", "userspec", "no_defaults", "no_maildir"}
    data = {}
    attributes = data["attributes"] = {key: value for key, value in args.items() if value is not None and key not in cliargs}
    if "storeprop" in attributes or "remove_storeprop" in attributes:
        cli.print(cli.col("--storeprop and --remove_storeprop arguments are deprecated, use --property and --remove_property "
                          "instead.", "yellow"))
    data["aliases"] = attributes.pop("alias", None) or ()
    data["aliases_rm"] = attributes.pop("remove_alias", None) or ()
    data["altnames"] = [{"altname": altname} for altname in attributes.pop("altname", None) or []]
    data["altnames_rm"] = attributes.pop("remove_altname", None) or {}
    data["props"] = attributes.pop("property", []) + attributes.pop("storeprop", [])
    data["props_rm"] = attributes.pop("remove_property", []) + attributes.pop("remove_storeprop", [])
    data["noldap"] = attributes.pop("no_ldap", False)
    data["delchat"] = attributes.pop("delete_chat_user", False)
    return data


def _usernamesFromFile(filename, args):
    import os
    cli = args._cli
    ret, user = _getUser(args)
    if ret:
        return ret, None, None
    if not user.maildir:
        cli.print(cli.col("User has no mailbox", color="yellow"))
        return 10, None, user

    try:
        with open(os.path.join(user.maildir, "config", filename), encoding="utf-8") as file:
            return 0, [line.strip() for line in file if line.strip() != ""], user
    except FileNotFoundError:
        return 0, [], user
    except (PermissionError, TypeError) as err:
        cli.print(cli.col(str(err), "red"))
        return 11, None, user


def _usernamesToFile(filename, usernames, args):
    import os
    from orm.users import Users
    from tools import formats
    from tools.config import Config
    from tools.misc import setDirectoryOwner, setDirectoryPermission

    cli = args._cli
    ret, user = _getUser(args)
    if ret:
        return ret
    if not user.maildir:
        cli.print(cli.col("User has no mailbox", color="yellow"))
        return 10

    if "force" not in args or not args.force:
        for entry in usernames:
            if not formats.email.match(entry):
                cli.print(cli.col(f"'{entry}' is not a valid e-mail address", color="red"))
                return 11
            if Users.query.filter(Users.username == entry).count() != 1:
                cli.print(cli.col(f"'{entry}' is not a known user", color="red"))
                return 12

    filepath = os.path.join(user.maildir, "config", filename)
    try:
        with open(filepath, "w", encoding="utf-8") as file:
            file.write("\n".join(usernames)+"\n")
    except (FileNotFoundError, PermissionError) as err:
        cli.print(cli.col(str(err), "red"))
        return 13
    try:
        setDirectoryOwner(filepath, Config["options"].get("fileUid"), Config["options"].get("fileGid"))
        setDirectoryPermission(filepath, Config["options"].get("filePermissions"))
    except Exception as err:
        cli.print(cli.col(f"Failed to set file permissions: {err}"))


def cliUserShow(args):
    cli = args._cli
    cli.require("DB")
    users = _mkUserQuery(args).all()
    if len(users) == 0:
        cli.print(cli.col("No users found.", "yellow"))
        return 1
    for user in users:
        cli.print(cli.col("{} ({}):".format(user.username, user.ID), attrs=["bold"]))
        _dumpUser(cli, user, 2)


def cliUserList(args):
    cli = args._cli
    cli.require("DB")
    cli.print(cli.col("The 'user list' command is deprecated and may be removed in the future. Use 'user query' instead.\n",
                      "yellow"))
    users = _mkUserQuery(args).all()
    if len(users) == 0:
        cli.print(cli.col("No users found.", "yellow"))
        return 1
    maxNameLen = max(len(user.username) for user in users)
    for user in users:
        if user.domainName() is not None:
            printName = "{}@{}".format(cli.col(user.baseName(), attrs=["bold"]), user.domainName())
        else:
            printName = cli.col(user.username, attrs=["bold"])
        cli.print("{}:\t{}{}({}|{})".format(user.ID, printName, " "*(maxNameLen-len(user.username)+4),
                                            _mkStatus(cli, user.domainStatus), _mkStatus(cli, user.status)))
    cli.print("({} users total)".format(len(users)))


def cliUserCreate(args):
    cli = args._cli
    cli.require("DB")
    from orm.domains import Domains
    from orm.misc import DBConf
    from orm.users import DB, Users
    from tools.misc import RecursiveDict
    if args.no_defaults:
        props = {}
    else:
        props = DBConf.getFile("grommunio-admin", "defaults-system", True).get("user", RecursiveDict())
        if "@" in args.username:
            domain = Domains.query.filter(Domains.domainname == args.username.split("@", 1)[1]).with_entities(Domains.ID).first()
            if domain is not None:
                props.update(DBConf.getFile("grommunio-admin", "defaults-domain-"+str(domain.ID), True).get("user", {}))
    data = _splitData(args.__dict__)
    props.update(data["attributes"])
    props["username"] = args.username
    props["aliases"] = data["aliases"]
    props["altnames"] = data["altnames"]
    properties = data["properties"] = {}
    if args.domain:
        from .common import domainCandidates
        domain = domainCandidates(args.domain).with_entities(Domains.ID).all()
        if len(domain) == 0:
            cli.print(cli.col("Domain not found.", "red"))
            return 2
        if len(domain) != 1:
            cli.print(cli.col("Domain specification is ambiguous.", "red"))
            return 3
        props["domainID"] = domain[0].ID

    for pv in data["props"]:
        if "=" in pv:
            prop, val = pv.split("=", 1)
            properties[prop] = val
    props["properties"] = properties
    result, code = Users.mkContact(props) if props.get("status", 0) == Users.CONTACT else\
        Users.create(props, maildir=not args.no_maildir)
    if code != 201:
        cli.print(cli.col("Could not create user: "+result, "red"))
        return 1
    DB.session.commit()
    _dumpUser(cli, result)


def cliUserDelete(args):
    cli = args._cli
    cli.require("DB")
    from orm import DB
    from tools.misc import GenericObject
    ret, user = _getUser(args)
    if ret:
        return ret
    userdata = GenericObject(maildir=user.maildir, homeserver=user.homeserver)
    if not args.yes:
        if cli.confirm("Delete user '{}' ({})? [y/N]: ".format(user.username, user.ID)) != Cli.SUCCESS:
            return 3
    else:
        cli.print("Deleting user '{}' ({})".format(user.username, user.ID))
    user.delete(not args.keep_chat)
    DB.session.commit()
    cli.print("User deleted.")
    if userdata.maildir == "":
        cli.print("No user files to delete.")
        return 0
    cli.print("Unloading store...", end="", flush=True)

    from services import Service
    with Service("exmdb", errors=Service.SUPPRESS_INOP) as exmdb:
        client = exmdb.user(user)
        client.unloadStore()
        cli.print("Done.", end="")
    cli.print("")
    if args.keep_files or (not args.yes and cli.confirm("Delete user directory from disk? [y/N]: ") != Cli.SUCCESS):
        cli.print(cli.col("Files remain in "+userdata.maildir, attrs=["bold"]))
        return 0
    cli.print("Deleting user files...", end="")
    import shutil
    shutil.rmtree(userdata.maildir, ignore_errors=True)
    cli.print("Done.")


def cliUserLogin(args):
    cli = args._cli
    cli.require("DB")
    from orm.users import Users
    user = Users.query.filter(Users.username == args.username).first()
    if user is None:
        cli.print(cli.col("User does not exist.", "red"))
        return 1
    if user.status != Users.NORMAL:
        cli.print(cli.col("Login deactivated for {} user.".format(_statusMap.get(user.status, "invalid")), "red"))
        return 2
    if user.externID is None and not user.password:
        cli.print(cli.col("User has no password set.", "red"))
        return 3
    from api.security import loginUser, mkCSRF, mkJWT
    if not args.nopass:
        if not args.password:
            args.password = cli.input("Password: ", secret=True)
        success, msg = loginUser(args.username, args.password)
        if not success:
            cli.print(cli.col(f"Login failed: {msg}", "red"))
            return 4
    if not args.token:
        cli.print(cli.col("Login ok.", "green"))
    else:
        token = mkJWT({"usr": user.username})
        csrf = mkCSRF(token)
        cli.print(cli.col("Token: ", attrs=["bold"])+token+"\n"+cli.col("CSRF: ", attrs=["bold"])+csrf)


def _cliUserDevicesDecodeSyncState(args, data, username):
    import base64
    import json
    try:
        data = json.loads(base64.b64decode(data))["data"]
        if "devices" in data:
            data = data["devices"][username]["data"]
        return data
    except Exception as err:
        cli = args._cli
        cli.print(cli.col("Failed to decode sync state ({}: {}"
                          .format(type(err).__name__, " - ".join(str(arg) for arg in err.args))))
        return {}


def _cliUserDevicesGetDevices(args, user):
    from services import Service
    from tools.config import Config
    from orm.users import UserDevices
    with Service("exmdb") as exmdb:
        client = exmdb.user(user)
        syncStates = client.getSyncData(Config["sync"]["syncStateFolder"])
    requested = args.device if "device" in args else ()
    syncStates = {device: _cliUserDevicesDecodeSyncState(args, state, user.username) for device, state in syncStates.items()
                  if not requested or device in requested}
    wipeStatus = {device.deviceID: device.status for device in UserDevices.query.filter(UserDevices.userID == user.ID)
                  if not requested or device.deviceID in requested}
    for device, state in syncStates.items():
        state["wipeStatus"] = wipeStatus.pop(device, 0)
    for device, status in wipeStatus.items():
        syncStates[device] = {"wipeStatus": status}
    with Service("redis", errors=Service.SUPPRESS_INOP) as redis:
        for device, state in syncStates.items():
            state["lastconnecttime"] = retrieve_lastconnecttime(redis, user.username, device, state.get("lastupdatetime"))
    return syncStates


def _mkDate(cli, timestamp):
    if not timestamp:
        return ""
    from datetime import datetime
    now = datetime.now()
    date = datetime.fromtimestamp(timestamp)
    datestr = date.strftime("%H:%M")
    if date.day-now.day or date.month-now.month or date.year-now.year:
        datestr += cli.col(date.strftime(" %d.%m.%Y"), attrs=["dark"])
    return datestr


def _mkWipeStatus(cli, status):
    return cli.col(_deviceStatus.get(status, f"<{status}>"), **_deviceStatusStyle.get(status, {"color": "magenta"}))


def cliUserDevicesList(args):
    cli = args._cli
    ret, user = _getUser(args, requireMailbox=True)
    if ret:
        return ret

    data = _cliUserDevicesGetDevices(args, user)
    devices = [(cli.col(device, attrs=["bold"]), state.get("devicefriendlyname", ""), state.get("useragent", ""),
                str(state.get("asversion", "")), _mkDate(cli, state.get("lastconnecttime")),
                _mkWipeStatus(cli, state["wipeStatus"]))
               for device, state in data.items()]
    devices = sorted(devices, key=lambda entry: entry[0])
    Table(devices, ("ID", "Device", "Agent", "Version", "Last connect", "Status"), empty=cli.col("(No devices)", attrs=["dark"]))\
        .print(cli)


def cliUserDevicesShow(args):
    cli = args._cli
    ret, user = _getUser(args, requireMailbox=True)
    if ret:
        return ret

    tf = {"firstsynctime": _mkDate, "lastupdatetime": _mkDate, "lastconnecttime": _mkDate, "wipeStatus": _mkWipeStatus}
    keys = ("devicetype", "devicemodel", "deviceos", "useragent", "devicemobileoperator", "deviceimei", "deviceoslanguage",
            "deviceuser", "firstsynctime", "lastupdatetime", "lastconnecttime", "asversion", "announcedasversion",
            "hierarchyuuid", "wipeStatus")
    devices = _cliUserDevicesGetDevices(args, user)
    for device, state in devices.items():
        cli.print(cli.col(device, attrs=["bold"]))
        data = [("  "+key+":", str(tf.get(key, lambda _, x: x)(cli, state[key]))) for key in keys if key in state]
        Table(data).print(cli)


def cliUserDevicesRemoveResync(args):
    from orm.users import DB, UserDevices
    from services import Service
    from tools.config import Config

    cli = args._cli
    ret, user = _getUser(args, requireMailbox=True)
    if ret:
        return ret

    with Service("exmdb") as exmdb:
        client = exmdb.user(user)
        if args.action == "remove" and not args.device:
            client.removeSyncStates(Config["sync"]["syncStateFolder"])
            cli.print(cli.col("Removed all devices", "green"))
            UserDevices.query.filter(UserDevices.userID == user.ID).delete()
            DB.session.commit()
            return

        devices = args.device or [device for device, state in _cliUserDevicesGetDevices(args, user).items()
                                  if "deviceid" in state]
        for device in devices:
            if args.action == "remove":
                client.removeDevice(Config["sync"]["syncStateFolder"], device)
                UserDevices.query.filter(UserDevices.userID == user.ID, UserDevices.deviceID == device).delete()
                cli.print(f"Removed {device}")
            else:
                client.resyncDevice(Config["sync"]["syncStateFolder"], device, user.ID)
                cli.print(f"Removed states of {device}")


def cliUserDeviceWipe(args):
    from datetime import datetime
    from orm.users import DB, UserDevices, UserDeviceHistory

    cli = args._cli
    ret, user = _getUser(args, requireMailbox=True)
    if ret:
        return ret

    device = UserDevices.query.filter(UserDevices.userID == user.ID, UserDevices.deviceID == args.device).first()
    currentStatus = device.status if device is not None else 0
    requestedStatus = 1 if args.mode == "cancel" else 16 if args.mode == "account" else 2
    if requestedStatus == currentStatus:
        cli.print("Nothing to do.")
        return
    if currentStatus in (4, 8, 32, 64):
        cli.print("Cannot modify while wipe already in progress")
        return 10
    if device is None:
        device = UserDevices(dict(userID=user.ID, deviceID=args.device, status=requestedStatus))
        DB.session.add(device)
        DB.session.flush()
    else:
        device.status = requestedStatus
    DB.session.add(UserDeviceHistory(dict(userDeviceID=device.ID, time=datetime.utcnow(), remoteIP="[CLI]",
                                          status=device.status)))
    DB.session.commit()
    if requestedStatus == 1:
        cli.print(cli.col(f"Cancelled wipe on {args.device}"))
    else:
        cli.print(cli.col(f"Requested {args.mode} wipe for device {args.device}", on_color="on_red", attrs=["bold"]))


def cliUserModify(args):
    cli = args._cli
    cli.require("DB")
    from orm import DB
    from orm.users import Aliases, Altnames
    ret, user = _getUser(args)
    if ret:
        return ret
    data = _splitData(args.__dict__)
    if data["noldap"]:
        user.externID = None
    if data["delchat"]:
        from services import Service
        with Service("chat") as chat:
            chat.deleteUser(user)
    properties = data["attributes"]["properties"] = {}
    for pv in data["props"]:
        try:
            prop, val = pv.split("=", 1)
            properties[prop] = val
        except (KeyError, ValueError) as err:
            cli.print(cli.col("Failed to set property '{}': {}".format(prop, err.args[0]), "yellow"))
    for prop in data["props_rm"]:
        properties[prop] = None
    try:
        user.fromdict(data["attributes"], syncStore="always")
        if data["aliases"]:
            existing = {a.aliasname for a in user.aliases}
            newAliases = [Aliases(alias, user) for alias in data["aliases"] if alias not in existing]
            DB.session.add_all(newAliases)
        if data["aliases_rm"]:
            user.aliases = [alias for alias in user.aliases if alias.aliasname not in data["aliases_rm"]]
        if data["altnames"]:
            existing = {a.altname for a in user.altnames}
            newAltnames = [Altnames(altname, user) for altname in data["altnames"] if altname["altname"] not in existing]
            DB.session.add_all(newAltnames)
        if data["altnames_rm"]:
            user.altnames = [altname for altname in user.altnames if altname.altname not in data["altnames_rm"]]
    except ValueError as err:
        cli.print(cli.col("Failed to update user: "+err.args[0], "red"))
        return 1
    DB.session.commit()
    _dumpUser(cli, user)


def cliUserQuery(args):
    def mkUsername(value):
        if "@" not in value:
            return cli.col(value, attrs=["bold"])
        username, domain = value.split("@", 1)
        return cli.col(username, attrs=["bold"])+"@"+domain

    cli = args._cli
    cli.require("DB")

    attrTf = {"username": mkUsername,
              "status": lambda v: cli.col(str(v)+"/", attrs=["dark"])+_mkStatus(cli, v)}\
        if args.format == "pretty" else {}

    from orm.users import Users
    args.attributes = args.attributes or ("ID", "username", "status")
    query = _mkUserQuery(args)
    query = Users.optimize_query(query, args.attributes)
    users = [user.todict(args.attributes) for user in query]
    data = [[attrTf.get(attr, lambda x: x)(user.get(attr)) for attr in args.attributes] for user in users]
    header = None if len(args.attributes) <= 1 and args.format == "pretty" else args.attributes
    table = Table(data, header, args.separator, cli.col("(no results)", attrs=["dark"]))
    table.dump(cli, args.format)


def cliUserManageFileList(args):
    cli = args._cli
    cli.require("DB")

    if "userspec" not in args:
        raise InvalidUseError()
    if "action" not in args:
        args.action = "list"

    filename = args.filename+".txt"
    ret, usernames, user = _usernamesFromFile(filename, args)
    if ret:
        return ret

    if args.action == "add":
        for username in args.username:
            if username in usernames:
                cli.print(cli.col(f"'{username}' already has {args.dispname} permission", "yellow"))
            else:
                usernames.append(username)
        ret = _usernamesToFile(filename, usernames, args)
    elif args.action == "clear":
        usernames = ()
        ret = _usernamesToFile(filename, usernames, args)
    elif args.action == "remove":
        args.force = True
        for username in args.username:
            if username not in usernames:
                cli.print(cli.col(f"'{username}' does not have {args.dispname} permission", "yellow"))
            else:
                usernames.remove(username)
        ret = _usernamesToFile(filename, usernames, args)

    if ret:
        return ret
    if not usernames:
        cli.print(cli.col(f"No users have {args.dispname} permission for '{user.username}'", attrs=["dark"]))
    else:
        cli.print("User{} with {} permission for '{}':".format("" if len(usernames) == 1 else "s", args.dispname,
                                                               cli.col(user.username, attrs=["bold"])))
        for username in usernames:
            cli.print("  "+username)


def _cliUserspecCompleter(prefix, **kwargs):
    from orm.users import Users
    return (user.username for user in Users.query.filter(Users.username.ilike(prefix+"%"))
                                                 .with_entities(Users.username).all())


def _cliParseStatus(value):
    try:
        return int(value)
    except Exception:
        pass
    from orm.users import Users
    value = value.lower()
    if value == "normal":
        return Users.NORMAL
    if value == "suspended":
        return Users.SUSPENDED
    if value == "deleted":
        return Users.DELETED
    if value == "shared":
        return Users.SHARED
    if value == "contact":
        return Users.CONTACT
    raise ValueError("Unknown user status '{}'".format(value))


def _cliAddUserAttributes(parser: ArgumentParser):
    def getBool(val):
        if not val.isdigit() and val.lower() not in ("yes", "no", "true", "false", "y", "n"):
            raise ValueError("'{}' cannot be interpreted as boolean.".format(val))
        return bool(int(val)) if val.isdigit() else val in ("yes", "true", "y")

    def optBool(val):
        if not val.isdigit() and val.lower() not in ("yes", "no", "true", "false", "y", "n"):
            return val
        return bool(int(val)) if val.isdigit() else val in ("yes", "true", "y")

    def assignment(arg):
        if "=" not in arg:
            raise ValueError("'{}' is not an assignment".format(arg))
        return arg

    def proptagAssignCompleter(*args, **kwargs):
        return proptagCompleter(*args, **kwargs, addSuffix="=")

    parser.add_argument("--changePassword", type=getBool, metavar="<bool>", help="Whether the user can change the password")
    parser.add_argument("--chat", type=optBool, metavar="<bool>", help="Whether to create a chat user")
    parser.add_argument("--chatAdmin", type=getBool, metavar="<bool>", help="Whether the user has chat admin privileges")
    parser.add_argument("--domain", metavar="DOMAINSPEC", help="Domain name or ID to create the user for")
    parser.add_argument("--homeserver", type=int, metavar="ID", help="ID of the home server or 0 for local user")
    parser.add_argument("--lang", help="User store language")
    parser.add_argument("--ldapID", help="Identifier of the LDAP object linked to the user")
    parser.add_argument("--pop3-imap", type=getBool, metavar="<bool>", help="Whether the user has the POP3/IMAP privilege")
    parser.add_argument("--privArchive", type=getBool, metavar="<bool>", help="Whether the user has the archiving privilege")
    parser.add_argument("--privChat", type=getBool, metavar="<bool>", help="Whether the user has the chat privilege")
    parser.add_argument("--privFiles", type=getBool, metavar="<bool>", help="Whether the user has the files privilege")
    parser.add_argument("--privVideo", type=getBool, metavar="<bool>", help="Whether the user has the video privilege")
    parser.add_argument("--privWeb", type=getBool, metavar="<bool>", help="Whether the user has the web privilege")
    parser.add_argument("--privDav", type=getBool, metavar="<bool>", help="Whether the user has the DAV privilege")
    parser.add_argument("--privEas", type=getBool, metavar="<bool>", help="Whether the user has the EAS privilege")
    parser.add_argument("--public-address", type=getBool, metavar="<bool>",
                        help="Whether the user has the public address privilege")
    parser.add_argument("--smtp", type=getBool, metavar="<bool>", help="Whether the user has the SMTP privilege")
    parser.add_argument("--status", type=_cliParseStatus, help="User address status")

    parser.add_argument("--alias", action="append", help="Add alias")
    parser.add_argument("--altname", action="append", help="Add alternative name")
    parser.add_argument("--property", action="append", type=assignment, metavar="propspec=value",
                        help="Set property defined by propspec to value").completer = proptagAssignCompleter
    parser.add_argument("--storeprop", action="append", type=assignment, metavar="propspec=value",
                        help="Set store property defined by propspec to value").completer = proptagAssignCompleter


def _setupCliUser(subp: ArgumentParser):
    class AttrChoice:
        def __contains__(self, value):
            return value == [] or value in _userAttributes

        def __getitem__(self, i):
            return _userAttributes[i]

        def __len__(self):
            return len(_userAttributes)

    def deviceParser(parent, action, handler, **kwargs):
        sub = parent.add_parser(action, **kwargs)
        sub.set_defaults(action=action, _handle=handler)
        sub.add_argument("device", nargs="*", help="Device ID")
        return sub

    def userListFileParser(parent, name, dispname, handler):
        ulf = sub.add_parser(name, help=f"Manage {dispname} permission")
        ulf.set_defaults(_handle=handler, filename=name, dispname=dispname)
        ulf.add_argument("userspec", help="User ID or name prefix").completer = _cliUserspecCompleter
        ulfActions = ulf.add_subparsers()
        ulfAdd = ulfActions.add_parser("add", help=f"Grant {dispname} permissions to user")
        ulfAdd.set_defaults(action="add")
        ulfAdd.add_argument("--force", action="store_true", help="Override e-mail user check")
        ulfAdd.add_argument("username", nargs="+", help="E-Mail address of the user").completer = _cliUserspecCompleter
        ulfList = ulfActions.add_parser("clear", help=f"Clear {dispname} list")
        ulfList.set_defaults(action="clear")
        ulfList = ulfActions.add_parser("list", help=f"List users with {dispname} permission")
        ulfList.set_defaults(action="list")
        ulfRemove = ulfActions.add_parser("remove", help=f"Revoke {dispname} permission from user")
        ulfRemove.set_defaults(action="remove")
        ulfRemove.add_argument("username", nargs="+", help="E-Mail address of the user").completer = _cliUserspecCompleter

    Cli.parser_stub(subp)
    sub = subp.add_subparsers()
    create = sub.add_parser("create",  help="Create user")
    create.add_argument("username", help="E-Mail address of the user")
    create.add_argument("--no-defaults", action="store_true", help="Do not apply configured default values")
    create.add_argument("--no-maildir", action="store_true", help="Do not create a mailbox for that user")
    create.set_defaults(_handle=cliUserCreate)
    _cliAddUserAttributes(create)
    userListFileParser(sub, "delegates", "delegate", cliUserManageFileList)
    delete = sub.add_parser("delete", help="Delete user")
    delete.set_defaults(_handle=cliUserDelete)
    delete.add_argument("userspec", help="User ID or name").completer = _cliUserspecCompleter
    delete.add_argument("-c", "--keep-chat", action="store_true", help="Do not permanently delete the chat user")
    delete.add_argument("-k", "--keep-files", action="store_true", help="Do not delete files on disk")
    delete.add_argument("-y", "--yes", action="store_true", help="Do not ask for confirmation")
    device = sub.add_parser("devices", help="User device management")
    device.add_argument("userspec", help="User ID or name").completer = _cliUserspecCompleter
    deviceActions = device.add_subparsers()
    deviceParser(deviceActions, "list", cliUserDevicesList, help="List devices of a user")
    deviceParser(deviceActions, "show", cliUserDevicesShow, help="Show detailed information about a device")
    deviceParser(deviceActions, "remove", cliUserDevicesRemoveResync, help="Show detailed information about a device")
    deviceParser(deviceActions, "resync", cliUserDevicesRemoveResync, help="Show detailed information about a device")
    deviceWipe = deviceActions.add_parser("wipe")
    deviceWipe.set_defaults(_handle=cliUserDeviceWipe)
    deviceWipe.add_argument("device", help="Device ID")
    deviceWipe.add_argument("--mode", default="normal", choices=("account", "cancel", "normal"), help="Set device wipe mode")
    list = sub.add_parser("list", help="List users")
    list.set_defaults(_handle=cliUserList)
    list.add_argument("userspec", nargs="?", help="User ID or name prefix")
    list.add_argument("-f", "--filter", action="append", help="Filter by attribute, e.g. -f ID=42")
    list.add_argument("-s", "--sort", action="append", help="Sort by attribute, e.g. -s username,desc")
    login = sub.add_parser("login", help="Test user login")
    login.set_defaults(_handle=cliUserLogin)
    login.add_argument("username", help="E-Mail address of the user").completer = _cliUserspecCompleter
    login.add_argument("--nopass", action="store_true", help="Skip password check")
    login.add_argument("--password", help="User password to check")
    login.add_argument("--token", action="store_true", help="Generate access and CSFR token on successful login")
    modify = sub.add_parser("modify",  help="Modify user")
    modify.set_defaults(_handle=cliUserModify)
    modify.add_argument("userspec", help="User ID or name prefix").completer = _cliUserspecCompleter
    _cliAddUserAttributes(modify)
    modify.add_argument("--delete-chat-user", action="store_true", help="Permanently delete chat user")
    modify.add_argument("--no-ldap", action="store_true", help="Unlink user from ldap object")
    modify.add_argument("--remove-alias", metavar="ALIAS", action="append", help="Remove alias")
    modify.add_argument("--remove-altname", metavar="ALTNAME", action="append", help="Remove alternative name")
    modify.add_argument("--remove-property", action="append", metavar="propspec", help="Remove property from user")
    modify.add_argument("--remove-storeprop", action="append", metavar="propspec", help="Remove property from user's store")
    modify.add_argument("--username", help="Rename user")
    query = sub.add_parser("query", help="Query specific user attributes")
    query.set_defaults(_handle=cliUserQuery)
    query.add_argument("-f", "--filter", action="append", help="Filter by attribute, e.g. -f ID=42")
    query.add_argument("--format", choices=Table.FORMATS, help="Set output format",
                       metavar="FORMAT", default="pretty")
    query.add_argument("--separator", help="Set column separator")
    query.add_argument("-s", "--sort", action="append", help="Sort by attribute, e.g. -s username,desc")
    query.add_argument("attributes", nargs="*", choices=AttrChoice(), help="Attributes to query", metavar="ATTRIBUTE")
    userListFileParser(sub, "sendas", "send-as", cliUserManageFileList)
    show = sub.add_parser("show", help="Show detailed information about user")
    show.set_defaults(_handle=cliUserShow)
    show.add_argument("userspec", help="User ID or name").completer = _cliUserspecCompleter
    show.add_argument("-f", "--filter", action="append", help="Filter by attribute, e.g. -f ID=42")
    show.add_argument("-s", "--sort", action="append", help="Sort by attribute, e.g. -s username,desc")


@Cli.command("user", _setupCliUser, help="User management")
def cliUserStub(args):
    raise InvalidUseError()
