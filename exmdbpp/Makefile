CPP=g++ -std=c++17 -fPIC -O2
LD=g++ -shared
SWIG=swig -c++ -python -py3

SRC=$(wildcard src/*.cpp)
OBJ=$(SRC:.cpp=.o)

PYEXMDB_DIR=pyexmdb

INCLUDE=-I include
PYTHON_INCLUDE=-I$(shell python3 -c 'import sysconfig; print(sysconfig.get_config_var("INCLUDEPY"))')

.PHONY: clean all libexmdbpp exmdbpp-python doc

all: libexmdbpp exmdbpp-python

libexmdbpp: libexmdbpp.so
exmdbpp-python: $(PYEXMDB_DIR)/_pyexmdb.so

libexmdbpp.so: $(OBJ)
	$(LD) $(OBJ) -o libexmdbpp.so

$(PYEXMDB_DIR)/_pyexmdb.so: $(OBJ) $(PYEXMDB_DIR)/pyexmdb_wrap.o
	$(LD) $(OBJ) $(PYEXMDB_DIR)/pyexmdb_wrap.o -o $(PYEXMDB_DIR)/_pyexmdb.so

$(PYEXMDB_DIR)/pyexmdb_wrap.o: $(PYEXMDB_DIR)/pyexmdb_wrap.cxx
	$(CPP) -c $(PYEXMDB_DIR)/pyexmdb_wrap.cxx -o $(PYEXMDB_DIR)/pyexmdb_wrap.o $(PYTHON_INCLUDE) $(INCLUDE)

$(PYEXMDB_DIR)/pyexmdb_wrap.cxx: pyexmdb.i | $(PYEXMDB_DIR)
	$(SWIG) -o $(PYEXMDB_DIR)/pyexmdb_wrap.cxx pyexmdb.i

$(PYEXMDB_DIR):
	mkdir -p pyexmdb

%.o: %.cpp
	$(CPP) $(INCLUDE) -c $< -o $@

clean:
	rm -rf src/*.o libexmdbpp.so $(PYEXMDB_DIR) doc

doc:
	mkdir -p doc
	doxygen
