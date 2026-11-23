TS-Pico Native Files       TOPIC
--------------------------------
You can directly access files on
the SD card with an "f:" prefix
to the filename. The name after
f: can include a folder (total
of 64 characters).

LOAD/SAVE/VERIFY/MERGE:
-----------------------
You can work with one "file"
that you would normally save in
a .tap file, but you don't have
to mount it first.
  LOAD "f:myfile.bas"
This only works for files that
the 2068 normally saved in a
.tap file, which includes a
program, SCREEN$, CODE, numeric
array, and character array.

For example, you could have some
utility subroutines in separate
files and MERGE them into what
you are working on without
mounting them:
  MERGE "f:math.bas"

The file is stored with a 128
byte +3DOS header (Spectrum +3).
The exception is a SCREEN$ is
stored as the plain 6912 bytes
of the screen, so you can open
it in picture tools that
understand Spectrum screen (SCR)
files. Also, a raw file of bytes
on the SD card without a +3DOS
header can be loaded as CODE,
but you have to provide the
memory address. 

OPEN#/CLOSE# (Stream access):
-----------------------------
You can open a stream on any
file on the SD card with f: to
red and write to it with INPUT
and PRINT (and some others).
There are read, write and update
file modes as well as "binary"
versions that don't translate
control characters. See OPEN# or
Streams for more.

See also: LOAD, SAVE, VERIFY,
MERGE, OPEN#, CLOSE#, streams
