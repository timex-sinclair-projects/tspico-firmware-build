# Flow: `LPRINT`, `LLIST`, `COPY`

With `SAVE "tpi:picopt"` the TS-Pico is the 2068's printer: LPRINT and
LLIST become text files on the SD card, and COPY a BMP picture of the
screen. The 2068's ROM sends **every printed character as its own
transaction** — a pre-header with the character in it — and COPY as one
transaction carrying the whole screen. The Pico collects the text in RAM
and writes it to the card in blocks. This flow follows an `LPRINT "Hi"`,
an `LLIST`, a COPY, then the settings and the failures. User's view: [user
manual chapter 7](../../manual/user-manual.md#chapter-7-the-virtual-printer).

Notation as in [command.md](command.md): **TX**/**RX** the bus FIFOs, **Y**
the status (`FF` READY + IDLE, `F7` READY mid-transaction, `00` BUSY).

## The switch

TPMODE bit 0 ([../rom/sysvars.md](../rom/sysvars.md#5ddbh-tpmode-peek-24027)):
`tpi:picopt` sets it, `tpi:ts2040` clears it; `tpi:tape` and
`tpi:sdcard` leave it alone (before ROM 2.1, `tpi:tape` set TPMODE to 0 and
cleared it too, #176). The ROM handles all four itself; nothing is sent. Clear,
the 2068 prints as stock — the ZX Printer routines, moved from HOME to the
EXROM unchanged, still drive a printer on port FBh
([../rom/exrom-chunk1.md](../rom/exrom-chunk1.md#the-printer-path-1630h183bh)).

## One character: `LPRINT "Hi"`

LPRINT selects stream 3 (P) and prints `H`, `i` and ENTER through
`RST 10h`. Every character passes through HOME's PRINT-OUT at 0500h, whose
first call ROM 1.1 changed to the character router at 0A09h
([../rom/home.md](../rom/home.md#0a02h0a2fh-copy-the-character-router-copy-buff)).

| # | Side | Routine | Wire / state | What can go wrong |
|---|---|---|---|---|
| 1 | 2068 | HOME 0A09h | TPMODE bit 0 set, FLAGS bit 1 set (the printer is the channel), the character below 80h → 0A1Dh → 04F2h → the no-return thunk → EXROM 1639h → 1668h | bit 0 clear: the stock path; not the printer channel: the screen, as stock |
| 2 | 2068 | 1668h → 164Dh | SYNC_WRITE `'B'`; TADDR **5** (also kept in 5DD9h), BANK; PMR1 = the character, 1 (no body); PMR2 = flag bits and ATTR_P; length 0; XOR | |
| 3 | Pico | the dispatcher: `'B'` with TADDR 4–6 → `PRINT_IO` ([../firmware/tspico-dispatch.md](../firmware/tspico-dispatch.md#print_iopre)) | TX [01] (the pre-load, still there) | |
| 4 | 2068 | 1828h: reads the pre-load (01h), WAIT_PICO_READY | | 00h → J |
| 5 | Pico | `PRT.feed(pre[3])`: the character into the text buffer as zmakebas text; if the buffer has reached 4096 bytes, `PRINT_FLUSH()` writes it to the card now (the Z80 is in its ready-wait, so the card may have the pins); then the next pre-load 01h and READY + IDLE | TX [01], Y `FF` | a card error: logged, the text kept (dropped past 32 768 bytes) |
| 6 | 2068 | back through HOME 0A35h | | |

So a plain character's whole transaction is: SYNC, ten bytes out, one
byte in, one ready-wait. The pre-load the 2068 reads at step 4 *is* the
answer; `PRINT_IO` only stages the next one.

**Keywords.** In LLIST and in `LPRINT` of a token, a byte of A5h or more
goes to HOME 0A68h, which runs the stock PO-TOKENS: the keyword's letters
come back through 0500h one by one, each its own transaction. The file
gets the text, not the token.

**Block graphics and UDGs.** 80h–8Fh: HOME builds the 8×8 pattern at
MEMBOT and 04E8h passes its address as PMR1; 90h–A4h: 0A26h → EXROM 180Fh
computes the UDG's address. Either way PMR1 high = 2 and the length is 8:
after the pre-load and the ready-wait the 2068 sends a `'D'` body with the
eight bytes (SEND_DATA_BLOCK_D), and the Pico reads it, writes the
character's escape (`\A` … `\U`, or the block-graphic escape) and answers
a final status — TX [status, 01]. The pattern is read and not used; a bad
XOR is logged as a warning, and the character is printed anyway (#180).

**The buffer.** `PRT` turns the stream into zmakebas text: ENTER a line
end (`\n`, or `\r\n` with AUTOLF), the colour controls as `\{INK n}` and
so on with their parameters, a comma as `\{COMMA}`, wrapping at PRNSZ's
columns, a form feed every PRNSZ lines with AUTOPG
([../firmware/printer.md](../firmware/printer.md#textcapturefeedself-c)).
It reaches the card at 4096 bytes, on `tpi:clprint` or `tpi:opprint`, and
before any other transaction: the dispatcher flushes `PRT.buf` whenever a
pre-header that is not printer traffic arrives (after `PRELOAD_READ`, so
the flush does not eat that transaction's pre-load) ([../firmware/tspico-dispatch.md](../firmware/tspico-dispatch.md#print_flush)).

**The file.** The first flush opens the next free `/VLPRINT/PRNnnnn.TXT`
on the card and appends to it from then on; `tpi:clprint` closes it (the
next character opens a new one), `tpi:opprint` starts the next number
straight away ([../firmware/tspico-commands.md](../firmware/tspico-commands.md#the-printer-settings)).

**COPY-BUFF.** At the end of each LPRINT line the stock code still calls
COPY-BUFF (HOME 0A23h → EXROM 17CDh), the relocated ZX Printer routine. It
does not involve the Pico: with no ZX Printer fitted it returns at once.

## LLIST

The same as LPRINT, character by character, with the listing's line
numbers and keywords as text. A long program is thousands of transactions;
each takes roughly a millisecond of bus traffic plus the ready-wait's
first poll (~88 ms is the ROM's poll interval, but a Pico that is already
READY ends the wait at the first poll) *(inferred: LLIST speed has not
been measured here)*.

## COPY

`COPY` → HOME 0A02h → EXROM 1630h → 1781h: TPMODE bit 0 set → 16F3h, one
transaction ([../rom/exrom-chunk1.md](../rom/exrom-chunk1.md#the-printer-path-1630h183bh)).

| # | Side | What happens |
|---|---|---|
| 1 | 2068 | SYNC; `'B'`; TADDR 4 or 6 (from T_ADDR: the screen mode as the stock code encodes it); BANK; PMR1 low = the hi-res colour byte (from a table, by port FFh bits 3–5), high = the screen mode (port FFh bits 0–2, 6 sent as 3); PMR2; the length, 1B00h (6912) or 3B00h (15 104 for the larger screens); XOR |
| 2 | Pico | `PRINT_IO`: `RX_BLOCK(…, "mid")` listening, Y `F7` |
| 3 | 2068 | SEND_DATA_BLOCK_D from 4000h: the pre-load, a ready-wait, `'D'`, the length, the screen bytes, the XOR |
| 4 | Pico | the body captured (DMA ring); its XOR checked; `COPY_BMP` — the card mounted, `next_name` → `/VSCREEN/SCRnnnn.BMP`, the screen decoded (normal, dual or hi-res, with its colours) and written at `tpi:bmp`'s size, 4 bits a pixel ([../firmware/printer.md](../firmware/printer.md#write_bmpf-scr-mode-hires_colour-sx-sy)); then the final status and the next pre-load, READY + IDLE |
| 5 | 2068 | the final status: 1 → done; 2 → Report R (a bad body, no card, a failed write) |

With TPMODE bit 0 clear the stock COPY runs (176 pixel lines to a ZX
Printer).

## The settings

| Command | Effect |
|---|---|
| `tpi:prnsz CODE c,l` | wrap at `c` columns (0 = never), `l` lines per page |
| `tpi:autolf` / `tpi:noautolf` | ENTER as CR LF / LF |
| `tpi:autopg` / `tpi:noautopg` | a form feed every `l` lines / none |
| `tpi:bmp CODE w,h` | COPY's picture size: 256–4096 by 192–1536 in the listed steps |
| `tpi:opprint` / `tpi:clprint` | start the next file / close this one |

All last until power-off ([../firmware/tspico-commands.md](../firmware/tspico-commands.md#the-printer-settings)).

## What goes wrong, and where

| Failure | Where | The 2068 sees |
|---|---|---|
| no Pico | the pre-load or the ready-wait | J |
| no card while printing text | `PRINT_FLUSH` | nothing: the text is kept in RAM (up to 32 768 bytes, then dropped) and written when a card is back |
| a bad COPY body, no card, a failed BMP write | `PRINT_IO` | R |
| BREAK in a ready-wait of a COPY | `BRK_ABORT` sends the abort byte; the Pico's capture sees the 0Fh write → `MQ_TO_IDLE` | D |

## Where to read more

- The Pico side: [../firmware/tspico-dispatch.md](../firmware/tspico-dispatch.md#print_iopre)
  (`PRINT_IO`, `PRINT_FLUSH`, `COPY_BMP`), [../firmware/printer.md](../firmware/printer.md).
- The ROM side: [../rom/home.md](../rom/home.md#0a02h0a2fh-copy-the-character-router-copy-buff),
  [../rom/exrom-chunk1.md](../rom/exrom-chunk1.md#the-printer-path-1630h183bh).
- Byte by byte: [PROTOCOL.md §8](../../PROTOCOL.md#8-printer-transactions).
