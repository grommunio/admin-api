CPP=g++ -O2

build: grodbconf

grodbconf: grodbconf.cpp
	$(CPP) grodbconf.cpp -o grodbconf -lmysqlclient

clean:
	rm grodbconf
