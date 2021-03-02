CPP=g++ -O2

build: grammm-dbconf

grammm-dbconf: grammm-dbconf.cpp
	$(CPP) grammm-dbconf.cpp -o grammm-dbconf -lmysqlclient

clean:
	rm grammm-dbconf
