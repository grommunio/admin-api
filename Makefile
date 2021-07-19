.PHONY: tools/pyexmdb clean grodbconf

all: tools/pyexmdb grodbconf

tools/pyexmdb:
	make -C exmdbpp exmdbpp-python
	mkdir -p tools/pyexmdb
	cp exmdbpp/pyexmdb/_pyexmdb.so exmdbpp/pyexmdb/pyexmdb.py tools/pyexmdb

grodbconf:
	make -C grodbconf build

clean:
	rm -rf tools/pyexmdb
	make -C exmdbpp clean
	make -C grodbconf clean
