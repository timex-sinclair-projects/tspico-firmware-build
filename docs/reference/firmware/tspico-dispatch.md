# TS/tspico.py (part 3) — the dispatcher

Source: [`src/TS/tspico.py`](../../../src/TS/tspico.py), lines 4763–4840
(`LOAD_CONFIG`), 5612–5708 (the printer path), 5788–6124 (`FAIL_CMD`,
`PROCESS_CMD`) and 6132–7313 (`TS2068_IO`, `ZX_TPI`, `ZX48_IO`).

This part is the firmware's main program. `TS2068_IO` is what `main.py`
calls and never returns from: it sets the board up, then loops, taking one
ten-byte pre-header at a time from the Z80 and handing it to a handler.
`PROCESS_CMD` is the handler for `tpi:` commands; `PRINT_IO` for the virtual
printer; `ZX48_IO` is the second loop the firmware runs while the 2068 is a
ZX Spectrum, and `ZX_TPI` its one command. `LOAD_CONFIG` reads `config.ini`
before any of that. The functions here read and set the state described in
[tspico-state.md](tspico-state.md), take and give back the bus with the
helpers in [tspico-bus.md](tspico-bus.md), print through
[tspico-messages.md](tspico-messages.md), and call the handlers of
[tspico-commands.md](tspico-commands.md) and [tspico-disk.md](tspico-disk.md).
LOAD and SAVE blocks are served by `LOAD_SERVE`, `LOAD_TS` and `SAVE_TS` in
[tspico_io.md](tspico_io.md); the receive and send primitives
(`RX_CAPTURE`, `RxDMA`, `RX_BLOCK`, `STREAM_DMA`, `MQ_TO_IDLE`, `MQ_STATUS`)
are there too. The wire protocol these functions implement is
[PROTOCOL.md](../../PROTOCOL.md); the operations they carry out end to end
are the flows ([command](../flows/command.md), [load](../flows/load.md),
[save](../flows/save.md), [printer](../flows/printer.md),
[break-and-recovery](../flows/break-and-recovery.md), [zx48](../flows/zx48.md)).

Two words used throughout. The **Y register** is the PIO register the Z80
reads on port 0Fh: `0xFF` is READY and IDLE, `0xF7` READY with a
transaction open ("mid"), `0xFB` READY and IDLE with RECOVERED low, `0` is
BUSY; the PIO drops it to `0` on every Z80 OUT ([pio.md](pio.md), issue #14).
The **pre-load** is the one `0x01` that sits in the TX FIFO between
transactions, which the ROM reads with no wait straight after its
pre-header ([PROTOCOL.md §4.2](../../PROTOCOL.md#42-the-pre-load-byte)).

## Map

| Symbol | Line | Role |
|---|---|---|
| `LOAD_CONFIG()` | 4763 | `config.ini` → the dictionary `PICO_STATUS` is built from; the one-shot boot slot |
| `PRINT_FLUSH()` | 5612 | the buffered printer text → `/VLPRINT/PRNnnnn.TXT` |
| `COPY_BMP(scr, mode, colour)` | 5644 | a COPY body → `/VSCREEN/SCRnnnn.BMP` |
| `PRINT_IO(pre)` | 5665 | one printer transaction: an LPRINT character, or COPY |
| `FAIL_CMD(status)` | 5788 | a command that failed: one status byte, on a bus in a known state |
| `PROCESS_CMD(pre, SA_funct, EXT_SA_FUNCT)` | 5840 | a `'B'` pre-header: the body, the lookup, the handler, the tail |
| `TS2068_IO()` | 6132 | the board setup and the service loop |
| `ZX_TPI()` | 6995 | the ZX ROM's `'T'` command: `LOAD "tpi:name"`, `SAVE "tpi:dir"` |
| `ZX48_IO(pre)` | 7133 | the Spectrum-mode loop |

`ZX_REPORT` (line 6991), the status-to-ERR_NR table `ZX_TPI` uses, is a
module variable: [tspico-state.md](tspico-state.md).

## `LOAD_CONFIG()`

Reads `config.ini` and returns the dictionary `TS2068_IO` builds
`PICO_STATUS` from, filling in every missing key, refusing a bad `ROM_SM`,
and turning a non-default boot slot into a one-shot.

What it does:

1. `TLM`, then `json.load` on `config.ini` — a relative path; at boot the
   current directory is `/`, and `TS2068_IO` only changes it after this
   call. Any failure (no file, bad JSON) is a `LOG` at level 1 and an empty
   dictionary. `LOG` works before `TSP` exists; it did not until the
   2026-09-30 audit, and a corrupt `config.ini` then crashed the boot
   ([audit_fixes_hosttest.py](../../../src/test/audit_fixes_hosttest.py),
   `test_log_before_tsp`).
2. Fills in the defaults. Every key missing from the file is added and
   `defaulted` set:

   | Key | Default | Meaning |
   |---|---|---|
   | DCK_SLOT | `0` | flash/SRAM slot of the DOCK image at start-up |
   | ROM_SLOT | `1` | slot of the ROM image at start-up |
   | ROM_SM | `10` | the word `set_ctrl` is given: DOCK memory × 4 + boot memory, 1 = SRAM, 2 = flash |
   | LOG_LEVEL | `2` | `LOG` keeps entries at this level and above (0 info … 3 critical) |
   | VERBOSE | `False` | `SEND_MSG` prints its text only when true or forced |
   | ZX_TAPE_COMPAT | `False` | ZX48 mode: `LOAD_ZX_C` (the whole tape in RAM) instead of `LOAD_ZX` |
   | TELEMETRY | `False` | `main.py` reads this for `TLM_ENABLED`; `LOAD_CONFIG` only writes the default |
   | FW_VERSION | the module's `FW_VERSION` | written for information; `PICO_STATUS` ignores the file's value |
   | ROM_VERSION | the module's `ROM_VERSION` | the ROM this firmware ships with; shown by `tpi:info`, nothing else reads it |

   The shipped [`src/config.ini`](../../../src/config.ini) holds exactly
   these nine keys. The comment at line 4776 notes that `PICO_STATUS`
   carries a second copy of the defaults (it does, as `try/except` fallbacks)
   and that there should be one; there are still two.
3. `ROM_SM` must be one of 5, 6, 9, 10 — the four combinations `tpi:boot`
   and `tpi:dock` can set, since MEM 3 was refused in #91. Anything else
   (7, 11, a string from a hand-edited file) is logged at level 2 and
   replaced by 10. The old test was `<= 4 or 8 or 12` and raised
   `TypeError` on a string, which stopped the boot (audit §2 #18;
   `test_rom_sm` in the audit test).
4. The one-shot. `boot_mem = ROM_SM & 3`. If `ROM_SLOT` is not 1 or
   `boot_mem` is not 2 (flash), the configured pair is remembered, the
   dictionary is rewritten with `ROM_SLOT = 1` and `ROM_SM = (ROM_SM & 12) + 2`
   (the DOCK bits kept), and `defaulted` set.
5. If anything was defaulted, the dictionary is written back with
   `json.dump`; a failure to write is a level-2 `LOG` and a synchronous
   `SAVE_LOG`. Then, if a one-shot was taken, the remembered `ROM_SLOT` and
   `ROM_SM` are put back into the dictionary that is *returned*, so this run
   boots from them while the file already says flash slot 1.
6. `SAVE_LOG()` — synchronous, on core0; nothing else is running yet.

Why: `tpi:boot` to another slot is meant to last one power cycle — a ROM
under test that hangs must not come back on the next boot
([user-manual.md ch 8](../../manual/user-manual.md#82-boot-and-dock)).
[commands_hosttest.py](../../../src/test/commands_hosttest.py) `test_boot`
pins the round trip: BOOT saves memory and slot, `LOAD_CONFIG` returns them
once and writes flash slot 1 back, and the start after that boots slot 1.

Returns: the dictionary. State: reads and rewrites `/config.ini`; appends to
`/activity.log` through `SAVE_LOG`. Reads `BUILD_VERSION`, `FW_VERSION`,
`ROM_VERSION`. Caller: `TS2068_IO`, once. The `tpi:boot` and `tpi:dock`
handlers (`MEMBOOT`, `MEMDOCK`) write the keys this reads.

Beware: the bare `except` on the read swallows everything, including a
`MemoryError`; a key with the wrong *type* other than `ROM_SM` (say
`"VERBOSE": "no"`) goes into `PICO_STATUS` as it is.

## `PRINT_FLUSH()`

Appends `PRT.buf`, the text the virtual printer has accumulated, to the open
capture file on the card, opening the next `/VLPRINT/PRNnnnn.TXT` when none is
open.

What it does: nothing if `PRT.buf` is empty. Otherwise `ACTIVATE_SD()`, which
parks the bus state machine on `NULL_SM` and gives GPIO 2–4 to SPI; if
`prn_path` is `None`, `next_name(VLPRINT, "PRN", "TXT")` picks the next free
number; the buffer is appended, logged at level 0 ("Printer: n bytes -> path")
and replaced by an empty `bytearray`. On any exception the failure is logged
at level 2 with the byte count kept — unless the buffer has passed 32768
bytes, when it is dropped so a missing card does not eat the heap. The
`finally` is `DEACTIVATE_SD()` then `ACTIVATE_MQ()`: the bus state machine is
rebuilt, TX is empty, Y is BUSY.

Why the rule in its docstring: while the card has the bus a Z80 that starts a
transaction reads a floating bus, so this may run only while the Z80 is parked
in a READY wait, which the ROM allows ~20 s
([PROTOCOL_FROM_ROM.md](../../rom-analysis/PROTOCOL_FROM_ROM.md#the-timeout-is-20-seconds-and-this-is-the-most-misread-number-in-the-rom)).
The three places that qualify are the three callers: `PRINT_IO` before it
says READY (once `len(PRT.buf) >= PRINT_FLUSH_AT`, 4096), the `tpi:opprint`
and `tpi:clprint` handlers (`PRN_OPEN`, `PRN_CLOSE`), and `TS2068_IO` after
any other pre-header, before that pre-header's handler says READY. Because
it leaves TX empty, a caller that had a status staged has to put it back:
`TS2068_IO` does, with `PRELOAD_READ`.

State: `prn_path` (global; `PRN_CLOSE` sets it to `None`, `SD_REVALIDATE`
too when a different card is seen), `PRT.buf`, `sd_active` through the
bus helpers. [printer_io_hosttest.py](../../../src/test/printer_io_hosttest.py)
pins the file name, the mid-printout flush at `PRINT_FLUSH_AT`, the flush on
`tpi:clprint`, and that `tpi:opprint` starts the next numbered file.
The file format is [printer.md](printer.md); the user's view is
[user-manual.md ch 7](../../manual/user-manual.md#chapter-7-the-virtual-printer).

## `COPY_BMP(scr, mode, colour)`

Writes one COPY body as the next `/VSCREEN/SCRnnnn.BMP`, at the size
`SAVE "tpi:bmp"` chose. Returns `True` if the file was written.

What it does: `ACTIVATE_SD()`; `next_name(VSCREEN, "SCR", "BMP")`; the scale
factors are `sx = max(1, bmp_size[0] // w0)` with `w0` 512 for mode 3 (the
512-column hi-res screen) and 256 otherwise, and `sy = max(1, bmp_size[1] // 192)`;
`write_bmp(f, scr, mode, colour, sx, sy)` ([printer.md](printer.md)) does the
encoding and returns the pixel size, which is logged at level 0. Any
exception: level-2 `LOG`, `False`. `finally`: `DEACTIVATE_SD()`,
`ACTIVATE_MQ()` — the same bus rule as `PRINT_FLUSH`, and the same result:
TX empty, Y BUSY.

Takes: `scr`, a `memoryview` of the screen bytes from the body (6912 bytes
for mode 0, 15104 for the others: both screens, 4000h–7AFFh); `mode`, the
pre-header's `pre[4]`; `colour`, `pre[3]`, the hi-res colour byte. Reads
`bmp_size` (default `(512, 384)`; `PRN_BMP` sets it). Only caller:
`PRINT_IO`. The test writes the default size and checks 98422 bytes.

## `PRINT_IO(pre)`

One printer transaction. The ROM sends every LPRINT or LLIST character as its
own `'B'` pre-header with TADDR 5, and COPY as TADDR 4 or 6; the dispatcher
hands all of them here, SYNC and all ([PROTOCOL.md §8](../../PROTOCOL.md#8-printer-transactions);
the wire format, captured on hardware, is in [printer.py](../../../src/TS/printer.py)'s
header).

The pre-header's fields here: `pre[1]` 5 = a character, 4 or 6 = COPY;
`pre[3]` the character (TADDR 5) or the hi-res colour byte (COPY); `pre[4]`
the screen mode (COPY); `pre[7..8]` the body length, 0 for a plain character,
8 for a character of 80h or more (its pattern), 6912 or 15104 for COPY.

What it does:

1. `n = pre[7] | pre[8] << 8`. If `n` is not zero: `body = bytearray(n + 4)`,
   then `RX_BLOCK(MQ, body, n + 4, 1000, 1000, "mid")` — the Y register goes
   to `0xF7` (READY, transaction open) once the receiver is listening, and
   the body `'D'`, length low, length high, data, XOR arrives, by DMA where
   there is one. A result other than `RXB_OK` (`RXB_ABORT`: a port-0Fh
   write, BREAK; `RXB_STALL`: a second of silence) is `MQ_TO_IDLE(MQ,
   recovered=(why != RXB_ABORT))` — both FIFOs emptied, one `0x01` staged,
   Y = `0xFF` after a BREAK or `0xFB` after a stall — a level-1 `LOG`, and
   return. Otherwise `ok` is the XOR of `body[0..n+2]` matching
   `body[n+3]`, and `body[0] == 0x44`.
2. `status = _1_OK`. For a character (`pre[1] == 5`): `PRT.feed(pre[3])`
   turns it into text in `PRT.buf` ([printer.md](printer.md)); the pattern
   body of a UDG is read and discarded: its XOR is computed but not acted
   on, so a bad body still answers status 1. If the buffer has reached
   `PRINT_FLUSH_AT`, `PRINT_FLUSH()` — the Z80 is waiting for READY, so the
   SD access is allowed; afterwards TX is empty and Y BUSY, which is what the
   next step expects anyway. For COPY, `COPY_BMP(memoryview(body)[3:n + 3],
   pre[4], pre[3])` writes the file; if the body was bad, missing, or the
   write failed, `status = _2_R_Tape_load`.
3. If there was a body, `MQ.put(status)`: the final status the ROM reads
   at 223Eh after the body. Then `MQ.put(0x01)`, the next transaction's
   pre-load, and `MQ_STATUS(MQ, "idle")`: Y = `0xFF`.

So a plain character ends with TX = `[01]` and READY: the Z80 read this
transaction's status (the pre-load) straight after its pre-header and was
only waiting for READY. A UDG or a COPY ends with TX = `[status, 01]`.
`MQ.put` is the blocking put, safe here because TX is empty and two bytes
fit the four-deep FIFO.

Why one transaction per call: this function used to loop reading the next
pre-headers itself; on the 1.8b ROM the per-character SYNC misaligned it
after the first character, and the first non-printer pre-header ended the
loop and was swallowed. Why the dispatcher does not say READY before
calling it: the same rule as for LOAD and SAVE (see `TS2068_IO`); the ROM
reads the pre-load with no wait and then waits for READY.

Callers: `TS2068_IO` only. Callees: `RX_BLOCK`, `MQ_TO_IDLE`, `MQ_STATUS`
([tspico_io.md](tspico_io.md)), `PRT.feed`, `PRINT_FLUSH`, `COPY_BMP`.
[printer_io_hosttest.py](../../../src/test/printer_io_hosttest.py) pins:
each character is its own transaction with TX = `[01]` and status `FF`
after it; the UDG body is taken and the Z80 gets status 01; COPY writes the
BMP with status 01; BREAK in the middle of a COPY body goes back to idle with
no file. The flow is [flows/printer.md](../flows/printer.md).

## `FAIL_CMD(status)`

The recovery answer for a command that failed inside `PROCESS_CMD`: put the
bus and both FIFOs into a known state and hand the Z80 exactly one status
byte (issue #42).

What it does:

1. If `sd_active` — the handler died while the card had the bus (`MQ` parked
   on `NULL_SM`, GPIO 2–4 on SPI) — `DEACTIVATE_SD()` then `ACTIVATE_MQ()`,
   in a `try` that ignores any exception. Without this the status would go
   into the parked state machine and the TS-Pico would be deaf for the rest
   of the session ([sd_wedged_hosttest.py](../../../src/test/sd_wedged_hosttest.py)).
2. Empties TX (`pull (noblock)` / `mov (osr, null)` through `MQX`, at most
   64 times) and RX (`MQ.get()`, at most 64 times). Bounded on purpose: this
   is the recovery path, and an unbounded drain here would be the hang it
   exists to prevent. The FIFOs are four deep.
3. `MQ.put(status)`; `MQ_READY()`. TX = `[status]`, Y = `0xFF`.

Why not `SEND_MSG`: with `VERBOSE` on it streams text and, if the Z80 has
already given up, nothing drains TX and the Pico would wait in `MQ.put`.
One byte always fits. The explanation goes to `/activity.log` instead. Why
clear TX first: a handler may have written part of a response before it
raised; a partial response followed by a status shifts every later byte —
the orphan-byte family in [src/CLAUDE.md](../../../src/CLAUDE.md).

Callers, and the status each sends: `PROCESS_CMD` with `_2_R_Tape_load` on a
bad body checksum, `_5_C_Nonsense` on a body that does not decode, and
`_10_J_Invalid_IO` for any exception a handler lets out. `PROCESS_CMD`'s
tail then waits for the Z80 to read the byte and stages the pre-load; this
function never does. [process_cmd_hosttest.py](../../../src/test/process_cmd_hosttest.py)
pins that a partial response is cleared before the status
(`test_fail_cmd_clears_partial_response`) and that each path leaves exactly
one pre-load afterwards.

## `PROCESS_CMD(pre, SA_funct, EXT_SA_FUNCT)`

The handler for a `'B'` pre-header that is not printer traffic: receive and
check the body, find the command, run it, and leave the link in step for the
next command whatever happened. The exchange is [PROTOCOL.md §5](../../PROTOCOL.md#5-commands-b-taddr-0);
the walk-through is [PROTOCOL_GUIDE.md §4](../../PROTOCOL_GUIDE.md#4-a-command-step-by-step)
and [programmers-manual.md 10.2](../../manual/programmers-manual.md#102-from-pre-header-to-answer).

### What it starts from

The dispatcher has taken all ten pre-header bytes into `pre`; Y is BUSY
(every one of those OUTs dropped it); the Z80 read the pre-load from TX with
no wait straight after its tenth byte and is now in WAIT EXECUTION, polling
port 0Fh for READY, with ~20 s to spare. TX is empty. The dispatcher did not
say READY: since issue #51 stage 4 this function does, once it is listening,
because the Z80 sends the whole body the moment it sees READY, ~35 µs a byte
into a four-deep RX FIFO, and the dispatcher used to say it before its own
logging.

The pre-header fields as the ROM builds them
([PROTOCOL_FROM_ROM.md](../../rom-analysis/PROTOCOL_FROM_ROM.md#the-b-pre-header-as-actually-built)):

| Byte | Field | Used here as |
|---|---|---|
| 0 | `'B'` (42h) | — (the dispatcher chose this handler on it) |
| 1 | TADDR | `load_cmd`: 0 = `SAVE "tpi:…"` command, 1–3 = `LOAD "tpi:name"`, a mount |
| 2 | bank (FFh = HOME) | ignored |
| 3–4 | PMR1, the first `CODE` number, little-endian | the handlers' `par1` (`PARAMS(pre)`) |
| 5–6 | PMR2, the second `CODE` number | `par2` |
| 7–8 | length of the command text | the body size |
| 9 | XOR of bytes 0–8 | **not checked** |

What it does first: `TSP.zx48 = False` (the `tpi:zx48` handler sets it
`True`; see `ZX48_IO`); `load_cmd = pre[1]`. Two assignments are dead:
`cur_fname = TSP.f_name` and `wrt = MQ.put` are never read again.

### The body

`long = pre[7] + 256 * pre[8] + 4`: the body is `'D'`, length low, length
high, the text, then an XOR of all of those (EXROM 224Dh–2274h). It used to
be read as `len + 3`, which left the checksum byte in RX to be found after the
handler had said READY — it then dropped Y to BUSY, and only the tail's RX
drain disposed of it.

`raw = array("H", bytes(2 * long))`; `got = RX_CAPTURE(MQ, raw, long,
BODY_READ_TIMEOUT_MS, "mid")`. `RX_CAPTURE` sets Y to `0xF7` (READY, not
IDLE) once it is listening, then takes the burst, by DMA where there is one,
into nine-bit words. It returns `long` when all arrived; `k < long` after a
second of silence; `-k` when word `k-1` was a write to port 0Fh (BREAK or a
SYNC: the Z80 has stopped and waits for READY + IDLE). On anything but
`long`: `MQ_TO_IDLE(MQ, status=False)` — both FIFOs emptied, one `0x01`
staged, Y left alone — a `TLM` with the words, a `LOG` (level 1 for an
abort, 2 for a timeout), `MQ_STATUS(MQ, "idle")` after an abort or
`"recovered"` after a timeout, and return. This path is **outside** the
`try/finally` below on purpose: it stages its own pre-load, and the
`finally` would add a second one — the orphan byte that is Report R on the
next data block (`test_body_read_timeout_writes_one_preload`).

The 1000 ms limit exists for the cascade its comment describes (a Z80 that
reported J on the pre-load and never sent a body; the old `MQ.get()` loop
then hung for good). The comment still describes that blocking loop; the code
has been `RX_CAPTURE` since #51.

The low byte of every word goes into `cmd`, a `bytearray(long)`. Then the
first `TLM`: the Z80 is now waiting, so there is no time pressure.

### The checksum, the decode, the lookup

Everything from here to the dispatch runs inside `try … except CmdAbort …
except Exception … finally`, so the tail always runs (issue #42; before it,
a handler that raised — `MOUNT_FILE`'s unguarded `os.stat` with no card was
the easy one — skipped the tail, and the *next* command read `0x00` for its
pre-load: Report J one command late). `cmd_abort = 0` and `cmd_exec = "?"`
are set before the `try` so the tail can log them.

1. The XOR of `cmd[0 .. long-2]` must equal `cmd[long-1]`. A mismatch is a
   damaged or misaligned body: level-2 `LOG`, `FAIL_CMD(_2_R_Tape_load)` —
   Report R, as a LOAD parity error — and return
   (`test_bad_checksum_reports_r`, `test_checksum_byte_is_consumed`).
2. If `TSP.listing_stale` (a ZX48 SAVE wrote into the folder),
   `REFRESH_LISTING()` re-reads it — an SD access, allowed because the Z80
   is waiting; it leaves the bus with the MQ and Y BUSY.
3. The text is decoded: `cmd = "D.." + bytes(cmd[3:long - 1]).decode()`.
   Only the text goes through `decode`: `'D'` and the length are binary, and
   a length byte of 128 or more is not UTF-8. The `"D.."` keeps every
   handler's `cmd[3:]` and `cmd[7:]` offsets where they were
   (`test_long_command_decodes`). A decode error is garbage on the wire:
   level-2 `LOG`, `FAIL_CMD(_5_C_Nonsense)`, return
   (`test_undecodable_body_preserves_preload`).
4. `cmd_exec = cmd[3:].upper()` — the whole text, `TPI:` included;
   `rest_cmd = cmd[7:]` — after `tpi:`, case kept; `cmd_word` is `cmd_exec`
   up to the first space. The dictionary keys are `"TPI:DIR"` and so on;
   `getArgs(cmd)` gives a handler the rest.

### The card gate

`SD_NEEDED(load_cmd, cmd_word, cmd_exec, SA_funct)` says whether this
command needs the card: every mount does; `TPI:HELP` only with a topic (a
file on the card); otherwise a built-in command that is not in `SD_FREE`.
An external command never counts as needing it. If it does and
`TSP.sd_present` is false, `SD_PROBE()` looks once more (one mount attempt,
~0.5 s; it leaves the bus with the MQ and Y BUSY, and a card that has come
back is set up on the way). Still none: `NO_CARD_REPLY(cmd_word)` — the
level-1 `LOG`, then `CH_REPLY(_10_J_Invalid_IO)` for the `SD_QUIET`
channel commands (a printed message mid-statement would move the ROM's
channel) or `SEND_MSG(NO_CARD_MSG, "", _10_J_Invalid_IO, True)` for the
rest: "No SD card. Insert one and / try again." is always shown, with
Report J, the report that means the device is not there
([sd_state_hosttest.py](../../../src/test/sd_state_hosttest.py)).

### The dispatch

- `load_cmd` set: `msg, rest_cmd, status = LOAD_TPI(rest_cmd)` mounts the
  named file (or listing number, or wildcard; [tspico-files.md](tspico-files.md)),
  and `SEND_MSG(msg, rest_cmd, status, " files match: " in msg)` answers —
  a bare status unless VERBOSE, except the "n files match" message, which
  says what to do and is always shown.
- Otherwise `cmd_word` is looked up in `SA_funct` first, then
  `EXT_SA_FUNCT`. A built-in handler is called as `EXEC(pre, cmd)`, an
  external one as `EXEC(MQ, TSP, pre, cmd)` ([extcmd.md](extcmd.md)). Neither
  returns anything; each gives its one answer itself. Not found:
  `SEND_MSG("Unrecognized command: …", 'SAVE "tpi:help" for info',
  _5_C_Nonsense)` and a level-2 `LOG`.

### How a handler's answer reaches the Z80

A handler's answer goes through `CMD_PUT`, `CMD_SEND`, a `CmdOut` page, or
the message functions built on them ([tspico-bus.md](tspico-bus.md),
[tspico-messages.md](tspico-messages.md)): the first bytes into TX, then
`MQ_READY()` (or `CH_READY()`), then the rest, paced by the Z80's reads.
Y is BUSY when the handler starts (the body's OUTs), and stays wherever the
handler's last `MQ_READY`/`CH_READY` or the Z80's last OUT left it until the
tail. The rules a handler must keep — one answer, never the pre-load,
`CMD_*` not `MQ.*`, SD work inside `SD_CALL`, errors as statuses — are
[PROTOCOL.md §11](../../PROTOCOL.md#11-writing-a-command-handler).

### The two exception handlers

- `except CmdAbort as _a`: the Z80 stopped this command's output — BREAK
  at a key wait (the ROM's port-0Fh write), or it stopped reading
  (`TX_ROOM`'s stall). `CMD_FLUSH()` empties both FIFOs (bounded, no
  pre-load); `cmd_abort = _a.args[0]` (1 for the 0Fh write, 3 for the
  stall); a `LOG` at level 1 or 2. `CmdAbort` is a `BaseException` so a
  handler's `except Exception` cannot swallow it.
- `except Exception as _e`: protocol first, diagnostics second.
  `FAIL_CMD(_10_J_Invalid_IO)` allocates nothing and cannot block, so it
  runs before the `LOG` (level 3) and `TLM`, which sit in their own `try` —
  if the handler died of `MemoryError`, logging may fail too, and the one
  thing that must not fail is getting a byte to a Z80 in WAIT EXECUTION
  (`test_handler_exception_preserves_preload`).

### The tail (`finally`)

1. Wait for TX to empty — the Z80 reading the last bytes of the answer —
   for at most 3000 ms by the clock (audit §4: it used to be a loop count
   whose length depended on the MicroPython version); past that, a `TLM`
   "STUCK draining tx" and on.
2. Drain RX with `MQ.get()`, at most 64 words: a Z80 that keeps writing
   cannot hold the tail here.
3. `MQ.put(0x01)`: the pre-load for the next command. This is the V6 chain
   ([DUAL_PORT_DEVELOPMENT.md §7](../../DUAL_PORT_DEVELOPMENT.md#7-folding-the-v6-pattern-into-production-firmware),
   [DEVELOPER_GUIDE.md §7](../../DEVELOPER_GUIDE.md#7-the-pio--micropython-ready-contract)):
   a handler never writes it (`test_successful_handler_writes_one_preload`).
4. `RXD.arm(MQ)` if there is a DMA channel: the pre-header capture is armed
   *before* IDLE is said, as the SYNC path does, because the Z80 sends its
   next command the moment it sees IDLE and the gap between here and the top
   of the main loop overflowed the FIFO ("Partial pre-header 4/10", Report T,
   hardware 2026-10-03).
5. `MQ_STATUS(MQ, "recovered" if cmd_abort == 3 else "idle")`: Y = `0xFB`
   when the Z80 went silent, else `0xFF`. After a BREAK (`cmd_abort == 1`)
   the ROM's `BRK_ABORT` is waiting for exactly this READY + IDLE before it
   raises Report D ([exrom-sync.md](../rom/exrom-sync.md)).
6. A level-0 `LOG` with the command and both FIFO depths.

So every exit leaves TX = `[01]`, RX empty and Y READY. An answer the ROM
follows at once with another command must have said `CH_READY` (`0xF7`),
not `MQ_READY`, so the ROM waits for *this* IDLE before its SYNC
([PROTOCOL.md §5.6](../../PROTOCOL.md#56-the-tail-and-ready-vs-idle)).

Takes: `pre` (the 10-byte `bytearray`), the two tables. Returns nothing.
State: `TSP.zx48`, `TSP.listing_stale` (via `REFRESH_LISTING`); `RXD`; the
globals `files`/`files_upper` are declared but only the callees change them.
Caller: `TS2068_IO`. Callees: `RX_CAPTURE`, `MQ_TO_IDLE`, `MQ_STATUS`,
`FAIL_CMD`, `REFRESH_LISTING`, `SD_NEEDED`, `SD_PROBE`, `NO_CARD_REPLY`,
`LOAD_TPI`, `SEND_MSG`, `CMD_FLUSH`, the handlers.

Tests: [process_cmd_hosttest.py](../../../src/test/process_cmd_hosttest.py)
(the eight exit paths and their one pre-load),
[cmd_io_hosttest.py](../../../src/test/cmd_io_hosttest.py) (READY is said
here, not by the dispatcher; BREAK or SYNC during the body goes straight back
to idle; a Z80 that stops reading a listing ends in RECOVERED),
[extcmd_hosttest.py](../../../src/test/extcmd_hosttest.py) (external
commands through the real function),
[sd_state_hosttest.py](../../../src/test/sd_state_hosttest.py) (the card
gate), [sd_wedged_hosttest.py](../../../src/test/sd_wedged_hosttest.py)
(a card that fails mid-command).

Beware: the comments headed "DUAL-PORT MIGRATION" predate issue #14 and say
the Y register is "kept at READY for the entire session"; it is not — the PIO
drops it on every OUT, which is why the explicit READYs exist. The code wins.

## `TS2068_IO()`

The main program: everything from the first `LOG` after power-on to the
service loop that never ends. `main.py` calls it inside a `try` that logs a
fatal error to `/activity.log` and USB and then stops
([boot.md](boot.md)). Read it with [flows/boot.md](../flows/boot.md) beside
it.

### Globals

It owns `busy` (core1 is writing the log), `dead` (tells `BLINK_LED` to
stop), `kill` (set `False` here and read by nothing: the core1 watchdog that
read it was removed in #71/#72), `files`, `lista`, `log_entries`,
`log_to_serial` (initialised `False`; nothing in the module sets it `True` —
a REPL knob that sends `LOG` to USB instead of the file), `ROM`, `BANK`,
`MQ`, `led`, `TSP`, `alldirs`, `EXT_SA_FUNCT` and, from line 6422, `RXD`.
All are in [tspico-state.md](tspico-state.md).

### Configuration and the log file

`led = Pin(25, Pin.OUT)`. `init_values = LOAD_CONFIG()`; `TSP =
PICO_STATUS(init_values)` — from here `LOG` filters by `TSP.LOG_LEVEL`. If
`/activity.log` is 64 000 bytes or more it becomes `/activity.old` (the old
one removed first) and a level-3 "Starting new log file" opens the new one.
"Starting TS Pico. Memory at startup" and `SAVE_LOG()`.

### The ROM and BANK state machines

```python
ROM = StateMachine(4, set_ctrl, freq=150_000_000, in_base=Pin(0, Pin.IN), jmp_pin=Pin(26),
                   set_base=Pin(21, Pin.OUT), out_base=Pin(19, Pin.OUT))
BANK = StateMachine(5, sel_bank, freq=150_000_000, jmp_pin=Pin(26), out_base=Pin(15, Pin.OUT))
```

Both are started, then given one word each: `ROM.put(TSP.ROM_SM)` — which
memory (flash or SRAM) answers DOCK and ROM accesses, the 5/6/9/10 value
`LOAD_CONFIG` checked — and `BANK.put(TSP.bank_sm)`, `DCK_SLOT * 16 +
ROM_SLOT`, the slot of each. The programs are [pio.md](pio.md); the pins
[hardware.md](../hardware.md). A commented-out alternative (`set_dck` on
state machine 4) maps the DOCK only. These two machines are built once and
never again: the restart path at the end of the loop leaves them alone.
`tpi:boot` and `tpi:dock` feed them new words ([tspico-commands.md](tspico-commands.md)).

Then `gc.collect()` with free-memory `LOG`s (level 0) around it, as after
every stage of the boot; `REMOVE_DIR("/TMP")`, `os.mkdir("/TMP")` (the
mount's scratch folder, [tspico-files.md](tspico-files.md)); `os.chdir('/')`.

### The command table

`SA_funct` is built here, a dictionary from the upper-case command word
(`TPI:` included) to the handler, called as `handler(pre, cmd)`. Its rows,
in table order:

| Word | Handler | | Word | Handler |
|---|---|---|---|---|
| TPI:APPEND | `APPEND` | | TPI:MD | `MDIR` |
| TPI:BLKRCV | `BLKRCV` | | TPI:BOOT, TPI:MEMBOOT | `MEMBOOT` |
| TPI:CD | `CDIR` | | TPI:DOCK, TPI:MEMDOCK | `MEMDOCK` |
| TPI:CLOSE | `UNMOUNT` | | TPI:NOP | `NOP` |
| TPI:DIR | `DIR` | | TPI:PATH | `PATH` |
| TPI:COPY | `DISK_COPY` | | TPI:REW | `REW` |
| TPI:ERASE | `DISK_ERASE` | | TPI:RM | `RM` |
| TPI:FORMAT | `DISK_FORMAT` | | TPI:NEWTAP | `NEW_TAP` |
| TPI:REN | `DISK_REN` | | TPI:TAPDIR | `TAPDIR` |
| TPI:FOPEN | `NATIVE_OPEN` | | TPI:VERBOSE | `VERB_TOGGLE` |
| TPI:CHOPEN | `CH_OPEN` | | TPI:ZX48 | `ZX48` |
| TPI:CHWR | `CH_WRITE` | | TPI:AUTOLF, TPI:AUTOPG, TPI:NOAUTOLF, TPI:NOAUTOPG | `PRN_FLAG` |
| TPI:CHRD | `CH_READ` | | TPI:BMP | `PRN_BMP` |
| TPI:CHCLOSE | `CH_CLOSE` | | TPI:CLPRINT | `PRN_CLOSE` |
| TPI:FFW | `FWD` | | TPI:OPPRINT | `PRN_OPEN` |
| TPI:HELP | `GETHELP` | | TPI:PRNSZ | `PRN_SIZE` |
| TPI:IDIR | `IDIR` | | TPI:CONFIG, TPI:DELETE, TPI:FRESET, TPI:GETCONFIG, TPI:LIST, TPI:MEMINFO, TPI:STOP | `SA_NOT_IMP` |
| TPI:INFO | `GETINFO` | | | |
| TPI:LOG | `GETLOG` | | | |
| TPI:LOGLEVEL | `LOGLEVEL` | | | |

Each handler has its entry in [tspico-commands.md](tspico-commands.md) or
[tspico-disk.md](tspico-disk.md). The comment above the table ("Commands
expecting a name following the command word need a space at the end of
their dictionary key string") is contradicted by the table and by
`PROCESS_CMD`: no key ends in a space, and the command word is cut at the
first space before the lookup. The code wins.

### The external commands

`EXT_SA_FUNCT` comes from `/dev_extcmd.py` on the flash root if there is
one (the same override pattern as `/dev_tspico.py`, [boot.md](boot.md)),
else from the frozen `TS.extcmd` ([extcmd.md](extcmd.md)), else it is `{}`;
each outcome is a level-0 `LOG`. An external handler is called as
`handler(MQ, TSP, pre, cmd)`.

### The LED thread and the SD card

`dead = False`; `_thread.start_new_thread(BLINK_LED, (0.9,))`: core1 blinks
the LED every 0.9 s for the rest of the boot, with `busy = True` while it
runs. Then `ACTIVATE_SD(tries=5)`: five mount attempts 0.5 s apart (a cold
card can refuse and be fine seconds later). The first successful mount runs
`SD_NOTE_CARD` → `SD_REVALIDATE` ([tspico-bus.md](tspico-bus.md)): a missing
`/TAP` folder is made, the current folder and mounted file checked,
`DIR_FILES` and `GET_DIRS` fill the caches. An `OSError` is caught here:
`TSP.sd_present = False`, a level-1 `LOG` "Starting without an SD card".

What "no card" means from here on: `TSP.sd_present` is `False`; `files`,
`dirs`, `lista`, `alldirs` stay empty; `sd_ok` below is false; the idle
heartbeat double-blinks; every command that needs the card is refused by
`PROCESS_CMD`'s gate with "No SD card…" and Report J after one fresh probe,
so inserting a card is all it takes; `LOAD ""` with nothing mounted still
serves the flash's `nofile.tap`. A card that is present but whose folder
could not be listed (`sd_listing_ok` false) is logged as "mounted but
failing; continuing without a directory listing"
([dir_files_eio_hosttest.py](../../../src/test/dir_files_eio_hosttest.py):
this used to be a fatal `OSError` out of the boot).

`dead = True`; `while busy: pass` — safe unbounded, the comment argues,
because `BLINK_LED` only sleeps and toggles and clears `busy` within one
period. `sd_ok = TSP.sd_present and TSP.sd_listing_ok`; `gc.collect()`.

### Handing the bus to the Z80

`DEACTIVATE_SD()` — unmount, `U3_CS` high, GPIO 2–4 driven low — then
`ACTIVATE_MQ()`: `MQ = StateMachine(0, TS_IO_DUAL, freq=30_000_000, …)` on
GPIO 2 (D0) with `jmp_pin` 11 and side-set 12, started, `MQ_BUSY()`. Y is
BUSY, both FIFOs empty, `sd_active` false. `ACTIVATE_MQ` neither stages a
pre-load nor says READY; both were tried and both were bugs
(DUAL_PORT_DEVELOPMENT.md §8 "Bug 1"; the `ready` parameter removed by the
audit).

### The boot-noise flush and the boot pre-load

For 500 ms of silence, any word in RX is taken with `MQ.get()`, logged at
level 0, and the 500 ms restarted. Y is still BUSY, so a Z80 that is already
up waits in its first ready-wait and only noise from its power-on can
arrive. The audit moved this *before* the pre-load (it used to run after
READY, in the window where the 2068's first command could arrive and be
eaten). Then:

```python
MQ.put(0x01)
MQ_READY()
```

The one boot pre-load, and the first READY: TX = `[01]`, Y = `0xFF`. Put
then ready, never the reverse: a READY with an empty TX hands the Z80 `0x00`
and Report J. Every handler ends by staging the next `0x01`, so this one
seeds the chain for the life of the session. It must be here and not inside
`ACTIVATE_MQ`, which also runs mid-command.

### nofile.tap and the last boot messages

`OPEN_NOFILE_TAP()` caches a read handle to `/assets/nofile.tap`, which
`LOAD_TS` serves when nothing is mounted; a missing file is a level-1 warning
that `LOAD ""` will give Report R until the assets are copied. The SD outcome
is logged (OK / mounted but failing / no card), `SAVE_LOG()`, a `gc.collect()`,
"TS Pico initialized OK. Waiting for commands...", `SAVE_LOG()` again, LED
off. `wrt = MQ.put` at line 6407 is assigned and never used.

### The capture buffers and the DMA channel

`pre = bytearray(10)` is what the branches read; `pre_raw = array("I", [0]*10)`
takes the nine-bit words (bit 8 = a port-0Fh write); `rxd = RX_DMA(pre_raw)`
is an `RxDMA` — a DMA channel that, armed while the loop is idle, copies every
word the Z80 writes out of the RX FIFO whatever core0 is doing — or `None`
when there is no `rp2.DMA` or no free channel, in which case the loop polls
with `RX_CAPTURE` ([tspico_io.md](tspico_io.md)). `RXD = rxd` makes it
reachable from `PROCESS_CMD`'s tail. `r1 = range(10)`; `ts = time.ticks_us()`
is the heartbeat clock.

### The loop: catching the pre-header

Two nested `while True`s: the outer one restarts the inner after an
unexpected error (below). Each pass of the inner loop:

```python
if rxd is not None:
    rxd.arm(MQ)
if (rxd.waiting() if rxd is not None else MQ.rx_fifo()) != 0:
```

`arm` is a no-op while the channel is already armed. The test is "has the
Z80 written anything since": with DMA, words landed in `pre_raw`; without,
the FIFO. If not, the pass goes to the idle tail. If so, `ts` is reset and
`got = rxd.take(1000)` or `got = RX_CAPTURE(MQ, pre_raw, 10, 1000)` — no
READY is said for a capture: the Z80 is sending, not waiting. Both return
10 for a whole pre-header; `k` (0 ≤ k < 10) for `k` words then a second of
silence; `-k` when word `k-1` was a port-0Fh write. The two-phase rule
behind this ([src/CLAUDE.md](../../../src/CLAUDE.md)): nothing per word but
test, get, store — the Z80 writes every ~30 µs into a four-deep FIFO. The
DMA channel exists because even that was not enough on v1.29: a GC, a USB
interrupt or a flash write on core1 paused core0 for longer than the FIFO
lasts and the first command after a 2068 power-on lost a byte from the
middle of its pre-header (Report T; `RxDMA`'s docstring). Nothing in this
path allocates; the polling capture's comment explains why not even a bound
method is stored.

### SYNC and BREAK: `got < 0`

A write to port 0Fh. On ROM 2.x that is every transaction's opening SYNC
(`OUT (0Fh),03h`, then a wait of up to ~1 s for READY + IDLE), a BREAK
abort that landed after its transaction had finished, or a SYNC right
behind a half-sent pre-header after a 2068 reset
([PROTOCOL.md §4.1](../../PROTOCOL.md#41-sync-rom-20-and-firmware-20),
[exrom-sync.md](../rom/exrom-sync.md)). ROMs up to 1.7 never write 0Fh.

1. `MQ_TO_IDLE(MQ, status=False, first=FIRST_STATUS())`: both FIFOs emptied,
   one byte staged, Y left where the OUT dropped it (BUSY). The byte is
   `0x01`, or the error of a header LOAD refused within the last two seconds
   (`LOAD_REFUSE`, `FIRST_STATUS`): the ROM retries a refused header at once,
   and only its *next* request's first status can carry a report
   ([PROTOCOL.md §13](../../PROTOCOL.md#13-pitfalls), "A LOAD's first status
   can't carry an error").
2. If `got != -1` (something preceded the 0Fh write): a `TLM` with the
   words and a level-1 `LOG` "0Fh write after k pre-header byte(s) --
   resynced". A lone SYNC is every command and is not logged.
3. Wait, at most 800 ms, for `busy` to clear: a `SAVE_LOG` on core1 is
   programming flash, which stops both cores, and the Z80 will send its
   pre-header the moment IDLE is said — a freeze mid-burst lost bytes
   ("Partial pre-header 8/10" → Report T in Commander, hardware 2026-09-27).
   No `gc.collect()` here: 4.6 ms on every SYNC, every LPRINT character, and
   `RX_CAPTURE` allocates nothing.
4. `rxd.arm(MQ)` when there is a DMA capture — before IDLE, since the pre-header follows at once — then
   `MQ_STATUS(MQ, "idle")`: Y = `0xFF`. `continue`.

Y is BUSY from step 1 to step 4; the Z80 waits. A SYNC therefore always
leaves TX = `[01]` (or the staged error), RX empty, status `0xFF`, whatever
state an earlier client left. Note that the "idle" also clears a RECOVERED
status set earlier: the ROM only tests RECOVERED in `WAIT_PICO_READY`'s
status read (`RD_STATUS`), not in `SYNC_WAIT`, so a transaction the Pico
dropped reports T only if its ROM is still waiting for READY when the
`0xFB` goes up; a later command finds `0xFF` *(inferred from
[tspico-sync.asm](../../../src/rom/patches/tspico-sync.asm): `SYNC_WAIT`
masks READY and IDLE only)*. The comments at lines 6435 and 6527 that say
"the next command gets Report T" describe the ROM's own ready-wait of the
transaction in hand, not a later one.

### A partial pre-header: `0 ≤ got < 10`

Part of a burst, then a second of silence: a 2068 reset mid-pre-header, a
lost byte, or noise. The loop does not guess at a command: a level-2 `LOG`
"Partial pre-header k/10: …  -- RECOVERED", a `TLM`, and
`MQ_TO_IDLE(MQ, recovered=True)` — FIFOs emptied, one `0x01` staged,
Y = `0xFB`. A ROM 2.x still waiting for READY sees RECOVERED and reports
"T TS-Pico reset, try again"; its next SYNC clears it. `continue`.
Before #51 this read hung for good (the main-loop case in
[OPEN_QUESTIONS.md](../../OPEN_QUESTIONS.md)).

### Before the branches

`pre[i] = pre_raw[i]` for the ten words (all below 256: a 0Fh word would
have returned negative).

**The printer flush.** If `PRT.buf` holds text and this is *not* a printer
pre-header (`'B'` with TADDR 4–6): `_unread = not PRELOAD_READ()` waits up
to 100 ms for the Z80 to take the pre-load it reads straight after the
pre-header; `PRINT_FLUSH()` writes the text to the card (the Z80 is now
parked in its READY wait); if the pre-load had not been read, `MQ.put(0x01)`
puts it back, since the SD access rebuilt the state machine and emptied TX.
Y is BUSY afterwards, as the handler expects
([printer_io_hosttest.py](../../../src/test/printer_io_hosttest.py): "the
dispatcher flushes printer text before any other command").

**READY.** `if pre[0] not in (PRE_HEADER, PRE_DATA, PRE_CMD): MQ_READY()`.
Every known kind of pre-header — a tape block (00h/FFh), a command or the
printer (42h) — is left to its handler to say READY once its first bytes
are queued. For LOAD, `LOAD_TS` says it once the block's first bytes are in
TX: a READY here raced `LOAD_TS`'s start (a `TLM`, a file seek, a GC)
against the ROM's ~88 ms flag poll, and losing it handed the ROM `0x00` as
the flag — Report R, seen on hardware after a BREAK (#51, #64). For SAVE,
`SAVE_TS` says it right before its header capture: the Z80 streams the
21-byte header at ~43 µs a byte the moment it sees READY. For commands,
`PROCESS_CMD` (above). The condition used to be Ryan's
`not ((pre[0] == 0 or pre[0] == 255) and pre[1] < 10)`, which still gave a
headerless LOAD (TADDR ≥ 10) the early READY (audit §2 #11, 2026-09-30).
As the code stands the early READY is reached only by an unrecognised
pre-header, whose branch then goes to `MQ_TO_IDLE` anyway.
[load_ts_hosttest.py](../../../src/test/load_ts_hosttest.py) and
[save_ts_hosttest.py](../../../src/test/save_ts_hosttest.py) each check the
source text of this condition.

`_pre_snapshot = list(pre)` for the `TLM`s. With `LOG_LEVEL` 0 only, a
"Top of main loop" `LOG` with `gc.mem_free()` — 3.1 ms, which is why it is
not unconditional.

### SAVE: `pre[0] == 00h and pre[1] == 0`

A SAVE's header pre-header ([PROTOCOL.md §6.2](../../PROTOCOL.md#62-save),
[flows/save.md](../flows/save.md)). LED on.

1. `WAIT_CORE1(3000, "SAVE")`: a flash write on core1 stops both cores, and
   the header and data blocks arrive with no flow control. Bounded; the Z80
   waits ~20 s for READY here.
2. The card is checked *before* `SAVE_TS` says READY, so a SAVE with no card
   is refused at the header and the program stays in memory; before this it
   said "0 OK" and the write failed silently afterwards. `SD_PROBE()` rebuilds
   the bus state machine and so empties TX, so first `_unread = not
   PRELOAD_READ()`; `TSP.save_no_card = not SD_PROBE()`; `MQ.put(0x01)` back
   if unread. On hardware the Z80 reads the pre-load microseconds after the
   pre-header; in the emulator (`tools/emu`) every port access is a round
   trip and it lost the race until this was added (2026-10-04;
   save_ts_hosttest checks the order of the three calls).
3. `pf_name`, `pappend`, `pidx` save the mount's name, append flag and
   block index. `MQ, TSP, new_logs, saved = SAVE_TS(MQ, TSP, pre)`
   ([tspico_io.md](tspico_io.md)): READY, the header block, the mid status,
   the data block, the write; `saved` is `True` only if a `.tap` reached the
   card; `TSP.save_final` holds the final status the Z80 has not yet been
   given (`0x01`, or `0x0A` = J when nothing was written), or `None` if the
   data never arrived; `TSP.save_recovered` says `SAVE_TS` gave up on a
   silent Z80. `TSP.save_no_card = False`; the logs appended.
4. `DEACTIVATE_SD()` (`SAVE_TS` may leave `/sd` mounted).
5. If `saved`, the mount is brought into line, in a `try` (`MOUNT_FILE`
   raises when the card has stopped answering; this is not under
   `PROCESS_CMD`, so nothing else would catch it, and the SAVE itself already
   reached the card):
   - `TSP.native_saved` (a `SAVE "f:…"`): clear it, restore `TSP.f_name`;
     the mount is untouched;
   - `pappend`: `MOUNT_FILE(TSP.f_name, True)` re-mounts the appended TAP
     so the addition is visible, then restores `append`, `tap_idx` and the
     `offset` from `offset_tbl` that the mount reset;
   - no file was mounted and `SAVE_TS` made one: `MOUNT_FILE(TSP.f_name,
     True)` it (append stays off; as a "remount", a failure goes straight
     to `UNMOUNT`, which calls `SEND_MSG` before the arm point);
   - the SAVE overwrote the mounted TAP (`TSP.f_name == pf_name`): logged;
     the old content stays mounted, no re-mount;
   - a new file while another is mounted: `TSP.f_name = pf_name`.
   A failure sets `sd_gone`. If not `sd_gone`: `ACTIVATE_SD()`,
   `os.chdir(TSP.cur_path)` (`MOUNT_FILE` does not set it), `DIR_FILES()`
   refreshes the listing — skipped after a failed re-mount so five more
   attempts do not push the Z80 toward J. `DEACTIVATE_SD()`.
6. The single arm point, for a saved and for an aborted SAVE alike:
   `ACTIVATE_MQ()` (fresh state machine, TX empty, Y BUSY); then
   `MQ.put(final)` if `save_final` was set; `MQ.put(0x01)`; `MQ_STATUS(MQ,
   "recovered" if TSP.save_recovered else "idle")`. The Z80 has sat in its
   READY wait through all the SD work and reads the final status now, then
   the pre-load waits for the next command. LED off.

What happens after an aborted SAVE: `saved` is false, so step 5 is skipped;
`save_final` is `None` when the data block never came (a refusal at the
header, a BREAK, a stall), so only the `0x01` is staged; the status is
`0xFB` if `SAVE_TS` gave up on a silent Z80, else `0xFF` — which is what a
ROM that pressed BREAK is waiting for before Report D. The mount is as it
was.

Why one arm point at the end: this used to arm (`ACTIVATE_MQ` + `0x01` +
READY) before the re-mount, and the 2068 printed "0 OK" and went back to its
prompt while the Pico was still on the card — `ACTIVATE_SD` takes GPIO 2–4,
which are D0–D2, the pin-grab race #40 fixed inside `SAVE_TS` and
reintroduced one level up; a fast typist's next command then had the state
machine rebuilt under it (PROTOCOL.md §13, "Don't announce READY and then go
do SD work"). And why `saved` comes from `SAVE_TS`: it used to be guessed
from whether `/sd` was still mounted, which was wrong for the case that
matters — a write that fails after the mount.

### LOAD, VERIFY, MERGE: `pre[0]` 00h or FFh

Two branches with the same body: `pre[1] < 10` is logged as "Starting TS
LVM", anything else as "Headerless LOAD" (a machine-code `LD-BYTES` with
whatever TADDR held). Each: a `TLM` with the mount state, `WAIT_CORE1(3000,
…)` (`LOAD_TS` streams a block the Z80 reads blind, a byte every ~50 µs),
then `MQ, TSP, new_logs = LOAD_SERVE(pre, MQ, TSP)` and the logs appended.
`LOAD_SERVE` swaps in the one-shot tape of a `tpi:fopen` if one is armed and
runs `LOAD_TS` ([tspico_io.md](tspico_io.md), [flows/load.md](../flows/load.md)).
A FFh/0 pre-header (a data block with TADDR 0) comes here, not to SAVE.
`LOAD_TS` says READY itself, ends with the final status and one pre-load in
TX, or with `MQ_TO_IDLE` after a BREAK, a stall or a refused block.

### The printer: `'B'` with TADDR 4, 5 or 6

`PRINT_IO(pre)`, above. It is tested before the command branch.

### A command: `'B'`

A level-0 `LOG` "Starting TS COMMAND" with the pre-header, then
`PROCESS_CMD(pre, SA_funct, EXT_SA_FUNCT)` inside a `try` whose `except
Exception` logs "Invalid data received from PROCESS_CMD" at level 2 and
`continue`s. Since #42 a handler's exception never reaches here;
what could still is the body capture before `PROCESS_CMD`'s `try`.

Then `if TSP.zx48:` — the `tpi:zx48` handler set it (and `PROCESS_CMD`
cleared it at entry, so only this command's handler can have): `rxd.stop()`
if the tail armed the channel, because `ZX48_IO` reads RX by hand, then
`ZX48_IO(pre)`. The loop resumes here when the 2068 leaves Spectrum mode.

### Anything else

A level-1 `LOG` "Unrecognized command!" with the bytes, and
`MQ_TO_IDLE(MQ, recovered=True)`: FIFOs emptied, one `0x01` staged,
Y = `0xFB`. This branch used to drain both FIFOs, restart the state machine
and blink for a second — Ryan's single-port recovery, when the loop restaged
`0x01` on every pass; in the V6 chain the drain left no pre-load and a ROM
without SYNC got J on its next command (PROTOCOL.md §4.3), and the blink
blocked while that command could already be arriving. There was also an
`'A'` (41h) branch, `PROCESS_ASM` + `DIR_FILES`, a placeholder for an
assembler block in Gustavo's design that no ROM sends (the EXROM only does
`LD A,42h`); the audit removed it, and 41h now lands here.

There are no bottom-of-loop drains: each handler's tail must leave TX with
exactly one `0x01` and RX empty, and a drain here would mask a handler that
did not.

### The idle tail

When nothing has arrived, the heartbeat, with `time.ticks_diff` (the raw
subtraction went negative after `ticks_us` wrapped at 2³⁰ µs, ~17.9 min,
and the loop spun in `continue` for ever: the "LED stopped blinking" halt):

- under 2.0 s since `ts`: `continue`;
- 2.0–2.1 s: LED on;
- with no card: 2.1–2.25 s off, 2.25–2.35 s on again — the double blink;
- then: if there are `log_entries` and core1 is not `busy`, `busy = True`
  **on core0, before** `_thread.start_new_thread(SAVE_LOG, ())`, and an
  `OSError` ("core1 in use": `SAVE_LOG` clears `busy` before the thread has
  quite returned) clears `busy` again — nothing else would. Then
  `DRAIN_STDIN(MQ)` so a host's Ctrl-C can still get through MicroPython's
  stdin buffer ([stdin_drain_hosttest.py](../../../src/test/stdin_drain_hosttest.py)),
  LED off, `ts` reset.

No `gc.collect()` here: it stops the world for 10–100 ms, during which a
whole pre-header arrives and the FIFO drops bytes 4–9 (the comment keeps the
trace: `pre=[66, 0, 255, 2, 'D', 7, 0, 't', 'p', 'i']`, body bytes read as a
pre-header, Report J).

### The service-loop restart

`except Exception as err` around the inner loop (2026-10-02): `failures`
keeps the times of errors in the last 60 s; the error is logged at level 2
with the count, its traceback appended to `/activity.log` with
`sys.print_exception`, and `SAVE_LOG()` run synchronously. A third failure
within a minute re-raises, and `main.py` writes "FATAL ERROR in TS2068_IO"
with the traceback to `/activity.log` and USB and stops: the Pico is
quiescent and the post-mortem is on flash. Otherwise only the bus link is
reset: `rxd.stop()` if armed; `DEACTIVATE_SD()` if `sd_active`;
`ACTIVATE_MQ()`; `MQ_TO_IDLE(MQ, recovered=True)` (one `0x01`, Y = `0xFB`);
`TSP.zx48 = False`; `ts` reset. Not `machine.reset()`, which releases the
ROM-bank pins under a running 2068; not `TS2068_IO()` again, which would
rebuild the ROM/BANK machines and re-read `config.ini`, whose one-shot could
switch the ROM slot under the running 2068. `BaseException`s — Ctrl-C from
`DRAIN_STDIN` (`KeyboardInterrupt`), a `CmdAbort` — pass straight through;
`main.py` catches only `Exception`, so Ctrl-C reaches the REPL.

### What lands where

`/activity.log`: everything `LOG` kept at or above `TSP.LOG_LEVEL` (and
everything before `TSP` exists), written by `SAVE_LOG` — synchronously at
the four boot points and in the restart handler, on core1 from the idle
tail; `ZX48_IO`'s idle tail calls it synchronously. Plus the restart's
traceback and `main.py`'s fatal one. USB serial: the `[TLM …]` lines when
`config.ini` has `TELEMETRY` true ([boot.md](boot.md)); `print`s from
`ACTIVATE_SD`'s attempts, `ZX48_IO`'s "MQ FIFO:" and `main.py`; `LOG` text
too if `log_to_serial` is set from the REPL.

Tests that run this function: [sd_wedged_hosttest.py](../../../src/test/sd_wedged_hosttest.py)
(boot with no card continues into the loop; the post-SAVE re-mount logs and
re-arms), [dir_files_eio_hosttest.py](../../../src/test/dir_files_eio_hosttest.py)
(a card that fails its first write), [sync_io_hosttest.py](../../../src/test/sync_io_hosttest.py)
(the pre-header goes through `RX_CAPTURE` in both copies of the module),
[stdin_drain_hosttest.py](../../../src/test/stdin_drain_hosttest.py) (both
heartbeats drain stdin), [printer_io_hosttest.py](../../../src/test/printer_io_hosttest.py)
(the flush before other commands). The phase-by-phase byte behaviour of the
branches is pinned by the handlers' own tests
(`load_ts_hosttest`, `save_ts_hosttest`, `cmd_io_hosttest`), each of which
"does what the dispatcher does" around the handler.

Beware: `kill`, `wrt` and `log_to_serial = False` are leftovers; the long
"DUAL-PORT MIGRATION" comments describe the code as it was at each step and
several have been overtaken (the audit's §3 list of stale comments). The
10-word pre-header capture and the SYNC path must stay allocation-free and
must not log before IDLE.

## `ZX_TPI()`

The ZX ROM's `'T'` command: `LOAD "tpi:name"` (ZX v3 and v4) and
`SAVE "tpi:dir [arg]"` (v4), the only `tpi:` commands that exist in
Spectrum mode. Returns `nxt` as `LOAD_ZX` does: `-1`, or a word the Z80
wrote while the reply was going out — its next command, for `ZX48_IO` to
dispatch.

The ROM side ([tspico-zx48-v3.asm](../../../src/rom/patches/tspico-zx48-v3.asm),
`TPI_CMD`; [ROM_CHANGES.md](../../ROM_CHANGES.md#the-addition-load-tpiname-in-zx48-mode);
[rom/zx48.md](../rom/zx48.md)): after `OUT (0Eh),'T'` it waits for READY
(~3.8 s, else J), sends the op byte (T-ADDR: 0 SAVE, 1 LOAD, 2 VERIFY,
3 MERGE; v4 ORs in 80h), the length and the name after `tpi:`, with a delay
after each byte for the four-deep RX FIFO, then waits up to ~30 s for READY
(BREAK between rounds: Report D) and reads the reply: a status byte — FFh
is OK, anything else an ERR_NR — then, on v3, one length and the message;
on v4, pieces: a length 1–255, that many bytes, printed as they come, until
a length of 0. How long the ROM leaves between bytes is given three ways —
"~54 us" in this function's docstring, "~50 us (TPI_OUT/TPI_DLY)" in
ROM_CHANGES.md, "~45 us (TPI_DLY)" in the reply loop's comment — and this
chapter does not pick one.

What it does:

1. `gc.collect()` before READY: the name streams with no handshake. With the
   DMA ring (`tspico_io._ring`), one `RX_RING(…, both, False, 257,
   ZX_STALL_MS, ZX_STALL_MS, 1, "ready")`: READY (`0xFF`) once the channel
   runs, and op, length and name in *one* run, the burst ending `length`
   words after word 1 — two runs lost the name's first bytes while the second
   was set up (Report J, hardware 2026-10-03). Without DMA: `MQX` READY, then
   `RX_BLOCK` for two bytes and `RX_BLOCK` for the name. Anything but
   `RXB_OK` (a stall of `ZX_STALL_MS`, 1000 ms, or a 0Fh word): a level-2
   `LOG` and `return -1` — the ROM then gives up on its own, J or D.
2. `rest` is the name's printable characters; `pieces = hdr[0] & 0x80`;
   `op = hdr[0] & 0x7F`; `word = rest.lower()`; `stall = ZX_STALL_MS`.
3. `op == 0` and the word is `dir` or starts `dir `: on a v3 ROM (no
   `pieces`) the answer is `'SAVE "tpi:dir" needs ZX ROM v4'` with
   `_4_Q_Parameter`. On v4: `REFRESH_LISTING()` if a ZX SAVE made the
   listing stale; `ACTIVATE_SD()`; `text, st = CATALOG_TEXT(rest[3:].strip())`
   ([tspico-disk.md](tspico-disk.md)); `DEACTIVATE_SD()`, `ACTIVATE_MQ()`
   (Y BUSY); an `OSError` is "SD card error", `_3_F_Invalid_file`. On
   success `listing = CAT_COLOUR(text)` — the Spectrum has the same colour
   codes — and `stall = CMD_STALL_MS` (600 s), because the ROM's `PR_STRING`
   stops at its own "scroll?" for as long as the user likes and only a new
   command ends it.
4. Any other `op` but 1: `'Only LOAD "tpi:..." and SAVE "tpi:dir" in ZX48
   mode'`, Q.
5. `op == 1`: `REFRESH_LISTING()` if stale, then `msg, rest, st =
   LOAD_TPI(rest, only_tap=True)` — a name, any case, a listing number or a
   wildcard; anything but a `.tap` is refused with Q, since `.ROM`/`.DCK`/
   `.BIN` would mount the 2068 updater; a mount may use the card (the state
   machine is rebuilt).
6. The text: a listing becomes bytes with anything ≥ 80h replaced by `?`;
   otherwise `(msg.strip() + " " + rest).strip()`, cut to 200 bytes. A
   `LOG` at level 0 (2 for an error).
7. The reply buffer `out`: v4 — `status`, then for each 255-byte slice its
   length and bytes, then `0`; v3 — `status`, `len(text)`, the text.
   `out[0] = ZX_REPORT.get(st, 0x19)`: FFh for `_1_OK`, 1Ah (R), 0Eh (F),
   19h (Q), and Q for any other status.
8. `ZX_FLUSH_TX(MQ)`; `gc.collect()`; `r = STREAM_DMA(MQ, out, None, stall,
   True)`: by DMA where there is one, READY once the channel is moving — the
   ROM reads blind from the instant it sees READY. `r` is `(why, sent,
   word)`: `why` 0, all sent → `-1`; 4, the Z80 wrote a word (its next
   command, `echo` being `None` in ZX mode) → `ZX_FLUSH_TX`, a level-2 `LOG`
   "reply stopped at byte i of n", return that word; 1 or 3 (a 0Fh write,
   a stall) → the same flush and log, `-1`. Without DMA: up to `TX_DEPTH`
   bytes with `MQ.put`, `MQX` READY, then the loop — `ZX_ROOM(MQ, stall)`
   only when the FIFO is full (calling it per byte cost ~49 µs a byte on
   v1.29 and the FIFO ran dry; this shape is ~9 µs), which returns `-1` for
   room, `-2` for a stall, or the word the Z80 wrote; a stall or a word ends
   the reply as above.

Y: BUSY on entry (the `'T'` OUT dropped it); READY from the capture; each
of the ROM's OUTs drops it again, which does not matter while nothing polls;
READY again once the reply is moving, and left so. TX empty afterwards
unless the ROM stopped reading, when `ZX_FLUSH_TX` empties it. No pre-load:
ZX48 mode has none (PROTOCOL.md §13, "ZX48 mode is a different protocol").

Callers: `ZX48_IO`. Callees: `RX_RING`/`RX_BLOCK`, `STREAM_DMA`,
`ZX_FLUSH_TX`, `ZX_ROOM`, `MQX`, `REFRESH_LISTING`, `CATALOG_TEXT`,
`CAT_COLOUR`, `LOAD_TPI`, `ACTIVATE_SD`/`DEACTIVATE_SD`/`ACTIVATE_MQ`.
State: `TSP.listing_stale`, the mount through `LOAD_TPI`, `tspico_io._ring`.
[zx48_tpi_hosttest.py](../../../src/test/zx48_tpi_hosttest.py) pins: a name
in any case or a listing number mounts with FFh and the message; the reply's
first bytes are in TX before READY and the rest follows without an empty
read; a missing file is F (0Eh), a `.ROM` Q (19h), `SAVE "tpi:x"` Q, a
failed mount Q, v3 asking for `dir` gets the "needs ZX ROM v4" Q, v4's
`dir` goes through `ACTIVATE_SD`/`CATALOG`/`DEACTIVATE_SD`/`ACTIVATE_MQ`
and comes back in pieces with `nxt == -1`; a name that stops half-way gives
no reply, no mount, no hang; a stale listing is re-read first. The user's
view: [user-manual.md 9.2](../../manual/user-manual.md#92-what-works-in-spectrum-mode).

## `ZX48_IO(pre)`

The loop the firmware runs while the 2068 is a ZX Spectrum: after
`SAVE "tpi:zx48"` and `OUT 244,3` the customised Spectrum ROM in flash slot
0 talks a protocol with no status port, no pre-header, no pre-load and no
echo ([PROTOCOL.md §10](../../PROTOCOL.md#10-zx48-mode),
[flows/zx48.md](../flows/zx48.md)). `pre` is the `tpi:zx48` command's
pre-header, for its `CODE` numbers.

How the mode is entered: the `ZX48` handler ([tspico-commands.md](tspico-commands.md))
sets `TSP.zx48 = True`, `TSP.ZX_TAPE_COMPAT` from `par2`, and prints the
instructions; `PROCESS_CMD`'s tail runs as for any command (pre-load,
IDLE); then `TS2068_IO` stops the pre-header DMA channel and calls this.

What it does on entry: LED off; `par1, par2 = PARAMS(pre)`; a fresh bus
state machine — `MQ = StateMachine(0, TS_IO_DUAL, freq=30_000_000, …)` on
the same pins as `ACTIVATE_MQ`, stopped, 10 ms, started — and
`MQX(MQ, "mov(y, invert(null))")`: Y = READY. The comment says "for the
entire ZX session"; the PIO still drops Y on every Z80 OUT, and the handlers
say READY again when they are ready. The pre-load `PROCESS_CMD`'s tail had
staged is in the old state machine's FIFO and is gone *(inferred: the SDK's
state-machine init clears the FIFOs; the audit §2 #12 says "most likely")*.
A `TLM`, a level-0 `LOG` "Starting ZX Mode...", `ts`, `nxt = -1`.

The loop. If `nxt >= 0` (a command byte a handler took in the middle of
its block) or RX has a word: `a` is that byte or `MQ.get()` — the nine-bit
word, unmasked, which is safe because it is only compared. A bounded wait
(3000 ms, then a level-2 `LOG`) for a `SAVE_LOG` on core1: a flash write
stops both cores and must not overlap a block; the ZX v2 ROM waits ~3.8 s for
READY after its `'L'` or `'S'`. Then:

- `'L'` (76): with `TSP.ZX_TAPE_COMPAT`, `LOAD_ZX_C(MQ, TSP, buf_size)` —
  `buf_size` is `par2` if ≥ 16384, else 52100 ("lower this if mem
  allocation error arises"; the audit §4 notes the number dates from a
  smaller firmware) — else `LOAD_ZX(MQ, TSP)`. Both return `(MQ, TSP,
  new_logs, nxt)`; non-blank logs are appended.
- `'S'` (83): `SAVE_ZX(MQ, TSP)`, the same tuple.
- `'T'` (84): `nxt = ZX_TPI()`.
- `14`: the exit, `OUT 14,14` from the 2068 after `OUT 244,0`. The port is
  14 because the dual-port PIO listens on 0Eh and 0Fh only — the old guard
  `OUT 10,100` stopped working when the single-port PIO went; the value 14
  is arbitrary, chosen to match the port. A `TLM`, a level-0 `LOG` with the
  free memory, `gc.collect()`, `TSP.zx48 = False`, `break`.
- anything else: a level-1 `LOG` "Unrecognized ZX command"; RX and TX
  emptied (unbounded loops), the state machine stopped and started, a
  level-0 `LOG` with the FIFO depths.

Otherwise the heartbeat, the same shape as `TS2068_IO`'s: a 0.1 s flash
every 2 s, two with no card; then `SAVE_LOG()` if there are entries —
called directly, on core0, not as a thread — `DRAIN_STDIN(MQ)`, LED off.

How the mode is left. After `break`, if TX is not empty — a ZX LOAD that
stopped before the end of what was queued, the ROM having asked for fewer
bytes than the block holds, or a BREAK (hardware 2026-10-02: `tx=4` at the
exit) — a `print` to USB, a level-1 `LOG`, TX emptied, the state machine
restarted, a level-0 `LOG`; else a level-0 `LOG`. Ricardo's fix of
21 Aug 2025; the audit thought #52 (the one-byte-too-many in `LOAD_ZX`) had
made it obsolete, but that fixed one cause only. A `TLM`, and return to
`TS2068_IO`, which re-arms the pre-header channel at the top of its loop.
Nothing stages a pre-load on the way out: a ROM 2.x's next SYNC stages one
(`MQ_TO_IDLE`); on ROM 1.1 the next command would read `0x00` and get J
(audit §2 #12, *unverified* on hardware).

Y and the FIFOs, as a summary: entry READY, both FIFOs empty; each `'L'`,
`'S'` or `'T'` OUT drops Y and the handler raises it; exit TX empty, Y
wherever the last handler left it.

Takes: `pre`. Returns nothing. State: `MQ` (rebuilt), `TSP.zx48`,
`TSP.ZX_TAPE_COMPAT` (read), `TSP.sd_present` (the heartbeat),
`log_entries`, `busy` (read), `led`. Caller: `TS2068_IO`. Callees:
`PARAMS`, `LOAD_ZX`, `LOAD_ZX_C`, `SAVE_ZX`, `ZX_TPI`, `SAVE_LOG`,
`DRAIN_STDIN`, `MQX`.

Tests: [zx48_hosttest.py](../../../src/test/zx48_hosttest.py) drives
`LOAD_ZX`/`SAVE_ZX` with the `'L'`/`'S'` already consumed, as this loop
does; [zx48_tpi_hosttest.py](../../../src/test/zx48_tpi_hosttest.py) checks
both copies of the module dispatch `'T'` to `ZX_TPI`;
[stdin_drain_hosttest.py](../../../src/test/stdin_drain_hosttest.py) checks
the heartbeat drains stdin. Nothing host-side runs the loop itself.

Beware: the V6 chain does not apply here — a status or `0x01` written by a
ZX handler is an orphan the next `'L'` reads as its flag; never call
`ENA_MQ()` (the single-port machine) from a ZX handler; mask RX words before
storing them (PROTOCOL.md §13). The exit cleanup and the "unrecognized"
drains are unbounded `while` loops, unlike every other drain in this part.
