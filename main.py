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


def parseArgs():
    from argparse import ArgumentParser
    parser = ArgumentParser(description="Grammm admin backend")
    parser.add_argument("command", default="run", choices=("run", "create-db"), nargs="?")
    return parser.parse_args()


def run():
    from api import API
    from endpoints import ext, misc, orgs, users
    API.run(host="0.0.0.0", debug=True)


def createDB():
    from orm import ext, misc, orgs, users
    from orm import DB
    import logging
    import traceback
    if DB is None:
        logging.fatal("Could initialize database connection - check configuration")
    try:
        logging.info("Setting up database...")
        DB.create_all()
        logging.info("Success.")
    except:
        logging.fatal(traceback.format_exc())
        logging.info("Database setup failed.")
        exit(1)


# Run in stand-alone mode if file is executed directly
if __name__ == '__main__':
    args = parseArgs()
    if args.command == "create-db":
        createDB()
    elif args.command == "run":
        run()
else:
    from api import API
    from endpoints import *
