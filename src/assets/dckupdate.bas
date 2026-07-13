   10 BORDER 1: PAPER 1: INK 7
   20 LOAD ""CODE 32600: CLS 
   30 PRINT " ** TS-Pico Cartridge Update **"
   40 PRINT " **  \* 2023 TS-Pico DevTeam  **"
   50 PRINT "": PRINT ""
   60 PRINT TAB 10; FLASH 1;"*** WARNING ***"
   70 PRINT 
   80 PRINT "This operation completely erases"
   90 PRINT "the selected slot in Flash"
  140 PRINT : PRINT : PRINT 
  160 PRINT : PRINT : PRINT TAB 4;"Press any key to continue"
  170 IF INKEY$="" THEN GO TO 170
  220 GO SUB 1000
  230 IF loc=2 THEN GO TO 260
  240 FOR i=32685 TO 32699: POKE i,0
  245 NEXT i
  250 FOR i=32885 TO 32899: POKE i,0
  255 NEXT i
  260 INPUT "Hit <ENTER> to start process";c$
  270 SAVE "tpi:blkrcv"
  280 IF loc=1 THEN GO TO 360
  290 PRINT : PRINT "Erasing LOWER 32Kb block..."
  300 RANDOMIZE USR 32800
  310 PRINT "LOWER 32Kb erased"
  320 PRINT 
  330 PRINT "Erasing UPPER 32Kb block..."
  340 RANDOMIZE USR 32600
  350 PRINT "UPPER 32Kb erased"
  360 PRINT 
  370 PRINT "Writing LOWER 32Kb block..."
  380 RANDOMIZE USR 32870
  390 PRINT "LOWER 32Kb writing finished."
  400 PRINT 
  410 PRINT "Writing UPPER 32Kb block..."
  420 RANDOMIZE USR 32670
  430 PRINT "UPPER 32Kb writing finished."
  440 INPUT "Press <ENTER> to continue...";c$
  450 CLS 
  460 PRINT "To activate cartrdige, enter"
  470 PRINT "SAVE ""tpi:dock"" CODE ";STR$ (loc);", ";STR$ (sl)
  480 PRINT "and the NEW"
  490 PRINT : PRINT : PRINT "To skip cartridge load"
  500 PRINT "press ""D"" during boot"
  510 PRINT "All processes finished."
  520 PRINT : PRINT : INPUT "Press <ENTER> to exit...";c$
  530 PAPER 7: BORDER 7: INK 0
  540 GO TO 3000
 1000 CLS 
 1010 INPUT "Use SRAM(1) or Flash(2)?: ";loc
 1020 IF loc<1 OR loc>2 THEN GO TO 1010
 1030 CLS 
 1040 IF loc=2 THEN GO TO 1100
 1050 LET l$="SRAM"
 1060 INPUT "Select slot (even 0..14)?: ";sl
 1070 IF sl<0 OR sl>14 THEN GO TO 1060
 1080 IF (sl/2)>INT (sl/2) THEN GO TO 1060
 1090 GO TO 1140
 1100 LET l$="Flash"
 1110 INPUT "Select slot (even 4..14)?: ";sl
 1120 IF sl<4 OR sl>14 THEN GO TO 1110
 1130 IF (sl/2)>INT (sl/2) THEN GO TO 1110
 1140 PRINT "Selecting slot ";sl;" of ";l$
 1150 PRINT 
 1160 SAVE "tpi:memdock"CODE loc,sl
 1170 PRINT "Slot ";sl;" of ";l$;" selected OK"
 1180 RETURN 
 3000 CLS 
