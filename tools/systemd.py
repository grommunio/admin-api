# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2020 grommunio GmbH

import threading
import dbus
import dbus.mainloop.glib

from gi.repository import GLib
from datetime import datetime

class Future:
    def __init__(self):
        self._event = threading.Event()

    def set(self, value):
        self._value = value
        self._event.set()

    def get(self):
        self._event.wait()
        return self._value


dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)


class Systemd:
    """Systemd DBus wrapper."""

    DBusSystemd = "org.freedesktop.systemd1"
    eventThread = eventLoop = None
    activeQueries = {}
    queryLock = threading.Lock()
    subscribed = False

    def __init__(self, system: bool = False):
        """Initialize wrapper.

        Parameters
        ----------
        system : bool, optional
            Whether connect to system DBus. By default, the session DBus is used.

        """
        self._runEventLoop()
        self.bus = (dbus.SystemBus if system else dbus.SessionBus)()
        systemd = self.bus.get_object(self.DBusSystemd, "/org/freedesktop/systemd1")
        self.manager = dbus.Interface(systemd, self.DBusSystemd+".Manager")
        self._enableEvents(self.manager)

    @staticmethod
    def _jobRemovedHandler(ID, job, unit, result):
        """Handle JobRemoved signal.

        Stores job result in the corresponding future object.
        If the signaled job is not registered, the signal is ignored.

        Parameters
        ----------
        ID : dbus.Int32
            Unused
        job : dbus.String
            Path of the job object
        unit : dbus.String
            Unused
        result : dbus.String
            Result of the job
        """
        Systemd.queryLock.acquire()
        res = Systemd.activeQueries.pop(str(job), None)
        Systemd.queryLock.release()
        if res is None:
            return
        res.set(result)

    @staticmethod
    def _addQuery(job):
        """Register a job.

        Parameters
        ----------
        job : str
            Path of the job object

        Returns
        -------
        future : Future
            Future object containing the result of the job
        """
        future = Future()
        Systemd.queryLock.acquire()
        Systemd.activeQueries[str(job)] = future
        Systemd.queryLock.release()
        return future

    @staticmethod
    def _runEventLoop():
        """Start DBus event loop.

        Starts a separate thread running the main event loop.
        Blocks until Loop is running.
        """
        if Systemd.eventThread is None:
            Systemd.eventLoop = GLib.MainLoop()
            Systemd.eventThread = threading.Thread(target=Systemd.eventLoop.run)
            Systemd.eventThread.start()
            while not Systemd.eventLoop.is_running():
                pass

    @staticmethod
    def _enableEvents(manager):
        """Enable handling of JobRemoved signals.

        Parameters
        ----------
        manager : org.freedesktop.systemd1.Manager Proxy
            Manager proxy user for subscription.
        """
        if not Systemd.subscribed:
            Systemd._runEventLoop()
            manager.Subscribe()
            manager.connect_to_signal("JobRemoved", Systemd._jobRemovedHandler)
            Systemd.subscribed = True

    def getService(self, service: str):
        """Get status information about a service.

        Parameters
        ----------
        service : str
            Name of the unit

        Returns
        -------
        result : dict
            Dictionary containing state, substate, description and timestamp (since).
        """
        unit = self.bus.get_object(self.DBusSystemd, object_path=self.manager.GetUnit(service))
        interface = dbus.Interface(unit, dbus_interface="org.freedesktop.DBus.Properties")
        result = dict()
        result["state"] = str(interface.Get("org.freedesktop.systemd1.Unit", "ActiveState"))
        result["substate"] = str(interface.Get("org.freedesktop.systemd1.Unit", "SubState"))
        result["autostart"] = str(interface.Get("org.freedesktop.systemd1.Unit", "UnitFileState"))
        result["description"] = str(interface.Get("org.freedesktop.systemd1.Unit", "Description"))
        if result["state"] == "active":
            since = int(interface.Get("org.freedesktop.systemd1.Unit", "ActiveEnterTimestamp"))
        else:
            since = int(interface.Get("org.freedesktop.systemd1.Unit", "InactiveEnterTimestamp"))
        result["since"] = datetime.fromtimestamp(since/1000000).strftime("%Y-%m-%d %H:%M:%S") if since != 0 else None
        return result

    def startService(self, service: str):
        """Issue systemd service start.

        Parameters
        ----------
        service : str
            Name of the unit

        Raises
        ------
        dbus.DBusException
            DBus communication failed.
        """
        res = self._addQuery(self.manager.StartUnit(service, "replace"))
        return str(res.get())

    def stopService(self, service: str):
        """Issue systemd service shutdown.

        Parameters
        ----------
        service : str
            Name of the unit

        Raises
        ------
        dbus.DBusException
            DBus communication failed.
        """
        res = self._addQuery(self.manager.StopUnit(service, "replace"))
        return str(res.get())

    def restartService(self, service: str):
        """Issue systemd service restart.

        Parameters
        ----------
        service : str
            Name of the unit

        Raises
        ------
        dbus.DBusException
            DBus communication failed.
        """
        res = self._addQuery(self.manager.StartUnit(service, "replace"))
        return str(res.get())

    def reloadService(self, service: str):
        """Issue systemd service reload.

        Parameters
        ----------
        service : str
            Name of the unit

        Raises
        ------
        dbus.DBusException
            DBus communication failed.
        """
        res = self._addQuery(self.manager.ReloadUnit(service, "replace"))
        return str(res.get())

    def tryReloadRestartService(self, service: str):
        """Issue systemd service reload or restart.

        Parameters
        ----------
        service : str
            Name of the unit

        Raises
        ------
        dbus.DBusException
            DBus communication failed.
        """
        res = self._addQuery(self.manager.ReloadOrTryRestartUnit(service, "replace"))
        return str(res.get())

    def enableService(self, service: str, runtime: bool=False, force: bool=False):
        """Enable systemd service.

        Parameters
        ----------
        service : str
            Name of the unit
        runtime : bool, optional
            Enable only until next reboot. Default is False.
        force: bool, optional
            Override existing symlinks. Default is False.

        Raises
        ------
        dbus.DBusException
            DBus communication failed.
        """
        res = self.manager.EnableUnitFiles([service], runtime, force)
        self.manager.Reload()
        return "\n".join("{}: {} -> {}".format(*r) for r in res[1])


    def disableService(self, service: str, runtime: bool=False):
        """Disable systemd service.

        Parameters
        ----------
        service : str
            Name of the unit
        runtime : bool, optional
            Disable only until next reboot. Default is False.

        Raises
        ------
        dbus.DBusException
            DBus communication failed.
        """
        res = self.manager.DisableUnitFiles([service], runtime)
        self.manager.Reload()
        return "\n".join("{}: {} -> {}".format(*r) for r in res)

    @classmethod
    def quitLoop(cls):
        """Stop the DBus event loop.

        If the event loop is not running, the call does nothing.
        The event loop will be automatically restarted when a new Systemd object is created.

        Blocks execution until the event loop is stopped.

        Parameters
        ----------
        cls : TYPE
            DESCRIPTION.

        Returns
        -------
        None.

        """
        if cls.eventLoop is None:
            return
        cls.eventLoop.quit()
        while cls.eventThread.is_alive():
            pass
        cls.eventLoop = cls.eventThread = None

    @staticmethod
    def fafReload(*services, **sysdArgs):
        import logging
        sysd = Systemd(**sysdArgs)
        results = []
        for service in services:
            try:
                results.append(sysd._addQuery(sysd.manager.ReloadUnit(service, "replace")))
            except dbus.DBusException as err:
                logging.warning("Failed to reload {}: {}".format(service, " - ".join(str(arg) for arg in err.args)))
        for result in results:
            if str(result.get()) != "done":
                logging.warning("Failed to reload {}: {}".format(service, result))
