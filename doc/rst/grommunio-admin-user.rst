..
	SPDX-License-Identifier: CC-BY-SA-4.0 or-later
	SPDX-FileCopyrightText: 2021-2022 grommunio GmbH

=======================
grommunio-admin-user(1)
=======================

Name
====

grommunio-admin user — User management

Synopsis
========

| **grommunio-admin user** **create** [*--no-defaults*] [*<FIELDS>*] *USERNAME*
| **grommunio-admin user** **delegate** *USERSPEC* (*clear* \| *list*)
| **grommunio-admin user** **delegate** *USERSPEC* (*add* \| *remove*) *USERNAME* …
| **grommunio-admin user** **delete** [*-c*] [*-k*] [*-y*] *USERSPEC*
| **grommunio-admin user** **devices** *USERSPEC* (*list* \| *resync*
  \| *remove* \| *show*) [*DEVICE* …]
| **grommunio-admin user** **devices** *USERSPEC* wipe [*--mode MODE*]
  *DEVICE*
| **grommunio-admin user** **list** [*-f ATTRIBUTE=<value>*] [*-s FIELD*]
  [*USERSPEC*]
| **grommunio-admin user** **login** [*--nopass*] [*--password PASSWORD*]
  [*--token*] *USERNAME*
| **grommunio-admin user** **modify** [*<FIELDS>*] [*--delete-chat-user*]
  [*--no-ldap*] [*--remove-alias ALIAS*] [*--remove-altname ALTNAME*]
  [*--remove-property PROPSPEC*] [*--remove-storeprop PROPSPEC*] *USERSPEC*
| **grommunio-admin user** **query** [*-f ATTRIBUTE=<value>*] [*--format FORMAT*]
  [*--separator SEPARATOR*] [*-s FIELD*] [*ATTRIBUTE* …]
| **grommunio-admin user** **sendas** *USERSPEC* (*clear* \| *list*)
| **grommunio-admin user** **sendas** *USERSPEC* (*add* \| *remove*) *USERNAME* …
| **grommunio-admin user** **show** [*-f ATTRIBUTE=<value>*] [*-s FIELD*]
  *USERSPEC*

Description
===========

Subcommand for user management.

Commands
========

``create``
   Create a new user
``delegate``
   Manage delegate permission
``delete``
   Delete user
``devices``
   User mobile device management
``list``
   List users
   **Deprecated.** Use query instead.
``login``
   Test user login
``modify``
   Modify a user
``query``
   Query user attributes
``sendas``
   Manage send-as permission
``show``
   Show detailed information about a user

Options
=======

``ATTRIBUTE``
   Attributes to query. Available attributes are *ID*, *aliases*,
   *changePassword*, *chat*, *chatAdmin*, *domainID*, *forward*,
   *homeserverID*, *lang*, *ldapID*, *maildir*, *pop3_imap*, *privArchive*,
   *privChat*, *privFiles*, *privVideo*, *publicAddress*, *smtp*, *status* and
   *username*.

   If no attributes are specified, *ID*, *username* and *status* are shown.
``DEVICE``
   Limit command to given device ID(s)
``USERNAME``
   E-Mail address of the user
``USERSPEC``
   User name prefix or user ID
``-c``, ``--keep-chat``
   Deactivate but do not permanently delete chat user
``--delete-chat-user``
   Permanently delete chat user
``-f FIELD=<value>``, ``--filter FIELD=<value>``
   Filter expression in the form of ‘field=value’. Can be specified
   multiple times to refine filter
``--format FORMAT``
   Output format. Can be one of *csv*, *json-flat*, *json-structured* and
   *pretty*. Default is *pretty*.
``-k``, ``--keep-files``
   Do not delete user files from disk
``--mode MODE``
   Specify wipe status to set. Possible values are *account* and *normal*,
   or *cancel* to stop a pending wipe.
``--no-defaults``
   Do not apply configured default values
``--no-ldap``
   Detach user from LDAP object
``--nopass``
   Skip password check
``--password``
   User password. If omitted, password is retrieved from prompt.
``--remove-alias ALIAS``
   Remove ALIAS from user (can be given multiple times)
``--remove-altname ALTNAME``
   Remove ALTNAME from user (can be given multiple times)
``--remove-property PROPSPEC``
   Remove property from user (can be given multiple times)
``--remove-storeprop PROPSPEC``
   Remove property from user's store (can be given multiple times)
``--separator SEPARATOR``
   String to use for column separation (*csv* and *pretty* only). Must have
   length 1 if format is *csv*. Default is "," for *csv* and "  " for pretty.
``-s FIELD``, ``--sort FIELD``
   Sort by field. Can be given multiple times
``--token``
   Generate access and CSRF token on successful login
``-y``, ``--yes``
   Assume yes instead of prompting

Fields
======
``--changePassword <bool>``
   Whether the user can change the password
``--chat <bool>``
   Whether to create a chat user
``--chatAdmin <bool>``
   Whether the user has chat admin privileges
``--homeserver ID``
   ID of the home server or 0 for local user
``--lang LANG``
   User store language
``--ldapID LDAPID``
   Identifier of the LDAP object linked to the user
``--pop3-imap <bool>``
   Whether the user has the POP3/IMAP privilege
``--privArchive <bool>``
   Whether the user has the archiving privilege
``--privChat <bool>``
   Whether the user has the chat privilege
``--privFiles <bool>``
   Whether the user has the files privilege
``--privVideo <bool>``
   Whether the user has the video privilege
``--public-address <bool>``
   Whether the user has the public address privilege
``--smtp <bool>``
   Whether the user has the SMTP privilege
``--status STATUS``
   User address status. Either numeric value or one of *normal*, *suspended*,
   *deleted* or *shared*.
``--alias ALIAS``
   Add alias
``--altname ALTNAME``
   Add ALTNAME to user alternative login name list (can be given multiple times)
``--property propspec=value``
   Set property defined by propspec to value
``--storeprop propspec=value``
   Set store property defined by propspec to value
``--username``
   Rename user

See Also
========

**grommunio-admin**\ (1), **grommunio-admin-domain**\ (1),
**grommunio-admin-exmdb**\ (1), **grommunio-admin-fs**\ (1),
**grommunio-admin-ldap**\ (1), **grommunio-admin-passwd**\ (1),
**grommunio-admin-server**\ (1)
