# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH

from . import ServiceHub, ServiceUnavailableError

from mattermostdriver import Driver
from mattermostdriver.exceptions import InvalidOrMissingParameters, ResourceNotFound, ContentTooLarge
from requests.exceptions import ConnectionError, HTTPError

import random
import string


def handleGrochatExceptions(service, error):
    if isinstance(error, ConnectionError):
        return ServiceHub.SUSPENDED
    elif isinstance(error, (InvalidOrMissingParameters, ResourceNotFound, ContentTooLarge)):
        raise ValueError("grochat: invalid data")


@ServiceHub.register("chat", handleGrochatExceptions, maxreloads=3)
class GrochatService:
    def __init__(self):
        from tools.config import Config
        try:
            self.driver = Driver(Config["chat"]["connection"])
            self.driver.login()
        except Exception as err:
            raise ServiceUnavailableError("Failed to connect to grommunio-chat", err)

    @staticmethod
    def _addif(props, data, srcname, dstname):
        if srcname in props:
            data[dstname] = props[srcname]

    @staticmethod
    def userToData(user):
        userdata = {"email": user.username, "username": user.username.replace("@", "_")}
        props = user.propmap
        GrochatService._addif(props, userdata, "givenname", "first_name")
        GrochatService._addif(props, userdata, "surname", "last_name")
        GrochatService._addif(props, userdata, "nickname", "nickname")
        if user.chatID:
            userdata["id"] = user.chatID
        return userdata

    def createUser(self, user):
        """Create grochat user from grommunio user."""
        if user.chatID:
            return self.driver.users.get_user(user.chatID)
        userdata = self.userToData(user)
        userdata["auth_service"] = "pam"
        userdata["password"] = "".join(random.choices(string.ascii_letters+string.digits, k=16))
        gcUser = self.driver.users.create_user(userdata)
        user.chatID = gcUser["id"]
        self.linkUser(user)
        return gcUser

    def updateUser(self, user, create=False):
        """Update grochat user from grommunio user."""
        isdata = isinstance(user, dict)
        if not isdata and user.chatID is None:
            return self.createUser(user) if create else None
        userdata = user if isdata else self.userToData(user)
        return self.driver.users.patch_user(userdata["id"], userdata)

    def setUserRoles(self, userID, roles):
        return self.driver.users.update_user_role(userID, {"roles": roles})

    def linkUser(self, user):
        """Add user to domain team."""
        if not user.chatID or not user.domain.chatID:
            return None
        return self.driver.teams.add_user_to_team(user.domain.chatID, {"team_id": user.domain.chatID, "user_id": user.chatID})

    def activateUser(self, user, status):
        """Archive a user."""
        if not user.chatID:
            return None
        return self.driver.users.update_user_active_status(user.chatID, {"active": status})

    def getUser(self, userID):
        if not userID:
            return None
        try:
            return self.driver.users.get_user(userID)
        except HTTPError:
            return None

    def createTeam(self, domain):
        """Create team for domain."""
        if domain.chatID:
            return self.driver.teams.get_team(domain.chatID)
        teamname = "".join(c.lower() if c.isalnum() else hex(ord(c)) for c in domain.domainname)
        teamdata = {"name": teamname, "display_name": domain.title or domain.domainname, "type": "I"}
        gcTeam = self.driver.teams.create_team(teamdata)
        domain.chatID = gcTeam["id"]
        return gcTeam

    def activateTeam(self, domain, status):
        """Archive a domains team."""
        if not domain.chatID:
            return None
        if status:
            resp = self.driver.client.make_request("post", "/teams/"+domain.chatID+"/restore")
            return resp.json() if resp.status_code == 200 else None
        else:
            return self.driver.teams.delete_team(domain.chatID)

    def getTeam(self, teamID):
        if not teamID:
            return None
        return self.driver.teams.get_team(teamID)
