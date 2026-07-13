   10 BORDER 1: PAPER 1: INK 7
   20 LOAD ""CODE 32600: CLS 
   30 PRINT " **** TS-Pico ROM Update  ****"
   40 PRINT " **  \* 2023 TS-Pico DevTeam   **"
   50 PRINT "": PRINT ""
   60 PRINT TAB 10; FLASH 1;"*** WARNING ***"
   70 PRINT 
   80 PRINT "This operation completely erases"
   90 PRINT "the selected slot in Flash"
  140 PRINT : PRINT : PRINT 
  160 PRINT : PRINT : PRINT TAB 4;"Press any key to continue"
  170 IF INKEY$="" THEN GO TO 170
  220 GO SUB 1000
  230 IF loc=2 THEN GO TO 280
  240 FOR i=32685 TO 32699: POKE i,0
  250 NEXT i
  260 FOR i=32885 TO 32899: POKE i,0
  270 NEXT i
  280 INPUT "Hit <ENTER> to start process";c$
  290 SAVE "tpi:blkrcv"
  300 IF loc=1 THEN GO TO 350
  310 PRINT : PRINT "Erasing slot ";sl;" of Flash"
  320 IF low=0 THEN RANDOMIZE USR 32800
  330 IF low=1 THEN RANDOMIZE USR 32600
  340 PRINT "Slot ";sl;" of Flash erased OK."
  350 PRINT 
  360 PRINT "Writing to slot ";sl;" of ";l$;"..."
  370 IF low=0 THEN RANDOMIZE USR 32870
  380 IF low=1 THEN RANDOMIZE USR 32670
  390 PRINT 
  400 PRINT "Write to ";l$;" finished OK."
  410 INPUT "Press <ENTER> to continue...";c$
  420 CLS 
  430 PRINT "All processes finished."
  440 PRINT "Slot ";sl;" of ";l$;" updated OK"
  450 PRINT : PRINT 
  460 PRINT "Restoring system default config"
  470 SAVE "tpi:memdock"CODE 2,0
  480 PRINT "Default config restored OK"
  490 PRINT : PRINT 
  500 PRINT "You need to manually select ROM"
  505 PRINT "with SAVE ""tpi:mem"" CODE ";STR$ loc;",";STR$ sl
  510 PRINT "for changes to be effective"
  520 INPUT "Press <ENTER> to exit...";c$
  530 PAPER 7: BORDER 7: INK 0
  540 GO TO 3000
 1000 CLS 
 1010 INPUT "Use SRAM(1) or Flash(2)?: ";loc
 1020 IF loc<1 OR loc>2 THEN GO TO 1010
 1030 CLS 
 1040 IF loc=2 THEN GO TO 1090
 1050 LET l$="SRAM"
 1060 INPUT "Select slot (0..14)?: ";sl
 1070 IF sl<0 OR sl>14 THEN GO TO 1060
 1080 GO TO 1190
 1090 LET l$="Flash"
 1100 INPUT "Select slot (4..14)?: ";sl
 1110 IF sl>14 THEN GO TO 1100
 1120 IF sl>=4 THEN GO TO 1190
 1130 PRINT : PRINT FLASH 1;"** WARNING!!! * WARNING!!! **": PRINT : PRINT : PRINT "Are you ** ABSOLUTELY SURE **"
 1140 PRINT "to write to system area slot ";sl;"?"
 1160 PRINT : PRINT : PRINT "** HIGHLY "; FLASH 1;" NOT "; FLASH 0;" RECOMMENDED **"
 1170 INPUT "Please confirm (y/N): ";c$
 1180 IF c$<>"y" AND c$<>"Y" THEN GO TO 180
 1190 CLS : PRINT "Selecting slot ";sl;" of ";l$
 1200 PRINT 
 1210 SAVE "tpi:memdock"CODE loc,sl
 1220 PRINT "Slot ";sl;" of ";l$;" selected OK"
 1230 LET low=0
 1240 IF (sl/2)>INT (sl/2) THEN LET low=1
 1250 RETURN 
 3000 CLS 
