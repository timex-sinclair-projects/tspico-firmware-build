#! zmakebas -a 10 -n chtest4
   10 REM OPEN # channels test 4 (stage 3): d: directory listings
   20 CLS : OPEN #4,"d:*.tap": INPUT #4;TAB 0;n: PRINT n;" .tap files here:"
   30 FOR i=1 TO n: INPUT #4;a$: PRINT i;" ";a$: NEXT i
   40 CLOSE #4
   50 OPEN #4,"d:": INPUT #4;TAB 0;n: LET d=0
   60 FOR i=1 TO n: INPUT #4;a$: LET d=d+(a$(LEN a$)="/"): NEXT i
   70 CLOSE #4
   80 PRINT '"All: ";d;" dirs, ";n-d;" files"'"  (CAT shows the same)"
   90 PRINT '"Next, an empty match should stop"'"with 8 End of file."'"Then type CLOSE #5"
  100 OPEN #5,"d:*.zzz": INPUT #5;a$
  110 PRINT "FAIL: no end of file"
