..
	SPDX-License-Identifier: CC-BY-SA-4.0 or-later
	SPDX-FileCopyrightText: 2022 grommunio GmbH

========================
grommunio-admin-exmdb(1)
========================

Name
====

grommunio-admin exmdb — User or domain store management

Synopsis
========

| **grommunio-admin** **exmdb** *TARGET* *folder* *delete* [*-a*] [--clear] *FOLDERSPEC*
| **grommunio-admin** **exmdb** *TARGET* *folder* *find* [*-x*] *NAME* [*ID*]
| **grommunio-admin** **exmdb** *TARGET* *folder* *grant* [*-f*] [*-r*] *ID*
  *USERNAME* *PERMISSION* [*PERMISSION* …]
| **grommunio-admin** **exmdb** *TARGET* *folder* *list* [*-r*]
  [*--format FORMAT*] [*ID*]
| **grommunio-admin** **exmdb** *TARGET* *folder* *revoke* [*-r*] *ID*
  *USERNAME* [*PERMISSION* …]
| **grommunio-admin** **exmdb** *TARGET* *store* *delete* *PROPSPEC* [*PROPSPEC*  ...]
| **grommunio-admin** **exmdb** *TARGET* *store* *get* [*PROPSPEC* ...]
| **grommunio-admin** **exmdb** *TARGET* *store* *set* [*PROPSPEC=VALUE* ...]

Description
===========

Subcommand to access and modify a domain's or user's store via exmdb protocol.

Commands
========

Folder subcommand
-----------------

``delete``
   Delete folder by ID or name.
``find``
   Find folders with given name
``grant``
   Grant permissions on this folder to a user
``list``
   List subfolders of a folder. If no folder ID is specified, list subfolders
   of root folder.
``revoke``
   Revoke permissions on this folder from a user. If not permission is
   specified, revoke all permissions.

Store subcommand
----------------

``delete``
   Delete properties
``get``
   Get store properties
``set``
   Set store properties

Options
=======
``ID``
   ID of the folder
``FOLDERSPEC``
   ID or name of the folder
``NAME``
   Name of the folder
``PERMISSION``
   Name or numeric value of the permission
``PROPSPEC``
   Name or numeric value of the property
``TARGET``
   Name of the domain or e-mail address of the user
``USERNAME``
   E-Mail address of a user
``-a``, ``--all``
   Do not stop if target is ambiguous but apply to all.
``--clear``
   Delete folder contents. Required for non-empty folders.
``-f``, ``--force``
   Grant permissions to non-existing user
``--format FORMAT``
   Set output format. Valid values are `csv`, `json-flat`, `json-tree`, `pretty`
   and `table`. Default is `pretty`.
``-r``, ``--recursive``
   Apply recursively to subfolders
``-x``, ``--exact``
   Only match exact folder names instead of case-insensitive substrings

Notes
=====

- Folder IDs and permissions can be given in decimal,
  hexadecimal (`0x`-prefix), octal (`0`-prefix) or binary (`0b`-prefix).
- Currently, the permission value echoed by the `grant` and `revoke` commands
  is the one sent to the server and might differ from the value actually
  assigned.
- The `find` and `list` commands operate on the `IPMSUBTREE` folders
  (`0x9` for users, `0x2` for domains) by default, which can be overridden
  by the `ID` parameter.

See Also
========

**grommunio-admin**\ (1), **grommunio-admin-domain**\ (1),
**grommunio-admin-service**\ (1), **grommunio-admin-user**\ (1)
