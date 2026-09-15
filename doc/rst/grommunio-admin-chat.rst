..
	SPDX-License-Identifier: CC-BY-SA-4.0 or-later
	SPDX-FileCopyrightText: 2026 grommunio GmbH

=======================
grommunio-admin-chat(1)
=======================

Name
====

grommunio-admin chat — Chat management

Synopsis
========

| **grommunio-admin chat** **remove-all**
| **grommunio-admin chat** **sso** (*enable* \| *disable*) [*-d DOMAIN*] …

Description
===========

Commands for the grommunio-chat integration.

Commands
========

``remove-all``
   Set the chat IDs of all domains and users to NULL.
``sso``
   Move the chat accounts of grommunio users to single sign-on through the
   grommunio Keycloak realm (*enable*) or back to the local login
   (*disable*), and set the defaults for new accounts accordingly.
   Which OAuth service is used depends on what the chat server offers.
   grommunio-auth runs this when it configures grommunio-chat.

Options
=======

``-d DOMAIN``, ``--domain DOMAIN``
   Only affect users of DOMAIN and set its domain defaults. Can be given
   multiple times. Without this option the system defaults are set and
   per-domain overrides are removed.

See Also
========

**grommunio-admin**\ (1), **grommunio-admin-user**\ (1)
