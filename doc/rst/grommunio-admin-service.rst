==========================
grommunio-admin-service(1)
==========================

Name
====

grommunio-admin service — grommunio-admin external service interface control

Synopsis
========

| **grommunio-admin service** *disable* [*SERVICE* [*SERVICE* [...]]]
| **grommunio-admin service** [*-r*] *load* [*SERVICE* [*SERVICE* [...]]]
| **grommunio-admin service** [*-v*] *status*


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

| Each service has a state, reflecting the connection status. The following
  states are used:

``UNLOADED``
  The service has not been loaded yet. It will be loaded automatically when
  needed.

``LOADED``
  The service has been initialized successfully.

``UNAVAILABLE``
  An error occurred that inidicates that the service is not available, but
  might become available in the future. No reload is necessary to reconnect.

``SUSPENDED``
  Àn error occurred that inidicates that the service is not available, but
  might become available in the future. The service will be reloaded
  automatically on next usage.

``ERROR``
  The service is not available either because initialization failed or because
  to man errors occurred. It will remain unavailable until reloaded manually.

``DISABLED``
  The service has been manually disabled (either by configuration or command).


Commands
========

disable
-------

| Disable the service. Requires reload to enable.

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
**grommunio-admin-connect**\ (1), **grommunio-admin-mconf**\ (1)
