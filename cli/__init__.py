# -*- coding: utf-8 -*-
"""
Created on Thu Sep 17 11:32:57 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: Grammm GmbH, 2020
"""

from argparse import ArgumentParser

import random
import string
from datetime import datetime
from getpass import getpass

passwordChars = string.ascii_letters+string.digits+'!"#$%&()*+-/;<=>?[]_{|}~'
defaultPassLength = 16

class Cli:
    parser = ArgumentParser(description="Grammm admin backend")
    subparsers = parser.add_subparsers()

    @classmethod
    def execute(cls, args=None):
        """Execute commands as specified by args.

        If no args are passed, sys.args is used instead.

        Parameters
        ----------
        args : list of strings, optional
            Command line arguments to execute. The default is None.
        """
        dispatch = cls.parser.parse_args(args)
        if hasattr(dispatch, "_handle"):
            dispatch._handle(dispatch)
        else:
            cls.parser.print_help()
            exit(2)

    @classmethod
    def register(cls, name, handler) -> ArgumentParser:
        """Register a new sub-command.

        The parsed arguments are passed to the handler function.

        Parameters
        ----------
        name : str
            Name of the sub-command
        handler : Callable
            Function that executes the sub-command.

        Returns
        -------
        ArgumentParser
            Sub-parser that can be customized with sub-command specific arguments
        """
        subp = cls.subparsers.add_parser(name)
        subp.set_defaults(_handle=handler)
        return subp

    @classmethod
    def command(cls, name, parserSetup=lambda subp: None):
        """Decorator for sub-command handlers.

        Can be used instead of calling register().

        Parameters
        ----------
        name : str
            Name of the subcommand
        parserSetup : Callable, optional
            Function that sets up the sub-command parser. By default not further initialization is done.
        """
        def inner(func):
            subp = cls.register(name, func)
            parserSetup(subp)
            return func
        return inner


def _runParserSetup(subp: ArgumentParser):
    subp.add_argument("--ip", "-i", default="0.0.0.0", type=str, help="Host address to bind to")
    subp.add_argument("--port", "-p", default=5001, type=int, help="Host port to bind to")
    subp.add_argument("--debug", "-d", action="store_true", help="Run in debug mode")


@Cli.command("run", _runParserSetup)
def cliRun(args):
    from api import API
    import endpoints
    import importlib
    for group in endpoints.__all__:
        importlib.import_module("endpoints."+group)
    API.run(host=args.ip, port=args.port, debug=args.debug)


def mkPasswd(length=None):
    return "".join(random.choices(passwordChars, k=length or defaultPassLength))


def createAdmin():
    """Create admin user.

    Returns
    -------
    admin : Users
        The admin user object
    adminPass : str
        Clear text password
    """
    from orm.users import Users
    adminPass = mkPasswd()
    admin = Users(None)
    admin.ID = 0
    admin.username = "admin"
    admin.domainID = 0
    admin.password = adminPass
    admin.maxSize = 0
    admin.createDay = datetime.now()
    return admin, adminPass


@Cli.command("create-db")
def cliCreateDB(args):
    import logging
    from orm import DB
    if DB is None:
        logging.fatal("Could not initialize database connection - check configuration")

    from orm import ext, misc, orgs, roles, users
    try:
        logging.info("Setting up database...")
        DB.create_all()
        if users.Users.query.filter(users.Users.ID == 0).count() == 0:
            logging.info("Creating system admin...")
            DB.session.execute("SET sql_mode='NO_AUTO_VALUE_ON_ZERO';")
            admin, adminPass = createAdmin()
            DB.session.add(admin)
            try:
                DB.session.commit()
                logging.info("System admin credentials are: {}:{}".format(admin.username, adminPass))
            except:
                logging.error("Could not create admin user. Please contact your admin administrator.")
                exit(1)
        else:
            logging.info("System admin user already exists. Use `passwd` command to reset password.")
        logging.info("Success.")
    except:
        import traceback
        logging.fatal(traceback.format_exc())
        logging.info("Database setup failed.")
        exit(1)

def _versionParserSetup(subp: ArgumentParser):
    components = subp.add_mutually_exclusive_group()
    components.add_argument("--api", "-a", action="store_true", help="Print API version")
    components.add_argument("--backend", "-b", action="store_true", help="Print Backend version")
    components.add_argument("--combined", "-c", action="store_true", help="Print combined version")

@Cli.command("version", _versionParserSetup)
def cliVersion(args):
    from api import backendVersion, apiVersion
    if args.backend:
        print(backendVersion)
    elif args.combined:
        vdiff = int(backendVersion.rsplit(".", 1)[1])-int(apiVersion.rsplit(".", 1)[1])
        if vdiff == 0:
            print(apiVersion)
        else:
            print("{}{:+}".format(apiVersion, vdiff))
    else:
        print(apiVersion)
    exit(0)

@Cli.command("chkconfig")
def cliChkConfig(args):
    from tools.config import validate
    result = validate()
    if result is None:
        print("Configuration schema valid")
        exit(0)
    else:
        print("Error: "+result)
        exit(1)

def _passwdParserSetup(subp: ArgumentParser):
    subp.add_argument("--user", "-u", action="store", type=str,
                      help="User to change the password of. If omitted, set password of system administrator.")
    subp.add_argument("--auto", "-a", action="store_true", help="Automatically generate password.")
    subp.add_argument("--length", "-l", action="store", type=int, default=defaultPassLength,
                      help="Length of auto-generated password (default {})".format(defaultPassLength))


@Cli.command("passwd", _passwdParserSetup)
def setUserPassword(args):
    import logging
    from orm.users import DB, Users
    if args.user is not None:
        user = Users.query.filter(Users.username == args.user).first()
        if user is None:
            logging.error("User '{}' not found.")
            exit(1)
        if user.addressType != Users.NORMAL:
            logging.error("Cannot set password of alias user")
            exit(2)
    else:
        user = Users.query.filter(Users.ID == 0).first()
        if user is None:
            logging.info("System admin user not found, creating...")
            DB.session.execute("SET sql_mode='NO_AUTO_VALUE_ON_ZERO';")
            user, _ = createAdmin()
            DB.session.add(user)
    logging.info("Setting password for user '{}'".format(user.username))
    if args.auto:
        password = mkPasswd(args.length)
        logging.info("New password is "+password)
    else:
        password = getpass("Password: ")
        if getpass("Retype password: ") != password:
            logging.error("Passwords do not match, aborting.")
            exit(3)
    user.password = password
    DB.session.commit()
    logging.info("Password updated")
    exit(0)
