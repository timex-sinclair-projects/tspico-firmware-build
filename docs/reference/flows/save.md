# Flow: `SAVE "name"` into a TAP

`SAVE "name"` writes a program to the SD card as a TAP file in the current
folder — or, with append on, onto the end of the mounted TAP. The 2068's
tape code sends a header block and a data block as it would to a cassette;
each is a transaction with the Pico, which captures the blocks, checks
them, can refuse the SAVE before the data is sent, and writes the file
before it gives the final status. This flow follows one `SAVE "name"` of a
BASIC program, then APPEND and NEWTAP, `SAVE "f:path"`, and the failures.

Notation as in [command.md](command.md): **TX**/**RX** the bus FIFOs, **Y**
the status (`FF` READY + IDLE, `F7` READY mid-transaction, `FB` RECOVERED,
`00` BUSY).

## Before it starts

The link is idle: TX [01], Y `FF`. TPMODE bit 1 set (the default). The
statement's syntax pass has run: `SAVE` with a name of up to 10 characters
(the ROM refuses `SAVE ""` and longer names itself). At run time EXROM
SAVE-ETC (01D2h) goes through F_HOOK (not `f:`) and SESSION_SETUP, which
makes the **session id** from FRAMES and, the name not starting `tpi:`,
returns to the stock SAVE-ETC body ([../rom/exrom-driver.md](../rom/exrom-driver.md#session_setup-1a73h-is-this-name-a-command)).
The stock code builds the 17-byte header and prints "Start tape, then
press any key"; v1.7's routine at 22AEh waits for a key and tests BREAK
before anything is sent ([../rom/exrom-chunk1.md](../rom/exrom-chunk1.md#the-save-prompt-and-break-v17-22aeh22fdh)).

## The header block

The stock code calls SA-BYTES at EXROM 0068h (`JP 1879h`) with A = 00h, IX
= the header, DE = 17 ([../rom/exrom-driver.md](../rom/exrom-driver.md#save-1879h)).

| # | Side | Routine | Wire | TX / RX / Y after | What can go wrong |
|---|---|---|---|---|---|
| 1 | 2068 | 1879h: TPMODE bit 1 set → the Pico; `DI`; 00E5h pushed | — | [01] / [] / FF | |
| 2 | 2068 | SYNC_WRITE | `OUT (0Fh),03h` | | |
| 3 | Pico | `MQ_TO_IDLE` | | [01] / [] / FF | |
| 4 | 2068 | the pre-header: 00h, T_ADDR (0), BANK, the session, IX, DE (17), XOR | 10 × `OUT` | [01] / 10 / 00 | |
| 5 | Pico | the dispatcher: `pre[0]` 00h, TADDR 0 → a SAVE. Any buffered printer text goes to the card first; then `PRELOAD_READ` (wait for the Z80 to take the pre-load) and **`SD_PROBE()`** — is there a card? (`TSP.save_no_card`); the pre-load put back if the probe ate it; wait for core 1; `SAVE_TS` ([../firmware/tspico-dispatch.md](../firmware/tspico-dispatch.md#ts2068_io), [../firmware/tspico_io.md](../firmware/tspico_io.md#save_tsmq-tsp-prenone)) | | [01] / [] / 00 | a probe that rebuilds the state machine empties TX: hence `PRELOAD_READ` first |
| 6 | 2068 | reads the pre-load; `WAIT_PICO_READY` | `IN` = 01h | [] / [] / 00 | not 1 → `STATUS_TO_REPORT` |
| 7 | Pico | `SAVE_TS`: `RX_CAPTURE(…, 21, "mid")` — listening, then Y `F7` | | [] / [] / F7 | |
| 8 | 2068 | the block, ~43 µs a byte, H the XOR: 00h, the session (twice: 18E3h), the 17 header bytes, H | 21 × `OUT` | [] / 21 / 00 | |
| 9 | Pico | the checks, in order — each a **refusal** with a status the 2068 reads in step 11: the session must match the pre-header (R); the header's XOR (R); a card (`save_no_card`: J); an `f:` SAVE whose "Replace?" was answered N (D); the name (`SAVE_NAME`: F); a length of 0 (A); room for the block (6) | | | a refusal here keeps the program in the 2068: nothing more is sent |
| 10 | Pico | **mid-phase status** 01h, Y `F7` | | [01] / [] / F7 | |
| 11 | 2068 | 190Bh: WAIT_PICO_READY; reads it: 1 → carry set, back to the stock code | `IN` = 01h | | a refusal (02h, 03h, 08h, 0Ah, 0Bh, 06h) → `STATUS_TO_REPORT`: the report, and the SAVE stops |

## The pause and the data block

The stock code pauses about a second between the blocks (`HALT`s), then
calls SA-BYTES with A = FFh, IX = the program, DE = its length.

| # | Side | Routine | Wire | TX / RX / Y after | What can go wrong |
|---|---|---|---|---|---|
| 12 | Pico | `SAVE_TS`: `RX_BLOCK(MQ, blk, len + 4, 3000, 1000, "mid")` — up to 3 s for the first byte | | [] / [] / F7 | |
| 13 | 2068 | 1879h with A = FFh: **no pre-header** — straight to the block: FFh, the session (then cleared: 5DD1h = 0), the bytes, `STEP` after each (a BREAK test every 256 bytes), H | `OUT` × (len + 4) | | BREAK: `BRK_ABORT` → D, nothing written |
| 14 | Pico | the block captured (by DMA into a ring); its XOR (flag and data, not the session) | | [] / [] / 00 | a bad XOR: final status 02h now, Report R, no file |
| 15 | 2068 | WAIT_PICO_READY for the final status (~19.9 s) | polls 0Fh | | |
| 16 | Pico | both blocks rewritten into TAP form (the session slots become the block lengths); **the write**: `ENA_SD` → `SAVE_MOUNT` → `ACTIVATE_SD` (MQ parked), `cur_path/name.tap` created (`"wb"`), header and block written; `TSP.f_name` = the new file; `save_final` = 01h (or 0Ah if the write failed) | | no bus program while the card has the pins | a card pulled since step 5, a full card: `save_final` 0Ah, Report J, and the file is not mounted |
| 17 | Pico | the dispatcher: the new file re-mounted (`MOUNT_FILE`), the folder re-read; `DEACTIVATE_SD` + `ACTIVATE_MQ`; **the arm point**: `save_final`, then the next pre-load, then READY | | **[01, 01] / [] / FF** | |
| 18 | 2068 | reads the final status: 01h → "0 OK" | `IN` = 01h | [01] / [] / FF | |

The link ends idle with one pre-load. The final status waits for the write
on purpose: it used to be sent before the write, so the 2068 printed "0 OK"
and a BASIC program's next `tpi:` command arrived while the Pico was still
on the card with its bus interface down — its pre-header was lost
(hardware, 2026-10-04). Now a failed write is reported, and the next
command finds the Pico listening.

After the SAVE the new file is mounted, with append off: a second `SAVE`
makes another new file. An existing file of the same name is replaced.

## Variants

### Append (`tpi:append on`, or `tpi:newtap name`)

With a TAP mounted and `TSP.append` on, step 9 skips the name check and
step 16 opens the mounted TAP (`TSP.f_name`) in `"ab"`: the blocks go on
its end, and the mount is refreshed so they can be loaded. If the card was
swapped since (the mount found a different card and turned append off),
the write refuses rather than append to a same-named file on the other
card. `tpi:newtap name` (or `FORMAT "name.tap"`) makes an empty TAP,
mounts it and turns append on: the usual way to collect several programs
in one tape ([../firmware/tspico-commands.md](../firmware/tspico-commands.md#new_tappre-cmd)).

### `SAVE "f:path"` (ROM 2.1)

Before step 1, the module's F_HOOK sends **`tpi:fopen path`** with the
statement's session id and the modifier token (CODE, SCREEN$, DATA, LINE)
([../rom/exrom-fdd.md](../rom/exrom-fdd.md#f_hook)). The firmware's
`NATIVE_OPEN` checks the name and arms `TSP.native` for this session; if
the file exists it asks **"Replace NAME? (Y/N)"** with function 88h on the
lower screen (so the question does not land in a picture `SCREEN$` is
about to save). F_HOOK then shortens the name to the path's first 10
characters (a stand-in) and the stock SAVE runs: steps 1–18, except that at
step 9 an answer of N is refused with D, the name check is skipped, and at
step 16 the file is `path` itself, written with a +3DOS header and only the
data ([../firmware/native.md](../firmware/native.md)); the listing is
refreshed and the mount left alone ([../firmware/tspico-disk.md](../firmware/tspico-disk.md#native_openpre-cmd)).

### `tpi:tape`

TPMODE bit 1 clear: step 1 goes to the stock SA-BYTES; the cassette port
works as on any 2068.

### No card

Step 5's probe sets `save_no_card`; step 9 refuses with J at the header,
before the data block: the program is still in the 2068's memory. Putting
a card in and saving again is all it takes.

## What goes wrong, and where

| Failure | Where | The 2068 sees |
|---|---|---|
| no card, a bad name, a zero length, no room | step 9, the mid status | J, F, A, 6 — nothing sent after the header |
| the header misaligned or damaged | step 9 | R |
| BREAK at the prompt | v1.7's 22AEh, before step 1 | D |
| BREAK in a block | `STEP` → `BRK_ABORT`; `SAVE_TS` returns on the 0Fh write | D, nothing written |
| the data damaged in transit | step 14 | R, nothing written |
| the 2068 stops mid-block (reset) | `RX_BLOCK`'s stall, 1 s | the next command: T |
| the write fails (card pulled, full) | step 16 | J |
| no data block within 3 s | `RX_BLOCK` | R |

## Where to read more

- The Pico side: [../firmware/tspico_io.md](../firmware/tspico_io.md#save_tsmq-tsp-prenone)
  (`SAVE_TS`, `REFUSE_SAVE`, `SAVE_NAME`, `RX_BLOCK`),
  [../firmware/tspico-dispatch.md](../firmware/tspico-dispatch.md#ts2068_io)
  (the SAVE branch and its arm point).
- The ROM side: [../rom/exrom-driver.md](../rom/exrom-driver.md#save-1879h).
- Byte by byte: [PROTOCOL.md §6.2](../../PROTOCOL.md#62-save) (which still
  describes the final status before the write; the code sends it after).
- ZX48 mode's SAVE: [zx48.md](zx48.md).
