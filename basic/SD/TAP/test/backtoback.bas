#! zmakebas -n "backtoback" -a 10
# Hardware check for the 2026-09-30 audit, §4 "RX drains and flushes": 50
# tpi: commands as fast as BASIC can send them. Each next command's SYNC
# can arrive while the Pico is still in the last one's tail; before the
# tail armed the pre-header's DMA channel ahead of IDLE, the header could
# overflow the 4-deep FIFO ("Partial pre-header 4/10") and the program
# stopped with Report T. It should end with "50 commands OK".
   10 REM TS-Pico back-to-back tpi: commands
   20 CLS
   30 FOR i=1 TO 50
   40 SAVE "tpi:path"
   50 NEXT i
   60 PRINT "50 commands OK"
