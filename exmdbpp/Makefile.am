# -*- Makefile -*-

AM_CPPFLAGS = -I${srcdir}/include ${python_CFLAGS}
AM_CXXFLAGS = -std=c++17
SWIG_CXXFLAGS = -Wall -python -py3 -c++ -threads -I${srcdir}/include
PYTHON_INCLUDE=-I$(shell python3 -c 'import sysconfig; print(sysconfig.get_config_var("INCLUDEPY"))')

lib_LTLIBRARIES = libexmdbpp.la
pyexec_LTLIBRARIES = _pyexmdb.la
BUILT_SOURCES = pyexmdb/pyexmdb_wrap.h pyexmdb/pyexmdb_wrap.cxx
libexmdbpp_la_SOURCES = src/ExmdbClient.cpp src/queries.cpp src/requests.cpp src/structures.cpp src/util.cpp
noinst_DATA = pyexmdb/pyexmdb.py
nodist__pyexmdb_la_SOURCES = pyexmdb/pyexmdb_wrap.cxx
_pyexmdb_la_LIBADD = libexmdbpp.la ${python_LIBS}
_pyexmdb_la_LDFLAGS = -avoid-version -module

-include .*.dep

pyexmdb/pyexmdb.py: pyexmdb/pyexmdb_wrap.h
pyexmdb/pyexmdb_wrap.h: pyexmdb/pyexmdb_wrap.cxx
pyexmdb/pyexmdb_wrap.cxx: pyexmdb.i
	@if test "x$(SWIG_EXEC)" = "x"; then echo "swig is required for 'make dist'"; exit 1; fi
	${MKDIR_P} pyexmdb
	${AM_V_GEN}${SWIG_EXEC} -I${srcdir}/include ${SWIG_CXXFLAGS} -o $@ $<
	${MKDIR_P} ${top_srcdir}/tools/pyexmdb/
	cp -avf pyexmdb/pyexmdb.py ${top_srcdir}/tools/pyexmdb/

doc:
	${MKDIR_P} doc
	doxygen

clean-local:
	rm -Rf doc

all-am: copy-so

copy-so: _pyexmdb.la
	${MKDIR_P} ${top_srcdir}/tools/pyexmdb/
	cp -avf .libs/_pyexmdb.so ${top_srcdir}/tools/pyexmdb/

.PHONY: copy-so
