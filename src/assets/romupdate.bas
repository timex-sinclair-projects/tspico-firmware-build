   10 IF 0 THEN LOAD ""CODE 32600: CLS 
   20 LET fg=9: LET bg=5: LET bd=7
   22 LET wb=2: LET hb=0: LET df=1
   30 BORDER bd: PAPER bg: INK fg: BRIGHT 0: FLASH 0: INVERSE 0: OVER 0
   32 CLS 
   40 PRINT INK 5; PAPER hb;" TS-Pico ";
   42 PRINT PAPER hb; INK 2;"\::"; INK 4;"\::"; INK 1; BRIGHT 1;"\::";
   44 PRINT PAPER 7; INK 0; BRIGHT 1; TAB 20;" ROM Loader "
#   46 INK bd: PAPER hb: PLOT 0,174: DRAW 0,1: DRAW 1,0: PLOT 254,175: DRAW 1,0: DRAW 0,-1
# We could use tpi:path CODE 1,0 to get the mounted file name
# -> Nope, because the Pico switched it to this .tap file already.
# How about tpi:path CODE 1,1 to print the previous file mounted?
# This could go with a command to re-mount the previous file.
#   48 INK fg: PAPER bg
   49 PRINT PAPER bd; TAB 31; " "
   50 PRINT PAPER bd; INK df;"    \* 2023 TS-Pico DevTeam"
   60 PRINT PAPER bg; INK bd;"\''\''\''\''\''\''\''\''\''\''\''\''\''\''\''\''\''\''\''\''\''\''\''\''\''\''\''\''\''\''\''\''"
   80 PRINT #0;TAB 8; PAPER wb; BRIGHT 1; INK 9;"*** WARNING ***"'
   90 PRINT #0;"This operation completely erases";
   92 PRINT #0;"the selected SRAM or Flash slot.";
  160 GO SUB 1500
  220 GO SUB 1000
  230 IF loc=2 THEN GO TO 280
  240 FOR i=32685 TO 32699: POKE i,0
  250 NEXT i
  260 FOR i=32885 TO 32899: POKE i,0
  270 NEXT i
  290 IF 0 THEN SAVE "tpi:blkrcv"
  300 IF loc=1 THEN GO TO 350
  310 PRINT ">Erasing slot ";sl;" of Flash...";
  320 IF low=0 THEN REM RANDOMIZE USR 32800
  330 IF low=1 THEN REM RANDOMIZE USR 32600
  340 PRINT "OK"
  360 PRINT ">Writing to slot ";sl;" of ";l$;"...";
  370 IF low=0 THEN REM RANDOMIZE USR 32870
  380 IF low=1 THEN REM RANDOMIZE USR 32670
  400 PRINT "OK"
  460 PRINT ">Restoring DOCK slot to default  2,0...";
  470 IF 0 THEN SAVE "tpi:memdock"CODE 2,0
  480 PRINT "OK"
  500 PRINT '" Select this ROM with one of:"
  505 PRINT " > SAVE ""tpi:boot"" CODE ";STR$ loc;",";STR$ sl
  506 PRINT " > SAVE ""tpi:dock"" CODE ";STR$ loc;",";STR$ sl
  510 PRINT " for changes to be effective."
  530 PAPER 7: BORDER 7: INK 0
  540 GO TO 3000
 1010 INPUT "Use SRAM(1) or Flash(2)?: ";loc
 1020 IF loc<1 OR loc>2 THEN GO TO 1010
 1030 LET l$=("SRAM" AND loc=1)+("Flash" AND loc=2)
 1035 PRINT AT 5,0;" Memory: ";l$;" "
 1040 IF loc=2 THEN GO TO 1090
 1060 INPUT "Remember, slots are 32K in size"''"Select slot (0..14)?: ";sl
 1070 IF sl<0 OR sl>14 THEN GO TO 1060
 1080 GO TO 1190
 1100 INPUT "Remember, slots are 32K in size"''"Select slot (4..14)?: ";sl
 1110 IF sl>14 THEN GO TO 1100
 1120 IF sl>=4 THEN GO TO 1190
 1130 INPUT " "; PAPER wb; BRIGHT 1; INK 9;"** WARNING!!! ** WARNING!!! **"' BRIGHT 0; PAPER bd;"Are you "; INK wb;"ABSOLUTELY SURE"; INK 9;" you wantto write to system area slot ";(sl);"?"'"This is HIGHLY "; INK wb;"NOT"; INK 9;" RECOMMENDED"''"Please confirm (y/N): ";c$
 1180 IF c$<>"y" AND c$<>"Y" THEN GO TO 1000
 1190 PRINT " Slot  : ";sl;" "
 1200 PRINT 
 1210 INPUT "Any changes (y/N): ";c$
 1220 IF c$="y" OR c$="Y" THEN GO TO 1000
 1230 IF 0 THEN SAVE "tpi:memdock"CODE loc,sl
 1240 PRINT ">Slot ";sl;" of ";l$;" selected OK"
 1250 LET low=0
 1260 IF (sl/2)>INT (sl/2) THEN LET low=1
 1270 RETURN 
 1500 PRINT #0''"Press any key ...";
 1510 IF INKEY$="" THEN GO TO 1510
 1520 RETURN 
 2099 RETURN 
 3000 REM CLS 
