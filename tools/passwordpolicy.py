# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 grommunio GmbH

"""Password policy for password changes by the user.

Configured in `options.passwordPolicy`:

    minLength       minimum number of characters (0 = no limit)
    minCharClasses  minimum number of character classes from lowercase,
                    uppercase, digits and other characters (0 = no limit)
    forbidUsername  reject the user name and its local part (default: false)
    blocklist       path to a file with one rejected password on each line.
                    A password is rejected only if it is equal to a full line.
                    Uppercase, lowercase and whitespace at the start or end
                    are ignored. Lines that start with `#` are comments. If
                    the file is set but cannot be read, all changes are
                    rejected.

The defaults do not set limits.
"""

import logging

from .config import Config

logger = logging.getLogger("passwordpolicy")


class PolicyUnavailableError(Exception):
    """The password policy cannot be checked, e.g. the blocklist cannot be read."""


def _charClasses(password):
    return sum((any(c.islower() for c in password),
                any(c.isupper() for c in password),
                any(c.isdigit() for c in password),
                any(not c.isalnum() for c in password)))


def _blocked(password, path):
    candidate = password.strip().casefold()
    with open(path, encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if line and not line.startswith("#") and line.casefold() == candidate:
                return True
    return False


def checkPassword(password, username=None):
    """Check a new password against the configured policy.

    Parameters
    ----------
    password : str
        The new password.
    username : str, optional
        The user's name (e-mail address), used by `forbidUsername`.

    Raises
    ------
    PolicyUnavailableError
        The blocklist is set but cannot be read.

    Returns
    -------
    str
        Error message if the password is rejected, or None if it is accepted
    """
    policy = Config["options"].get("passwordPolicy") or {}
    minLength = policy.get("minLength") or 0
    if len(password) < minLength:
        return "Password must be at least {} characters long".format(minLength)
    minClasses = policy.get("minCharClasses") or 0
    if _charClasses(password) < minClasses:
        return "Password must contain at least {} of: lowercase, uppercase, digits, other characters"\
               .format(minClasses)
    if policy.get("forbidUsername") and username:
        folded = password.casefold()
        if folded in (username.casefold(), username.split("@")[0].casefold()):
            return "Password must not be the user name"
    blocklist = policy.get("blocklist")
    if blocklist:
        try:
            if _blocked(password, blocklist):
                return "Password is not allowed"
        except OSError as err:
            logger.error("Cannot read password blocklist '{}': {}".format(blocklist, err))
            raise PolicyUnavailableError("Password policy unavailable - please contact your administrator")
    return None
