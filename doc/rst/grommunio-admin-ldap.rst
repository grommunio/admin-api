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

| **grommunio-admin ldap** **check** [*-o ORGSPEC*] [*-r* [*-m*] [*-y*]]
| **grommunio-admin ldap** **configure** [*-d*] [*-o ORGSPEC*]
| **grommunio-admin ldap** **downsync** [*-c*] [*-f*] [*-l*]
  [*-o ORGSPEC*] [*-p PAGE_SIZE*] [*USER* [*USER* …]]
| **grommunio-admin ldap** **dump** [*-o ORGSPEC*] *USER*
| **grommunio-admin ldap** **info** [*-o ORGSPEC*]
| **grommunio-admin ldap** **reload** [*-o ORGSPEC*]
| **grommunio-admin ldap** **search** [*-a*] [*--format FORMAT*]
  [*-n MAX_RESULTS*] [*-o ORGSPEC*] [*-p PAGE_SIZE*] [*USER*]

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
``-a``, ``--all``
   Show all results, not only importable objects
``--auth-backend <automatic|externid|always_ldap|always_mysql>``
   For *reload* only.  Set the authmgr global system authentication backend.
   Can be one of *automatic* (same as *externid*), *externid*, *always_ldap*,
   *always_mysql*. Default is *externid* if unset.
``-c``, ``--complete``
   Import or update all users from the LDAP tree
``-f``, ``--force``
   Force update users that are linked to a different or no LDAP object
``--format FORMAT``
   Output format. Can be one of *csv*, *json-flat*, *json-kv*, *json-object*,
   *json-structured* and *pretty*. Default is *pretty*.
``-l``, ``--lang``
   Set language for imported users. Default is to not set any language.
``-m``, ``--remove-maildirs``
   Also remove user files from disk
``-n MAX_RESULTS``, ``--max-results MAX_RESULTS``
   Maximum number of results or 0 to disable limit (default 0).
   Note that the actual number of results may exceed the limit due to paging
   and filtering.
``-o ORGSPEC``, ``--organization ORGSPEC``
   Use organization specific LDAP connection. Supports organization ID or name.
``-p PAGE_SIZE``, ``--page-size PAGE_SIZE``
   Set batch size for paged search. Can be decreased when running into timeout
   errors with slow LDAP servers. Default is 1000.
``-r``, ``--remove``
   Remove imported users of which the linked LDAP object could not be
   found
``-t TYPES``, ``--types TYPES``
   Comma separated list of object types to search for. Supported are *user*,
   *contact* and *group*.
``-x <bool>``, ``--disable-ldap <bool>``
   For reload only. Set the disable LDAP switch for the organization or
   globally system wide.
``-y``, ``--yes``
   Do not prompt for confirmation, assume yes

See Also
========

**grommunio-admin**\ (1), **grommunio-admin-fs**\ (1), **grommunio-admin-user**\ (1)
