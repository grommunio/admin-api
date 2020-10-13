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
import alembic.command
import alembic.config
import alembic.script
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


def checkDBVersion(DB, aconf):
    currentVersions = alembic.migration.MigrationContext.configure(DB.session.connection()).get_current_heads()
    directory = alembic.script.ScriptDirectory.from_config(aconf)
    return set(currentVersions), set(directory.get_heads())


def _createParserSetup(subp: ArgumentParser):
    subp.add_argument("--force", "-f", action="store_true")
    subp.add_argument("--wipe", action="store_true")


@Cli.command("create-db", _createParserSetup)
def cliCreateDB(args):
    import logging
    from orm import DB
    if DB is None:
        logging.fatal("Could not initialize database connection - check configuration")

    upgrade = create = False
    aconf = alembic.config.Config("alembic.ini")
    if args.force:
        create = True
    elif args.wipe:
        create = True
        logging.warn("Wiping database")
        DB.drop_all()
    else:
        current, target = checkDBVersion(DB, aconf)
        if current == target:
            logging.info("Schema is up to date, exiting")
            exit(0)
        if len(current) == 0:
            logging.info("Could not determine current schema version - creating from scratch")
            create = True
        else:
            logging.info("Upgrading from '{}' to '{}'".format("|".join(current), "|".join(target)))
            upgrade = True
    if upgrade:
        alembic.command.upgrade(aconf, "head")
        logging.info("Upgrade complete")
    elif create:
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
                alembic.command.stamp(aconf, "head")
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
    subp.add_argument("--password", "-p", action="store", type=str,
                      help="New password. If neither -p nor -a are specified, the new password is set interactively.")


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
    elif args.password is not None:
        password = args.password
    else:
        password = getpass("Password: ")
        if getpass("Retype password: ") != password:
            logging.error("Passwords do not match, aborting.")
            exit(3)
    user.password = password
    DB.session.commit()
    logging.info("Password updated")
    exit(0)
