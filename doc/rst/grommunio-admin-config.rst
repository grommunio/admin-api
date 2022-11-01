..
	SPDX-License-Identifier: CC-BY-SA-4.0 or-later
	SPDX-FileCopyrightText: 2021 grommunio GmbH

=========================
grommunio-admin-config(1)
=========================

Name
====

grommunio-admin config — grommunio-admin config introspection

Synopsis
========

| **grommunio-admin config** *check*
| **grommunio-admin config** (*dump*\|*get*) [*KEY*]
| **grommunio-admin config** *trace* *[-s]* (*files*\|*values*) [*KEY*]

Commands
========

check
-----

| Check the structural validity of the configuration.
| Does currently not validate the semantic integrity, i.e. existence of
  referenced files, LDAP or database connectivity etc., although this
  functionality may be added in the future.

dump, get
---------

| Print the complete configuration.
| As the grommunio-admin configuration can (and probably will) be
  distributed over multiple files, the get command provides an easy way
  to see the effective configuration.
| The output can be reduced to a single *KEY*, if specified. Sub-levels
  can be specified in dotted notation (e.g. ``sync.defaultPolicy``)
| The *dump* command is an alias for *get* and remains for backward
  compatibility.

trace
-----
| Trace source of effective configuration.
| Results can be presented either by file (``files``), showing which parts of
  a file are actually used, or by value (``values``), showing which file each
  value originates from.
| Installation of the Python ``termcolor`` package is advised for a more
  readable output. See section *Tracing* for more information.

Options
=======

``KEY``
  Only view specified key.

``-s``, ``--show-history``
  Display more value history (see section *Tracing* for more information)

Tracing
=======

By-File
-------
| Print annotated contents of each file.
| Each line is marked and color coded to show its status.
  The following annotations are used:
- *+*, green: The value is part of the final configuration
- *x*, red: The value is overwritten by a later file
- *\**, yellow: The object or list is extended by a later file
- *~*, grey: The value is overwritten with the same value

| Additionally, lines overwriting or extending previous entries
  are printed in boldface.
| When specifying *--show-history*, each value that is overwritten
  or extended is annotated with the files doing so (each being color
  coded with the effect it has on the value).

By-Value
--------
| Print annotated effective configuration.
| Each line is annotated with the file it originates from. In case of
  objects and lists, all contributing files are listed.
| When specifying *--show-history*, overwritten files containing that
  value are listed as well. The effective source file is underlined.
| For better visualization, color coding is done on a per-file basis:
  Each file is assigned an individual style which is used for its
  contributions. Objects and lists originating from multiple files are
  always shown in boldface white.


See Also
========

**grommunio-admin**\ (1), **grommunio-admin-dbconf**\ (1),
**grommunio-admin-mconf**\ (1)
