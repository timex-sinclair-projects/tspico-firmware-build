#! zmakebas -a 10 -n cattest
   10 REM CAT #n test (#404). Any board, card in.
   20 BORDER 7: PAPER 7: INK 0: CLS : LET f=0
   30 PRINT "CAT #n test"
  100 OPEN #4,"f:cattest.txt","w"
  110 PRINT #4;"-- top --": CAT #4: PRINT #4;"-- taps --": CAT #4;"*.tap": PRINT #4;"-- end --"
  120 CLOSE #4
  200 OPEN #4,"f:cattest.txt": LET n=0: LET t=0: LET e=0
  210 ON ERR GO TO 300
  220 INPUT #4;LINE a$: LET n=n+1
  230 IF LEN a$>32 THEN PRINT "FAIL line ";n;" is ";LEN a$: LET f=f+1
  240 IF a$="-- taps --" THEN LET t=n
  250 IF a$="-- end --" THEN LET e=n
  260 IF n<=4 THEN PRINT a$
  270 GO TO 220
  300 ON ERR RESET: CLOSE #4
  310 PRINT n;" lines"
  320 IF t<3 OR e<=t+1 THEN PRINT "FAIL the listings are missing": LET f=f+1
  400 LET w=24: LET t$="CAT #9, not open, is O": LET r=420: ON ERR GO TO 900: CAT #9
  410 GO TO 950
  420 OPEN #5,"x:": LET w=26: LET t$="CAT # on x: is Q": LET r=440: ON ERR GO TO 900: CAT #5
  430 GO TO 950
  440 CLOSE #5: OPEN #5,"f:cattest.txt","r": LET w=26: LET t$="CAT # on a file open to read is Q": LET r=460: ON ERR GO TO 900: CAT #5
  450 GO TO 950
  460 CLOSE #5: OPEN #5,"f:cattest.txt","a": LET w=15: LET t$="CAT #5;""nothere"" is F": LET r=480: ON ERR GO TO 900: CAT #5;"nothere"
  470 GO TO 950
  480 CLOSE #5
  490 PRINT '"Done: ";f;" failed"
  500 STOP
  900 LET e=PEEK 23739: ON ERR RESET
  910 IF e=w THEN PRINT "ok   ";t$: GO TO r
  920 PRINT "FAIL ";t$;" (";e;")": LET f=f+1: GO TO r
  950 ON ERR RESET: PRINT "FAIL ";t$;" (no error)": LET f=f+1: GO TO r
