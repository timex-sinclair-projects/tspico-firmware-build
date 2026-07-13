   10 REM No file mounted!
   20 PAPER 7: INK 0: BORDER 7: FLASH 0: INVERSE 0
  100 GO SUB 500
  103 PRINT INK 7; PAPER 0; BRIGHT 1;"LOAD ""tpi:..."" to mount from SD"
  104 PRINT "LOAD ""tpi:name.tap""  by name"
  105 PRINT "LOAD ""tpi:&nn""       by index #"
  106 PRINT "LOAD ""...""  loads from tap file"
  109 PRINT INK 7; PAPER 0; BRIGHT 1;"SAVE ""tpi:..."" for commands    "' INK 6;"SAVE ""tpi:command"": [ ]->option"
  111 PRINT "SAVE ""tpi:close"" ->unmount file"
  112 PRINT "SAVE ""tpi:tapdir""  [CODE 0/1,n]"
  113 PRINT "SAVE ""tpi:ffw""     [CODE n,0/1]"
  114 PRINT "SAVE ""tpi:rew""     [CODE n,0/1]"
  115 PRINT "SAVE ""tpi:append""  [CODE 0/1,1]"
  116 PRINT "SAVE ""tpi:dir""     [CODE idx,1]"
  117 PRINT "SAVE ""tpi:cd <name>""[CODE 1,0]"
  118 PRINT "SAVE ""tpi:path""     [CODE 1,0]"
  119 PRINT "SAVE ""tpi:gethelp"""
  120 PRINT "SAVE ""tpi:gethelp <command>"""
  130 GO SUB 300
  140 IF CODE k$=13 THEN GO TO 200
  150 GO TO 400
  200 GO SUB 500
  203 PRINT INK 7; PAPER 0; BRIGHT 1;"      More SAVE commands:      "
  204 PRINT "SAVE ""tpi:md <name>"" [CODE 1,0]"
  205 PRINT "SAVE ""tpi:rm <name>"" [CODE 1,0]"
  206 PRINT "SAVE ""tpi:getinfo"""
  207 PRINT "SAVE ""tpi:getlog""  [CODE n,0]"
  208 PRINT "SAVE ""tpi:getlog""  [CODE 0,255]"
  209 PRINT "SAVE ""tpi:memboot"" [CODE loc,n]"
  210 PRINT "SAVE ""tpi:memdock"" [CODE loc,n]"
  211 PRINT "SAVE ""tpi:blkrcv""  [CODE n,m]"
  212 PRINT "SAVE ""tpi:zx48""    [CODE 1,0]"
  213 PRINT INVERSE 1;" TS-Pico mode <=> Hardware mode"
  214 PRINT """tpi:sdcard""  <=> ""tpi:tape"""
  215 PRINT """tpi:picopt""  <=> ""tpi:ts2040"""
  216 PRINT INVERSE 1;" Saving programs               "
  217 PRINT "SAVE ""name""   Saves to name.tap if append mode is off."
  280 GO SUB 300
  290 IF CODE k$=13 THEN GO TO 100
  299 GO TO 400
  300 PRINT #0;"Press Enter for more, SPACE for file menu, or other key to exit";
  310 LET k$=INKEY$: IF k$="" THEN GO TO 310
  320 INPUT ""
  330 IF k$=" " THEN CLS : STOP : LOAD ""
  340 RETURN 
  400 GO SUB 500
  410 PRINT "To load this again at any time:"''
  420 PRINT INK 1;"  SAVE ""tpi:close"""''
  430 PRINT INK 1;"  LOAD """""
  490 STOP 
  500 CLS 
  510 PRINT INK 5; PAPER 0;" TIMEX "; INK 0; PAPER 7; BRIGHT 1;" sinclair 2068 "; BRIGHT 0; INK 5; PAPER 0;" TS-Pico "
  520 PRINT 
  530 PRINT INK 7; PAPER 2;"    -- No file mounted! --     "
  540 PRINT 
  590 RETURN 
