.PHONY: tools/pyexmdb clean grommunio-dbconf

all: tools/pyexmdb grommunio-dbconf

tools/pyexmdb:
	${MAKE} -C exmdbpp exmdbpp-python
	mkdir -p tools/pyexmdb
	cp exmdbpp/pyexmdb/_pyexmdb.so exmdbpp/pyexmdb/pyexmdb.py tools/pyexmdb

grommunio-dbconf:
	${MAKE} -C grommunio-dbconf build

man:
	${MAKE} -C doc doc

clean:
	rm -rf tools/pyexmdb
	${MAKE} -C exmdbpp clean
	${MAKE} -C grommunio-dbconf clean
	${MAKE} -C doc clean
