# rice3d

Render 3d models in realtime in your terminal using just text.

![Screenshot](256color.png)

![Video of realtime rendering](new_example.webm)

# Basic Usage

```
./rice3d.py [FILE]
```

Where FILE points to a .obj file. There are example models in the "models" folder.

# Advanced Usage

```
usage: rice3d.py [-h] [-F FRAMERATE] [-f FRAMECOUNT] [-c COLUMNS] [-l LINES]
                 [-s] [-W] [-a ASCPECTRATIO] [-A] [-d] [-t TIME] [-u CAMERAU]
                 [-v CAMERAV] [-w CAMERAW] [-g GRADIENT]
                 FILE

positional arguments:
  FILE                  .obj file to be rendered

optional arguments:
  -h, --help            show this help message and exit
  -F FRAMERATE, --framerate FRAMERATE
                        Maximum framerate when drawing multiple frames
  -f FRAMECOUNT, --framecount FRAMECOUNT
                        Number of frames to render (ignore in combination with
                        --singleframe)
  -c COLUMNS, --columns COLUMNS
                        Number of columns (widht) per frame
  -l LINES, --lines LINES
                        Lines of output (height) per frame
  -s, --script          Output as a BASH shell script, to be run later
  -W, --wireframe       Draw model as wireframe instead of solid faces
  -a ASCPECTRATIO, --ascpectratio ASCPECTRATIO
                        Ratio between height and length of a character "pixel"
  -A, --autoscale       Automatically scale lighting to model depth
  -d, --dithering       Dither colors rather than rounding them down
  -t TIME, --time TIME  Time to start animation at
  -u CAMERAU, --camerau CAMERAU
                        Camera angle (u)
  -v CAMERAV, --camerav CAMERAV
                        Camera angle (v)
  -w CAMERAW, --cameraw CAMERAW
                        Camera angle (w)
  -g GRADIENT, --gradient GRADIENT
                        string used to generate a character gradient
```


# Requirments

- pypy3 (can be replace by python3 with a minor performance cost)
