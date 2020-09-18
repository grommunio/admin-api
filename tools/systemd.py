# -*- coding: utf-8 -*-
"""
Created on Tue Sep 15 09:46:15 2020

@author: Julia Schroeder, julia.schroeder@grammm.com
@copyright: Grammm GmbH, 2020
"""

import dbus

from datetime import datetime


class Systemd:
    """Systemd DBus wrapper."""

    DBusSystemd = "org.freedesktop.systemd1"

    def __init__(self, system: bool = False):
        """Initialize wrapper.

        Parameters
        ----------
        system : bool, optional
            Whether connect to system DBus. By default, the session DBus is used.

        """
        self.bus = (dbus.SystemBus if system else dbus.SessionBus)()
        systemd = self.bus.get_object(self.DBusSystemd, "/org/freedesktop/systemd1")
        self.manager = dbus.Interface(systemd, self.DBusSystemd+".Manager")

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
        self.manager.StartUnit(service, "replace")

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
        self.manager.StopUnit(service, "replace")

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
        self.manager.RestartUnit(service, "replace")
