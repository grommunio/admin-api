# -*- coding: utf-8 -*-
"""
Created on Mon Oct  5 15:02:52 2020

@copyright: grammm GmbH, 2020
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


def _passwdParserSetup(subp: ArgumentParser):
    subp.add_argument("--user", "-u", action="store", type=str,
                      help="User to change the password of. If omitted, set password of system administrator.")
    subp.add_argument("--auto", "-a", action="store_true", help="Automatically generate password.")
    subp.add_argument("--length", "-l", action="store", type=int, default=defaultPassLength,
                      help="Length of auto-generated password (default {})".format(defaultPassLength))
    subp.add_argument("--password", "-p", action="store", type=str,
                      help="New password. If neither -p nor -a are specified, the new password is set interactively.")


@Cli.command("passwd", _passwdParserSetup)
def setUserPassword(args):
    import logging
    from orm.users import DB, Users
    import orm.roles
    if args.user is not None:
        user = Users.query.filter(Users.username == args.user).first()
        if user is None:
            logging.error("User '{}' not found.")
            return 1
        if user.addressType != Users.NORMAL:
            logging.error("Cannot set password of alias user")
            return 2
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
    elif args.password is not None:
        password = args.password
    else:
        password = getpass("Password: ")
        if getpass("Retype password: ") != password:
            logging.error("Passwords do not match, aborting.")
            return 3
    user.password = password
    DB.session.commit()
    logging.info("Password updated")
