#! zmakebas -n labeltst -a 10
# The SD card's label on the TS-Pico (PR #349): SAVE "tpi:label" and
# FORMAT ":name". It writes the card's label, so use a card you have backed
# up. It asks for the label the card has now and puts it back at the end.
#
# Besides showing and setting it, it checks the two things a label change
# could break, because the firmware unmounts the card to write it: a file
# open for writing across the change, and a mounted TAP loaded after one.
#
# A step you see: GO SUB 8000 (title), the step, GO SUB 8100 (y/n).
# A step it checks itself: x the report it should give, w$ a value it should
# read (or ""), n the line after it, ON ERR GO TO 9000; GO SUB 8200 counts it.
   10 CLEAR 59999: LET e$="0123456789ABCDEFGHIJKLMNOPQR": LET p=0: LET f=0: LET f$="": LET v$="": LET w$=""
   20 CLS : PRINT INVERSE 1;" TS-Pico label test             "
   30 PRINT '"This writes the SD card's label,"'"the name a PC or Mac shows for"'"it. Use a card you have backed"'"up. At the end it puts back the"'"label the card has now."
   40 PRINT '"It makes lbtest.txt and"'"lbtest.tap here, and erases them."
   50 INPUT "Go on? (y/n) ";a$: IF a$<>"y" AND a$<>"Y" THEN STOP
# ─── 1: the label now ───
  100 LET s=1: GO SUB 8000: PRINT "SAVE ""tpi:label"" shows it:"'"Label: NAME, or No label."': SAVE "tpi:label"
  110 PRINT : INPUT "The label it showed (ENTER if"'"No label): ";LINE o$
# ─── 2: set it, with a file open for writing across the change ───
  200 CLS : PRINT INVERSE 1;" Checks                         "'"No";TAB 3;"Test";TAB 24;"E G"
  210 LET t=2: LET d$="open lbtest.txt": LET x=0: LET n=220: ON ERR GO TO 9000: OPEN #5,"f:lbtest.txt","w": PRINT #5;"before": LET g=0: GO SUB 8200
  220 LET t=3: LET d$="label PICOTEST": LET x=0: LET n=230: ON ERR GO TO 9000: SAVE "tpi:label PICOTEST": LET g=0: GO SUB 8200
  230 LET t=4: LET d$="write, CLOSE": LET x=0: LET n=240: ON ERR GO TO 9000: PRINT #5;"after": CLOSE #5: LET g=0: GO SUB 8200
  240 LET t=5: LET d$="read it back": LET x=0: LET w$="before/after": LET n=250: ON ERR GO TO 9000: OPEN #4,"f:lbtest.txt": INPUT #4;a$: INPUT #4;b$: CLOSE #4: LET v$=a$+"/"+b$: LET g=0: GO SUB 8200
# Names it refuses: 12 characters, a dot, a star
  250 LET t=6: LET d$="12 characters": LET x=26: LET n=260: ON ERR GO TO 9000: SAVE "tpi:label ABCDEFGHIJKL": LET g=0: GO SUB 8200
  260 LET t=7: LET d$="FORMAT "":A.B""": LET x=26: LET n=270: ON ERR GO TO 9000: FORMAT ":A.B": LET g=0: GO SUB 8200
  270 LET t=8: LET d$="tpi:label A*B": LET x=26: LET n=300: ON ERR GO TO 9000: SAVE "tpi:label A*B": LET g=0: GO SUB 8200
  300 PRINT '"Press a key.": PAUSE 0
  310 LET s=9: GO SUB 8000: PRINT "SAVE ""tpi:label"" should show"'"Label: PICOTEST"': SAVE "tpi:label": GO SUB 8100
# ─── 3: CAT shows it ───
  400 LET s=10: GO SUB 8000: PRINT "CAT: the second line of the"'"listing starts PICOTEST: and"'"then the card's size. Press N"'"at Scroll? if it asks.": GO SUB 8050: CAT : GO SUB 8100
# ─── 4: FORMAT ":name" sets it too, in upper case ───
  500 LET s=11: GO SUB 8000: PRINT "FORMAT "":games 2"", then"'"SAVE ""tpi:label"" should show"'"Label: GAMES 2"'
  510 LET t=12: LET d$="FORMAT "":games 2""": LET x=0: LET n=520: ON ERR GO TO 9000: FORMAT ":games 2": LET g=0: GO SUB 8200
  520 PRINT : SAVE "tpi:label": GO SUB 8100
# ─── 5: a mounted TAP still loads after a change ───
  600 LET s=13: GO SUB 8000: PRINT "A new TAP, lbtest.tap, and 64"'"bytes saved into it."'"When it says Start tape, press"'"ENTER.": GO SUB 8050
  610 LET t=14: LET d$="FORMAT lbtest.tap": LET x=0: LET n=620: ON ERR GO TO 9000: FORMAT "lbtest.tap": LET g=0: GO SUB 8200
# 64 bytes of RAM, 0 to 63 * 3 (not the ROM: SAVE runs with the TS-Pico's
# EXROM paged in, so CODE 0,64 isn't what PEEK reads)
  615 FOR i=0 TO 63: POKE 61000+i,i*3: NEXT i
  620 LET t=15: LET d$="SAVE CODE 61000,64": LET x=0: LET n=630: ON ERR GO TO 9000: SAVE "lbcode"CODE 61000,64: LET g=0: GO SUB 8200
  630 LET t=16: LET d$="mount it": LET x=0: LET n=640: ON ERR GO TO 9000: LOAD "tpi:lbtest.tap": LET g=0: GO SUB 8200
  640 LET t=17: LET d$="label PICO 3": LET x=0: LET n=650: ON ERR GO TO 9000: FORMAT ":PICO 3": LET g=0: GO SUB 8200
  650 LET t=18: LET d$="LOAD it": LET x=0: LET w$="64": LET n=700: ON ERR GO TO 9000: LOAD ""CODE 60000: LET q=0: FOR i=0 TO 63: LET q=q+(PEEK (60000+i)=i*3): NEXT i: LET v$=STR$ q: LET g=0: GO SUB 8200
# ─── 6: take it off ───
  700 PRINT '"Press a key.": PAUSE 0
  710 LET s=19: GO SUB 8000: PRINT "FORMAT "":"", then"'"SAVE ""tpi:label"" should show"'"No label"'
  712 LET t=20: LET d$="FORMAT "":""": LET x=0: LET n=714: ON ERR GO TO 9000: FORMAT ":": LET g=0: GO SUB 8200
  714 PRINT : SAVE "tpi:label": GO SUB 8100
  720 LET s=21: GO SUB 8000: PRINT "CAT: the second line starts"'"SD: now. Press N at Scroll? if"'"it asks.": GO SUB 8050: CAT : GO SUB 8100
  730 CLS : LET t=22: LET d$="tpi:label - again": LET x=0: LET n=800: ON ERR GO TO 9000: SAVE "tpi:label -": LET g=0: GO SUB 8200
# ─── 7: tidy up, and put the card's own label back ───
  800 ON ERR GO TO 810: SAVE "tpi:close"
  810 ON ERR GO TO 820: ERASE "lbtest.txt"
  820 ON ERR GO TO 830: ERASE "lbtest.tap"
  830 ON ERR RESET : LET s=23: GO SUB 8000: PRINT "Your label back. It should show"'("Label: "+o$ AND o$<>"");("No label" AND o$=""): PRINT
  832 IF o$="" THEN GO TO 840
  834 LET t=24: LET d$="put it back": LET x=0: LET n=840: ON ERR GO TO 9000: FORMAT ":"+o$: LET g=0: GO SUB 8200
  840 PRINT : SAVE "tpi:label": GO SUB 8100
# ─── Summary ───
  900 CLS : PRINT "Passed ";p-f;" of ";p
  910 IF f THEN PRINT "Failed: ";f$
  920 IF NOT f THEN PRINT "All passed."
  930 PRINT '"Now put the card in a PC or Mac."'"It should open as usual and show"'"the label you started with. Run"'"a disk check on it too (Disk"'"Utility's First Aid on a Mac,"'"chkdsk on a PC)."
  940 STOP
# A step you see: clear the screen and title it.
 8000 CLS : PRINT INVERSE 1;" Step ";s;" ";TAB 31;" ": PRINT : RETURN
 8050 PRINT '"Press a key to run it.": PAUSE 0: CLS : RETURN
 8100 INPUT "Did it look right? (y/n) ";a$: LET p=p+1
 8110 IF a$<>"y" AND a$<>"Y" THEN LET f=f+1: LET f$=f$+STR$ s+" "
 8120 RETURN
# A step it checks: print and count it.
 8200 ON ERR RESET : LET p=p+1: LET k=(g=x) AND (w$="" OR v$=w$)
 8210 IF NOT k THEN LET f=f+1: LET f$=f$+STR$ t+" "
 8220 POKE 23692,255: PRINT t;TAB 3;d$;TAB 24;e$(x+1);" ";e$(g+1);TAB 28;("ok" AND k);("FAIL" AND NOT k)
 8230 IF NOT k AND w$<>"" THEN POKE 23692,255: PRINT TAB 3;"read """;v$;""""
 8240 LET v$="": LET w$="": RETURN
# A report was trapped: close stream 4, count it, go on.
 9000 LET g=PEEK 23739: ON ERR RESET : CLOSE #4: GO SUB 8200: GO TO n
