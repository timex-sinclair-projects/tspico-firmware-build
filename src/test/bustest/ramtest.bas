#! zmakebas -n ramtest -a 10
# ramtest.asm's loader: the code goes to 32768, whose stub moves it to 5B00h.
# It never returns; reset the 2068 when you have read the screen.
   10 CLEAR 32767: LOAD ""CODE 32768
   20 PRINT "ramtest: RAM 5F00-FFFF, forever."'"BASIC will be gone. Reset to stop."''"Press a key to start."
   30 PAUSE 0
   40 RANDOMIZE USR 32768
