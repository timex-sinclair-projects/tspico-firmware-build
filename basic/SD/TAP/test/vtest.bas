#! zmakebas -a 10 -n vtest
   10 REM v: speech channel test (#375). v3 card only.
   20 BORDER 7: PAPER 7: INK 0: CLS : LET f=0
   30 PRINT "OPEN #4,""v:"" speech test"'"Listen to each one, then press"'"a key for the next."'
  100 PRINT "1. A line, said as it prints"
  110 OPEN #4,"v:"
  120 PRINT #4;"HELLO, I AM YOUR TIMEX SINCLAIR 2068."
  130 FOR i=1 TO 25: PRINT AT 20,0;"The 2068 keeps going: ";i;" ": PAUSE 4: NEXT i
  140 PRINT AT 20,0;"                               ": PAUSE 0
  200 PRINT "2. Over 64 characters, as one"
  210 PRINT #4;"THIS LINE IS LONGER THAN SIXTY FOUR CHARACTERS, SO IT GOES OVER IN TWO PIECES, BUT IT IS SAID AS ONE."
  220 PAUSE 0
  300 PRINT "3. A number: 2068"
  310 LET s=2068: PRINT #4;"YOUR SCORE IS ";s;" POINTS."
  320 PAUSE 0
  400 PRINT "4. Allophones: HELLO THERE"
  410 PRINT #4;"[HH1 EH LL OW PA4] THERE."
  420 PAUSE 0
  500 PRINT "5. A line in two PRINTs"
  510 PRINT #4;"THIS IS SAID";: PRINT "   (silent until a key)": PAUSE 0
  520 PRINT #4;" WHEN THE LINE ENDS."
  530 PAUSE 0
  600 PRINT "6. Said at CLOSE #4: GOODBYE"
  610 PRINT #4;"GOODBYE.";: PRINT "   (silent until a key)": PAUSE 0
  620 CLOSE #4
  630 PAUSE 0
  700 PRINT '"7. Errors (nothing to hear)"
  710 OPEN #4,"v:"
  720 LET w=26: LET t$="INPUT #4 is Q": LET r=740: ON ERR GO TO 900: INPUT #4;a$
  730 GO TO 950
  740 CLOSE #4
  750 LET w=26: LET t$="OPEN #5,""v:x"" is Q": LET r=770: ON ERR GO TO 900: OPEN #5,"v:x"
  760 GO TO 950
  770 LET w=24: LET t$="#5 is not open: O": LET r=790: ON ERR GO TO 900: PRINT #5;"X"
  780 GO TO 950
  790 LET w=26: LET t$="a record length is Q": LET r=810: ON ERR GO TO 900: OPEN #6,"v:","w",10
  800 GO TO 950
  810 PRINT '"Done: ";f;" failed"
  820 STOP
  900 LET e=PEEK 23739: ON ERR RESET
  910 IF e=w THEN PRINT "ok   ";t$: GO TO r
  920 PRINT "FAIL ";t$;" (";e;")": LET f=f+1: GO TO r
  950 ON ERR RESET: PRINT "FAIL ";t$;" (no error)": LET f=f+1: GO TO r
