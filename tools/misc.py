# -*- coding: utf-8 -*-
"""
Created on Tue Jun 30 17:14:08 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: Grammm GmbH, 2020
"""

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
