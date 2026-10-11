#! zmakebas -n dckupd3 -a 10
# The v3 card's DCK loader (phase 5 step 4, docs/v3-slots-proposal.md).
# MOUNT_FILE serves it for a mounted .DCK on the v3 card, in place of
# dckupdate.tap. Same questions as dckupdate.bas: a cartridge is 64K, two
# slots numbered by the even one; but the Pico writes the
# slot file itself (SAVE "tpi:blkrcv" CODE mem,slot), so there is no
# machine code and no erase. If those slots are in the DOCK now, the Pico
# reloads it there at once.
   10 LET fg=9: LET bg=1: LET bd=7
   12 LET wb=2: LET wf=9: LET df=1
   14 LET loc0=0: LET sl0=0
   20 BORDER bd: PAPER bg: INK fg: BRIGHT 0: FLASH 0: INVERSE 0: OVER 0
   30 GO SUB 1500
   40 INK fg: CLS : PRINT AT 1,0;
   48 SAVE "tpi:path"CODE 1,0
   50 PRINT AT 0,0; INK fg; PAPER bd;TAB 31;" "
   52 PRINT INK 5; PAPER 0;" TS-Pico ";
   54 PRINT INK 2;"\::"; INK 4;"\::"; INK 1; BRIGHT 1;"\::";
   56 PRINT PAPER 7; INK 0;TAB 20;" DCK Loader "
   58 PRINT PAPER bd;TAB 31;" "
   60 PLOT INK 0; PAPER bd;0,168: DRAW 255,0: DRAW 0,-9: DRAW -255,0
   70 PRINT #0; INK df;"    \* 2026 TS-Pico DevTeam      ";
   80 PRINT #0;TAB 8; PAPER wb; BRIGHT 1; INK wf;"*** WARNING ***"'
   90 PRINT #0;"This operation replaces all of  ";
   92 PRINT #0;"the selected SRAM or Flash slot.";
  100 PRINT #0''"Press any key ...";
  110 IF INKEY$="" THEN GO TO 110
  200 GO SUB 1000
  300 PRINT ">Writing slots ";sl;"-";sl+1;" of ";l$;TAB 25;"...";
  310 SAVE "tpi:blkrcv"CODE loc,sl
  320 PRINT "OK"
  500 PRINT 
  530 PRINT "-Put this cartridge in with:"
  540 PRINT " SAVE ""tpi:dock""CODE ";loc;",";sl
  580 INPUT "DOCK resets to config setting atpower-on."''"Put ";(loc);",";(sl);" in the DOCK NOW (y/N)?";c$
  590 PRINT '">Unmounting .dck file     ...";
  600 SAVE "tpi:close"
  610 PRINT "OK"
  620 PAPER 7: BORDER 7: INK 0
  630 IF c$="y" OR c$="Y" THEN SAVE "tpi:dock"CODE loc,sl
  640 STOP 
 1000 INPUT "Use SRAM(1) or Flash(2)? ";loc
 1010 IF loc<1 OR loc>2 THEN GO TO 1000
 1020 LET l$=("SRAM" AND loc=1)+("Flash" AND loc=2)
 1030 PRINT AT 5,0;" Memory: ";l$;" "
 1032 LET w$=""
 1034 IF loc=loc0 THEN LET w$="BOOT is using "+l$+" slot "+STR$ sl0
 1040 IF loc=2 THEN GO TO 1100
 1050 INPUT "Remember, slots are 32K in size,"'"and cartridges use two slots.";(w$)''"Select slot (even 0..14)? ";sl
 1060 IF sl<0 OR sl>14 OR sl<>INT sl OR sl/2<>INT (sl/2) THEN GO TO 1050
 1080 GO TO 1160
 1100 INPUT "Remember, slots are 32K in size,"'"and cartridges use two slots.   ";(w$)'"Slots 0..3 are for the system."''"Select slot (even 4..14)? ";sl
 1110 IF sl<0 OR sl>14 OR sl<>INT sl OR sl/2<>INT (sl/2) THEN GO TO 1100
 1120 IF sl>=4 THEN GO TO 1160
 1130 IF sl<>0 THEN GO TO 1140
#                                                                                                01234567890123456789012345678901 01234567890123456789012345678901
 1132 INPUT " "; PAPER wb; BRIGHT 1; INK 9;"** WARNING!!! ** WARNING!!! **"' BRIGHT 0; PAPER bd;"Flash slot 0 is the Spectrum ROMthat Spectrum mode needs."''"Replace it (y/N)? ";c$
 1134 IF c$<>"y" AND c$<>"Y" THEN GO TO 1000
 1140 INPUT " "; PAPER wb; BRIGHT 1; INK 9;"** WARNING!!! ** WARNING!!! **"' BRIGHT 0; PAPER bd;"Are you "; INK wb;"ABSOLUTELY SURE"; INK 9;" you wantto write to system area slot ";(sl);"?"'"This is HIGHLY "; INK wb;"NOT"; INK 9;" RECOMMENDED"''"Please confirm (y/N)? ";c$
 1150 IF c$<>"y" AND c$<>"Y" THEN GO TO 1000
 1160 IF loc<>loc0 OR (sl<>sl0 AND sl+1<>sl0) THEN GO TO 1200
 1170 INPUT "Currently booted to one of thoseslots: it runs the new contents from the next boot or tpi:boot."''"Continue (y/N)? ";c$
 1180 IF c$<>"y" AND c$<>"Y" THEN GO TO 1000
 1200 PRINT " Slot  : ";sl;" "
 1210 PRINT 
 1220 INPUT "SRAM data is lost at power off,"'"Flash data persists. DOCK resets"'"to config setting at power-on."''"Any changes (y/N)? ";c$
 1230 IF c$="y" OR c$="Y" THEN GO TO 1000
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
