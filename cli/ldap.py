# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grammm GmbH

from argparse import ArgumentParser

from . import Cli

SUCCESS = 0
ERR_NO_LDAP = 1  # LDAP not available
ERR_GENERIC = 2  # Something went wrong
ERR_USR_ABRT = 3  # User aborted
ERR_DECLINE = 4  # User declined prompt
ERR_NO_USER = 5  # LDAP User not found
ERR_AMBIG = 6  # Request was ambiguous
ERR_DB = 7  # Error occured when communicating with the database
ERR_CONFLICT = 8  # Target DB user is associated with another LDAP object
ERR_COMMIT = 9  # Error during database commit
ERR_INVALID_DATA = 10  # User data check failed
ERR_SETUP = 11  # Error during user setup


def _confirm(prompt=""):
    try:
        return SUCCESS if input(prompt).lower() == "y" else ERR_DECLINE
    except:
        return ERR_USR_ABRT


def cliLdapInfo(args):
    from tools import ldap
    if not ldap.LDAP_available:
        print("LDAP is not available.")
        return ERR_NO_LDAP
    print("Successfully connected to {} as {}".format(ldap.ldapconf["connection"]["server"],
                                                      ldap.ldapconf["connection"].get("bindUser") or "anonymous"))


def _getCandidate(expr, auto):
    from tools import ldap
    from base64 import b64decode
    try:
        candidate = ldap.getUserInfo(b64decode(expr))
    except:
        candidate = None
    if candidate is None:
        matches = ldap.searchUsers(expr)
        if len(matches) == 0:
            print("No user found")
            return ERR_NO_USER
        if len(matches) == 1:
            candidate = matches[0]
        else:
            if auto:
                print("Multiple candidates for '{}' found - aborting".format(expr))
                return ERR_AMBIG
            print("Found {} users matching '{}':".format(len(matches), expr))
            for i in range(len(matches)):
                print("{: 2d}: {} ({})".format(i+1, matches[i].name, matches[i].email))
            candidate = None
            while candidate == None:
                try:
                    selected = input("Choose index of user (1-{}) or CTRL+C to exit: ".format(len(matches)))
                    index = int(selected)-1
                    if not 0 <= index < len(matches):
                        continue
                    candidate = matches[index]
                except (EOFError, KeyboardInterrupt):
                    print("k bye.")
                    return ERR_USR_ABRT
                except ValueError:
                    continue
    return candidate


def _downsyncUser(candidate, yes, auto, force):
    from tools import ldap
    from base64 import b64decode

    if yes or auto:
        print("Synchronizing user '{}' ({})".format(candidate.name, candidate.email))
    else:
        result = _confirm("Synchronize user '{}' ({})? [y/N]: ".format(candidate.name, candidate.email))
        if result != SUCCESS:
            if result == ERR_USR_ABRT:
                print("\nAborted.")
            return result

    from orm import DB
    if DB is None:
        print("Database not configured")
        return ERR_DB
    from orm.domains import Domains
    from orm.users import Users
    from orm import roles
    from tools.DataModel import MismatchROError, InvalidAttributeError

    domain = Domains.query.filter(Domains.domainname == candidate.email.split("@")[1]).with_entities(Domains.ID).first()
    if domain is None:
        print(message="Cannot import user: Domain not found")
    user = Users.query.filter(Users.externID == candidate.ID).first() or\
        Users.query.filter(Users.username == candidate.email).first()
    if user is not None:
        if user.externID != candidate.ID and not force:
            if auto:
                print("Cannot import user: User exists " +
                      ("locally" if user.externID is None else "and is associated with another LDAP object"))
                return ERR_CONFLICT
            else:
                result = _confirm("Force update "+("local only user" if user.externID is None else
                                                   "user linked to different LDAP object")+"? [y/N]: ")
                if result != SUCCESS:
                    if result == ERR_USR_ABRT:
                        print("Aborted")
                    return result
        userdata = ldap.downsyncUser(candidate.ID, user.propmap)
        try:
            user.fromdict(userdata)
            user.externID = candidate.ID
            DB.session.commit()
            print("User updated.")
            return SUCCESS
        except (InvalidAttributeError, MismatchROError, ValueError) as err:
            DB.session.rollback()
            print("Failed to update user: "+err.args[0])
            return ERR_COMMIT

    userdata = ldap.downsyncUser(candidate.ID)
    if userdata is None:
        print("Error retrieving user")
        return ERR_NO_USER
    error = Users.checkCreateParams(userdata)
    if error is not None:
        print("Cannot import user: "+error)
        return ERR_INVALID_DATA
    try:
        user = Users(userdata)
        user.externID = candidate.ID
        DB.session.add(user)
        DB.session.flush()
    except (InvalidAttributeError, MismatchROError, ValueError) as err:
        DB.session.rollback()
        print("Failed to update user: "+err.args[0])
        return ERR_COMMIT
    from tools.storage import UserSetup
    with UserSetup(user) as us:
        us.run()
    if not us.success:
        print("Error during user setup: ", us.error), us.errorCode
        return ERR_SETUP
    DB.session.commit()
    print("User '{}' created with ID {}.".format(user.username, user.ID))
    return SUCCESS


def cliLdapDownsync(args):
    from tools import ldap
    if not ldap.LDAP_available:
        print("LDAP is not available.")
        return ERR_NO_LDAP
    error = False
    if args.user is not None and len(args.user) != 0:
        for expr in args.user:
            candidate = _getCandidate(expr, args.auto)
            if isinstance(candidate, int):
                error = True
                if candidate == ERR_USR_ABRT:
                    break
                continue
            result = _downsyncUser(candidate, args.yes, args.auto, args.force)
            if result == ERR_USR_ABRT:
                break
            error = error or result != SUCCESS
        return ERR_GENERIC if error else SUCCESS
    elif args.complete:
        from time import time
        candidates = ldap.searchUsers(None)
        if len(candidates) == 0:
            print("No LDAP users found.")
            return SUCCESS
        print("Synchronizing {} user{}...".format(len(candidates), "" if len(candidates) == 1 else "s"))
        error = False
        for candidate in candidates:
            result = _downsyncUser(candidate, args.yes, args.auto, args.force)
            error = error or result != SUCCESS
            if result == ERR_USR_ABRT:
                break
        return ERR_GENERIC if error else SUCCESS
    from orm.users import Users
    users = Users.query.filter(Users.externID != None).with_entities(Users.externID).all()
    if len(users) == 0:
        print("No imported users found")
        return SUCCESS
    candidates = ldap.getAll(user.externID for user in users)
    if len(candidates) != len(users):
        print("Some ldap references seem to be broken - please run ldap check")
    error = False
    print("Synchronizing {} user{}...".format(len(candidates), "" if len(candidates) == 1 else "s"))
    for candidate in candidates:
        result = _downsyncUser(candidate, args.yes, args.auto, args.force)
        error = error or result != SUCCESS
        if result == ERR_USR_ABRT:
            break
    return ERR_GENERIC if error else SUCCESS


def cliLdapSearch(args):
    from tools import ldap
    if not ldap.LDAP_available:
        print("LDAP is not available.")
        return 2
    matches = ldap.searchUsers(args.query)
    if len(matches) == 0:
        print("No matches")
        return 1
    from base64 import b64encode
    for match in matches:
        print("{}: {} ({})".format(b64encode(match.ID).decode("ascii"), match.name, match.email))


def cliLdapCheck(args):
    from tools import ldap
    if not ldap.LDAP_available:
        print("LDAP is not available.")
        return 2
    from time import time
    from orm import DB
    from orm.users import Users
    users = Users.query.filter(Users.externID != None).with_entities(Users.ID, Users.username, Users.externID, Users.maildir)\
                       .all()
    if len(users) == 0:
        print("No LDAP users found")
        return
    print("Checking {} user{}...".format(len(users), "" if len(users) == 1 else "s"))
    count, last = 0, time()
    orphaned = []
    for user in users:
        if ldap.getUserInfo(user.externID) is None:
            orphaned.append(user)
        count += 1
        if time()-last > 1:
            last = time()
            print("\t{}/{} checked, {} orphaned".format(count, len(users), len(orphaned)))
    if len(orphaned) == 0:
        print("Everything is ok")
        return
    print("LDAP entries of the following users could not be found:")
    for user in orphaned:
        print("\t"+user.username)
    if args.remove:
        if args.yes or _confirm("Delete all orphaned users? [y/N]: ") == SUCCESS:
            from tools.config import Config
            from tools.constants import ExmdbCodes
            from tools.pyexmdb import pyexmdb
            print("Unloading exmdb stores...")
            try:
                options = Config["options"]
                client = pyexmdb.ExmdbQueries(options["exmdbHost"], options["exmdbPort"], options["userPrefix"], True)
                for user in orphaned:
                    client.unloadStore(user.maildir)
            except pyexmdb.ExmdbError as err:
                print("WARNING: Could not unload exmdb store: "+ExmdbCodes.lookup(err.code, hex(err.code)))
            except RuntimeError as err:
                print("WARNING: Could not unload exmdb store: "+err.args[0])
            if args.remove_maildirs:
                import shutil
                print("Removing mail directories...")
                for user in orphaned:
                    shutil.rmtree(user.maildir, ignore_errors=True)
            deleted = Users.query.filter(Users.ID.in_(user.ID for user in orphaned)).delete(synchronize_session=False)
            DB.session.commit()
            print("Deleted {} user{}".format(deleted, "" if deleted == 1 else "s"))
    return ERR_NO_USER


def _cliLdapParserSetup(subp: ArgumentParser):
    sub = subp.add_subparsers()
    info = sub.add_parser("info")
    info.set_defaults(_handle=cliLdapInfo)
    downsync = sub.add_parser("downsync")
    downsync.set_defaults(_handle=cliLdapDownsync)
    downsync.add_argument("user", nargs="*", help="LDAP ID or user search query string. If omitted, all users linked to an "\
                                                  "LDAP object are updated.")
    downsync.add_argument("-a", "--auto", action="store_true", help="Do not prompt, exit with error instead. Implies -y.")
    downsync.add_argument("-c", "--complete", action="store_true", help="Import/update all users in the ldap tree")
    downsync.add_argument("-f", "--force", action="store_true", help="Force synchronization of unassociated users")
    downsync.add_argument("-y", "--yes", action="store_true", help="Proceed automatically if target is unambiguous")
    search = sub.add_parser("search")
    search.set_defaults(_handle=cliLdapSearch)
    search.add_argument("query")
    check = sub.add_parser("check")
    check.set_defaults(_handle=cliLdapCheck)
    check.add_argument("-y", "--yes", action="store_true", help="Do not prompt for user deletion (only with -r)")
    check.add_argument("-r", "--remove", action="store_true", help="Prompt for user deletion if orphaned users exist")
    check.add_argument("-m", "--remove-maildirs", action="store_true", help="When deleting users, also remove their mail "\
                                                                             "directories from disk")


@Cli.command("ldap", _cliLdapParserSetup)
def cliLdap(args):
    if hasattr(args, "_handle") and args._handle != cliLdap:
        return args._handle(args) or 0
    else:
        return cliLdapInfo(args)
