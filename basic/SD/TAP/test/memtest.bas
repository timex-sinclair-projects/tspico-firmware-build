#! zmakebas -n memtest -a 10
# The heap measurement for #384 (tools/memcheck.py runs it): the same
# commands, round after round, with SAVE "tpi:meminfo <tag>" after each, so
# the Pico's free memory and largest free block can be followed step by step.
# The Pico prints one MEM line per step on its USB console; memcheck.py
# collects them. "map" in a tag adds the heap map (start, round 1's first
# folder, end).
#
# It needs in /TAP (memcheck.py puts them there): memcfg.tap (a CODE block at
# 60000: board, 1 for the v3 card; rounds; the length of a folder path, then
# the path: the card's biggest folder), memtape.tap (a 35000-byte CODE block,
# then 30 small ones), memdock.dck (an 8K dock image) and the folder MEMDIR
# (300 small tapes). The SAVE asks for a key every round: press ENTER.
#
# Each step: LET n (the line after it), ON ERR GO TO 9000, the command, then
# the measurement. A trapped report is measured too, as "err<code>_at<n>",
# and the program goes on at n. RAMTOP 29999: the 35000-byte block goes at
# 30000, above the program.
   10 CLEAR 29999: LET r=3: LET v=0: LET b$="": LET s$="r0_": LET t$=""
   20 LET n=40: ON ERR GO TO 9000: LOAD "tpi:memcfg.tap": LOAD ""CODE 60000: LET v=PEEK 60000: LET r=PEEK 60001: FOR i=1 TO PEEK 60002: LET b$=b$+CHR$ PEEK (60002+i): NEXT i
   40 ON ERR RESET: CLS : PRINT "TS-Pico memory test, ";r;" rounds"'"Press ENTER at each Start tape."'': LET t$="start map": GO SUB 8000
   50 FOR k=1 TO r
   60 LET s$="r"+STR$ k+"_"
   70 LET n=80: ON ERR GO TO 9000: MOVE TO "/memdir": LET t$=s$+"memdir"+(" map" AND k=1): GO SUB 8000
   80 LET n=90: IF b$="" THEN GO TO 90
   85 ON ERR GO TO 9000: MOVE TO b$: LET t$=s$+"bigdir": GO SUB 8000
   90 LET n=100: ON ERR GO TO 9000: MOVE TO "/": LET t$=s$+"root": GO SUB 8000
  100 LET n=110: ON ERR GO TO 9000: LOAD "tpi:memtape.tap": LET t$=s$+"mount": GO SUB 8000
  110 LET n=120: ON ERR GO TO 9000: LOAD ""CODE 30000: LET t$=s$+"load": GO SUB 8000
  120 LET n=130: ON ERR GO TO 9000: SAVE "memsave"CODE 30000,35000: LET t$=s$+"save": GO SUB 8000
  130 LET n=140: ON ERR GO TO 9000: LOAD "tpi:memdock.dck": LET t$=s$+"dck": GO SUB 8000
  140 LET n=150: ON ERR GO TO 9000: SAVE "tpi:close": LET t$=s$+"close": GO SUB 8000
  150 IF v<>1 THEN GO TO 170
  160 LET n=170: ON ERR GO TO 9000: SAVE "tpi:say memory test": LET t$=s$+"say": GO SUB 8000
  170 NEXT k
  180 ON ERR RESET
  190 LET t$="end map": GO SUB 8000
  200 PRINT '; PAPER 4; INK 0;"   MEMTEST DONE: back to memcheck   ": STOP
# Measure: no "scroll?" between the messages, then tpi:meminfo with the tag.
 8000 POKE 23692,255: SAVE "tpi:meminfo "+t$: RETURN
# A report was trapped: measure it under its own tag, go on at n.
 9000 ON ERR RESET: LET t$=s$+"err"+STR$ (PEEK 23739)+"_at"+STR$ n: GO SUB 8000: GO TO n
