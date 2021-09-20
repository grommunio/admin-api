# -*- Makefile -*-

ACLOCAL_AMFLAGS = -I build-aux
SUBDIRS = exmdbpp grommunio-dbconf

tools/pyexmdb:
	${MKDIR_P} tools/pyexmdb
	cp exmdbpp/pyexmdb/_pyexmdb.so exmdbpp/pyexmdb/pyexmdb.py tools/pyexmdb

man:
	${MAKE} -C doc doc

clean-local:
	rm -rf tools/pyexmdb
	${MAKE} -C doc clean
