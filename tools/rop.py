# -*- coding: utf-8 -*-
"""
Created on Tue Aug 11 20:30:02 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: Grammm GmbH, 2020
"""

import time


def valueToGc(value: int) -> bytes:
    """-> rop_util.c:57."""
    return value.to_bytes(6, "little")


def makeEid(replid: int, gc: bytes) -> int:
    """-> rop_util.c:93."""
    return replid | (int.from_bytes(gc, "big") << 16)


def makeEidEx(replid: int, value: int) -> int:
    """-> rop_util.c:109."""
    gc = valueToGc(value)
    return makeEid(replid, gc)


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


def nxTime(timestamp) -> float:
    timestamp /= 10000000
    timestamp -= 11644473600
    return timestamp
