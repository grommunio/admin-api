======================
grommunio-admin-run(1)
======================

Name
====

grommunio-admin run — Start a stand-alone HTTP server

Synopsis
========

**grommunio-admin run** [*-d*] [*-i IP*] [*--no-config-check*] [*-p
PORT*]

Description
===========

Run REST API in a stand-alone HTTP server.

| **—–DO NOT USE IN PRODUCTION!—–**
| This command is intended for development and testing. A production
  instance should use an external WSGI server like *uwsgi*.

Options
=======

``-d``, ``--debug``
   Enable debug mode
``-i IP``, ``--ip IP``
   Host address to bind to (default ::)
``--no-config-check``
   Skip configuration check
``-p PORT``, ``--port PORT``
   Host port to bind to (default 5001)

See Also
========

**grommunio-admin**\ (1), **grommunio-admin-config**\ (1)
