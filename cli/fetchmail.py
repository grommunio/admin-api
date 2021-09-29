# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH
"""Create fetchmail configuration from database"""

from . import Cli
from .common import userspecAutocomp, userCandidates
from argparse import ArgumentParser


_globalConf = "# Global settings\n" \
              "set postmaster \"postmaster\"\n" \
              "set nobouncemail\n"\
              "set no spambounce\n"\
              "set properties \"\"\n"\
              "\n# Accounts\n"

_auths = ("password", "kerberos_v5", "kerberos", "kerberos_v4", "gssapi", "cram-md5", "otp", "ntlm", "msn", "ssh", "any")
_proto = ("POP3", "IMAP", "POP2", "ETRN", "AUTO")


def _sanitizeData(data):
    _cliargs = {"_handle", "_cli", "userspec", "mbspec"}
    return {key: value for key, value in data.items() if key not in _cliargs and value is not None}


def _dumpFml(cli, fml, passwd=False):
    cli.print(cli.col("{} ({}):".format(fml.mailbox, fml.ID), attrs=["bold"]))
    cli.print("  user: {} ({})".format(fml.user.username, fml.user.ID))
    cli.print("  active: "+(cli.col("yes", "green") if fml.active == 1 else cli.col("no", "red")))
    cli.print("  changed: "+fml.date.ctime())
    cli.print("  srcUser: "+fml.srcUser)
    if passwd:
        cli.print("  srcPassword: "+fml.srcPassword)
    for attr in ("srcFolder", "srcServer", "srcAuth", "protocol"):
        val = getattr(fml, attr)
        cli.print("  {}: {}".format(attr, val if val else cli.col("(unset)", attrs=["dark"])))
    for attr in ("fetchall", "keep", "useSSL"):
        cli.print("  {}: {}".format(attr, "yes" if  getattr(fml, attr) else "no"))
    if fml.useSSL == 1:
        cli.print("  sslCheckCert: "+("yes" if fml.sslCertCheck == 1 else "no"))
        cli.print("  sslFingerprint: "+(fml.sslFingerprint or cli.col("(unset)", attrs=["dark"])))
        cli.print("  sslCertPath: "+(fml.sslCertPath or cli.col("(unset)", attrs=["dark"])))
    cli.print("  extraOptions: "+(fml.extraOptions or cli.col("(none)", attrs=["dark"])))


def cliCreateFetchmail(args):
    cli = args._cli
    cli.require("DB")
    from orm import DB
    from orm.users import Fetchmail
    users = userCandidates(args.userspec).all()
    if len(users) == 0:
        cli.print(cli.col("User not found.", "yellow"))
        return 1
    if len(users) > 1:
        cli.print(cli.col("'{}' is ambiguous.".format(args.userspec), "yellow"))
        return 2
    user = users[0]
    if args.mailbox is None:
        args.mailbox = user.username
    data = (_sanitizeData(args.__dict__))
    err = Fetchmail.checkCreateParams(data)
    if err is not None:
        cli.print(cli.col("Cannot create fetchmail entry: "+err, "red"))
        return 3
    try:
        fml = Fetchmail(data, user)
        DB.session.add(fml)
        DB.session.commit()
        _dumpFml(cli, fml)
    except BaseException as err:
        cli.print(cli.col("Cannot create fetchmail entry: "+" - ".join(str(arg) for arg in err.args), "red"))
        DB.session.rollback()
        return 4


def cliDeleteFetchmail(args):
    cli = args._cli
    cli.require("DB")
    from orm import DB
    from orm.users import Fetchmail
    fmls = Fetchmail.query.filter(Fetchmail.ID == args.mbspec if args.mbspec.isdigit() else
                                  Fetchmail.mailbox.ilike(args.mbspec+"%")).all()
    if len(fmls) == 0:
        cli.print(cli.col("Fetchmail entry not found.", "yellow"))
        return 1
    if len(fmls) > 1 and not args.yes:
        prompt = "Delete multiple entries:\n  "+"\n  ".join("{} ({})".format(fml.mailbox, fml.ID) for fml in fmls)+"\n[y/N]: "
        if cli.confirm(prompt) != Cli.SUCCESS:
            return 2
    try:
        for fml in fmls:
            DB.session.delete(fml)
        DB.session.commit()
    except BaseException as err:
        cli.print(cli.col("Deletion failed: "+" - ".join(str(arg) for arg in err.args), "red"))
        DB.session.rollback()
        return 4
    cli.print("{} entr{} deleted.\n".format(len(fmls), "y" if len(fmls) == 1 else "ies")+
              cli.col("Entry deletion will not be handled automatically, consider running ", "yellow")+
              cli.col("write-rc -f", "yellow", attrs=["bold", "dark"])+
              cli.col(" to manually update the configuration.", "yellow"))


def cliListFetchmail(args):
    cli = args._cli
    cli.require("DB")
    from orm.users import Fetchmail
    query = Fetchmail.optimized_query(1)
    if "filter" in args and args.filter is not None:
        query = Fetchmail.autofilter(query, {f.split("=", 1)[0]: f.split("=", 1)[1] for f in args.filter if "=" in f})
    if "sort" not in args or args.sort is None:
        args.sort = "active,desc"
    query = Fetchmail.autosort(query, args.sort)
    if args.mbspec is not None:
        query = query.filter(Fetchmail.ID == args.mbspec if args.mbspec.isdigit() else Fetchmail.mailbox.ilike(args.mbspec+"%"))
    entries = query.all()
    if len(entries) == 0:
        cli.print(cli.col("No results", "yellow"))
    for entry in entries:
        cli.print("{} ({}) from '{}@{}/{}', {}, updated {}".format(
                cli.col(entry.mailbox, attrs=["bold"]),
                cli.col(entry.ID, attrs=["bold"]),
                entry.srcUser,
                entry.srcServer,
                entry.srcFolder,
                cli.col("active", "green") if entry.active == 1 else cli.col("inactive", "red"),
                entry.date.ctime()))


def cliModifyFetchmail(args):
    cli = args._cli
    cli.require("DB")
    from orm import DB
    from orm.users import Fetchmail
    fmls = Fetchmail.query.filter(Fetchmail.ID == args.mbspec if args.mbspec.isdigit() else
                                  Fetchmail.mailbox.ilike(args.mbspec+"%")).all()
    if len(fmls) == 0:
        cli.print(cli.col("Fetchmail entry not found.", "yellow"))
        return 1
    if len(fmls) > 1:
        cli.print(cli.col("'{}' is ambiguous.".format(args.mbspec), "yellow"))
        return 2
    fml = fmls[0]
    data = _sanitizeData(args.__dict__)
    try:
        fml.fromdict(data)
        DB.session.commit()
        _dumpFml(cli, fml)
    except BaseException as err:
        cli.print(cli.col("Cannot create fetchmail entry: "+" - ".join(str(arg) for arg in err.args), "red"))
        DB.session.rollback()
        return 3


def cliPrintFetchmail(args):
    cli = args._cli
    cli.require("DB")
    from orm.users import Fetchmail
    fmls = Fetchmail.query.filter(Fetchmail.ID == args.mbspec if args.mbspec.isdigit() else
                                  Fetchmail.mailbox.ilike(args.mbspec+"%")).all()
    if len(fmls) == 0:
        cli.print(cli.col("No fetchmail entries found.", "yellow"))
    for fml in fmls:
        cli.print(("{} ({}): ".format(fml.mailbox, fml.ID) if not args.quiet else "")+cli.col(str(fml), attrs=["bold"]), end="")


def cliShowFetchmail(args):
    cli = args._cli
    cli.require("DB")
    from orm.users import Fetchmail
    from sqlalchemy.orm import joinedload
    fmls = Fetchmail.query.filter(Fetchmail.ID == args.mbspec if args.mbspec.isdigit() else
                                  Fetchmail.mailbox.ilike(args.mbspec+"%")).options(joinedload(Fetchmail.user)).all()
    if len(fmls) == 0:
        cli.print(cli.col("No fetchmail entries found.", "yellow"))
    for fml in fmls:
        _dumpFml(cli, fml, args.password)


def cliWriteFetchmailrc(args):
    cli = args._cli
    def write(data):
        file.write(data)
        if args.print:
            cli.print(cli.col(data, attrs=["bold"]), end="")

    def vprint(*vargs, **vkwargs):
        if args.verbose:
            cli.print(*vargs, **vkwargs)

    cli.require("DB")
    from datetime import datetime, timedelta
    from orm.users import Fetchmail
    if not args.force:
        if args.time == "auto":
            if cli.fs is not None:
                vprint("Filesystem is emulated - update autdetection skipped")
                mtime = None
            else:
                try:
                    import os
                    mtime = datetime.utcfromtimestamp(os.path.getmtime(args.out_file))
                    vprint("Last fetchmailrc modification was on "+mtime.ctime())
                except:
                    mtime = None
                    vprint("No fetchmailrc found, creating")
        else:
            try:
                mtime = datetime.now()-timedelta(minutes=int(args.time))
                vprint("Manually set last update to "+mtime.ctime())
            except:
                vprint(cli.col("Invalid time specification. Must be integer or 'auto'.", "red"))
                return 3
        if mtime is not None and Fetchmail.query.filter(Fetchmail.date > mtime).count() == 0:
            cli.print(cli.col("No new accounts created since {}. Use -f to force creation.".format(mtime.ctime()), "yellow"))
            return 0
    try:
        vprint("Writing output to "+args.out_file)
        with cli.open(args.out_file, "w") as file:
            write(_globalConf)
            for record in Fetchmail.query.filter(Fetchmail.active == 1).all():
                write(str(record))
    except OSError as err:
        cli.print(cli.col("Could not write to file: {} - {}".format(err.errno, err.strerror), "red"))
        return 2
    except Exception as err:
        cli.print(cli.col("Could not write to file: "+"-".join(str(arg) for arg in err.args)))
        return 3
    if cli.fs is None:
        from tools.misc import setDirectoryOwner, setDirectoryPermission
        try:
            setDirectoryPermission(args.out_file, 0o600)
        except Exception as err:
            cli.print(cli.col("Failed to set file permission: {} - {}"\
                              .format(type(err).__name__, " - ".join(str(arg) for arg in err.args)), "yellow"))
        try:
            setDirectoryOwner(args.out_file, "fetchmail")
        except Exception as err:
            cli.print(cli.col("Failed to set file owner: {} - {}"\
                              .format(type(err).__name__, " - ".join(str(arg) for arg in err.args)), "yellow"))


def _fmlAutocomp(prefix, **kwargs):
    try:
        from orm.users import Fetchmail
        return (fml.mailbox
                for fml in Fetchmail.query.with_entities(Fetchmail.mailbox).filter(Fetchmail.mailbox.ilike(prefix+"%")))
    except:
        return ()

def _setupCliFetchmailParser(subp: ArgumentParser):
    def getBool(val):
        if not val.isdigit() and val not in ("yes", "no"):
            return val
        return bool(int(val)) if val.isdigit() else val == "yes"

    def addParameters(parser: ArgumentParser, init: bool=False):
        idef = lambda x: x if init else None
        bvals = (0, 1, "yes", "no")
        parser.add_argument("--active", default=idef(1), type=getBool, choices=bvals, help="Whether to activate the entry")
        parser.add_argument("--extraOptions", help="Additional fetchmail options")
        parser.add_argument("--fetchall", default=idef(0), type=getBool, choices=bvals, help="Also fetch seen mails")
        parser.add_argument("--keep", default=idef(1), type=getBool, choices=bvals, help="Keep fetched mails on the source server")
        parser.add_argument("--protocol", default=idef("IMAP"), choices=_proto, help="Protocol to use")
        parser.add_argument("--srcAuth", default=idef("password"), choices=_auths, help="Source server authentication")
        parser.add_argument("--srcFolder", help="Source folder")
        parser.add_argument("--srcPassword", required=init, help="Source user password")
        parser.add_argument("--srcServer", required=init, help="Source server adress")
        parser.add_argument("--srcUser", required=init, help="Source user")
        parser.add_argument("--sslCertCheck", default=idef(0), type=getBool, choices=bvals, help="Force SSL certificate check")
        parser.add_argument("--sslCertPath", help="Path to certificate directory or empty for system default")
        parser.add_argument("--useSSL", default=idef(1), type=getBool, choices=bvals, help="Enable SSL")

    sub = subp.add_subparsers()
    create = sub.add_parser("create", help="Create new fetchmail entry")
    create.add_argument("userspec", help="Target user").completer = userspecAutocomp
    create.add_argument("mailbox", nargs="?", help="Local mailbox address. Defaults to target user.")
    create.set_defaults(_handle=cliCreateFetchmail)
    addParameters(create, True)
    delete = sub.add_parser("delete", help="Delete fetchmail entry")
    delete.set_defaults(_handle=cliDeleteFetchmail)
    delete.add_argument("mbspec", nargs="?", help="Name of the mailbox or ID of the entry").completer = _fmlAutocomp
    delete.add_argument("-y", "--yes", action="store_true", help="Delete multiple entries without confirmation")
    list = sub.add_parser("list", help="List fetchmail entries")
    list.set_defaults(_handle=cliListFetchmail)
    list.add_argument("mbspec", nargs="?", help="Mailbox prefix or ID").completer = _fmlAutocomp
    list.add_argument("-f", "--filter", nargs="*", help="Filter by attribute, e.g. -f ID=42")
    list.add_argument("-s", "--sort", nargs="*", help="Sort by attribute, e.g. -s mailbox,desc")
    modify = sub.add_parser("modify", help="Modify fetchmail entry")
    modify.set_defaults(_handle=cliModifyFetchmail)
    modify.add_argument("mbspec", help="Name of the mailbox or ID of the entry").completer = _fmlAutocomp
    modify.add_argument("--mailbox", help="Local mailbox address")
    addParameters(modify)
    print = sub.add_parser("print", help="Print configuration line generated by fetchmail entry")
    print.set_defaults(_handle=cliPrintFetchmail)
    print.add_argument("mbspec", help="Name of the mailbox or ID of the entry").completer = _fmlAutocomp
    print.add_argument("-q", "--quiet", action="store_true", help="Do not print additional info")
    show = sub.add_parser("show", help="Show detailed information about fetchmail entry")
    show.set_defaults(_handle=cliShowFetchmail)
    show.add_argument("mbspec", help="Name of the mailbox or ID of the entry").completer = _fmlAutocomp
    show.add_argument("--password", action="store_true", help="Print source user password")
    writerc = sub.add_parser("write-rc", help="Write fetchmail configuration file")
    writerc.set_defaults(_handle=cliWriteFetchmailrc)
    writerc.add_argument("-f", "--force", action="store_true", help="Update even if no new accounts were created")
    writerc.add_argument("-o", "--out-file", metavar="FILE", default="/etc/fetchmailrc", help="Override output file")
    writerc.add_argument("-p", "--print", action="store_true", help="Print output")
    writerc.add_argument("-t", "--time", default="auto", help="Time since last update (minutes), or 'auto'")
    writerc.add_argument("-v", "--verbose", action="store_true", help="Be more verbose")


@Cli.command("fetchmail", _setupCliFetchmailParser, help="Fetchmail management")
def cliFetchmailStub(args):
    pass
