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

**grommunio-admin passwd** [*-a*] [*-l LENGTH*] [*-p PASSWORD*]
  [*--password-stdin*] [*USER*]

Description
===========

| Set user password.
| If no user is specified, the password is set for the *admin* user,
  which is created automatically if necessary.
| If none of *-a*, *-p* or *--password-stdin* is provided, the user is
  prompted for a password.

Options
=======

``USER``
   User to set password for (default *admin*)
``-a``, ``--auto``
   Automatically generate a password
``-l LENGTH``, ``--length LENGTH``
   Length of the automatically generated password (default 16)
``-p PASSWORD``, ``--password PASSWORD``
   Password to set (do not prompt).
   Note that the password is visible to every local user in the process
   list for as long as the command runs; on multi-user hosts use
   *--password-stdin* instead.
``--password-stdin``
   Read the password from the first line of standard input (do not prompt).
   The trailing newline is stripped; any further input is ignored.

See Also
========

**grommunio-admin**\ (1), **grommunio-admin-user**\ (1)
