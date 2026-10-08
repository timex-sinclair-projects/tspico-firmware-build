# EXROM 3000h: the disk module

Source: [`src/rom/fdd/fddcmd.asm`](../../../src/rom/fdd/fddcmd.asm) (all
1488 lines), assembled by [`tools/build-rom.py`](../../../tools/build-rom.py)
at EXROM 3000h–37B4h and spliced into the SYNC layer's image
(`src/rom/TSPICO-SYNC.ROM`) with the patches that call it, giving
`src/rom/TSPICO-23.ROM` ([overview.md](overview.md#toolsbuild-rompy-the-disk-command-layer)); the result read in
[`tspico-22-exrom.labelled.asm`](../../rom-analysis/disasm/tspico-22-exrom.labelled.asm).

The module and its patches are ROM 2.3's last layer (2.2's, plus #227 and
#228: see `PS_READ` and [overview.md](overview.md)). The module gives the
2068's dormant disk keywords — CAT, MOVE, ERASE, FORMAT — real meanings
on the SD card; adds
`SAVE`/`LOAD`/`VERIFY`/`MERGE "f:path"` for plain files; adds file
channels: `OPEN #n,"f:path","mode"[,reclen]`, `PRINT #`, `INPUT #`,
`CLOSE #`, and `"d:"` directory listings; adds response function 88h (a
Y/N prompt on the lower screen); makes the BIOS C_END report a timeout
as J, never F; and, from ROM 2.3, replaces the string reader every response
function prints with (`PS_READ`). Everything is turned into `tpi:` commands the firmware already
answers ([../firmware/tspico-disk.md](../firmware/tspico-disk.md)). The
design is [FDD_COMMANDS_DESIGN.md](../../FDD_COMMANDS_DESIGN.md) and the
specification [DISK_COMMANDS_SPEC.md](../../DISK_COMMANDS_SPEC.md); the
byte-level change list is in [the build history](../../ROM_CHANGES.md#rom-21-the-module-at-exrom-3000h).

The module is 1973 bytes (1919 in ROM 2.2; `PS_READ` added 54 at the end). It enters the 2068's code only through a vector
table at its start, reached from HOME and EXROM patches, so it can be
rebuilt without moving any entry point. Every entry from HOME runs inside
GUARDED, an error frame that keeps the RAM bank stack straight when a
report is raised. Commands are built in the calculator-stack workspace and
sent either through the `SAVE "tpi:"` machinery the ROM has had since 1.1
(entered past its name-length gate, so arguments can be longer) or byte by byte through
the Pico Interface BIOS.

## Map

| Source lines | EXROM | What |
|---|---|---|
| 34–136 | — | the `EQU`s: base, ROM addresses, system variables, the channel record, tokens |
| 143–164 | 3000h–3020h | the vector table |
| 166–177 | 3021h | `TAPE_MODE` |
| 192–215 | 3029h | `G_BEEP` |
| 217–275 | | the `G_*` entries, `GUARDED`, `JP_HL` |
| 277–297 | | `FDD_MAIN`, the signature, `FDD_VERSION` (30AFh) |
| 299–391 | | `FDD_CAT`, `FDD_ONE_ARG`, `FDD_MOVE`, `NONSENSE`, `TOO_LONG` |
| 393–467 | | the parsing helpers |
| 469–568 | | building and sending a command: `BUILD_START` … `TPI_SEND`, `COPY_CSTR` |
| 570–806 | | `f:` files: `F_HOOK`, `PEEK_NAME`, `SEND_FOPEN`, `TXX`, `TX_STR`, `WF_FAIL`, `C_FAIL`, `C_END2`, `FOPEN_TXT` |
| 808–828 | | `LOWER_LOOP` (function 88h) |
| 830–1385 | | the channel driver |
| 1387–1405 | | `HEXDIG`, `STRLEN` |
| 1407–1419 | to 3777h | the command strings, `MODE_R` |
| 1421–1435 | 3778h–377Eh | `PRELOAD` |
| 1437–1488 | 377Fh–37B4h | `PS_READ` (ROM 2.3's string reader), `FDD_END` |

Labels inside a routine (`.bare`, `.loop`) are explained with it. Names
that also exist elsewhere — CALL_HOME, SESSION_SETUP, READ_STATUS_BYTE,
SYNC_WRITE, BIOS_WF_NPH, BIOS_C_END, C_END_TAIL, BEEPER, CH_STATUS — are
explained in the chapters that own them, with a row here saying what the
module uses them for; the index links each name to the chapter of the file
that defines it. One of them means something different here: the module's
BEEPER is 2000h (the `JP` to BEEPER). (The module's READ_STATUS_BYTE, 02B9h, was
called READ_STATUS until #181, the name of a different routine at 0655h.)

## The `EQU`s

### Where it lives

| Name | Value | Meaning |
|---|---|---|
| `FDD_BASE` | 3000h | the `ORG`. Must equal `FDD_ORG` in `build-rom.py`, which also checks that `FDD_DISPATCH` lands there. 3000h–3FFFh is the module's 4K; 2300h–23D3h is the SYNC layer's |

### HOME and EXROM addresses the module calls

Every one is checked by `build-rom.py`'s ANCHORS before a build, so a base
ROM that moves one fails instead of jumping into the wrong code
([overview.md](overview.md#the-anchors)).

| Name | Value | What it is |
|---|---|---|
| `SESSION_NAMED` | EXROM 1AACh | SESSION_SETUP past its 5–31-character gate, DE = name, BC = length ([exrom-driver.md](exrom-driver.md#session_setup-1a73h-is-this-name-a-command)) |
| `CALL_HOME` | EXROM 03DDh | the EXROM→HOME returning thunk |
| `H_EXPT_STR` | HOME 1BEFh | syntax class 0Ah: SCANNING, then Report C unless the result is a string |
| `H_TEST_ROOM` | HOME 1FBBh | TEST-ROOM: Report 4 unless BC bytes fit at STKEND |
| `SESSION_SETUP` | EXROM 1A73h | where 01D2h went before F_HOOK |
| `SAVE_ETC_BODY` | EXROM 01D5h | the stock SAVE-ETC after SESSION_SETUP's non-command exit (BC = 11h) |
| `STATUS_REPORT` | EXROM 1BF3h | `STATUS_TO_REPORT`: A = status − 1 → the report |
| `SYNC_WRITE` | EXROM 2300h | the SYNC layer's: SYNC, wait READY + IDLE, `OUT (0Eh),A` |
| `BIOS_TX_A` | EXROM 1846h | BIOS: `OUT (0Eh),A` |
| `BIOS_RX_A` | EXROM 1848h | BIOS: `IN A,(0Eh)` |
| `BIOS_C_END` | EXROM 184Ah | BIOS: the status; NC OK, C with A = status − 1 (through the module's C_END2) |
| `BIOS_WF_NPH` | EXROM 184Ch | BIOS: wait for the Pico; C with A = 02h / 0Ch / 1Ch |
| `C_END_TAIL` | EXROM 227Fh | C_END after its wait: read the status, run any response function |
| `READ_STATUS_BYTE` | EXROM 02B9h | the response function's own status byte (the curated name; `READ_STATUS` until #181) |
| `OPEN_STREAM` | EXROM 0426h | open stream A (through HOME CHAN-OPEN) |
| `LOOP_BODY` | EXROM 21E6h | function 86h's loop after its opening |
| `TSPICO_READ_DATA` | EXROM 2298h | `IN A,(0Eh) / AND A / RET`: one byte from the Pico, no ready-wait, Z for 00h. `PS_READ`'s read |
| `PRINT_A` | EXROM 05FAh | `LD (IY+52h),FFh` (SCR_CT, so the 2068 never stops with its own "scroll?") then RST 10h through CALL_HOME: what the v1.1 reader printed with. `PS_READ`'s print |
| `THUNK_HX` | HOME 03FCh | the returning HOME→EXROM thunk (named; the module never calls it — HOME's stubs do) |
| `H_OUT_STUB` | HOME 14A0h | `DI / LD HL,CH_OUT_VEC / CALL 03FCh / EI / RET` |
| `H_IN_STUB` | HOME 14A9h | the same for `CH_IN_VEC` |
| `H_MAKE_ROOM` | HOME 12BBh | MAKE-ROOM: BC bytes after (HL); Report 4 |
| `H_RECLAIM` | HOME 1750h | RECLAIM: remove BC bytes at HL |
| `H_CHAN_OPEN` | HOME 1230h | CHAN-OPEN: select stream A |
| `H_EXPT_1NUM` | HOME 1BE5h | syntax class 06h: a numeric expression |
| `H_FIND_INT2` | HOME 1F23h | the number on the calculator stack → BC; Report B |
| `H_TRAP` | HOME 14B2h | GUARDED's error trap ([home.md](home.md#1488h14c5h-the-modules-home-entries)) |
| `BEEPER` | EXROM 2000h | the `JP` to the relocated BEEPER |

### System variables

| Name | Value | Use |
|---|---|---|
| `CH_ADD` | 5C5Dh | the next character of the BASIC line: the module's parser |
| `FLAGS` | 5C3Bh | bit 7: 1 = run time, 0 = syntax check |
| `TADDR` | 5C74h | T-ADDR: its low byte is the pre-header's TADDR |
| `STKEND` | 5C65h | the calculator stack's end: strings are popped from below it, commands built above it |
| `FRAMES` | 5C78h | the session id's seed |
| `SESSION_ID` | 5DD1h | where the session id is kept |
| `IY_SYSVARS` | 5C3Ah | what HOME expects in IY (the bank switch clobbers IY) |
| `BANK_SV` | 5DCFh | pre-header byte 2 up to ROM 2.2 (always FFh); no longer read by the module |
| `ROM_ID` | 23h | not a variable: what ROM 2.3 sends as byte 2 of a command pre-header instead of `BANK_SV`, the same value as its version marker (HOME 0065h). `SEND_FOPEN` and `CH_SEND` send it, and `build-rom.py` patches `BUILD_PREHEADER_B` (1BB5h) to send it too, so the firmware knows which ROM sent each command (`rom_id`, shown by `tpi:info`, [../firmware/tspico-state.md](../firmware/tspico-state.md#rom_id), #227) |
| `MODE_SV` | 5DDBh | TPMODE; F_HOOK clears bits 7–4 as SESSION_SETUP's non-command exit does; TAPE_MODE clears bit 1 |
| `MODE_SET_OK` | 2105h | where `tpi:sdcard` and `tpi:picopt` end: `CALL S_MODE` (1862h) with A, `CALL 042Fh`, `JP 1B72h` ("0 OK"); TAPE_MODE jumps here |
| `CURCHL` | 5C51h | the current channel's record |
| `STRMS` | 5C10h | the stream table, streams −3 to 15, two bytes each |
| `CHANS` | 5C4Fh | the channel area |
| `PROG` | 5C53h | the BASIC program, just above the channel area |
| `STREAM_N` | 5CCBh | the stream OPEN/CLOSE # is working on (stored by HOME 140Fh) |
| `ERR_SP` | 5C3Dh | the error handler's stack frame |
| `BANK_SP` | 65CEh | the RAM bank stack's pointer |

All in [sysvars.md](sysvars.md).

### The channel record

An `F` channel takes `CH_ALLOC` bytes in CHANS, with the record `R_PAD`
bytes into the allocation. Offsets from the record's start:

| Name | Value | Field |
|---|---|---|
| `R_OUT` | 0 | output routine: HOME 14A0h (→ `CH_OUT`) |
| `R_IN` | 2 | input routine: HOME 14A9h (→ `CH_IN`) |
| `R_LETTER` | 4 | `'F'` |
| `R_STRM` | 5 | the stream number: the Pico's key for the open file |
| `R_PAD` | 6 | bytes before the record in its allocation (0–128) |
| `R_OUTN` | 7 | bytes waiting in the output buffer |
| `R_INN` | 8 | bytes in the input buffer |
| `R_INP` | 9 | the next input byte to hand out |
| `R_FLAGS` | 10 | bit 0: a record file (OPEN # gave a length) |
| `R_OUTBUF` | 11 | the output buffer |
| `OUTMAX` | 64 | its size: `tpi:chwr` sends the bytes as hex, 9 + 128 < 256 |
| `R_INBUF` | 75 | the input buffer |
| `INMAX` | 255 | its size: one `tpi:chrd` answer |
| `REC_LEN` | 330 | the record's length |
| `CH_ALLOC` | 200h (512) | an allocation: `REC_LEN` + the largest pad fits, and a multiple of 256 so reclaiming one never changes the low byte of another's offset |

The record's first five bytes are the 2068's standard channel header (two
routine addresses and the letter), so `RST 10` and INPUT treat it as any
other channel. The two addresses are fixed HOME stubs, never addresses in
the module, so nothing in a record moves when CHANS does or the module is
rebuilt ([home.md](home.md#1488h14c5h-the-modules-home-entries)). The
pad keeps both bytes of the stream's offset below 80h, because CHAN-OPEN
treats an offset whose high bit is set as a SYSCON channel (its `D OR E ≥
80h` test, an anchor).

### Constants

| Name | Value | Meaning |
|---|---|---|
| `STREAM_LOWER` | FDh | stream −3, K, the lower screen |
| `READ_DELAY` | 16 | × 16 T-states between data-phase reads, ~75 µs: the Pico feeds a 4-deep FIFO |
| `TOK_SCREEN` | AAh | SCREEN$ |
| `TOK_CODE` | AFh | CODE |
| `TOK_LINE` | CAh | LINE |
| `TOK_DATA` | E4h | DATA |
| `MAX_ARG` | 64 | the longest argument; longer is Report F |
| `ROOM` | 160 | workspace a command may need: 2 × MAX_ARG + 32 |
| `CR` | 0Dh | BASIC's end of line |
| `SEP` | `'\|'` | MOVE's source/destination separator: cannot occur in a FAT name |
| `TOK_TO` | CCh | TO |
| `TOK_CAT` | CFh | CAT |
| `TOK_FORMAT` | D0h | FORMAT |
| `TOK_MOVE` | D1h | MOVE |
| `TOK_ERASE` | D2h | ERASE |

## The vector table

### `FDD_DISPATCH` (3000h)

The first of ten `JP`s; `build-rom.py` refuses a build where this label is
not at 3000h. The patches point at these vectors, never at routines:

| Name | EXROM | Jumps to | Reached from |
|---|---|---|---|
| `FDD_DISPATCH` | 3000h | `G_MAIN` | HOME 25D6h, the disk keywords |
| `F_HOOK_VEC` | 3003h | `F_HOOK` | EXROM 01D2h, SAVE-ETC's jump to SESSION_SETUP |
| `LOWER_VEC` | 3006h | `LOWER_LOOP` | EXROM 2213h, function 88h |
| `CH_OUT_VEC` | 3009h | `G_OUT` | HOME 14A0h, an `F` record's output |
| `CH_IN_VEC` | 300Ch | `G_IN` | HOME 14A9h, its input |
| `CH_OPEN_VEC` | 300Fh | `G_OPEN` | HOME 1488h, OPEN # |
| `CH_CLOSE_VEC` | 3012h | `G_CLOSE` | HOME 1494h, CLOSE # |
| `BEEP_VEC` | 3015h | `G_BEEP` | HOME 03F3h → 041Ch, BEEPER |
| `OPEN_SYN_VEC` | 3018h | `G_OSYN` | HOME 14BDh, OPEN #'s syntax |
| `C_END_VEC` | 301Bh | `C_END2` | EXROM 184Fh, the BIOS C_END |
| `TAPE_VEC` | 301Eh | `TAPE_MODE` | EXROM 20BEh, `SAVE "tpi:tape"` |

The HOME entries come through the returning thunk under `DI`; the EXROM
ones (01D2h, 2213h, 184Fh, 20BEh) are plain jumps within the EXROM.

### `TAPE_MODE` (3021h)

`SAVE "tpi:tape"`: LOAD and SAVE back to the cassette, the printer switch
left as it is. `LD A,(MODE_SV)` / `RES 1,A` / `JP MODE_SET_OK` (2105h),
which stores TPMODE through S_MODE and ends the statement with "0 OK",
as `tpi:sdcard` and `tpi:picopt` do.

Reached by `JP TAPE_VEC` at EXROM 20BEh, once the switch-word code has
matched the four letters and the length 8 and cleared bits 7–6 of TPMODE
([sysvars.md](sysvars.md#5ddbh-tpmode-peek-24027)). A held the length
test's 8 there, so TPMODE is read again.

Why: 1.1 did `CALL 1861h` here, and so does the SYNC layer's image the
module is built on — `XOR A` into S_MODE — setting TPMODE to 0 and so clearing the printer switch (bit 0) as well,
while `tpi:sdcard` sets only bit 1: `tpi:picopt`, `tpi:tape`,
`tpi:sdcard` left printing on the 2068 (#176). The five bytes at 20BEh
could not hold the fix (a reload, a `RES` and the jump to 2105h are
seven), hence the vector. [`rom_tpmode_hosttest.py`](../../../src/test/rom_tpmode_hosttest.py)
runs the switch words from the committed image.

## Entries and the error frame

### `G_BEEP` (3029h)

BEEPER's new entry (the module's patch moves HOME's thunk here, [home.md](home.md#03f3h0420h-beeper-moved-out)).
With HL = C8h (the editor's key click, from HOME 0A97h) and the current
channel an `F` record (CURCHL + 4 = `'F'`), it skips the beep: INPUT #
from a file takes characters through the editor, which clicks for every
one, and the speaker chattered through every line read (the Spectrum did
the same with microdrives). Otherwise `CALL BEEPER`. Either way it ends
with `DI`: BEEPER ends with `EI`, and the switch back to HOME must not be
interrupted; HOME's 041Ch does the `EI`. The keyboard click, BEEP and the
error buzz (HOME 1A90h) are unchanged.

### `G_MAIN`, `G_OUT`, `G_IN`, `G_OPEN`, `G_OSYN`, `G_CLOSE`

Each is `LD HL,routine / JR GUARDED` (the last falls in):

| Entry | Routine |
|---|---|
| `G_MAIN` | `FDD_MAIN` |
| `G_OUT` | `CH_OUT` |
| `G_IN` | `CH_IN` |
| `G_OPEN` | `CH_OPEN_HOOK` |
| `G_OSYN` | `OPEN_SYNTAX` |
| `G_CLOSE` | `CH_CLOSE_HOOK` |

### `GUARDED`

Runs HL's routine under an error frame, so that a report raised inside the
module — or in the HOME code it calls — does not leak the RAM bank stack.

```text
GUARDED: PUSH HL                      ; the routine
         LD HL,(ERR_SP) / EX (SP),HL  ; [old ERR_SP]
         PUSH HL
         LD HL,(BANK_SP) / INC HL × 4 / EX (SP),HL   ; [the bank stack before the thunk]
         PUSH HL
         LD HL,H_TRAP / EX (SP),HL    ; [H_TRAP]
         LD (ERR_SP),SP               ; a report now returns through H_TRAP
         CALL JP_HL                   ; the routine
         DI                           ; the switch back must not be interrupted
         INC SP × 4                   ; drop H_TRAP and the bank-stack value
         EX (SP),HL / LD (ERR_SP),HL  ; ERR_SP back
         POP HL
         RET
```

Why: the returning thunk (HOME 03FCh) pushes a frame on the RAM bank stack
at (65CEh) and pops it on the way back. `RST 8` unwinds the Z80 stack to
ERR_SP but never the bank stack, so each report raised inside a thunked
call left it 4–8 bytes lower; after about 16 errors it overwrote the
bank-switch code below it. Both ROMs' `RST 8` end `LD SP,(ERR_SP)`, HOME
1354h, `RET` with HOME paged — so the trap must be in HOME, at 14B2h, which
puts 65CEh back to the value recorded here (the pointer as it was before
the thunk's 4-byte frame), restores ERR_SP, `EI`, and returns into the old
handler as the `RST 8` would have ([home.md](home.md#1488h14c5h-the-modules-home-entries)).

Registers: A, F, BC and DE reach the routine; it returns AF, BC, DE and HL
(the `EX (SP),HL` / `POP HL` pair preserves HL across the restore).
Interrupts: every HOME stub enters under `DI` because the 2068's bank
switch writes port FFh then F4h with interrupts on, and an interrupt
between the two runs `RST 38h` over the empty DOCK; a channel switches for
every character and hit that window within a few hundred characters in
ZEsarUX. `FDD_MAIN` re-enables interrupts for its own work (it may wait at
a prompt with `HALT`); `GUARDED`'s `DI` closes them again before the
switch back.

### `JP_HL`

`JP (HL)`: lets `GUARDED` `CALL` the routine in HL.

### `FDD_MAIN`

The disk keywords' routine, entered on **both** passes (HOME 25D6h has no
other way to hand over the syntax check), with B = the token.

1. `LD IY,IY_SYSVARS`: the bank call clobbers IY, and HOME routines need it.
2. `EI`: HOME's hook entered under `DI`, and CAT's "Scroll?" and the Y/N
   prompts wait with `HALT`.
3. CAT → `FDD_CAT`; MOVE → `FDD_MOVE`; ERASE → `FDD_ONE_ARG` with HL =
   `CMD_ERASE`; FORMAT → `FDD_ONE_ARG` with `CMD_FORMAT`; any other token →
   `RET` (no-op; nothing else reaches 25D6h).

After it, at 30A8h, `"FDDCMD",0` — a signature nothing checks;
`build-rom.py` checks `FDD_DISPATCH`'s address instead, as the comment says
(until #181 it claimed "build.py verifies this").

### `FDD_VERSION` (30AFh)

One byte, 8: the module's revision number. Nothing reads it; the
ROM's version for programs is `PEEK 101` and G_VERS
([overview.md](overview.md#which-rom-is-this)).

## The disk keywords

Each keyword routine follows one pattern: parse the arguments with HOME's
expression evaluator (so syntax errors are marked in the line as usual),
return on the syntax pass, and at run time pop the strings, build a
`tpi:` command in the workspace above STKEND, and send it. What the
firmware does with each command is [../firmware/tspico-disk.md](../firmware/tspico-disk.md).

| BASIC | Sent | Firmware |
|---|---|---|
| `CAT` | `tpi:dir` | [`DIR`](../firmware/tspico-commands.md#dirpre-cmd) |
| `CAT ""` | `tpi:tapdir` | [`TAPDIR`](../firmware/tspico-commands.md#tapdirpre-cmd) |
| `CAT x` | `tpi:dir x` | [`CATALOG`](../firmware/tspico-disk.md#catalogarg) |
| `MOVE TO x` | `tpi:cd x` | [`CDIR`](../firmware/tspico-commands.md#cdirpre-cmd) |
| `MOVE TO ""` | `tpi:cd -` (back to the previous folder) | the same |
| `MOVE a TO b` | `tpi:copy a\|b` | [`DISK_COPY`](../firmware/tspico-disk.md#disk_copypre-cmd) |
| `ERASE x` | `tpi:erase x` | [`DISK_ERASE`](../firmware/tspico-disk.md#disk_erasepre-cmd) |
| `FORMAT x` | `tpi:format x` | [`DISK_FORMAT`](../firmware/tspico-disk.md#disk_formatpre-cmd) |

MOVE copies; there is no keyword for rename (`SAVE "tpi:ren a|b"`).

### `FDD_CAT`

`AT_END`: a bare `CAT` → `.bare`: `RUNTIME`, return on the syntax pass, else
`SEND_PREFIX` with `CMD_DIR`. Otherwise `EXPT_STR_END` (one string
expression that ends the statement; return on the syntax pass), `POP_STR`;
an empty string → `SEND_PREFIX` with `CMD_TAPDIR` (the mounted tape's
blocks, as `CAT ""` lists a tape on a stock 2068); anything else →
`SEND_ONE` with `CMD_DIR_ARG`.

### `FDD_ONE_ARG`

ERASE and FORMAT; HL = the prefix. The argument is required: `AT_END` →
`NONSENSE`. `EXPT_STR_END`, return on the syntax pass; `POP_STR`;
`NOT_EMPTY` (an empty name is Report F); `SEND_ONE`.

### `FDD_MOVE`

`SKIP_SPACES`; `TO` straight away → `.cd`. Otherwise a source is required
(`AT_END` → `NONSENSE`): `HC_EXPT_STR` (the source), `TO` required (else
`NONSENSE`), `NEXT_CHAR` past it, `EXPT_STR_END` (the destination); return
on the syntax pass. At run time pop the destination (on top) then the
source, both `NOT_EMPTY`; `BUILD_START` with `CMD_COPY`, then the source,
`SEP` (`|`), the destination; `SEND_TAIL`.

`.cd`: `NEXT_CHAR` past `TO`, `EXPT_STR_END`, `POP_STR`; an empty string →
`CMD_CD_BACK` (`tpi:cd -`); else `SEND_ONE` with `CMD_CD`.

`|` is the separator because it cannot occur in a FAT name; a command typed
by hand may use a space instead, which the firmware also accepts
(`catalog.split_pair`, [../firmware/catalog.md](../firmware/catalog.md)).

### `NONSENSE`

`RST 8 / DEFB 0Bh`: Report C. On the syntax pass the 2068 marks the error
in the line.

### `TOO_LONG`

`RST 8 / DEFB 0Eh`: Report F — an argument over `MAX_ARG` characters, or
an empty one.

## Parsing helpers

All work on CH_ADD (the next character of the statement) the way HOME's
own syntax routines do.

### `SKIP_SPACES`

A = the character at CH_ADD, after stepping CH_ADD over spaces.

### `NEXT_CHAR`

CH_ADD + 1: step over one character (a token such as TO).

### `AT_END`

`SKIP_SPACES`, then Z if it is CR or `:` — the statement ends here.

### `EXPT_STR_END`

`HC_EXPT_STR`, then `AT_END` or `NONSENSE`, then falls into `RUNTIME`:
returns Z on the syntax pass (nothing more to do), NZ at run time with the
string on the calculator stack.

### `RUNTIME`

`LD A,(FLAGS) / AND 80h / RET`: NZ at run time, Z on the syntax pass.

### `HC_EXPT_STR`

`PUSH IX / EXX / LD HL,H_EXPT_STR / JP CALL_HOME`: HOME's class-0Ah
routine — evaluate an expression at CH_ADD, Report C unless it is a
string; at run time the string is left on the calculator stack. The other
`HC_*` helpers below are the same three instructions for another HOME
routine.

### `POP_STR`

Pops a string descriptor off the calculator stack (STKEND − 5): DE = the
text, BC = the length; STKEND moved down. Report F (`TOO_LONG`) if it is
longer than `MAX_ARG` (64).

### `NOT_EMPTY`

Report F if BC = 0; returns otherwise.

## Building and sending a command

### `BUILD_START`

`HC_TEST_ROOM` with BC = `ROOM` (160: Report 4 if the workspace has not
that much room), then copies the NUL-ended prefix at HL to STKEND.
Returns HL = the command's start, DE = the next free byte.

### `HC_TEST_ROOM`

HOME's TEST-ROOM through `CALL_HOME`: Report 4 unless BC bytes fit above
STKEND.

### `SEND_PREFIX`

`BUILD_START`, push the start, `SEND_TAIL`: a command that is only its
prefix (`tpi:dir`, `tpi:tapdir`, `tpi:cd -`).

### `SEND_ONE`

The prefix (HL) followed by one string (DE, BC): `BUILD_START`, `LDIR` the
string after it, falls into `SEND_TAIL`.

### `SEND_TAIL`

DE = the command's end, its start on the stack. Computes the length,
writes a five-byte string descriptor after the text — `00`, start, length,
as `SAVE "..."` leaves its name on the calculator stack — moves STKEND past
it, sets T-ADDR (both bytes) to 0 (a SAVE: TADDR 0, a command), and falls
into `TPI_SEND`.

### `TPI_SEND`

SESSION_SETUP without its gate. It repeats SESSION_SETUP's opening
(1A73h–1A7Dh: `PUSH HL / PUSH DE`, the session id from FRAMES, never 0),
reads the descriptor just written from the top of the calculator stack,
and jumps to `SESSION_NAMED` (1AACh) with DE = the text and BC = the
length. From there the command goes exactly as `SAVE "tpi:…"` does
([exrom-driver.md](exrom-driver.md#session_setup-1a73h-is-this-name-a-command)):
the `tpi:` check, `BUILD_PREHEADER_B`, the body, the answer through the
function chain (so a listing pages with "Scroll?"), and `STATUS_OK` or a
report. Why skip the gate: SESSION_SETUP only takes names of 5–31
characters, which is BASIC's limit for `SAVE "tpi:…"` text, but everything
past it keeps the name as a pointer and a 16-bit length, and the Pico sizes
its buffer from the pre-header; so a `MOVE` of two 64-character paths
(137 characters with the prefix) goes through. The anchors at 1A73h and
1AACh guard both halves of this.

### `COPY_CSTR`

Copies the NUL-ended string at HL to DE (not the NUL); HL and DE end past
it.

## `f:` files

`SAVE "f:path"`, `LOAD "f:path"`, and the same with VERIFY and MERGE, read
and write plain files on the card — the path resolves as CAT's does,
from the current folder, with `/` the card's `TAP` folder — instead of blocks in a TAP. The 2068's own SAVE and
LOAD code runs as usual; the module only tells the Pico, before the first
block, that this statement's blocks belong to a file
(`tpi:fopen`), and shortens the name so the stock code accepts it. The
Pico then writes the SAVE's data to the file (with a +3DOS header,
[../firmware/native.md](../firmware/native.md)) or serves the file to the
LOAD as a one-shot tape ([../firmware/tspico-disk.md](../firmware/tspico-disk.md#native_openpre-cmd),
[../flows/save.md](../flows/save.md)).

### `F_HOOK`

Reached through `F_HOOK_VEC` from EXROM 01D2h, which was SAVE-ETC's only
jump to SESSION_SETUP — so at run time only (01CCh sends the syntax pass
elsewhere), with the name on the calculator stack, T-ADDR 0–3 (SAVE, LOAD,
VERIFY, MERGE) and CH_ADD past the name.

1. `PUSH HL / PUSH DE`, as SESSION_SETUP does. `PEEK_NAME`.
2. Not ours → `.stock`: pop them and `JP SESSION_SETUP` — every other name
   goes on exactly as before. Ours: a length of 3–255 starting `f:` (the
   `f` either case, `AND DFh`).
3. A path over 64 characters (length ≥ 67) → `TOO_LONG`, Report F.
4. The session id, from FRAMES as SESSION_SETUP makes it (never 0), into
   5DD1h: the `tpi:fopen` and the blocks that follow carry the same one,
   which is how the Pico ties them together.
5. `SEND_FOPEN` (IX saved around it). An error status raises its report
   here, before any block is sent.
6. Shorten the name in place on the calculator stack. SAVE: the descriptor
   now points 2 bytes on (past `f:`) with the length cut to at most 10 — a
   stand-in the tape header needs and the Pico ignores. LOAD, VERIFY,
   MERGE: length 0, `""`, which matches any header: the one-shot tape holds
   one file.
7. TPMODE AND 0Fh (as SESSION_SETUP's exit), `POP DE / POP HL`, BC = 11h,
   `JP SAVE_ETC_BODY` (01D5h): the stock SAVE-ETC body, exactly as for a
   plain name. TPMODE bit 1 must be set (the default) for the blocks to go
   to the Pico; with `tpi:tape` they would go to tape *(inferred from the
   path through 1879h/196Dh; the `tpi:fopen` would already have been sent)*.

### `PEEK_NAME`

The string on top of the calculator stack, not popped: DE = the text, BC =
the length (from STKEND − 4).

### `SEND_FOPEN`

`tpi:fopen <path>`, sent by hand through the BIOS rather than through
SESSION_SETUP, because it runs in the middle of a SAVE/LOAD statement and
must return to it: the BIOS returns, prints only what the Pico asks it to,
and leaves CH_ADD alone.

1. The token after the name, looking past spaces from CH_ADD (which is not
   moved): CODE, SCREEN$, DATA or LINE, else 0.
2. The path (past `f:`) and its length B; the command's length C = B +
   `FOPEN_LEN` (under 128).
3. **The pre-header**, D the running XOR from `'B'`: SYNC_WRITE `'B'`; TADDR
   0 (a command); `ROM_ID` (`LD A,ROM_ID / NOP` where `LD A,(BANK_SV)` was,
   so no address after it moved); PMR1 low = T-ADDR (0 SAVE, 1 LOAD, 2 VERIFY, 3
   MERGE), PMR1 high = the token; PMR2 = the session id; the length (C, 0);
   the XOR.
4. `PRELOAD` reads the pre-load: 0 is Report J at once; any other value
   goes on (#179). `BIOS_WF_NPH`; a failure → `WF_FAIL`.
5. **The body**: `'D'` (D reseeded), the length, `FOPEN_TXT` ("tpi:fopen "),
   the path, the XOR.
6. `BIOS_C_END` (`C_END2`): NC → return. The Pico may first run a response
   function: for a SAVE over an existing file it asks "Replace NAME?
   (Y/N)" with function 88h on the lower screen (`LOWER_LOOP`), so the
   question does not land in a picture that `SAVE … SCREEN$` is about to
   save. A refusal is remembered by the Pico, which refuses the SAVE's
   header (the stock code then reports it). Carry → `C_FAIL`: F, Q, R … as
   for any command.

The firmware's handler is `NATIVE_OPEN` ([../firmware/tspico-disk.md](../firmware/tspico-disk.md#native_openpre-cmd));
the PMR1 encoding (operation in the low byte, the statement's modifier
token in the high byte) is what it reads to decide how to serve a LOAD.

Beware: the pre-load is not checked, unlike `SEND_DATA_BLOCK_D`'s. A Pico
that refused at the pre-load would still be sent the body *(inferred; the
firmware never refuses a command at its pre-load)*.

### `TXX`

`PUSH AF / XOR D / LD D,A / POP AF / JP BIOS_TX_A`: send A, folding it into
D.

### `TX_STR`

Send B (at least 1) bytes from HL through `TXX`.

### `WF_FAIL`

The Pico did not get to READY after the pre-header: A = 0Ch → Report D
(BREAK; the abort byte was already sent by BIOS_WF_NPH); 1Ch → Report T;
otherwise (02h, a timeout) Report J.

### `C_FAIL`

After a `BIOS_C_END` failure: 0Ch → D and 1Ch → T (`WF_FAIL`'s targets,
since `STATUS_REPORT` would call both D), anything else → `STATUS_REPORT`
with A = status − 1 (and 09h, the timeout, is J).

### `C_END2`

The BIOS C_END of ROM 2.2, reached from the table entry 184Ah → 184Fh
(patched) through `C_END_VEC`.

```text
C_END2: CALL BIOS_WF_NPH
        JP NC,C_END_TAIL      ; READY: read the status, run any function
        CP 02h
        SCF
        RET NZ                ; 0Ch BREAK, 1Ch reset: as they are
        LD A,09h              ; the timeout: J, never F
        RET                   ; carry still set
```

Why: the SYNC layer's BIOS_C_END (23CDh), which 184Fh reached before the
module's patch, fails with A = 02h both for a timeout (BIOS_WF_NPH's code)
and for status 3 (A = status − 1 = 02h, Report F), so a caller could not
tell a silent Pico from a bad file name — and this module's callers would
report a timeout as F. With C_END2 every failure comes back ready for
`STATUS_REPORT` or `C_FAIL`: an error status, A = status − 1 (01h R, 02h F
… 09h J, 0Ah and up D); a timeout, A = 09h (J, what the ROM's own commands
report); BREAK, 0Ch; a Pico reset, 1Ch. 0Ch and 1Ch are never status − 1
values, since the firmware's highest status is 11. Carry clear and A = 0
for status 1, as the BIOS always did. Machine-code callers of the BIOS get
the same contract ([PROTOCOL.md §9](../../PROTOCOL.md#9-the-pico-interface-bios-exrom-1840));
[`rom_cend_hosttest.py`](../../../src/test/rom_cend_hosttest.py) runs it in
a Z80 interpreter against the SYNC layer's BIOS_C_END for contrast.

### `FOPEN_TXT` and `FOPEN_LEN`

`"tpi:fopen "` and its length, 10.

## Function 88h

### `LOWER_LOOP`

Response function 88h: function 86h on the **lower** screen.

```text
LOWER_LOOP: CALL READ_STATUS_BYTE ; 02B9h: the function's own status
            PUSH AF
            LD A,STREAM_LOWER     ; FDh, K
            CALL OPEN_STREAM
            POP AF
            JP LOOP_BODY          ; 21E6h: 86h's loop, which prints through
                                  ;   the current channel and ends with its
                                  ;   own POP AF / RET
```

Exactly 86h's handler (`CALL 01C3h`, which opens stream FEh) with another
stream, so it has whatever 86h's loop does: from ROM 2.3 that is every key
sent as typed and `N` going round the loop like any other key, the Pico
ending it with `03h` (#227, [exrom-chunk1.md](exrom-chunk1.md#fn_86_yn_prompt-21e3h)). Reached from the function chain's last check at 2213h, which had
been dead (a second `CP 86h`) and the module's patch makes `CP 87h / JP
Z,3006h / RET` ([exrom-chunk1.md](exrom-chunk1.md#fn_dead_beep-2216h)). On
1.1 a 88h falls off the chain (Report D), so the firmware sends it only in reply
to `tpi:fopen`, which only this module sends. The lower screen starts
clear, so the firmware's 88h text has no leading CR; keep it to one line
([../firmware/tspico-messages.md](../firmware/tspico-messages.md#send_msg_prompt_ynprompt-echotrue-lowerfalse)).

## The channel driver

`OPEN #n,"f:path"[,"mode"[,reclen]]` builds an `F` record in CHANS and
points stream n at it; `PRINT #n`, `INPUT #n`, `LIST #n`, `INKEY$ #n` go
through the record's routines; `CLOSE #n` flushes it, tells the Pico and
takes the record out again. `OPEN #n,"d:[pattern]"` does the same with a
read-only listing of names. Modes: `r` read, `w` write (truncate), `a`
append, `u` update, each with an optional `b` (binary: no text
conversion); the Pico interprets them ([../firmware/channels.md](../firmware/channels.md)).
With a record length the file is a record file, and `PRINT #n;TAB r;…`
seeks to record r ([user manual ch 6](../../manual/user-manual.md#67-records-jumping-straight-to-what-you-want)).

Every exchange goes through the BIOS with a bare-status answer and keeps
CURCHL: these commands run in the middle of a `PRINT #` or `INPUT #`, and a
printed message would move the current channel to the screen. The firmware
answers channel commands READY but not IDLE until its tail is done, so
`CH_SEND` waits for IDLE before each SYNC
([../firmware/tspico-bus.md](../firmware/tspico-bus.md#ch_ready),
[../flows/channels.md](../flows/channels.md)).

### `CH_OPEN_HOOK`

OPEN # at run time. HOME 145Eh's `CALL 1465h` now goes to 1488h, which
comes here (through `G_OPEN`); the stream is in 5CCBh, the spec string on
top of the calculator stack, and CH_ADD is on the `,` of a mode, if any
(the syntax pass checked what follows: `OPEN_SYNTAX`).

1. `LD IY,IY_SYSVARS`; `PEEK_NAME`. Not ours → `STRMS_NC` (carry clear,
   HL = the STRMS entry, the stack untouched) and HOME's stock 1465h opens
   K, S or P as before. Ours: `d:` (any case, any length ≥ 2, the rest a
   pattern) or `f:` with at least one more character.
2. A spec over 64 characters after the prefix → `TOO_LONG` (F).
   `HC_TEST_ROOM` with `CH_ALLOC + ROOM`: Report 4 now, before the Pico
   hears of it, if the record and the command will not fit.
3. The mode and length: none → mode `"r"` (`MODE_R`), length 0. Otherwise
   `,` (else `NONSENSE`), `HC_EXPT_STR` (the mode); optionally `,` and
   `HC_EXPT_1NUM`, `HC_FIND_INT2` (the record length into BC); the
   statement must end (else `NONSENSE`). The mode is popped: `""` is `r`;
   1–3 characters are passed on; 4 or more is Report Q.
4. **`tpi:chopen <mode> <path>`**, built at STKEND: `CMD_CHOPEN`, the mode,
   a space, then the spec — without its `f:`, or whole for `d:` (the Pico
   lists it). A zero-length path is skipped (an `LDIR` with BC = 0 would
   copy 64K). PMR2 = the record length, or FFh if it is over 255 (the Pico
   answers Q). `CH_SEND` with A = the stream, no payload; `CH_STATUS` (F,
   Q … raise their reports; nothing has been allocated yet).
5. The spec is dropped from the calculator stack (STKEND − 5), as 1465h's
   STK-FETCH would have.
6. **The allocation**: it goes where CHANS' closing 80h is (PROG − 1, or
   PROG − 2 when one spare byte sits between that 80h and PROG, as on the
   2068). The pad: if the offset the record would have (record − CHANS + 1)
   has its low byte's bit 7 set, the record is moved in by 256 − L bytes
   so both bytes of the offset are below 80h — CHAN-OPEN would otherwise
   take it for a SYSCON channel. `HC_MAKE_ROOM` opens `CH_ALLOC` bytes after
   (start − 1) so the 80h moves up past them; the allocation is zeroed.
7. **The record**, IX = start + pad: `R_OUT` = 14A0h, `R_IN` = 14A9h,
   `R_LETTER` = `'F'`, `R_PAD`, `R_STRM` = the stream, `R_FLAGS` bit 0 if a
   record length was given.
8. DE = the offset (record − CHANS + 1), HL = the STRMS entry (`STRMS_HL`),
   carry set: HOME's 1461h stores DE there.

### `OPEN_SYNTAX`

OPEN #'s syntax pass after the spec. Stock 1438h called 2569h, which
skipped everything after the comma — and so never stored the hidden
five-byte form of a number there, so a record length could not be
evaluated at run time (Report C). 1438h now comes here (through HOME
14BDh and `G_OSYN`) with CH_ADD on the `,`: `NEXT_CHAR`, `HC_EXPT_STR`
(the mode); then, if a `,` follows, `NEXT_CHAR` and `HC_EXPT_1NUM` (the
length). HOME's 143Bh then demands the end of the statement. An `OPEN #` to
K, S or P with extra arguments is still Report C, now caught at syntax
time.

### `STRMS_NC`

`STRMS_HL`, then `AND A` (carry clear): the "not ours" exit of the two
hooks.

### `STRMS_HL`

HL = STRMS + 6 + 2 × (5CCBh): stream n's entry (streams start at −3, so
stream 0 is STRMS + 6).

### `CH_CLOSE_HOOK`

CLOSE # at run time. HOME 13A5h's `CALL 13BEh` now goes to 1494h, which
comes here (`G_CLOSE`) with BC = the stream's offset (not 0) and the stream
in 5CCBh.

1. `LD IY,IY_SYSVARS`. Bit 7 of B set → a SYSCON channel: stock.
   Otherwise IX = CHANS + BC − 1, the record; its letter not `F` → stock:
   `STRMS_HL`, A = B OR C, carry clear, for HOME's 13BEh.
2. `CH_FLUSH` — anything still buffered goes out first.
3. **`tpi:chclose`**, A = the stream, no payload; `CH_STATUS`.
4. The allocation's start = the record − `R_PAD`.
5. **Every stream whose offset is above this one** (not SYSCON) has its high
   byte decremented twice — moved down `CH_ALLOC` (200h) — for all 19
   entries of STRMS. Because `CH_ALLOC` is a multiple of 256, the low bytes
   (and so the pads) never change.
6. **CURCHL**: if the current channel is inside this allocation, it is
   about to point into someone else's bytes (RECLAIM's POINTERS would leave
   it `CH_ALLOC` lower), so stream 2 (S) is selected after the reclaim
   (`HC_CHAN_OPEN`).
7. `HC_RECLAIM` the allocation; `STRMS_HL`; carry set: HOME's 13A8h resets
   the entry to 0.

Stock CLOSE # on an unknown channel letter ran off the end of its table
and crashed; with the hook, an `F` stream is closed here and anything else
still goes to the stock code, as before.

### `HC_EXPT_1NUM`, `HC_FIND_INT2`, `HC_MAKE_ROOM`, `HC_RECLAIM`, `HC_CHAN_OPEN`

`PUSH IX / EXX / LD HL,target / JP CALL_HOME`, one per HOME routine:

| Helper | HOME | What |
|---|---|---|
| `HC_EXPT_1NUM` | 1BE5h | a numeric expression (class 06h) |
| `HC_FIND_INT2` | 1F23h | the number on the stack → BC (Report B) |
| `HC_MAKE_ROOM` | 12BBh | make BC bytes of room after HL (Report 4) |
| `HC_RECLAIM` | 1750h | remove BC bytes at HL |
| `HC_CHAN_OPEN` | 1230h | select stream A |

### `CH_OUT`

An `F` record's output routine: `RST 10h` with CURCHL on the record
reaches HOME 14A0h, which comes here through `G_OUT` with A = the
character.

1. `LD IY,IY_SYSVARS`; IX = CURCHL.
2. A TAB control (23) is a seek on a record file, so whatever was read
   ahead is no longer next: `R_INN` and `R_INP` = 0.
3. The byte goes into `R_OUTBUF` at `R_OUTN`, which goes up.
4. `CH_FLUSH` when the buffer is full (64), or — on a record file — at
   every CR, so a record that is too long is Report Q on the PRINT that
   made it.

TAB's two parameter bytes come through here as ordinary characters, and the
Pico interprets the sequence (23, lo, hi) ([../firmware/channels.md](../firmware/channels.md)).

### `CH_IN`

An `F` record's input routine (HOME 14A9h, `G_IN`): returns carry set with
A = the next byte, or NC NZ at the end of the file — which the ROM's
WAIT-KEY (HOME 11CFh) turns into Report 8 by itself, so `INPUT #` past the
end is "8 End of file".

1. `LD IY,IY_SYSVARS`; IX = CURCHL.
2. A byte left in `R_INBUF` (`R_INP` < `R_INN`): hand it out, `R_INP` + 1.
3. Otherwise `CH_FLUSH` (what was printed first goes out first — `INPUT
   #4;TAB n;` is a seek followed by a read), then `CH_FETCH`; Z: try again;
   NZ: the end of the file.

### `CH_FLUSH`

Sends `R_OUTBUF`'s bytes, if any: `R_OUTN` cleared **first** (so if the
Pico refuses them they are dropped with the report, and CLOSE # can still
close the stream), then **`tpi:chwr <hex>`** with A = the stream, B = the
count, PMR2 = 0, and `CH_STATUS`. The bytes travel as hexadecimal in the
command text because the body must be text.

### `CH_FETCH`

Refills `R_INBUF`: **`tpi:chrd`** with A = the stream, PMR2 = 255 (how many
bytes are wanted), no payload. Then the data phase, which is not a normal
answer:

1. `BIOS_WF_NPH` (failure → `WF_FAIL`); `BIOS_RX_A`: the status. 7 → the
   end of the file: NZ. Not 1 → `STATUS_REPORT` with A = status − 1.
2. The count (1–255) into `R_INN`, `R_INP` = 0.
3. The bytes into `R_INBUF`, each after a delay of `READ_DELAY` × 16
   T-states (~75 µs), D the running XOR.
4. The XOR after one more delay; a mismatch is Report R (a starved FIFO).
5. Z: there are bytes to hand out.

The bytes are read blind, as LOAD reads them: the firmware streams them
into the 4-deep FIFO (by DMA where it can) after saying READY, and the
delay paces the Z80 to it ([../firmware/tspico-disk.md](../firmware/tspico-disk.md#ch_readpre-cmd)).

### `CH_STATUS`

`BIOS_C_END` with CURCHL saved and restored around it; carry → `C_FAIL`.
The Pico answers channel commands with a bare status, but C_END could open
the screen if a response function arrived, so CURCHL is put back either
way. (The firmware's channel-status table is also called CH_STATUS:
[../firmware/tspico-state.md](../firmware/tspico-state.md#channels-ch_status).)

### `CH_SEND`

Sends the `'B'` command `<prefix HL>[the hex of B bytes from IX +
R_OUTBUF]` with PMR1 = A (the stream) and PMR2 = C, through the BIOS; stops
after the body, and the caller reads the answer.

1. The command's length E = `STRLEN`(prefix) + 2 × B (under 256: at most
   9 + 128).
2. **Wait for IDLE** (status bits 6 and 3 both set), at most 65 536 polls
   of `IN A,(0Fh)`, about one second. The firmware says READY without IDLE
   (`F7h`) when it answers a channel command and IDLE only when its tail
   has staged the next pre-load; a SYNC sent before that is lost with the
   pre-header behind it (Report T; hardware, 2026-09-29). This is the
   module's only direct port read.
3. **The pre-header**, D the running XOR: SYNC_WRITE `'B'`, TADDR 0,
   `ROM_ID` (as in `SEND_FOPEN`), the stream and 0 (PMR1), C and 0 (PMR2), E and 0 (the length), the XOR.
   `PRELOAD` (the pre-load: 0 is J, #179), `BIOS_WF_NPH` (failure →
   `WF_FAIL`).
4. **The body**: `'D'`, E, 0, the prefix, then each payload byte as two
   lower-case hex digits (`HEXDIG`), then the XOR.

### `HEXDIG`

The low nibble of A as one lower-case hex digit (`0`–`9`, `a`–`f`), sent
through `TXX`.

### `STRLEN`

A = C = the length of the NUL-ended string at HL (HL ends past the NUL).

## The command strings

NUL-ended prefixes, sent as the start of each command:

| Name | Text | Used by |
|---|---|---|
| `CMD_DIR` | `tpi:dir` | `CAT` |
| `CMD_DIR_ARG` | `tpi:dir ` | `CAT x` |
| `CMD_TAPDIR` | `tpi:tapdir` | `CAT ""` |
| `CMD_CD` | `tpi:cd ` | `MOVE TO x` |
| `CMD_CD_BACK` | `tpi:cd -` | `MOVE TO ""` |
| `CMD_COPY` | `tpi:copy ` | `MOVE a TO b` |
| `CMD_ERASE` | `tpi:erase ` | `ERASE` |
| `CMD_FORMAT` | `tpi:format ` | `FORMAT` |
| `CMD_CHWR` | `tpi:chwr ` | `CH_FLUSH` |
| `CMD_CHRD` | `tpi:chrd` | `CH_FETCH` |
| `CMD_CHCLOSE` | `tpi:chclose` | `CH_CLOSE_HOOK` |
| `CMD_CHOPEN` | `tpi:chopen ` | `CH_OPEN_HOOK` |
| `MODE_R` | `r` (not NUL-ended: copied with a length of 1) | OPEN # with no mode |

### `PRELOAD` (3778h)

`SEND_FOPEN`'s and `CH_SEND`'s read of the pre-load status: `CALL
BIOS_RX_A` (`IN A,(0Eh) / AND A`), `RET NZ`, `JP WF_FAIL`. A 0 means no
Pico, or a link out of step, and is Report J at once, as the ROM's own
exchanges give it (1A35h), instead of going on into `BIOS_WF_NPH`'s
timeout. Any other value goes on as before (#179).

Why not the ROM's whole rule, "not 1: the Pico's refusal, status − 1"?
The firmware refuses nothing at these pre-loads. The one other value it
stages is a refused header LOAD's error (R or 8), for two seconds after
the refusal, meant for the LOAD's retry
([../firmware/tspico-dispatch.md](../firmware/tspico-dispatch.md)). A
channel command in that time -- an `ON ERR` handler doing `PRINT #` -- would
read it and report it as its own. Added at the end of the module, so that
adding it moved no other address: the two `CALL BIOS_RX_A`s became `CALL PRELOAD`
in place. [`rom_preload_hosttest.py`](../../../src/test/rom_preload_hosttest.py)
runs it from the committed image.

### `PS_READ`

ROM 2.3's `PRINT_STRING_FROM_PICO` (#228). `build-rom.py` patches EXROM
045Fh, the v1.1 routine's first three bytes (`PUSH AF / JR 0465h`), to `JP
PS_READ`, and checks the module still puts it at 377Fh (`FIXED_SYMS`). Its
callers all enter at 045Fh: function 81h (027Ah), 82h (219Eh), and 86h's
loop (21E7h), which 88h joins.

```text
PS_READ:  PUSH AF                ; the caller's status
.next:    CALL TSPICO_READ_DATA  ; no ready-wait; Z for 00h
          JR Z,.end              ; 00h: the end of the text or the page
          CP 03h / JR Z,.loopend ; 03h: the end of an 86h/88h loop
          CP 10h / JR C,.print
          CP 18h / JR NC,.print  ; 18h and up, 80h-FFh included: print it
          LD C,1                 ; INK..OVER (10h-15h): one value byte
          CP 16h / JR C,.code
          INC C                  ; AT, TAB: two
.code:    PUSH BC / CALL PRINT_A / POP BC
.param:   CALL TSPICO_READ_DATA  ; a value: never a terminator
          PUSH BC / CALL PRINT_A / POP BC
          DEC C / JR NZ,.param
          JR .next
.print:   CALL PRINT_A / JR .next
.loopend: POP AF / SCF / RET     ; as v1.1's 21FAh: ends an 86h loop
.end:     POP AF / AND A / RET   ; as v1.1's 046Dh: carry clear
```

What changed from v1.1's reader ([exrom-chunk1.md](exrom-chunk1.md#print_string_from_pico-045fh)),
and why:

- **A control code's value bytes are not tested.** v1.1 tested every byte,
  so a `00h` or `03h` after INK, PAPER, FLASH, BRIGHT, INVERSE, OVER, AT or
  TAB ended the text or the loop: INK 0, PAPER 3 and the like could never
  be sent. RST 10h already knows a code takes one or two value bytes; the
  reader now counts them too and hands them on unexamined.
- **Only `00h` and `03h` end the text.** v1.1's classifier (`068Eh`, `CP
  80h / CCF`) also ended it on any byte of 80h or more, so block graphics,
  UDGs and keyword tokens could not be sent. They go to RST 10h now, which
  prints them as the 2068 always does.

The exits are v1.1's, so every caller sees what it did before: `00h` gives
the caller's AF back with carry clear, `03h` with carry set (86h's `JP
C,LOOP_EXIT_ERR` ends its loop on it). The reads still have no
ready-wait, as before; the extra instructions are a few T-states a byte
against RST 10h's hundreds, so a Pico that kept ahead of v1.1 keeps ahead
of this. C carries the count across `PRINT_A`, which goes through HOME
and may change any register.

The firmware assumes this reader (INK 0, PAPER 3 and the other attribute
values in `SEND_MSG2`, [../firmware/tspico-messages.md](../firmware/tspico-messages.md));
to an older ROM those bytes would end the text early. Tested in the Z80
interpreter against the committed image, with v1.1's reader (from
`TSPICO-SYNC.ROM`) for contrast:
[`rom_fn86_hosttest.py`](../../../src/test/rom_fn86_hosttest.py).

### `FDD_END`

The end of the module, 37B5h (377Fh in ROM 2.2, before `PS_READ`); `SAVEBIN` writes `FDD_BASE` to here as
`fddcmd.bin`, which `build-rom.py` splices in after checking that the
region is all `FFh`.

## Where comments, documents and the code disagree

None known. The last, `SEND_FOPEN` and `CH_SEND` reading the pre-load
without checking it, is `PRELOAD` since #179.

