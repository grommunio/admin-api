=======================
grommunio-admin-user(1)
=======================

Name
====

grommunio-admin user — User management

Synopsis
========

| **grommunio-admin user** **delete** [*-k*] [*-y*] *USERSPEC*
| **grommunio-admin user** **list** [*-f FIELD=<value>*] [*-s FIELD*]
  [*USERSPEC*]
| **grommunio-admin user** **show** [*-f FIELD=<value>*] [*-s FIELD*]
  *USERSPEC*

Description
===========

Subcommand to show and delete users.

No functionality for adding or modifying users is implemented at the
moment.

Commands
========

``delete``
   Delete user
``list``
   List users
``show``
   Show detailed information about a user

Options
=======

``USERSPEC``
   User name prefix or user ID
``-f FIELD=<value>``, ``--filter FIELD=<value>``
   Filter expression in the form of ‘field=value’. Can be specified
   multiple times to refine filter
``-k``, ``--keep-files``
   Do not delete user files from disk
``-s FIELD``, ``--sort FIELD``
   Sort by field. Can be given multiple times
``-y``, ``--yes``
   Assume yes instead of prompting

See Also
========

**grommunio-admin**\ (1), **grommunio-admin-domain**\ (1),
**grommunio-admin-fs**\ (1), **grommunio-admin-ldap**\ (1),
**grommunio-admin-passwd**\ (1)
