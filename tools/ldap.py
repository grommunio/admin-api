# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2023 grommunio GmbH

import logging
from orm import DB
from services import Service, ServiceUnavailableError
from sqlalchemy.exc import IntegrityError
from tools.DataModel import MismatchROError, InvalidAttributeError
from tools.misc import RecursiveDict

logger = logging.getLogger("ldap")


def downsyncUser(user, externID=None):
    """Synchronize a user from LDAP.

    Must not be called on group objects.

    Parameters
    ----------
    user : orm.Users
        User object to synchronize
    externID : bytes, optional
        Reassign externID to this ID. The default is None.

    Returns
    -------
    str
        Message
    int
        HTTP-like result code
    """
    userdata = None
    with Service("ldap", user.orgID, errors=Service.SUPPRESS_INOP) as ldap:
        userdata = ldap.downsyncUser(externID or user.externID, user.properties)

    if userdata is None:
        return "Failed to get user data", 500
    try:
        try:
            user.fromdict(userdata)
        except ServiceUnavailableError:
            logger.warning(f"Failed to synchronize store of user {user.username} - service unavailable")
        user.externID = externID or user.externID
        DB.session.commit()
        return "success", 200
    except (InvalidAttributeError, MismatchROError, ValueError) as err:
        DB.session.rollback()
        return err.args[0], 400
    except IntegrityError as err:
        DB.session.rollback()
        return err.orig.args[1], 400


def downsyncGroup(mlist, externID=None):
    """Synchronize group from LDAP.

    Must not be called on user object.

    Parameters
    ----------
    mlist : orm.MLists
        Group object to synchronize
    externID : bytes, optional
        Reassign externID to this ID. The default is None.

    Returns
    -------
    str
        Message
    int
        HTTP-like result code
    """
    listdata = None
    with Service("ldap", mlist.user.orgID, errors=Service.SUPPRESS_INOP) as ldap:
        listdata = ldap.downsyncUser(externID or mlist.user.externID, mlist.user.properties)

    if listdata is None:
        return "Failed to get group data", 500
    try:
        mlist.fromdict(listdata)
        mlist.user.externID = externID or mlist.user.externID
        DB.session.commit()
        return "success", 200
    except (InvalidAttributeError, MismatchROError, ValueError) as err:
        DB.session.rollback()
        return err.args[0], 400
    except IntegrityError as err:
        DB.session.rollback()
        return err.orig.args[1], 400


def downsyncObject(user, externID=None):
    """Synchronize user object from LDAP.

    Dispatches to appropriate synchronization function (user or group)
    and updates group members if requested.

    Parameters
    ----------
    user : TYPE
        DESCRIPTION.
    externID : TYPE, optional
        DESCRIPTION. The default is None.

    Returns
    -------
    str
        Message
    int
        HTTP-like status code

    """
    if user.properties["displaytypeex"] != 1:
        return downsyncUser(user, externID)
    from orm.mlists import MLists
    mlist = MLists.query.filter(MLists.listname == user.username).first()
    if not mlist:
        return "No such group", 400
    mlist.listname = mlist.listname.lower()
    message, code = downsyncGroup(mlist, externID)
    return message, code


def importContact(candidate, ldap, orgID, syncExisting=False, domains=None, **kwargs):
    """Import contact from LDAP.

    Parameters
    ----------
    candidate : services.ldap.SearchResult
        Object to synchronize
    ldap : services.ldap.LdapService
        LDAP connection to use
    orgID : int
        Organization ID to limit import to
    syncExisting : bool, optional
        Whether to implicitely update existing objects. The default is False.
    domains : Iterable[int], optional
        Set of domain IDs to import contacts to or None for no restriction. The default is None

    Returns
    -------
    synced : list[orm.users.Users]
        List of synchronized users
    imported : list[orm.users.Users]
        List of imported users
    errors : list[tuple[str, int]]
        List of (message, code) tuple containing error information.
    """
    from orm.domains import Domains
    from orm.users import Users

    synced = []
    imported = []
    errors = []
    domains = Domains.query.filter(Domains.orgID == orgID, Domains.ID.in_(domains) if domains else True)\
                           .with_entities(Domains.ID, Domains.domainname).all()
    existing = Users.query.filter(Users.orgID == orgID, Users.externID == candidate.ID).all()
    if syncExisting:
        for user in existing:
            error, code = downsyncUser(user)
            if code != 200:
                errors.append((f"Failed to synchronize {user.username}: {error}", code))
            else:
                synced.append(user)
    existingDomains = {user.domainID for user in existing}
    domains = [domain for domain in domains if domain.ID not in existingDomains]
    for domain in domains:
        contactData = ldap.downsyncUser(candidate.ID)
        contactData["domainID"] = domain.ID
        result, code = Users.mkContact(contactData, candidate.ID)
        if code != 201:
            errors.append((f"Failed to import contact {candidate.email} into {domain.domainname}: {result}", code))
        else:
            imported.append(result)
    return synced, imported, errors


def importUser(candidate, ldap, force=False, lang="", **kwargs):
    """Import user from LDAP

    Parameters
    ----------
    candidate : services.ldap.SearchResult
        Object to synchronize
    ldap : services.ldap.LdapService
        LDAP connection to use
    force : bool, optional
        Force import if user exists and is linked to a different object. The default is False.
    lang : str, optional
        Language to set for the user. The default is "".

    Returns
    -------
    str | orm.Users
        User object if successful, error message otherwise
    int
        HTTP-like result code
    """
    from orm.misc import DBConf
    from orm.domains import Domains
    from orm.users import Users

    existing = Users.query.filter(Users.username == candidate.email).first()
    if existing:
        if existing.externID == candidate.ID or force:
            result, code = downsyncUser(existing, candidate.ID)
            return existing if code == 200 else result, code
        msg = "and is linked to another LDAP object" if existing.externID else "locally"
        return candidate.type.capitalize()+" already exists "+msg, 400

    domain = Domains.query.filter(Domains.domainname == candidate.email.split("@")[1]).with_entities(Domains.ID).first()
    defaults = RecursiveDict({"user": {}, "domain": {}})
    defaults.update(DBConf.getFile("grommunio-admin", "defaults-system", True))
    defaults.update(DBConf.getFile("grommunio-admin", "defaults-domain-"+str(domain.ID)))
    defaults = defaults.get("user", {})

    userdata = ldap.downsyncUser(candidate.ID)
    defaults.update(RecursiveDict(userdata))
    defaults["lang"] = lang or defaults.get("lang", "")
    return Users.create(defaults, externID=candidate.ID)


def importGroup(candidate, ldap, force=False, syncMembers=False, **kwargs):
    """Import group from LDAP.

    Parameters
    ----------
    candidate : services.ldap.SearchResult
        Object to synchronize
    ldap : services.ldap.LdapService
        LDAP connection to use
    force : bool, optional
        Force import if user exists and is linked to a different object. The default is False.
    syncMembers : bool, optional
        Whether to sync group members after importing. The default is False.

    Returns
    -------
    str | orm.MLists
        Group object if successful, error message otherwise
    int
        HTTP-like result code
    """
    from orm.mlists import MLists
    from orm.users import Users
    xuser = Users.query.filter(Users.username == candidate.email).first()
    xlist = MLists.query.filter(MLists.listname == candidate.email).first()
    if xuser and xlist:
        if xuser.externID == candidate.ID or force:
            result, code = downsyncGroup(xlist, candidate.ID)
            return xlist if code == 200 else result, code
        msg = "and is linked to another LDAP object" if xuser.externID else "locally"
        return candidate.type.capitalize()+" already exists "+msg, 400

    listdata = ldap.downsyncUser(candidate.ID)
    error = MLists.checkCreateParams(listdata)
    if error:
        return error, 400
    try:
        mlist = MLists(listdata)
        mlist.user.externID = candidate.ID
        DB.session.add(mlist)
        DB.session.commit()
        if syncMembers:
            syncGroupMembers(mlist.user.orgID, candidate, ldap)
        return mlist, 201
    except Exception as err:
        return type(err).__name__+": "+" - ".join(str(arg) for arg in err.args), 500


def importObject(candidate, ldap, **kwargs):
    """Import LDAP object

    Automatically calls the appropriate function according to the candidates type

    Parameters
    ----------
    candidate : services.ldap.SearchResult
        LDAP object to import
    ldap : services.ldap.LdapService
        LDAP connection to use
    **kwargs : Any
        Keyword arguments forwarded to the importer

    Raises
    ------
    TypeError
        LDAP object has an invalid type

    Returns
    -------
    dict
        Result object
    int
        HTTP-like status code
    """
    if candidate.type == "contact":
        synced, imported, failed = importContact(candidate, ldap, **kwargs)
        return {"message": f"{len(synced)} synced, {len(imported)} imported, {len(failed)} failed"}, 200
    if candidate.type == "group":
        result, code = importGroup(candidate, ldap, **kwargs)
        return {"message": result} if isinstance(result, str) else result.user.fulldesc(), code
    if candidate.type == "user":
        result, code = importUser(candidate, ldap, **kwargs)
        return {"message": result} if isinstance(result, str) else result.fulldesc(), code
    raise TypeError(f"Unknown object type '{candidate.type}'")


def syncGroupMembers(orgID, ldapgroup, ldap):
    """Synchronize group members.

    Parameters
    ----------
    orgID : int
        Organization ID to limit members to.
    ldapgroup : services.ldap.SearchResult
        LDAP group object to synchronize.
    ldap : services.ldap.LdapService
        LDAP connection to use

    Returns
    -------
    int | NoneType
        Number of users that were added to the group or None if group not found
    int | NoneType
        Number of users that were removed from the group or None if group not found
    """
    from orm.mlists import Associations, MLists
    from orm.users import Users
    group = MLists.query.filter(MLists.listname == ldapgroup.email).first()
    if group is None or group.user.orgID != orgID:
        return None, None
    users = {user.externID: user.username
             for user in Users.query.filter(Users.orgID == orgID, Users.externID != None)
                                    .with_entities(Users.externID, Users.username)}
    assocs = {assoc.username: assoc for assoc in Associations.query.filter(Associations.listID == group.ID).all()}
    add = []
    for member in ldap.searchUsers(attributes="idonly", customFilter=ldap.groupMemberFilter(ldapgroup.DN)):
        assoc = assocs.pop(users.get(member.ID), None)
        if assoc is None and member.ID in users:  # Do nothing if already associated or not known
            add.append((users[member.ID], group.ID))
    for assoc in assocs.values():
        DB.session.delete(assoc)
    DB.session.flush()  # necessary to fix case-confusions (i.e. User@example.org -> user@example.org)
    DB.session.add_all([Associations(memberEmail, groupID) for memberEmail, groupID in add])
    DB.session.commit()
    return len(add), len(assocs)
