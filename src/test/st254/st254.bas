#! zmakebas -n st254 -a 10
# The issue-#254 stress test's loader: the machine code (st254.asm) follows
# this program on st254.tap. RUN 100 starts the read loop.
   10 CLEAR 59999: LOAD ""CODE
   20 PRINT "st254 loaded."''"Tell Claude, then type RUN 100"
   30 STOP
  100 PRINT "Reading port 15..."
  110 PRINT "bad reads: ";USR 60000
  120 STOP
