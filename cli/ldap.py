# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grammm GmbH

from argparse import ArgumentParser

from . import Cli


def _confirm(prompt=""):
    try:
        return input(prompt).lower() == "y"
    except:
        return False


def cliLdapInfo(args):
    from tools import ldap
    if not ldap.LDAP_available:
        print("LDAP is not available.")
        return 1
    print("Successfully connected to {} as {}".format(ldap.ldapconf["connection"]["server"],
                                                      ldap.ldapconf["connection"].get("bindUser") or "anonymous"))


def cliLdapDownsync(args):
    from tools import ldap
    from base64 import b64decode
    if not ldap.LDAP_available:
        print("LDAP is not available.")
    try:
        candidate = ldap.getUserInfo(b64decode(args.user))
    except:
        candidate = None
    if candidate is None:
        matches = ldap.searchUsers(args.user)
        if len(matches) == 0:
            print("No user found")
            return 1
        if len(matches) == 1:
            candidate = matches[0]
        else:
            if args.auto:
                print("Multiple candidates for '{}' found - aborting".format(args.user))
                return 2
            print("Found {} users matching '{}':".format(len(matches), args.user))
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
                    return 3
                except ValueError:
                    continue
    if args.yes or args.auto:
        print("Synchronizing user '{}' ({})".format(candidate.name, candidate.email))
    else:
        if not _confirm("Synchronize user '{}' ({})? [y/N]: ".format(candidate.name, candidate.email)):
            print("Aborted.")
            return 4

    from orm import DB
    if DB is None:
        print("Database not configured")
        return 6
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
        if user.externID != candidate.ID and not args.force:
            if args.auto:
                print("Cannot import user: User exists " +
                      ("locally" if user.externID is None else "and is associated with another LDAP object"))
                return 7
            else:
                if not _confirm("Force update "+("local only user" if user.externID is None else
                                                 "user linked to different LDAP object")+"? [y/N]: "):
                    print("Aborted")
                    return 8
        userdata = ldap.downsyncUser(candidate.ID, user.propmap)
        try:
            user.fromdict(userdata)
            user.externID = candidate.ID
            DB.session.commit()
            print("User updated.")
            return 0
        except (InvalidAttributeError, MismatchROError, ValueError) as err:
            DB.session.rollback()
            return print("Failed to update user: "+err.args)
        return 9

    userdata = ldap.downsyncUser(candidate.ID)
    if userdata is None:
        print("Error retrieving user")
        return 9
    error = Users.checkCreateParams(userdata)
    if error is not None:
        print("Cannot import user: "+error)
        return 10
    user = Users(userdata)
    user.externID = candidate.ID
    DB.session.add(user)
    DB.session.flush()
    from tools.storage import UserSetup
    with UserSetup(user) as us:
        us.run()
    if not us.success:
        print("Error during user setup: ", us.error), us.errorCode
        return 11
    DB.session.commit()
    print("User '{}' created with ID {}.".format(user.username, user.ID))


def cliLdapSearch(args):
    from tools import ldap
    if not ldap.LDAP_available:
        print("LDAP is not available.")
    matches = ldap.searchUsers(args.query)
    if len(matches) == 0:
        print("No matches")
        return 1
    from base64 import b64encode
    for match in matches:
        print("{}: {} ({})".format(b64encode(match.ID).decode("ascii"), match.name, match.email))


def _cliLdapParserSetup(subp: ArgumentParser):
    sub = subp.add_subparsers()
    info = sub.add_parser("info")
    info.set_defaults(_handle=cliLdapInfo)
    downsync = sub.add_parser("downsync")
    downsync.set_defaults(_handle=cliLdapDownsync)
    downsync.add_argument("user", help="LDAP ID or user search query string")
    downsync.add_argument("-f", "--force", action="store_true", help="Force synchronization of unassociated users")
    downsync.add_argument("-y", "--yes", action="store_true", help="Proceed automatically if target is unambiguous")
    downsync.add_argument("-a", "--auto", action="store_true", help="Do not prompt, exit with error instead. Implies -y")
    search = sub.add_parser("search")
    search.set_defaults(_handle=cliLdapSearch)
    search.add_argument("query")


@Cli.command("ldap", _cliLdapParserSetup)
def cliLdap(args):
    if hasattr(args, "_handle") and args._handle != cliLdap:
        return args._handle(args) or 0
    else:
        return cliLdapInfo(args)

