# Damaged TAPs

Seven small TAP files with the kinds of damage found in archive tapes, for
checking that a damaged or impossible block ends in **Report R** with the
protocol left clean (not Report T, and not an endless retry). Built by
`make_damaged_taps.py`; the files here are the exact bytes that were tested on
hardware (TS-2068, ROM 2.1, 2026-10-05) and in ZEsarUX (`tools/emu`).

Copy them to the SD card (e.g. `TAP/damaged/`), mount one with
`LOAD "tpi:<name>"`, then:

| File | Damage | Expected |
|---|---|---|
| `big.tap` | its only block: header flag, 7625 bytes, bad checksum | `LOAD ""`: R, and R again each time |
| `zero.tap` | starts `00 00` (a zero-length block), then a good program | R; a second `LOAD ""` loads "prog" |
| `bad.tap` | good header, data block with a bad checksum | "Program: prog", then R |
| `hcrc.tap` | 17-byte header with a bad checksum, then a good program | R; a second `LOAD ""` loads "prog" |
| `multi.tap` | two bad header-flag blocks (6 bytes, not 19), then a good program | R, R, then "prog" loads |
| `dlong.tap` | CODE header says 4 bytes; the data block holds 10 | `LOAD "" CODE`: "Bytes: c", then R |
| `hdd.tap` | "prog", two stray data blocks, then "two" | `LOAD "two"` finds it; `LOAD "nosuch"` ends in R after one pass |

After each R the next command should work first time.

Why a header search can only end in R this way: `docs/PROTOCOL.md` §13 (the
LOAD first-status pitfall) and `LOAD_REFUSE` in `src/TS/tspico_io.py`. The
host-side version of these cases is in `src/test/load_ts_hosttest.py`.
