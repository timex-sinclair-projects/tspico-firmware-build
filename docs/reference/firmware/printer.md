# src/TS/printer.py — the virtual printer, text and BMP

Source: [`src/TS/printer.py`](../../../src/TS/printer.py). Part of the
[programmer's reference](../README.md).

The 2068 sends its printer output to the TS-Pico while bit 0 of TPMODE
(5DDBh, `PEEK 24027`) is set, which `SAVE "tpi:picopt"` does and
`SAVE "tpi:ts2040"` undoes; the ROM parses both commands itself and the Pico
never sees them ([user-manual.md D.2](../../manual/user-manual.md),
[rom/exrom-chunk1.md](../rom/exrom-chunk1.md)). The module docstring records
the wire format, captured on hardware on 2026-09-27 and
unchanged in ROM 2.2: an LPRINT or LLIST character is one transaction, the
10-byte pre-header `42 05 FF <char> 01|02 <flags> <ATTR_P> LL HH <xor>`,
with an 8-byte body (the character's pattern) for characters of 80h and
above; LLIST arrives already detokenised, and ENTER is 0Dh. COPY is
`42 04 FF <hires colour> <mode> 20 18|40 18 LL HH <xor>` followed by a body
of display memory from 4000h: 6912 bytes in mode 0, 15104 bytes
(4000h–7AFFh, both screens) in the other modes ([PROTOCOL.md §8](../../PROTOCOL.md)).

This module is pure: it turns the character stream into text, picks file
names and encodes a COPY body as a BMP. The bus side, which decides when the
SD card may be touched, lives in `tspico.py`: `PRINT_IO` feeds each character
to the `TextCapture` held in `PRT` and hands each COPY body to `COPY_BMP`;
`PRINT_FLUSH` writes `PRT.buf` to the capture file `prn_path`, opened with
`next_name`, once the buffer passes `PRINT_FLUSH_AT` (4096 bytes), before
any other command, and on `tpi:clprint` / `tpi:opprint`; `COPY_BMP` scales
the picture to `bmp_size`, 512×384 by default ([tspico-dispatch.md](tspico-dispatch.md)
for the three functions, [tspico-state.md](tspico-state.md) for the four
globals, [tspico-commands.md](tspico-commands.md) for `PRN_OPEN`,
`PRN_CLOSE`, `PRN_FLAG`, `PRN_SIZE` and `PRN_BMP`). The whole path from
`LPRINT` to the file is [flows/printer.md](../flows/printer.md); the user's
view is [user-manual.md ch 7](../../manual/user-manual.md). The module came
with #70; the hi-res colour table with #138.

Two tests pin it: [`src/test/printer_hosttest.py`](../../../src/test/printer_hosttest.py)
imports this module alone and checks every conversion, the file naming and
the four screen modes pixel by pixel against the fixture
`src/test/fixtures/copy_screen_mode0.bin`, a blank screen captured on
hardware; [`src/test/printer_io_hosttest.py`](../../../src/test/printer_io_hosttest.py)
runs the production `PRINT_IO` and the printer commands against a Z80 that
follows the EXROM's sequences, with the SD card as a temp folder.

## Map

| Lines | What |
|---|---|
| 1–20 | the docstring: where output goes, the wire format, what is and is not in this module |
| 22–25 | `import os`; `VLPRINT`, `VSCREEN` |
| 27–32 | `BLOCKS`, `CONTROLS`: the zmakebas escapes |
| 35–47 | `char_text` |
| 50–109 | `TextCapture` |
| 112–128 | `next_name` |
| 131–139 | `_PALETTE` |
| 142–149 | `_pix_addr`, `screen_size` |
| 152–168 | `HIRES_K`, `hires_ink_paper`: the ROM's 64-column colour byte |
| 171–206 | `row_colours`: the four screen modes |
| 209–243 | `write_bmp`: the file |

## `VLPRINT`, `VSCREEN`

| Constant | Value | Use |
|---|---|---|
| `VLPRINT` | `"/sd/VLPRINT"` | the folder of LPRINT/LLIST captures, `PRNnnnn.TXT` |
| `VSCREEN` | `"/sd/VSCREEN"` | the folder of COPY pictures, `SCRnnnn.BMP` |

Both are at the top of the card next to `TAP`, not inside it, so they do
not appear in `CAT` (user manual 7.1); Gustavo's manual v16 §2.26–2.27 put
them there. `tspico.py` imports the two names (`from TS.printer import …
VLPRINT, VSCREEN`), so they are bound in `tspico` at import time;
`printer_io_hosttest.py` points `t.VLPRINT` at a temp folder for that
reason, and a dev override that changed `printer.VLPRINT` afterwards would
change nothing in `tspico`.

## `BLOCKS`

The sixteen zmakebas escapes for the block graphics 80h–8Fh, indexed by
`c - 0x80`. Each is two characters, the left column then the right: a space
for nothing, `'` for the top half, `.` for the bottom half, `:` for both.
The character's bits are 1 = top-right, 2 = top-left, 4 = bottom-right,
8 = bottom-left, so `BLOCKS[1]` is `" '"`, `BLOCKS[3]` is `"''"` (both top)
and `BLOCKS[15]` is `"::"` (solid). The convention is
[zmakebas-plus](https://github.com/timex-sinclair-projects/zmakebas-plus)'s,
chosen so a capture reads like a zmakebas source listing. Pinned by
`printer_hosttest.py` ("block graphics -> zmakebas quadrant pairs").

## `CONTROLS`

The six one-parameter colour controls, byte to name: 10h INK, 11h PAPER,
12h FLASH, 13h BRIGHT, 14h INVERSE, 15h OVER. `TextCapture.feed` writes them
as `\{INK n}` and so on. 16h AT (two parameters) and 17h TAB (one) are
handled by `feed` itself and are not in the dict; `feed` only indexes
`CONTROLS` for 10h–15h.

## `char_text(c)`

The zmakebas text for one printable byte, with ENTER and the controls
already taken out by `feed`:

| `c` | Text |
|---|---|
| 5Ch | `\\` (a backslash must be escaped) |
| 7Fh | `\*` (copyright) |
| 20h–7Eh | the ASCII character; 60h, the pound sign on the 2068, stays `` ` `` |
| 80h–8Fh | `\` + `BLOCKS[c - 0x80]` |
| 90h–A4h | `\A`..`\U`, the user-defined graphics |
| anything else | `\{0xNN}`, the raw byte |

Pure; returns a `str`. Pinned by `printer_hosttest.py`: UDGs, copyright,
backslash, pound, and `\{0x01}\{0xC5}` for the rest.

## `TextCapture`

Turns the 2068's printer stream into zmakebas text in `buf`, tracking the
column and line for PRNSZ wrapping and AUTOPG. One instance exists, `PRT`
in `tspico.py`, created at import. Its fields:

| Field | Type, initial | Set by | Read by |
|---|---|---|---|
| `cols` | int, 80 | `__init__`; `PRN_SIZE` (`tpi:prnsz`, 0–255) | `feed`: wrap at this column; 0 = never |
| `lines` | int, 72 | `__init__`; `PRN_SIZE` | `_newline`: lines per page for AUTOPG; `PRN_FLAG`'s message |
| `autolf` | bool, False | `__init__`; `PRN_FLAG` (`tpi:autolf` / `noautolf`) | `_newline`: ENTER becomes CR LF instead of LF |
| `autopg` | bool, False | `__init__`; `PRN_FLAG` (`tpi:autopg` / `noautopg`) | `_newline`: a form feed every `lines` lines |
| `buf` | `bytearray`, empty | `reset`; `feed`; `PRINT_FLUSH` replaces it with an empty one after writing, or when more than 32768 bytes have piled up with no card | `PRINT_IO` (`len(PRT.buf) >= PRINT_FLUSH_AT`), `PRINT_FLUSH`, the dispatcher's "flush before any other command" test |
| `col`, `line` | int, 0 | `reset`; `feed`, `_newline`; `PRN_OPEN` and `PRN_CLOSE` set both to 0 | `feed`, `_newline` |
| `_ctl` | int or None | `reset`; `feed` | `feed`: a control byte waiting for its parameter(s) |
| `_arg` | list | `reset`; `feed` | `feed`: the parameters collected so far |

The settings are RAM only; nothing in `config.ini` holds them, so they last
until the Pico is switched off (user manual 7.3). The text is ASCII (every
escape is), kept as bytes so `PRINT_FLUSH` can write it as is.

### `TextCapture.__init__(self)`

Sets the four settings to their defaults, 80 columns, 72 lines, no CR LF,
no paging, and calls `reset`.

### `TextCapture.reset(self)`

A fresh buffer, column 0, line 0, no pending control. Called only from
`__init__`; the bus side empties `buf` by assignment and zeroes `col` and
`line` itself, which keeps the settings.

### `TextCapture._newline(self)`

Appends `\r\n` when `autolf`, else `\n`; column 0; one more line; and when
`autopg` is on, `lines` is non-zero and the count has reached it, appends a
form feed (`\f`) and starts the count again. Called by `feed` for ENTER and
for a wrap.

### `TextCapture.feed(self, c)`

One byte from the 2068, `pre[3]` of each printer pre-header, in this order:

1. A control is pending (`_ctl` is not None): append `c` to `_arg`; AT needs
   two parameters, every other control one; once complete, clear `_ctl` and
   append `\{AT r,c}`, `\{TAB n}` or `\{NAME n}` with `NAME` from `CONTROLS`.
   Parameter bytes do not count as columns.
2. 0Dh: `_newline`.
3. 10h–17h: remember it in `_ctl`, start a new `_arg`.
4. 06h: `\{COMMA}`, the PRINT comma.
5. Any other byte below 20h: `\{0xNN}`.
6. Otherwise a printable byte: if `cols` is non-zero and `col` has reached
   it, `_newline` first; then `char_text(c)` and one more column. An escape
   counts as one column however long its text is.

Pinned by `printer_hosttest.py`: ENTER → LF, AUTOLF → CR LF, the controls
with their parameters, AT / TAB / COMMA, raw bytes, wrapping at `cols`,
AUTOPG's form feed, `cols=0` never wrapping, and the stream captured on
hardware, `HELLO`, `CHR$ 144`, `"A";` and an LLIST line, which comes out as
`HELLO\n\A\nA  10 PRINT "foo"\n`. `printer_io_hosttest.py` pins that the
text lands in `/VLPRINT/PRN0001.TXT`.

Beware: a control's parameters arrive as later characters, each its own
transaction, so a `PRINT_FLUSH` can run between a control and its
parameter; `buf` is written and replaced, `_ctl` and `_arg` survive, and
the escape lands in the next write.

## `next_name(folder, prefix, ext)`

The next free `<prefix>NNNN.<ext>` in `folder`, creating the folder when it
is missing. `os.listdir(folder)`; an `OSError` means no folder, so
`os.mkdir(folder)` and an empty listing (a second `OSError` there, a card
that is write-protected or absent, propagates to the caller). Every name
is upper-cased and, when it starts with the prefix and ends with `.EXT`,
the digits between are parsed; names that do not parse are ignored. Returns
`"%s/%s%04d.%s" % (folder, prefix, top + 1, ext)`, so the first file is
`PRN0001.TXT` and the number after 9999 simply has five digits. The SD card
must be active: its callers, `PRINT_FLUSH` and `PRN_OPEN` with
`(VLPRINT, "PRN", "TXT")` and `COPY_BMP` with `(VSCREEN, "SCR", "BMP")`, run
inside `ACTIVATE_SD` … `DEACTIVATE_SD`. Pinned by `printer_hosttest.py`: a
missing folder gives `PRN0001.TXT` and exists afterwards; with `PRN0001.TXT`,
`prn0007.txt`, `PRN00X2.TXT` and `OTHER.TXT` present the next is
`PRN0008.TXT`.

## `_PALETTE`

The 16-colour BMP palette, 64 bytes built at import: entry `i` is `(B, G,
R, 0)`, with each channel either 0 or `v`, where `v` is D7h for the normal
colours 0–7 and FFh for the bright ones 8–15; blue comes from bit 0, red
from bit 1 and green from bit 2 of `i & 7`, the Spectrum numbering (1 blue,
2 red, 4 green, 7 white). The loop's `_i`, `_v`, `_c` stay as module
variables with leading underscores. Pinned: entry 7 is `D7 D7 D7 00`.

## `_pix_addr(y)`

The offset of pixel row `y` (0–191) in a display file, column 0:
`((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2)`, the Spectrum and
2068 layout in which the screen's third (bits 6–7) selects 2048 bytes, the
pixel line within a character row (bits 0–2) 256 bytes, and the character
row within the third (bits 3–5) 32 bytes. Add the byte column (0–31) for a
byte. Used by `row_colours`, and by the tests to set single pixels.

## `screen_size(mode)`

`(512, 192)` for COPY's mode byte 3, the 64-column hi-res screen;
`(256, 192)` for everything else. `write_bmp` sizes the picture from it;
`COPY_BMP` makes the same choice (`512 if mode == 3 else 256`) to work out
the scale factors.

## `HIRES_K`

The ROM's COPY (EXROM `sub_16f3h` in the listing, which opens with
`ld a,042h` and `SYNC_WRITE`) reads port FFh and, in 64-column mode, sends
the colour choice `k` (bits 3–5 of the port) not as `k` but as the `k`-th
byte of the table at EXROM 16EBh, `07 16 43 52 25 34 61 70` (the listing's
`l16ebh`, disassembled as instructions). `HIRES_K` maps each byte back to
`k`. On the screen, choice `k` is ink `k` on paper `7 - k`, the complement
the 2068 makes: black on white, blue on yellow, red on cyan, magenta on
green, green on magenta, cyan on red, yellow on blue, white on black.
Established on hardware on 2026-10-03 with the eight COPYs of
`basic/SD/TAP/test/hirescopy.bas` against the TV (#138; audit §4's open item
"hi-res COPY colours from the pre-header byte"). The comment explains why
the bytes cannot be read as two colour nibbles: they hold two colours a
nibble each, but with red and green swapped in the middle four, so a lookup
is the only safe reading. Pinned by `printer_hosttest.py`: the eight bytes
give the eight TV pairs, in that order.

## `hires_ink_paper(c)`

`(ink, paper)` of a 64-column COPY from the pre-header's colour byte
(`pre[3]`): `HIRES_K[c]` gives `k` and the answer is `(k, 7 - k)`; a byte not
in the table, from a ROM that does not use it, is read as a nibble each,
`((c >> 4) & 7, c & 7)`. Only `row_colours` calls it. Before #138 the
firmware read every byte as nibbles and the test fed it a made-up byte.

## `row_colours(scr, mode, y, hires_colour, out)`

Fills `out`, a `bytearray` of the picture's width, with the colour index
(0–15) of every pixel of row `y`. `scr` is the COPY body, display memory from
4000h, so offset 0 is 4000h, 1800h is 5800h, 2000h is 6000h and 3800h is
7800h. `pa = _pix_addr(y)`, then by mode:

- **3, hi-res 512×192:** `ink, paper = hires_ink_paper(hires_colour)`; for
  each of the 32 byte columns, the byte at `pa + col` in the first screen
  and then the one at `0x2000 + pa + col` in the second, eight pixels each,
  most significant bit first: the two screens interleave byte by byte, 512
  pixels in all.
- **1, the second screen:** bitmap at `0x2000 + pa`, attributes at
  `0x3800 + (y >> 3) * 32` (6000h and 7800h).
- **2, hi-colour:** bitmap at `pa`, one attribute byte per pixel row at
  `0x2000 + pa`, the same offset in the second bank.
- **anything else, including 0:** bitmap at `pa`, attributes at
  `0x1800 + (y >> 3) * 32` (5800h).

For the three attribute modes each of the 32 attribute bytes gives
`bright = 8` when bit 6 is set, `ink = (a & 7) | bright`, `paper =
((a >> 3) & 7) | bright`, and the bitmap byte's eight bits pick ink or paper.
FLASH (bit 7) is not read. Pinned by `printer_hosttest.py` for all four
modes: single pixels set in the fixture land where the TV would put them.

## `write_bmp(f, scr, mode, hires_colour, sx, sy)`

Writes the COPY body to the open file `f` as a 4-bit, 16-colour BMP with
each screen pixel `sx` wide and `sy` tall, one row at a time, so no
whole-picture buffer exists ("2048x1536 would not fit": that picture is
1.5 MB at 4 bits a pixel). Returns `(w, h)`, the picture size in pixels.

1. `w0, h0 = screen_size(mode)`; `w = w0 * sx`, `h = h0 * sy`; the row stride
   is `w * 4` bits rounded up to a multiple of 4 bytes; the pixel data
   starts at `off = 14 + 40 + 64` = 118 (file header, `BITMAPINFOHEADER`,
   16 palette entries); `size = off + stride * h`.
2. The header, little-endian: `BM`; the file size at 2; `off` at 10; 40 at
   14 (the info header's size); `w` at 18; `h` at 22, positive, so the rows
   are stored bottom-up; 1 plane at 26; 4 bits per pixel at 28; the image
   size at 34; 2835 pixels per metre (72 dpi) at 38 and 42; 16 colours at
   46; the compression field at 30 and the "important colours" at 50 stay
   0. `_PALETTE` at 54.
3. For `y` from `h0 - 1` down to 0: `row_colours` into `cols`; pack `sx`
   copies of each index into `row`, the high nibble of a byte for an even
   `x` and the low nibble for an odd one; write `row` `sy` times.

The default `bmp_size` of 512×384 makes `COPY_BMP` pass `sx = sy = 2` for a
256-wide screen and `sx = 1, sy = 2` for the hi-res one, so both come out
512 wide; `tpi:bmp` accepts widths of 256, 512, 1024, 2048 or 4096 and
heights of 192, 384, 768 or 1536, with 1596 read as 1536 as the manual
misprints it (`PRN_BMP`). Pinned by `printer_hosttest.py`: a 512×384 file is
14 + 40 + 64 + 256 × 384 = 98,422 bytes with a consistent header, 4 bpp and
16 colours; a pixel at (x, y) lands at (2x, 2y) doubled; the bottom-right
pixel is in the bottom-right; 1× gives 256×192; and
`printer_io_hosttest.py` checks the 98,422-byte `SCR0001.BMP` from a real
COPY transaction, and that a BREAK in the middle of the body leaves no file.
