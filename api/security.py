#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jun 23 11:20:50 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: _Placeholder_copyright_
"""


def getSecurityContext():
    """Create security context for the request.

    Check for `jwt` cookie in the request and try to decode it. If token is valid, the claims are saved in `request.auth`

    If authentication is disabled in the configuration (security.requireAuth=False), the default security context is used
    (security.defaultContext).

    Returns
    -------
    str
        Error message or None if successful

    """
    pass
