# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grommunio GmbH

from collections import defaultdict
from io import BytesIO


class AutoClean:
    """Simple context manager calling a function on exit."""

    def __init__(self, func, *args, **kwargs):
        """Initialize context manager

        Parameters
        ----------
        func : function
            Function to call on exit
        *args : tuple
            Arguments for func
        **kwargs : dict
            Keyword arguments for func
        """
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def __enter__(self):
        """Dummy method to allow use of `with` statement."""
        return self

    def __exit__(self, type, value, traceback):
        """Call function."""
        if self.func is not None:
            self.func(*self.args, **self.kwargs)

    def release(self):
        self.func = None


def createMapping(iterable, key, value=lambda x: x):
    """Convert list of elements to dictionary.

    Parameters
    ----------
    iterable : Iterable
        List of elements to map
    key : function
        Function returning the key given an element of `iterable`
    value : function
        Function returning the value given an element of `iterable`

    Returns
    -------
    mapping : dict
        A dictionary mapping each key to a list of values
    """
    mapping = dict()
    for item in iterable:
        k = key(item)
        if k in mapping:
            mapping[k].append(value(item))
        else:
            mapping[k] = value(item)
    return mapping


class GenericObject:
    def __init__(self, **attrs):
        for key, value in attrs.items():
            setattr(self, key, value)

    def __repr__(self):
        return "GenericObject({})".format(", ".join((key+"="+repr(getattr(self, key))
                                                     for key in dir(self) if not key.startswith("_"))))

    def __contains__(self, key):
        return key in dir(self)

    def __getitem__(self, item):
        return getattr(self, item)


def setDirectoryOwner(path, uid=None, gid=None):
    """Recursively set directory ownership of path.

    If neither uid nor gid is set, the function returns immediately without touching any files.

    Parameters
    ----------
    path : str
        Name of the target directory or file
    uid : str or in, optional
        uid of the new owner
    gid : str or int, optional
    """
    import os
    import shutil
    uid = None if uid == "" else uid
    gid = None if gid == "" else gid
    if uid is None and gid is None:
        return
    if os.path.isfile(path):
        shutil.chown(path, uid, gid)
    for path, subdirs, files in os.walk(path):
        shutil.chown(path, uid, gid)
        for entry in subdirs+files:
            shutil.chown(os.path.join(path, entry), uid, gid)


def setDirectoryPermission(path, mode):
    """Recursively set directory permissions of path.

    If mode is not set, the function returns immediately without touching any files.

    Parameters
    ----------
    path : str
        Name of the target directory or file
    uid : str or in, optional
        uid of the new owner
    gid : str or int, optional
    """
    import os
    if not mode:
        return
    if isinstance(mode, str):
        mode = int(mode, 0)
    if os.path.isfile(path):
        os.chmod(path, mode)
    dirmode = mode
    for field in range(0, 9, 3):
        dirmode |= 1<<field if mode & 7<<field else 0
    for path, subdirs, files in os.walk(path):
        os.chmod(path, dirmode)
        for entry in subdirs:
            os.chmod(os.path.join(path, entry), dirmode)
        for entry in files:
            os.chmod(os.path.join(path, entry), mode)

#######################################################
#
# Shamelessly stolen from `phpserialize` project and
# enhanced to support objects and classes out of the
# box.
#
#######################################################
def loadPSO(data, charset='utf-8', decode_strings=False,
         object_hook=None, array_hook=None):
    """Read a string from the open file object `fp` and interpret it as a
    data stream of PHP-serialized objects, reconstructing and returning
    the original object hierarchy.

    `fp` must provide a `read()` method that takes an integer argument.  Both
    method should return strings.  Thus `fp` can be a file object opened for
    reading, a `StringIO` object (`BytesIO` on Python 3), or any other custom
    object that meets this interface.

    `load` will read exactly one object from the stream.  See the docstring of
    the module for this chained behavior.

    If an object hook is given object-opcodes are supported in the serilization
    format.  The function is called with the class name and a dict of the
    class data members.  The data member names are in PHP format which is
    usually not what you want.  The `simple_object_hook` function can convert
    them to Python identifier names.

    If an `array_hook` is given that function is called with a list of pairs
    for all array items.  This can for example be set to
    `collections.OrderedDict` for an ordered, hashed dictionary.
    """
    fp = BytesIO(data)
    if array_hook is None:
        array_hook = dict

    def _expect(e):
        v = fp.read(len(e))
        if v != e:
            raise ValueError('failed expectation, expected %r got %r' % (e, v))

    def _read_until(delim):
        buf = []
        while 1:
            char = fp.read(1)
            if char == delim:
                break
            elif not char:
                raise ValueError('unexpected end of stream')
            buf.append(char)
        return b''.join(buf)

    def _load_array():
        items = int(_read_until(b':')) * 2
        _expect(b'{')
        result = []
        last_item = Ellipsis
        for idx in range(items):
            item = _unserialize()
            if last_item is Ellipsis:
                last_item = item
            else:
                result.append((last_item, item))
                last_item = Ellipsis
        _expect(b'}')
        return result

    def _load_class():
        unused = int(_read_until(b':'))
        _expect(b'{')
        data = _unserialize()
        _expect(b'}')
        return data

    def _unserialize():
        type_ = fp.read(1).lower()
        if type_ == b'n':
            _expect(b';')
            return None
        if type_ in b'idb':
            _expect(b':')
            data = _read_until(b';')
            if type_ == b'i':
                return int(data)
            if type_ == b'd':
                return float(data)
            return int(data) != 0
        if type_ == b's':
            _expect(b':')
            length = int(_read_until(b':'))
            _expect(b'"')
            data = fp.read(length)
            _expect(b'"')
            if decode_strings:
                data = data.decode(charset)
            _expect(b';')
            return data
        if type_ == b'a':
            _expect(b':')
            return array_hook(_load_array())
        if type_ in b'oc':
            _expect(b':')
            name_length = int(_read_until(b':'))
            _expect(b'"')
            name = fp.read(name_length)
            _expect(b'":')
            if decode_strings:
                name = name.decode(charset)
            return {name: dict(_load_array()) if type_ == b'o' else _load_class()}
        raise ValueError('unexpected opcode')

    return _unserialize()


class RecursiveDict(dict):
    """dict extension to handle keys in dottet notation."""

    def __init__(self, data=None, reconstruct=True):
        """Construct from data

        Parameters
        ----------
        data : dict, optional
            Dict to create from. The default is None.
        reconstruct : bool, optional
            Whether to cast contained dicts to RecursiveDict
        """
        if data:
            for key, value in data.items():
                self.insert(key, RecursiveDict(value) if reconstruct and isinstance(value, dict) else value)

    def flat(self):
        """Flatten RecursiveDicts to normal dict with dot notation.

        Returns
        -------
        data : dict
            Converted dict.
        """
        data = {}
        for key, value in self.items():
            if not isinstance(value, RecursiveDict):
                data[key] = value
                continue
            for k, v in value.flat().items():
                data[key if k is None else key+"."+k] = v
        return data

    def insert(self, key, value):
        """Insert key, creating sub-levels as necessary.

        Parameters
        ----------
        key : any
            Key of the value to insert
        value : any
            Value to insert
        """
        if not isinstance(key, str) or "." not in key:
            if isinstance(self.get(key), RecursiveDict):
                self[key][None] = value
            else:
                self[key] = value
            return
        pre, post = key.split(".", 1)
        if pre not in self:
            self[pre] = RecursiveDict()
        elif not isinstance(self[pre], RecursiveDict):
            self[pre] = RecursiveDict({None: self[pre]})
        self[pre].insert(post, value)

    def update(self, E=None, **F):
        """Override for dict.update, using insert for each key.

        Parameters
        ----------
        E : dict, optional
            DESCRIPTION. The default is None.
        **F : TYPE
            DESCRIPTION.
        """
        if isinstance(E, RecursiveDict):
            for key, value in E.items():
                if isinstance(self.get(key), dict) and isinstance(value, dict):
                    self[key].update(value)
                else:
                    self[key] = value
        elif isinstance(E, dict):
            for key, value in E.items():
                self.insert(key, value)
        for key, value in F.items():
            self.insert(key, value)
        return self


# Copied from the jellyfish package and slightly modified
def damerau_levenshtein_distance(s1, s2):
    """Compute Damerau-Levenshtein string distance

    Parameters
    ----------
    s1 : str
        First string
    s2 : str
        Second string

    Returns
    -------
    int
        Distance between the two strings
    """
    if not isinstance(s1, str) or not isinstance(s2, str):
        raise TypeError("Arguments must be string")

    len1 = len(s1)
    len2 = len(s2)
    infinite = len1 + len2

    # character array
    da = defaultdict(int)

    # distance matrix
    score = [[0] * (len2 + 2) for x in range(len1 + 2)]

    score[0][0] = infinite
    for i in range(0, len1 + 1):
        score[i + 1][0] = infinite
        score[i + 1][1] = i
    for i in range(0, len2 + 1):
        score[0][i + 1] = infinite
        score[1][i + 1] = i

    for i in range(1, len1 + 1):
        db = 0
        for j in range(1, len2 + 1):
            i1 = da[s2[j - 1]]
            j1 = db
            cost = 1
            if s1[i - 1] == s2[j - 1]:
                cost = 0
                db = j

            score[i + 1][j + 1] = min(
                score[i][j] + cost,
                score[i + 1][j] + 1,
                score[i][j + 1] + 1,
                score[i1][j1] + (i - i1 - 1) + 1 + (j - j1 - 1),
            )
        da[s1[i - 1]] = i

    return score[len1 + 1][len2 + 1]
