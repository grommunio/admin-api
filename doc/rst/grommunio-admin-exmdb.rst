========================
grommunio-admin-exmdb(1)
========================

Name
====

grommunio-admin exmdb — User or domain store management

Synopsis
========

| **grommunio-admin** **exmdb** *TARGET* *folder* *find* [*-x*] *NAME* [*ID*]
| **grommunio-admin** **exmdb** *TARGET* *folder* *grant* [*-f*] [*-r*] *ID*
  *USERNAME* *PERMISSION* [*PERMISSION* …]
| **grommunio-admin** **exmdb** *TARGET* *folder* *list* [*-r*] [*ID*]
| **grommunio-admin** **exmdb** *TARGET* *folder* *revoke* [*-r*] *ID*
  *USERNAME* [*PERMISSION* …]

Description
===========

Subcommand to access and modify a domain's or user's store via exmdb protocol.

Currently only basic operations on folders are available but support for more
functions is planned for the future.

Commands
========

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

Options
=======
``ID``
   ID of the folder
``NAME``
   Name of the folder
``PERMSSION``
   Name or numeric value of the permission
``TARGET``
   Name of the domain or e-mail address of the user
``USERNAME``
   E-Mail address of a user
``-f``, ``--force``
   Grant permissions to non-existing user
``-r``, ``--recursive``
   Apply recursively to subfolders
``-x``, ``--exact``
   Only match exact folder names instead of case-insensitive substrings

Notes
=====

- Folder IDs and permssions can be given in decimal,
  hexadecimal (`0x`-prefix), octal (`0`-prefix) or binary (`0b`-prefix).
- Currently, the permission value echoed by the `grant` and `revoke` commands
  is the one sent to the server and might differ from the value actually
  assigned.
- The `find` and `list` commands operate on the `IPMSUBTREE` folders
  (`0x2` for users, `0x9` for domains) by default, which can be overridden
  by the `ID` parameter.

See Also
========

**grommunio-admin**\ (1), **grommunio-admin-domain**\ (1),
**grommunio-admin-service**\ (1), **grommunio-admin-user**\ (1)
