# Flow: `SAVE "tpi:dir"` from keyword to answer

A `tpi:` command is the TS-Pico's basic transaction: the 2068 sends a
pre-header and a body holding the text, the Pico runs a handler, and the
answer comes back as a status or as a response function that prints and
takes keys. This flow follows `SAVE "tpi:dir"` — the folder listing, a
paged answer — through both sides, then the variants: a bare status, a
one-line message, a Y/N question, a mount, an external command, and a
command that needs the card when there is none.

Notation: **TX**/**RX** are the bus state machine's FIFOs (TX is what the
Z80 reads next); **Y** is the status on port 0Fh: `FF` READY + IDLE, `F7`
READY with a transaction open, `FB` READY + IDLE + RECOVERED, `00` BUSY.
The PIO drops Y to `00` after every Z80 OUT by itself (auto-busy). ROM 2.1
and firmware 2.1.2 throughout.

## Before it starts

The link is idle: **TX [01]** (the pre-load the previous transaction's tail
staged, or the boot's), **RX empty**, **Y `FF`**, and on the Pico the
pre-header DMA channel armed ([boot.md](boot.md)).

## The syntax pass

When the line is entered, BASIC checks it: `SAVE` is syntax class 0Bh →
HOME 2548h → EXROM SAVE-ETC (01ABh), which borrows HOME's expression
evaluator for the name and reaches 01CCh; with FLAGS bit 7 clear (syntax)
it goes to the stock syntax path. For a `tpi:` name SESSION_SETUP is
entered too ([../rom/exrom-driver.md](../rom/exrom-driver.md#session_setup-1a73h-is-this-name-a-command)),
parses an optional `CODE a,b`, and on the syntax pass accepts the statement
without sending anything. Nothing reaches the Pico.

## Run time

| # | Side | Routine | Wire | TX / RX / Y after | What can go wrong |
|---|---|---|---|---|---|
| 1 | 2068 | HOME 2548h → EXROM 01ABh → 0210h (pushes 01EAh, T_ADDR → 0) → HOME 254Fh (the name) → EXROM 01CCh → 01D2h → F_HOOK (3003h: not `f:`) → SESSION_SETUP (1A73h) ([../rom/home.md](../rom/home.md#2548h2560h-save-load-verify-merge-v11)) | — | [01] / [] / FF | |
| 2 | 2068 | SESSION_SETUP: session id from FRAMES; the name 5–31 characters; `TPI` + `:` → TPMODE bit 7; no `CODE`: PMR1 = PMR2 = 0; run time; not a switch word → 1B8Dh: STK-FETCH | — | | a name of 32+ characters: Report C; under 5 or no `tpi:`: an ordinary SAVE |
| 3 | 2068 | BUILD_PREHEADER_B (1BA0h) → SYNC_WRITE (2300h) ([../rom/exrom-sync.md](../rom/exrom-sync.md#sync_write-2300h)) | `OUT (0Fh),03h` | | |
| 4 | Pico | the capture sees a port-0Fh write: `MQ_TO_IDLE` — FIFOs emptied, one 01h staged, READY + IDLE ([../firmware/tspico_io.md](../firmware/tspico_io.md#mq_to_idlemq-recoveredfalse-statustrue-first0x01)) | | [01] / [] / FF | |
| 5 | 2068 | SYNC_WAIT: up to ~1 s for READY + IDLE | reads 0Fh | | no IDLE in time: carry → Report J |
| 6 | 2068 | the pre-header, D the XOR | `OUT` 42h ('B'), 00h (TADDR), FFh (bank), 00h 00h (PMR1), 00h 00h (PMR2), 07h 00h (length of `tpi:dir`), XOR | [01] / 10 words / 00 | |
| 7 | Pico | the DMA channel (or `RX_CAPTURE`) takes ten words; the dispatcher sees `pre[0] = 'B'`, `pre[1] = 0` → `PROCESS_CMD` ([../firmware/tspico-dispatch.md](../firmware/tspico-dispatch.md#process_cmdpre-sa_funct-ext_sa_funct)) | | [01] / [] / 00 | a pre-header that stops short: `MQ_TO_IDLE(recovered=True)`, Y `FB`, the 2068 gets Report T |
| 8 | 2068 | SEND_DATA_BLOCK_D (223Eh): reads 0Eh at once — **the pre-load** ([../rom/exrom-chunk1.md](../rom/exrom-chunk1.md#send_data_block_d-223eh)) | `IN` = 01h | [] / [] / 00 | 00h (an empty TX): ERR_9 → Report J |
| 9 | 2068 | WAIT_PICO_READY: polls 0Fh, ~88 ms a poll, up to ~19.9 s ([../rom/exrom-driver.md](../rom/exrom-driver.md#wait_pico_ready-1a54h)) | reads 0Fh | | |
| 10 | Pico | `PROCESS_CMD`: `RX_CAPTURE(…, "mid")` — listening first, then Y `F7` | | [] / [] / F7 | |
| 11 | 2068 | the body, D the XOR, with no waits between bytes | `OUT` 'D', 07h, 00h, `tpi:dir`, XOR | | |
| 12 | Pico | eleven words captured; the XOR checked; the text decoded; `cmd_word = "TPI:DIR"` | | [] / [] / 00 | a bad XOR: `FAIL_CMD(2)`, Report R; undecodable: `FAIL_CMD(5)`, C; a second of silence: Y `FB`, T |
| 13 | 2068 | PICO_TRANSACT (2274h): WAIT_PICO_READY | reads 0Fh | | |
| 14 | Pico | the card gate: `TPI:DIR` needs the card; `sd_present` true, so no probe ([../firmware/tspico-bus.md](../firmware/tspico-bus.md#sd_neededload_cmd-cmd_word-cmd_exec-sa_funct)) | | | no card: see the variant below |
| 15 | Pico | `SA_funct["TPI:DIR"]` → `DIR(pre, cmd)`: `LISTING_CHECK()` — the card mounted (MQ parked), the folder re-read if it changed, `DEACTIVATE_SD` + `ACTIVATE_MQ` ([../firmware/tspico-commands.md](../firmware/tspico-commands.md#dirpre-cmd)) | | [] / [] / 00 | the 2068 is in step 13's wait meanwhile; a slow card is fine within ~19.9 s ([sd-handover.md](sd-handover.md)) |
| 16 | Pico | `SEND_MSG2(CAT_COLOUR(lista), 1, …)`: page 1 built in RAM — `86h`, `01h`, `0Dh 0Dh`, 21 lines, `(nn%) Scroll? (Y/n)`, `00h` — and sent by `CMD_SEND`: the first bytes in TX, **then** READY, the rest by DMA ([../firmware/tspico-messages.md](../firmware/tspico-messages.md#send_msg2msg-st-expandkeywordstrue-colourfalse)) | | [86 01 0D 0D] / [] / FF | READY before the bytes: the Z80 reads 00h, Report J |
| 17 | 2068 | C_END_TAIL (227Fh): reads the status: 86h → `DEC A` → the function chain → `FN_86_YN_PROMPT`: reads its own status (01h), opens the screen, prints the page byte by byte, blind, to the `00h` ([../rom/exrom-chunk1.md](../rom/exrom-chunk1.md#fn_86_yn_prompt-21e3h)) | `IN` × the page | [rest…] / [] / FF | an empty FIFO mid-page prints nothing more of it (00h ends the text) |
| 18 | 2068 | GET_KEY_AND_SEND: waits for no key, then a key (BREAK tested), then SEND_KEY: WAIT_PICO_READY, `OUT` the key | `OUT` 'Y' | [] / [59] / 00 | BREAK here: `BRK_ABORT` (below) |
| 19 | Pico | `CMD_KEY()` returns 'Y'; the next page: 19 × (`08h 20h 08h`) to erase the prompt, the text, … `CMD_SEND` again: bytes, then READY | | [08 20 08 08] / [] / FF | |
| 20 | 2068 | YN_LOOP_GUARD (22A1h): WAIT_PICO_READY, then the next page | | | a timeout here: Report J (v1.5w's guard) |
| … | | steps 17–20 for each page | | | |
| 21 | Pico | the last page ends `03h` instead of `00h`; `CMD_DRAIN()` waits until the Z80 has read it all | | [] / [] / FF | |
| 22 | 2068 | PRINT_STRING_FROM_PICO meets `03h` → the loop's end: the function returns its status, 1 → A = 0 | | | |
| 23 | Pico | `PROCESS_CMD`'s tail: TX empty, RX drained, **`MQ.put(0x01)`**, the pre-header channel armed, `MQ_STATUS("idle")` | | **[01] / [] / FF** | |
| 24 | 2068 | STATUS_OK: "0 OK"; back through 01EAh → HOME 24C7h, the end-of-statement check | | | |

The link is back where it started: TX [01], RX empty, Y READY + IDLE.

## The variants

### A bare status (VERBOSE off)

Most handlers answer through `SEND_MSG`. With VERBOSE off and no forced
message, step 16 is `CMD_PUT(st)` / `MQ_READY()`: TX [st]. Step 17 reads it:
01h → "0 OK"; 02h–0Ah → `STATUS_TO_REPORT` → the report
([../rom/exrom-driver.md](../rom/exrom-driver.md#status_to_report-1bf3h)).
`tpi:nop` is the shortest: `MQ.put(0x01)` / `MQ_READY()`.

### A message (81h)

VERBOSE on, or a forced message (`NO_CARD_MSG`, `tpi:path`, the show forms):
TX gets `81h`, the status, `0Dh`, the text, `00h`. The ROM's function 81h
reads its status, opens the main screen and prints to the `00h`; the
status is the result ([../firmware/tspico-messages.md](../firmware/tspico-messages.md#send_msgmsg-msg1-st-forcedisplayfalse)).

### A Y/N question (`tpi:rm name`)

`RM` checks the name with the card (`SD_CALL(RM_CHECK)`), then
`SEND_MSG_PROMPT_YN('Remove "name" (y/N)?')`: `86h`, `01h`, `0Dh`, the
prompt, `00h`. The ROM prints it and sends a key. `N`: the ROM leaves its
loop and reads nothing more; the firmware sends nothing more either
(`MQ_READY` only). Anything else: the firmware sends the echo and `03h`,
and only after the exchange has ended does it remove the file (another
`SD_CALL`) — so the answer to the question is the whole answer the 2068
sees; the removal's result goes to the log
([../firmware/tspico-commands.md](../firmware/tspico-commands.md#rmpre-cmd)).
Rule: **nothing may be sent after a builder that waited for a key.**

### A mount: `LOAD "tpi:games.tap"`

The same up to step 12, with TADDR 1 (the ROM sends LOAD's T_ADDR). The
firmware's dispatch takes `load_cmd`: `LOAD_TPI("games.tap")` finds the
name (or a number, or a wildcard), copies the file to `/TMP/temp.tap` on the
Pico's flash, builds the block table ([../firmware/tspico-files.md](../firmware/tspico-files.md#load_tpiname-only_tapfalse-freshfalse)),
and `SEND_MSG` answers. The copy can take seconds — the 2068 is in step 13's
wait. The next `LOAD ""` is [the LOAD flow](load.md).

### An external command (`SAVE "tpi:.fact"`)

Not in `SA_funct`; found in `EXT_SA_FUNCT` and called as
`f(MQ, TSP, pre, cmd)`. The card gate does not apply. The handler answers
with the same helpers (`tp.SEND_MSG`, `CMD_PUT`), and the tail is the same
([../firmware/extcmd.md](../firmware/extcmd.md)).

### No card

At step 14 `TSP.sd_present` is false: `SD_PROBE()` mounts once (~0.5 s; a
card that has come back is set up). Still none: `NO_CARD_REPLY("TPI:DIR")`
— `SEND_MSG(NO_CARD_MSG, "", 10, True)`: "No SD card. Insert one and try
again.", always shown, Report J. For the ROM 2.1 channel commands the answer
is `CH_REPLY(10)`, a bare J. Commands in `SD_FREE` (`tpi:info`, `tpi:boot`,
the printer settings …) run as usual.

### An unknown word

`SEND_MSG("Unrecognized command: TPI:XYZ", 'SAVE "tpi:help" for info', 5)`:
Report C. The four switch words (`tpi:tape`, `tpi:sdcard`, `tpi:picopt`,
`tpi:ts2040`) never get here: the ROM handles them at step 2
([../rom/sysvars.md](../rom/sysvars.md#5ddbh-tpmode-peek-24027)).

## What goes wrong, and where

| Failure | Detected by | The 2068 sees |
|---|---|---|
| no Pico, or one that never says READY | WAIT_PICO_READY, ~19.9 s | J |
| an empty TX when the ROM reads (READY before data) | the `AND A` after the read | J (status), or a cut-off page |
| a pre-header or body cut short | the firmware's capture, 1 s | T (RECOVERED) |
| a damaged body | the firmware's XOR check | R |
| a handler that raises | `PROCESS_CMD`'s `except` → `FAIL_CMD(10)` | J |
| BREAK at a "Scroll?" or a Y/N key wait | `KEYWAIT` → `BRK_ABORT` (OUT 0Fh, 03h); the firmware's `CMD_KEY` raises `CmdAbort` → `CMD_FLUSH` → the tail's READY + IDLE | D ([break-and-recovery.md](break-and-recovery.md)) |
| the 2068 stops reading (reset mid-listing) | `TX_ROOM`/`STREAM_DMA` stall, 10 min — or at once on the next SYNC | the next command after a reset: T |

## Where to read more

- The handlers: [../firmware/tspico-commands.md](../firmware/tspico-commands.md),
  [../firmware/tspico-disk.md](../firmware/tspico-disk.md).
- The answer builders: [../firmware/tspico-messages.md](../firmware/tspico-messages.md).
- The ROM's side: [../rom/exrom-driver.md](../rom/exrom-driver.md),
  [../rom/exrom-chunk1.md](../rom/exrom-chunk1.md).
- Byte by byte: [PROTOCOL.md §5](../../PROTOCOL.md#5-commands-b-taddr-0).
