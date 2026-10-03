#! zmakebas -n "hirescopy" -a 10
# Hardware check for the 2026-09-30 audit, §4 "hi-res COPY colours"
# (src/TS/printer.py row_colours, mode 3): the firmware colours a 512x192
# COPY from the pre-header's colour byte, ink in bits 0-2 and paper in bits
# 3-5, and only a made-up byte has ever been fed to it. This program COPYs
# the 64-column screen once with each of the 2068's eight colour choices
# (OUT 255 bits 3-5), so each /VSCREEN/SCRnnnn.BMP can be compared with
# what the TV showed. Text on the first display file shows in the even
# byte columns; the odd ones show whatever is at 6000h.
   10 REM TS-Pico hi-res COPY test
   15 SAVE "tpi:picopt": REM COPY to the TS-Pico, not a TS 2040
   20 BORDER 7: PAPER 7: INK 0: CLS
   30 FOR i=1 TO 21: PRINT "TS-Pico hi-res COPY colour test": NEXT i
   40 FOR k=0 TO 7
   50 OUT 255,6+8*k
   60 PAUSE 100
   70 COPY
   80 NEXT k
   90 OUT 255,0: CLS
  100 PRINT "Done: 8 pictures in /VSCREEN"
