#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jun 23 11:22:42 CEST 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: _Placeholder_copyright_

Main file to execute.

Can be used to run the API in stand-alone mode by directly executing the file or
in combination with a WSGI server using the API object as callable
"""

if __name__ == '__main__':
    from cli import Cli
    Cli.execute()
else:
    from api import API
    from endpoints import *
