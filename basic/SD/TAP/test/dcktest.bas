#! zmakebas -n dcktest -a 10
#! append ../../../assets/dckupdate_code.tap
# The #372 check (tools/memcheck.py --dck runs it): dckupdate.bas's SRAM
# path, round after round, on a heap that has just listed the card's biggest
# folders. Each round: MOVE TO the 300-tape MEMDIR and the biggest folder,
# back to /TAP, mount memdck64.dck (a 64K DOCK image), measure, select SRAM
# slot 8, SAVE "tpi:blkrcv", the two 32K write loops, then tpi:close at once
# -- the command that came back J in #372 -- tried up to five times a second
# apart, the tries in the tag ("closed_t0": the first one answered). Then
# the DOCK goes back to what it was. SRAM only: no flash is written, and
# slot 8 is lost at power off.
#
# The firmware's telemetry (TELEMETRY in config.ini) says how each 32K piece
# went: "BLKRCV streamed by DMA" with why=0 and every byte sent is the fast
# path. memcheck.py --dck counts those lines per round.
#
# It needs in /TAP (memcheck.py puts them there): memcfg.tap (memtest.bas's:
# board, rounds, the biggest folder), memdck64.dck and the folder MEMDIR.
# The write loops are dckupdate's own (dckupdate_code.tap, after this
# program on the tape), with the flash commands POKEd out as dckupdate.bas
# does for SRAM.
#
# Each step: LET n (the line after it), ON ERR GO TO 9000, the command, then
# the measurement. A trapped report is measured too, as "err<code>_at<n>".
   10 CLEAR 32599: LET r=3: LET b$="": LET s$="r0_": LET t$="": LET sl=8: LET j=0
   20 LET n=30: ON ERR GO TO 9000: LOAD ""CODE 32600
   30 LET n=40: ON ERR GO TO 9000: LOAD "tpi:memcfg.tap": LOAD ""CODE 60000: LET r=PEEK 60001: FOR i=1 TO PEEK 60002: LET b$=b$+CHR$ PEEK (60002+i): NEXT i
# dckupdate.bas lines 240-270: the write loops without the flash commands
   40 ON ERR RESET : FOR i=32685 TO 32699: POKE i,0: NEXT i: FOR i=32885 TO 32899: POKE i,0: NEXT i
   45 CLS : PRINT "TS-Pico DCK stream test, ";r;" rounds"'"Writes SRAM slot ";sl;". No keys needed.": LET t$="start map": GO SUB 8000
   50 FOR k=1 TO r
   60 LET s$="r"+STR$ k+"_"
   70 LET n=80: ON ERR GO TO 9000: MOVE TO "/memdir": IF b$<>"" THEN MOVE TO b$
   80 LET n=90: ON ERR GO TO 9000: MOVE TO "/": LOAD "tpi:memdck64.dck": LET t$=s$+"mounted": GO SUB 8000
   90 LET n=100: ON ERR GO TO 9000: SAVE "tpi:memdock"CODE 1,sl
  100 LET n=150: ON ERR GO TO 9000: SAVE "tpi:blkrcv"
# dckupdate.bas lines 400-450: the same PRINTs between the loops, so the
# Pico has the same BASIC time to read the second piece
  110 ON ERR RESET : PRINT "Round ";k;": lower...";: RANDOMIZE USR 32870: PRINT "OK"
  115 PRINT "         upper...";: RANDOMIZE USR 32670: PRINT "OK"
# tpi:close straight after the loops (dckupdate.bas asks a question first)
  120 LET tr=0
  122 ON ERR GO TO 130
  124 SAVE "tpi:close": ON ERR RESET : GO TO 140
  130 ON ERR RESET : IF PEEK 23739<>19 THEN LET n=140: GO TO 9000
  132 LET tr=tr+1: LET j=j+1: IF tr<5 THEN PAUSE 50: GO TO 122
  140 LET t$=s$+"closed_t"+STR$ tr: GO SUB 8000
  150 LET n=160: ON ERR GO TO 9000: SAVE "tpi:memdock"CODE 0,2
  160 NEXT k
  170 ON ERR RESET
  180 LET t$="end map": GO SUB 8000
  190 PRINT '; PAPER 4; INK 0;" DCK TEST DONE: J retries ";j;" ": STOP
# Measure: no "scroll?" between the messages, then tpi:meminfo with the tag.
 8000 POKE 23692,255: SAVE "tpi:meminfo "+t$: RETURN
# A report was trapped: measure it under its own tag, go on at n.
 9000 ON ERR RESET : LET t$=s$+"err"+STR$ (PEEK 23739)+"_at"+STR$ n: GO SUB 8000: GO TO n
