   10 REM No file mounted!
   20 PAPER 7: INK 0: BORDER 7: FLASH 0: INVERSE 0: BRIGHT 0
   30 CLS 
  100 GO SUB 500
  101 PRINT AT 3,25; INK 5;"1 of 2"
  102 PRINT AT 4,0;
  104 PRINT INK 0; PAPER 5;"LOAD to mount .tap from SD     "
  105 PRINT "LOAD ""tpi:name.tap""  "; INK 1;"by name   "
  106 PRINT "LOAD ""tpi:nnn""       "; INK 1;"by index # "
  107 PRINT "LOAD ""name"" "; INK 1;"loads from tap file"
  108 PRINT "SAVE ""name"" "; INK 1;"Save to name.tap if "'"            append mode is off."
  110 PRINT INK 0; PAPER 5; BRIGHT 0;"SAVE for commands "; INK 1;"[] = optional "
  111 PRINT "SAVE ""tpi:close"" "; INK 1;"->unmount file"
  112 PRINT "SAVE ""tpi:tapdir""  "; INK 1;"[CODE 0/1,n]"
  113 PRINT "SAVE ""tpi:ffw"" "; INK 1;"[CODE 0/1/2/3,n]"
  114 PRINT "SAVE ""tpi:rew"" "; INK 1;"[CODE 0/1/2/3,n]"
#            012345 67890123456          78901234          5 678901
  115 PRINT "SAVE ""tpi:append "; INK 1;"[on/off]"; INK 0;"""     "
  116 PRINT "SAVE ""tpi:dir""   "; INK 1;"[CODE 1/2,idx]"
  117 PRINT "SAVE ""tpi:idir"" SAVE ""tpi:info"""
  118 PRINT "SAVE ""tpi:cd "; INK 1;"[dir]"; INK 0;""""; INK 1;"[CODE 1/2,0]"
  119 PRINT "SAVE ""tpi:cd""    "; INK 1;"[CODE 0,1]    "
  130 GO SUB 300
  140 IF CODE k$=13 THEN GO TO 200
  150 GO TO 400
  200 PRINT AT 3,25; INK 5;"2 of 2"
  201 PRINT AT 4,0;
  204 PRINT INK 0; PAPER 5;"         More commands         "
  205 PRINT "SAVE ""tpi:path""    "; INK 1;"[CODE 1,0]  "
  206 PRINT "SAVE ""tpi:help "; INK 1;"[?/command]"; INK 0;"""    "
  207 PRINT "SAVE ""tpi:md <name>"""; INK 1;"[CODE 1,0] "
  208 PRINT "SAVE ""tpi:rm <name>"""; INK 1;"[CODE 255,0]"
  209 PRINT "SAVE ""tpi:log""      "; INK 1;"[CODE 0,n]  "
  210 PRINT "SAVE ""tpi:log clear"""; INK 1;"[CODE 255,0]"
  211 PRINT "SAVE ""tpi:loglevel "; INK 1;"[n]"; INK 0;"""        "
  212 PRINT "SAVE ""tpi:boot""    "; INK 1;"[CODE loc,n]"
  213 PRINT "SAVE ""tpi:dock""    "; INK 1;"[CODE loc,n]"
  214 PRINT "SAVE ""tpi:dock""CODE 0,1/2      "
  215 PRINT "SAVE ""tpi:newtap <name>"; INK 1;"[.tap]"" "
  216 PRINT "SAVE ""tpi:zx48"""; INK 1;"[CODE 0/1,0/1/2]"
  217 PRINT INK 0; PAPER 5;" TS-Pico mode "; INK 1;"<=>"; INK 0;" Hardware mode"
  218 PRINT """tpi:sdcard""  "; INK 1;"<=>"; INK 0;" ""tpi:tape""   "
  219 PRINT """tpi:picopt""  "; INK 1;"<=>"; INK 0;" ""tpi:ts2040"" "
  280 GO SUB 300
  290 IF CODE k$=13 THEN GO TO 101
  299 GO TO 400
  300 PRINT #0; INK 1;"ENTER for more        Other key SPACE for menu         to exit";
  310 LET k$=INKEY$: IF k$="" THEN GO TO 310
  320 INPUT ""
  330 IF k$=" " THEN CLS : LOAD ""
  340 RETURN 
  400 FOR a=3 TO 21
  402 PRINT AT a,0;TAB 31;" "
  404 NEXT a
  406 PRINT AT 4,0;
  410 PRINT "To load this again at any time:"''
  420 PRINT INK 1;"  SAVE ""tpi:close"""
  430 PRINT INK 1;"  LOAD """""
  440 PRINT '"Welcome to the TS Pico!"
  450 PRINT '"We hope you enjoy using it.     We have worked hard to bring    it to you and continue to work  on improving it."
  460 PRINT '"Please join the TS Pico email   list or the groups.io TS2068    list to stay up to date on      future improvements."
  470 PRINT ,,,"Enjoy!"
  490 GO TO 999 
  500 CLS 
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
