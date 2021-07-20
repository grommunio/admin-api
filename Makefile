.PHONY: tools/pyexmdb clean grommunio-dbconf

all: tools/pyexmdb grommunio-dbconf

tools/pyexmdb:
	make -C exmdbpp exmdbpp-python
	mkdir -p tools/pyexmdb
	cp exmdbpp/pyexmdb/_pyexmdb.so exmdbpp/pyexmdb/pyexmdb.py tools/pyexmdb

grommunio-dbconf:
	make -C grommunio-dbconf build

clean:
	rm -rf tools/pyexmdb
	make -C exmdbpp clean
	make -C grommunio-dbconf clean
