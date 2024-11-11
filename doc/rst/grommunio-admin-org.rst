..
	SPDX-License-Identifier: CC-BY-SA-4.0 or-later
	SPDX-FileCopyrightText: 2024 grommunio GmbH

=========================
grommunio-admin-org(1)
=========================

Name
====

grommunio-admin org — Organization management

Synopsis
========

| **grommunio-admin org** **create** [*--description DESCRIPTION*] [*--domain DOMAIN* …]
  *ORGNAME*
| **grommunio-admin org** **delete** *ORGSPEC*
| **grommunio-admin org** **modify** [*<FIELDS>*] *ORGSPEC*
| **grommunio-admin org** **query** [*-f ATTRIBUTE=<value>*] [*--format FORMAT*]
  [*--separator SEPARATOR*] [*-s FIELD*] [*ATTRIBUTE* …]
| **grommunio-admin org** **show** [*-f FIELD=<value>*] [*-s FIELD*]
  *ORGSPEC*

Description
===========

Subcommand to show and manipulate organizations.

Commands
========

``create``
   Create a new organization
``delete``
   Delete an organization
``modify``
   Modify organization
``query``
   Query organization attributes
``show``
   Show detailed information about an organization

Options
=======

``ATTRIBUTE``
   Attributes to query. Available attributes are *ID*, *name*, *description* and *domainCount*

   If no attributes are specified, *ID*, *name* and *domainCount* are shown.
``ORGNAME``
   Complete name of the organization
``ORGSPEC``
   Organization name prefix or organization ID
``-f FIELD=<value>``, ``--filter FIELD=<value>``
   Filter expression in the form of ‘field=value’. Can be specified
   multiple times to refine filter
``--format FORMAT``
   Output format. Can be one of *csv*, *json-flat*, *json-kv*, *json-object*,
   *json-structured* and *pretty*. Default is *pretty*.
``--separator SEPARATOR``
   String to use for column separation (*csv* and *pretty* only). Must have
   length 1 if format is *csv*. Default is "," for *csv* and "  " for pretty.
``-s FIELD``, ``--sort FIELD``
   Sort by field. Can be given multiple times
``-y``, ``--yes``
   Assume yes instead of prompting

Fields
======

``--description DESCRIPTION``
   Description of the organization
``--domain DOMAINSPEC``
   Name prefix or ID of the domain to adopt. Can be given multiple times
``--name ORGNAME``
   Name of the organization

See Also
========

**grommunio-admin**\ (1), **grommunio-admin-domain**\ (1),
**grommunio-admin-ldap**\ (1)
