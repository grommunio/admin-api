CPP=g++ -O2
MYSQL_INCLUDE=$(shell pkg-config libmariadb --cflags)
MYSQL_LINK=$(shell pkg-config libmariadb --libs)

build: grommunio-dbconf

grommunio-dbconf: grommunio-dbconf.cpp
	$(CPP) grommunio-dbconf.cpp -o grommunio-dbconf $(MYSQL_INCLUDE) $(MYSQL_LINK)

clean:
	rm -f grommunio-dbconf
