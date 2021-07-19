# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH

from .misc import createMapping

import os
import shlex

keyCommits = {"postconf -e $ENTRY"}
fileCommits = {}
serviceCommits = {"systemctl reload $SERVICE",
                  "systemctl restart $SERVICE"}

def subVars(command, data):
    out = ""
    index = command.find("$")
    last = 0
    while index != -1:
        out += command[last:index]
        if index == len(command)-1:
            return out+"$"
        if command[index+1] == "$":
            last = index+2
            out += "$"
        else:
            last = index+1
            while last != len(command) and command[last].isalnum():
                last += 1
            token = command[index+1:last]
            out += shlex.quote(data[token]) if token in data else ""
        index = command.find("$", last)
    out += command[last:]
    return out


def _commitKey(exprmap, service, file, key):
    command = exprmap["commit_key"]
    if command not in keyCommits:
        return "Command not allowed for key trigger"
    if "$" in command:
        from orm.misc import DBConf
        entry = DBConf.query.filter(DBConf.service == service, DBConf.file == file, DBConf.key == key)\
                            .with_entities(DBConf.value).first()
        data = dict(KEY=key, VALUE=entry.value, ENTRY=key+"="+entry.value, FILENAME=file, SERVICE=service)
        command = subVars(command, data)
    ret = os.system(command)
    if ret:
        return "Command exited with status code "+str(ret)


def _commitFile(exprmap, service, file):
    command = exprmap["commit_file"]
    if command not in fileCommits:
        return "Command not allowed for file trigger"
    if "$" in command:
        from orm.misc import DBConf
        entries = DBConf.query.filter(DBConf.service == service, DBConf.file == file)\
                              .with_entities(DBConf.key, DBConf.value).all()
        filedata = "\n".join(entry.key+"="+entry.value for entry in entries)
        data = dict(FILE=filedata, FILENAME=file, SERVICE=service)
        command = subVars(command, data)
    ret = os.system(command)
    if ret:
        return "Command exited with status code "+str(ret)


def _commitService(exprmap, service):
    command = exprmap.get("commit_service")
    if command is not None:
        if command not in serviceCommits:
            return "Command not allowed for service trigger"
        command = subVars(command, {"SERVICE": service})
        ret = os.system(command)
        if ret:
            return "Command exited with status code "+str(ret)


def commit(service, file=None, key=None):
    """Commit configuration changes.

    Parameters
    ----------
    service : str
        Name of the service
    file : str, optional
        Name of the file or None to commit the service
    key : str, optional
        Name of the key or None to commit the file

    Returns
    -------
    str
        Error message or None if successful
    """
    from orm.misc import DBConf
    exprs = DBConf.query.filter(DBConf.service == "grommunio-dbconf", DBConf.file == service, DBConf.key.like("commit_%"))\
                        .with_entities(DBConf.key, DBConf.value).all()
    if len(exprs) == 0:
        return None
    exprmap = createMapping(exprs, lambda x: x.key, lambda x: x.value)
    if key is not None and "commit_key" in exprmap:
        return _commitKey(exprmap, service, file, key)
    if file is not None and "commit_file" in exprmap:
        return _commitFile(exprmap, service, file)
    return _commitService(exprmap, service)
