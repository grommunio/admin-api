# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grammm GmbH

from systemd.journal import Reader

class LogReader:
    """Central log reader class."""
    rreg = {}

    @classmethod
    def register(cls, name):
        """Class decorator to register a log reader at the factory.

        Parameters
        ----------
        name : str
            Name of the log reader

        Returns
        -------
        function
            Decorator function
        """
        def inner(obj):
            cls.rreg[name] = obj
            return obj
        return inner

    @classmethod
    def tail(cls, source, target, *args, **kwargs):
        """Get log tail.

        Automatically uses the correct log reader according to `source`.

        Parameters
        ----------
        source : str
            Name of the log source
        target : str
            Name of the log file or unit
        *args : any
            Arguments forwarded to the log reader
        **kwargs : any
            Keyword arguments forwarded to the log reader

        Raises
        ------
        ValueError
            `source` is not a registered log reader

        Returns
        -------
        list
            List of log file entries
        """
        if source not in cls.rreg:
            raise ValueError("Unknown source '{}'".format(source))
        return cls.rreg[source](target).tail(*args, **kwargs)


@LogReader.register("journald")
class JournaldReader:
    """Reader class four journald logs."""

    def __init__(self, unit):
        """Create journald reader

        Parameters
        ----------
        unit : str
            Name of the unit.
        """
        self.reader = Reader()
        self.reader.add_match(_SYSTEMD_UNIT=unit)

    @staticmethod
    def _entry(data):
        return dict(level=data["PRIORITY"],
                    message=data["MESSAGE"],
                    time=data["__REALTIME_TIMESTAMP"].strftime("%Y-%m-%d %H:%M:%S.%f"),
                    runtime=data["__MONOTONIC_TIMESTAMP"].timestamp.total_seconds())

    def tail(self, n=10, skip=0, after=None):
        """Get log tail.

        Parameters
        ----------
        n : int, optional
            Number of lines to return. The default is 10.
        skip : int, optional
            Number of lines to skip. The default is 0.
        after : datetime, optional
            Return all lines after given time point. Overrides `n` and `skip`. The default is None.

        Returns
        -------
        list
            List of log file entries
        """
        self.reader.seek_tail()
        if after is None:
            if skip > 0:
                self.reader.get_previous(skip)
            entries = reversed([self.reader.get_previous() for _ in range(n)])
            return [self._entry(entry) for entry in entries if len(entry) != 0]
        entries = []
        while True:
            entry = self.reader.get_previous()
            if len(entry) == 0 or entry["__REALTIME_TIMESTAMP"] <= after:
                break
            entries.append(self._entry(entry))
        return list(reversed(entries))
