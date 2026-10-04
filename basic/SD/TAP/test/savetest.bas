#! zmakebas -n "savetest" -a 10
# Hardware check for the SAVE start (PR #146): before the card check that
# starts every SAVE, the Pico now waits for the 2068 to read its status
# byte (PRELOAD_READ). Five 1000-byte CODE blocks, each different, and then
# the program itself are SAVEd; each new file is mounted and VERIFYd. Any
# failure stops with a report (R: a block didn't match; T or J: the SAVE
# didn't start). Press a key at each "Start tape" prompt. It ends with
# "6 SAVEs verified" and leaves savetst1..5.tap and savetstp.tap.
   10 REM TS-Pico SAVE + VERIFY test
   20 BORDER 7: PAPER 7: INK 0: CLS
   30 FOR i=1 TO 5
   40 PRINT AT 10,2;"SAVE + VERIFY ";i;" of 5      "
   50 FOR k=0 TO 999: POKE 40000+k,k*i+i-256*INT ((k*i+i)/256): NEXT k
   60 LET a$="savetst"+STR$ i
   70 SAVE a$ CODE 40000,1000
   80 LOAD "tpi:"+a$+".tap"
   90 VERIFY a$ CODE
  100 NEXT i
  110 SAVE "savetstp" LINE 10
  120 LOAD "tpi:savetstp.tap"
  130 VERIFY "savetstp"
  140 CLS: PRINT "6 SAVEs verified"
