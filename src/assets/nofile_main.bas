# TS-Pico "No File!" program for nofile.tap
# 31 Dec 2025 TS-Pico Team
# The nofile.tap file is mounted if the user types LOAD "" with no .tap file
# mounted, and this is the first program in it. It presents TS-Pico branding
# with a notice that no file is mounted along with a simple menu.
#
# NOTE: We still have the problem using tpi command in BASIC of needing to wait
# until the pico has finished the previous command, or you will get an error.
# You can insert a long pause, ask for user input, or make an error handler to 
# keep trying tpi:nop until there is no error or a long time has passed, then 
# move on to the desired tpi command.
#
    1 REM \{0xF3}\{0xF5}\{0xAF}\{0xDB}\{0xFF}\{0xF6}\{0x80}\{0xD3}\{0xFF}\{0xF5}\
\{0x3E}\{0x03}\{0xD3}\{0xF4}\{0x3A}\{0x53}\{0x18}\{0x32}\{0x40}\{0x9C}\
\{0x3A}\{0xFD}\{0x1A}\{0x32}\{0x41}\{0x9C}\{0x3A}\{0x58}\{0x1C}\{0x32}\
\{0x42}\{0x9C}\{0xF1}\{0xD3}\{0xFF}\{0xAF}\{0xD3}\{0xF4}\{0xF1}\{0xFB}\
\{0xC9}\{0x00}\{0x00}\{0x00}\{0x00}
    2 REM No file mounted!
   20 PAPER 7: INK 0: BORDER 7: FLASH 0: INVERSE 0: BRIGHT 0
   30 CLS 
  100 GO SUB 500
  101 PRINT AT 4,0;
  110 PRINT 'TAB 8; INVERSE 1;"H"; INVERSE 0;"elp: general"
  120 PRINT 'TAB 8; INVERSE 1;"C"; INVERSE 0;"ommand help"
  130 PRINT 'TAB 8; INVERSE 1;"P"; INVERSE 0;"ick a file"
  140 PRINT 'TAB 8; INVERSE 1;"F"; INVERSE 0;"ile manager"
  145 PRINT 'TAB 8; INVERSE 1;"R"; INVERSE 0;"OM version"
  150 PRINT 'TAB 8; INVERSE 1;"I"; INVERSE 0;"nfo"
  155 PRINT 'TAB 8; "Pico "; INVERSE 1;"V"; INVERSE 0;"ideo ..."
  160 PRINT 'TAB 8; INVERSE 1;"Q"; INVERSE 0;"uit"
  200 LET k$=INKEY$
  210 IF k$="" THEN GO TO 200
  220 IF k$="q" THEN GO TO 400
  230 IF k$="f" THEN LOAD ""
  240 IF k$="h" THEN GO TO 1000
  250 IF k$="p" THEN GO TO 2000
  260 IF k$="c" THEN GO TO 1100
  270 IF k$="i" THEN GO TO 1200
  280 IF k$="r" THEN GO SUB 2100: GO TO 20
  285 IF k$="v" THEN GO TO 1300
  290 GO TO 200
#
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
#
  900 FOR i=1 TO 100
  910 NEXT i
  920 RETURN 
#
# Main menu
#
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
 1300 CLS
 1310 GO SUB 500
 1312 PRINT AT 4,0;
 1320 PRINT ' INVERSE 1;"0"; INVERSE 0;" "; BRIGHT 1; INVERSE 1; "Bright"; BRIGHT 0;" black off"
 1330 PRINT ' INVERSE 1;"1"; INVERSE 0;" "; BRIGHT 1; INVERSE 1; "Bright"; BRIGHT 0;" black on"
 1340 PRINT ' INVERSE 1;"X"; INVERSE 0;" back"
 1350 LET k$=INKEY$
 1360 IF k$="0" THEN OUT 48955,66: OUT 65339,1: GO TO 1350
 1370 IF k$="1" THEN OUT 48955,66: OUT 65339,0: GO TO 1350
 1380 IF k$="x" THEN GO TO 30
 1390 GO TO 1350
 2000 CLS 
 2010 SAVE "tpi:cd"CODE 0,1
# 2012 LET k$=SCREEN$ (20,0)
# 2014 IF k$="(" THEN GO TO 30
 2012 LET k$=SCREEN$ (21,30)
 2014 IF k$="N" THEN GO TO 30
 2016 GO SUB 900
 2025 CLS 
 2030 SAVE "tpi:idir"
# 2040 LET k$=SCREEN$ (20,0)
# 2050 IF k$="(" THEN GO SUB 900: GO TO 2000
 2040 LET k$=SCREEN$ (21,30)
 2050 IF k$="N" THEN GO SUB 900: GO TO 2000
## 2052 IF k$<>"M" THEN INPUT "Press Enter:";k$: GO TO 2000
 2060 INPUT "Load (Y/n):";k$
 2070 IF k$<>"n" AND k$<>"N" THEN LOAD ""
 2080 GO TO 30
 2100 CLS 
 2110 LET v=PEEK 101
 2115 IF v=255 THEN GO TO 3000
 2120 LET m=INT (v/16)
 2130 LET n=v-16*m
 2140 PRINT "You appear to have ROM v";m;".";n
 2150 INPUT "Press Enter to continue:.... ";a$
 2160 RETURN
#
 3000 REM Determine ROM version
 3020 LET PROG=PEEK 23635+256*PEEK 23636
 3030 LET MC=PROG+5
 3040 RANDOMIZE USR MC
 3045 LET v$="Unknown ROM": LET s$=""
 3050 IF PEEK 40000=255 THEN LET v$="Stock ROM"
 3060 IF PEEK 40000=16 THEN LET v$="TS-Pico ROM v1.0": LET s$="(initial release)"
 3070 IF PEEK 40000=17 THEN LET v$="TS-Pico ROM v1.1": LET s$="(second screen)"
 3080 IF PEEK 40000=18 THEN LET v$="TS-Pico ROM v1.2": LET s$="(new Text Display function)"
 3090 IF PEEK 40000=19 THEN LET v$="TS-Pico ROM v1.3": LET s$="(new Text Display function)"
 3100 IF PEEK 40000=20 THEN GO SUB 500
 3110 PRINT "YOUR SYSTEM IS RUNNING:"
 3120 PRINT v$
 3130 PRINT s$
 3140 INPUT "Press Enter to continue:.... ";a$
 3150 GO TO 1000
 3500 IF PEEK 40001=07 THEN LET v$="TS-Pico ROM v1.4a": LET s$="(32KB ROM initial release)": RETURN 
 3510 IF PEEK 40002=234 THEN LET v$="TS-Pico ROM v1.4b": LET s$="(2ch min command)"
 3520 IF PEEK 40002=134 THEN LET v$="TS-Pico ROM v1.4c": LET s$="(disable DCK at boot)"
 3530 RETURN 
