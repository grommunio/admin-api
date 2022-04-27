=======================
grommunio-admin-user(1)
=======================

Name
====

grommunio-admin user — User management

Synopsis
========

| **grommunio-admin user** **create** [*--no-defaults*] [*<FIELDS>*] *USERNAME*
| **grommunio-admin user** **delete** [*-k*] [*-y*] *USERSPEC*
| **grommunio-admin user** **list** [*-f FIELD=<value>*] [*-s FIELD*]
  [*USERSPEC*]
| **grommunio-admin user** **modify** [*<FIELDS>*] [*--no-ldap*] [*--remove-alias ALIAS*] [*--remove-property PROPSPEC*] [*--remove-storeprop PROPSPEC*] *USERSPEC*
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

``USERNAME``
   E-Mail address of the user
``USERSPEC``
   User name prefix or user ID
``-f FIELD=<value>``, ``--filter FIELD=<value>``
   Filter expression in the form of ‘field=value’. Can be specified
   multiple times to refine filter
``-k``, ``--keep-files``
   Do not delete user files from disk
``--no-defaults``
   Do not apply configured default values
``--no-ldap``
   Detach user from LDAP object
``--remove-alias ALIAS``
   Remove ALIAS from user (can be given multiple times)
``--remove-property PROPSPEC``
   Remove property from user (can be given multiple times)
``--remove-storeprop PROPSPEC``
   Remove property from user's store (can be given multiple times)
``-s FIELD``, ``--sort FIELD``
   Sort by field. Can be given multiple times
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
   *out-of-date*, *deleted* or *shared*.
``--alias ALIAS``
   Add alias
``--property propspec=value``
   Set property defined by propspec to value
``--storeprop propspec=value``
   Set store property defined by propspec to value

See Also
========

**grommunio-admin**\ (1), **grommunio-admin-domain**\ (1),
**grommunio-admin-fs**\ (1), **grommunio-admin-ldap**\ (1),
**grommunio-admin-passwd**\ (1), **grommunio-admin-server**\ (1)
