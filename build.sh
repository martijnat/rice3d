#!/bin/bash
# required packages cython
cython --embed -3 rice3d.py
gcc -O3 `pkg-config --libs --cflags python3` rice3d.c -o rice3d

