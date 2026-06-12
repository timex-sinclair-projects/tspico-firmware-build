#! zmakebas -a 10 -n hello
#
# Example BASIC program, here to prove the basic/ -> .tap toolchain and to
# demonstrate the directory convention: living at basic/SD/TAP/demo/, it builds
# (gitignored) to "SD card/TAP/demo/hello.tap" = /TAP/demo/hello.tap on the SD
# card. Delete this folder once you've added real programs.
#
# zmakebas treats lines starting with '#' as comments, so everything above
# (including the `#!` build directive) is ignored by the tokenizer.

10 border 1: paper 1: ink 7: cls
20 print "Hello from the TS-Pico!"
30 print
40 print "This .tap was built from BASIC"
50 print "source by zmakebas at build time."
60 stop
