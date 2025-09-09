# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grommunio GmbH

import logging


class ServiceUnavailableError(Exception):
    """Service not available.

    Thrown to indicate that the service is not available,
    either because initialization failed or an error occurred
    that is typically caused by the external service being unreachable
    (in contrast to errors caused by e.g. faulty data).

    When thrown in a service constructor to indicate that reloading
    at a later time may resolve the issue
    (putting the service in SUSPENDED state)."""
    pass


class ServiceDisabledError(Exception):
    """Service is manually disabled.

    Should be thrown in service constructor to indicate
    that the service is theoretically available,
    but was disabled manually and can be reactivated later."""
    pass


class InstanceDefault(Exception):
    """Service parametrization not supported.

    Thrown in the service constructor to indicate that parametrization is
    either not supported or the given parameters would offer the same
    functionality the default instance does."""


class _ServiceHubMeta(type):
    def __contains__(cls, value):
        return value in cls._services

    def __iter__(cls):
        return iter(cls._services.values())

    def __getitem__(cls, item):
        return cls._services[item]


class ServiceHub(metaclass=_ServiceHubMeta):
    _services = {}
    _instances = {}

    UNINITIALIZED = -1  # State has not been set
    LOADED = 0          # Service is available
    UNAVAILABLE = 1     # Temporarily unavailable, might become available automatically
    SUSPENDED = 2       # Needs to be reloaded in order to work
    ERROR = 3           # Fatal error
    DISABLED = 4        # Ok, but disabled manually

    _names = {UNINITIALIZED: "UNLOADED",
              LOADED: "LOADED",
              UNAVAILABLE: "UNAVAILABLE",
              SUSPENDED: "SUSPENDED",
              ERROR: "ERROR",
              DISABLED: "DISABLED"}

    class ServiceInfo:
        def __init__(self, name, mgrclass, exchandler, maxreloads, maxfailures, reloadlocktime, argspec, argname):
            self._argname = argname
            self._argspec = argspec
            self._maxfailures = maxfailures
            self._maxreloads = maxreloads
            self._name = name
            self._reloadlocktime = reloadlocktime
            self.exchandler = exchandler
            self.logger = logging.getLogger(self._name)
            self.mgrclass = mgrclass

        def checkArgs(self, *args):
            for spec in self._argspec:
                if len(spec) != len(args):
                    continue
                try:
                    return tuple(t(a) for t, a in zip(spec, args))
                except Exception:
                    pass
            raise ValueError("Invalid service parameters")

    class ServiceInstance:
        def __init__(self, service, *args):
            self._args = args
            self._failures = 0
            self._lastreload = 0
            self._name = ServiceHub.servicename(service._name, *args)
            self._reloads = 0
            self._service = service
            self._state = ServiceHub.UNINITIALIZED
            self.exc = None
            self.logger = service.logger.getChild("".join("{:02x}".format(x) for x in self._name.encode("utf8")))
            self.logger.name = self.name
            self.manager = None
            self.load()

        def __repr__(self):
            statename = {-1: "UNINITIALIZED", 0: "LOADED", 1: "UNAVAILABLE", 2: "SUSPENDED", 3: "ERROR"}
            return "<Service '{}' state {}>".format(self.name, statename.get(self._state))

        def _checkArgs(self):
            return self._service.checkArgs(*self._args)

        def disable(self):
            self.state = ServiceHub.DISABLED
            self.exc = ServiceDisabledError("Service disabled manually")

        def failed(self, newstate, exception):
            self._failures += 1
            self.exc = exception
            if self._service._maxfailures is not None and self._failures > self._service._maxfailures:
                self.state = ServiceHub.ERROR
                self._failures = self._service._maxfailures
                self.logger.info("Service deactivated after too many errors")
                return False
            self.state = newstate
            return True

        def load(self, force_reload=False):
            from time import time
            if (self._state not in (ServiceHub.UNINITIALIZED, ServiceHub.SUSPENDED) or
               time()-self._lastreload < self._service._reloadlocktime) and not force_reload:
                return
            self._reloads += 1
            try:
                self._checkArgs()
                self.manager = self._service.mgrclass(*self._args)
                self.state = ServiceHub.LOADED
                self._reloads = 0
                self.logger.info("Service loaded successfully")
                return
            except ServiceUnavailableError as err:
                self.exc = err
                self.logger.warning("Failed to load service: "+" - ".join(str(arg) for arg in err.args))
                self.state = ServiceHub.SUSPENDED if self._reloads <= self._service._maxreloads else ServiceHub.ERROR
                self._reloads = min(self._reloads, self._service._maxreloads)
            except ServiceDisabledError as err:
                self.exc = err
                self.logger.warning("Failed to load service: "+err.args[0])
                self.state = ServiceHub.DISABLED
            except InstanceDefault:
                raise
            except Exception as err:
                self.exc = err
                self.logger.error("Failed to load service: "+" - ".join(str(arg) for arg in err.args))
                self.state = ServiceHub.ERROR
            self._lastreload = time()
            self.manager = None

        @property
        def available(self):
            return self.state not in (ServiceHub.SUSPENDED, ServiceHub.ERROR, ServiceHub.DISABLED)

        @property
        def failures(self):
            return self._failures

        @property
        def maxfailures(self):
            return self._service._maxfailures

        @property
        def maxreloads(self):
            return self._service._maxreloads

        @property
        def name(self):
            return self._name

        @property
        def reloads(self):
            return self._reloads

        @property
        def state(self):
            return self._state

        @state.setter
        def state(self, value):
            newstate = value if ServiceHub.UNINITIALIZED <= value <= ServiceHub.DISABLED else ServiceHub.ERROR
            if newstate != self._state:
                self.logger.debug("State changed {} -> {}".format(self.statename, ServiceHub.statename(newstate)))
            self._state = newstate

        @property
        def statename(self):
            return ServiceHub.statename(self._state)

    @classmethod
    def register(cls, name, exchandler=lambda *args, **kwargs: None, maxreloads=0, maxfailures=None, reloadlocktime=1,
                 argspec=((),), argname=None):
        """Decorator to register a new service provider class.

        Register a new class as service provider.

        An exception handler function can be defined taking the service instance and exception raised in the service context,
        returning either None (indicating that the exception was not handled) or the new service state and optionally
        an error message (indicating that the original exception was handled, throwing a ServiceUnavailableException instead).
        This provides a convenient way to react to exception resulting from lost connections and put automatic reloading and
        deactivation mechanics to use.

        `maxreloads` and `maxfailures` provide limits which, when reached, will permanently disable a service
        (the service can still be recovered with force_reload).
        `maxreloads` is the maximum number of automatic reloads, i.e. number of failed load operations.
        `maxfailures` is the maximum number of exceptions handled by the exception handler

        `reloadlocktime` can be used for rate-limiting automatic reloads. This can prevent that a short temporary downtime
        of a service permanently disables it because it is requested multiple times in rapid succession.

        Parameters
        ----------
        name : str
            Name of the service.
        exchandler : function, optional
            Exception handler. The default is the empty function.
        **kwargs : None
            Keyword argument dict, only for compatibility
        maxreloads : int, optional
            Number of acceptable automatic reloads before service enters ERROR state. The default is 0.
        maxfailures : int, optional
            Number acceptable load error before service enters ERROR state or None for indefinite reloading.
            The default is None.
        reloadlocktime : float, optional
            Minimum time (in seconds) between automatic reloads. The default is 1.
        argspec : tuple of tuples of types, optional
            Allowed types for arguments. Default is `((),)` (no arguments).
        argname : function, optional
            Function returning a sensible name for given arguments, or None for fallback naming. Default is None.
        """
        def inner(mgrclass):
            cls._services[name] = cls.ServiceInfo(name, mgrclass, exchandler, maxreloads, maxfailures, reloadlocktime,
                                                  argspec, argname)
            return mgrclass
        return inner

    @classmethod
    def load(cls, service, *args, force_reload=False):
        if service not in cls._services:
            raise ServiceUnavailableError("Service '{}' does not exist.".format(service))

        args = cls._services[service].checkArgs(*args)
        instanceKey = (service, *args)
        if force_reload or instanceKey not in cls._instances:
            try:
                cls._instances[instanceKey] = cls.ServiceInstance(cls._services[service], *args)
            except InstanceDefault:
                cls._instances[instanceKey] = cls.load(service)
        else:
            cls._instances[instanceKey].load()
        return cls._instances[instanceKey]

    @classmethod
    def unload(cls, instance):
        servicekey = (instance._service._name, *instance._args)
        if servicekey in cls._services:
            del cls._services[servicekey]

    @classmethod
    def statename(cls, state):
        return cls._names.get(state, "UNKNOWN")

    @classmethod
    def services(cls):
        return [service for service in cls._services]

    @classmethod
    def instances(cls, service=None):
        return [(key[1:], value) for key, value in cls._instances.items() if service is None or key[0] == service]

    @classmethod
    def servicename(cls, service, *args):
        base = service+"@"
        if service in cls._services and cls._services[service]._argname:
            cls._services[service].checkArgs(*args)
            name = cls._services[service]._argname(*args)
            if name is not None:
                return base+name
        base += "default" if not args else repr(args[0]) if len(args) == 1 else "["+",".join(repr(arg) for arg in args)+"]"
        return base


class Service:
    SUPPRESS_NONE = 0   # All exceptions are passed to the calling function
    SUPPRESS_INOP = 1   # Suppress exceptions indicating service unavailability
    SUPPRESS_ALL = 2    # Suppress all exceptions

    class Stub:
        def __init__(self, name):
            self.name = name

        def __getattr__(self, name):
            raise ServiceUnavailableError("Service '{}' is currently not available".format(self.name))

    def __init__(self, name, *args, errors=SUPPRESS_NONE):
        displayname = ServiceHub.servicename(name, *args)
        try:
            self.__suppress = errors
            self.__service = ServiceHub.load(name, *args)
            self.plugin = self.__service._service.mgrclass
            self.__mgr = self.__service.manager if self.__service.available else self.Stub(displayname)
        except Exception:
            if errors == self.SUPPRESS_ALL:
                self.__service = None
                self.__mgr = self.Stub(displayname)
            else:
                raise

    def __enter__(self):
        return self.__mgr

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None or isinstance(exc_value, ServiceUnavailableError):
            return self.__suppress != 0
        self.__service.logger.warning(repr(exc_value))
        excresult = self.__service._service.exchandler(self.__service, exc_value)
        if isinstance(excresult, tuple):
            newstate, msg = excresult
        else:
            newstate, msg = excresult, "Service '{}' is currently not available".format(self.__service.name)
        if newstate == 0:
            return True
        if newstate:
            self.__service.failed(newstate, exc_value)
            if self.__suppress:
                return True
            raise ServiceUnavailableError(msg)
        if self.__suppress == Service.SUPPRESS_ALL:
            return True

    @staticmethod
    def available(name, *args):
        return name in ServiceHub and ServiceHub.load(name, *args).available

    def service(self):
        return self.__mgr


from . import chat, exmdb, ldap, redis, systemd
