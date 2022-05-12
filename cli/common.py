# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH


def domainFilter(domainSpec, *filters):
    from orm.domains import Domains
    from sqlalchemy import and_
    return and_(True if domainSpec is None else
                Domains.ID == domainSpec if domainSpec.isdigit() else
                Domains.domainname.ilike(domainSpec+"%"), *filters)


def domainCandidates(domainSpec, *filters):
    from orm.domains import Domains
    return Domains.query.filter(domainFilter(domainSpec, *filters))


def userFilter(userSpec, *filters):
    from orm.users import Users
    from sqlalchemy import and_
    return and_(True if userSpec is None else
                Users.ID == userSpec if userSpec.isdigit() else
                Users.username.ilike(userSpec+"%"), *filters)


def userCandidates(userSpec, *filters):
    from orm.users import Users
    return Users.query.filter(userFilter(userSpec, *filters))


def userspecAutocomp(prefix, **kwargs):
    from . import Cli
    if Cli.rlAvail:
        from orm.users import Users
        return (user.username for user in userCandidates(prefix).with_entities(Users.username))
    else:
        return ()


class NotFound(dict):
    pass


def getKey(c, keyspec):
    if keyspec:
        for key in keyspec:
            c = c.get(key, NotFound()) if key else c
    return c


def proptagCompleter(prefix, addSuffix="", **kwargs):
    from tools.constants import PropTags
    PropTags.lookup(None)
    c = []
    if prefix == "" or prefix[0].islower():
        c += [tag.lower()+addSuffix for value, tag in PropTags._lookup.items() if isinstance(value, int)]
    if prefix == "" or prefix[0].isupper():
        c += [tag.upper()+addSuffix for value, tag in PropTags._lookup.items() if isinstance(value, int)]
    if prefix == "" or prefix[0] == "0" and (len(prefix) <= 2 or not prefix[2:].isupper()):
        c += ["0x{:08x}{}".format(value, addSuffix) for value in PropTags._lookup.keys() if isinstance(value, int)]
    if prefix == "" or prefix[0] == "0" and (len(prefix) <= 2 or not prefix[2:].islower()):
        c += ["0x{:08X}{}".format(value, addSuffix) for value in PropTags._lookup.keys() if isinstance(value, int)]
    if prefix == "" or prefix.isnumeric():
        c += [str(value)+addSuffix for value in PropTags._lookup.keys() if isinstance(value, int)]
    return c
