=========================
grommunio-admin-dbconf(1)
=========================

Name
====

grommunio-admin dbconf — Database-stored configuration management.

Synopsis
========

| **grommunio-admin dbconf** (*commit* \| *delete*) *SERVICE* [*FILE*
  [*KEY*]]
| **grommunio-admin dbconf** *get* *SERVICE* *FILE* [*KEY*]
| **grommunio-admin dbconf** *list* [*SERVICE* [*FILE* [*KEY*]]]
| **grommunio-admin dbconf** *set* [*-b*] [*-i*] [--] *SERVICE* *FILE*
  *KEY* *VALUE*

Description
===========

| *grommunio dbconf* provides the ability to store and manage
  configurations at a single location while making it available across
  distributed systems. The configurations are stored in the central
  MySQL database and can be accessed via *grommunio-dbconf(1)* and
  *grommunio-admin-dbconf(1)*.
| While both tools essentially provide the same functionality,
  *grommunio-dbconf(1)* provides far better performance and is intended
  to be used for quickly accessing the configuration.

Configurations consist of key/value pairs organized in files, grouped by
service. Each service can have an arbitrary number of configuration
files, which in turn can contain an arbitrary number of unique keys.

Commands
========

``commit``
   Trigger commit hook for service, file or key
``delete``
   Delete service, file or key
``get``
   Get file or single key
``list``
   List available services, files or keys
``set``
   Set a configuration key

Options
=======

``SERVICE``
   Name of the service to configure
``FILE``
   Name of the configuration file
``KEY``
   Name of the configuration key
``VALUE``
   Value to store in the key
``--``
   Indicate that all options have been specified and only names follow
``-b``, ``--batch``
   Do not auto-commit
``-i``, ``--init``
   Only set if configuration key does not exist yet

Commit Hooks
============

When modifying values, potential consumers can be notified of this
change via commit hooks, for example by restarting the service using the
configuration. For security reasons only a few white-listed commands are
available (see section *AVAILABLE COMMIT COMMANDS*).

Commit hooks can be defined on ``key``, ``file`` or ``service`` level.
*set* operations always trigger commits at key level, while the *commit*
command can directly trigger key or service level hooks depending on
whether a file or key is specified.

If no hook is defined for a specific trigger level, it automatically
falls through to the next lower level, in the order *key* > *file* >
*service*.

Commit hooks for a service can be defined by setting ``commit_key``,
``commit_file`` and ``commit_service`` keys under
*grommunio-dbconf/<service>* to a valid command (see below).

Available Commit Commands
=========================

The following commands are available:

Key
---

``postconf -e $ENTRY``

File
----

There are currently no file-level commands.

Service
-------

| ``systemctl reload $SERVICE``
| ``systemctl restart $SERVICE``

Command Variable Expansion
==========================

Commands can contain *$*-prefixed variables that are expanded before
execution. The literal *$$* can be used to generate a single *$*.

The following variables are valid:

``ENTRY``
   Expands to ``$KEY=$VALUE`` (key level only)
``FILE``
   Complete content of the modified file as newline separated key=value
   entries (file level only)
``FILENAME``
   Name of the modified file (key and file level)
``KEY``
   The modified key (key level only)
``SERVICE``
   Name of the modified service
``VALUE``
   New value of the modified key (key level only)

See Also
========

**grommunio-admin**\ (1), **grommunio-admin-config**\ (1),
**grommunio-admin-mconf**\ (1). **grommunio-dbconf**\ (1)
