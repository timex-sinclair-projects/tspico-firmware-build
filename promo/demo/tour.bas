#! zmakebas -a 10 -n tour
#
# TS-Pico 2.3: a guided tour, for the release video (promo/demo/README.md).
# One chapter per feature: a title card, then the chapter's commands with a
# caption for each, and a key press between steps. The presenter sets the pace.
#
# The tour works in a folder it makes, /tour, and removes it at the end (and at
# the start, if a stopped run left it behind), so every run shows the same
# screens. It needs the demo card's art.tap, multi.tap and library/ in the
# top folder (promo/demo/card/TAP), and the help folder for chapter 11.
#
# It never replaces itself: no LOAD "" with nothing mounted, no program loads,
# no MERGE, no tpi:boot, no Spectrum mode.
#
# Build: see promo/demo/README.md (zmakebas -a 10 -n tour -o TOUR.TAP tour.bas).
#
# Variables: n chapter number, t$ d$ e$ f$ title-card lines, c$ the command
# shown, cs the character set, g$ gr gc gp a big-letter string and where.
# 64000 counts the key waits (a test hook: emu_tour.py reads it), so the
# tour CLEARs 63999.

# ---- Start: a clean slate --------------------------------------------------
   10 REM TS-Pico 2.3 guided tour
   20 CLEAR 63999: POKE 64000,0
   30 BORDER 1: PAPER 1: INK 7: BRIGHT 0: CLS
   40 PRINT AT 10,8;"Getting ready..."
   50 LET cs=PEEK 23606+256*PEEK 23607
   60 SAVE "tpi:verbose" CODE 1,0: SAVE "tpi:close": MOVE TO "/"
   70 LET z=1: GO TO 7000

# ---- 1 Welcome ---------------------------------------------------------------
 1000 LET n=1: LET t$="Welcome to TS-Pico 2.3"
 1010 LET d$="A tour of what is new since": LET e$="version 1.1, one feature per": LET f$="chapter.": GO SUB 8000
 1020 GO SUB 8100
 1030 PRINT INK 1;"Which ROM is this 2068 running?"''
 1040 LET c$="PRINT PEEK 101": GO SUB 8200
 1050 PRINT ''"  ";PEEK 101''
 1060 PRINT INK 1;"35 means ROM 2.3. The firmware"'"and the ROM are a pair: the"'"web updater installs both."''
 1070 PRINT INK 1;"Commands are SAVE now:"
 1080 PRINT "  SAVE ""tpi:dir"""'"  SAVE ""tpi:cd games"""''
 1090 PRINT INK 1;"LOAD ""tpi:name.tap"" only mounts"'"a file, ready for LOAD """"."
 1100 GO SUB 8900
 1110 GO SUB 8100
 1120 LET c$="SAVE ""tpi:info""": GO SUB 8200
 1130 SAVE "tpi:info"
 1140 GO SUB 8890

# ---- 2 CAT -------------------------------------------------------------------
 1500 LET n=2: LET t$="Listings in color"
 1510 LET d$="CAT lists the card: folders,": LET e$="files and their numbers, with": LET f$="patterns, a page at a time.": GO SUB 8000
 1520 GO SUB 8100
 1530 LET c$="CAT": GO SUB 8200
 1540 CAT
 1550 PRINT 'INK 1;"Folders first, in blue. Each"'"file has a number: LOAD ""tpi:2"""'"mounts file 002."
 1560 GO SUB 8900
 1570 GO SUB 8100
 1580 PRINT INK 1;"Only the TAP files:"
 1590 LET c$="CAT ""*.tap""": GO SUB 8200
 1600 CAT "*.tap"
 1610 GO SUB 8900
 1620 GO SUB 8100
 1630 PRINT INK 1;"Another folder, from here. A"'"long list stops and asks:"
 1640 PRINT INK 1;"Press Y for more, N to stop."
 1650 LET c$="CAT ""library""": GO SUB 8200
 1660 CAT "library"
 1670 GO SUB 8890

# ---- 3 Folders ---------------------------------------------------------------
 2000 LET n=3: LET t$="Folders"
 2010 LET d$="Make a folder, go into it, see": LET e$="where you are, and come back.": LET f$="": GO SUB 8000
 2020 GO SUB 8100
 2030 LET c$="FORMAT ""tour/""": GO SUB 8200
 2040 FORMAT "tour/"
 2050 PRINT INK 1;"FORMAT never wipes the card: it"'"makes a new folder (or tape)."'
 2060 LET c$="MOVE TO ""tour""": GO SUB 8200
 2070 MOVE TO "tour"
 2080 LET c$="SAVE ""tpi:path""": GO SUB 8200
 2090 SAVE "tpi:path"
 2100 PRINT 'INK 1;"MOVE TO """" goes back:"
 2110 LET c$="MOVE TO """"": GO SUB 8200
 2120 MOVE TO ""
 2130 LET c$="SAVE ""tpi:path""": GO SUB 8200
 2140 SAVE "tpi:path"
 2150 GO SUB 8900
 2160 GO SUB 8100
 2170 PRINT INK 1;"The new folder is in the list:"
 2180 LET c$="CAT": GO SUB 8200
 2190 CAT
 2200 GO SUB 8890

# ---- 4 Copying and new tapes -------------------------------------------------
 2500 LET n=4: LET t$="Copies and new tapes"
 2510 LET d$="MOVE copies files. FORMAT": LET e$="starts a new, empty TAP. CAT": LET f$="looks inside a TAP.": GO SUB 8000
 2520 GO SUB 8100
 2530 PRINT INK 1;"Copy a file into the folder:"
 2540 LET c$="MOVE ""multi.tap"" TO ""tour""": GO SUB 8200
 2550 MOVE "multi.tap" TO "tour"
 2560 PRINT 'INK 1;"Go in, and copy with a new name:"
 2570 LET c$="MOVE TO ""tour""": GO SUB 8200
 2580 MOVE TO "tour"
 2590 LET c$="MOVE ""/art.tap"" TO ""pics.tap""": GO SUB 8200
 2600 MOVE "/art.tap" TO "pics.tap"
 2610 PRINT 'INK 1;"A new, empty tape:"
 2620 LET c$="FORMAT ""songs.tap""": GO SUB 8200
 2630 FORMAT "songs.tap"
 2640 PRINT : LET c$="CAT": GO SUB 8200
 2650 CAT
 2660 GO SUB 8900
 2670 GO SUB 8100
 2680 PRINT INK 1;"What is inside a TAP:"
 2690 LET c$="CAT ""multi.tap""": GO SUB 8200
 2700 CAT "multi.tap"
 2705 GO SUB 8900: GO SUB 8100
 2710 PRINT INK 1;"The new tape is mounted. It is"'"empty, and append is on:"
 2720 LET c$="CAT """"": GO SUB 8200
 2730 CAT ""
 2740 PRINT 'INK 1;"Eject it:"
 2750 LET c$="SAVE ""tpi:close""": GO SUB 8200
 2760 SAVE "tpi:close"
 2770 GO SUB 8890

# ---- 5 Single files with f: --------------------------------------------------
 3000 LET n=5: LET t$="Single files with f:"
 3010 LET d$="Save a picture, or some code,": LET e$="as one file of its own.": LET f$="Press ENTER at Start tape.": GO SUB 8000
 3020 GO SUB 8100
 3030 PRINT INK 1;"Draw a picture, then save it as"'"one file on the card:"''
 3040 LET c$="SAVE ""f:title.scr"" SCREEN$": GO SUB 8200
 3050 PRINT 'INK 1;"Press ENTER at Start tape."
 3060 GO SUB 8900
 3070 BORDER 0: PAPER 0: INK 7: CLS
 3080 FOR i=0 TO 9: PRINT AT 12+i,22-i; PAPER 2;"  "; PAPER 6;"  "; PAPER 4;"  "; PAPER 5;"  ": NEXT i
 3090 LET g$="2.3": LET gr=1: LET gc=4: LET gp=5: GO SUB 8600
 3100 PRINT AT 10,4; BRIGHT 1;"TS-Pico";AT 13,1;"One picture,";AT 14,1;"one file:";AT 16,1; INK 6;"title.scr"
 3110 SAVE "f:title.scr" SCREEN$
 3120 GO SUB 8900
 3130 BORDER 7: PAPER 7: INK 0: CLS: GO SUB 8100
 3140 PRINT INK 1;"The screen is wiped. Load the"'"picture back:"''
 3150 LET c$="LOAD ""f:title.scr"" SCREEN$": GO SUB 8200
 3160 GO SUB 8900
 3170 BORDER 0: LOAD "f:title.scr" SCREEN$
 3180 GO SUB 8900
 3190 BORDER 7: PAPER 7: INK 0: CLS: GO SUB 8100
 3200 RESTORE 3210: FOR i=0 TO 15: READ a: POKE USR "a"+i,a: NEXT i
 3210 DATA 36,36,255,129,129,157,149,157,129,129,157,149,157,129,255,36
 3220 PRINT INK 1;"Code too. Two graphics, A and B:"''
 3230 GO SUB 8700
 3240 LET c$="SAVE ""f:ab.bin"" CODE USR ""a"",16": GO SUB 8200
 3250 SAVE "f:ab.bin" CODE USR "a",16
 3260 PRINT 'INK 1;"Wipe them:"''
 3270 FOR i=0 TO 15: POKE USR "a"+i,0: NEXT i
 3280 GO SUB 8700
 3290 LET c$="LOAD ""f:ab.bin"" CODE": GO SUB 8200
 3300 LOAD "f:ab.bin" CODE
 3310 PRINT 'INK 1;"They are back:"''
 3320 GO SUB 8700
 3330 GO SUB 8890

# ---- 6 Streams -----------------------------------------------------------------
 3500 LET n=6: LET t$="Files as streams"
 3510 LET d$="OPEN # connects a stream to a": LET e$="file. PRINT # writes it and": LET f$="INPUT # reads it back.": GO SUB 8000
 3520 GO SUB 8100
 3530 LET c$="OPEN #4,""f:notes.txt"",""w""": GO SUB 8200
 3540 OPEN #4,"f:notes.txt","w"
 3550 LET c$="PRINT #4;""Buy more SD cards""": GO SUB 8200
 3560 PRINT #4;"Buy more SD cards": PRINT #4;"Record the video": PRINT #4;"Have a cup of tea"
 3570 PRINT INK 1;"...and two more lines."
 3580 LET c$="CLOSE #4": GO SUB 8200
 3590 CLOSE #4: PAUSE 10
 3600 PRINT 'INK 1;"Read it back, line by line:"
 3610 LET c$="INPUT #4;a$": GO SUB 8200
 3620 OPEN #4,"f:notes.txt": LET k=0: PRINT
 3630 ON ERR GO TO 3650
 3640 INPUT #4;a$: LET k=k+1: PRINT "  ";k;". ";a$: GO TO 3640
 3650 ON ERR RESET: GO SUB 8800: CLOSE #4: PAUSE 10
 3660 PRINT 'INK 1;"Past the last line: Report ";r$;","'"caught by ON ERR GO TO."
 3670 GO SUB 8900
 3680 GO SUB 8100
 3690 PRINT INK 1;"Records: TAB jumps to one."
 3700 LET c$="OPEN #4,""f:scores.dat"",""u"",12": GO SUB 8200
 3710 OPEN #4,"f:scores.dat","u",12
 3720 LET c$="PRINT #4;TAB 3;""CAROL   150""": GO SUB 8200
 3730 PRINT #4;TAB 3;"CAROL   150": PRINT #4;TAB 1;"ALICE   320": PRINT #4;TAB 2;"BOB     240"
 3740 PRINT INK 1;"(and records 1 and 2)"
 3750 LET c$="INPUT #4;TAB 0;k": GO SUB 8200
 3760 INPUT #4;TAB 0;k
 3770 PRINT "  ";k;" records"'
 3780 FOR i=1 TO k: INPUT #4;TAB i;a$: PRINT "  ";i;". ";a$: NEXT i
 3790 CLOSE #4: PAUSE 10
 3800 GO SUB 8900
 3810 GO SUB 8100
 3820 PRINT INK 1;"A folder listing, a name at a"'"time, for a menu of your own:"
 3830 LET c$="OPEN #5,""d:/*.tap""": GO SUB 8200
 3840 OPEN #5,"d:/*.tap"
 3850 INPUT #5;TAB 0;k
 3860 PRINT 'INK 1;k;" tapes in the top folder:"'
 3870 FOR i=1 TO k: INPUT #5;a$: PRINT "  ";i;"  ";a$: NEXT i
 3880 CLOSE #5: PAUSE 10
 3890 GO SUB 8890

# ---- 7 The virtual printer -----------------------------------------------------
 4000 LET n=7: LET t$="The virtual printer"
 4010 LET d$="LPRINT, LLIST and COPY go to": LET e$="files on the card instead of a": LET f$="TS 2040 printer.": GO SUB 8000
 4020 GO SUB 8100
 4030 LET c$="SAVE ""tpi:picopt""": GO SUB 8200
 4040 SAVE "tpi:picopt"
 4050 LET c$="PRINT PEEK 24027": GO SUB 8200
 4060 PRINT "  ";PEEK 24027;INK 1;"  printing goes to the card"'
 4070 LET c$="LPRINT ""Hello from the 2068""": GO SUB 8200
 4080 LPRINT "Hello from the 2068": LPRINT "TS-Pico 2.3 tour, chapter 7"
 4090 LET c$="LLIST 9900": GO SUB 8200
 4100 LLIST 9900
 4110 PRINT INK 1;"A picture of this screen:"
 4120 LET c$="COPY": GO SUB 8200
 4130 COPY
 4140 GO SUB 8900
 4150 GO SUB 8100
 4160 PRINT INK 1;"Finish the text file:"
 4170 LET c$="SAVE ""tpi:clprint""": GO SUB 8200
 4180 SAVE "tpi:clprint"
 4190 PRINT 'INK 1;"Printing back to the TS 2040:"
 4200 LET c$="SAVE ""tpi:ts2040""": GO SUB 8200
 4210 SAVE "tpi:ts2040"
 4220 LET c$="PRINT PEEK 24027": GO SUB 8200
 4230 PRINT "  ";PEEK 24027''
 4240 PRINT INK 1;"On the card, next to the TAP"'"folder:"''"  /VLPRINT/PRNnnnn.TXT  the text"'"  /VSCREEN/SCRnnnn.BMP  the COPY"
 4250 GO SUB 8890

# ---- 8 Mounting a tape ---------------------------------------------------------
 4500 LET n=8: LET t$="Mounting a tape"
 4510 LET d$="LOAD ""tpi:name.tap"" mounts a": LET e$="tape; LOAD """" reads it, block": LET f$="by block, like a cassette.": GO SUB 8000
 4520 GO SUB 8100
 4530 LET c$="LOAD ""tpi:pics.tap""": GO SUB 8200
 4540 LOAD "tpi:pics.tap"
 4550 PRINT INK 1;"What is on it:"
 4560 LET c$="CAT """"": GO SUB 8200
 4570 CAT ""
 4580 PRINT 'INK 1;"> marks the tape pointer: the"'"block the next LOAD starts from."
 4590 GO SUB 8900
 4600 GO SUB 8100
 4610 PRINT INK 1;"Load the code: graphics A to H."
 4620 LET c$="LOAD """" CODE USR ""a""": GO SUB 8200
 4630 LOAD "" CODE USR "a"
 4640 PRINT '"    "; INK 1;"\a\b"; INK 2;"  \e\f"'"    "; INK 1;"\c\d"; INK 2;"  \g\h"''
 4650 PRINT INK 1;"The pointer has moved on:"
 4660 LET c$="CAT """"": GO SUB 8200
 4670 CAT ""
 4680 GO SUB 8900
 4690 GO SUB 8100
 4700 PRINT INK 1;"Now the picture:"''
 4702 LET c$="LOAD """" SCREEN$": GO SUB 8200
 4704 GO SUB 8900
 4706 BORDER 1: LOAD "" SCREEN$
 4708 GO SUB 8900
 4710 BORDER 7: PAPER 7: INK 0: CLS: GO SUB 8100
 4720 PRINT INK 1;"Eject the tape:"
 4730 LET c$="SAVE ""tpi:close""": GO SUB 8200
 4740 SAVE "tpi:close"
 4750 GO SUB 8890

# ---- 9 Reports, not hangs --------------------------------------------------------
 5000 LET n=9: LET t$="Reports, not hangs"
 5010 LET d$="A mistake gives a report. A": LET e$="program can catch it with ON": LET f$="ERR and carry on.": GO SUB 8000
 5020 GO SUB 8100
 5030 PRINT INK 1;"A version 1.1 habit, with the"'"messages on:"
 5040 LET c$="SAVE ""tpi:verbose"" CODE 1,1": GO SUB 8200
 5050 SAVE "tpi:verbose" CODE 1,1: PRINT 
 5060 LET c$="LOAD ""tpi:dir""": GO SUB 8200
 5070 ON ERR GO TO 5090
 5080 LOAD "tpi:dir"
 5090 ON ERR RESET: GO SUB 8800: PRINT 
 5100 PRINT 'INK 1;"Report ";r$;": LOAD only mounts a"'"file now. The listing is"'"SAVE ""tpi:dir"", or CAT."'
 5110 LET c$="SAVE ""tpi:verbose"" CODE 1,0": GO SUB 8200
 5120 SAVE "tpi:verbose" CODE 1,0
 5130 GO SUB 8900
 5140 GO SUB 8100
 5150 PRINT INK 1;"A SAVE name with a space in it:"
 5160 LET c$="SAVE ""my game""": GO SUB 8200
 5170 PRINT INK 1;"(press ENTER at Start tape)"
 5180 ON ERR GO TO 5200
 5190 SAVE "my game"
 5200 ON ERR RESET: GO SUB 8800
 5210 PRINT 'INK 1;"Report ";r$;". A SAVE name takes"'"letters, digits, - and _ only."'"Nothing was written."
 5220 GO SUB 8900
 5230 GO SUB 8100
 5240 PRINT INK 1;"ERASE with a pattern asks first:"
 5250 PRINT PAPER 5;" Y erases it, N keeps it "
 5260 LET c$="ERASE ""*.tap""": GO SUB 8200
 5270 ERASE "*.tap": PRINT 
 5280 PRINT 'INK 1;"What is left:"
 5290 LET c$="CAT": GO SUB 8200
 5300 CAT
 5310 GO SUB 8890

# ---- 10 BREAK ------------------------------------------------------------------
 5500 LET n=10: LET t$="BREAK is safe"
 5510 LET d$="CAPS SHIFT + SPACE stops a": LET e$="TS-Pico command, and the next": LET f$="one works at once.": GO SUB 8000
 5520 GO SUB 8100
 5530 PRINT INK 1;"At Scroll?, press BREAK"
 5540 PRINT PAPER 5;" CAPS SHIFT + SPACE "
 5550 LET c$="CAT ""/library""": GO SUB 8200
 5560 POKE 23739,0: LET q=0: ON ERR GO TO 5580
 5570 CAT "/library": GO TO 5590
# BREAK gives D in the CAT. Fingers still on the keys then give L BREAK into
# program at the next statement, so the trap stays set until they let go.
 5580 IF q=0 THEN LET q=PEEK 23739
 5585 ON ERR GO TO 5580
 5590 IF INKEY$<>"" THEN GO TO 5590
 5595 PAUSE 25: ON ERR RESET: LET r$=CHR$ (48+q+7*(q>9))
 5600 GO SUB 8100
 5610 IF r$="D" THEN PRINT INK 1;"Report D BREAK - CONT repeats,"'"caught by ON ERR GO TO."''
 5620 IF r$<>"D" THEN PRINT INK 1;"(No BREAK that time.)"''
 5630 PRINT INK 1;"The next command works at once:"
 5640 LET c$="SAVE ""tpi:path""": GO SUB 8200
 5650 SAVE "tpi:path"
 5660 GO SUB 8890

# ---- 11 Help -------------------------------------------------------------------
 6000 LET n=11: LET t$="Help on the card"
 6010 LET d$="SAVE ""tpi:help"" lists the": LET e$="commands; add a word for its": LET f$="page. Y scrolls on, N stops.": GO SUB 8000
 6020 GO SUB 8100
 6030 LET c$="SAVE ""tpi:help""": GO SUB 8200
 6040 SAVE "tpi:help"
 6050 GO SUB 8900
 6060 GO SUB 8100
 6070 LET c$="SAVE ""tpi:help cat""": GO SUB 8200
 6080 SAVE "tpi:help cat"
 6090 GO SUB 8890

# ---- 12 Clean-up and the end card ------------------------------------------------
 6500 LET n=12: LET t$="Tidying up"
 6510 LET d$="Erase what the tour made, so": LET e$="it can run again.": LET f$="": GO SUB 8000
 6520 GO SUB 8100
 6530 LET c$="MOVE TO ""/""": GO SUB 8200
 6540 MOVE TO "/"
 6550 PRINT INK 1;"Each file in tour/, by name:"
 6560 LET z=2: GO TO 7000
 6570 LET c$="ERASE ""tour/""": GO SUB 8200
 6590 LET c$="CAT": GO SUB 8200
 6600 CAT
 6610 GO SUB 8900
 6620 BORDER 1: PAPER 1: INK 7: BRIGHT 0: CLS
 6630 PRINT AT 0,0; PAPER 2;"        "; PAPER 6;"        "; PAPER 4;"        "; PAPER 5;"        "
 6640 LET g$="2.3": LET gr=2: LET gc=4: LET gp=6: GO SUB 8600
 6650 PRINT AT 11,4; BRIGHT 1; INK 6;"TS-Pico 2.3"
 6660 PRINT AT 13,4;"Next, shown by hand:";AT 15,4;"the menu and the Commander,";AT 16,4;"cartridges, and Spectrum";AT 17,4;"mode."
 6670 PRINT AT 21,0; PAPER 2;"        "; PAPER 6;"        "; PAPER 4;"        "; PAPER 5;"        "
 6680 GO SUB 8900
 6690 BORDER 7: PAPER 7: INK 0: CLS
 6700 GO TO 9999

# ---- Clean the tour folder away (z=1: at the start, z=2: chapter 12) ------------
# Reads tour/ with a d: stream, erasing each name; ERASE "tour/" then removes
# the folder. A missing folder (the usual case at the start) gives F at the
# OPEN, and the erases are skipped. PAUSE 10 after CLOSE #: in the emulator a
# command sent straight after CLOSE # of a d: stream can arrive while the Pico
# is still finishing the CLOSE, and get Report T (README, "Findings").
 7000 ON ERR GO TO 7060
 7010 OPEN #4,"d:tour/"
 7020 ON ERR GO TO 7050
 7030 INPUT #4;a$: ERASE "tour/"+a$
 7040 IF z=2 THEN PRINT "  ERASE ""tour/";a$;""""
 7045 GO TO 7030
 7050 ON ERR RESET: CLOSE #4: PAUSE 10
 7055 ON ERR GO TO 7060: ERASE "tour/"
 7060 ON ERR RESET
 7070 IF z=1 THEN GO TO 1000
 7080 GO TO 6570

# ---- Subroutines ---------------------------------------------------------------
# 8000 the title card: chapter n, title t$, three lines d$ e$ f$
 8000 BORDER 1: PAPER 1: INK 7: BRIGHT 0: CLS
 8010 PRINT AT 0,0; PAPER 2;"        "; PAPER 6;"        "; PAPER 4;"        "; PAPER 5;"        "
 8020 LET g$=STR$ n: LET gr=2: LET gc=2: LET gp=6: GO SUB 8600
 8030 PRINT AT 4,21; INK 5;"CHAPTER";AT 6,21; INK 5;n;" of 12"
 8040 PRINT AT 12,2; BRIGHT 1; INK 6;t$
 8050 PRINT AT 14,2;d$;AT 15,2;e$;AT 16,2;f$
 8060 PRINT AT 21,0; PAPER 2;"        "; PAPER 6;"        "; PAPER 4;"        "; PAPER 5;"        "
 8070 GO TO 8900
# 8100 a chapter screen: white, with the chapter's name on a blue bar
 8100 BORDER 7: PAPER 7: INK 0: BRIGHT 0: CLS
 8110 LET c$=" "+STR$ n+"  "+t$+"                                "
 8120 PRINT AT 0,0; PAPER 1; INK 7; BRIGHT 1;c$( TO 32)
 8130 PRINT : POKE 23692,255: RETURN
# 8200 show the command about to run, on a yellow strip
 8200 IF LEN c$<31 THEN LET c$=" "+c$+" "
 8210 POKE 23692,255: PRINT PAPER 6; BRIGHT 1;c$: POKE 23692,255: RETURN
# 8600 big letters: g$ at row gr, column gc, a cell per dot, PAPER gp
 8600 FOR k=1 TO LEN g$: LET a=cs+8*CODE g$(k)
 8610 FOR y=0 TO 7: LET b=PEEK (a+y)
 8620 FOR x=0 TO 7: LET b=b+b: IF b>255 THEN LET b=b-256: PRINT AT gr+y,gc+8*(k-1)+x; PAPER gp;" "
 8630 NEXT x: NEXT y: NEXT k: RETURN
# 8700 the two graphics, A and B, big and small
 8700 PRINT "    "; INK 2;"\a\b\a\b\a\b";"   "; INK 1;"\a\b"''
 8710 RETURN
# 8800 the last report as its letter, in r$
 8800 LET r=PEEK 23739: LET r$=CHR$ (48+r+7*(r>9)): RETURN
# 8890 wait for a key: the end of a chapter; 8900: any other step. It waits
# for the key to be let go, too: SPACE still down when a LOAD or SAVE starts
# is BREAK to the tape routines.
 8890 LET c$=" Press any key: next chapter ": GO TO 8910
 8900 LET c$=" Press any key "
 8910 POKE 64000,PEEK 64000+1: POKE 23692,255
 8920 PRINT #0;AT 1,0; PAPER 0; INK 7; BRIGHT 1;c$;
 8930 IF INKEY$<>"" THEN GO TO 8930
 8940 IF INKEY$="" THEN GO TO 8940
 8945 IF INKEY$<>"" THEN GO TO 8945
 8950 PRINT #0;AT 1,0;"                                ";
 8960 RETURN

# ---- LLIST 9900 (chapter 7) prints these --------------------------------------
 9900 REM TS-Pico 2.3 guided tour
 9910 REM LLIST 9900 sent these lines
 9920 REM to /VLPRINT on the SD card
 9999 REM end of the tour
