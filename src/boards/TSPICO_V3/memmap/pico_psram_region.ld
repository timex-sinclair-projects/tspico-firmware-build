/* TS-Pico v3: the PSRAM region, 8 MB (U22, APS6404L). The SDK writes this
   file with LENGTH = PICO_PSRAM_SIZE_BYTES, which is 0 here: the size is
   found at boot (PICO_AUTO_DETECT_PSRAM_SIZE), not set at build time, and a
   0-byte region cannot hold tspico_v3_psram_reserve (board_init.c). This
   board's memmap/ is first in the linker search path, so this copy wins. */
PSRAM(rwx) : ORIGIN = 0x11000000, LENGTH = 8M
