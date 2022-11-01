..
	SPDX-License-Identifier: CC-BY-SA-4.0 or-later
	SPDX-FileCopyrightText: 2021 grommunio GmbH

=========================
grommunio-admin-passwd(1)
=========================

Name
====

grommunio-admin passwd — Set user password

Synopsis
========

**grommunio-admin passwd** [*-a*] [*-l LENGTH*] [*-p PASSWORD*] [*USER*]

Description
===========

| Set user password.
| If no user is specified, the password is set for the *admin* user,
  which is created automatically if necessary.
| If neither *-a* nor *-p* is provided, the user is prompted for a
  password.

Options
=======

``USER``
   User to set password for (default *admin*)
``-a``, ``--auto``
   Automatically generate a password
``-l LENGTH``, ``--length LENGTH``
   Length of the automatically generated password (default 16)
``-p PASSWORD``, ``--password PASSWORD``
   Password to set (do not prompt)

See Also
========

**grommunio-admin**\ (1), **grommunio-admin-user**\ (1)
