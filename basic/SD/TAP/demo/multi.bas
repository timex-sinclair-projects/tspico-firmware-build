#! zmakebas -n loader -a 10
#
# Example MULTI-program tape. This single source builds a .tap holding THREE
# tape files in sequence -> "SD card/TAP/demo/multi.tap" (= /TAP/demo/multi.tap
# on the SD card). Each `#! zmakebas` line below starts a new program; the build
# tokenizes each and concatenates them in this top-to-bottom order.
#
# zmakebas ignores lines starting with '#', so every `#!` directive (and these
# comments) are invisible to the tokenizer. Delete this folder once you've added
# real programs (see basic/README.md).
#
# Program 1 of 3: "loader", autostarts at line 10.
10 border 2: paper 0: ink 7: cls
20 print "Multi-program tape demo"
30 print "Three files on one .tap"
40 stop

#! zmakebas -n data1
# Program 2 of 3: "data1" (no autostart).
10 rem second file on the tape

#! zmakebas -n data2
# Program 3 of 3: "data2" (no autostart).
10 rem third file on the tape
