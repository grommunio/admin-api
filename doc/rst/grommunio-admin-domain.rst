=========================
grommunio-admin-domain(1)
=========================

Name
====

grommunio-admin domain — Domain management

Synopsis
========

| **grommunio-admin domain** **create** [*<FIELDS>*] [*--create-role*]
  [*--skip-adaptor-reload*] *-u MAXUSER* *DOMAINNAME*
| **grommunio-admin domain** **delete** *DOMAINSPEC*
| **grommunio-admin domain** **list** [*-f FIELD=<value>*] [*-s FIELD*]
  [*DOMAINSPEC*]
| **grommunio-admin domain** **modify** [*<FIELDS>*] *DOMAINSPEC*
| **grommunio-admin domain** **purge** [*--files*] [*-y*] *DOMAINSPEC*
| **grommunio-admin domain** **recover** *DOMAINSPEC*
| **grommunio-admin domain** **show** [*-f FIELD=<value>*] [*-s FIELD*]
  *DOMAINSPEC*

Description
===========

Subcommand to show and manipulate domains.

Commands
========

``create``
   Create a new domain
``delete``
   Soft-delete a domain
``list``
   List domains
``modify``
   Modify domain
``purge``
   Permanently delete domain
``recover``
   Recover a soft-deleted domain
``show``
   Show detailed information about a domain

Options
=======

``DOMAINNAME``
   Complete name of the domain
``DOMAINSPEC``
   Domain name prefix or domain ID
``--create-role``
   Automatically create a domain administrator role for the new domain
``--files``
   Also delete files from disk
``-f FIELD=<value>``, ``--filter FIELD=<value>``
   Filter expression in the form of ‘field=value’. Can be specified
   multiple times to refine filter
``-s FIELD``, ``--sort FIELD``
   Sort by field. Can be given multiple times
``-y``, ``--yes``
   Assume yes instead of prompting

Fields
======

``--address ADDRESS``
   Content of address field
``--adminName ADMINNAME``
   Name of the domain administrator or primary contact
``--endDay ENDDAY``
   Date of domain expiration in YYYY-MM-DD format
``--orgID ID``
   ID of the organization to assign the domain to
``--tel TEL``
   Telephone number of domain administrator or primary contact
``-u MAXUSER``, ``--maxUser MAXUSER``
   Maxmimum number of users in the domain

See Also
========

**grommunio-admin**\ (1), **grommunio-admin-fs**\ (1), **grommunio-admin-user**\ (1)
