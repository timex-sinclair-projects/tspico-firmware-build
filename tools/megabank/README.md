# Megabank test tapes

`mbmem.tap` is the TS-2068 Megabank's memory test (the Megabank spec,
Testing, "On hardware" step 2), copied here for `tools/hwcheck.py
--megabank`, which puts it on the card. Its source and build are in the
Megabank repo, `firmware/controller/memtest/` (`mbmem.asm`, `mbmem.bas`,
`build.py`); rebuild it there and copy the TAP here.

It writes 13 result bytes from 32261 as `mbmemres` on the card: state (0
done, 1 no board, 2 write-protected), bad pages (2 bytes), the first bad
one's pass, bank, 8K, chunk, offset (2), byte wanted, byte read, and the
pages read (2).
