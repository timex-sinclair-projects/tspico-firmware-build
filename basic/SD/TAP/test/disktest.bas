#! zmakebas -n disktest -a 10
# COPY, MOVE, FORMAT and RESTORE # on the TS-Pico (PR #349), checked by the
# 2068 itself: no keys to press. It works in /dtwork, which it makes and
# removes, and leaves you in the card's top folder.
#
# Each test: LET t (its number), d$ (what it does), x (the report it should
# end with: 0 OK, 15 F, 26 Q, as PEEK 23739 gives them), w$ (a value it
# should read back, or "" for none), n (the line after it), ON ERR GO TO
# 9000, then the command. 8000 prints the line and counts it; a trapped
# report goes to 9000, which does the same and goes on at n.
#
# At the end the results are in /dtres.txt too, one test to a line.
   10 CLEAR : LET e$="0123456789ABCDEFGHIJKLMNOPQR": LET p=0: LET f=0: LET f$="": LET r$="": LET v$="": LET w$=""
   20 CLS : PRINT INVERSE 1;" TS-Pico disk test              "
   30 PRINT "COPY, MOVE, FORMAT, RESTORE #."'"It works in /dtwork, then"'"removes it."
   40 PRINT '"No";TAB 3;"Test";TAB 24;"E G"
   50 GO SUB 7000
# ─── FORMAT makes a folder; MOVE TO goes into it ───
  100 LET t=1: LET d$="FORMAT folder": LET x=0: LET n=110: ON ERR GO TO 9000: FORMAT "/dtwork/": LET g=0: GO SUB 8000
  110 LET t=2: LET d$="FORMAT it again": LET x=15: LET n=120: ON ERR GO TO 9000: FORMAT "/dtwork/": LET g=0: GO SUB 8000
  120 LET t=3: LET d$="MOVE TO folder": LET x=0: LET n=130: ON ERR GO TO 9000: MOVE TO "/dtwork": LET g=0: GO SUB 8000
  130 LET t=4: LET d$="write a.txt": LET x=0: LET n=200: ON ERR GO TO 9000: OPEN #4,"f:a.txt","w": PRINT #4;"Eggs": PRINT #4;"Milk": CLOSE #4: LET g=0: GO SUB 8000
# ─── COPY copies, and the original stays ───
  200 LET t=5: LET d$="COPY a TO b": LET x=0: LET n=210: ON ERR GO TO 9000: COPY "a.txt" TO "b.txt": LET g=0: GO SUB 8000
  210 LET t=6: LET d$="read b": LET x=0: LET w$="Eggs": LET n=220: ON ERR GO TO 9000: LET n$="b.txt": GO SUB 8500: LET g=0: GO SUB 8000
  220 LET t=7: LET d$="a still there": LET x=0: LET w$="Eggs": LET n=230: ON ERR GO TO 9000: LET n$="a.txt": GO SUB 8500: LET g=0: GO SUB 8000
  230 LET t=8: LET d$="COPY over b": LET x=15: LET n=240: ON ERR GO TO 9000: COPY "a.txt" TO "b.txt": LET g=0: GO SUB 8000
  240 LET t=9: LET d$="COPY missing": LET x=15: LET n=250: ON ERR GO TO 9000: COPY "no.txt" TO "c.txt": LET g=0: GO SUB 8000
  250 LET t=10: LET d$="FORMAT ""sub/""": LET x=0: LET n=260: ON ERR GO TO 9000: FORMAT "sub/": LET g=0: GO SUB 8000
  260 LET t=11: LET d$="COPY a TO folder": LET x=0: LET n=270: ON ERR GO TO 9000: COPY "a.txt" TO "sub": LET g=0: GO SUB 8000
  270 LET t=12: LET d$="read sub/a": LET x=0: LET w$="Eggs": LET n=280: ON ERR GO TO 9000: LET n$="sub/a.txt": GO SUB 8500: LET g=0: GO SUB 8000
# a.txt is there already ("exists"), b.txt is copied: still 0 OK
  280 LET t=13: LET d$="COPY *.txt TO sub": LET x=0: LET n=290: ON ERR GO TO 9000: COPY "*.txt" TO "sub": LET g=0: GO SUB 8000
  290 LET t=14: LET d$="read sub/b": LET x=0: LET w$="Eggs": LET n=300: ON ERR GO TO 9000: LET n$="sub/b.txt": GO SUB 8500: LET g=0: GO SUB 8000
  300 LET t=15: LET d$="COPY a folder": LET x=26: LET n=310: ON ERR GO TO 9000: COPY "sub" TO "x.txt": LET g=0: GO SUB 8000
  310 LET t=16: LET d$="COPY *.txt TO file": LET x=26: LET n=320: ON ERR GO TO 9000: COPY "*.txt" TO "c.txt": LET g=0: GO SUB 8000
  320 LET t=17: LET d$="COPY no match": LET x=15: LET n=330: ON ERR GO TO 9000: COPY "*.zzz" TO "sub": LET g=0: GO SUB 8000
  330 LET t=18: LET d$="tpi:copy a d": LET x=0: LET n=400: ON ERR GO TO 9000: SAVE "tpi:copy a.txt d.txt": LET g=0: GO SUB 8000
# ─── MOVE renames and moves; it doesn't copy ───
  400 LET t=19: LET d$="MOVE d TO e": LET x=0: LET n=410: ON ERR GO TO 9000: MOVE "d.txt" TO "e.txt": LET g=0: GO SUB 8000
  410 LET t=20: LET d$="d is gone": LET x=15: LET n=420: ON ERR GO TO 9000: LET n$="d.txt": GO SUB 8500: LET g=0: GO SUB 8000
  420 LET t=21: LET d$="read e": LET x=0: LET w$="Eggs": LET n=430: ON ERR GO TO 9000: LET n$="e.txt": GO SUB 8500: LET g=0: GO SUB 8000
  430 LET t=22: LET d$="MOVE onto a file": LET x=15: LET n=440: ON ERR GO TO 9000: MOVE "e.txt" TO "a.txt": LET g=0: GO SUB 8000
  440 LET t=23: LET d$="MOVE e TO folder": LET x=0: LET n=450: ON ERR GO TO 9000: MOVE "e.txt" TO "sub": LET g=0: GO SUB 8000
  450 LET t=24: LET d$="read sub/e": LET x=0: LET w$="Eggs": LET n=460: ON ERR GO TO 9000: LET n$="sub/e.txt": GO SUB 8500: LET g=0: GO SUB 8000
  460 LET t=25: LET d$="MOVE sub TO sub2": LET x=0: LET n=470: ON ERR GO TO 9000: MOVE "sub" TO "sub2": LET g=0: GO SUB 8000
  470 LET t=26: LET d$="read sub2/a": LET x=0: LET w$="Eggs": LET n=480: ON ERR GO TO 9000: LET n$="sub2/a.txt": GO SUB 8500: LET g=0: GO SUB 8000
  480 LET t=27: LET d$="MOVE into itself": LET x=26: LET n=490: ON ERR GO TO 9000: MOVE "sub2" TO "sub2/x": LET g=0: GO SUB 8000
  490 LET t=28: LET d$="MOVE missing": LET x=15: LET n=500: ON ERR GO TO 9000: MOVE "no.txt" TO "f.txt": LET g=0: GO SUB 8000
# ─── MOVE TO changes folder: e.txt is only in sub2 now ───
  500 LET t=29: LET d$="MOVE TO sub2": LET x=0: LET w$="Eggs": LET n=510: ON ERR GO TO 9000: MOVE TO "sub2": LET n$="e.txt": GO SUB 8500: LET g=0: GO SUB 8000
  510 LET t=30: LET d$="MOVE current dir": LET x=26: LET n=520: ON ERR GO TO 9000: MOVE "/dtwork/sub2" TO "/dtwork/sub3": LET g=0: GO SUB 8000
  520 LET t=31: LET d$="MOVE TO ""..""": LET x=0: LET n=530: ON ERR GO TO 9000: MOVE TO "..": LET g=0: GO SUB 8000
  530 LET t=32: LET d$="no e.txt up here": LET x=15: LET n=540: ON ERR GO TO 9000: LET n$="e.txt": GO SUB 8500: LET g=0: GO SUB 8000
  540 LET t=33: LET d$="MOVE TO ""-""": LET x=0: LET w$="Eggs": LET n=550: ON ERR GO TO 9000: MOVE TO "-": LET n$="e.txt": GO SUB 8500: LET g=0: GO SUB 8000
  550 LET t=34: LET d$="MOVE TO /dtwork": LET x=0: LET n=600: ON ERR GO TO 9000: MOVE TO "/dtwork": LET g=0: GO SUB 8000
# ─── FORMAT makes TAPs (the old tpi:newtap is gone) ───
  600 LET t=35: LET d$="FORMAT ""t1.tap""": LET x=0: LET n=610: ON ERR GO TO 9000: FORMAT "t1.tap": LET g=0: GO SUB 8000
  610 LET t=36: LET d$="FORMAT ""t1"" again": LET x=15: LET n=620: ON ERR GO TO 9000: FORMAT "t1": LET g=0: GO SUB 8000
  620 LET t=37: LET d$="MOVE mounted tap": LET x=26: LET n=630: ON ERR GO TO 9000: MOVE "t1.tap" TO "t2.tap": LET g=0: GO SUB 8000
  630 LET t=38: LET d$="tpi:close": LET x=0: LET n=640: ON ERR GO TO 9000: SAVE "tpi:close": LET g=0: GO SUB 8000
  640 LET t=39: LET d$="now MOVE it": LET x=0: LET n=650: ON ERR GO TO 9000: MOVE "t1.tap" TO "t2.tap": LET g=0: GO SUB 8000
  650 LET t=40: LET d$="FORMAT ""x.bin""": LET x=26: LET n=660: ON ERR GO TO 9000: FORMAT "x.bin": LET g=0: GO SUB 8000
  660 LET t=41: LET d$="FORMAT "".tap""": LET x=15: LET n=670: ON ERR GO TO 9000: FORMAT ".tap": LET g=0: GO SUB 8000
  670 LET t=42: LET d$="FORMAT ""v1.2""": LET x=26: LET n=680: ON ERR GO TO 9000: FORMAT "v1.2": LET g=0: GO SUB 8000
  680 LET t=43: LET d$="tpi:format t3": LET x=0: LET n=690: ON ERR GO TO 9000: SAVE "tpi:format t3": SAVE "tpi:close": LET g=0: GO SUB 8000
  690 LET t=44: LET d$="t3.tap is there": LET x=0: LET n=700: ON ERR GO TO 9000: OPEN #4,"f:t3.tap","rb": CLOSE #4: LET g=0: GO SUB 8000
  700 LET t=45: LET d$="tpi:newtap gone": LET x=12: LET n=800: ON ERR GO TO 9000: SAVE "tpi:newtap t4": LET g=0: GO SUB 8000
# ─── RESTORE # goes back to the start of a file ───
  800 LET t=46: LET d$="RESTORE # reading": LET x=0: LET w$="Milk/Eggs": LET n=810: ON ERR GO TO 9000: OPEN #4,"f:a.txt": INPUT #4;a$: INPUT #4;b$: RESTORE #4: INPUT #4;c$: CLOSE #4: LET v$=b$+"/"+c$: LET g=0: GO SUB 8000
  810 LET t=47: LET d$="RESTORE # writing": LET x=0: LET n=820: ON ERR GO TO 9000: OPEN #4,"f:w.txt","w": PRINT #4;"AAAA": RESTORE #4: PRINT #4;"BB": CLOSE #4: LET g=0: GO SUB 8000
  820 LET t=48: LET d$="read w: BB first": LET x=0: LET w$="BB": LET n=830: ON ERR GO TO 9000: LET n$="w.txt": GO SUB 8500: LET g=0: GO SUB 8000
  830 LET t=49: LET d$="RESTORE #9 closed": LET x=24: LET n=840: ON ERR GO TO 9000: RESTORE #9: LET g=0: GO SUB 8000
  840 LET t=50: LET d$="RESTORE #2 screen": LET x=24: LET n=850: ON ERR GO TO 9000: RESTORE #2: LET g=0: GO SUB 8000
  850 LET t=51: LET d$="RESTORE #16": LET x=24: LET n=860: ON ERR GO TO 9000: RESTORE #16: LET g=0: GO SUB 8000
  860 LET t=52: LET d$="RESTORE 9500: DATA": LET x=0: LET w$="42": LET n=900: ON ERR GO TO 9000: RESTORE 9500: READ q: LET v$=STR$ q: LET g=0: GO SUB 8000
# ─── Tidy up, then the summary ───
  900 GO SUB 7000
  910 POKE 23692,255: PRINT '"Passed ";p-f;" of ";p
  920 IF f THEN PRINT "Failed: ";f$
  930 IF NOT f THEN PRINT "All passed."
  940 ON ERR GO TO 960: OPEN #7,"f:/dtres.txt","w": PRINT #7;r$;"Passed ";p-f;" of ";p: CLOSE #7
  950 ON ERR RESET : PRINT "Results: /dtres.txt": STOP
  960 ON ERR RESET : PRINT "Couldn't write /dtres.txt": STOP
# Tidy up: everything a run can leave in /dtwork, deepest first; any report
# (no such file) is ignored. MOVE TO "/" first: ERASE won't remove the
# folder you're in.
 7000 ON ERR GO TO 7010: SAVE "tpi:close"
 7010 ON ERR GO TO 7020: MOVE TO "/"
 7020 RESTORE 7100
 7030 READ k$: IF k$="*" THEN ON ERR RESET : RETURN
 7040 ON ERR GO TO 7030: ERASE k$: GO TO 7030
 7100 DATA "/dtwork/sub/a.txt","/dtwork/sub/b.txt","/dtwork/sub/e.txt","/dtwork/sub/x/","/dtwork/sub/"
 7110 DATA "/dtwork/sub2/a.txt","/dtwork/sub2/b.txt","/dtwork/sub2/e.txt","/dtwork/sub2/x/","/dtwork/sub2/","/dtwork/sub3/"
 7120 DATA "/dtwork/a.txt","/dtwork/b.txt","/dtwork/c.txt","/dtwork/d.txt","/dtwork/e.txt","/dtwork/f.txt","/dtwork/w.txt","/dtwork/x.txt"
 7130 DATA "/dtwork/t1.tap","/dtwork/t2.tap","/dtwork/t3.tap","/dtwork/t4.tap","/dtwork/","*"
# Print and count one test: number, what, the report it should give (E),
# the one it gave (G), ok or FAIL; for a FAIL with a value, what it read.
 8000 ON ERR RESET : LET p=p+1: LET k=(g=x) AND (w$="" OR v$=w$)
 8010 IF NOT k THEN LET f=f+1: LET f$=f$+STR$ t+" "
 8020 POKE 23692,255: PRINT t;TAB 3;d$;TAB 24;e$(x+1);" ";e$(g+1);TAB 28;("ok" AND k);("FAIL" AND NOT k)
 8030 IF NOT k AND w$<>"" THEN POKE 23692,255: PRINT TAB 3;"read """;v$;""""
 8040 LET r$=r$+STR$ t+" "+e$(x+1)+" "+e$(g+1)+" "+("ok" AND k)+("FAIL" AND NOT k)+" "+d$+(" read "+v$ AND w$<>"")+CHR$ 13
 8050 LET v$="": LET w$="": RETURN
# Read the first line of n$ into v$.
 8500 OPEN #4,"f:"+n$: INPUT #4;v$: CLOSE #4: RETURN
# A report was trapped: close stream 4 if a read left it open, count it, go on.
 9000 LET g=PEEK 23739: ON ERR RESET : CLOSE #4: GO SUB 8000: GO TO n
 9500 DATA 42
