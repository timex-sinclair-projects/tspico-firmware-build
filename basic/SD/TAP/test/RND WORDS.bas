#! zmakebas -n "RND WORDS" -a 10
# TS-Pico external command example: a random word from /words.txt on the
# Pico's flash. SAVE "tpi:.rndw" answers with a message the ROM prints.
# See src/TS/extcmd.py.
   10 REM TS-Pico EXT CMD example
   20 SAVE "tpi:.rndw"
   30 INPUT "Another word? (Y/n) ";c$
   40 IF c$<>"n" AND c$<>"N" THEN GO TO 20
