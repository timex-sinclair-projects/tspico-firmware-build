#! zmakebas -a 10 -n xtest
   10 REM x: command channel test (#404). Any board, card in.
   20 BORDER 7: PAPER 7: INK 0: CLS : LET f=0
   30 PRINT "OPEN #4,""x:"" test"
  100 OPEN #4,"x:"
  110 PRINT #4;"path": INPUT #4;p$: PRINT "path: ";p$
  120 PRINT #4;"mount": INPUT #4;m$: PRINT "mount: [";m$;"]"
  130 PRINT #4;"info": INPUT #4;l$: INPUT #4;a: INPUT #4;b: INPUT #4;v$: INPUT #4;r$
  140 PRINT "card [";l$;"] ";INT (a/1048576);" of ";INT (b/1048576);" MB free"'"firmware ";v$;", ROM ";r$
  150 IF r$<>"2.4" THEN PRINT "FAIL the ROM is not 2.4": LET f=f+1
  200 PRINT #4;"dir": INPUT #4;d: INPUT #4;n: PRINT d;" folders, ";n;" files"
  210 FOR i=1 TO d+n: INPUT #4;a$
  220 IF LEN a$<>32 THEN PRINT "FAIL row ";i;" is ";LEN a$: LET f=f+1
  230 IF i<=3 OR i>d AND i<=d+3 THEN PRINT a$
  240 NEXT i
  300 PRINT #4;"dir": INPUT #4;d
  310 PRINT #4;"PATH": INPUT #4;q$
  320 IF q$=p$ THEN PRINT "ok   PATH after part of a dir"
  330 IF q$<>p$ THEN PRINT "FAIL PATH after part of a dir: ";q$: LET f=f+1
  400 LET w=8: LET t$="past the end is 8": LET r=420: ON ERR GO TO 900: INPUT #4;a$
  410 GO TO 950
  420 LET w=26: LET t$="an unknown command is Q": LET r=440: ON ERR GO TO 900: PRINT #4;"bogus"
  430 GO TO 950
  440 CLOSE #4
  450 LET w=26: LET t$="OPEN #5,""x:y"" is Q": LET r=470: ON ERR GO TO 900: OPEN #5,"x:y"
  460 GO TO 950
  470 LET w=26: LET t$="a record length is Q": LET r=490: ON ERR GO TO 900: OPEN #6,"x:","r",10
  480 GO TO 950
  490 PRINT '"Done: ";f;" failed"
  500 STOP
  900 LET e=PEEK 23739: ON ERR RESET
  910 IF e=w THEN PRINT "ok   ";t$: GO TO r
  920 PRINT "FAIL ";t$;" (";e;")": LET f=f+1: GO TO r
  950 ON ERR RESET: PRINT "FAIL ";t$;" (no error)": LET f=f+1: GO TO r
