==========================
grommunio-admin-version(1)
==========================

Name
====

grommunio-admin version — Show backend and/or API version

Synopsis
========

**grommunio-admin version** [*-a*] [*-b*] [*-c*]

Description
===========

| Show the current version of the API (specification) or the backend
  (code).
| The combined mode (default) appends the difference between between
  backend and API version at the end of the API version.

If multiple options are given, each requested version is printed on a
separate line. The order is always API – backend – combined.

Options
=======

``-a``, ``--api``
   Print API version
``-b``, ``--backend``
   Print backend version
``-c``, ``--combined``
   Print combined version

See Also
========

**grommunio-admin**\ (1)
