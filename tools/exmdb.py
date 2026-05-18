from tools.constants import _perms, _permsAll


def getClient(username, exmdb):
    from orm.users import Users
    user = Users.query.filter(Users.username == username).first()
    if user is None:
        return 1, None
    client = exmdb.user(user)
    client.accountID = user.ID
    return 0, client


def exmdbFolderPermissionString(permission):
    permstring = "all" if permission & _permsAll == _permsAll else\
                 "none" if permission == 0 else\
                 ", ".join(name for name, val in _perms.items() if permission & val)
    return permstring


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