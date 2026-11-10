..
	SPDX-License-Identifier: CC-BY-SA-4.0 or-later
	SPDX-FileCopyrightText: 2021-2022 grommunio GmbH

=====================
grommunio-admin-fs(1)
=====================

Name
====

grommunio-admin fs — Filesystem operations

Synopsis
========

| **grommunio-admin fs** **clean** [*-d*] [*-s*] [*PARTITION*]
| **grommunio-admin fs** **du** [*PARTITION*]

Description
===========

Show space used by user and domain home directories or remove unused
files.

Unused files may remain when users or domains are deleted without
removing their files. An interrupted removal leaves a directory ending
in ``@deleting``.

The commands work on the local file system and have to be run on the
mailbox server.

Commands
========

``clean``
   Remove directories and files that are not used by any domain or user.
   Directories that contain or are part of a directory in use are kept.
``du``
   Show data usage statistics

Options
=======

``PARTITION``
   Apply only to selected partition. Can be either *domain* or *user*
``-d``, ``--dryrun``
   Do not delete anything, just print what would be deleted
``-s``, ``--nostat``
   Do not collect disk usage statistics of deleted files

See Also
========

**grommunio-admin**\ (1), **grommunio-admin-domain**\ (1),
**grommunio-admin-user**\ (1)
