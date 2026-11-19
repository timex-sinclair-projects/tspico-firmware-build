#! zmakebas -n mbchan -a 10
# The Megabank's r: channels on real hardware (the Megabank spec, Testing,
# "Channels (phase 9)" steps 1-4, 7 and 8; 5 and 6 need hands and are
# tools/hwcheck.py --megabank-channels'). It needs ROM 2.5 with phase 9, the
# phase 9 firmware, a Megabank and the SD card. Each test records four bytes:
# the test number, the report it ended with (PEEK 23739: 0 OK, 8 End of
# file, 15 F, 26 Q) and a 16-bit value it read, low byte first; they are
# saved at the end as mbchres.tap. Then it loads mbchpg.bas, tests 20-23,
# which needs RAMTOP below 32768 and so can't share this program's memory.
#
# It FORMATs the RAM disk, so it asks first. It leaves its files on the RAM
# disk and mbchf.txt on the card.
   10 CLEAR 39999: LET r$=""
   20 CLS : PRINT "Megabank r: channel test"''"This FORMATs the RAM disk: every"'"file on it is lost."''"Press Y to go on, any other key"'"to stop."
   30 PAUSE 0: LET k$=INKEY$: IF k$<>"y" AND k$<>"Y" THEN STOP
   40 PRINT '"Running..."
   50 LET l$="0123456789012345678"
  100 LET t=1: LET n=110: LET v=0: ON ERR GO TO 9000: FORMAT "r:": GO SUB 8000
  110 LET t=2: LET n=120: ON ERR GO TO 9000: FORMAT "r:": GO SUB 8000
# Text: TAB n on a stream file is byte n; a CR ends each line.
  120 LET t=3: LET n=130: ON ERR GO TO 9000: OPEN #4,"r:t","w": PRINT #4;"hello";TAB 10;"x": PRINT #4;"line two": CLOSE #4: GO SUB 8000
  130 LET t=4: LET n=140: ON ERR GO TO 9000: OPEN #4,"r:t": INPUT #4;a$: INPUT #4;b$: LET v=(a$="hello    x")+2*(b$="line two"): GO SUB 8000
  140 LET t=5: LET n=150: LET v=0: ON ERR GO TO 9000: INPUT #4;c$: GO SUB 8000
  150 CLOSE #4
  160 LET t=6: LET n=170: ON ERR GO TO 9000: OPEN #4,"r:t","a": PRINT #4;"more": CLOSE #4: POKE 40020,0: LOAD "r:t"CODE 40000: LET v=PEEK 40020: GO SUB 8000
# Records of 8: TAB n is record n; TAB 0 then a read is the count.
  170 LET t=7: LET n=180: LET v=0: ON ERR GO TO 9000: OPEN #5,"r:rec","u",8: PRINT #5;TAB 3;"three": PRINT #5;TAB 1;"one": CLOSE #5: GO SUB 8000
  180 LET t=8: LET n=190: ON ERR GO TO 9000: OPEN #5,"r:rec","r",8: INPUT #5;TAB 3;a$: INPUT #5;TAB 0;m: CLOSE #5: LET v=(a$( TO 5)="three")+2*(m=3): GO SUB 8000
  190 LET t=9: LET n=200: LET v=0: ON ERR GO TO 9000: OPEN #5,"r:rec","u",8: PRINT #5;TAB 2;"123456789": GO SUB 8000
  200 CLOSE #5
  210 LET t=10: LET n=220: ON ERR GO TO 9000: OPEN #5,"r:rec","u",8: PRINT #5;TAB 0;"x": GO SUB 8000
  220 CLOSE #5
  230 LET t=11: LET n=240: ON ERR GO TO 9000: OPEN #4,"r:wo","w": INPUT #4;a$: GO SUB 8000
  240 CLOSE #4
# Binary keeps control bytes; text drops 16 and its parameter.
  250 LET t=12: LET n=260: ON ERR GO TO 9000: OPEN #4,"r:bin","wb": PRINT #4;CHR$ 16;CHR$ 2;"A": CLOSE #4: OPEN #4,"r:bin","rb": LET v=CODE INKEY$ #4: CLOSE #4: GO SUB 8000
  260 LET t=13: LET n=270: LET v=0: ON ERR GO TO 9000: OPEN #4,"r:txt","w": PRINT #4;CHR$ 16;CHR$ 2;"A": CLOSE #4: OPEN #4,"r:txt": LET v=CODE INKEY$ #4: CLOSE #4: GO SUB 8000
# The listing: t, rec, wo, bin, txt.
  270 LET t=14: LET n=280: LET v=0: ON ERR GO TO 9000: OPEN #6,"r:": INPUT #6;TAB 0;m: CLOSE #6: LET v=m: GO SUB 8000
  280 LET t=15: LET n=290: LET v=0: ON ERR GO TO 9000: OPEN #6,"r:b*": INPUT #6;a$: CLOSE #6: LET v=(a$="bin"): GO SUB 8000
  290 LET t=16: LET n=300: LET v=0: ON ERR GO TO 9000: OPEN #4,"r:t","a": ERASE "r:t": GO SUB 8000
  300 CLOSE #4
# Growth: r:after lands just past r:g's extent, so r:g must move to grow.
  310 LET t=17: LET n=320: ON ERR GO TO 9000: OPEN #4,"r:g","w": FOR j=1 TO 50: PRINT #4;l$: NEXT j: OPEN #5,"r:after","w": PRINT #5;"after file": CLOSE #5: FOR j=51 TO 1000: PRINT #4;l$: NEXT j: CLOSE #4: GO SUB 8000
  320 LET t=18: LET n=330: LET v=0: ON ERR GO TO 9000: LOAD "r:g"CODE 40000: LET v=(PEEK 40019=13)+2*(PEEK 59999=13)+4*(PEEK 59980=48): GO SUB 8000
  330 LET t=19: LET n=400: LET v=0: ON ERR GO TO 9000: OPEN #5,"r:after": INPUT #5;a$: CLOSE #5: LET v=(a$="after file"): GO SUB 8000
# 32 errors in a row inside the channel (End of file), then it still works.
  500 LET t=24: LET n=560: LET e=0: ON ERR GO TO 9000: OPEN #4,"r:t"
  510 ON ERR GO TO 530: INPUT #4;a$: GO TO 510
  530 LET e=e+1: IF e<32 THEN GO TO 510
  540 ON ERR GO TO 9000: LET v=e: CLOSE #4: OPEN #4,"r:t": INPUT #4;a$: CLOSE #4: LET v=e+100*(a$="hello    x"): GO SUB 8000
  560 CLOSE #4
# f: and r: open together, closed in all six orders.
  600 RESTORE 690: FOR o=1 TO 6: READ o$: LET t=24+o: LET n=680: LET v=0: ON ERR GO TO 9000
  610 OPEN #4,"r:a","w": OPEN #5,"f:mbchf.txt","w": OPEN #6,"r:b","w"
  620 PRINT #4;"a";o: PRINT #5;"f";o: PRINT #6;"b";o
# Literal CLOSEs: CLOSE # with an expression is C in a program (ROM 2.4 too).
  630 FOR k=1 TO 3: LET d=VAL o$(k): IF d=4 THEN CLOSE #4
  632 IF d=5 THEN CLOSE #5
  634 IF d=6 THEN CLOSE #6
  636 NEXT k
  640 OPEN #4,"r:a": INPUT #4;a$: CLOSE #4: OPEN #5,"f:mbchf.txt": INPUT #5;f$: CLOSE #5: OPEN #6,"r:b": INPUT #6;c$: CLOSE #6
  650 LET v=(a$="a"+STR$ o)+2*(f$="f"+STR$ o)+4*(c$="b"+STR$ o): GO SUB 8000: GO TO 685
  680 CLOSE #4: CLOSE #5: CLOSE #6
  685 NEXT o
  690 DATA "456","465","546","564","645","654"
# LLIST into an r: stream; CLOSE #3 must give stream 3 back to P.
  700 LET t=31: LET n=710: LET v=0: ON ERR GO TO 9000: OPEN #3,"r:list","w": LLIST : CLOSE #3: LET v=PEEK 23580+256*PEEK 23581: GO SUB 8000
  710 LET t=32: LET n=800: LET v=0: ON ERR GO TO 9000: LOAD "r:list"CODE 40000: LET v=PEEK 40002: GO SUB 8000
# The cost: 2000 characters, and the same loop without them. FRAMES is
# only a hint (the r: code runs with interrupts off, so it loses frames):
# hwcheck.py times each loop from its stream's tpi:rchopen to its
# tpi:rchclose in the firmware's telemetry.
  800 LET t=33: LET n=820: ON ERR GO TO 9000: OPEN #4,"r:speed","w": LET f=PEEK 23672+256*PEEK 23673: FOR j=1 TO 100: PRINT #4;l$: NEXT j: LET v=PEEK 23672+256*PEEK 23673-f: CLOSE #4: LET v=v+65536*(v<0): GO SUB 8000
  820 LET t=34: LET n=900: ON ERR GO TO 9000: OPEN #6,"r:speed2","w": LET f=PEEK 23672+256*PEEK 23673: FOR j=1 TO 100: LET x$=l$: NEXT j: LET v=PEEK 23672+256*PEEK 23673-f: CLOSE #6: LET v=v+65536*(v<0): GO SUB 8000
  900 ON ERR RESET
  910 FOR i=1 TO LEN r$: POKE 60999+i,CODE r$(i): NEXT i
  920 SAVE "mbchres"CODE 61000,LEN r$
  930 CLS : PRINT "mbchan: ";LEN r$/4;" tests saved."'"Loading mbchpg, the page tests..."
  940 LOAD "tpi:mbchpg.tap": LOAD ""
# Record a test: number, report 0, value (two bytes).
 8000 LET r$=r$+CHR$ t+CHR$ 0+CHR$ (v-256*INT (v/256))+CHR$ INT (v/256): RETURN
# A report was trapped: record it, go on at line n. ON ERR goes off first,
# so an error in here stops the program rather than looping.
 9000 ON ERR RESET : LET r$=r$+CHR$ t+CHR$ PEEK 23739+CHR$ (v-256*INT (v/256))+CHR$ INT (v/256): GO TO n
