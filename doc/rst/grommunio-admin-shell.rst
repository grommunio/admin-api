..
	SPDX-License-Identifier: CC-BY-SA-4.0 or-later
	SPDX-FileCopyrightText: 2021 grommunio GmbH

========================
grommunio-admin-shell(1)
========================

Name
====

grommunio-admin shell — Start interactive shell

Synopsis
========

**grommunio-admin shell** [*-d*] [*-n*] [*-x*]

Description
===========

The interactive shell mode allows execution of multiple (new line
separated) commands in a single session. Command syntax is identical to
the CLI arguments, with addition of the *exit* command which ends the
interactive shell.

If possible, typed history will be saved in *~/.grommunio-admin.history*.

Options
=======

``-d``, ``--debug``
   Enable more verbose debug output

``-n``, ``--no-history``
   Disable loading/saving of the typed history

``-x``, ``--exit``
   Exit immediately if a command results in a non-zero exit code

See Also
========

**grommunio-admin**\ (1), **grommunio-admin-connect**\ (1)
