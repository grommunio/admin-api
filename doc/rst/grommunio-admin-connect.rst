==========================
grommunio-admin-connect(1)
==========================

Name
====

grommunio-admin connect — Connect to remote CLI

Synopsis
========

**grommunio-admin connect** [-c COMMAND] [--no-verify] [--redirect-fs
[--auto-save (local\|remote\|discard\|print)]] [-v] HOST [USER [PASSWORD]]

Description
===========

| Connect to a remote server to invoke CLI commands on.
| Requires a running admin API with active remote CLI and a user with
  ``SystemAdminPermission``.

Note that the remote CLI currently uses a REST interface which does not
provide a standard input, rendering commands that rely on user
interaction useless.

Options
=======

``HOST``
   Host to connect to, in the format *protocol*://*hostname*:*port*,
   where protocol is either http or https. If omitted, the protocol is
   auto-detected, with https taking precendence over http. If no port is
   specified, the default ports 8080 (http) and 8443 (https) are used.
``PASSWORD``
   Password to use for authentication. Default is to prompt.
``USER``
   User to use for authentication. Defaults is *admin*.
``--auto-save ACTION``
   Choose automatic action for received files when filesystem
   redirection is enabled. Possible actions are:

   | *discard* - discard any received file
   | *local* - save at local path
   | *print* - print file contents to stdout and discard
   | *remote* - save at path reported from remote server

``-c``, ``--command``
   Execute command on remote server and exit instead of starting an
   interactive shell.
``--no-verify``
   Continue with https even if the TLS certificate presented by the
   server is invalid. Required if the server uses a self-signed
   certificate that is not installed on the system. Use with caution.
``--redirect-fs``
   Redirect CLI initiated file operations to local filesystem. See
   section *Filesystem Emulation* for details.
``-v``, ``--verbose``
   Print more detailed information about the connection process.

Filesystem Emulation
====================

When the *--redirect-fs* option is given, CLI initiated file operations
are performed in an emulated filesystem and written files are sent back
to the client.

Note that this does only apply to files which are opend by CLI
operations, while module-level operations (e.g. loading of
configurations) are unaffected.

Files received from the remote server can then be viewed or saved
locally.

See Also
========

**grommunio-admin**\ (1), **grommunio-admin-shell**\ (1)
