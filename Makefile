.PHONY: tools/pyexmdb clean

tools/pyexmdb:
	make -C exmdbpp exmdbpp-python
	mkdir -p tools/pyexmdb
	cp exmdbpp/pyexmdb/_pyexmdb.so exmdbpp/pyexmdb/pyexmdb.py tools/pyexmdb

clean:
	rm -rf tools/pyexmdb
	make -C exmdbpp clean
