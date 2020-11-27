#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jun 23 11:22:42 CEST 2020

@copyright: grammm GmbH, 2020

Main file to execute.

Can be used to run the API in stand-alone mode by directly executing the file or
in combination with a WSGI server using the API object as callable
"""

if __name__ == '__main__':
    import os
    import sys
    os.chdir(os.path.dirname(__file__))
    from cli import Cli
    sys.exit(Cli.execute())
else:
    from api.core import API
    from endpoints import *
