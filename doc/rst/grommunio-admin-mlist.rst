..
	SPDX-License-Identifier: CC-BY-SA-4.0 or-later
	SPDX-FileCopyrightText: 2021 grommunio GmbH

========================
grommunio-admin-mlist(1)
========================

Name
====

grommunio-admin mlist — Mailing/distribution list management

Synopsis
========

| **grommunio-admin mlist** **add** *MLISTSPEC*
  (*sender*\ \|\ *recipient*) *ENTRY* **grommunio-admin mlist**
  **create** [*-c CLASS*] [*-p PRIVILEGE*] [*-r RECIPIENT*] [*-s
  SENDER*] [*-t TYPE*] NAME
| **grommunio-admin mlist** **delete** [*-y*] *MLISTSPEC*
| **grommunio-admin mlist** **list** [*-f FIELD=<value>*] [*-s FIELD*]
  [*MLISTSPEC*]
| **grommunio-admin mlist** **modify** [*-c CLASS*] [*-p PRIVILEGE*]
  [*-r RECIPIENT*] *MLISTSPEC* **grommunio-admin mlist** **remove**
  *MLISTSPEC* (*sender*\ \|\ *recipient*) *ENTRY* **grommunio-admin
  mlist** **show**

Description
===========

Create, modify or delete mailing lists.

Commands
========

``add``
   Add sender or recipient to list
``create``
   Create a new mailing list
``delete``
   Delete mailing list
``list``
   List mailing lists
``modify``
   Modify mailing list
``remove``
   Remove sender or recipient from list
``show``
   Show detailed information about mailing list

Options
=======

``-c CLASS``, ``--class CLASS``
   ID of the associated class (class type only)
``-p PRIVILEGE``, ``--privilege PRIVILEGE``
   Set who is allowed to send mails to the list, one of *all*, *domain*,
   *internal*, *outgoing* or *specific*
``-f FIELD=<value>``, ``--filter FIELD=<value>``
   Filter expression in the form of ‘field=value’. Can be specified
   multiple times to refine filter
``-s FIELD``, ``--sort FIELD``
   Sort by field. Can be given multiple times
``-t TYPE``, ``--type TYPE``
   List type (recipient selection), one of *normal*, *domain* or *class*

See Also
========

**grommunio-admin**\ (1), **grommunio-admin-domain**\ (1),
**grommunio-admin-user**\ (1)
