# Flow: `LOAD ""` from keyword to the last byte

`LOAD ""` on a TS-Pico reads the next program from the mounted TAP as if a
tape were playing. The 2068's own tape code does the work it always did —
it asks for a header, checks the name, asks for the data — but each "block
from tape" is a transaction with the Pico: a pre-header saying which block
is wanted, then the block streamed into the Z80 at its own pace. This flow
follows one `LOAD ""` of a BASIC program (a header block and a data block),
then VERIFY and MERGE, a headerless LOAD, nothing mounted, `f:` files, and
the failures.

Notation as in [command.md](command.md): **TX**/**RX** the bus FIFOs, **Y**
the status (`FF` READY + IDLE, `00` BUSY, `FB` RECOVERED).

## Before it starts

A tape is mounted (`LOAD "tpi:games.tap"`, [command.md](command.md#a-mount-load-tpigamestap)):
the file is copied to `/TMP/temp.tap` on the Pico's flash, `TSP.offset_tbl`
lists its blocks, the pointer (`TSP.tap_idx`, `TSP.offset`) is at block 0
or wherever `tpi:ffw`/`tpi:rew` left it. The link is idle: TX [01], Y `FF`.
TPMODE bit 1 is set (the default; [../rom/sysvars.md](../rom/sysvars.md#5ddbh-tpmode-peek-24027)).

## One block

The stock LOAD code (LD-LOOK-H and its callers) asks for a block by
calling LD-BYTES at EXROM 00FCh with A = the flag wanted (00h for a
header), carry set for LOAD, IX = where to put it, DE = how many bytes.
00FCh is `JP 196Dh`, the TS-Pico's LOAD ([../rom/exrom-driver.md](../rom/exrom-driver.md#load-196dh)).

| # | Side | Routine | Wire | TX / RX / Y after | What can go wrong |
|---|---|---|---|---|---|
| 1 | 2068 | 196Dh: TPMODE bit 1 set → the Pico (clear: the stock tape loader at 00FFh); `DI`; 00E5h pushed as the return | — | [01] / [] / FF | |
| 2 | 2068 | SYNC_WRITE: SYNC, wait READY + IDLE ([../rom/exrom-sync.md](../rom/exrom-sync.md#sync_write-2300h)) | `OUT (0Fh),03h` | | |
| 3 | Pico | port-0Fh write → `MQ_TO_IDLE` | | [01] / [] / FF | |
| 4 | 2068 | the pre-header, L the XOR: flag (00h), TADDR (1 LOAD), BANK (FFh), the session id (for a data block: then cleared), IX, DE (17 for a header), XOR | 10 × `OUT` | [01] / 10 words / 00 | |
| 5 | Pico | the dispatcher: `pre[0]` 00h/FFh with TADDR ≠ 0 → wait (≤ 3 s) for any core-1 flash write → `LOAD_SERVE` → `LOAD_TS` ([../firmware/tspico_io.md](../firmware/tspico_io.md#load_tspre-mq-tsp)) | | | a flash write in progress would stall the stream: hence the wait |
| 6 | 2068 | reads the pre-load | `IN` = 01h | [] / [] / 00 | 00h → J; not 1 → **Report R** (a refusal) |
| 7 | 2068 | WAIT_PICO_READY (~19.9 s) | polls 0Fh | | |
| 8 | Pico | `LOAD_TS`: open `/TMP/temp.tap`; **the search**: from `TSP.offset`, skip every block whose flag is not `pre[0]` (all in one request); check the block — whole, the length the Z80 asked for (`DE + 2`), a good XOR — and read it into RAM; `gc.collect()` | | | a damaged or wrong-length block: `LOAD_REFUSE(2)`, Report R, and the pointer moves past it; a full lap with no header accepted: status 7 |
| 9 | Pico | **the stream**: the flag, the content and the checksum by `STREAM_DMA` — the channel starts, *then* READY ([../firmware/tspico_io.md](../firmware/tspico_io.md#stream_dmamq-buf-echo-stall_ms-ready-first_ms0)) | | [flag, …] / [] / FF | READY before the first bytes: the Z80 reads 00h as the flag → R |
| 10 | 2068 | **echo 1**: H (the flag) | `OUT` flag | | |
| 11 | 2068 | the block, read blind, ~47 µs a byte: the flag compared with A' (a mismatch returns at once), then each byte stored at IX (or compared, VERIFY), H the running XOR, `STEP` (a BREAK test every 256 bytes) | `IN` × (DE + 2) | TX drained by the Z80 as the channel refills it | an empty FIFO reads 00h: a bad checksum, R. BREAK: `BRK_ABORT`, D |
| 12 | 2068 | the checksum byte XOR H: not 0 → 0815h: H sent as echo 2, carry clear, `RET` → the stock code's Report R | | | |
| 13 | 2068 | **echo 2**: H (0) | `OUT` 00h | [] / [flag, 00] / 00 | |
| 14 | Pico | the two echoes (`RX_WORD`, 1 s each); `TSP.tap_idx += 1`, `TSP.offset` past the block; **two bytes**: the final status 01h and the next pre-load 01h; READY | | **[01, 01] / [] / FF** | silence after the stream: RECOVERED (`MQ_TO_IDLE(recovered=True)`), the next command gets T |
| 15 | 2068 | WAIT_PICO_READY; the final status: 01h → carry set ("loaded"); other → the function chain, carry clear | `IN` = 01h | [01] / [] / FF | |
| 16 | 2068 | `EI`; `RET` through 00E5h (SA/LD-RETURN: border, interrupts) | | | |

The link ends as it began: TX [01], Y `FF`. `LOAD_TS` stages two bytes
because nothing runs after it in the dispatcher's LOAD branch: the final
status and the pre-load are both its job.

## A whole `LOAD ""`

1. **The header.** The stock code calls LD-BYTES for 17 bytes with flag
   00h → steps 1–16. On success it has a header in its buffer. `LOAD ""`
   takes any name; `LOAD "name"` compares, prints "Program: …" for a
   header that does not match, and calls LD-BYTES again for the next
   header — a new transaction, the pointer already past the last one.
2. **The data.** It calls LD-BYTES with flag FFh and the length from the
   header → steps 1–16 again. The pre-header's session id is the same as
   the header's; the firmware's search ends (`TSP.ld_start = -1`). After
   this block the ROM clears the session (5DD1h = 0).
3. **Autorun.** A BASIC program with a LINE in its header runs; the ROM
   decides that (EXROM 06C3h), the firmware passes the header unchanged.

### The bounded search

The Z80 drives the search: it asks for headers until one matches, and a ROM
without SYNC (ROM 1.1) cannot tell the Pico it gave up. So `LOAD_TS` keeps a search
start (`ld_start`) and lets the tape wrap round once: a header request that
comes back to where the search began after a wrap is answered with status
7 ("End of file"; ROM 2.2 shows it as R), and the search ends. `LOAD
"name"` with no such program therefore ends with a report after one lap,
not a hang ([../firmware/tspico_io.md](../firmware/tspico_io.md#load_tspre-mq-tsp)).

## Variants

### VERIFY

Carry clear at 196Dh, TADDR 2. The block is compared with memory instead of
stored (1A2Dh); a difference returns carry clear → the stock code's Report
R. The Pico serves the block the same way.

### MERGE

TADDR 3. The ROM loads the program into the workspace and merges it; the
Pico's side is identical.

### Headerless LOAD (machine code calling LD-BYTES)

A program that calls LD-BYTES itself (a game loader loading its next part)
sends a pre-header with its own TADDR (often 10 or more, whatever T_ADDR
holds) and flag. The dispatcher sends any 00h/FFh block with TADDR ≠ 0 to
`LOAD_SERVE`, so these load from the mounted tape too, in tape order.
Loaders with their own tape routines (turbo loaders) do not go through
LD-BYTES and cannot load from the Pico.

### Nothing mounted

`LOAD_TS` serves `/assets/nofile.tap`, a two-program tape: a "No file!"
screen with a menu, which chains to TS-Pico Commander, a file browser
(`basic/assets/nofile.bas`). If that file is missing from the Pico's flash, the LOAD is
refused with Report R ([../firmware/boot.md](../firmware/boot.md#the-picos-flash-filesystem-at-run-time)).

### `LOAD "f:file"`

The disk module's F_HOOK sends `tpi:fopen file` first, with the statement's
session id, and replaces the name with `""`
([../rom/exrom-fdd.md](../rom/exrom-fdd.md#f_hook)). The firmware builds a
one-shot tape `/TMP/native.tap` from the file's +3DOS header and data. When
the header request arrives with the same session, `LOAD_SERVE` swaps that
tape in for the mount, `LOAD_TS` serves it, and the mount comes back
afterwards unchanged; a different session means the arm is stale and the
mount is served ([../firmware/tspico_io.md](../firmware/tspico_io.md#load_servepre-mq-tsp),
[../firmware/tspico-disk.md](../firmware/tspico-disk.md#native_openpre-cmd)).

### `tpi:tape`

TPMODE bit 1 clear: step 1 goes to the stock tape loader. Nothing reaches
the Pico; the cassette port works as on any 2068.

## What goes wrong, and where

| Failure | Where | The 2068 sees |
|---|---|---|
| a damaged block, a wrong length, a bad TAP checksum | `LOAD_TS` before READY → `LOAD_REFUSE(2)` | R, and the pointer moves past the block |
| no matching header after one lap | `LOAD_TS`'s search: status 7 at the pre-load | R (196Dh turns any refused pre-load into R) |
| the FIFO ran dry mid-block (a GC, a flash write) | the Z80's checksum | R |
| BREAK during the block | `STEP` → `BRK_ABORT`; the Pico sees the 0Fh write in `STREAM_DMA`, rewinds the search, `MQ_TO_IDLE` | D |
| the Z80 stops reading (reset) | `STREAM_DMA` stall, 3 s → RECOVERED | the next command: T |
| no Pico | WAIT_PICO_READY | J |

## Where to read more

- The Pico side: [../firmware/tspico_io.md](../firmware/tspico_io.md#load_tspre-mq-tsp)
  (`LOAD_TS`, `LOAD_REFUSE`, `STREAM_DMA`), [../firmware/tspico-dispatch.md](../firmware/tspico-dispatch.md#ts2068_io)
  (the LOAD branch).
- The ROM side: [../rom/exrom-driver.md](../rom/exrom-driver.md#load-196dh).
- Byte by byte: [PROTOCOL.md §6.1](../../PROTOCOL.md#61-load--verify--merge).
- ZX48 mode's LOAD: [zx48.md](zx48.md).
