========================
grommunio-admin-mconf(1)
========================

Name
====

grommunio-admin mconf — Managed configuration manipulation

Synopsis
========

| **grommunio-admin mconf** **dump** [*-c*] *CONFIG*
| **grommunio-admin mconf** **modify** *CONFIG* *unset* *KEY*
| **grommunio-admin mconf** **modify** *CONFIG* *ACTION* [*-i* \| *-b*]
  *KEY* *VALUE*
| **grommunio-admin mconf** **print** *CONFIG*
| **grommunio-admin mconf** **reload** *CONFIG*
| **grommunio-admin mconf** **save** *CONFIG*

Description
===========

grommunio managed configuration (mconf) offers the possibility to
manipulate configuration files used by gromox.

Commands
========

``dump``
   Print configuration file that would be generated from internal state
``modify``
   Modify internal configuration state
``print``
   Print internal configuration state
``reload``
   Reload configuration from disk
``save``
   Save configuration file to disk

Options
=======

``ACTION``
   Modification action:

   | *add* - Add entry to list
   | *remove* - Remove entry from list
   | *set* - Add key
   | *unset* - Remove key

``CONFIG``
   Configuration file, either *authmgr* or *ldap*
``KEY``
   Configuration key
``VALUE``
   Configuration value for numeric or boolean values use *-b* and *-i*
   respectively
``-b``, ``--bool``
   Convert value to boolean, valid values are *y*, *n*, *yes*, *no*,
   *true*, *false*, *1*, *0*
``-c``, ``--censor``
   Hide confidential information
``-i``, ``--int``
   Convert value to integer, octal (*0o*) and hexadecimal (*0x*)
   prefixes are supported

See Also
========

**grommunio-admin**\ (1), **grommunio-admin-config**\ (1),
grommunio-admin-dbconf**\ (1),**grommunio-admin-ldap**\ (1)
