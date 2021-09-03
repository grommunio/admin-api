==================
grommunio-admin(1)
==================

Name
====

grommunio-admin — grommunio admin CLI

Synopsis
========

| **grommunio-admin** *-h*
| **grommunio-admin** *COMMAND* [*-h* \| *ARGS…*]

Description
===========

Command line interface of the grommunio Admin API.

| The CLI is not intended to provide the full functionality of the REST
  interface, but rather a low level administrative tool.
| As the CLI is still under development, usage in automated scripts is
  generally discouraged.

The *-h*/*--help* option is not documented separately for each
subcommand, but is valid at any point and prints usage information for
the current subcommand.

The CLI supports color output if the *termcolor* module is installed.

Commands
========

config
------

Configuration introspection. See *grommunio-admin-config(1)*.

connect
-------

Connect to remote CLI. See *grommunio-admin-connect(1)*

dbconf
------

Database-stored configuration management. See
*grommunio-admin-dbconf(1)*.

domain
------

Domain management. See *grommunio-admin-domain(1)*.

fetchmail
---------

Fetchmail management. See *grommunio-admin-fetchmail(1)*.

fs
--

Filesystem operations. See *grommunio-admin-fs(1)*.

ldap
----

LDAP configuration, diagnostics and synchronization. See
*grommunio-admin-ldap(1)*.

mconf
-----

Managed configurations manipulation. See *grommunio-admin-mconf(1)*.

mlist
-----

Mailing/distribution list management. See *grommunio-admin-mlist(1)*.

passwd
------

User password management. See *grommunio-admin-passwd(1)*.

run
---

Run the REST API. See *grommunio-admin-run(1)*.

service
-------

Control external services interface. See *grommunio-admin-service(1)*

shell
-----

Start interactive shell. See *grommunio-admin-shell(1)*.

taginfo
-------

Print information about proptags. See *grommunio-admin-taginfo(1)*.

user
----

User management. See *grommunio-admin-user(1)*.

version
-------

Show version information. See *grommunio-admin-version(1)*.

See Also
========

**grommunio-dbconf**\ (1)
