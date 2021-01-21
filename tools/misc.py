# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grammm GmbH

import time

from datetime import datetime

from .constants import PropTags, PropTypes
from .rop import nxTime

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


def propvals2dict(vals: list) -> dict:
    def prop2val(prop):
        if prop.type == PropTypes.FILETIME:
            return datetime.fromtimestamp(nxTime(int(prop.toString()))).strftime("%Y-%m-%d %H:%M:%S")
        elif prop.type in PropTypes.intTypes:
            return int(prop.toString())
        elif prop.type in PropTypes().floatTypes:
            return float(prop.toString())
        return prop.toString()

    return {PropTags.lookup(prop.tag).lower(): prop2val(prop) for prop in vals}


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


def setDirectoryOwner(path, uid=None, gid=None):
    """Recursively set directory ownership of path.

    If neither uid nor gid is set, the function return immediatly without touching any files.

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
    if uid is None and gid is None:
        return
    for path, subdirs, files in os.walk(path):
        shutil.chown(path, uid, gid)
        for entry in subdirs+files:
            shutil.chown(os.path.join(path, entry), uid, gid)
