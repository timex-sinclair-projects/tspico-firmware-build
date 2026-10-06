# Flow: SYNC, BREAK, and a dropped transaction

The Z80 and the Pico must agree, byte for byte, on where they are in a
transaction. On ROM 1.1 nothing puts them back in step when they
disagree — after a BREAK, a crash on either side, a dropped byte — and
the usual result is a long wait and Report J, often for every command
after it. ROM 2.2 and the firmware have three mechanisms: **SYNC** at the
start of every transaction, a **BREAK abort** that tells the Pico, and a
**RECOVERED** bit with which the Pico says it gave up. This flow follows
each, then the Pico's own give-ups and the BIOS's contract for machine code.

Notation as in [command.md](command.md). The status bits
([../appendix/ports-and-status.md](../appendix/ports-and-status.md#the-status-byte)):
READY bit 6, IDLE bit 3, RECOVERED bit 2 (active low). `FF` READY + IDLE,
`F7` READY not IDLE, `FB` READY + IDLE + RECOVERED, `00` BUSY. Any Z80
write to port 0Fh reaches the Pico as an RX word with bit 8 set
(`PORT_0F`); the firmware treats every such write as "abandon whatever you
were doing".

## SYNC: every transaction starts from idle

| # | Side | What happens | TX / Y |
|---|---|---|---|
| 1 | 2068 | SYNC_WRITE (2300h): `OUT (0Fh),03h` ([../rom/exrom-sync.md](../rom/exrom-sync.md#sync_write-2300h)) | whatever was there |
| 2 | Pico | wherever it is listening — the idle loop's capture, `RX_CAPTURE`, `RX_BLOCK`, `TX_ROOM`, `CMD_KEY`, `CMD_DRAIN`, `STREAM_DMA` — the 0Fh word ends that wait. A transfer routine or `PROCESS_CMD` stops (`CmdAbort` or its return code) and empties its state; the dispatcher's SYNC branch then: `MQ_TO_IDLE(status=False)` (both FIFOs emptied, one byte staged — 01h, or a refused header LOAD's error), waits ≤ 800 ms for a core-1 flash write, arms the pre-header DMA channel, says idle ([../firmware/tspico-dispatch.md](../firmware/tspico-dispatch.md#sync-and-break-got--0)) | [01] / `FF` |
| 3 | 2068 | SYNC_WAIT: up to ~1.05 s (65 536 polls of 56 T) for READY + IDLE; carries on either way | |
| 4 | 2068 | the pre-header, as in every flow | |

So a SYNC always leaves the link at TX [01], RX empty, `FF`, whatever state
an earlier client — a crashed program, a 2068 reset mid-transaction, a
different ROM — left it in. It also clears RECOVERED. The cost is one OUT
and one wait per transaction. Firmware 1.1 would read the 03h as the
first byte of a pre-header: ROM 2.2 needs firmware that knows SYNC.

Two rules follow on the Pico side:

- **Say IDLE only when ready for the next pre-header.** The 2068 sends its
  pre-header the moment it sees IDLE; slow work (logging, a flash write)
  must come before the status, and the DMA capture is armed before it.
- **Answer the channel commands with `F7`.** The ROM's channel driver can
  send its next command at once; `CH_SEND` waits for IDLE before its SYNC,
  so the `FF` must mean "the tail is done" ([channels.md](channels.md)).

## BREAK

The user holds CAPS SHIFT + SPACE. The ROM looks for it in four places:

| Where the Z80 is | The check |
|---|---|
| any ready-wait (`WAIT_PICO_READY`, every poll) | `READ_STATUS` → `CHECK_BREAK` → 06AAh → `BRK_ABORT` |
| a SAVE or LOAD byte loop | `STEP`, every 256 bytes (`BRK_TEST`, which reads the keyboard directly: the loops run under `DI`) |
| a key wait (functions 82h, 84h, 86h: "Scroll?", Y/N, menus) | `KEYWAIT` at 0479h |
| the SAVE prompt ("Start tape, then press any key") | the base image's 22F0h (SPACE alone), before anything is sent |

ROM 1.1 checks the ready-wait too, but never tells the Pico; the other
three checks and the abort come from the SYNC/BREAK layer
([../rom/exrom-sync.md](../rom/exrom-sync.md)), except the SAVE prompt's,
which is in the base image (`src/rom/TSPICO.ROM`).

`BRK_TEST` and 22F0h ignore BREAK while bit 6 of 5CB7h is set (the flag
`ON ERR` sets when it traps; see [../rom/exrom-sync.md](../rom/exrom-sync.md#brk_test-2327h)).

`BRK_ABORT` (231Eh) ([../rom/exrom-sync.md](../rom/exrom-sync.md#brk_abort-231eh)):

| # | Side | What happens |
|---|---|---|
| 1 | 2068 | `OUT (0Fh),03h` — the same byte as SYNC |
| 2 | Pico | the 0Fh word ends whatever it was doing. **In a command** (`CMD_KEY`, `CMD_PUT`, `CMD_DRAIN`, `CMD_RX_FLUSH`): `CmdAbort(1)` → `PROCESS_CMD`'s `except` → `CMD_FLUSH` → the tail stages 01h and says `FF`. **In a LOAD** (`STREAM_DMA`/`TX_ROOM`): the search rewound to where it began, `MQ_TO_IDLE` → `FF`. **In a SAVE** (`RX_CAPTURE`/`RX_BLOCK`): nothing is written, `MQ_TO_IDLE` → `FF`. **In the idle loop**: the SYNC branch |
| 3 | 2068 | SYNC_WAIT: up to ~1 s for READY + IDLE |
| 4 | 2068 | `RST 8 / DEFB 0Ch`: **Report D BREAK - CONT repeats**; RST 8 resets the stack from ERR_SP, so this is safe at any depth and under `DI` |

After it the link is idle (TX [01], `FF`) and the next command works.
Without the SYNC/BREAK layer a BREAK in a ready-wait became Report J (A = 02h laundered
through ERR_9), the Pico was never told, and a Pico waiting in a key wait
or a full TX could hang until reset; the firmware's `CmdAbort` and the
bounded waits are the other half of the fix ([../firmware/tspico-bus.md](../firmware/tspico-bus.md#command-io-that-never-blocks),
[BREAK_AND_ABORT.md](../../rom-analysis/BREAK_AND_ABORT.md)).

Between `STEP`'s tests up to 255 more bytes go by, so an abort lands mid
block; the SYNC is what puts the Pico back, not the position of the abort.

## The Pico gives up: RECOVERED

Some failures the Pico sees and the Z80 cannot: a pre-header that stops
after a few bytes (a 2068 reset mid-transaction, a lost byte), a body or
block that stops part way, a Z80 that stops reading the answer. The Pico
waits a bounded time, then gives up and says so:

| Wait | Limit | Then |
|---|---|---|
| a pre-header, a command body, a SAVE block | 1 s of silence (`RX_CAPTURE`, `RX_BLOCK`; 3 s before a SAVE's data block) | `MQ_TO_IDLE(recovered=True)`: TX [01], Y `FB` |
| the LOAD stream, the echoes | 3 s without a read; 1 s for each echo | the same |
| command output nobody reads | `CMD_STALL_MS`, 10 minutes (a listing at "Scroll?" may wait as long as the user likes) | `CmdAbort(3)` → the tail says `FB` |
| a key wait | `KEY_WAIT_MS`, a day | the same |
| an unrecognised pre-header | at once | `MQ_TO_IDLE(recovered=True)` |

On the 2068, the ROM's `RD_STATUS` (inside every `WAIT_PICO_READY` poll)
sees READY with bit 2 low and raises **Report T "TS-Pico reset, try
again"** (ERR_NR 1Ch) at once — where ROM 1.1 waits ~19.9 s for J. The next
SYNC clears the bit. The BIOS returns it as carry with A = 1Ch instead of
raising it ([../rom/exrom-sync.md](../rom/exrom-sync.md#rd_status-234fh)).

Test order matters: BUSY (00h) has bit 2 clear too, so RECOVERED is only
meaningful with READY set.

## The firmware's own recovery

- **A handler that raises**: `PROCESS_CMD` catches it, `FAIL_CMD(10)` puts
  the bus back if the card had it and answers J; the tail stages the next
  pre-load. The 2068 sees J for that command and nothing after.
- **An error in the service loop itself**: `TS2068_IO`'s outer loop resets
  only the bus link — the ROM and bank state machines are never touched,
  so the 2068 keeps running — and stages RECOVERED, so the next command
  gets T. Three such failures within a minute and it gives up: the
  exception reaches `main.py`, which logs it and stops
  ([../firmware/tspico-dispatch.md](../firmware/tspico-dispatch.md#ts2068_io)).
- **A card left mid-transfer** by a reset during an SD access: the
  driver's recovery at the next mount ([sd-handover.md](sd-handover.md#no-card-and-a-stuck-card)).

## Machine code: the BIOS contract

A program in RAM that talks to the Pico through the BIOS table (EXROM
1840h) does not want reports raised under it. The ROM gives it its own wait
and end:

| Entry | Returns |
|---|---|
| WF_NPH (184Ch → 239Eh) | NC ready; C with A = 02h timeout, 0Ch BREAK (abort already sent), 1Ch the Pico reset the transaction |
| C_END (184Ah → 184Fh → C_END2 in the disk module) | NC status 1; C with A = status − 1, 09h timeout, 0Ch, 1Ch |

0Ch and 1Ch can never be a status − 1, since the firmware's highest status
is 11. A program should start each exchange with SYNC (`OUT (0Fh),03h`, then
wait for bits 6 and 3) as the ROM does ([../rom/exrom-driver.md](../rom/exrom-driver.md#bios_table-1840h),
[PROTOCOL.md §9](../../PROTOCOL.md#9-the-pico-interface-bios-exrom-1840),
the programmer's manual, chapter 8).

## Summary

| Event | 2068 | Pico | Link after | Report |
|---|---|---|---|---|
| a new transaction | SYNC | `MQ_TO_IDLE` | [01], `FF` | — |
| BREAK in a wait or a loop | `BRK_ABORT` | stops, cleans up, idle | [01], `FF` | D |
| the Pico gives up on a stalled transaction | — | `MQ_TO_IDLE(recovered=True)` | [01], `FB` | T at the next ready-wait |
| no Pico, or one that never answers | `WAIT_PICO_READY` times out | — | — | J after ~19.9 s |
| a handler crashes | — | `FAIL_CMD(10)` | [01], `FF` | J |
