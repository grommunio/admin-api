=========================
grommunio-admin-server(1)
=========================

Name
====

grommunio-admin server — Multi-server management

Synopsis
========

| **grommunio-admin server** **create** *-H HOSTNAME* *-e EXTNAME*]
| **grommunio-admin server** **delete** *SERVERSPEC*
| **grommunio-admin server** **list** [*-f FIELD=<value>*] [*-s FIELD*]
  [*SERVERSPEC*]
| **grommunio-admin server** **modify** [*<FIELDS>*] *SERVERSPEC*
| **grommunio-admin server** **show** [*-f FIELD=<value>*] [*-s FIELD*]
  *SERVERSPEC*

Description
===========

Subcommand to show and manipulate server entries.

If at least one server is specified, newly created users and domains will be
associated with one of the servers. The destination server may be specified
explicitely, or is chosen automatically according to `options.serverPolicy`.


Commands
========

``create``
   Register a new server
``delete``
   Soft-delete a server
``list``
   List domains
``modify``
   Modify server
``show``
   Show detailed information about a server

Options
=======

``SERVERSPEC``
   Server hostname or ID
``-f FIELD=<value>``, ``--filter FIELD=<value>``
   Filter expression in the form of ‘field=value’. Can be specified
   multiple times to refine filter
``-s FIELD``, ``--sort FIELD``
   Sort by field. Can be given multiple times

Fields
======

``-H HOSTNAME``, ``--hostname HOSTNAME``
   Internal hostname of the server
```-e EXTNAME``, ``--extname EXTNAME``
   External hostname (e.g. FQDN) of the server.

See Also
========

**grommunio-admin**\ (1), **grommunio-admin-domain**\ (1), **grommunio-admin-user**\ (1)
