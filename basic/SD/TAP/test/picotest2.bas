#! zmakebas -n tspicotst2 -a 1
# TS-Pico BASIC Tester
    4 DEF FN S$(l,t$,a,b)=("LOAD " AND l=1)+("SAVE " AND l=2)+""""+t$+""""+(("CODE "+STR$ a+","+STR$ b) AND (a OR b))
    7 LET e$="0123456789ABCDEFGHIJKLMNOPQR"
   10 LET l=0: LET t$="": LET a=0: LET b=0
   20 LET fg=9: LET bg=7: LET bd=5
   22 LET wb=2: LET wf=9: LET df=1
   24 LET ch=1: LET cb=bd
   26 LET t=0: LET s=0: LET cl=1
   30 BORDER bd: PAPER bd: INK fg: BRIGHT 0: FLASH 0: INVERSE 0: OVER 0
   44 CLS 
   52 PRINT " TS-Pico ";TAB 16;" TS-Pico Tester "
   70 PRINT #0; INK df;"    \* 2025 TS-Pico DevTeam      ";
   80 PRINT #0;"This tests some TS-Pico commandsfor saving with user assistance.";
#               01234567890123456789012345678901
   90 PRINT #0''"Press a key to start...";
   92 LET c$=INKEY$: IF c$="" THEN GO TO 92
   98 GO TO 900
  300 CLS 
  302 PRINT "Test #";t;" of ";n;", line ";dl'">";z$'u$
  306 PRINT "Expect:";r$'"Log:"
  310 LET err=0: ON ERR GO TO 500
  320 SAVE "tpi:log"
  330 ON ERR RESET 
  340 IF err>0 THEN PRINT '"*** ERROR in tpi:log": STOP 
  360 INPUT "Press Enter:";c$: RETURN 
  370 RETURN 
  500 LET err=PEEK 23739
  510 LET erl=PEEK 23736+256*PEEK 23737
  520 PRINT 'PAPER 2;"*** ERROR: ";e$(err+1);" ***";TAB 31;" "
  530 IF err=19 THEN PRINT '"*** TS-Pico communication error"
  540 IF err=9 OR err=17 OR err=19 THEN ON ERR RESET : STOP 
  550 GO TO erl+1
#
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
 1140 PRINT AT 0,0;
#.           01234567890123456789012345678901   01234567890123456789012345678901
 1150 INPUT INVERSE 1;"Enter"; INVERSE 0;" to run, "; INVERSE 1;"S"; INVERSE 0;"kip, "; INVERSE 1;"J"; INVERSE 0;"ump, "; INVERSE 1;"Q"; INVERSE 0;"uit, "; INVERSE 1;"M"; INVERSE 0;"anual mode:"; LINE c$
#.                          01234567890123456789012345678901  01234567890123456789012345678901
 1158 PAPER bg: CLS 
 1160 IF c$="m" THEN PRINT "Manual mode:"'"- GO TO 1200 to resume after"'"- GO TO 1100 to repeat this test"'' INVERSE 1;z$;TAB 31;" "; INVERSE 0; PAPER 4;"Expect"; PAPER bg;":"; INK df;r$: STOP 
 1162 IF c$="q" THEN STOP 
 1164 IF c$="j" THEN INPUT "Test # to skip to (";(t+1);"-";(n);"):";s: LET s=((t+1) AND s=0)+(s AND s>t): GO TO 1000
 1166 IF c$="s" THEN GO TO 1000
 1170 LET err=0
 1172 ON ERR GO TO 500
 1174 IF l=1 AND a=0 AND b=0 THEN LOAD t$
 1176 IF l=2 AND a=0 AND b=0 THEN SAVE t$
 1178 IF l=2 AND (a<>0 OR b<>0) THEN SAVE t$CODE a,b
 1196 ON ERR RESET 
 1198 IF l>2 THEN PRINT "Types 1 and 2 only": STOP 
 1200 FOR i=1 TO 100: NEXT i
 1220 PAPER cb
 1230 INPUT PAPER 4;"Expect"; PAPER bd;":"; INK df;(r$); INK 2;((" (wrong code:"+e$(err+1)+")") AND err<>e); INK fg;": "; INVERSE 1;"Q"; INVERSE 0;"uit,"; INVERSE 1;"L"; INVERSE 0;"og,"; INVERSE 1;"R"; INVERSE 0;"epeat,"; INVERSE 1;"Enter"; INVERSE 0;":"; LINE c$
 1232 PAPER bg
 1240 IF c$="q" THEN STOP 
 1250 IF c$="l" THEN GO SUB 300
 1260 IF c$="r" THEN GO TO 1100
 1300 LET err=0: ON ERR GO TO 500
 1310 SAVE "tpi:log clear"CODE 255,0
 1320 ON ERR RESET 
 1330 IF err>0 THEN INPUT '"*** ERROR clearing the log (Enter)";c$
#
 1400 GO TO 1000
#
 1999 DATA 43
# 1-10
 2010 DATA 2,"tpi:verbose on",0,0,"Turn on verbose mode","Verbose is now enabled","0"
 2020 DATA 2,"tpi:loglevel 0",0,0,"Set loglevel to 0 for testing","LOG level set to 0 INFO","0"
 2050 DATA 2,"tpi:cd /TAP",0,0,"Change to /TAP","cd to /TAP","0"
#
 2480 DATA 2,"tpi:md picotest",1,0,"Make test directory & change to it","We can ignore an error if it exists","0"
 2490 DATA 2,"tpi:newtap foo",0,0,"Make a new tap file with append on","File created","0"
#
 2500 DATA 2,"tpi:append",0,0,"Show append state","Append is ON","0"
 2510 DATA 2,"tpi:path",1,0,"Show mounted file","/TAP/picotest/foo.tap","0"
 2520 DATA 2,"tpi:tapdir",0,0,"Show empty tapdir","Indicates empty","0"
 2530 DATA 2,"tpi:dir",0,0,"Show new empty .tap file","foo.tap with size 0 b","0"
 2540 DATA 2,"tpi:info",0,0,"Show info with tap file","foo.tap info shown in    tpi:info","0"
 2550 DATA 2,"foo1",0,0,"Save program to empty tap","Program foo1 saved to    foo.tap","0"
 2560 DATA 2,"tpi:tapdir",0,0,"Show foo.tap with foo1 program","Two blocks for program   'foo1'","0"
 2570 DATA 2,"tpi:dir",0,0,"Show directory","foo.tap shown with non-  zero size","0"
 2580 DATA 2,"foo2",0,0,"Save but PRESS SPACE to cancel","Program foo2 not saved,  error D","D"
 2590 DATA 2,"foo2",0,0,"Save again but DO NOT cancel","Program foo2 saved","0"
#
 2600 DATA 2,"tpi:tapdir",0,0,"Show foo.tap with foo1 and foo2 programs","Four blocks for programs","0"
 2610 DATA 2,"tpi:dir",0,0,"Show directory","foo.tap has a larger size","0"
 2620 DATA 2,"tpi:append off",0,0,"Turn off append mode","Append is OFF","0"
 2630 DATA 2,"foo3",0,0,"Save foo3 as a separate tap file","Saved foo3.tap","0"
#                                     Expect:789012345678901234567890101234567890123456789012345678901
 2640 DATA 2,"tpi:dir",0,0,"Show directory","See foo.tap the same size as before with the new smaller foo3.tap","0"
 2650 DATA 2,"tpi:path",1,0,"Show mounted file","Still foo.tap","0"
 2660 DATA 2,"tpi:tapdir",1,0,"Show tapdir by file","foo.tap does not include foo3","0"
 2670 DATA 2,"foo",0,0,"Append=off, SAVE over foo.tap","Program is saved over the mounted tap","0"
 2680 DATA 2,"tpi:tapdir",0,0,"Show tapdir","See the previous content remains even though foo.tap was overwritten","0"
 2690 DATA 1,"tpi:foo.tap",0,0,"Mount foo.tap by name","foo.tap is re-mounted","0"
#
 2700 DATA 2,"tpi:tapdir",0,0,"Show tapdir of foo.tap","See the new content that overwrote the previous.","0"
 2710 DATA 1,"tpi:00",0,0,"Mount foo.tap by index","foo.tap mounted","0"
 2720 DATA 2,"Foo-Bar123",0,0,"Save to a new file","Filename used the allowed characters: digits, alpha, dash and underscore.","0"
 2730 DATA 2,"foo$bar",0,0,"Save to a new file with invalid characters","File is not saved, error F","F"
 2740 DATA 2,"tpi:path",1,0,"Show mounted file","Still is foo.tap","0"
 2750 DATA 2,"tpi:close",0,0,"Unmount current file","foo.tap unmounted","0"
 2760 DATA 2,"bam",0,0,"Save with no file mounted","bam.tap saved and mounted","0"
 2770 DATA 2,"tpi:path",1,0,"Show mounted file","bam.tap is mounted","0"
 2780 DATA 2,"tpi:dir",0,0,"Show files created","Should be: bam, foo, foo3 and Foo-Bar123","0"
#
 2910 DATA 2,"tpi:rm foo.tap",255,0,"Remove foo.tap","foo.tap removed","0"
 2920 DATA 2,"tpi:rm foo3.tap",255,0,"Remove foo3.tap","foo3.tap removed","0"
 2930 DATA 2,"tpi:rm bam.tap",255,0,"Remove bam.tap","bam.tap removed","0"
 2940 DATA 2,"tpi:rm Foo-Bar123.tap",255,0,"Remove Foo-Bar123.tap","Foo-Bar123.tap removed","0"
 2970 DATA 2,"tpi:cd ..",0,0,"Change to parent dir","Change to /TAP","0"
 2980 DATA 2,"tpi:rm picotest",0,0,"Remove empty dir (choose Y)","Removed","0"
#
 7990 DATA 0
