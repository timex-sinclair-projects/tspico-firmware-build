#! zmakebas -n bustest -a 10
# The bus-integrity test's loader and report (bustest.asm; the cartridge from
# make_dck.py must be in the dock). RUN 100: normal display; RUN 200: ECM
# (DECR 2), as Sinistar. Each run is 16 x 65536 iterations, a minute or two.
   10 CLEAR 45055: LOAD ""CODE
   20 PRINT "bustest loaded."''"Dock the test cartridge, then"'"RUN 100 (normal) or RUN 200 (ECM)"
   30 STOP
  100 POKE 48142,0: GO TO 300
  200 POKE 48142,2
  300 POKE 48143,16
  310 PRINT "Testing..."
  320 LET e=USR 45568
  330 CLS : PRINT "bustest, DECR ";PEEK 48142
  340 PRINT "iterations: ";PEEK 48130+256*PEEK 48131+65536*PEEK 48132
  350 PRINT "interrupts: ";PEEK 48140+256*PEEK 48141
  360 PRINT "errors: ";e
  370 FOR t=1 TO 7: LET a=48144+2*t: PRINT " type ";t;": ";PEEK a+256*PEEK (a+1): NEXT t
  380 PRINT "1 rd 2 jp 3 ISRd 4 ISRr 5 LDIR"'"6 stack 7 RAM"
  390 LET n=PEEK 48144: IF n>12 THEN LET n=12
  400 IF n=0 THEN STOP
  410 PRINT "t hsr addr exp got iter"
  420 FOR i=0 TO n-1: LET a=48640+8*i
  430 PRINT PEEK a;" ";PEEK (a+1);" ";PEEK (a+2)+256*PEEK (a+3);" ";PEEK (a+4);" ";PEEK (a+5);" ";PEEK (a+6)+256*PEEK (a+7)
  440 NEXT i
  450 STOP
