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


def _setDefault(file, key, value):
    """Set (or remove, if value is None) a key of a grommunio-admin defaults file."""
    from orm.misc import DB, DBConf
    entry = DBConf.query.filter(DBConf.service == "grommunio-admin", DBConf.file == file, DBConf.key == key).first()
    if value is None:
        if entry is not None:
            DB.session.delete(entry)
    elif entry is None:
        DB.session.add(DBConf(service="grommunio-admin", file=file, key=key, value=value))
    else:
        entry.value = value


def cliChatSso(args):
    cli = args._cli
    cli.require("DB")
    from orm import DB
    from orm.domains import Domains
    from orm.users import Users
    from services import Service, ServiceUnavailableError
    enable = args.mode == "enable"
    domains = []
    for name in args.domain or ():
        domain = Domains.query.filter(Domains.domainname == name).first()
        if domain is None:
            cli.print(cli.col("Domain '{}' not found".format(name), "red"))
            return 1
        domains.append(domain)
    try:
        with Service("chat") as chat:
            service = chat.ssoService() if enable else None
            users = Users.query.filter(Users.chatID != None)
            if domains:
                users = users.filter(Users.domainID.in_([domain.ID for domain in domains]))
            users = users.all()
            accounts = {account["id"]: account for account in chat.getUsers([user.chatID for user in users])}
            changed = skipped = 0
            for user in users:
                account = accounts.get(user.chatID)
                if account is None:
                    cli.print(cli.col("{}: chat account {} not found".format(user.username, user.chatID), "yellow"))
                    continue
                current = account.get("auth_service")
                if current == (service or "pam") or (not enable and current not in ("keycloak", "gitlab")):
                    skipped += 1
                    continue
                try:
                    chat.setUserAuth(user, service)
                    changed += 1
                except Exception as err:
                    cli.print(cli.col("{}: {}".format(user.username, err), "yellow"))
    except ServiceUnavailableError as err:
        cli.print(cli.col("grommunio-chat is not available: {}".format(err), "red"))
        return 2
    except Exception as err:
        cli.print(cli.col("grommunio-chat request failed: {}".format(err), "red"))
        return 3
    # Defaults decide the login method of accounts created later
    value = "true" if enable else "false"
    if domains:
        for domain in domains:
            _setDefault("defaults-domain-"+str(domain.ID), "user.keycloak", value)
    else:
        _setDefault("defaults-system", "user.keycloak", value)
        for domain in Domains.query.with_entities(Domains.ID):
            _setDefault("defaults-domain-"+str(domain.ID), "user.keycloak", None)
    DB.session.commit()
    cli.print("Chat accounts moved to {}: {}, unchanged: {}".format(service or "pam", changed, skipped))


def _setupCliChat(subp: ArgumentParser):
    Cli.parser_stub(subp)
    sub = subp.add_subparsers()
    removeChat = sub.add_parser("remove-all", help="Set all chat-ids from domains and users to NULL")
    removeChat.set_defaults(_handle=cliUsersChatFullDelete)
    sso = sub.add_parser("sso", help="Switch chat accounts between single sign-on and local login")
    sso.set_defaults(_handle=cliChatSso)
    sso.add_argument("mode", choices=("enable", "disable"), help="Login method to switch to")
    sso.add_argument("-d", "--domain", action="append", help="Only affect users of this domain (can be repeated)")


@Cli.command("chat", _setupCliChat, help="Chat management")
def cliChatStub(args):
    raise InvalidUseError()
