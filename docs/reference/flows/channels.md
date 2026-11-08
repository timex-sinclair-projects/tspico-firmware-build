# Flow: `OPEN #`, `PRINT #`, `INPUT #`, `CLOSE #`

The ROM lets BASIC open a file on the SD card as a stream:
`OPEN #4,"f:log.txt","a"`, then `PRINT #4` and `INPUT #4` as with any
channel, then `CLOSE #4`. The 2068 keeps a channel record in CHANS, with a
small output and input buffer; the Pico keeps each stream's file, mode and
position. Every exchange is a `tpi:` command sent in the middle of a BASIC
statement, so every answer is a bare status — a printed message would move
the current channel to the screen — and the ROM must wait for the Pico's
tail before each new command. This flow follows one file from OPEN to
CLOSE, then records, `d:` listings, the speech channel (`v:`), the command
channel (`x:`) and the failures. User's view: [user
manual chapter 6](../../manual/user-manual.md#chapter-6-streams-and-channels-open-).

Notation as in [command.md](command.md): **TX**/**RX** the bus FIFOs, **Y**
the status (`FF` READY + IDLE, `F7` READY not IDLE, `00` BUSY).

## How a channel command differs from a `tpi:` command

| | A `SAVE "tpi:…"` command | A channel command |
|---|---|---|
| sent by | SESSION_SETUP → BUILD_PREHEADER_B | the module's `CH_SEND`, byte by byte through the BIOS ([../rom/exrom-fdd.md](../rom/exrom-fdd.md#ch_send)) |
| before the SYNC | — | waits up to ~1 s for IDLE (bits 6 and 3) |
| the answer | any: status, message, pages | a bare status: `CH_REPLY` = `CMD_PUT(st)` + `CH_READY` (Y `F7`) ([../firmware/tspico-bus.md](../firmware/tspico-bus.md#ch_replyst)) |
| read by | C_END_TAIL, through the function chain | `CH_STATUS` = BIOS C_END (C_END2) with CURCHL saved and restored |
| a refusal | the report, statement ends | the report, statement ends; nothing half-built is left |
| the card gate | `SD_NEEDED` | the same; no card → `CH_REPLY(10)`, a bare J ([../firmware/tspico-bus.md](../firmware/tspico-bus.md#no_card_replycmd_word)) |

Why READY without IDLE: the module can send its next command the moment it
has an answer (CLOSE # flushes and closes back to back). If the answer said
IDLE, the next SYNC could arrive while `PROCESS_CMD`'s tail was still
draining and logging, and the tail's own IDLE then let the pre-header go
by uncaught ("Partial pre-header 4/10", Report T; hardware, 2026-09-29). So
the answer says `F7`, the tail says `FF` once it has staged the pre-load
and armed the capture, and `CH_SEND` waits for that `FF` before its SYNC.

## OPEN

`OPEN #4,"f:log.txt","a"`.

| # | Side | Routine | What happens | What can go wrong |
|---|---|---|---|---|
| 1 | 2068, syntax | HOME 1438h → 14BDh → `OPEN_SYNTAX` | the spec, then `,"mode"` and an optional `,reclen` are evaluated, so the number's hidden form is stored ([../rom/home.md](../rom/home.md#13a5h-1438h-145eh-open--and-close-)) | extra arguments to a K/S/P OPEN: Report C, now at syntax time |
| 2 | 2068, run time | HOME 140Fh (the stream into 5CCBh) → 145Eh → 1488h → `CH_OPEN_HOOK` | `f:`, `d:` or `v:`: ours (`SPEC_KIND`); K/S/P go to the stock 1465h | |
| 3 | 2068 | `CH_OPEN_HOOK` | room for the record and the command (Report 4); the mode popped (1–3 characters; none = `r`); `tpi:chopen a log.txt` built at STKEND | a mode of 4+ characters: Q |
| 4 | 2068 | `CH_SEND` | waits for IDLE; SYNC; the pre-header — TADDR 0, PMR1 = 4 (the stream), PMR2 = the record length (0) — the pre-load (`PRELOAD`: 0 is J), WF_NPH, the body | |
| 5 | Pico | `PROCESS_CMD` → card gate → `CH_OPEN` ([../firmware/tspico-disk.md](../firmware/tspico-disk.md#ch_openpre-cmd)) | the path resolved (`/` is the card's TAP folder); inside `CH_CALL`: a directory Q, a missing parent F, `CHANNELS.open(4, real, "a", 0)` — creates the file for `a`/`u`, truncates for `w`, requires it for `r` | TX [st], Y `F7`; then the tail: TX [01], Y `FF` |
| 6 | 2068 | `CH_STATUS` | NC: on. C: `C_FAIL` → the report; **no record is built**, the stream stays closed | F, Q, J (no card) |
| 7 | 2068 | `CH_OPEN_HOOK` | the spec dropped from the calculator stack; 512 bytes made at CHANS' end (padded so the offset's bytes stay below 80h); the record written: 14A0h, 14A9h, `'F'`, the stream, the pad, the flags | |
| 8 | 2068 | HOME 1461h | the offset into STRMS: stream 4 points at the record | |

The Pico opened the file and closed it again: the card is unmounted
between commands, so every channel operation opens, seeks, reads or
writes, and closes.

## PRINT

`PRINT #4;"hello"`: the 2068 selects stream 4 — CURCHL = the record — and
`RST 10h` sends each character to the record's output routine, HOME 14A0h →
`CH_OUT` ([../rom/exrom-fdd.md](../rom/exrom-fdd.md#ch_out)), under `DI`
through the returning thunk.

1. `CH_OUT` puts the byte in the record's 64-byte buffer. A TAB code (23)
   also empties the read-ahead (a seek).
2. When the buffer is full — or at a CR on a record file — `CH_FLUSH`:
   the count cleared first, then **`tpi:chwr 68656c6c6f0d`** (the bytes as
   lower-case hex: the body must be text) with PMR1 = 4.
3. Pico: `CH_WRITE` decodes the hex (a bad digit: C, nothing written) and
   `CH_CALL(CHANNELS.write, 4, data)`: the card mounted, the bytes appended
   at the stream's position with the text translated (the 2068's CR to the
   file's line ending; the TAB escape `17h lo hi` honored), the card given
   back. `CH_REPLY(st)` ([../firmware/tspico-disk.md](../firmware/tspico-disk.md#ch_writepre-cmd),
   [../firmware/channels.md](../firmware/channels.md)).
4. 2068: `CH_STATUS`.

A short PRINT stays in the 2068's buffer until the buffer fills, a CR on a
record file, an INPUT on the same stream, or CLOSE: PRINT is cheap, the
command is per 64 bytes.

## INPUT

`INPUT #4;a$` (on a stream opened `r` or `u`): the 2068's INPUT reads
characters through the record's input routine, HOME 14A9h → `CH_IN`.

1. A byte left in the record's 255-byte input buffer: hand it out (carry
   set).
2. Otherwise `CH_FLUSH` (what was printed goes first — `INPUT #4;TAB n;` is
   a seek, then a read), then `CH_FETCH`: **`tpi:chrd`**, PMR1 = 4, PMR2 =
   255.
3. Pico: `CH_READ` — `CH_CALL(CHANNELS.read, 4, 255)`; then **a data phase,
   not a status**: `01`, the count, the bytes, their XOR — built in RAM and
   streamed by DMA, `CH_READY` once it runs; or, at the end of the file,
   the single byte 7 ([../firmware/tspico-disk.md](../firmware/tspico-disk.md#ch_readpre-cmd)).
4. 2068: WF_NPH; the status: 1 → the count, then each byte after a ~75 µs
   delay (read blind, as LOAD reads), then the XOR (a mismatch: Report R);
   7 → `CH_IN` returns NC NZ, which the ROM's WAIT-KEY turns into **Report
   8, End of file**; anything else, its report.
5. Back in `CH_IN`: hand out the first byte.

The editor clicks once per character taken; the ROM's G_BEEP skips the
click when the current channel is an `F` record, so a file is read
silently ([../rom/exrom-fdd.md](../rom/exrom-fdd.md#g_beep-3029h)).

## RESTORE

`RESTORE #4`: back to the start of the file. HOME's syntax table sends
RESTORE to the hook at 25D6h (class 05h), and the module's `FDD_RESTORE`
takes the `#` form itself; plain `RESTORE` and `RESTORE n` go back to
HOME's RESTORE ([../rom/exrom-fdd.md](../rom/exrom-fdd.md#fdd_restore-3819h)).

1. Stream 4's STRMS entry must lead to an `F` record (not open, a SYSCON
   channel, another channel letter or a stream above 15: **Report O**).
2. `CH_FLUSH`: anything printed and still buffered goes out as
   `tpi:chwr`.
3. The record's input buffer is emptied (`R_INN` = `R_INP` = 0): what was
   read ahead is no longer next.
4. `CH_FLUSH` again with the three bytes 23, 1, 0 in the output buffer:
   **`tpi:chwr 170100`**, TAB 1. Nothing new on the wire.
5. Pico: `CH_WRITE` → `Channels.write`, which takes the TAB in any mode
   (the same escape as in Records, below) → `Channels._seek(ch, 1)`: an
   open record is closed (padded), the position is 0, the text-in state is
   reset ([../firmware/channels.md](../firmware/channels.md#channels_seekself-ch-n)).
   Bare status, as for any `tpi:chwr`.

So the next `INPUT #4` reads the first line again, and on a `w`, `a` or `u`
stream the next `PRINT #4` writes over the start of the file. That holds
for an `a` stream too: `_seek` sets the position whatever the mode, and
`_data` writes at the position. A `d:` listing goes back to its first
name.

## CLOSE

`CLOSE #4`: HOME 13A5h → 1494h → `CH_CLOSE_HOOK`.

1. Not an `F` record (or a SYSCON one): the stock 13BEh.
2. `CH_FLUSH`: anything still buffered goes out as `tpi:chwr`; then
   **`tpi:chclose`**, PMR1 = 4, `CH_STATUS`. These two commands go back to
   back, which is exactly the case `CH_READY` exists for.
3. Pico: `CH_CLOSE` — only a record file with a record left open needs the
   card (to pad it); otherwise the stream is forgotten without it. An error
   (no card: J) is answered and the stream stays open on both sides, so
   CLOSE # can be repeated once the card is back.
4. 2068: every stream offset above this record's moved down 512, the
   current channel reselected as S if it was this one, the 512 bytes
   reclaimed; HOME 13A8h clears the STRMS entry.

## Records

`OPEN #4,"f:data.dat","u",30` opens a record file with 30-byte records
(PMR2 = 30; 1–254; 255 or more is sent as 255 and refused with Q). A record
file sends at every CR, so a record longer than 30 is Report Q on the
PRINT that made it; `PRINT #4;TAB n;…` and `INPUT #4;TAB n;…` seek to
record n, the TAB arriving at the Pico as the escape `17h lo hi` in the
`tpi:chwr` data. CLOSE pads a record left open by a trailing `;` to its
full length ([../firmware/channels.md](../firmware/channels.md), [user
manual §6.7](../../manual/user-manual.md#67-records-jumping-straight-to-what-you-want)).

## `d:` listings

`OPEN #5,"d:games/*.tap"` (mode `r`, no length): `CH_OPEN_HOOK` sends the
spec whole (`tpi:chopen r d:games/*.tap`); the Pico lists the names
(`DIR_NAMES`: folders first with a `/`, then files) into an in-memory
stream, and `INPUT #5;n$` reads one name per line until Report 8. A mode
other than `r` or a record length is Q. The names are read from the card
once, at OPEN: each `tpi:chrd` after that is answered from RAM with no
mount (`CHANNELS.in_memory`, since #404).

## The speech channel (`v:`)

`OPEN #4,"v:"` on the v3 card (#375): `CH_OPEN_HOOK` sends the spec whole
(`tpi:chopen r v:`, any mode). `SD_NEEDED` lets it through with no card
(`CH_NOCARD_PATH`); `CH_OPEN` answers F on a board without speech, Q for a
record length or anything after `v:`, else opens a speech stream
(`CHANNELS.open_speech(4, board.say)`). The record is an ordinary `'F'`
record with `R_FLAGS` bit 1 (`REC_FLAGS`).

`PRINT #4;"HELLO THERE"`: `CH_OUT` buffers the bytes and, because of bit 1,
flushes at the CR: one `tpi:chwr` with the line. `SD_NEEDED` passes it with
no card (`CHANNELS.in_memory(4)`), and `CH_WRITE` runs `CHANNELS.write`
without `SD_CALL`: `TextOut` spells out keywords and drops control codes,
and each complete line goes to `board.say`, which queues its allophones for
core 1 and returns at once — the 2068 carries on while the card speaks. A
line over 64 bytes arrives in pieces and is said whole at its CR; `PRINT
#4;"BYE";` (no CR) is said at `CLOSE #4`. Speech off (it never started at
boot) is J on the `PRINT`; an unknown `[NAME]` Q. `INPUT #4` is Q: the
stream is only written.

## The command channel (`x:`)

`OPEN #4,"x:"` (#404): `CH_OPEN_HOOK` sends the spec whole (`tpi:chopen
r x:`, any mode). `SD_NEEDED` lets it through with no card
(`CH_NOCARD_PATH`); `CH_OPEN` answers Q for a record length or anything
after `x:`, else opens a command stream (`CHANNELS.open_command(4,
X_RUN)`). The record is an ordinary `'F'` record with `R_FLAGS` bits 1 and
2 (`REC_FLAGS`).

`PRINT #4;"dir"`: `CH_OUT` buffers the bytes, and because of bit 1 flushes
at the CR: one `tpi:chwr` with the line. `SD_NEEDED` passes it with no card
(`CHANNELS.in_memory(4)`); `CH_WRITE` runs `CHANNELS.write` without
`SD_CALL`, and `Channels._command` runs the line through `X_RUN` and keeps
the answer in the channel. `path` and `mount` need nothing but RAM; `dir`
and `info` mount the card for themselves (`dir` brings the folder index up
to date with `LISTING_FRESHEN`, then answers with an `XDirText` over it).
The `tpi:chwr` answers its status: an unknown command is Q on the `PRINT`,
`dir` with no card J.

`INPUT #4;d`: `CH_IN` finds its buffer empty, flushes (nothing), and
`CH_FETCH` sends `tpi:chrd`; `CH_READ` reads the answer from RAM with no
mount, up to 255 bytes (`XDirText.chunk` builds just those rows), and
`CH_IN` hands them out a byte at a time until the CR, which `INPUT` takes
as the end of the line. Further `INPUT #4` read on from the same 255 bytes,
then fetch again. Past the end of the answer the Pico sends status 7 and
`INPUT` stops with Report 8, so `dir` gives its counts first: two lines,
the folders and the files, then one 32-character row each.

`PRINT #4;"path"` after a `dir` read only in part: every byte `CH_OUT`
takes on an `x:` record clears `R_INN` and `R_INP` (`IN_DROP`, because of
bit 2), so the rows `CH_IN` had read ahead are gone; on the Pico,
`_command` starts the new answer from its beginning. The next `INPUT #4`
fetches the path, not the rest of the listing. The answer lives in the
channel until the next command, `CLOSE #4`, or the stream's next OPEN.

## Errors inside the module

Every one of these runs inside GUARDED: a report raised inside the module
or in the HOME code it calls (Report 4 from MAKE-ROOM, a refusal) restores
the bank stack through HOME's H_TRAP before going on to the normal error
handling ([../rom/exrom-fdd.md](../rom/exrom-fdd.md#guarded)). Every entry
from HOME runs the bank switch under `DI`, because a channel switches banks
for every character.

## What goes wrong, and where

| Failure | Where | BASIC sees |
|---|---|---|
| no card | the card gate (`x:` `dir`: `X_RUN`) | J (bare); the stream stays as it was |
| a missing file for `r`, a missing folder | `CH_OPEN` | F, no channel |
| a bad mode, a record too long, `TAB 0` with data | `CH_OPEN`, `CH_WRITE` | Q |
| the end of the file | `CH_READ` → 7 | 8 End of file |
| a starved FIFO in the data phase | `CH_FETCH`'s XOR | R |
| the Pico's tail not finished before the next SYNC | `CH_SEND`'s IDLE wait (~1 s) | — (prevented); without it, T |
| NEW or a reset with channels open | the 2068's records are gone; the Pico's table keeps the streams | nothing: the next OPEN of the stream number replaces the stale entry |

## Where to read more

- The ROM side: [../rom/exrom-fdd.md](../rom/exrom-fdd.md#the-channel-driver).
- The Pico side: [../firmware/tspico-disk.md](../firmware/tspico-disk.md#open--channels-tpichopen-tpichwr-tpichrd-tpichclose),
  [../firmware/channels.md](../firmware/channels.md).
- Byte by byte: [PROTOCOL.md §7](../../PROTOCOL.md#7-the-channel-commands).
