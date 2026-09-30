#! zmakebas -a 10 -n chtest3
   10 REM OPEN # channels test 3 (stage 2): records, TAB, update mode
   20 CLS : OPEN #4,"f:chrec.dat","w",20: CLOSE #4
   30 OPEN #4,"f:chrec.dat","u",20
   40 PRINT #4;TAB 3;"third"
   50 PRINT #4;TAB 1;"first"
   60 PRINT #4;TAB 2;"sec";: PRINT #4;"ond"
   70 INPUT #4;TAB 0;n: PRINT "records: ";n;"  (want 3)"
   80 INPUT #4;TAB 2;a$: PRINT "[";a$;"]"'"  (want second + 14 spaces)"
   90 FOR i=3 TO 1 STEP -1: INPUT #4;TAB i;a$: PRINT i;": ";a$( TO 6): NEXT i
  100 PRINT "  (want third, second, first)"
  110 PRINT #4;TAB 2;"SECOND"
  120 INPUT #4;TAB 2;a$: PRINT "rewritten: ";a$( TO 6);"  (want SECOND)"
  130 PRINT #4;TAB 6;"sixth"
  140 INPUT #4;TAB 0;n: PRINT "records: ";n;"  (want 6)"
  150 INPUT #4;TAB 5;a$: PRINT "record 5: [";a$( TO 5);"]"'"  (want 5 spaces)"
  160 INPUT #4;TAB 6;a$: PRINT "record 6: ";a$( TO 5);"  (want sixth)"
  170 PRINT '"Next, a 21-character record"'"should stop with Q Parameter"'"error. Then type CLOSE #4"
  180 PRINT #4;TAB 1;"123456789012345678901"
  190 PRINT "FAIL: no Q"
