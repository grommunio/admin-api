# -*- coding: utf-8 -*-
"""
Created on Fri Oct  2 16:28:13 2020

@copyright: grammm GmbH, 2020
"""


class Permissions:
    """Central Permissions class.

    Functions as a permission factory and provides easy permission checking.
    """

    preg = {}

    def __init__(self, *args):
        """Initialize permission object.

        Parameters
        ----------
        *args : Permission
            Permissions held by the object
        """
        self.permissions = args

    @classmethod
    def fromDB(cls, permissionsData=[]):
        """Initialize from database objects.

        Parameters
        ----------
        permissionsData : Iterable, optional
            List of objects with `name` and `param` attributes. The default is [].

        Returns
        -------
        Permissions
            Permissions object with permissions loaded from database
        """
        return Permissions(*(cls.preg[pData.permission](pData.params)
                             for pData in permissionsData if pData.permission in cls.preg))

    def has(self, permission):
        """
        Check if permission is represented by permissions object.

        Parameters
        ----------
        permission : Permission
            Requested permission

        Returns
        -------
        bool
            True if the requested permission is represented, False otherwise
        """
        return any(perm.permits(permission) for perm in self.permissions)

    def __contains__(self, permission):
        """Convenience alias for `has`.

        Parameters
        ----------
        permission : Permission
            Requested permission

        Returns
        -------
        bool
            True if the requested permission is represented, False otherwise
        """
        return self.has(permission)

    def __iter__(self):
        """Return permission iterator

        Returns
        -------
        iterator
            Iterator that iterates over the contained permission objects.
        """
        return self.permissions.__iter__()

    @classmethod
    def register(cls, name):
        """Class decorator to register a permission at the factory.

        Parameters
        ----------
        name : str
            Name of the permission

        Returns
        -------
        function
            Decorator function
        """
        def inner(obj):
            cls.preg[name] = obj
            return obj
        return inner

    @classmethod
    def knownPermissions(cls):
        """List names of registered permissions.

        Returns
        -------
        tuple
            List of registered permissions
        """
        return tuple(cls.preg.keys())

    @classmethod
    def create(cls, name, params=None):
        """Create permission by name.

        Parameters
        ----------
        name : str
            Name of the permission
        params : Any, optional
            Parameters passed to the permission. The default is None.

        Raises
        ------
        KeyError
            No permission with this name exists

        Returns
        -------
        Permission
            New permission.
        """
        if name not in cls.preg:
            raise KeyError("Unknown permission '{}'".format(name))
        return cls.preg[name](params)

    @staticmethod
    def sysadmin():
        """Create Permissions object with system admin permissions.

        Returns
        -------
        Permissions
            Permissions object with system admin permissions.
        """
        return Permissions(SystemAdminPermission())

    def capabilities(self):
        """Return set of capabilities from all represented permissions.

        Returns
        -------
        set
            Union of capabilities from all permissions
        """
        return set.union(*(permission.capabilities() for permission in self.permissions))


class PermissionBase:
    """Base class for permissions.

    Implements `permits` method, automatically dispatching the correct, permission specific, `_permits` method.
    """

    def __init__(self):
        """Default constructor."""
        pass

    def permits(self, permission):
        """Check if `permission` is represented by the object.

        Checks if self is an instance of `permission` and, if so, dispatches the `_permits` method of the correct base class.

        Parameters
        ----------
        permission : PermissionBase
            Permission to check for.

        Returns
        -------
        bool
            True if `permission` is represented by this object, False otherwise
        """
        permission_t = type(permission)
        if type(self) == permission_t:
            self._permits(permission)
        if isinstance(self, permission_t):
            return permission_t._permits(self, permission)
        return False

    def capabilities(self):
        """Get a set of capabilities provided by this permission.

        Returns
        -------
        set
            Empty set
        """
        return set()

@Permissions.register("SystemAdmin")
class SystemAdminPermission:
    """System admin permission.

    Permits every action by default.
    """

    def __init__(self, *args, **kwargs):
        """Initialize permission.

        Parameters
        ----------
        *args : Any
            Ignored.
        **kwargs : Any
            Ignored.
        """
        pass

    def permits(self, permission):
        """Return True.

        Parameters
        ----------
        permission : PermissionBase
            Permission to check

        Returns
        -------
        bool
            Always True
        """
        return True

    def __repr__(self):
        """Return string representation."""
        return "SystemAdminPermission()"

    def capabilities(self):
        """Get a set of capabilities provided by this permission.

        Returns
        -------
        set
            Set containg "SystemAdmin" capability.
        """
        return {"SystemAdmin"}


@Permissions.register("DomainAdmin")
class DomainAdminPermission(PermissionBase):
    """Permission class representing admin permissions for a domain.

    Can represent permission for a specific domain, or domains in general (when parameter is '*').

    Note that the special parameter '*' is permissive in both directions:
    Requesting a DomainAdminPermission with parameter '*' and
    requesting DomainAdminPermission for a specific domain from a permission with parameter '*' will both return True.
    """

    def __init__(self, domainID):
        """Initialize domain admin permission.

        Parameters
        ----------
        domainID : int or '*'
            Domain ID this permission is for, or '*' to match all domains

        Raises
        ------
        ValueError
            `domainID` is neither an integer nor special identifier '*'
        """
        if domainID != "*" and not isinstance(domainID, int):
            raise ValueError("DomainAdminPermission parameter must be integer or '*'")
        self.__domain = domainID

    def _permits(self, permission):
        """Check if permission is represented.

        Parameters
        ----------
        permission : DomainAdminPermission
            Permission to check for equality

        Returns
        -------
        bool
            True if domain IDs match or either is a wildcard domain, False otherwise
        """
        return "*" in (self.__domain, permission.__domain) or self.__domain == permission.__domain

    def __repr__(self):
        """Return string representation."""
        return "DomainAdminPermission({})".format(repr(self.__domain))

    def capabilities(self):
        """Get a set of capabilities provided by this permission.

        Returns
        -------
        set
            Set containg "DomainAdmin" capability.
        """
        return {"DomainAdmin"}

    @property
    def domainID(self):
        """Return domain parameter."""
        return self.__domain
