=========================
grommunio-admin-config(1)
=========================

Name
====

grommunio-admin config — Show or check grommunio-admin configuration

Synopsis
========

**grommunio-admin config** (*check* \| *dump*) [*-h*]

Commands
========

check
-----

| Checks the structural validity of the configuration.
| Does currently not validate the semantic integrity, i.e. existence of
  referenced files, LDAP or database connectivity etc., although this
  functionality may be added in the future.

dump
----

| Prints the complete configuration.
| As the grommunio-admin configuration can (and probably will) be
  distributed over multiple files, the dump command provides an easy way
  to see the effective configuration.

See Also
========

**grommunio-admin**\ (1), **grommunio-admin-dbconf**\ (1),
**grommunio-admin-mconf**\ (1)
