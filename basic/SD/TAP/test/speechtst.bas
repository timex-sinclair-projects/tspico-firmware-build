#! zmakebas -a 10 -n speechtst
# The v3 card's speech (docs/v3-speech-proposal.md, user manual Appendix G):
# a menu of tests. The ROM takes a SAVE "tpi:..." name of at most 31
# characters (32 or more is Report C at run time), so tpi:say carries at
# most 23 characters of text: longer text goes in pieces. A piece that ends
# in a word runs straight on into the next (#289), so 2's pieces sound like
# one sentence. 1-3 and 5-6 use tpi:say; 4 drives ports 17 and 37 as a
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
200 REM 1: sentences, in pieces of 23 characters or fewer, queued
210 SAVE "tpi:say HELLO.": SAVE "tpi:say I AM YOUR TIMEX"
220 SAVE "tpi:say SINCLAIR 2068.": SAVE "tpi:say PRESS ANY KEY."
230 SAVE "tpi:say WARNING!": SAVE "tpi:say INTRUDER ALERT."
240 PRINT "Sentences queued:": PRINT "the 2068 is free meanwhile."
250 RETURN
300 REM 2: say what you type (ENTER alone ends), in pieces of up to 23 characters, split at a space
310 INPUT "Say: ";a$: IF a$="" THEN RETURN
315 PRINT a$
320 IF LEN a$<=23 THEN SAVE "tpi:say "+a$: GO TO 310
330 FOR j=23 TO 2 STEP -1: IF a$(j)=" " THEN GO TO 350
340 NEXT j: LET j=23
350 SAVE "tpi:say "+a$( TO j): LET a$=a$(j+1 TO ): GO TO 320
400 REM 3: allophones by name
410 PRINT "HELLO WORLD, by allophones"
420 SAVE "tpi:say [HH1 EH LL OW PA4]": SAVE "tpi:say [WW ER1 LL DD1 PA5]"
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
610 SAVE "tpi:say ONE TWO THREE FOUR FIVE": SAVE "tpi:say SIX SEVEN EIGHT NINE": SAVE "tpi:say TEN."
620 PAUSE 75: SAVE "tpi:say"
630 PRINT "Stopped: should be cut off": PRINT "around four or five."
640 RETURN
700 REM 6: a TS-Pico command while the card talks
710 SAVE "tpi:say THE TS-PICO CAN TALK": SAVE "tpi:say AND WORK AT THE SAME": SAVE "tpi:say TIME. THIS SENTENCE": SAVE "tpi:say KEEPS GOING WHILE IT": SAVE "tpi:say ANSWERS."
720 SAVE "tpi:info"
730 PRINT: PRINT "The speech should not stop": PRINT "or stutter during tpi:info."
740 RETURN
