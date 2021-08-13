# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020-2021 grommunio GmbH

from mattermostdriver import Driver
from .config import Config
import logging
import random
import string

try:
    Grochat = Driver(Config["chat"]["connection"])
    Grochat.login()
    logging.info("Connected to grommunio-chat {scheme}://{login_id}@{url}:{port}{basepath}".format(**Grochat.driver))
except Exception as err:
    logging.error("Failed to connect to grommunio-chat: "+type(err).__name__+": "+" - ".join(str(arg) for arg in err.args))
    Grochat = None


def _addif(props, data, srcname, dstname):
    if srcname in props:
        data[dstname] = props[srcname]


def userToData(user):
    userdata = {"email": user.username, "username": user.username.replace("@", "_")}
    props = user.propmap
    _addif(props, userdata, "givenname", "first_name")
    _addif(props, userdata, "surname", "last_name")
    _addif(props, userdata, "nickname", "nickname")
    if user.chatID:
        userdata["id"] = user.chatID
    return userdata


def createUser(user):
    """Create grochat user from grommunio user."""
    if Grochat is None:
        return None
    try:
        if user.chatID:
            return Grochat.users.get_user(user.chatID)
        userdata = userToData(user)
        userdata["auth_service"] = "pam"
        userdata["password"] = "".join(random.choices(string.ascii_letters+string.digits, k=16))
        gcUser = Grochat.users.create_user(userdata)
        user.chatID = gcUser["id"]
        linkUser(user)
        return gcUser
    except Exception as err:
        logging.error("Failed to create user: "+type(err).__name__+": "+" - ".join(str(arg) for arg in err.args))


def updateUser(user, create=False):
    """Update grochat user from grommunio user."""
    if Grochat is None:
        return None
    isdata = isinstance(user, dict)
    if not isdata and user.chatID is None:
        return createUser(user) if create else None
    try:
        userdata = user if isdata else userToData(user)
        return Grochat.users.patch_user(userdata["id"], userdata)
    except Exception as err:
        logging.error("Failed to update user: "+type(err).__name__+": "+" - ".join(str(arg) for arg in err.args))


def setUserRoles(userID, roles):
    if Grochat is None:
        return None
    try:
        return Grochat.users.update_user_role(userID, {"roles": roles})
    except Exception as err:
        logging.error("Failed to update user: "+type(err).__name__+": "+" - ".join(str(arg) for arg in err.args))

def linkUser(user):
    """Add user to domain team."""
    if Grochat is None or not user.chatID or not user.domain.chatID:
        return None
    try:
        return Grochat.teams.add_user_to_team(user.domain.chatID, {"team_id": user.domain.chatID, "user_id": user.chatID})
    except Exception as err:
        logging.error("Failed to add user to team: "+type(err).__name__+": "+" - ".join(str(arg) for arg in err.args))


def activateUser(user, status):
    """Archive a user."""
    if Grochat is None or not user.chatID:
        return None
    try:
        return Grochat.users.update_user_active_status(user.chatID, {"active": status})
    except Exception as err:
        logging.error("Failed to delete user: "+type(err).__name__+": "+" - ".join(str(arg) for arg in err.args))


def getUser(userID):
    if Grochat is None or not userID:
        return None
    try:
        return Grochat.users.get_user(userID)
    except Exception as err:
        logging.error("Failed to find user: "+type(err).__name__+": "+" - ".join(str(arg) for arg in err.args))

def createTeam(domain):
    """Create team for domain."""
    if Grochat is None:
        return None
    try:
        if domain.chatID:
            return Grochat.teams.get_team(domain.chatID)
        teamname = "".join(c.lower() if c.isalnum() else hex(ord(c)) for c in domain.domainname)
        teamdata = {"name": teamname, "display_name": domain.title or domain.domainname, "type": "I"}
        gcTeam = Grochat.teams.create_team(teamdata)
        domain.chatID = gcTeam["id"]
        return gcTeam
    except Exception as err:
        logging.error("Failed to create team: "+type(err).__name__+": "+" - ".join(str(arg) for arg in err.args))


def activateTeam(domain, status):
    """Archive a domains team."""
    if Grochat is None or not domain.chatID:
        return None
    try:
        if status:
            resp = Grochat.client.make_request("post", "/teams/"+domain.chatID+"/restore")
            return resp.json() if resp.status_code == 200 else None
        else:
            return Grochat.teams.delete_team(domain.chatID)
    except Exception as err:
        logging.error("Failed to delete team: "+type(err).__name__+": "+" - ".join(str(arg) for arg in err.args))


def getTeam(teamID):
    if Grochat is None or not teamID:
        return None
    try:
        return Grochat.teams.get_team(teamID)
    except Exception as err:
        logging.error("Failed to find team: "+type(err).__name__+": "+" - ".join(str(arg) for arg in err.args))