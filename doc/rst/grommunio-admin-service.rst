..
	SPDX-License-Identifier: CC-BY-SA-4.0 or-later
	SPDX-FileCopyrightText: 2021-2022 grommunio GmbH

==========================
grommunio-admin-service(1)
==========================

Name
====

grommunio-admin service — grommunio-admin external service interface control

Synopsis
========

| **grommunio-admin service** [*-r*] *load* *SERVICE* [*ARGS* …]
| **grommunio-admin service** [*-v*] *status* [*SERVICE* [*SERVICE* […]]]


Description
===========

| grommunio-admin connects to several external services to either provide means
  of configuration via API (e.g. grommunio chat) or to retrieve additional
  information (e.g. LDAP).
| *grommunio-admin service* can be used to introspect the connection status of
  these services.
| Note that the CLI runs separately from the API backend. If introspection of
  the running server instance is required, use the *connect* command to access
  the server instance.
| As of version 1.9, each service acts as a blueprint for parameterized
  instances. Currently only the LDAP service supports parameters, allowing for
  organization-specific ldap connections.
| Each instance has a state, reflecting the connection status. The following
  states are used:

``UNLOADED``
  The service has not been loaded yet. It will be loaded automatically when
  needed.

``LOADED``
  The service has been initialized successfully.

``UNAVAILABLE``
  An error occurred that indicates that the service is not available, but
  might become available in the future. No reload is necessary to reconnect.

``SUSPENDED``
  Àn error occurred that indicates that the service is not available, but
  might become available in the future. The service will be reloaded
  automatically on next usage.

``ERROR``
  The service is not available either because initialization failed or because
  to man errors occurred. It will remain unavailable until reloaded manually.

``DISABLED``
  The service has been manually disabled (either by configuration or command).


Commands
========

load
-----

| Load or reload services.
| Only services in UNLOADED or SUSPENDED state will be affected unless the
  *--reload* option is given.

status
------

| Show status of all services.


Options
=======

``SERVICE``
  Name of the service.

``-r``, ``--reload``
  Force reload of service.

``-v``, ``--verbose``
  Show more information.

Services
========

The following services are currently connected via the service interface:

``chat``
  grommunio chat. Connected via REST interface.

``exmdb``
  gromox exmdb provider (gromox-http). Connected via custom TCP protocol.

``ldap``
  External LDAP service. Connected via LDAP(s).

``redis``
  Redis instance (used by grommunio sync). Connected via redis driver (TCP).

``systemd``
  Systemd shell execution.

See Also
========

**grommunio-admin**\ (1), **grommunio-admin-config**\ (1),
**grommunio-admin-connect**\ (1), **grommunio-admin-ldap**\ (1)
**grommunio-admin-mconf**\ (1)
