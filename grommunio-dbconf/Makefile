CPP=g++ -O2

build: grommunio-dbconf

grommunio-dbconf: grommunio-dbconf.cpp
	$(CPP) grommunio-dbconf.cpp -o grommunio-dbconf -lmysqlclient

clean:
	rm grommunio-dbconf
