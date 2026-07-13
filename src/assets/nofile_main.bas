   10 REM No file mounted!
   20 PAPER 7: INK 0: BORDER 7: FLASH 0: INVERSE 0: BRIGHT 0
   30 CLS 
  100 GO SUB 500
  101 PRINT AT 4,0;
  110 PRINT 'TAB 8; INVERSE 1;"H"; INVERSE 0;"elp: general"
  120 PRINT 'TAB 8; INVERSE 1;"C"; INVERSE 0;"ommand help"
  130 PRINT 'TAB 8; INVERSE 1;"P"; INVERSE 0;"ick a file"
  140 PRINT 'TAB 8; INVERSE 1;"F"; INVERSE 0;"ile manager"
  150 PRINT 'TAB 8; INVERSE 1;"I"; INVERSE 0;"nfo"
  160 PRINT 'TAB 8; INVERSE 1;"Q"; INVERSE 0;"uit"
  200 LET k$=INKEY$
  210 IF k$="" THEN GO TO 200
  220 IF k$="q" THEN GO TO 400
  230 IF k$="f" THEN LOAD ""
  240 IF k$="h" THEN GO TO 1000
  250 IF k$="p" THEN GO TO 2000
  260 IF k$="c" THEN GO TO 1100
  270 IF k$="i" THEN GO TO 1200
  290 GO TO 200
  400 FOR a=4 TO 21
  402 PRINT AT a,0;TAB 31;" "
  404 NEXT a
  406 PRINT AT 4,0;
  410 PRINT "To load this again at any time:"''
  420 PRINT INK 1;"  SAVE ""tpi:close"""
  430 PRINT INK 1;"  LOAD """""
  440 PRINT '"Welcome to the TS Pico!"
  450 PRINT ,,"We hope you enjoy using it.     We have worked hard to bring    it to you and continue to work  on improving it."
  460 PRINT "Please join the TS Pico email   list or the groups.io TS2068    list to stay up to date on      future improvements."
  470 PRINT ,,,"Enjoy!"
  490 STOP 
  500 REM Draw titlebar
  510 PRINT INK 5; PAPER 0;" TIMEX "; INK 0; PAPER 7; BRIGHT 1;"               "; BRIGHT 0; INK 5; PAPER 0;" TS-Pico "
  520 PRINT 
  530 PRINT INK 7; PAPER 2;"    -- No file mounted! --     "
  540 PRINT 
  600 PLOT 64,169: DRAW 8,0: DRAW 0,2: DRAW -8,0: DRAW 0,2: DRAW 8,0
  602 PLOT 71,170: PLOT 65,172
  610 PLOT 74,169: DRAW 0,4: DRAW 1,0: DRAW 0,-4: PLOT 74,175: DRAW 1,0
  620 PLOT 78,172: DRAW 0,-3: DRAW -1,0: DRAW 0,4: DRAW 8,0: DRAW 0,-4: DRAW -1,0: DRAW 0,3
  630 PLOT 95,169: DRAW -8,0: DRAW 0,4: DRAW 8,0: PLOT 88,170: DRAW 0,3
  640 PLOT 97,169: DRAW 0,6: DRAW 1,0: DRAW 0,-6
  650 PLOT 100,173: DRAW 8,0: DRAW 0,-4: DRAW -8,0: DRAW 0,2: DRAW 6,0
  652 PLOT 101,170: PLOT 107,170: DRAW 0,3
  660 PLOT 110,169: DRAW 0,4: DRAW 1,0: DRAW 0,-4: PLOT 110,175: DRAW 1,0
  670 PLOT 114,172: DRAW 0,-3: DRAW -1,0: DRAW 0,4: DRAW 8,0
  680 PLOT 132,173: DRAW 7,0: DRAW 0,-2: DRAW -7,0: DRAW 0,-2: DRAW 7,0
  690 PLOT 141,169: DRAW 7,0: DRAW 0,4: DRAW -7,0: DRAW 0,-3
  700 PLOT 157,173: DRAW -7,0: DRAW 0,-4: DRAW 7,0: DRAW 0,2: DRAW -7,0
  710 PLOT 159,170: DRAW 0,-1: DRAW 7,0: DRAW 0,4: DRAW -7,0: DRAW 0,-2: DRAW 6,0
  799 RETURN 
  900 FOR i=1 TO 100
  910 NEXT i
  920 RETURN 
 1000 CLS 
 1010 SAVE "tpi:help"
 1020 INPUT "Press Enter:";k$
 1030 GO TO 30
 1100 CLS 
 1110 SAVE "tpi:help ?"
 1120 INPUT "Command or topic:";k$
 1130 IF k$="" THEN GO TO 30
 1140 SAVE "tpi:help "+k$
 1150 GO TO 1120
 1200 CLS 
 1210 SAVE "tpi:info"
 1220 INPUT "Press Enter:";k$
 1230 GO TO 30
 2000 CLS 
 2010 SAVE "tpi:cd"CODE 0,1
 2012 LET k$=SCREEN$ (20,0)
 2014 IF k$="(" THEN GO TO 30
 2020 GO SUB 900
 2030 SAVE "tpi:idir"
 2040 LET k$=SCREEN$ (20,0)
 2050 IF k$="(" THEN GO SUB 900: GO TO 2000
 2060 INPUT "Load (Y/n):";k$
 2070 IF k$<>"n" AND k$<>"N" THEN LOAD ""
 2080 GO TO 30
