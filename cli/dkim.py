# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Alexander Gott

from . import Cli, InvalidUseError, ArgumentParser


def cliDkimSync(args):
    cli = args._cli
    cli.require("DB")
    from tools.dnsHealth import syncDkimKeysToRedis
    pushed, failed = syncDkimKeysToRedis()
    if pushed == 0 and failed == 0:
        cli.print(cli.col("No DKIM keys to sync (database empty or schema too old)", "yellow"))
        return 0
    cli.print("Pushed {} DKIM key(s) into the local keystore".format(pushed))
    if failed:
        cli.print(cli.col("{} key(s) failed - retried by grommunio-admin-dkim-sync.timer".format(failed), "red"))
        return 1
    return 0


def cliDkimImport(args):
    cli = args._cli
    cli.require("DB")
    from tools.dnsHealth import importLegacyDkimFiles
    error = importLegacyDkimFiles()
    if error is None:
        cli.print("DKIM legacy key file import checked")
        return 0
    cli.print(cli.col("DKIM legacy key file import failed: " + error, "red"))
    return 1


def _setupCliDkimParser(subp: ArgumentParser):
    Cli.parser_stub(subp)
    sub = subp.add_subparsers()
    sync = sub.add_parser("sync", help="Push all DKIM keys from the database into the local keystore")
    sync.set_defaults(_handle=cliDkimSync)
    import_ = sub.add_parser("import", help="Import DKIM key files of previous versions (once per node)")
    import_.set_defaults(_handle=cliDkimImport)


@Cli.command("dkim", _setupCliDkimParser, help="DKIM key management")
def cliDkimStub(args):
    raise InvalidUseError()
