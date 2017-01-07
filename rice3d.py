#!/usr/bin/env python3

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

size = width, height = 80, 24

try:
    columns, rows = shutil.get_terminal_size((80, 20))
    size = width, height = columns ,rows
except:
    pass

zoomfactor = min(width,height)

engine_version = "0.6"

draw_faces     = True
draw_wireframe = not draw_faces
debug_draw     = False
borderwidth    = 0
target_fps     = 60
single_frame   = False

ascii_gradient = " .:;+=xX$&"     # works with simple terminal
block_gradient = " ░▒▓█"        # requires unicode support
block_gradient2 = " ▁▂▃▄▅▆▇█"
grays = [16] + list(range(232,255)) + [255]
c256_gradient = ["\033[48;5;%dm\033[38;5;%dm%s"%(grays[i],grays[i+1],c)\
                 for i in range(len(grays)-1)\
                 for c in ascii_gradient] # requires 256 color support

c256_gradient2 = ["\033[48;5;%dm\033[38;5;%dm%s"%(grays[i],grays[i+1],c)\
                  for i in range(len(grays)-1)\
                  for c in block_gradient2]

# set gradient depending on what terminal we are using
TERM = os.environ['TERM']

if TERM in ["screen-256color","xterm-256color","xterm"]:
    # 256 colors
    color_gradient = c256_gradient
elif TERM in ["eterm-color"]:
    # 8 colors only
    color_gradient = ascii_gradient
elif TERM in ["linux"]:          # tty
    color_gradient = block_gradient
else:
    # simplest gradient that workst for sure
    color_gradient = ascii_gradient

backgroundchar = color_gradient[0]
draw_dist_min = 0
draw_dist_max = 1

def char_from_color(v):
    global draw_dist_min
    global draw_dist_max
    # go from range min_v,mav_v to [0,1]
    d = (v - draw_dist_min) / (draw_dist_max - draw_dist_min)

    gi =int(d*(len(color_gradient))-0.5)
    if gi >= len(color_gradient):
        gi = len(color_gradient)-1
    elif gi<0:
        gi = 0
    return color_gradient[gi]



triangle_buffer = []

def newscreen(w,h,c):
    # start with empty grid
    r =[[c for _w in range(w)] for _h in range(h)]


    for d in range(min(borderwidth,h//2)):
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

def generate_floor(x_start,x_end,y_start,y_end,tile_size=1):
    for x in range(x_start,x_end,tile_size):
        for y in range(y_start,y_end,tile_size):
            p1 = Point(x,y,1)
            p2 = Point(x,y+tile_size,1)
            p3 = Point(x+tile_size,y,1)
            p4 = Point(x+tile_size,y+tile_size,1)

            yield Triangle(p1,p2,p3, (164,164,164))
            yield Triangle(p2,p3,p4, (128,128,128))

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

    x *= 1.6

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
        if z_buffer[y][x] < z and z>=draw_dist_min and z<=draw_dist_max:
            screen[y][x] = char_from_color(z)
            z_buffer[y][x] = z

def draw_line(x1,y1,x2,y2,c1,c2):
    steps = max(abs(x1-x2),abs(y1-y2))
    if steps>1:
        for s in range(int(steps+2)):
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

    # sys.stdout.write("\033[0;0H"+"\n".join(["".join(line) for line in screen]))

    if draw_faces:
        edge_length = int(max(map((lambda p:max(map(abs,[(p[0].x - p[1].x),(p[0].y - p[1].y)]))),
                                  [(p1,p2),(p2,p3),(p3,p1)])))

        for r in [t/edge_length for t in range(edge_length)]:
            _x3 = r*p1.x + (1-r)*p2.x
            _y3 = r*p1.y + (1-r)*p2.y
            _c3 = r*p1.color + (1-r)*p2.color

            _x1 = r*p3.x + (1-r)*p2.x
            _y1 = r*p3.y + (1-r)*p2.y
            _c1 = r*p3.color + (1-r)*p2.color

            _x2 = r*p1.x + (1-r)*p3.x
            _y2 = r*p1.y + (1-r)*p3.y
            _c2 = r*p1.color + (1-r)*p3.color

            draw_line(p3.x,p3.y,_x3,_y3,p3.color,_c3)
            draw_line(p2.x,p2.y,_x2,_y2,p2.color,_c2)
            draw_line(p1.x,p1.y,_x1,_y1,p1.color,_c1)


    if draw_wireframe:
        draw_line(p1.x ,p1.y, p3.x, p3.y, p1.color, p3.color)
        draw_line(p2.x ,p2.y, p3.x, p3.y, p2.color, p3.color)
        draw_line(p1.x ,p1.y, p2.x, p2.y, p1.color, p2.color)


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

model_tetrahedron = [Triangle(Point(0,-1,1) ,Point(0,-1,-1),Point(-1,1,0)),
                     Triangle(Point(0,-1,-1),Point(0,-1,1) ,Point(1,1,0)),
                     Triangle(Point(1,1,0)  ,Point(-1,1,0)  ,Point(0,-1,1)),
                     Triangle(Point(1,1,0)  ,Point(-1,1,0)  ,Point(0,-1,-1)),]

cube_point = [Point(x,y,z) for x in [-.6,.6] for y in [-.6,.6] for z in [-.6,.6]]
model_cube = [Triangle(cube_point[0b000],cube_point[0b001],cube_point[0b010]),
              Triangle(cube_point[0b001],cube_point[0b010],cube_point[0b011]),
              Triangle(cube_point[0b100],cube_point[0b101],cube_point[0b110]),
              Triangle(cube_point[0b101],cube_point[0b110],cube_point[0b111]),
              Triangle(cube_point[0b000],cube_point[0b100],cube_point[0b001]),
              Triangle(cube_point[0b100],cube_point[0b001],cube_point[0b101]),
              Triangle(cube_point[0b010],cube_point[0b110],cube_point[0b011]),
              Triangle(cube_point[0b110],cube_point[0b011],cube_point[0b111]),
              Triangle(cube_point[0b000],cube_point[0b010],cube_point[0b100]),
              Triangle(cube_point[0b010],cube_point[0b100],cube_point[0b110]),
              Triangle(cube_point[0b001],cube_point[0b011],cube_point[0b101]),
              Triangle(cube_point[0b011],cube_point[0b101],cube_point[0b111]),]


pm = [-1,1]                     # plus or minus
model_octahedron = [Triangle(Point(x,0,0),
                             Point(0,y,0),
                             Point(0,0,z))
                    for x in pm
                    for y in pm
                    for z in pm]

phi= (1 + sqrt(5)) / 2 # golden ratio
model_icosahedron = [Triangle(  Point(0,1/phi,-1),   Point(1/phi,1,0),    Point(-1/phi,1,0)),
                     Triangle(  Point(0,1/phi,1),    Point(-1/phi,1,0),   Point(1/phi,1,0)),
                     Triangle(  Point(0,1/phi,1),    Point(0,-1/phi,1),   Point(-1,0,1/phi)),
                     Triangle(  Point(0,1/phi,1),    Point(1,0,1/phi),    Point(0,-1/phi,1)),
                     Triangle(  Point(0,1/phi,-1),   Point(0,-1/phi,-1),  Point(1,0,-1/phi)),
                     Triangle(  Point(0,1/phi,-1),   Point(-1,0,-1/phi),  Point(0,-1/phi,-1)),
                     Triangle(  Point(0,-1/phi,1),   Point(1/phi,-1,0),   Point(-1/phi,-1,0)),
                     Triangle(  Point(0,-1/phi,-1),  Point(-1/phi,-1,0),  Point(1/phi,-1,0)),
                     Triangle(  Point(-1/phi,1,0),   Point(-1,0,1/phi),   Point(-1,0,-1/phi)),
                     Triangle(  Point(-1/phi,-1,0),  Point(-1,0,-1/phi),  Point(-1,0,1/phi)),
                     Triangle(  Point(1/phi,1,0),    Point(1,0,-1/phi),   Point(1,0,1/phi)),
                     Triangle(  Point(1/phi,-1,0),   Point(1,0,1/phi),    Point(1,0,-1/phi)),
                     Triangle(  Point(0,1/phi,1),    Point(-1,0,1/phi),   Point(-1/phi,1,0)),
                     Triangle(  Point(0,1/phi,1),    Point(1/phi,1,0),    Point(1,0,1/phi)),
                     Triangle(  Point(0,1/phi,-1),   Point(-1/phi,1,0),   Point(-1,0,-1/phi)),
                     Triangle(  Point(0,1/phi,-1),   Point(1,0,-1/phi),   Point(1/phi,1,0)),
                     Triangle(  Point(0,-1/phi,-1),  Point(-1,0,-1/phi),  Point(-1/phi,-1,0)),
                     Triangle(  Point(0,-1/phi,-1),  Point(1/phi,-1,0),   Point(1,0,-1/phi)),
                     Triangle(  Point(0,-1/phi,1),   Point(-1/phi,-1,0),  Point(-1,0,1/phi)),
                     Triangle(  Point(0,-1/phi,1),   Point(1,0,1/phi),    Point(1/phi,-1,0))]

dodecahedron_points = [[Point( (2-phi), 0, 1),  Point(-(2-phi), 0, 1),  Point(-(1/phi), (1/phi), (1/phi)),  Point( 0, 1, (2-phi)),  Point( (1/phi), (1/phi), (1/phi))],
                       [Point(-(2-phi), 0, 1),  Point( (2-phi), 0, 1),  Point( (1/phi),-(1/phi), (1/phi)),  Point( 0,-1, (2-phi)),  Point(-(1/phi),-(1/phi), (1/phi))],
                       [Point( (2-phi), 0,-1),  Point(-(2-phi), 0,-1),  Point(-(1/phi),-(1/phi),-(1/phi)),  Point( 0,-1,-(2-phi)),  Point( (1/phi),-(1/phi),-(1/phi))],
                       [Point(-(2-phi), 0,-1),  Point( (2-phi), 0,-1),  Point( (1/phi), (1/phi),-(1/phi)),  Point( 0, 1,-(2-phi)),  Point(-(1/phi), (1/phi),-(1/phi))],
                       [Point( 0, 1,-(2-phi)),  Point( 0, 1, (2-phi)),  Point( (1/phi), (1/phi), (1/phi)),  Point( 1, (2-phi), 0),  Point( (1/phi), (1/phi),-(1/phi))],
                       [Point( 0, 1, (2-phi)),  Point( 0, 1,-(2-phi)),  Point(-(1/phi), (1/phi),-(1/phi)),  Point(-1, (2-phi), 0),  Point(-(1/phi), (1/phi), (1/phi))],
                       [Point( 0,-1,-(2-phi)),  Point( 0,-1, (2-phi)),  Point(-(1/phi),-(1/phi), (1/phi)),  Point(-1,-(2-phi), 0),  Point(-(1/phi),-(1/phi),-(1/phi))],
                       [Point( 0,-1, (2-phi)),  Point( 0,-1,-(2-phi)),  Point( (1/phi),-(1/phi),-(1/phi)),  Point( 1,-(2-phi), 0),  Point( (1/phi),-(1/phi), (1/phi))],
                       [Point( 1, (2-phi), 0),  Point( 1,-(2-phi), 0),  Point( (1/phi),-(1/phi), (1/phi)),  Point( (2-phi), 0, 1),  Point( (1/phi), (1/phi), (1/phi))],
                       [Point( 1,-(2-phi), 0),  Point( 1, (2-phi), 0),  Point( (1/phi), (1/phi),-(1/phi)),  Point( (2-phi), 0,-1),  Point( (1/phi),-(1/phi),-(1/phi))],
                       [Point(-1, (2-phi), 0),  Point(-1,-(2-phi), 0),  Point(-(1/phi),-(1/phi),-(1/phi)),  Point(-(2-phi), 0,-1),  Point(-(1/phi), (1/phi),-(1/phi))],
                       [Point(-1,-(2-phi), 0),  Point(-1, (2-phi), 0),  Point(-(1/phi), (1/phi), (1/phi)),  Point(-(2-phi), 0, 1),  Point(-(1/phi),-(1/phi), (1/phi))]]

model_dodecahedron = [Triangle(p1,p2,p3) for (p1,p2,p3,p4,p5) in dodecahedron_points] +\
                     [Triangle(p1,p3,p4) for (p1,p2,p3,p4,p5) in dodecahedron_points] +\
                     [Triangle(p1,p4,p5) for (p1,p2,p3,p4,p5) in dodecahedron_points]


camera = Camera()

def all_numbers(n=0):
    while not single_frame:
        yield n
        n += 1
    yield 0


builtin_models = [model_tetrahedron,
                  model_cube,
                  model_octahedron,
                  model_icosahedron,
                  model_dodecahedron]


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
    max_x = 0.0
    min_x = 0.0
    max_y = 0.0
    min_y = 0.0
    max_z = 0.0
    min_z = 0.0

    for line in open(filename).readlines():
        c = line[0]
        if c == "v":
            if line[1] == "t":  # textures
                pass
            elif line[1] == "n": # normals
                pass
            else:
                coords = list(map(float,line[1:-1].split()))
                x,y,z = coords[0],coords[1],coords[2]
                vertices.append(Point(x,y,z))
                max_x = max(x,max_x)
                min_x = min(x,min_x)
                max_y = max(y,max_y)
                min_y = min(y,min_y)
                max_z = max(z,max_z)
                min_z = min(z,min_z)

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
            sys.stderr.write("Ignoring line (%s)\n"%c)

    # adjust camera for large/small models
    camera.x = (max_x + min_x) / 2
    camera.y = (max_y + min_y) / 2
    camera.z = (max_z + min_z) / 2


    max_dist_from_center = max([(max_x-min_x),
                                (max_y-min_y),
                                (max_z-min_z)])/2
    draw_dist_min = 0
    draw_dist_max = max_dist_from_center * 1.1
    camera.zoom /= draw_dist_max**2
    return [f for f in faces]


if len(sys.argv)>1 :
    model = load_obj(sys.argv[1],camera)
    os.system("clear")
else:
    model = model_cube

sys.stdout.write("\033[1J")     # escape sequence to clear screen
sys.stdout.write("\033[?25l")   # hide cursor
try:
    old_time = time.time()
    for t in all_numbers():
        camera.u = 2*pi * -0.001 * t
        camera.v = 2*pi * 0.01 * t
        camera.w = 2*pi * 0.0001 * t

        for _ in model:
            draw_triangle_relative(_,camera)

        next_frame = engine_step()
        new_time = time.time()
        diff_time = new_time-old_time
        old_time = new_time
        sys.stdout.write(next_frame)
        time.sleep(max(0,(1/target_fps)-diff_time))
except KeyboardInterrupt:
    pass

# sys.stdout.write("\033[1J")     # clear screen again
sys.stdout.write("\033[?25h")   # show cursor again
