#! zmakebas -n mbdisk -a 10
# The Megabank RAM disk on real hardware (the Megabank spec, Testing, "On
# hardware" step 5): tools/hwcheck.py --megabank runs it. It needs ROM 2.5,
# the phase 5 firmware and a Megabank. Like hwtest.bas, each test records
# three bytes at 61000 on: the test number, the report it ended with (PEEK
# 23739: 0 OK, 15 F, 19 J, 26 Q, 27 R) and a value it read. The last SAVE
# writes them as mbdkres.tap.
#
# It FORMATs the RAM disk (twice: over files, FORMAT asks to be repeated), so
# it asks first. It leaves a default RAM disk, empty, and mbdkcopy.tap and
# mbdkimg.rdi on the card.
   10 CLEAR 32767: LET p=61000
   20 CLS : PRINT "Megabank RAM disk test"''"This FORMATs the RAM disk: every"'"file on it is lost."''"Press Y to go on, any other key"'"to stop."
   30 PAUSE 0: LET k$=INKEY$: IF k$<>"y" AND k$<>"Y" THEN STOP
   40 PRINT '"Running..."
# A 3000-byte pattern at 40000: byte i is i mod 256.
   50 FOR i=0 TO 2999: POKE 40000+i,i-256*INT (i/256): NEXT i
  100 LET t=1: LET n=110: LET v=0: ON ERR GO TO 9000: FORMAT "r:": GO SUB 8000
  110 LET t=2: LET n=120: ON ERR GO TO 9000: FORMAT "r:": GO SUB 8000
  120 LET t=3: LET n=130: ON ERR GO TO 9000: SAVE "tpi:ram": GO SUB 8000
  130 LET t=4: LET n=140: ON ERR GO TO 9000: SAVE "r:mbdk"CODE 40000,3000: GO SUB 8000
  140 LET t=5: LET n=150: ON ERR GO TO 9000: VERIFY "r:mbdk"CODE : GO SUB 8000
  150 LET t=6: LET n=160: FOR i=0 TO 9: POKE 40000+i,0: NEXT i: ON ERR GO TO 9000: LOAD "r:mbdk"CODE : LET v=PEEK 40005: GO SUB 8000
  160 LET t=7: LET n=170: LET v=0: POKE 40001,99: ON ERR GO TO 9000: VERIFY "r:mbdk"CODE : GO SUB 8000
  170 POKE 40001,1
  180 LET t=8: LET n=190: ON ERR GO TO 9000: SAVE "r:prog": GO SUB 8000
# Not VERIFY "r:prog": the variables have changed since (t, n), so it would
# give R whatever the disk did.
  190 LET t=9: LET n=200: ON ERR GO TO 9000: CAT "r:": GO SUB 8000
  200 LET t=10: LET n=210: ON ERR GO TO 9000: MOVE "r:mbdk" TO "r:mbdk2": GO SUB 8000
  210 LET t=11: LET n=220: ON ERR GO TO 9000: LOAD "r:mbdk"CODE : GO SUB 8000
  220 LET t=12: LET n=230: ON ERR GO TO 9000: COPY "r:mbdk2" TO "mbdkcopy": GO SUB 8000
  230 LET t=13: LET n=240: ON ERR GO TO 9000: COPY "mbdkcopy" TO "r:back": GO SUB 8000
  240 LET t=14: LET n=250: POKE 50005,0: ON ERR GO TO 9000: LOAD "r:back"CODE 50000: LET v=PEEK 50005: GO SUB 8000
  250 LET t=15: LET n=260: LET v=0: ON ERR GO TO 9000: COPY "r:back" TO "r:back2": GO SUB 8000
  260 LET t=16: LET n=270: ON ERR GO TO 9000: ERASE "r:back2": GO SUB 8000
# A 64K disk: seven 8K pages of data and the directory's page.
  270 LET t=17: LET n=280: ON ERR GO TO 9000: FORMAT "r:64": GO SUB 8000
  280 LET t=18: LET n=290: ON ERR GO TO 9000: FORMAT "r:64": GO SUB 8000
  290 LET t=19: LET n=300: ON ERR GO TO 9000: SAVE "r:big"CODE 16384,49152: GO SUB 8000
  300 LET t=20: LET n=310: ON ERR GO TO 9000: SAVE "r:big2"CODE 16384,49152: GO SUB 8000
  310 LET t=21: LET n=320: ON ERR GO TO 9000: SAVE "r:small"CODE 40000,3000: GO SUB 8000
  320 LET t=22: LET n=330: ON ERR GO TO 9000: SAVE "tpi:ram backup mbdkimg": GO SUB 8000
  330 LET t=23: LET n=340: ON ERR GO TO 9000: ERASE "r:small": GO SUB 8000
# Over files, a restore asks to be repeated too.
  340 LET t=24: LET n=350: ON ERR GO TO 9000: SAVE "tpi:ram restore mbdkimg": GO SUB 8000
  350 LET t=25: LET n=360: ON ERR GO TO 9000: SAVE "tpi:ram restore mbdkimg": GO SUB 8000
  360 LET t=26: LET n=370: POKE 50005,0: ON ERR GO TO 9000: LOAD "r:small"CODE 50000: LET v=PEEK 50005: GO SUB 8000
  370 LET t=27: LET n=380: LET v=0: ON ERR GO TO 9000: FORMAT "r:": GO SUB 8000
  380 LET t=28: LET n=400: ON ERR GO TO 9000: FORMAT "r:": GO SUB 8000
  400 ON ERR RESET
  410 SAVE "mbdkres"CODE 61000,p-61000
  420 CLS : PRINT AT 10,0; PAPER 4; INK 0;"   MBDISK DONE: ";(p-61000)/3;" tests   "''"Back to the computer: hwcheck.py"'"reads the results off the card."
  430 STOP
# Record a test: number, report, value.
 8000 POKE p,t: POKE p+1,0: POKE p+2,v-256*INT (v/256): LET p=p+3: RETURN
# A report was trapped: record it, go on with the next test.
 9000 POKE p,t: POKE p+1,PEEK 23739: POKE p+2,v-256*INT (v/256): LET p=p+3: GO TO n
