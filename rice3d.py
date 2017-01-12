#!/usr/bin/env pypy3
# -*- coding: utf-8 -*-

# Copyright (C) 2017  Martijn Terpstra

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from math import sin,cos,atan,atan2,sqrt
from math import sin,cos,pi

import math
import os
import shutil
import sys
import time
import argparse

columns, rows = shutil.get_terminal_size((80, 20))

parser = argparse.ArgumentParser()
parser.add_argument("-b", "--borderwidth",
                    help="width of border in characters",
                    type=int,
                    default=0)

parser.add_argument("-F", "--framerate",
                    help="Maximum framerate when drawing multiple frames",
                    type=int,
                    default=60)

parser.add_argument("-f", "--framecount",
                    help="Number of frames to render (ignore in combination with --singleframe)",
                    type=int,
                    default=-1)

parser.add_argument("-c", "--columns",
                    help="Number of columns (widht) per frame",
                    type=int,
                    default=columns)

parser.add_argument("-l", "--lines",
                    help="Lines of output (height) per frame",
                    type=int,
                    default=rows)

parser.add_argument("-s", "--script",
                    help="Output as a BASH shell script, to be run later",
                    action="store_true")

parser.add_argument("-w", "--wireframe",
                    help="Draw model as wireframe instead of solid faces",
                    action="store_true")

parser.add_argument("-a", "--ascpectratio",
                    help="Ratio between height and length of a character \"pixel\"",
                    type=float,
                    default=1.5)

parser.add_argument("-d", "--dithering",
                    help="Dither colors rather than rounding them down",
                    action="store_true")


parser.add_argument("FILE", help=".obj file to be rendered")

ascii_gradient = " .:;=X"     # works with simple terminal
block_gradient = " ░▒▓█"        # requires unicode support
block_gradient2 = " ▁▂▃▄▅▆▇█"
grays = [16] + list(range(232,256)) + [255]
c256_gradient = ["\033[48;5;%dm\033[38;5;%dm%s"%(grays[i],grays[i+1],c)\
                 for i in range(len(grays)-1)\
                 for c in ascii_gradient] # requires 256 color support


# set gradient depending on what terminal we are using
TERM = os.environ['TERM']

if TERM in ["screen-256color","xterm-256color","xterm"]:
    # 256 colors
    color_gradient = c256_gradient
elif TERM in ["eterm-color","linux"]:
    # 8 colors only
    color_gradient = ascii_gradient
else:
    # simplest gradient that workst for sure
    color_gradient = ascii_gradient


parser.add_argument("-g", "--gradient",
                    help="string used to generate a character gradient",
                    default=color_gradient)

args = parser.parse_args()

width, height = args.columns, args.lines
zoomfactor = min(width,height)
backgroundchar = args.gradient[0]

draw_dist_min = 0
draw_dist_max = 1

dither_erorrate = 0.0

def char_from_color(z):
    global draw_dist_min
    global draw_dist_max
    global dither_erorrate
    l =len(args.gradient)
    d = (z - draw_dist_min) / ((draw_dist_max) - draw_dist_min)

    index =int(d*l)

    if args.dithering:
        error = d*l - int(index)
        dither_erorrate += error
        if dither_erorrate >= 1.0:
            dither_erorrate -= 1.0
            index+=1

    if index >= l:
        index = l-1
    elif index<0:
        index = 0
    return args.gradient[index]



triangle_buffer = []

def newscreen(w,h,c):
    # start with empty grid
    r =[[c for _w in range(w)] for _h in range(h)]


    for d in range(min(args.borderwidth,h//2)):
        # add left/right border
        escapecode      = "\033[48;5;232m\033[38;5;4m%s\033[0m"
        for y in range(d,h-d):
            r[y][w-d-1] = escapecode%"│"
            r[y][d]     = escapecode%"│"

        # add top/bottom border
        for x in range(d,w-d):
            r[d][x]     = escapecode%"─"
            r[h-d-1][x] = escapecode%"─"

        # add corners
        r[d][d]         = escapecode%"┌"
        r[h-d-1][d]     = escapecode%"└"
        r[d][w-d-1]     = escapecode%"┐"
        r[h-d-1][w-d-1] = escapecode%"┘"

    return r



screen   = newscreen(width,height,backgroundchar)
z_buffer = [[-999 for x in range(width)] for y in range(height)]

class Keypress():
    left   =  False
    right  =  False
    down   =  False
    up     =  False
    w      =  False
    a      =  False
    s      =  False
    d      =  False
    u      =  False
    i      =  False

white = 1

class Point():
    def __init__(self,x,y,z,color=white):
        self.x = x
        self.y = y
        self.z = z
        self.color=color

class Line():
    def __init__(self,p1,p2,color=white):
        self.p1=p1
        self.p2=p2
        self.color=color

class Triangle():
    def __init__(self,p1,p2,p3,color=white,outline = None):
        self.p1=p1
        self.p2=p2
        self.p3=p3
        self.color=color
        self.outline = outline

class Camera():
    def __init__(self,x=0,y=0,z=0,u=0,v=0,w=0,zoom=1.0):
        self.x = x              # position
        self.y = y
        self.z = z
        self.u = u              # angle
        self.v = v
        self.w = w
        global zoomfactor
        self.zoom = zoom * zoomfactor # zoom scale

def point_relative_to_camera(point,camera):
    """
    Gives x,y,z coordinates a point would be relative to a camera

    The projection is isomorphic, meaning distance does not decrease the size of objects.
    """

    # first we tranlate to camera
    x = point.x - camera.x
    y = point.y - camera.y
    z = point.z - camera.z

    # shorthands so the projection formula is easier to read
    sx,cx,sy,cy,sz,cz = (sin(camera.u),
                         cos(camera.u),
                         sin(camera.v),
                         cos(camera.v),
                         sin(camera.w),
                         cos(camera.w))

    # isomorphic Rotation around camera
    # Trigonomitry black magic copied from wikipedia
    # https://en.wikipedia.org/wiki/3D_projection
    x, y, z = (cy* (sz*y + cz*x) - sy*z,
               sx* (cy*z + sy*(sz*y + cz*x)) + cx*(cz*y-sz*x),
               cx* (cy*z + sy*(sz*y + cz*x)) - sx*(cz*y-sz*x))

    # add depth perception
    # get a z > 0 to avoid diving by zero
    z_tmp = max(0.01,z+draw_dist_max) * 0.5
    # multiple by z axis to get perspective
    x*= z_tmp
    y*= z_tmp

    # to zoom in/out we multiply each coordinte by a factor
    x,y,z = map(lambda a:a * camera.zoom,[x,y,z])

    color = point.color * (z / camera.zoom)

    # compensate for non-square fonts

    x *= args.ascpectratio

    return Point(x,y,z,color)

def draw_pixel(_x,_y,z):
    global screen
    global width
    global height
    global draw_dist_min
    global draw_dist_max

    x = int(width/2+_x)
    y = int(height/2-_y)
    if (x >= 0 and x < width) and (y >= 0 and y < height):
        if z_buffer[y][x] < z and z>=draw_dist_min:
            screen[y][x] = char_from_color(z)
            z_buffer[y][x] = z

def draw_line(x1,y1,x2,y2,c1,c2):
    steps = max(abs(x1-x2),abs(y1-y2))
    if steps>0:
        for s in range(int(steps+1)):
            r1 = s/steps
            r2 = 1-r1
            x = r1*x1 + r2*x2
            y = r1*y1 + r2*y2
            draw_pixel(x,y,(c1*r1 + c2*r2))
    else:
        return
        draw_pixel(x1,y2,c1)

def draw_line_relative(line,camera):
    p1 = point_relative_to_camera(line.p1,camera)
    p2 = point_relative_to_camera(line.p2,camera)
    draw_line(p1.x,p1.y,p2.x,p2.y,line.color)


class Scanbuffer():
    def __init__(self):
        global width
        global height
        self.minX=[0 for _ in range(height)]
        self.maxX=[0 for _ in range(height)]
        self.minC=[0 for _ in range(height)]
        self.maxC=[0 for _ in range(height)]
    def draw_part(self,y_min,y_max):
        for y in range(int(y_min),int(y_max)):
            draw_line(self.minX[y],y,self.maxX[y],y,self.minC[y],self.maxC[y])
    def setminmax(self,y,p1,p2):
        self.minX[y] = p1.x
        self.MaxX[y] = p2.x
        self.minC[y] = p1.color
        self.maxC[y] = p2.color
    def write_line(self,p_low,p_high,handedness):
        xdist = p_high.x - p_low.x
        ydist = p_high.y - p_low.y
        cdist = p_high.color - p_low.color
        if ydist<=0:
            return
        xstep = xdist / ydist
        cstep = cdist / ydist
        xcurrent = p_low.x
        ccurrent = p_low.color
        for y in range(int(p_low.y),int(p_high.y)+1):
            if handedness:
                self.minX[y] = int(xcurrent)
                self.minC[y] = ccurrent
            else:
                self.maxX[y] = int(xcurrent)
                self.maxC[y] = ccurrent

            xcurrent += xstep
            ccurrent += cstep

def draw_triangle(p1,p2,p3):
    # simple bubble sort
    if p1.y > p2.y:
        p1,p2 = p2,p1
    if p2.y > p3.y:
        p2,p3 = p3,p2
    if p1.y > p2.y:
        p1,p2 = p2,p1

    sbuffer = Scanbuffer()
    sbuffer.write_line(p1, p2, True)
    sbuffer.write_line(p2, p3, True)
    sbuffer.write_line(p1, p3, False)
    sbuffer.draw_part(p1.y,p3.y)

def draw_triangle_relative(triangle,camera):
    global height,width
    # get three point of triangle

    p1 = point_relative_to_camera(triangle.p1,camera)
    p2 = point_relative_to_camera(triangle.p2,camera)
    p3 = point_relative_to_camera(triangle.p3,camera)

    # if triangle is outside of screen, don't bother drawing it
    if max([p1.x,p2.x,p3.x]) < -width/2 or\
       min([p1.x,p2.x,p3.x]) > width/2 or\
       max([p1.y,p2.y,p3.y]) < -height/2 or\
       min([p1.y,p2.y,p3.y]) > height/2 or\
       max([p1.z,p2.z,p3.z]) < draw_dist_min:
        return

    if args.wireframe:
        draw_line(p1.x ,p1.y, p3.x, p3.y, p1.color, p3.color)
        draw_line(p2.x ,p2.y, p3.x, p3.y, p2.color, p3.color)
        draw_line(p1.x ,p1.y, p2.x, p2.y, p1.color, p2.color)
    else:
        draw_triangle(p1,p2,p3)


def engine_step():
    global screen
    global width
    global height
    global z_buffer
    global draw_dist_min
    p = "\n".join(["".join(line) for line in screen])
    screen = newscreen(width,height,backgroundchar)
    z_buffer = [[draw_dist_min for x in range(width)] for y in range(height)]
    return "\033[0;0H"+p

camera = Camera()

def all_numbers(n=0):
    if args.framecount > 0:
        for t in range(args.framecount):
            yield t
    else:
        while True:
            yield n
            n += 1

def load_obj(filename,camera):
    global draw_dist_min
    global draw_dist_max

    try:
        obj_file = open(filename)
    except FileNotFoundError:
        print("File not found: %s"%filename)
        quit(1)

    vertices = []
    faces = []

    for line in open(filename).readlines():
        c = line[0]
        if c == "v":
            if line[1] == "t":  # textures
                pass
            elif line[1] == "n": # normals
                pass
            else:
                coords = list(map(float,line[1:-1].split()))
                vertices.append(Point(coords[0],coords[1],coords[2]))
        elif c == "f":
            if "/" in line: # check for a/b/c syntax
                # vertex_indexes = list(map(lambda x:(int(x) - 1),line[1:-1].split()))
                indexes = [list(map(int,miniline.split("/")))[0]-1 for miniline in line[2:-1].split()]
            else:
                indexes = list(map(lambda x:(int(x) - 1),line[1:-1].split()))


            # if there are more than 3 vertices, split the face into triangles
            for i in range(0,len(indexes)-2):
                face = Triangle(vertices[indexes[0]],
                                vertices[indexes[i+1]],
                                vertices[indexes[i+2]])
                faces.append(face)
        elif len(line)<=1:
            pass
        else:
            pass
            # sys.stderr.write("Ignoring line (%s)\n"%c)

    # adjust camera for large/small models

    min_x = min(map(lambda v:v.x,vertices))
    min_y = min(map(lambda v:v.y,vertices))
    min_z = min(map(lambda v:v.z,vertices))

    max_x = max(map(lambda v:v.x,vertices))
    max_y = max(map(lambda v:v.y,vertices))
    max_z = max(map(lambda v:v.z,vertices))



    camera.x = (max_x + min_x) / 2
    camera.y = (max_y + min_y) / 2
    camera.z = (max_z + min_z) / 2


    max_dist_from_center = max([(max_x-min_x),
                                (max_y-min_y),
                                (max_z-min_z)])/2
    draw_dist_min = -max_dist_from_center
    draw_dist_max = max_dist_from_center * 1.1
    camera.zoom /= draw_dist_max**2
    return [f for f in faces]


model = load_obj(args.FILE,camera)

if args.script:
    sys.stdout.write("#!/bin/sh\n")
    sys.stdout.write("# Script generated with rice3d\n\n\n")
    sys.stdout.write("echo -e \"\033[1J\"")
    sys.stdout.write("echo -e \"\\033[?25l\"")
else:
    sys.stdout.write("\033[1J")     # escape sequence to clear screen
    sys.stdout.write("\033[?25l")   # hide cursor
try:
    old_time = time.time()
    for t in all_numbers():
        camera.u = 2*pi*t* -0.0005
        camera.v = 2*pi*t* 0.005
        camera.w = 2*pi*t* 0.00005

        for _ in model:
            draw_triangle_relative(_,camera)

        next_frame = engine_step()

        if args.script:
            sys.stdout.write("\ncat << 'EOF'\n")
            sys.stdout.write(next_frame)
            sys.stdout.write("\nEOF\n")
            sys.stdout.write("sleep %f\n"%(1/args.framerate))
            pass
        else:
            new_time = time.time()
            diff_time = new_time-old_time
            old_time = new_time
            sys.stdout.write(next_frame)
            time.sleep(max(0,(1/args.framerate)-diff_time))
except KeyboardInterrupt:
    pass

if args.script:
    sys.stdout.write("\n\necho -e \"\033[?25h\"")   # show cursor again
else:
    sys.stdout.write("\033[?25h")   # show cursor again
