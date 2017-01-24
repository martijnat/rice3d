PREFIX = /usr

all:
	cython rice3d.py --embed --verbose
	gcc -O3 -I/usr/include/python3.6m -lpython3.6m rice3d.c -o rice3d-bin

install:
	mkdir -p $(DESTDIR)$(PREFIX)/bin
	cp -p rice3d-bin $(DESTDIR)$(PREFIX)/bin/rice3d

uninstall:
	rm -f $(DESTDIR)$(PREFIX)/bin/rice3d

clean:
	rm rice3d.c
	rm rice3d-bin

