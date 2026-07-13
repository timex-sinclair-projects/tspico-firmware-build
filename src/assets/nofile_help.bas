   10 REM No file mounted!
   20 PAPER 7: INK 0: BORDER 7: FLASH 0: INVERSE 0
   30 CLS 
  100 GO SUB 500
  101 PRINT AT 4,0;
  104 PRINT INK 0; PAPER 5;"LOAD ""tpi:..."" to mount from SD"
  105 PRINT "LOAD ""tpi:name.tap""  "; INK 1;"by name   "
  106 PRINT "LOAD ""tpi:&nn""       "; INK 1;"by index # "
  107 PRINT "LOAD ""name"" "; INK 1;"loads from tap file"
  108 PRINT INK 0; PAPER 5; BRIGHT 0;"SAVE ""tpi:..."" for commands    "
  109 PRINT INK 1; PAPER 5;"                 [ ] = optional"
  110 PRINT "SAVE ""tpi:close"" "; INK 1;"->unmount file"
  111 PRINT "SAVE ""tpi:tapdir""  "; INK 1;"[CODE 0/1,n]"
  112 PRINT "SAVE ""tpi:ffw"" "; INK 1;"[CODE 0/1/2/3,n]"
  113 PRINT "SAVE ""tpi:rew"" "; INK 1;"[CODE 0/1/2/3,n]"
  114 PRINT "SAVE ""tpi:append""  "; INK 1;"[CODE 1,0/1]"
  115 PRINT "SAVE ""tpi:dir""     "; INK 1;"[CODE 1,idx]"
  116 PRINT "SAVE ""tpi:cd <dir>"""; INK 1;"[CODE 1/2,0]"
  117 PRINT "SAVE ""tpi:path""    "; INK 1;"[CODE 1,0]  "
  118 PRINT "SAVE ""tpi:gethelp "; INK 1;"[command]""   "
  119 PRINT "SAVE ""tpi:getinfo""             "
  130 GO SUB 300
  140 IF CODE k$=13 THEN GO TO 200
  150 GO TO 400
  200 PRINT AT 4,0;
  204 PRINT INK 0; PAPER 5;"         More commands         "
  205 PRINT "SAVE ""tpi:md <name>"""; INK 1;"[CODE 1,0] "
  206 PRINT "SAVE ""tpi:rm <name>"""; INK 1;"[CODE 255,0]"
  207 PRINT "SAVE ""tpi:getlog""   "; INK 1;"[CODE 0,n]  "
  208 PRINT "SAVE ""tpi:getlog""CODE 255,0    "
  209 PRINT "SAVE ""tpi:loglevel"""; INK 1;"[CODE 1,n]  "
  210 PRINT "SAVE ""tpi:memboot"" "; INK 1;"[CODE loc,n]"
  211 PRINT "SAVE ""tpi:memdock"" "; INK 1;"[CODE loc,n]"
  212 PRINT "SAVE ""tpi:blkrcv""  "; INK 1;"[CODE n,m]  "
  213 PRINT "SAVE ""tpi:zx48""  "; INK 1;"[CODE 0/1,0/1]"
  214 PRINT INK 0; PAPER 5;" TS-Pico mode "; INK 1;"<=>"; INK 0;" Hardware mode"
  215 PRINT """tpi:sdcard""  "; INK 1;"<=>"; INK 0;" ""tpi:tape""   "
  216 PRINT """tpi:picopt""  "; INK 1;"<=>"; INK 0;" ""tpi:ts2040"" "
  217 PRINT INK 0; PAPER 5;"SAVE ""name"" "; INK 1;"Save to name.tap if"'"            append mode is off."
  219 PRINT TAB 31;
  280 GO SUB 300
  290 IF CODE k$=13 THEN GO TO 101
  299 GO TO 400
  300 PRINT #0; INK 1;"ENTER for more        Other key SPACE for menu         to exit";
  310 LET k$=INKEY$: IF k$="" THEN GO TO 310
  320 INPUT ""
  330 IF k$=" " THEN CLS : LOAD ""
  340 RETURN 
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
  500 CLS 
  510 PRINT INK 5; PAPER 0;" TIMEX "; INK 0; PAPER 7; BRIGHT 1;"             "; BRIGHT 0; INK 5; PAPER 0;"  TS-Pico  "
  520 PRINT 
  530 PRINT INK 7; PAPER 2;"    -- No file mounted! --     "
  540 PRINT 
  600 PLOT 64,169: DRAW 7,0: DRAW 0,2: DRAW -7,0: DRAW 0,2: DRAW 7,0
  610 PLOT 73,169: DRAW 0,4: PLOT 73,175
  620 PLOT 75,169: DRAW 0,4: DRAW 7,0: DRAW 0,-4
  630 PLOT 91,169: DRAW -7,0: DRAW 0,4: DRAW 7,0
  640 PLOT 93,169: DRAW 0,6
  650 PLOT 95,173: DRAW 7,0: DRAW 0,-4: DRAW -7,0: DRAW 0,2: DRAW 6,0
  660 PLOT 104,169: DRAW 0,4: PLOT 104,175
  670 PLOT 106,169: DRAW 0,4: DRAW 7,0
  680 PLOT 122,173: DRAW 6,0: DRAW 0,-2: DRAW -6,0: DRAW 0,-2: DRAW 6,0
  690 PLOT 130,169: DRAW 6,0: DRAW 0,4: DRAW -6,0: DRAW 0,-3
  700 PLOT 144,173: DRAW -6,0: DRAW 0,-4: DRAW 6,0: DRAW 0,2: DRAW -6,0
  710 PLOT 146,170: DRAW 0,-1: DRAW 6,0: DRAW 0,4: DRAW -6,0: DRAW 0,-2: DRAW 5,0
  799 RETURN 
