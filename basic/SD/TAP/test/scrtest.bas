#! zmakebas -a 10 -n scrtest
   10 REM SCR_CT after TS-Pico commands (#455). Any board, card in.
   20 BORDER 7: PAPER 7: INK 0: CLS : DIM s(5): LET f=0
   30 PRINT "SCR_CT test (#455)"''"Press a key at any ""press a key"""'"and answer y to any Replace?"''"Press a key to start": PAUSE 0
   40 CLS : POKE 23692,1: PRINT "";: LET s(1)=PEEK 23692
   50 CLS : POKE 23692,1: CAT : LET s(2)=PEEK 23692
   60 CLS : POKE 23692,1: SAVE "tpi:info": LET s(3)=PEEK 23692
   70 CLS : POKE 23692,1: SAVE "tpi:path": LET s(4)=PEEK 23692
   80 CLS : SAVE "f:scrtest.scr"SCREEN$
   90 CLS : PRINT "Answer y to Replace?": POKE 23692,1: SAVE "f:scrtest.scr"SCREEN$: LET s(5)=PEEK 23692
  100 CLS : PRINT "SCR_CT after each command"'"(255: scroll? is off)"'
  110 RESTORE 150: FOR i=1 TO 5: READ a$: PRINT a$;TAB 16;s(i);
  120 IF s(i)=255 THEN PRINT TAB 22;"FAIL": LET f=f+1: GO TO 140
  130 PRINT TAB 22;"ok"
  140 NEXT i
  150 DATA "PRINT """"","CAT","tpi:info","tpi:path","Replace?"
  160 PRINT '"Failed: ";f
  170 PRINT '"Next, 40 lines after tpi:path."'"scroll? should stop them when"'"the screen fills."''"Press a key": PAUSE 0
  180 CLS : POKE 23692,1: SAVE "tpi:path": FOR i=1 TO 40: PRINT "after tpi:path, line ";i: NEXT i
  190 PRINT "Did scroll? stop it? Press a key": PAUSE 0
  200 CLS : POKE 23692,1: PRINT "";: FOR i=1 TO 40: PRINT "after PRINT """", line ";i: NEXT i
  210 PRINT '"Done"
