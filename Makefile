.PHONY: tools/pyexmdb clean grammm-dbconf

all: tools/pyexmdb grammm-dbconf

tools/pyexmdb:
	make -C exmdbpp exmdbpp-python
	mkdir -p tools/pyexmdb
	cp exmdbpp/pyexmdb/_pyexmdb.so exmdbpp/pyexmdb/pyexmdb.py tools/pyexmdb

grammm-dbconf:
	make -C grammm-dbconf build

clean:
	rm -rf tools/pyexmdb
	make -C exmdbpp clean
	make -C grammm-dbconf clean
