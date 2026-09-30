#! zmakebas -n factorial -a 10
# TS-Pico external command example: n! worked out on the Pico.
# SAVE "tpi:.fact" CODE n,0 answers OK, then the answer waits in the Pico:
# a count, the digits, and a checksum, which BASIC reads with IN 14.
# n over 32 gives Report 6 (Number too big). See src/TS/extcmd.py.
   10 REM TS-Pico EXT CMD example
   20 REM SAVE "tpi:.fact" CODE n,0
  100 INPUT "Factorial of (0-32)? ";n
  110 IF n<0 OR n>32 OR n<>INT n THEN PRINT "0 to 32, please": GO TO 100
  120 SAVE "tpi:.fact" CODE n,0
  130 LET c=IN 14: LET m$=""
  140 FOR i=1 TO c: LET m$=m$+CHR$ IN 14: NEXT i
  150 LET x=IN 14
  160 PRINT n;"! = ";m$
  170 INPUT "Another? (Y/n) ";o$
  180 IF o$<>"n" AND o$<>"N" THEN GO TO 100
