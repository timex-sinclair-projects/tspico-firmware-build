#! zmakebas -a 10 -n speechtst
# The v3 card's speech (docs/v3-speech-proposal.md, user manual Appendix G):
# a menu of tests. 1-3 and 5-6 use tpi:say; 4 drives ports 17 and 37 as a
# program for the Pico Speech Synth 2068 board does (OUT 17 an allophone,
# IN 37 bit 7 busy), and counts the IN 37 polls that read busy.
10 REM TS-Pico speech test
20 CLS: PRINT "TS-Pico v3 speech test": PRINT
30 PRINT "1 Sentences (tpi:say)": PRINT "2 Say what you type": PRINT "3 Allophones [HH1 EH ...]": PRINT "4 Ports 17 and 37": PRINT "5 Stop mid-sentence": PRINT "6 A command while it talks": PRINT "0 Quit"
40 PRINT: PRINT "Choose: ";
50 LET k$=INKEY$: IF k$<"0" OR k$>"6" THEN GO TO 50
60 PRINT k$: IF k$="0" THEN STOP
70 GO SUB 100*VAL k$+100
80 PRINT: PRINT "Press a key for the menu": PAUSE 0: GO TO 20
200 REM 1: three sentences, queued one after another
210 SAVE "tpi:say HELLO. I AM YOUR TIMEX SINCLAIR 2068."
220 SAVE "tpi:say PRESS ANY KEY TO CONTINUE."
230 SAVE "tpi:say WARNING! INTRUDER ALERT. INTRUDER ALERT."
240 PRINT "Three sentences queued:": PRINT "the 2068 is free meanwhile."
250 RETURN
300 REM 2: say what you type (ENTER alone ends)
310 INPUT "Say: ";a$: IF a$="" THEN RETURN
320 PRINT a$: SAVE "tpi:say "+a$: GO TO 310
400 REM 3: allophones by name
410 PRINT "HELLO WORLD, by allophones"
420 SAVE "tpi:say [HH1 EH LL OW PA4 WW ER1 LL DD1 PA5]"
430 RETURN
500 REM 4: ports 17 and 37, as the speech board's programs
510 LET b=0: RESTORE 590
520 FOR i=1 TO 10: READ a
530 IF IN 37>=128 THEN LET b=b+1: GO TO 530
540 OUT 17,a: NEXT i
550 PRINT "Said HELLO WORLD by OUT 17"
560 PRINT "IN 37 read busy ";b;" times"
570 PRINT "IN 37 now: ";IN 37;" (255 busy, 127 ready)"
580 RETURN
590 DATA 27,7,45,53,3,46,51,45,21,4
600 REM 5: stop after about a second and a half
610 SAVE "tpi:say ONE TWO THREE FOUR FIVE SIX SEVEN EIGHT NINE TEN"
620 PAUSE 75: SAVE "tpi:say"
630 PRINT "Stopped: should be cut off": PRINT "around three or four."
640 RETURN
700 REM 6: a TS-Pico command while the card talks
710 SAVE "tpi:say THE TS-PICO CAN TALK AND WORK AT THE SAME TIME. THIS SENTENCE KEEPS GOING WHILE IT ANSWERS."
720 SAVE "tpi:info"
730 PRINT: PRINT "The speech should not stop": PRINT "or stutter during tpi:info."
740 RETURN
