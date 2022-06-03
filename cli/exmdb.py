# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2022 grommunio GmbH

from . import Cli, InvalidUseError, ArgumentParser
from .common import proptagCompleter

_perms = {
    "readany": 0x1,
    "create": 0x2,
    "sendas": 0x4,
    "editowned": 0x8,
    "deleteowned": 0x10,
    "editany": 0x20,
    "deleteany": 0x40,
    "createsubfolder": 0x80,
    "folderowner": 0x100,
    "foldercontact": 0x200,
    "foldervisible": 0x400,
    "freebusysimple": 0x800,
    "freebusydetailed": 0x1000,
    "storeowner": 0x2000}
_permsAll = 0x27ff


def _getClient(args, exmdb):
    cli = args._cli
    if "@" in args.target:
        from orm.users import Users
        user = Users.query.filter(Users.username == args.target).first()
        if user is None:
            cli.print(cli.col("No user matching '{}'.".format(args.target), "red"))
            return 1, None
        return 0, exmdb.user(user)
    from orm.domains import Domains
    domain = Domains.query.filter(Domains.domainname == args.target).first()
    if domain is None:
        cli.print(cli.col("No domain matching '{}'.".format(args.target), "red"))
        return 1, None
    return 0, exmdb.domain(domain)


def _isPrivate(args):
    return "@" in args.target


class _FolderNode():
    I = chr(0x2502)+" "
    L = chr(0x2514)+chr(0x2500)
    T = chr(0x251c)+chr(0x2500)

    def __init__(self, folder, subfolders=[]):
        from tools.rop import gcToValue
        self.ID = gcToValue(folder.folderId)
        self.parentID = gcToValue(folder.parentId)
        self.name = folder.displayName
        self.subfolders = []
        if subfolders:
            self._buildTree(subfolders)

    def _buildTree(self, subfolders):
        subfolders = [f if isinstance(f, _FolderNode) else _FolderNode(f) for f in subfolders]
        idmap = {sub.ID: sub for sub in subfolders}
        idmap[self.ID] = self
        for sub in subfolders:
            if sub.parentID in idmap:
                idmap[sub.parentID].subfolders.append(sub)

    @property
    def idstr(self):
        return hex(self.ID)

    def print(self, cli, level=-1, pref=""):
        content = "{} ({})\n".format(cli.col(self.name, attrs=["bold"]), self.idstr)
        if self.subfolders:
            for sub in self.subfolders[:-1]:
                content += pref+self.T+sub.print(cli, level+1, pref+self.I)
            content += pref+self.L+self.subfolders[-1].print(cli, level+1, pref+"  ")
        return content if level >= 0 else content[:-1]


def cliExmdbFolderFind(args):
    cli = args._cli
    cli.require("DB")
    from services import Service
    from tools.constants import PublicFIDs, PrivateFIDs
    from tools.rop import makeEidEx
    fid = args.ID or (PrivateFIDs.IPMSUBTREE if _isPrivate(args) else PublicFIDs.IPMSUBTREE)
    fid = makeEidEx(1, fid)
    with Service("exmdb") as exmdb:
        ret, client = _getClient(args, exmdb)
        if ret:
            return ret
        fuzzyLevel = 0 if args.exact else 65537  # 65537 = SUBSTRING | IGNORECASE
        folders = exmdb.FolderList(client.findFolder(args.name, fid, fuzzyLevel=fuzzyLevel)).folders
        for folder in folders:
            cli.print(_FolderNode(folder).print(cli))
        cli.print(cli.col("({} result{})".format(len(folders), "" if len(folders) == 1 else "s"), attrs=["dark"]))


def cliExmdbFolderList(args):
    cli = args._cli
    cli.require("DB")
    from services import Service
    from tools.constants import PublicFIDs, PrivateFIDs
    from tools.rop import makeEidEx
    fid = args.ID or (PrivateFIDs.IPMSUBTREE if _isPrivate(args) else PublicFIDs.IPMSUBTREE)
    fid = makeEidEx(1, fid)
    with Service("exmdb") as exmdb:
        ret, client = _getClient(args, exmdb)
        if ret:
            return ret
        root = exmdb.Folder(client.getFolderProperties(0, fid))
        subfolders = exmdb.FolderList(client.listFolders(fid, args.recursive)).folders
        cli.print(_FolderNode(root, subfolders).print(cli))


def _cliExmdbFolderPermissionPrint(cli, permission):
    permstring = "all" if permission & _permsAll == _permsAll else\
                 "none" if permission == 0 else\
                 ",".join(name for name, val in _perms.items() if permission & val)
    return "0x{:04x} ({})".format(permission, cli.col(permstring, attrs=["dark"]))


def cliExmdbFolderPermissionsModify(args):
    cli = args._cli
    cli.require("DB")
    from .common import Table
    from functools import reduce
    from orm.users import Users
    from services import Service
    from tools.rop import makeEidEx
    if not args.revoke:
        if Users.query.filter(Users.username == args.username).count() == 0:
            cli.print(cli.col("Target user '{}' does not exist".format(args.username), "yellow" if args.force else "red"))
            if not args.force:
                return 100
    fid = makeEidEx(1, args.ID)
    perms = reduce(lambda x, y: x | y, args.permission, 0) or _permsAll
    with Service("exmdb") as exmdb:
        ret, client = _getClient(args, exmdb)
        if ret:
            return ret
        fids = (fid,)
        folders = [exmdb.Folder(client.getFolderProperties(0, fid))]
        if args.recursive:
            folders += exmdb.FolderList(client.listFolders(fid, True)).folders
            fids += tuple(folder.folderId for folder in folders)
        perms = [client.setFolderMember(fid, args.username, perms, args.revoke) for fid in fids]
        cli.print("New permissions for user '{}':".format(cli.col(args.username, attrs=["bold"])))
        Table([(_FolderNode(folder).print(cli), _cliExmdbFolderPermissionPrint(cli, perm))
               for folder, perm in zip(folders, perms)]).print(cli)


def cliExmdbFolderPermissionsShow(args):
    cli = args._cli
    cli.require("DB")
    from .common import Table
    from services import Service
    from tools.rop import makeEidEx
    fid = makeEidEx(1, args.ID)
    with Service("exmdb") as exmdb:
        ret, client = _getClient(args, exmdb)
        if ret:
            return ret
        members = exmdb.FolderMemberList(client.getFolderMemberList(fid)).members
        Table([(member.mail, _cliExmdbFolderPermissionPrint(cli, member.rights))
               for member in members if not member.special and (not args.username or member.mail in args.username)],
              empty=cli.col("(no entries)", attrs=["dark"])).print(cli)


def cliExmdbStoreGetDelete(args):
    def printSize(value):
        suffix = ("B", "kiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB", "YiB")
        index = 0
        prec = 0
        while value > 1000 and index < len(suffix)-1:
            value /= 1024
            index += 1
            prec = 0 if value >= 100 else 1 if value >= 10 else 2 if value >= 1 else 3
        return "{:.{}f} {}".format(value, prec, suffix[index])

    def printVal(pv):
        from datetime import datetime
        from tools.rop import nxTime
        if pv.type == PropTypes.BINARY:
            return cli.col("[{} byte{}]".format(len(pv.val), "" if len(pv.val) == 1 else "s"), attrs="dark"), ""
        elif pv.type == PropTypes.FILETIME:
            timestring = datetime.fromtimestamp(nxTime(pv.val)).strftime("%Y-%m-%d %H:%M:%S")
            return pv.val, cli.col(timestring, attrs=["dark"])
        elif pv.type == PropTypes.BINARY_ARRAY:
            return cli.col("[{} value{}]".format(len(pv.val), "" if len(pv.val) == 1 else "s"), attrs="dark"), ""
        elif PropTypes.ismv(pv.type):
            return "["+", ".join(repr(pv.val))+"]", ""
        return pv.val, cli.col(printSize(pv.val), attrs=["dark"]) if pv.tag in PropTags.sizeTags else ""

    cli = args._cli
    cli.require("DB")
    from .common import Table
    from tools.constants import PropTags, PropTypes
    from services import Service
    tags = [PropTags.deriveTag(tag) for tag in args.propspec]
    with Service("exmdb") as exmdb:
        ret, client = _getClient(args, exmdb)
        if ret:
            return ret
        if not tags:
            tags = client.getAllStoreProperties()
        if args.command == "delete":
            client.removeStoreProperties(tags)
            return
        props = client.getStoreProperties(0, tags)
        Table([(PropTags.lookup(prop.tag, hex(prop.tag)).lower(), *printVal(prop)) for prop in props],
              empty=cli.col("(No properties)", attrs=["dark"])).print(cli)


def cliExmdbStoreSet(args):
    cli = args._cli
    cli.require("DB")
    from tools.constants import PropTags
    from services import Service
    with Service("exmdb") as exmdb:
        props = [exmdb.TaggedPropval(*PropTags.normalize(*prop.split("=", 1))) for prop in args.propspec if "=" in prop]
        ret, client = _getClient(args, exmdb)
        if ret:
            return ret
        client.setStoreProperties(0, props)


def _cliTargetCompleter(prefix, **kwargs):
    from orm.users import Users
    from orm.domains import Domains
    return [user.username for user in Users.query.filter(Users.username.ilike(prefix+"%"))
                                                 .with_entities(Users.username)] +\
           [domain.domainname for domain in Domains.query.filter(Domains.domainname.ilike(prefix+"%"))
                                                         .with_entities(Domains.domainname)]


def _setupCliExmdb(subp: ArgumentParser):
    class PermChoices:
        _permChoices = ("all",)+tuple(_perms.keys())

        def __contains__(self, value):
            return True

        def __getitem__(self, i):
            return self._permChoices[i]

        def __len__(self):
            return len(self._permChoices)

    def xint(x):
        return int(x, 0)

    def perm(x):
        return _permsAll if x.lower() == "all" else _perms.get(x.lower()) or int(x, 0)

    subp.add_argument("target", help="User or domain name").completer = _cliTargetCompleter
    sub = subp.add_subparsers()

    folder = sub.add_parser("folder", help="Access folders")
    foldersub = folder.add_subparsers()
    find = foldersub.add_parser("find", help="Find folder by name")
    find.set_defaults(_handle=cliExmdbFolderFind)
    find.add_argument("-x", "--exact", action="store_true", help="Only report exact matches instead of substring matches")
    find.add_argument("name", help="Name of the folder to find")
    find.add_argument("ID", nargs="?", type=xint, help="Folder ID")
    grant = foldersub.add_parser("grant", help="Grant permissions to user")
    grant.set_defaults(_handle=cliExmdbFolderPermissionsModify, revoke=False)
    grant.add_argument("ID", type=xint, help="Folder ID")
    grant.add_argument("username", help="E-Mail address of the user to grant permissions to").completer = _cliTargetCompleter
    grant.add_argument("permission", nargs="+", type=perm, choices=PermChoices(), help="Permission name or value",
                       metavar="permission")
    grant.add_argument("-f", "--force", action="store_true", help="Add permissions even if user does not exist")
    grant.add_argument("-r", "--recursive", action="store_true", help="Apply to subfolders recursively")
    list = foldersub.add_parser("list", help="List subfolders")
    list.set_defaults(_handle=cliExmdbFolderList)
    list.add_argument("ID", nargs="?", type=xint, default=0, help="Folder ID")
    list.add_argument("-r", "--recursive", action="store_true", help="Recursively list subfolders")
    permissions = foldersub.add_parser("permissions")
    permissions.set_defaults(_handle=cliExmdbFolderPermissionsShow)
    permissions.add_argument("ID", type=xint, help="Folder ID")
    permissions.add_argument("username", nargs="*", help="E-Mail address of the user to show permissions of")\
               .completer = _cliTargetCompleter
    revoke = foldersub.add_parser("revoke", help="Grant permissions to user")
    revoke.set_defaults(_handle=cliExmdbFolderPermissionsModify, revoke=True)
    revoke.add_argument("ID", type=xint, help="Folder ID")
    revoke.add_argument("username", help="E-Mail address of the user to revoke permissions from")\
          .completer = _cliTargetCompleter
    revoke.add_argument("permission", nargs="*", type=perm, choices=PermChoices(), help="Permission name or value",
                        metavar="permission")
    revoke.add_argument("-r", "--recursive", action="store_true", help="Apply to subfolders recursively")

    store = sub.add_parser("store", help="Access store properties")
    storesub = store.add_subparsers()
    get = storesub.add_parser("get", help="Query store properties")
    get.set_defaults(_handle=cliExmdbStoreGetDelete, command="get")
    get.add_argument("propspec", nargs="*", help="Properties to query").completer = proptagCompleter
    delete = storesub.add_parser("delete", help="Delete store properties")
    delete.set_defaults(_handle=cliExmdbStoreGetDelete, command="delete")
    delete.add_argument("propspec", nargs="+", help="Properties to delete").completer = proptagCompleter
    set = storesub.add_parser("set", help="Set store properties")
    set.set_defaults(_handle=cliExmdbStoreSet)
    set.add_argument("propspec", nargs="+", help="Properties to query", metavar="propspec=value")\
       .completer = lambda *args, **kwargs: proptagCompleter(*args, **kwargs, addSuffix="=")


@Cli.command("exmdb", _setupCliExmdb, help="Private/public store management")
def cliExmdbStub(args):
    raise InvalidUseError()
