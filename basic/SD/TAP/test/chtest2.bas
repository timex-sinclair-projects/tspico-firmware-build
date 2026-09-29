#! zmakebas -a 10 -n chtest2
   10 REM OPEN # channels test 2: two streams, append, INKEY$ #, OPEN #2, LIST #
   20 CLS : OPEN #5,"f:cha.txt","w": OPEN #6,"f:chb.txt","w"
   30 PRINT #5;"to a": PRINT #6;"to b"
   40 CLOSE #5
   50 PRINT #6;"b after closing 5"
   60 CLOSE #6
   70 OPEN #5,"f:cha.txt","a": PRINT #5;"appended": CLOSE #5
   80 OPEN #5,"f:cha.txt": INPUT #5;x$: INPUT #5;y$: CLOSE #5
   90 PRINT "cha.txt: ";x$;" / ";y$'"  (want to a / appended)"
  100 OPEN #6,"f:chb.txt": INPUT #6;x$: INPUT #6;y$: CLOSE #6
  110 PRINT "chb.txt: ";x$;" / ";y$'"  (want to b / b after closing 5)"
  120 OPEN #6,"f:chb.txt": LET k$=INKEY$ #6+INKEY$ #6+INKEY$ #6+INKEY$ #6: CLOSE #6
  130 PRINT "INKEY$ #6 x4: ";k$;"  (want to b)"
  140 OPEN #2,"f:chscr.txt","w": PRINT "this line goes to the file": CLOSE #2
  150 PRINT "screen is back"
  160 OPEN #7,"f:chlist.txt","w": LIST #7: CLOSE #7
  170 OPEN #7,"f:chlist.txt": INPUT #7;l$: CLOSE #7
  180 PRINT "listing starts:"'l$
  190 OPEN #7,"f:chscr.txt": INPUT #7;l$: CLOSE #7
  200 PRINT "chscr.txt: ";l$
  210 PRINT '"Done. CAT ""ch*"" should show"'"cha, chb, chlist, chscr .txt"
