# -*- coding: utf-8 -*-
"""
Created on Mon Oct  5 15:02:52 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: Grammm GmbH, 2020
"""

from . import Cli

from argparse import ArgumentParser

import random
import string
from datetime import datetime
from getpass import getpass

passwordChars = string.ascii_letters+string.digits+'!"#$%&()*+-/;<=>?[]_{|}~'
defaultPassLength = 16


def mkPasswd(length=None):
    """Generate random password.

    Parameters
    ----------
    length : int, optional
        Length of the password. The default is `defaultPassLength` (16).

    Returns
    -------
    str
        String containing the password.
    """
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
    admin.realName = "System Administrator"
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
    from orm.roles import AdminRoles
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
