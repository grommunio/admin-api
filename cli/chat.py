# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 grommunio GmbH

from . import Cli, InvalidUseError
from argparse import ArgumentParser


def cliUsersChatFullDelete(args):
    cli = args._cli
    cli.require("DB")
    from orm import DB
    from orm.domains import Domains
    from orm.users import Users
    Users.query.update({Users.chatID: None })
    Domains.query.update({Domains.chatID: None })
    DB.session.commit()
    cli.print("All chat-IDs deleted.")


def _setupCliChat(subp: ArgumentParser):
    Cli.parser_stub(subp)
    sub = subp.add_subparsers()
    removeChat = sub.add_parser("remove-all", help="Set all chat-ids from domains and users to NULL")
    removeChat.set_defaults(_handle=cliUsersChatFullDelete)


@Cli.command("chat", _setupCliChat, help="Chat management")
def cliChatStub(args):
    raise InvalidUseError()
