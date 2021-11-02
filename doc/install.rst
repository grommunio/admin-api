Source run procedure
====================

To make use of the basic Admin API command-line interface, one will need:

* python3-Flask-SQLAlchemy
* python3-argcomplete
* python3-ldap3
* python3-mattermostdriver
* python3-multidict
* python3-redis
* python3-requests
* python3-sqlalchemy

To run the AAPI CLI from a source checkout, one has to copy
``data/config.yaml`` and overwrite ``config.yaml`` before starting ``main.py``.


Minimal configuration
=====================

SQL database
------------

A MariaDB/MySQL database is used to store (and replicate, if so needed later)
users, groups and other objects like distribution lists. Configuration is done
through ``/etc/grommunio-admin-api/conf.d/database.yaml``, where hostname,
access credentials, etc. are located.::

	DB:
	  host: 'localhost'
	  user: 'grommunio'
	  pass: 'secret'
	  database: 'grommunio'

AAPI requires broad write permissions to the database.


Synchronization from LDAP
=========================

Users can be imported/synchronized from an existing LDAP tree to MySQL.
Configuration is done through ``/etc/gromox/ldap_adaptor.cfg``, where hostname,
access credentials, etc. are located. Admin API re-uses this Gromox config file
and recognizes additional directives that are specific to AAPI. The Gromox
manpage ldap_adaptor(4gx) has both directive sets documented.

To use AAPI's LDAP user synchronization mechanism, ``ldap_adaptor.cfg`` needs to be
extended by the sync-related directives. A quickstart for OpenLDAP::

	ldap_search_base=o=com
	ldap_bind_user=o=com
	ldap_host=ldap://localhost
	ldap_bind_pass=secret
	ldap_start_tls=false

	# for grommunio-admin-api
	ldap_object_id=entryUUID
	ldap_mail_attr=mail
	ldap_user_displayname=displayName
	ldap_user_filter=(objectClass=posixAccount)
	ldap_user_search_attrs=mail
	ldap_user_search_attrs=givenName
	ldap_user_search_attrs=cn
	ldap_user_search_attrs=sn
	ldap_user_search_attrs=displayName
	ldap_user_search_attrs=gecos
	ldap_user_templates=common
	ldap_user_templates=OpenLDAP
	ldap_user_aliases=mailAlternativeAddress


Minimal LDAP test server
------------------------

For our own recollection, these are the steps for a minimally-populated LDAP
server for testing:

* Install ``openldap2``

* Edit ``/etc/openldap/slapd.conf``. This is the OpenLDAP server configuration.
  There will be one line, ``moduleload back_mdb.la``, which should be
  uncommented. Further down below in the file, there should already be an
  example database instance section, starting with ``database mdb``; if not,
  add it. Set a suffix and password of choice such that it is consistent with
  the LDAP config from the previous section of this install document;;
  ultimately, it should look like::

    database mdb
    suffix o=com
    rootdn o=com
    rootpw secret
    directory /var/lib/ldap
    index objectClass eq

* Edit ``/etc/openldap/ldap.conf``, this is the libldap client-side
  configuration; it should look something like::

    BASE o=com
    URI ldap://localhost

* Restart OpenLDAP: ``systemctl restart slapd``

* Verify connectivity using ``ldapsearch -x``. What you do _not_ want to see:
  ``Can't contact LDAP server``. What should be shown: ``result: 32 No such
  object``. This is because the LDAP tree is still empty.

* Populate a temporary file with the following LDIF content::

    dn: o=com
    objectClass: organization

    dn: uid=jdoe,o=com
    objectClass: posixAccount
    objectClass: inetOrgPerson
    objectClass: shadowAccount
    givenName: John
    sn: Doe
    displayName: John Doe
    uid: jdoe
    homeDirectory: /home/jdoe
    gecos: John Doe
    loginShell: /bin/bash
    shadowFlag: 0
    shadowMin: 0
    shadowMax: 99999
    shadowWarning: 0
    shadowInactive: 99999
    shadowLastChange: 12011
    shadowExpire: 99999
    cn: John Doe
    uidNumber: 11111
    o: com
    title: Test User
    gidNumber: 1000
    mail: jdoe@example.com
    postalAddress: 1 Broad St
    postalCode: 10005
    l: NYC
    mobile: +18006874668
    telephoneNumber: +18004489887

* Populate the LDAP tree with the temp file: ``ldapadd -D o=com -xw secret
  <temp.ldif``. The ldapsearch command from before should now return the
  objects so added.

After having added ``example.com`` to the list of domains known to Grommunio
as a whole (add via AWEB for now), one can start the synchronization, which
will look like this::

	# grommunio-admin ldap downsync --complete
	Synchronizing 1 user...
	Synchronize user 'John Doe' (jdoe@example.com)? [y/N]:
