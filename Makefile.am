# -*- Makefile -*-

ACLOCAL_AMFLAGS = -I build-aux
SUBDIRS = exmdbpp grommunio-dbconf

xxdir = ${libexecdir}/grommunio-admin-api
xx_DATA = data/api-config.ini data/config.yaml
nobase_xx_DATA = ${apifiles} ${clifiles} ${endpfiles} ${ormfiles} ${resfiles} ${srvfiles} ${toolfiles}
apifiles = api/__init__.py api/core.py api/errors.py api/security.py
clifiles = cli/__init__.py cli/common.py cli/config.py cli/dbconf.py cli/dbtools.py cli/domain.py cli/fetchmail.py cli/fs.py cli/ldap.py cli/mconf.py cli/misc.py cli/mlist.py cli/remote.py cli/user.py
endpfiles = endpoints/__init__.py endpoints/misc.py endpoints/domain/__init__.py endpoints/domain/classes.py endpoints/domain/folders.py endpoints/domain/ldap.py endpoints/domain/misc.py endpoints/domain/mlists.py endpoints/domain/users.py endpoints/system/__init__.py endpoints/system/dbconf.py endpoints/system/domains.py endpoints/system/logs.py endpoints/system/mconf.py endpoints/system/misc.py endpoints/system/roles.py
ormfiles = orm/__init__.py orm/classes.py orm/domains.py orm/misc.py orm/mlists.py orm/roles.py orm/users.py
resfiles = res/config.yaml res/domain.sqlite3 res/ldapTemplates.yaml res/midb.sqlite3 res/openapi.yaml res/user.sqlite3
srvfiles = services/chat.py services/exmdb.py services/__init__.py services/ldap.py services/redis.py services/systemd.py
toolfiles = tools/DataModel.py tools/classfilters.py tools/config.py tools/constants.py tools/dbconf.py tools/formats.py tools/license.py tools/logs.py tools/mconf.py tools/misc.py tools/permissions.py tools/rop.py tools/storage.py tools/structures.py main.py

compldir = ${datadir}/bash-completion/completions
compl_DATA = res/autocomplete.sh

gacdir = ${datadir}/grommunio-admin-common
gac_DATA = data/portrait.jpg

nginxdir = ${gacdir}/nginx.d
nginx_DATA = data/api.conf

unit_DATA = data/grommunio-admin-api.service data/grommunio-admin-api.socket
tmpfiles_DATA = data/tmpfiles-grommunio-admin-api.conf

polkitdir = ${datadir}/polkit-1/rules.d
polkit_DATA = data/pkit-10-gromox.rules

man_MANS = doc/man/grommunio-admin-config.1 doc/man/grommunio-admin-connect.1 doc/man/grommunio-admin-dbconf.1 doc/man/grommunio-admin-domain.1 doc/man/grommunio-admin-fetchmail.1 doc/man/grommunio-admin-fs.1 doc/man/grommunio-admin-ldap.1 doc/man/grommunio-admin-mconf.1 doc/man/grommunio-admin-mlist.1 doc/man/grommunio-admin-passwd.1 doc/man/grommunio-admin-run.1 doc/man/grommunio-admin-shell.1 doc/man/grommunio-admin-taginfo.1 doc/man/grommunio-admin-user.1 doc/man/grommunio-admin-version.1 doc/man/grommunio-admin.1 doc/man/grommunio-dbconf.1

man:
	${MAKE} -C doc doc

install-exec-local:
	${MKDIR_P} ${DESTDIR}${sbindir}
	ln -sv ${xxdir}/main.py ${DESTDIR}${sbindir}/grommunio-admin

clean-local:
	rm -rf tools/pyexmdb
	${MAKE} -C doc clean
