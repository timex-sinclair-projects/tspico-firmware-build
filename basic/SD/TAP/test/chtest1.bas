#! zmakebas -a 10 -n chtest1
   10 REM OPEN # channels test 1: write a text file, read it back, end of file
   20 CLS : PRINT "Writing chtest.txt"
   30 OPEN #4,"f:chtest.txt","w"
   40 PRINT #4;"Hello"
   50 PRINT #4;"two";2*3
   60 FOR i=1 TO 30: PRINT #4;"line ";i: NEXT i
   70 CLOSE #4
   80 PRINT "Reading it back"
   90 OPEN #4,"f:chtest.txt"
  100 INPUT #4;a$: INPUT #4;b$
  110 PRINT a$;"/";b$;"  (want Hello/two6)"
  120 LET n=0
  130 FOR i=1 TO 30: INPUT #4;c$: IF c$="line "+STR$ i THEN LET n=n+1
  140 NEXT i
  150 PRINT n;" of 30 lines right  (want 30)"
  160 PRINT "The next INPUT # should stop"'"with 8 End of file."'"Then type CLOSE #4"
  170 INPUT #4;d$
  180 PRINT "FAIL: no end of file, got ";d$
  190 CLOSE #4
