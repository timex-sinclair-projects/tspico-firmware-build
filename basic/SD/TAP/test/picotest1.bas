#! zmakebas -n picotest1 -a 1 -o - picotest1.bas | cat - test12.tap > picotest1.tap
# TS-Pico BASIC Tester
    4 DEF FN S$(l,t$,a,b)=("LOAD " AND l=1)+("SAVE " AND l=2)+("IN " AND l=3)+("OUT " AND l=4)+((""""+t$+"""") AND l<3)+((("CODE " AND l<3)+STR$ a+((","+STR$ b) AND l<>3)) AND (a OR b OR l>2))
    6 LET demo=0
    7 LET e$="0123456789ABCDEFGHIJKLMNOPQR"
   10 LET l=0: LET t$="": LET a=0: LET b=0
   20 LET fg=9: LET bg=7: LET bd=5
   22 LET wb=2: LET wf=9: LET df=1
   24 LET ch=1: LET cb=bd
   25 LET p=0
   26 LET t=0: LET s=0: LET cl=1
   30 BORDER bd: PAPER bd: INK fg: BRIGHT 0: FLASH 0: INVERSE 0: OVER 0
   44 CLS 
   50 PRINT AT 0,0; INK fg; PAPER bd;TAB 31;" "
   52 PRINT INK 5; PAPER 0;" TS-Pico ";
   54 PRINT INK 2;"\::"; INK 4;"\::"; INK 1; BRIGHT 1;"\::";
   56 PRINT PAPER 7; INK 0;TAB 16;" TS-Pico Tester "
   58 PRINT PAPER bd;TAB 31;" "
   60 PLOT INK 0; PAPER bd;0,168: DRAW INK 0; PAPER bd;255,0: DRAW INK 0; PAPER 7;0,-9: DRAW INK 0; PAPER bd;-255,0
   70 PRINT #0; INK df;"    \* 2025 TS-Pico DevTeam      ";
   80 PRINT #0;"This tests most TS-Pico commandswith user assistance.";
   84 IF demo THEN PRINT #0' INK df;"       --- DEMO MODE ---";
#                            01234567890123456789012345678901
   90 PRINT #0''"Press a key to start...";
   92 LET c$=INKEY$: IF c$="" THEN GO TO 92
   98 GO TO 900
  200 INPUT "Press Enter:";c$: RETURN 
  300 CLS 
  302 PRINT "Test #";t;" of ";n;", line ";dl'">";z$'u$
  306 PRINT "Expect:";r$'"Log:"
  310 LET err=0: ON ERR GO TO 500
  320 IF NOT demo THEN SAVE "tpi:log"
  330 ON ERR RESET 
  340 IF err>0 THEN PRINT '"*** ERROR in tpi:log": STOP 
  350 IF demo THEN PRINT "<output of tpi:log>"
  360 GO SUB 200
  370 RETURN 
  500 LET err=PEEK 23739
  510 LET erl=PEEK 23736+256*PEEK 23737
  520 PRINT ' PAPER 2;"*** ERROR: ";e$(err+1);" ***";TAB 31;" "
  530 IF err=19 THEN PRINT '"*** TS-Pico communication error"
  540 IF err=9 OR err=17 OR err=19 THEN ON ERR RESET : STOP 
  550 GO TO erl+1
  900 PRINT "We start in the /TAP folder of"
  901 PRINT "the SD card which is the ""root"""
  902 PRINT "that the TS-Pico is limited to."
#            01234567890123456789012345678901
  910 PRINT '"For each command, you're shown"
  911 PRINT "the command, a description of"
  912 PRINT "what it will do, and afterward,"
  913 PRINT "what the expected result is. At"
  914 PRINT "the prompt after, you can enter"
  915 PRINT """l"" to see the system log of"
  916 PRINT "the result."
  920 GO SUB 200
  930 READ n
 1000 LET d=PEEK 23639+256*PEEK 23640
 1002 IF PEEK d<>13 THEN LET d=d+1: GO TO 1002
 1004 LET dl=256*PEEK (d+1)+PEEK (d+2)
 1008 READ l
 1010 IF l=0 THEN PRINT '"End of tests": STOP 
 1020 LET t=t+1
 1030 READ t$,a,b,u$,r$,x$
 1032 IF (s>0 AND t<s) THEN GO TO 1000
 1034 IF l<0 THEN PRINT "Test ";t;" disabled": GO TO 1000
 1040 LET e=CODE x$-CODE "0"
 1050 IF x$>"A" THEN LET e=CODE x$-CODE "A"+10
 1060 LET pk=-1
 1070 IF a<0 THEN LET pk=b: LET a=0: LET b=0: LET e=VAL x$: REM A PEEK test result
 1100 PAPER bg: CLS 
 1110 LET z$=FN S$(l,t$,a,b)
# A seeming bug in Fuse: PRINT PAPER p;"text";FN S$()
# Prints "text" with the paper given, but the result of FN S$() is not.
# You have to store the FN result in a string to print.
 1112 PAPER cb
 1114 FOR x=16 TO 21
 1116 PRINT AT x,0;TAB 31;" ";
 1118 NEXT x
 1120 PRINT AT 16,0;"   Test #";t;" of ";n;", line ";dl
 1122 PRINT INVERSE 1;z$;TAB 31;" "
 1124 PRINT INK ch;u$
 1130 IF p THEN LPRINT '"Test #";t;" of ";n;", line ";dl'">";z$'u$
 1140 PRINT AT 0,0;
#.           01234567890123456789012345678901   01234567890123456789012345678901
 1150 INPUT INVERSE 1;"Enter"; INVERSE 0;" to run, "; INVERSE 1;"S"; INVERSE 0;"kip, "; INVERSE 1;"J"; INVERSE 0;"ump, "; INVERSE 1;"Q"; INVERSE 0;"uit, "; INVERSE 1;"M"; INVERSE 0;"anual mode, "; INVERSE 1;"P"; INVERSE 0;"rinter log (";(p);"):"; LINE c$
#.                          01234567890123456789012345678901  01234567890123456789012345678901
 1158 PAPER bg: CLS 
 1160 IF c$="m" THEN PRINT "Manual mode:"'"- GO TO 1200 to resume after"'"- GO TO 1100 to repeat this test"'' INVERSE 1;z$;TAB 31;" "; INVERSE 0; PAPER 4;"Expect"; PAPER bg;":"; INK df;r$: STOP 
 1162 IF c$="q" THEN STOP 
 1164 IF c$="j" THEN INPUT "Test # to skip to (";(t+1);"-";(n);"):";s: LET s=((t+1) AND s=0)+(s AND s>t): GO TO 1000
 1166 IF c$="s" THEN GO TO 1000
 1168 IF c$="p" THEN LET p=NOT p: GO TO 1100
 1170 LET err=0: IF demo THEN PRINT "<output of ";z$;">";TAB 31;" ": GO TO 1200
 1172 ON ERR GO TO 500
 1174 IF l=1 AND a=0 AND b=0 THEN LOAD t$
 1176 IF (l=2 OR l=3) AND a=0 AND b=0 THEN SAVE t$
 1178 IF (l=2 OR l=3) AND (a<>0 OR b<>0) THEN SAVE t$CODE a,b
 1180 IF l=4 THEN OUT a,b
 1182 IF l<>3 THEN GO TO 1196
 1186 LET c=IN 14
 1188 IF c<32 THEN PRINT c
 1190 IF c>=32 THEN PRINT c,CHR$ c
 1192 IF c<>0 THEN GO TO 1186
 1196 ON ERR RESET 
 1200 FOR i=1 TO 100: NEXT i
 1210 IF pk>=0 THEN LET err=PEEK pk: PRINT "PEEK ";pk;" = ";err
 1212 IF p THEN LPRINT "Expect:";r$
 1214 IF P AND err=e THEN LPRINT "OK"
 1216 IF P AND err<>e THEN LPRINT "Wrong report code: ";e$(err+1)
 1220 PAPER cb
 1230 INPUT PAPER 4;"Expect"; PAPER bd;":"; INK df;(r$); INK 2;((" (wrong code:"+e$(err+1)+")") AND err<>e); INK fg;": "; INVERSE 1;"Q"; INVERSE 0;"uit,"; INVERSE 1;"L"; INVERSE 0;"og,"; INVERSE 1;"R"; INVERSE 0;"epeat,"; INVERSE 1;"Enter";"(comment)" AND p; INVERSE 0;":"; LINE c$
 1232 PAPER bg
 1240 IF c$="q" THEN STOP 
 1250 IF c$="l" THEN GO SUB 300
 1260 IF c$="r" THEN GO TO 1100
 1262 IF p AND c$<>"" THEN LPRINT "Note: ";c$
 1270 IF cl=0 THEN GO TO 1400
 1300 LET err=0: ON ERR GO TO 500
 1310 IF NOT demo AND t$<>"tpi:zx48" THEN SAVE "tpi:log clear"CODE 255,0
 1320 ON ERR RESET 
 1330 IF err>0 THEN INPUT '"*** ERROR clearing the log (Enter)";c$
#
 1400 GO TO 1000
#
 1900 REM Test DATA:
 1910 REM 1: Type: 1=LOAD, 2=SAVE, 3=IN, 4=OUT, 0=end of data, negative to skip
 1920 REM 2: tpi:command string
 1930 REM 3: a value for CODE a,b or port for IN/OUT
 1940 REM 4: b value for CODE a,b or byte count for IN (0=repeat until a 0 byte)
 1950 REM 5: Description of command
 1960 REM 6: Description of result
 1970 REM 7: Error code expected: "0".."9","A".."R"
 1999 DATA 88: REM Total number of tests (not critical if this is wrong)
# 1-10
 2000 DATA 2,"tpi:loglevel",0,0,"Show loglevel","LOG level set to the     default","0"
 2010 DATA 2,"tpi:verbose on",0,0,"Turn on verbose mode","Verbose is now enabled","0"
 2020 DATA 2,"tpi:loglevel 0",0,0,"Set loglevel to 0 for testing","LOG level set to 0 INFO","0"
 2030 DATA 2,"tpi:verbose",0,0,"Show verbose mode","Verbose is enabled or    disabled","0"
 2040 DATA 2,"tpi:path",0,0,"Shows the current path","Current path shown","0"
 2050 DATA 2,"tpi:cd /TAP",0,0,"Change to /TAP","cd to /TAP","0"
 2060 DATA 2,"tpi:cd ..",0,0,"Change to /TAP/..","cd to /TAP","0"
 2070 DATA 2,"tpi:cd bazooka",0,0,"Change to non-existent dir","Error F","F"
 2080 DATA 2,"tpi:cd",0,0,"Interactive CD","Change to dir chosen","0"
 2090 DATA 2,"tpi:cd",0,1,"Interactive CD with global paths","Change to dir chosen","0"
#
 2100 DATA 2,"tpi:dir",0,0,"Directory listing","Directories and numbered files with sizes","0"
 2110 DATA 2,"tpi:dir",1,0,"Single file listing","Single file's full name  shown","0"
 2120 DATA 2,"tpi:dir",2,0,"File listing","Numbered files with full names","0"
 2130 DATA 2,"tpi:dir",2,2,"File listing starting starting  at given index","Numbered files listing   starting at 002","0"
 2140 DATA 2,"tpi:info",0,0,"TS-Pico information","Info text","0"
 2150 DATA 2,"tpi:help",0,0,"TS-Pico help summary","A few pages of help","0"
 2160 DATA 2,"tpi:help cd",0,0,"Command/topic help","Help page for ""tpi:cd""","0"
 2170 DATA 2,"tpi:help border",0,0,"Command/topic help","Help page for BORDER","0"
 2180 DATA 2,"tpi:help ?",0,0,"List external help files","List of words","0"
 2190 DATA 2,"tpi:tapdir",0,0,"Mounted tap file directory","See the blocks stored in the tap file with '>' pointing  to the current block, 2.","0"
#
#                           01234567890123456789012345678901           Expect:789012345678901234567890101234567890123456789012345678901
 2200 DATA 2,"tpi:ffw",0,0,"Move the tap read pointer '>'   forward 1 block","Pointer at block 3","0"
 2210 DATA 2,"tpi:ffw",0,1,"Move the tap read pointer '>'   forward 1 block","Pointer at block 4","0"
 2220 DATA 2,"tpi:ffw",2,2,"Move the pointer forward by two files/headers","Pointer at block 8","0"
 2230 DATA 2,"tpi:ffw",3,1,"Move forward by 1 file and show a tapdir","A tapdir listing with    pointer at block 10","0"
 2240 DATA 2,"tpi:tapdir",0,3,"Show tapdir of 3 blocks around  current point","A tapdir of blocks 7 to  13","0"
 2250 DATA 2,"tpi:tapdir",1,2,"Show tapdir of 2 files around   current point","A tapdir of even blocks 6 to 14","0"
 2260 DATA 2,"tpi:ffw",0,999,"Move pointer to last block","Pointer on last block, 27","0"
 2270 DATA 2,"tpi:ffw",0,1,"Move forward one block","Stays on last block with message indicating that.","0"
 2280 DATA 2,"tpi:rew",0,3,"Move tap pointer backward by 3  blocks","Move to block 24","0"
 2290 DATA 2,"tpi:rew",1,1,"Move pointer back by one block  and show tapdir","A tapdir showing pointer on block 23","0"
#
 2300 DATA 2,"tpi:rew",0,999,"Move pointer to block 0","Pointer on block 0","0"
 2310 DATA 2,"tpi:rew",1,1,"Move pointer back 1 file","Stays on block 0","0"
 2320 DATA 2,"tpi:picopt",-1,24027,"Switch printing output to go to the TS-Pico","PEEK 24027=3 (Printing is not implemented yet)","3"
 2330 DATA 2,"tpi:ts2040",-1,24027,"Switch printing output to go to the TS2040 printer","PEEK 24027=2 (This is the default)","2"
 2340 DATA 2,"tpi:tape",-1,24027,"Switch SAVEs to go to the real  audio tape interface","PEEK 24027=0 (saving not being  tested)","0"
 2350 DATA 2,"tpi:sdcard",-1,24027,"Switch SAVE/LOAD to use the SD  card","PEEK 24027=2 (default)","2"
 2360 DATA 2,"tpi:close",0,0,"Unmount current file","Likely this tap file unmounted","0"
 2370 DATA 2,"tpi:append on",0,0,"Turn on append with no tap file mounted","Parameter Error Q","Q"
 2380 DATA 2,"tpi:log",0,0,"Show the log file","A few lines of the log.  (log is cleared after each test)","0"
 2390 DATA 2,"tpi:log",0,40,"Show last bytes of the log file","Show last 40 bytes","0"
#
 2400 DATA 2,"tpi:log clear",0,0,"Clear the log file with a prompt (choose Y)","Log was cleared","0"
 2410 DATA 2,"tpi:log clear",255,0,"Clear the log without a prompt","Log was cleared","0"
 2420 DATA 2,"tpi:cd /",0,0,"Change to 'root'","cd to /TAP","0"
 2430 DATA 2,"tpi:md foo",0,0,"Make dir","create /TAP/foo","0"
 2440 DATA 2,"tpi:md foo",0,0,"Make dir but dir exists","End of File error, 8","8"
 2450 DATA 2,"tpi:rm foo",0,0,"Remove dir with a prompt (choose Y)","removed /TAP/foo","0"
 2460 DATA 2,"tpi:rm foo",255,0,"Remove non-existent dir without a prompt","Invalid filename F","F"
 2470 DATA 2,"tpi:md b*m",0,0,"Make dir with a bad name","Parameter Error Q (OS error)","Q"
 2480 DATA 2,"tpi:md picotest",1,0,"Make test directory & change to it","We can ignore an error if it exists","0"
 2490 DATA 2,"tpi:newtap foo",0,0,"Make a new tap file with append on","File created and mounted","0"
# v--- remove ---v ?
##
# 2500 DATA 2,"tpi:append",0,0,"Show append state","Append is ON","0"
# 2510 DATA 2,"tpi:path",1,0,"Show mounted file","/TAP/picotest/foo.tap","0"
# 2520 DATA 2,"tpi:tapdir",0,0,"Show empty tapdir","Indicates empty","0"
# 2530 DATA 2,"tpi:dir",0,0,"Show new empty .tap file","foo.tap with size 0 b","0"
# 2540 DATA 2,"tpi:info",0,0,"Show info with tap file","foo.tap info shown in    tpi:info","0"
# 2550 DATA 2,"foo1",0,0,"Save program to empty tap","Program foo1 saved to    foo.tap","0"
# 2560 DATA 2,"tpi:tapdir",0,0,"Show foo.tap with foo1 program","Two blocks for program 'foo1'","0"
# 2570 DATA 2,"tpi:dir",0,0,"Show directory","foo.tap with non-zero size","0"
# 2580 DATA 2,"foo2",0,0,"Save but PRESS SPACE to cancel","Program foo2 not saved,  error D","D"
# 2590 DATA 2,"foo2",0,0,"Save again but DO NOT cancel","Program foo2 saved","0"
##
# 2600 DATA 2,"tpi:tapdir",0,0,"Show foo.tap with foo1 and foo2 programs","Four blocks for programs","0"
# 2610 DATA 2,"tpi:dir",0,0,"Show directory","foo.tap has a larger size","0"
# 2620 DATA 2,"tpi:append off",0,0,"Turn off append mode","Append is OFF","0"
# 2630 DATA 2,"foo3",0,0,"Save foo3 as a separate tap file","Saved foo3.tap","0"
# 2640 DATA 2,"tpi:dir",0,0,"Show directory","See foo.tap the same size as before and new smaller foo3.tap","0"
# 2650 DATA 2,"tpi:path",1,0,"Show mounted file","Still foo.tap","0"
# 2660 DATA 2,"tpi:tapdir",1,0,"Show tapdir by file","foo.tap does not include foo3","0"
# 2670 DATA 2,"foo",0,0,"Append=off, SAVE over foo.tap","Program is saved over the mounted tap","0"
# 2680 DATA 2,"tpi:tapdir",0,0,"Show tapdir","See the previous content remains even though foo.tap was overwritten","0"
# 2690 DATA 1,"tpi:foo.tap",0,0,"Mount foo.tap by name","foo.tap is mounted","0"
##
# 2700 DATA 2,"tpi:tapdir",0,0,"Show tapdir of foo.tap","See the new content that overwrote the previous.","0"
# 2710 DATA 1,"tpi:00",0,0,"Mount foo.tap by index","foo.tap mounted","0"
# 2720 DATA 2,"Foo-Bar123",0,0,"Save to a new file","Filename used the allowed characters: digits, alpha, dash and underscore.","0"
# 2730 DATA 2,"foo$bar",0,0,"Save to a new file with invalid characters","File is not saved, error F","F"
# 2740 DATA 2,"tpi:path",1,0,"Show mounted file","Still is foo.tap","0"
# 2750 DATA 2,"tpi:close",0,0,"Unmount current file","foo.tap unmounted","0"
# 2760 DATA 2,"bam",0,0,"Save with no file mounted","bam.tap saved and mounted","0"
# 2770 DATA 2,"tpi:path",1,0,"Show mounted file","bam.tap is mounted","0"
# ^--- remove ---^ ?
 2780 DATA 2,"tpi:newtap bar",0,0,"Make a new tap file with append on","File created","0"
 2790 DATA 2,"tpi:idir",0,0,"Interactive directory. Choose a file to mount.","Mounted the file chosen","0"
#
 2800 DATA 2,"tpi:close",0,0,"Unmount tap file","Unmounted","0"
 2810 DATA 2,"tpi:rm 000",0,0,"Remove file by index (choose N)","Asked to remove file #000","0"
 2820 DATA 2,"tpi:rm 000",0,0,"Remove file by index (choose Y)","Removed file #000","0"
 2840 DATA 2,"tpi:cd ..",2,0,"Change to parent dir and show   new dir path","Change to /TAP and show  the path","0"
 2850 DATA 2,"tpi:cd picotest",1,0,"Change to dir and show tpi:dir","Change to /TAP/picotest  and show dir","0"
 2860 DATA 2,"tpi:cd ..",1,2,"Change to parent dir and show   tpi:dir CODE 2,0","Change to /TAP and show  dir of files only","0"
 2870 DATA 2,"tpi:cd picotest",1,1,"Change to dir and show tpi:idir to pick","Change to /TAP/picotest  and show idir","0"
 2880 DATA 2,"tpi:cd ..",0,0,"Change to parent dir","Change to /TAP","0"
 2890 DATA 2,"tpi:rm picotest",0,0,"Remove non-empty dir with prompt","Error is given only when there is no prompt ","0"
#
 2900 DATA 2,"tpi:cd picotest",0,0,"Change to picotest","Dir is now /TAP/picotest","0"
 2910 DATA 2,"tpi:rm foo.tap",255,0,"Remove file without prompt","File removed","0"
 2920 DATA 2,"tpi:dir",0,0,"Dir of empty folder","Empty directory list","0"
 2930 DATA 2,"tpi:dir",1,0,"Dir of file with empty folder","File index out of range, error 6","6"
 2940 DATA 2,"tpi:dir",2,0,"File dir with empty folder","Error 6","6"
 2950 DATA 2,"tpi:idir",0,0,"Interactive dir with an empty   folder","Directory is empty","0"
 2960 DATA 2,"tpi:cd",0,0,"Interactive cd with empty folder","'..' as the only choice'","0"
 2970 DATA 2,"tpi:cd ..",0,0,"Change to parent dir","Change to /TAP","0"
 2980 DATA 2,"tpi:rm picotest",0,0,"Remove empty dir (choose Y)","Removed","0"
 2990 DATA 2,"tpi:dock",1,2,"Set the dock setting","Set to MEM=1, PAGE=2","0"
#
 3000 DATA 2,"tpi:dock",0,1,"Show the dock previous setting","Likely MEM=2, PAGE=0","0"
 3010 DATA 2,"tpi:dock",0,2,"Swap to previous dock setting","Likely MEM=2, PAGE=0","0"
 3020 DATA 2,"tpi:boot",0,0,"Show the boot setting","Likely MEM=2, PAGE=1","0"
 3030 DATA 2,"tpi:dock",0,0,"Show the dock setting","Likely MEM=2, PAGE=0","0"
 3040 DATA 2,"tpi:zx48",0,0,"Set TS-Pico for Spectrum mode","TS-Pico stops responding until OUT 10,100","0"
 3050 DATA 4,"out",10,100,"Re-enable TS-Pico from Spectrum mode","TS-Pico should respond to tpi: commands again","0"
 3060 DATA 2,"tpi:rompatch",0,0,"Mount rompatch.tap for patching the ROM","Should tell you to do a  LOAD """"","0"
 3070 DATA 2,"tpi:cd pico",0,0,"Change to /TAP/pico folder","To get to test files","0"
 3080 DATA 1,"tpi:test.dck",0,0,"Mount a .dck file","test.dck mounted (LOADing not tested here)","0"
 3090 DATA 1,"tpi:test.rom",0,0,"Mount a .rom file","test.rom mounted (LOADing not tested here)","0"
#
 3100 DATA 1,"tpi:test.bin",0,0,"Mount a .bin file","test.bin mounted (LOADing not tested here)","0"
 3110 DATA 3,"tpi:.rndw",0,0,"External command .rndw","Command output read with IN 14: the characters of a word","0"
 3130 DATA 2,"tpi:verbose off",0,0,"Set verbose off","No message, but verbose  is off (for next test)","0"
 3140 DATA 2,"tpi:nop",0,0,"No operation","No output, just a return code 0","0"
 3150 DATA 2,"tpi:close",0,0,"Unmount current file","Unmounted file to prepare for last test","0"
 3160 DATA 1,"",0,0,"Do LOAD """" to load the No File! program (this program will end)","Chained to the No File!  program","0"
#
 7990 DATA 0
 9999 LET demo=1: GO TO 7
#
# Things NOT tested:
#
# * External help files
#     - Any missing pico or BASIC commands, typos, or incorrect info
#     - Any command syntaxes incorrect or missing. 
#
# * Values set in config.ini have desired effect
#
# * External commands (examples require special .tap files)
#
# * LOAD "" with a .dck file mounted will load a utility to save it to a memory
#   slot for use. 
#     - Test that .dck files mount
#     - Test the use of this utility
#     - Test that pressing "D" at boot bypasses the dock cartridge loading.
#     - Test various DCK files. Some are non-standard and may not work or work
#       with the "D" key. Some are Spectrum programs that only work with Spectrum
#       joysticks. 
# * LOAD "" with a .rom or .bin file mounted will load a similar utility to save 
#   it to a memory slot for use.
#     - Test that the .rom or .bin files mount
#     - Test the use of this utility
#     - Test various file. Some may not be meant to work with a TS2068.
# * LOAD "tpi:name"
#     - Should allow many characters for the name (up to 27?) before needing to
#       use an index load.
# * "tpi:boot"
#     - CODE 1,n - Set to SRAM slot n
#     - CODE 2,n - Set to Flash slot n
#     - "tpi:memboot" is still aliased to "tpi:boot"
# * "tpi:upgrade"
# * "tpi:zx48" - Prepare the pico for ZX Spectrum mode. Prints instructions.
#     - CODE *,1 - Force the normal tape loader routine
#     - CODE *,2 - Force the compatible tape loader routine
#     - CODE *,n - With n >= 16384 to set compatible loader with buffer size n.
#     - CODE 1,* - Don't show the instruction text.
#     - You can mount a .tap file to save/load with before switching.
#     - The ROM used should be the current DOCK slot setting (2,0 by default).
#     - Test switching back
#     - It is recommended to use the TS-reset button on the TS-Pico after the "OUT
#       244,x" commands rather than issuing a "NEW" command.
# * External commands
