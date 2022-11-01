..
	SPDX-License-Identifier: CC-BY-SA-4.0 or-later
	SPDX-FileCopyrightText: 2021-2022 grommunio GmbH

=======================
grommunio-admin-ldap(1)
=======================

Name
====

grommunio-admin ldap — LDAP tools

Synopsis
========

| **grommunio-admin ldap** **check** [*-r* [*-m*] [*-y*]]
| **grommunio-admin ldap** **configure**
| **grommunio-admin ldap** **downsync** [*-a*] [*-c*] [*-f*] [*-l*]
  [*-p PAGE_SIZE*] [*-y*] [*USER* [*USER* …]]
| **grommunio-admin ldap** **dump** *USER*
| **grommunio-admin ldap** **info**
| **grommunio-admin ldap** **reload**
| **grommunio-admin ldap** **search** [*-n MAX_RESULTS*] [*-p PAGE_SIZE*]
  [*USER*]

Description
===========

The grommunio admin ldap module provides functions for configuring and
testing the LDAP connection and downloading or updating users.

Commands
========

``check``
   Check if the LDAP objects imported users are linked to can still be
   found, optionally removing orphaned users
``configure``
   Interactively configure or modify LDAP connection
``downsync``
   Synchronize or import users from LDAP
``dump``
   Print LDAP object
``info``
   Show connection status
``reload``
   Reload the LDAP configuration and reconnect
``search``
   Search for users

Options
=======

``USER``
   LDAP object ID or search string
``-a``, ``--auto``
   Never prompt, exit with error on conflicts. Implies -y.
``-c``, ``--complete``
   Import or update all users from the LDAP tree
``-f``, ``--force``
   Force update users that are linked to a different or no LDAP object
``-l``, ``--lang``
   Set language for imported users. Default is to not set any language.
``-p PAGE_SIZE``, ``--page-size PAGE_SIZE``
   Set batch size for paged search. Can be decreased when running into timeout
   errors with slow LDAP servers. Default is 1000.
``-m``, ``--remove-maildirs``
   Also remove user files from disk
``-n MAX_RESULTS``, ``--max-results MAX_RESULTS``
   Maximum number of results or 0 to disable limit (default 0).
   Note that the actual number of results may exceed the limit due to paging
   and filtering.
``-r``, ``--remove``
   Remove imported users of which the linked LDAP object could not be
   found
``-y``, ``--yes``
   Do not prompt for confirmation, assume yes

See Also
========

**grommunio-admin**\ (1), **grommunio-admin-fs**\ (1), **grommunio-admin-user**\ (1)
