#! zmakebas -n hwtest -a 10
# The TS-Pico hardware check's automatic half (tools/hwcheck.py runs it):
# about 20 tests the 2068 can run with nobody at the keyboard. Each records
# three bytes at 61000 on: the test number, the report it ended with (PEEK
# 23739, ERRT: 0 for OK, 15 for F; docs/rom-analysis/ERROR_TRAPPING.md) and a
# value it read. The last SAVE writes them as hwres.tap; hwcheck.py fetches
# it off the card and checks each against what that board should give.
#
# It needs, in the current folder (hwcheck.py puts them there): hwcfg.tap, one
# byte saying which board (1: the v3 card). v3-only tests are skipped on v2:
# booting an empty slot, for one, would hang a v2.
#
# No tape SAVE, LOAD or VERIFY here (tests 4-9 and 12 once were): they ask
# for a key, and a SAVE after the round trip rebooted the v3 card's 2068
# (2026-10-10, not yet understood; each worked typed by hand).
# src/test/sd_roundtrip.py covers them, and the ZX48 step in hwcheck.py.
#
# Each test: LET t (its number), n (the line after it), ON ERR GO TO 9000,
# then the command. A trapped report goes to 9000, which records it and goes
# on at n.
   10 CLEAR 32767: LET p=61000: LET b=0
   20 LET t=1: LET n=40: LET v=0: ON ERR GO TO 9000: LOAD "tpi:hwcfg.tap": LOAD ""CODE 60000: LET b=PEEK 60000: LET v=b: GO SUB 8000
   40 LET t=2: LET n=50: LET v=0: ON ERR GO TO 9000: SAVE "tpi:info": GO SUB 8000
   50 LET t=3: LET n=120: ON ERR GO TO 9000: SAVE "tpi:dir": GO SUB 8000
  120 LET t=10: LET n=130: ON ERR GO TO 9000: SAVE "tpi:md hwdir": GO SUB 8000
  130 LET t=11: LET n=150: ON ERR GO TO 9000: SAVE "tpi:cd hwdir": GO SUB 8000
  150 LET t=13: LET n=160: ON ERR GO TO 9000: SAVE "tpi:cd ..": GO SUB 8000
  160 LET t=14: LET n=170: ON ERR GO TO 9000: SAVE "tpi:picopt": GO SUB 8000
  170 LET t=15: LET n=180: ON ERR GO TO 9000: LPRINT "hwtest 1234": GO SUB 8000
  180 LET t=16: LET n=190: ON ERR GO TO 9000: SAVE "tpi:clprint": GO SUB 8000
  190 LET t=17: LET n=200: ON ERR GO TO 9000: SAVE "tpi:ts2040": GO SUB 8000
# Mounting a tape that isn't there: an error on purpose.
  200 LET t=18: LET n=210: ON ERR GO TO 9000: LOAD "tpi:nosuch.tap": GO SUB 8000
# The dock, read at 32770 (chunk 4): 115 Flight Simulator (slot 10), 40 Crazy
# Bugs (12), 17 the default dock (slot 0, ROM 2.3 in its upper half).
  210 LET t=19: LET n=220: ON ERR GO TO 9000: SAVE "tpi:dock"CODE 2,10: OUT 244,16: LET v=PEEK 32770: OUT 244,0: GO SUB 8000
  220 LET t=20: LET n=230: ON ERR GO TO 9000: SAVE "tpi:dock"CODE 2,12: OUT 244,16: LET v=PEEK 32770: OUT 244,0: GO SUB 8000
  230 IF b<>1 THEN GO TO 280
# v3 only: a flash dock ignores writes; a RAM dock keeps them across a switch.
  240 LET t=21: LET n=250: ON ERR GO TO 9000: OUT 244,16: POKE 32770,99: LET v=PEEK 32770: OUT 244,0: GO SUB 8000
  250 LET t=22: LET n=260: ON ERR GO TO 9000: SAVE "tpi:dock"CODE 1,4: OUT 244,16: POKE 32770,99: LET v=PEEK 32770: OUT 244,0: GO SUB 8000
  260 LET t=23: LET n=270: ON ERR GO TO 9000: SAVE "tpi:dock"CODE 2,0: SAVE "tpi:dock"CODE 1,4: OUT 244,16: LET v=PEEK 32770: OUT 244,0: GO SUB 8000
# v3 only: booting an empty slot is refused (F). On v2 it would hang. RAM
# slot 9: the RAM slots are cleared at every boot and nothing here writes 9.
# (Not a flash slot: one the user filled -- 7 holds a cartridge's upper half
# on some cards -- would be booted, and crash the 2068.)
  270 LET t=25: LET n=280: LET v=0: ON ERR GO TO 9000: SAVE "tpi:boot"CODE 1,9: GO SUB 8000
  280 LET t=24: LET n=300: ON ERR GO TO 9000: SAVE "tpi:dock"CODE 2,0: OUT 244,16: LET v=PEEK 32770: OUT 244,0: GO SUB 8000
# No plain SAVE "tpi:boot" here: on the v3 card it resets the 2068 at once,
# before line 310 saves the results. hwcheck.py asks for it by hand.
  300 ON ERR RESET
  310 SAVE "hwres"CODE 61000,p-61000
  320 CLS : PRINT AT 10,0; PAPER 4; INK 0;"   HWTEST DONE: ";(p-61000)/3;" tests   "''"Back to the computer: hwcheck.py"'"reads the results off the card."
  330 STOP
# Record a test: number, report, value.
 8000 POKE p,t: POKE p+1,0: POKE p+2,v-256*INT (v/256): LET p=p+3: RETURN
# A report was trapped: record it, go on with the next test.
 9000 POKE p,t: POKE p+1,PEEK 23739: POKE p+2,v-256*INT (v/256): LET p=p+3: GO TO n
