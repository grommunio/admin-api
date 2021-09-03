#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grommunio GmbH
"""
Main file to execute.

Can be used to run the API in stand-alone mode by directly executing the file or
in combination with a WSGI server using the API object as callable
"""

if __name__ == '__main__':
    import os
    import sys
    os.chdir(os.path.dirname(os.path.realpath(__file__)))
    from cli import Cli
    res = Cli().execute(secure=False)
    sys.exit(res)
else:
    from api.core import API  # Export to uwsgi server
    from cli import Cli
    from endpoints import *  # Register all endpoints
    from tools import config
    Cli.initLogging()
    error = config.validate()
    if error:
        raise TypeError("Invalid configuration found - aborting ({})".format(error))
