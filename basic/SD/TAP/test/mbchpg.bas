#! zmakebas -n mbchpg -a 10
# The Megabank's r: channels, step 2 of "Channels (phase 9)" in the
# Megabank spec's Testing: a board page of the program's own mapped in each
# of chunks 4-7 (OWNc = BASE, SUBc = c, then HSR bit c) while 3000
# characters go through an r: stream. The ROM's window must put the page
# back, and the stream must be right. mbchan.bas loads it; it needs RAMTOP
# below 32768 so that chunks 4-7 hold nothing of BASIC's. Each test records
# four bytes as mbchan's do (the test number, the report, a 16-bit value: the
# bytes of the page that changed, + 1000 if the file is wrong), saved as
# mbchpres.tap.
   10 CLEAR 32767: LET r$="": LET b=PEEK 25604: LET l$="0123456789012345678"
   20 FOR c=4 TO 7: LET t=16+c: LET v=0: ON ERR GO TO 9000
   30 OPEN #4,"r:pg"+STR$ c,"w"
   40 OUT 253,c: OUT 252,b: OUT 253,8+c: OUT 252,c: OUT 244,2^c
   50 FOR i=0 TO 255: POKE 8192*c+i,i: NEXT i
   60 FOR j=1 TO 150: PRINT #4;l$: NEXT j
   70 FOR i=0 TO 255: IF PEEK (8192*c+i)<>i THEN LET v=v+1
   80 NEXT i
   90 OUT 244,0: OUT 253,c: OUT 252,0: CLOSE #4: POKE 42999,0: LOAD ("r:pg"+STR$ c)CODE 40000: IF PEEK 40019<>13 OR PEEK 42999<>13 THEN LET v=v+1000
  100 LET r$=r$+CHR$ t+CHR$ 0+CHR$ (v-256*INT (v/256))+CHR$ INT (v/256)
  110 NEXT c
  200 ON ERR RESET
  210 FOR i=1 TO LEN r$: POKE 60999+i,CODE r$(i): NEXT i
  220 SAVE "mbchpres"CODE 61000,LEN r$
  230 CLS : PRINT AT 10,0; PAPER 4; INK 0;"   MBCHAN DONE   "''"Back to the computer: hwcheck.py"'"reads the results off the card."
  240 STOP
# A report was trapped: the page unmapped, the stream closed, the report
# recorded; on with the next chunk.
 9000 ON ERR RESET : OUT 244,0: OUT 253,c: OUT 252,0: CLOSE #4: LET r$=r$+CHR$ t+CHR$ PEEK 23739+CHR$ (v-256*INT (v/256))+CHR$ INT (v/256): GO TO 110
