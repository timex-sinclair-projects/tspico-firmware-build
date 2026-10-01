#! zmakebas -n hdrless -a 1
# TS-Pico test: a HEADERLESS LOAD with TADDR >= 10.
#
# Audit 2026-09-30, section 2 item 11. Fixed on branch batch-b-protocol; this
# program is the hardware check that branch is waiting on.
#
# Why machine code is needed at all: the pre-header's TADDR byte is the low
# byte of the stock T-ADDR sysvar (5C74h), which the ROM reads straight out of
# it (docs/rom-analysis/PROTOCOL_FROM_ROM.md). A BASIC LOAD always leaves
# TADDR 1-3 -- the path the dispatcher already handled. Only a direct call to
# the EXROM's LD_BYTES entry can present TADDR >= 10, which is the headerless
# case in the pre-header table in docs/PROTOCOL.md section 4.
#
# The bug: the dispatcher skipped its early READY only when pre[1] < 10, so a
# headerless LOAD still got it. The Z80 could then read an empty TX as 00,
# which is Report R -- the documented symptom after a BREAK.
#
# The 26-byte stub in line 1, assembled with z80asm and checked with z80dasm
# against the ROM 2.1 image:
#
#   3E 14        LD   A,20          ; any TADDR >= 10
#   32 74 5C     LD   (5C74h),A     ; T-ADDR low -> pre-header byte 1
#   DD 21 nn nn  LD   IX,dest       ; operand POKEd at mc+7, mc+8
#   11 nn nn     LD   DE,len        ; operand POKEd at mc+10, mc+11
#   3E FF        LD   A,0FFh        ; flag FFh = data block, no header
#   37           SCF                ; carry set = LOAD (clear = VERIFY)
#   CD FC 00     CALL 00FCh         ; EXROM LD_BYTES, verified as JP 196Dh
#   01 00 00     LD   BC,0          ; USR result: 0 = carry clear
#   30 01        JR   NC,+1
#   0C           INC  C             ;              1 = carry set = loaded
#   FB           EI                 ; LD_BYTES runs DI
#   C9           RET
#
# EXROM 00FCh is gated on TPMODE (5DDBh) bit 1, which SAVE "tpi:sdcard" sets
# and which is the state at switch-on.
#
# PASS: USR returns 1 and the destination holds the block's bytes.
# FAIL: USR returns 0 -- LD_BYTES gave carry clear, which is what the ROM
#       turns into Report R.
#
    1 REM \{0x3E}\{0x14}\{0x32}\{0x74}\{0x5C}\{0xDD}\{0x21}\{0x00}\{0x00}\{0x11}\
\{0x00}\{0x00}\{0x3E}\{0xFF}\{0x37}\{0xCD}\{0xFC}\{0x00}\{0x01}\{0x00}\
\{0x00}\{0x30}\{0x01}\{0x0C}\{0xFB}\{0xC9}
    2 REM Headerless LOAD TADDR>=10
   10 LET prog=PEEK 23635+256*PEEK 23636: LET mc=prog+5
   12 LET dest=60000: LET bl=0: LET er=0: LET r=-1
   14 LET e$="0123456789ABCDEFGHIJKLMNOPQR"
   20 BORDER 7: PAPER 7: INK 0: BRIGHT 0: FLASH 0: INVERSE 0: OVER 0: CLS 
   22 PRINT INVERSE 1;"Headerless LOAD, TADDR>=10";TAB 31;" "
   24 PRINT "audit 2026-09-30 item 11"'"stub at ";mc;", 26 bytes"
   26 PRINT ''"Needs a .tap mounted that has"'"a data block in it."
   30 PRINT ''"Enter: point LOAD/SAVE at the"'"TS-Pico (tpi:sdcard)"
   32 INPUT c$
   34 LET er=0: ON ERR GO TO 900
   36 SAVE "tpi:sdcard"
   38 ON ERR RESET 
   40 CLS : PRINT "Mount a file by name, or"'"Enter to keep the mounted one:"
   42 INPUT LINE f$
   44 IF f$="" THEN GO TO 60
   46 LET er=0: ON ERR GO TO 900
   48 LOAD "tpi:"+f$
   50 ON ERR RESET 
# Position the read pointer: a headerless LOAD serves the block at '>'.
   60 CLS : LET er=0: ON ERR GO TO 900
   62 SAVE "tpi:tapdir"
   64 ON ERR RESET 
   66 PRINT ''"'>' is the block that will be"'"read."
   68 PRINT INVERSE 1;"F";: PRINT INVERSE 0;"wd  ";: PRINT INVERSE 1;"R";: PRINT INVERSE 0;"ew  ";: PRINT INVERSE 1;"Enter";: PRINT INVERSE 0;" to use it:"
   70 INPUT LINE c$
   72 IF c$="f" OR c$="F" THEN LET er=0: ON ERR GO TO 900: SAVE "tpi:ffw"
   74 IF c$="f" OR c$="F" THEN ON ERR RESET : GO TO 60
   76 IF c$="r" OR c$="R" THEN LET er=0: ON ERR GO TO 900: SAVE "tpi:rew"
   78 IF c$="r" OR c$="R" THEN ON ERR RESET : GO TO 60
# tapdir's Len counts flag + data + checksum; LD_BYTES wants the data count.
   80 CLS : PRINT "That block's tapdir Len"'"(flag+data+checksum):"
   82 INPUT bl
   84 IF bl<3 THEN PRINT "Too small for a block.": GO TO 80
   86 LET bl=bl-2: PRINT ''"So ";bl;" data bytes."
   90 PRINT ''"Load them to which address?"'"Enter for ";dest;":"
   92 INPUT LINE c$
   94 LET er=0: ON ERR GO TO 900
   96 IF c$<>"" THEN LET dest=VAL c$
   98 ON ERR RESET 
  100 IF dest<24576 OR dest+bl>65535 THEN PRINT "Pick 24576..";65535-bl: GO TO 90
# The early READY showed as Report R on the command AFTER a BREAK, so offer
# to get a BREAK in first.
  110 CLS : PRINT "The bug showed up on the"'"command after a BREAK."
  112 PRINT ''"Do a LOAD and BREAK out of it"'"first? y, or Enter to skip:"
  114 INPUT LINE c$
  116 IF c$<>"y" AND c$<>"Y" THEN GO TO 130
  118 PRINT ''"Press BREAK (SPACE) during"'"this LOAD."
  120 LET er=0: ON ERR GO TO 900
  122 LOAD ""
  124 ON ERR RESET 
  126 PRINT ''"That LOAD reported ";e$(er+1)
  128 INPUT "Enter to go on:";LINE c$
# Poke the two operands into the stub and call it.
  130 POKE mc+7,dest-256*INT (dest/256): POKE mc+8,INT (dest/256)
  132 POKE mc+10,bl-256*INT (bl/256): POKE mc+11,INT (bl/256)
  140 CLS : PRINT "CALL 00FCh: TADDR 20, flag"'"FFh, ";bl;" bytes to ";dest
  142 PRINT ''"Running..."
  144 LET er=0: ON ERR GO TO 900
  146 LET r=USR mc
  148 ON ERR RESET 
  150 PRINT ''"USR returned ";r
  152 IF er>0 THEN PRINT "Trapped report ";e$(er+1)
  160 IF r=1 THEN PRINT ''"PASS: the block loaded."
  162 IF r<>1 THEN PRINT ''"FAIL: carry clear from"'"LD_BYTES -- what the ROM"'"turns into Report R."
  170 PRINT ''"First bytes at ";dest;":"
  172 FOR i=0 TO 7: PRINT PEEK (dest+i);" ";: NEXT i
  180 PRINT ''''"Now check the Pico still"'"answers, with:"
  182 PRINT '"  SAVE ""tpi:nop"""
  190 STOP 
# Error trap: the picotest idiom -- record the report, resume after the line
# that raised it (GO TO a missing line lands on the next one).
  900 LET er=PEEK 23739
  910 GO TO PEEK 23736+256*PEEK 23737+1
