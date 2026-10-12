#! zmakebas -n modemtst
# The v3 card's TS2050 modem (docs/v3-modem-proposal.md), in Hayes mode: a
# tiny terminal through the 8251 at ports 115 (73h, data) and 119 (77h,
# status/command). Line 20 resets the 8251 as MTERM does (three 0s, 64 =
# internal reset), mode 79 (4Fh: x64, 8 bits, no parity, 1 stop) and
# command 55 (37h: TxEN, DTR, RxE, ER, RTS). Type AT and ENTER (CAPS LOCK
# on): Zimodem echoes it and answers OK.
10 REM TS2050 8251 test terminal
20 FOR i=1 TO 3: OUT 119,0: NEXT i: OUT 119,64: OUT 119,79: OUT 119,55
30 PRINT "Status ";IN 119;" (133 = ready)"
40 LET k$=INKEY$: IF k$="" THEN GO TO 70
50 OUT 115,CODE k$
60 IF INKEY$<>"" THEN GO TO 60
70 LET s=IN 119: IF INT (s/2)-2*INT (s/4)=0 THEN GO TO 40
80 LET c=IN 115: IF c=13 THEN PRINT
90 IF c>31 AND c<128 THEN PRINT CHR$ c;
100 GO TO 40
