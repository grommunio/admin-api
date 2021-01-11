#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grammm GmbH
"""
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
    from tools import config
    error = config.validate()
    if error:
        raise TypeError("Invalid configuration found - aborting ({})".format(error))
