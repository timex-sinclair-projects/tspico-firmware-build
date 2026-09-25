#! zmakebas -n picotest-s -a 1
#
# picotest-s - TS-Pico SAVE test suite.
#
# Builds to "SD card/TAP/picotest-s.tap" = /TAP/picotest-s.tap on the card.
# Companion to picotest.tap; the "-s" is for SAVE.
#
# HOW IT WORKS
#   Every case is driven through ON ERR GO TO, so a failing SAVE is trapped
#   instead of stopping the program. The handler reads ERRT (PEEK 23739),
#   which the HOME ROM sets to the report INDEX -- 0 for "0 OK", 10 for
#   "A Invalid argument", 15 for "F Invalid file name", 27 for "R Tape
#   loading error". See docs/rom-analysis/ERROR_TRAPPING.md for where that
#   comes from; note SD card/help/onerr.txt used to name the wrong sysvar.
#
#   Tests dispatch by computed GO TO, never GO SUB: an error trap jumps out
#   of the block, so a GO SUB return address would be stranded on the stack
#   and every trapped test would leak one.
#
#   Expected value -1 means "observe, do not judge". No case uses it now --
#   the two that did were settled from the ROM (see below) -- but the
#   mechanism is kept for adding cases whose answer is not yet known.
#
# TWO CASES NEVER REACH THE PICO
#   SAVE "" and SAVE with a name over 10 characters are both rejected by the
#   EXROM's filename evaluator at $021A, before any pre-header is built, and
#   both give Report F. The length test is one comparison: an empty name
#   wraps BC to $FFFF and lands in the same branch as an over-long one. The
#   rejection is guarded on T-ADDR = 0, so LOAD tolerates both (empty means
#   "match anything", over-long is truncated to 10). See
#   docs/rom-analysis/ERROR_TRAPPING.md.
#
# WHAT IT WRITES
#   Successful cases create files named zz* in the current TS-Pico
#   directory. Remove them afterwards with SAVE "tpi:rm zzs1" etc.
#
# THE LAST TEST IS SEPARATE ON PURPOSE
#   SAVE ... CODE addr,0 makes the Z80 put 65536 bytes on the bus (the ZX
#   "SAVE 0 = SAVE 64K" quirk: SA-BYTES decrements DE after the send, so 0
#   wraps to 0xFFFF). Firmware with the empty-save guard refuses it with
#   Report A; firmware without it jams. So it runs only if you say yes.

  1 rem picotest-s : TS-Pico SAVE tests
 10 border 1: paper 1: ink 7: bright 0: cls
 20 print "TS-Pico SAVE test suite"
 30 print "======================="
 40 print
 50 print "Traps each SAVE with ON ERR and"
 60 print "reads ERRT (peek 23739)."
 70 print
 80 print "report 0=ok  A=10  C=12  F=15"
 90 print
100 print "Writes files named zz* here."
110 print "Remove later with tpi:rm"
120 print
130 print "any key to start"
140 if inkey$="" then go to 140
150 cls

200 let n=18
210 let t=0: let p=0: let q=0
220 dim z(4): dim y$(2,4)

300 rem next test
310 let t=t+1
320 if t>n then go to 600
330 let a=0: let e=0: let d$=""
340 on err go to 500
350 go to 1000+t*20

400 rem record the outcome
410 if e=-1 then print "obs  ";d$;" = ";a: let p=p+1: go to 300
420 if a=e then print "ok   ";d$: let p=p+1: go to 300
430 print flash 1;"FAIL";flash 0;" ";d$
440 print "     want ";e;" got ";a
450 let q=q+1
460 go to 300

500 rem error trap
510 let a=peek 23739
520 go to 400

600 rem summary
610 on err reset
620 print
630 print "passed ";p;"  failed ";q
640 print
650 if q=0 then print "all checks matched"
660 print
670 print "Last test floods 64K if the"
680 print "empty-save guard is missing."
690 print "Run it? (y/n)"
700 let k$=inkey$: if k$="" then go to 700
710 if k$<>"y" and k$<>"Y" then go to 900
720 cls
730 let d$="code addr,0 - 64K flood": let e=10
740 let a=0
750 on err go to 800
760 save "zzzero" code 32768,0
770 go to 810
800 let a=peek 23739
810 on err reset
820 if a=e then print "ok   ";d$: go to 900
830 print flash 1;"FAIL";flash 0;" ";d$
840 print "     want ";e;" got ";a

900 rem manual checks
910 print
920 print "Not covered here - do by hand:"
930 print " NEW then SAVE ""x"" (empty pgm)"
940 print " tpi:append on, then SAVE"
950 print " ZX48 mode SAVE"
960 print
970 print "Delete the zz* files when done."
980 stop

1020 let d$="space in name": let e=15
1024 let s$="bad file"
1028 save s$
1032 go to 400

1040 let d$="dot in name": let e=15
1044 let s$="a.tap"
1048 save s$
1052 go to 400

1060 let d$="slash in name": let e=15
1064 let s$="a/b"
1068 save s$
1072 go to 400

1080 let d$="star in name": let e=15
1084 let s$="a*b"
1088 save s$
1092 go to 400

1100 let d$="byte >127 in name": let e=15
1104 let s$="a\{160}b"
1108 save s$
1112 go to 400

1120 let d$="control byte in name": let e=15
1124 let s$="a"+chr$ 13+"b"
1128 save s$
1132 go to 400

1140 let d$="plain program save": let e=0
1144 let s$="zzs1"
1148 save s$
1152 go to 400

1160 let d$="10 char name": let e=0
1164 let s$="zzs2345678"
1168 save s$
1172 go to 400

1180 let d$="dash and underscore": let e=0
1184 let s$="zz-s_3"
1188 save s$
1192 go to 400

1200 let d$="empty name (ROM rejects)": let e=15
1204 let s$=""
1208 save s$
1212 go to 400

1220 let d$="name padded with spaces": let e=0
1224 let s$="  zzs4  "
1228 save s$
1232 go to 400

1240 let d$="save LINE (autostart)": let e=0
1244 let s$="zzline"
1248 save s$ line 1
1252 go to 400

1260 let d$="save CODE": let e=0
1264 let s$="zzcode"
1268 save s$ code 32768,64
1272 go to 400

1280 let d$="save DATA numeric": let e=0
1284 let s$="zznum"
1288 save s$ data z()
1292 go to 400

1300 let d$="save DATA character": let e=0
1304 let s$="zzchr"
1308 save s$ data y$()
1312 go to 400

1320 let d$="overwrite existing": let e=0
1324 let s$="zzs1"
1328 save s$
1332 go to 400

1340 let d$="name over 10 (ROM rejects)": let e=15
1344 let s$="abcdefghijkl"
1348 save s$
1352 go to 400

1360 let d$="tpi unknown command": let e=12
1364 let s$="tpi:nosuchcmd"
1368 save s$
1372 go to 400
