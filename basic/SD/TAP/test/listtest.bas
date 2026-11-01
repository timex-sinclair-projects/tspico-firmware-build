#! zmakebas -n listtest -a 10
# LIST "file" on the TS-Pico (PR #349). It makes four files in the current
# folder, LISTs each one, and asks you whether the screen looked as it says;
# then it checks LIST's refusals by their reports, with no keys to press, and
# erases what it made.
#
# A step you see: s (its number), then GO SUB 8000 shows what to expect and
# waits for a key, the step runs, GO SUB 8100 asks y/n.
# A step it checks itself: as in disktest (x the report it should give, n the
# line after it, ON ERR GO TO 9000), GO SUB 8200 prints and counts it.
   10 CLEAR : LET e$="0123456789ABCDEFGHIJKLMNOPQR": LET p=0: LET f=0: LET f$=""
   20 CLS : PRINT INVERSE 1;" TS-Pico LIST test              "
   30 PRINT '"It makes four files here: lt1.txt"'"lt2.txt, lt3.dat and lt4.dat,"'"LISTs each and asks what you"'"saw. Then it erases them."
   40 PRINT '"Making the files...": GO SUB 7000
# lt1.txt: four lines, written in binary ("wb") with line feeds, so the bytes
# are as given: on the 2068 CHR$ 123 to 126 are keywords (ON ERR, STICK,
# SOUND, FREE), and text mode would write the words. In the file they are
# { | } ~, which LIST shows as ?, and CHR$ 9 is a TAB, shown as two spaces.
   50 LET l$=CHR$ 10: OPEN #4,"f:lt1.txt","wb": PRINT #4;"Hello from the TS-Pico";l$;"Line two";l$;"Odd ones: ";CHR$ 123;CHR$ 124;CHR$ 125;CHR$ 126;l$;"A";CHR$ 9;"TAB";l$;: CLOSE #4
# lt2.txt: 250 lines, more than the 8192 bytes LIST shows
   60 OPEN #4,"f:lt2.txt","w": FOR i=1 TO 250: PRINT #4;"Line ";i;" of 250, the quick brown fox": NEXT i: CLOSE #4
# lt3.dat: bytes 0 to 255 but 23 (PRINT # can't write it): 255 bytes, a hex dump
   70 OPEN #4,"f:lt3.dat","wb": FOR i=0 TO 255
   72 IF i<>23 THEN PRINT #4;CHR$ i;
   74 NEXT i: CLOSE #4
# lt4.dat: a 0, then ABC..Z over and over: 3001 bytes, more than the 2048 it dumps
   80 LET a$="": FOR i=0 TO 99: LET a$=a$+CHR$ (65+i-26*INT (i/26)): NEXT i
   82 OPEN #4,"f:lt4.dat","wb": PRINT #4;CHR$ 0;: FOR i=1 TO 30: PRINT #4;a$;: NEXT i: CLOSE #4
# ─── What you see ───
  100 LET s=1: GO SUB 8000: PRINT "LIST ""lt1.txt"": four lines:"''"Hello from the TS-Pico"'"Line two"'"Odd ones: ????"'"A  TAB"''"(two spaces in the last one)": GO SUB 8050: LIST "lt1.txt": GO SUB 8100
  200 LET s=2: GO SUB 8000: PRINT "LIST ""lt2.txt"": a long file."''"Lines ""Line 1 of 250, the quick"'"brown fox"" on, and Scroll? (Y/n)"'"at each screen. Press Y to the"'"end: the last line is cut short"'"at ""Line 225 of"", then"'"(the first 8192 of 9142 bytes)": GO SUB 8050: LIST "lt2.txt": GO SUB 8100
  300 LET s=3: GO SUB 8000: PRINT "LIST ""lt3.dat"": a hex dump, 8"'"bytes a row. The first rows:"''"0000 0001020304050607 ........"'"0008 08090A0B0C0D0E0F ........"'"0010 1011121314151618 ........"''"and the last:"''"00F8 F9FAFBFCFDFEFF   ......."''"with no ""(the first ..."" line.": GO SUB 8050: LIST "lt3.dat": GO SUB 8100
  400 LET s=4: GO SUB 8000: PRINT "LIST ""lt4.dat"": a longer dump."'"The first row:"''"0000 0041424344454647 .ABCDEFG"''"Press Y to the end: the last"'"row is"''"07F8 4E4F505152535455 NOPQRSTU"''"then (the first 2048 of 3001"'"bytes)": GO SUB 8050: LIST "lt4.dat": GO SUB 8100
  500 LET s=5: GO SUB 8000: PRINT "SAVE ""tpi:list lt1.txt"": the"'"command form. The same four"'"lines as step 1.": GO SUB 8050: SAVE "tpi:list lt1.txt": GO SUB 8100
  600 LET s=6: GO SUB 8000: PRINT "LIST z$, with z$=""lt1.txt"": the"'"same four lines again.": GO SUB 8050: LET z$="lt1.txt": LIST z$: GO SUB 8100
  700 LET s=7: GO SUB 8000: PRINT "LIST 9990: the program's own"'"line 9990, as LIST always did:"''"9990>REM LIST 9990 shows this"''"(> marks the current line)": GO SUB 8050: LIST 9990: GO SUB 8100
# ─── What it checks itself ───
  800 CLS : PRINT INVERSE 1;" Refusals                       "'"No";TAB 3;"Test";TAB 24;"E G"
  810 LET t=8: LET d$="LIST missing": LET x=15: LET n=820: ON ERR GO TO 9000: LIST "nosuch.txt": LET g=0: GO SUB 8200
  820 LET t=9: LET d$="LIST ""*.txt""": LET x=26: LET n=830: ON ERR GO TO 9000: LIST "*.txt": LET g=0: GO SUB 8200
  830 LET t=10: LET d$="LIST ""lt?.dat""": LET x=26: LET n=840: ON ERR GO TO 9000: LIST "lt?.dat": LET g=0: GO SUB 8200
  840 LET t=11: LET d$="LIST a folder": LET x=26: LET n=850: ON ERR GO TO 9000: FORMAT "ltdir/": LIST "ltdir": LET g=0: GO SUB 8200
  850 LET t=12: LET d$="LIST (""lt1.txt"")": LET x=12: LET n=860: ON ERR GO TO 9000: LIST ("lt1.txt"): LET g=0: GO SUB 8200
  860 LET t=13: LET d$="tpi:list, no name": LET x=26: LET n=900: ON ERR GO TO 9000: SAVE "tpi:list": LET g=0: GO SUB 8200
# ─── Tidy up, then the summary ───
  900 GO SUB 7000
  930 POKE 23692,255: PRINT '"Passed ";p-f;" of ";p
  940 IF f THEN PRINT "Failed: ";f$
  950 IF NOT f THEN PRINT "All passed."
  960 STOP
# Tidy up: erase what it made; any report (not there) is ignored.
 7000 RESTORE 9900
 7010 READ k$: IF k$="*" THEN ON ERR RESET : RETURN
 7020 ON ERR GO TO 7010: ERASE k$: GO TO 7010
# A step you see: clear the screen and title it; then wait for a key.
 8000 CLS : PRINT INVERSE 1;" Step ";s;" of 7 ";TAB 31;" ": PRINT : RETURN
 8050 PRINT '"Press a key to run it.": PAUSE 0: CLS : RETURN
 8100 INPUT "Did it look right? (y/n) ";a$: LET p=p+1
 8110 IF a$<>"y" AND a$<>"Y" THEN LET f=f+1: LET f$=f$+STR$ s+" "
 8120 RETURN
# A step it checks: print and count it, as disktest does.
 8200 ON ERR RESET : LET p=p+1: LET k=(g=x)
 8210 IF NOT k THEN LET f=f+1: LET f$=f$+STR$ t+" "
 8220 POKE 23692,255: PRINT t;TAB 3;d$;TAB 24;e$(x+1);" ";e$(g+1);TAB 28;("ok" AND k);("FAIL" AND NOT k)
 8230 RETURN
 9000 LET g=PEEK 23739: ON ERR RESET : GO SUB 8200: GO TO n
 9900 DATA "lt1.txt","lt2.txt","lt3.dat","lt4.dat","ltdir/","*"
 9990 REM LIST 9990 shows this
