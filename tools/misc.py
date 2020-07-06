# -*- coding: utf-8 -*-
"""
Created on Tue Jun 30 17:14:08 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: Grammm GmbH, 2020
"""

import time

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


def ntTime(timestamp=None) -> int:
    """Convert UNIX timestamp to Windows timestamp.

    Parameters
    ----------
    timestamp : float, optional
        Timestamp to convert. If not specified, use current time. The default is None.

    Returns
    -------
    int
        Windows NT timestamp
    """
    timestamp = timestamp or time.time()
    timestamp += 11644473600
    timestamp *= 10000000
    return int(timestamp)
