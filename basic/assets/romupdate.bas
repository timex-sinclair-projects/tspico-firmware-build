#! zmakebas -n romupdate -a 1
#! append romupdate_code.tap
# Store previous RAMTOP in SEED
    4 POKE 23670,PEEK 23730: POKE 23671,PEEK 23731
    6 CLEAR 32599: LET demo=0: LET n=0
# Get previous RAMTOP back from SEED
    8 LET ramtop=PEEK 23670+256*PEEK 23671
   10 IF NOT demo THEN LOAD ""CODE 32600
   20 LET fg=9: LET bg=1: LET bd=7
   22 LET wb=2: LET wf=9: LET df=1
   24 LET loc0=0: LET sl0=0
   30 BORDER bd: PAPER bg: INK fg: BRIGHT 0: FLASH 0: INVERSE 0: OVER 0
   40 IF NOT demo THEN GO SUB 1500
   44 INK fg: CLS : PRINT AT 1,0;
   48 IF NOT demo THEN SAVE "tpi:path"CODE 1,0
   49 IF demo THEN PRINT '"Current mounted file is:"'"/TAP/demo.rom"
   50 PRINT AT 0,0; INK fg; PAPER bd;TAB 31;" "
   52 PRINT INK 5; PAPER 0;" TS-Pico ";
   54 PRINT INK 2;"\::"; INK 4;"\::"; INK 1; BRIGHT 1;"\::";
   56 PRINT PAPER 7; INK 0;TAB 20;" ROM Loader "
   58 PRINT PAPER bd;TAB 31;" "
   60 PLOT INK 0; PAPER bd;0,168: DRAW 255,0: DRAW 0,-9: DRAW -255,0
   70 PRINT #0; INK df;"    \* 2025 TS-Pico DevTeam      ";
   80 PRINT #0;TAB 8; PAPER wb; BRIGHT 1; INK wf;"*** WARNING ***"'
   90 PRINT #0;"This operation completely erases";
   92 PRINT #0;"the selected SRAM or Flash slot.";
  100 PRINT #0''"Press any key ...";
  110 IF INKEY$="" THEN GO TO 110
  200 GO SUB 1000
  210 IF demo THEN GO TO 300
  220 IF loc=2 THEN GO TO 280
  240 FOR i=32685 TO 32699: POKE i,0
  250 NEXT i
  260 FOR i=32885 TO 32899: POKE i,0
  270 NEXT i
  280 SAVE "tpi:blkrcv"
  300 IF loc=1 THEN GO TO 400
  310 PRINT ">Erasing slot ";sl;" of Flash";TAB 26;"...";
  320 IF low=0 AND NOT demo THEN RANDOMIZE USR 32800
  350 IF low=1 AND NOT demo THEN RANDOMIZE USR 32600
  360 PRINT "OK"
  400 PRINT ">Writing slot ";sl;" of ";l$;TAB 26;"...";
  410 IF low=0 AND NOT demo THEN RANDOMIZE USR 32870
  440 IF low=1 AND NOT demo THEN RANDOMIZE USR 32670
  450 PRINT "OK"
  460 REM Need to wait some time after this before giving a tpi: command or it will fail.
  470 REM So do it after the INPUT below.
  500 PRINT 
  530 PRINT "-Select this ROM with one of:"
  540 PRINT " 1.SAVE ""tpi:boot""CODE ";loc;",";sl;":NEW"
  550 PRINT " 2.SAVE ""tpi:dock""CODE ";loc;",";sl
  560 PRINT " for changes to be effective."
  580 INPUT "BOOT resets to 2,1 after boot."''"Boot to ROM ";(loc);",";(sl);" NOW (y/N)?";c$
  590 PRINT '">Unmounting .rom file     ...";
  600 IF NOT demo THEN SAVE "tpi:close"
  610 PRINT "OK"
  620 IF c$="y" OR c$="Y" THEN LET n=1
  630 PRINT ">Restoring DOCK slot...";
  640 ON ERR GO TO 670
  650 IF NOT demo THEN SAVE "tpi:memdock"CODE 0,2: REM Restore prev setting
  660 PRINT "OK": GO TO 900
  670 ON ERR RESET 
  680 IF NOT demo THEN SAVE "tpi:memdock"CODE 2,0: REM default
  690 PRINT "2,0"
  900 PAPER 7: BORDER 7: INK 0
  910 GO TO 3000
 1000 INPUT "Use SRAM(1) or Flash(2)? ";loc
 1010 IF loc<1 OR loc>2 THEN GO TO 1000
 1020 LET l$=("SRAM" AND loc=1)+("Flash" AND loc=2)
 1030 PRINT AT 5,0;" Memory: ";l$;" "
 1032 LET w$=""
 1034 IF loc=loc0 THEN LET w$="BOOT is using "+l$+" slot "+STR$ sl0
 1040 IF loc=2 THEN GO TO 1100
 1050 INPUT "Remember, slots are 32K in size.";(w$)''"Select slot (0..14)? ";sl
 1060 IF sl<0 OR sl>14 THEN GO TO 1050
 1080 GO TO 1160
 1100 INPUT "Remember, slots are 32K in size.";(w$)'"Slots 0..3 are for the system."''"Select slot (4..14)? ";sl
 1110 IF sl>14 THEN GO TO 1100
 1130 IF sl>=4 THEN GO TO 1160
 1140 INPUT " "; PAPER wb; BRIGHT 1; INK 9;"** WARNING!!! ** WARNING!!! **"' BRIGHT 0; PAPER bd;"Are you "; INK wb;"ABSOLUTELY SURE"; INK 9;" you wantto write to system area slot ";(sl);"?"'"This is HIGHLY "; INK wb;"NOT"; INK 9;" RECOMMENDED"''"Please confirm (y/N)? ";c$
 1150 IF c$<>"y" AND c$<>"Y" THEN GO TO 1000
 1160 IF loc<>loc0 OR sl<>sl0 THEN GO TO 1200
#                                                                                                01234567890123456789012345678901 01234567890123456789012345678901
 1170 INPUT " "; PAPER wb; BRIGHT 1; INK 9;"** WARNING!!! ** WARNING!!! **"' BRIGHT 0; PAPER bd;"Currently booted to that slot."'"Continuing will crash the system"''"Please confirm (y/N)? ";c$
 1180 IF c$<>"y" AND c$<>"Y" THEN GO TO 1000
 1200 PRINT " Slot  : ";sl;" "
 1210 PRINT 
 1220 INPUT "SRAM data is lost at power off,"'"Flash data persists."''"Any changes (y/N)? ";c$
 1230 IF c$="y" OR c$="Y" THEN GO TO 1000
 1240 PRINT ">Select slot ";sl;" of ";l$;TAB 26;"...";
 1250 IF NOT demo THEN SAVE "tpi:memdock"CODE loc,sl
 1260 PRINT "OK"
 1270 LET low=0
 1280 IF (sl/2)>INT (sl/2) THEN LET low=1
 1290 RETURN 
# Get current BOOT slot
 1500 INK bg: CLS 
 1502 SAVE "tpi:memboot"
 1510 LET c=0
 1520 GO SUB 1590: IF c$<>"=" THEN RETURN 
 1530 LET c=c+1: LET c$=SCREEN$ (1,c)
 1532 IF c$<>"1" AND c$<>"2" THEN RETURN 
 1534 LET loc0=VAL c$
 1540 GO SUB 1590: IF c$<>"=" THEN RETURN 
 1550 LET c$=SCREEN$ (1,c+1): IF c$=" " THEN RETURN 
 1552 LET sl0=VAL c$
 1560 LET c$=SCREEN$ (1,c+2): IF c$=" " THEN RETURN 
 1562 LET sl0=10*sl0+VAL c$
 1580 RETURN 
 1590 LET c$=SCREEN$ (1,c)
 1592 IF c$="=" THEN RETURN 
 1594 LET c=c+1: IF c<31 THEN GO TO 1590
 1596 RETURN 
# Exit
 3000 IF NOT n THEN GO TO 3100
# Put RAMTOP back and then restart
 3010 PRINT ">Reboot (use reset if needed)...";
 3020 IF NOT demo THEN SAVE "tpi:memboot"CODE loc,sl: NEW 
 3030 CLEAR ramtop: NEW 
# Put RAMTOP back and then clear program
 3100 CLEAR ramtop
