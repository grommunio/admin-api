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
| **grommunio-admin ldap** **downsync** [*-a*] [*-c*] [*-f*] [*-l*] [*-y*]
  [*USER* [*USER* …]]
| **grommunio-admin ldap** **dump** *USER*
| **grommunio-admin ldap** **info**
| **grommunio-admin ldap** **reload**
| **grommunio-admin ldap** **search** [*-n MAX_RESULTS*] [*USER*]

Description
===========

The grommunio admin ldap module provides functions for configuring and
testing the LDAP connection and dowloading or updating users.

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
   Synchronize all imported users. No new users are created, to import
   users use *-c*
``-c``, ``--complete``
   Import or update all users from the LDAP tree
``-f``, ``--force``
   Force update users that are linked to a different or no LDAP object
``-l``, ``--lang``
   Set language for imported users. Default is to not set any language.
``-m``, ``--remove-maildirs``
   Also remove user files from disk
``-n``, ``--max-results``
   Maximum number of results or 0 to diable limit (default 25)
``-r``, ``--remove``
   Remove imported users of which the linked LDAP object could not be
   found
``-y``, ``--yes``
   Do not prompt, assume yes

See Also
========

**grommunio-admin**\ (1), **grommunio-admin-fs**\ (1), **grommunio-admin-user**\ (1)
