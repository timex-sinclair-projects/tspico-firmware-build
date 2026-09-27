# The updater's BASIC loader, for the ORIGINAL slot-0 Spectrum ROM (Spectrum
# tokens: zmakebas's default). RAMTOP below 6000h keeps BASIC out of the
# updater's chunk; see updater.asm.
10 CLEAR 24575: PRINT "Loading the TS-Pico ROM updater"
20 LOAD ""CODE : RANDOMIZE USR 24576
30 PRINT "LOAD """" to try again."
