# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2022 grommunio GmbH

from . import Cli, InvalidUseError, ArgumentParser
from .common import proptagCompleter, Table

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
        client = exmdb.user(user)
        client.accountID = user.ID
        return 0, client
    from orm.domains import Domains
    domain = Domains.query.filter(Domains.domainname == args.target).first()
    if domain is None:
        cli.print(cli.col("No domain matching '{}'.".format(args.target), "red"))
        return 1, None
    client = exmdb.domain(domain)
    client.accountID = domain.ID
    return 0, client


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

    def _toDict(self, recursive=True):
        me = dict(ID=self.ID, parentID=self.parentID, name=self.name)
        if recursive:
            me["subfolders"] = [sf._toDict(True) for sf in self.subfolders]
        return me

    def _collectSubfolders(self):
        sfs = list(self.subfolders)
        for sf in self.subfolders:
            sfs += sf._collectSubfolders()
        return sfs

    def _print_json(self, flat=False):
        import json
        me = self._toDict(not flat)
        if flat:
            me["subfolders"] = [sf._toDict(False) for sf in self._collectSubfolders()]
        return json.dumps(me, separators=(",", ":"))

    def _print_pretty(self, cli, level=-1, pref=""):
        content = "{} ({})\n".format(cli.col(self.name, attrs=["bold"]), self.idstr)
        if self.subfolders:
            for sub in self.subfolders[:-1]:
                content += pref+self.T+sub._print_pretty(cli, level+1, pref+self.I)
            content += pref+self.L+self.subfolders[-1]._print_pretty(cli, level+1, pref+"  ")
        return content if level >= 0 else content[:-1]

    def print(self, cli, format="pretty"):
        if format in ("json-flat", "json-tree"):
            return self._print_json(format == "json-flat")
        return self._print_pretty(cli)

    def tabledata(self):
        sfs = self._collectSubfolders()
        return [(self.ID, self.parentID, self.name)]+[(sf.ID, sf.parentID, sf.name) for sf in sfs]


def cliExmdbFolderCreate(args):
    cli = args._cli
    cli.require("DB")
    from services import Service
    from tools.constants import PublicFIDs, PrivateFIDs
    from tools.rop import makeEidEx
    parentID = args.ID or (PrivateFIDs.IPMSUBTREE if _isPrivate(args) else PublicFIDs.IPMSUBTREE)
    parentID = makeEidEx(1, parentID)
    with Service("exmdb") as exmdb:
        ret, client = _getClient(args, exmdb)
        if ret:
            return ret
        folderID = client.createFolder(client.accountID, args.name, args.type, args.comment, parentID)
        if folderID == 0:
            cli.print(cli.col("Folder creation failed", "red"))
            return 2
        folder = exmdb.Folder(client.getFolderProperties(0, folderID, client.defaultFolderProps))
        cli.print(_FolderNode(folder).print(cli))


def cliExmdbFolderDelete(args):
    cli = args._cli
    cli.require("DB")
    from services import Service
    from tools.constants import PublicFIDs, PrivateFIDs
    from tools.rop import makeEidEx, gcToValue
    with Service("exmdb") as exmdb:
        ret, client = _getClient(args, exmdb)
        if ret:
            return ret
        try:
            fids = [makeEidEx(1, int(args.folderspec, 0))]
        except ValueError:
            rootID = makeEidEx(1, PrivateFIDs.ROOT if _isPrivate(args) else PublicFIDs.ROOT)
            folders = exmdb.FolderList(client.findFolder(args.folderspec, rootID)).folders
            fids = [folder.folderId for folder in folders]
        if len(fids) == 0:
            cli.print(cli.col("No folders found", "red"))
            return 1
        if len(fids) > 1 and not args.all:
            cli.print(cli.col(f"'{args.folderspec}' is ambiguous. Use -a to delete all or specify the folder ID.", "red"))
            return 2
        for fid in fids:
            try:
                success = client.deleteFolder(fid, args.clear)
                if success:
                    cli.print("Deleted folder 0x{:x}".format(gcToValue(fid)))
                else:
                    cli.print(cli.col("Could not delete folder 0x{:x}".format(gcToValue(fid)), "yellow"))
            except exmdb.ExmdbError:
                cli.print(cli.col("Failed to delete folder 0x{:x}".format(gcToValue(fid)), "yellow"))


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
        folder = _FolderNode(root, subfolders)
        if args.format in ("csv", "table"):
            from .common import Table
            Table(folder.tabledata(), header=("ID", "parentID", "name"), colsep="," if args.format == "csv" else "  ")\
                .dump(cli, args.format)
        else:
            cli.print(folder.print(cli, args.format))


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
        if Users.query.filter(Users.username == args.username).count() == 0 and args.username not in ('default', 'anonymous'):
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
        mode = client.REMOVE if args.revoke else client.ADD
        # We need to remove prior permissions for those users
        if args.username in ('default', 'anonymous'):
            for fid in fids:
                # Anonymous is '' in exmdb, so we have to rewrite it
                if args.username == 'anonymous':
                    args.username = ''
                client.setFolderMember(fid, args.username, _permsAll, client.REMOVE)
        # Anonymous is '' in exmdb, so we have to rewrite it
        if args.username == 'anonymous':
            args.username = ''
        perms = [client.setFolderMember(fid, args.username, perms, mode) for fid in fids]
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
        try:
            Table([(member.name, _cliExmdbFolderPermissionPrint(cli, member.rights))
                   for member in members if (not args.username or member.mail in args.username)],
                  empty=cli.col("(no entries)", attrs=["dark"])).print(cli)
        except Exception as exc:
            import traceback
            traceback.print_exc()


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
            res = Table.Styled("[{} byte{}]".format(len(pv.val), "" if len(pv.val) == 1 else "s"), attrs=["dark"]), ""
        elif pv.type == PropTypes.FILETIME:
            timestring = datetime.fromtimestamp(nxTime(pv.val)).strftime("%Y-%m-%d %H:%M:%S")
            res = pv.val, cli.col(timestring, attrs=["dark"])
        elif pv.type in (PropTypes.STRING, PropTypes.WSTRING):
            res = pv.val, cli.col(printSize(len(pv.val)), attrs=["dark"])
        elif pv.type == PropTypes.BINARY_ARRAY:
            res = Table.Styled("[{} blob{}]".format(len(pv.val), "" if len(pv.val) == 1 else "s"), attrs=["dark"]), ""
        elif PropTypes.ismv(pv.type):
            res = [str(val) for val in pv.val], ""
        else:
            res = pv.val, cli.col(printSize(pv.val*PropTags.sizeFactor.get(pv.tag, 1)), attrs=["dark"])\
                if pv.tag in PropTags.sizeTags else ""
        return res if pretty else (res[0],)

    cli = args._cli
    cli.require("DB")
    from tools.constants import PropTags, PropTypes
    from services import Service
    tags = [PropTags.deriveTag(tag) for tag in args.propspec]
    pretty = args.format == "pretty"
    header = ("tag", "value", "") if pretty else ("tag", "value")
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
        data = [(PropTags.lookup(prop.tag, hex(prop.tag)).lower(), *printVal(prop)) for prop in props]
        Table(data, header, args.separator, cli.col("(No properties)", attrs=["dark"])).dump(cli, args.format)


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
    Cli.parser_stub(folder)
    foldersub = folder.add_subparsers()
    create = foldersub.add_parser("create", help="Create folder")
    create.set_defaults(_handle=cliExmdbFolderCreate)
    create.add_argument("--comment", default="", help="Folder comment")
    create.add_argument("-t", "--type", default="IPF.Note", help="Folder type (default: IPF.Note)")
    create.add_argument("name", help="Name of the folder to create")
    create.add_argument("ID", nargs="?", type=xint, default=0, help="Parent folder ID")
    delete = foldersub.add_parser("delete", help="Delete folder")
    delete.set_defaults(_handle=cliExmdbFolderDelete)
    delete.add_argument("-a", "--all", action="store_true", help="Delete all matching folders")
    delete.add_argument("--clear", action="store_true", help="Empty folder before deleting")
    delete.add_argument("folderspec", help="ID or name of folder")
    find = foldersub.add_parser("find", help="Find folder by name")
    find.set_defaults(_handle=cliExmdbFolderFind)
    find.add_argument("-x", "--exact", action="store_true", help="Only report exact matches instead of substring matches")
    find.add_argument("name", help="Name of the folder to find")
    find.add_argument("ID", nargs="?", type=xint, help="ID of the folder to search in")
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
    list.add_argument("--format", nargs="?", default="pretty", help="Output format", metavar="FORMAT",
                      choices=("csv", "json-flat", "json-tree", "pretty", "table"))
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
    Cli.parser_stub(store)
    storesub = store.add_subparsers()
    get = storesub.add_parser("get", help="Query store properties")
    get.set_defaults(_handle=cliExmdbStoreGetDelete, command="get")
    get.add_argument("--format", choices=Table.FORMATS, help="Set output format",
                     metavar="FORMAT", default="pretty")
    get.add_argument("--separator", help="Set column separator")
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
