all:
	cython rice3d.py --embed --verbose
	gcc -O3 -I/usr/include/python3.6m -lpython3.6m rice3d.c -o rice3d

clean:
	rm rice3d.c
	rm rice3d

