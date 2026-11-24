# EXROM 3000h: the disk module

Source: [`src/rom/fdd/fddcmd.asm`](../../../src/rom/fdd/fddcmd.asm) (all
2826 lines), assembled by [`tools/build-rom.py`](../../../tools/build-rom.py)
at EXROM 3000h–3997h and spliced into the SYNC layer's image
(`src/rom/TSPICO-SYNC.ROM`) with the patches that call it, giving
`src/rom/TSPICO-24.ROM`, ROM 2.4 ([overview.md](overview.md#toolsbuild-rompy-the-disk-command-layer)), and with
`-DMEGABANK` `src/rom/TSPICO-25.ROM`, ROM 2.5, the release ROM
([below](#the-megabank-build--dmegabank-rom-25)); the result read in
[`tspico-22-exrom.labelled.asm`](../../rom-analysis/disasm/tspico-22-exrom.labelled.asm).

The module and its patches are ROM 2.4's last layer (2.2's, plus #227 and
#228 in 2.3 — see `PS_READ` — and COPY, LIST, RESTORE, `CAT #` and the
`v:` and `x:` channels in 2.4: [overview.md](overview.md)). The module gives the
2068's dormant disk keywords — CAT, MOVE, ERASE, FORMAT — real meanings
on the SD card; gives COPY a file form (`COPY "a" TO "b"`) beside the
printer one, LIST a file form (`LIST "name"`) beside the program listing,
and RESTORE a stream form (`RESTORE #n`, back to the start of a file); adds
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

The module is 2456 bytes (1919 in ROM 2.2; `PS_READ` added 54 at the end, then
COPY's file form, MOVE as rename, `LIST "name"` and `RESTORE #n` 311 more, also
at the end, then the speech channel, `v:`, 47 more: 14 of them free bytes
before `PS_READ`, #375; then the command channel, `x:`, 22 more at the end,
#404; then `CAT #n`, 103 more at the end, #404). It enters the 2068's code only through a vector
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
| 44–169 | — | the `EQU`s: base, ROM addresses, system variables, the channel record, tokens |
| 176–197 | 3000h–3020h | the vector table |
| 199–210 | 3021h | `TAPE_MODE` |
| 225–252 | 3029h | `G_BEEP` |
| 254–330 | | the `G_*` entries, `GUARDED`, `JP_HL` |
| 332–352 | | `FDD_MAIN`, the signature, `FDD_VERSION` (30AFh) |
| 354–451 | | `FDD_CAT`, `FDD_ONE_ARG`, `FDD_MOVE`, `TWO_NAMES`, `MOVE_TO`, `NONSENSE`, `TOO_LONG` |
| 453–527 | | the parsing helpers |
| 529–634 | | building and sending a command: `BUILD_START` … `TPI_SEND`, `COPY_CSTR` |
| 636–886 | | `f:` files: `F_HOOK`, `PEEK_NAME`, `SEND_FOPEN`, `TXX`, `TX_STR`, `WF_FAIL`, `C_FAIL`, `C_END2`, `FOPEN_TXT` |
| 888–908 | | `LOWER_LOOP` (function 88h) |
| 910–1479 | | the channel driver |
| 1481–1499 | | `HEXDIG`, `STRLEN` |
| 1501–1518 | to 3769h | the command strings, `MODE_R` |
| 1520–1533 | 376Ah–3770h | `PRELOAD` |
| 1535–1537 | 3771h–377Eh | 14 free bytes (`FFh`): `PS_READ` stays at 377Fh |
| 1539–1588 | 377Fh–37B4h | `PS_READ` (ROM 2.3's string reader) |
| 1590–1797 | 37B5h–38ECh | `FDD_ENTRY`, `FDD_COPY` (COPY), `FDD_LIST` (LIST), `FDD_RESTORE` (RESTORE), `STRM_REC`, `STR_NEXT`, `HC_USE_ZERO`, `CMD_LIST`, `CMD_CD_MENU` |
| 1799–1864 | 38EDh–3928h | the speech and command channels' helpers: `SPEC_KIND`, `DV_TEST`, `PUSH_LETTER`, `REC_FLAGS` (#375, #404) |
| 1866–1871 | 3929h–3931h | `IN_DROP` (#404) |
| 1873–1933 | 3932h–3997h | `CAT_HASH`, `CMD_CHCAT`: `CAT #n` (#404) |
| 1935–2841 | 3998h–3E52h | only with `-DMEGABANK`: the Megabank build (`MB_BOOT`, `R_SA`, `R_LD`, `FN_EXT`, `MOVER`, …, `MB_DETECT`, `MB_CALL_HOME`) |
| 2844–2845 | 3998h (3E53h) | `FDD_END` |
| 2847–2859 | 2400h–2C77h | only with `-DMEGABANK`: `RCH_BASE`, `rchan.asm` included, `RCH_END` ([the `r:` channels](#the-r-channels-rchanasm-phase-9)) |

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
| `H_COPY` | HOME 0A02h | HOME's COPY (`EXX / LD HL,1630h / JP 3CE3h`), the screen to the printer: `FDD_COPY` hands it back to the 25D6h hook for a bare COPY (`build-rom.py` checks its bytes) |
| `H_LIST` | HOME 1545h | HOME's LIST (`LD A,2 / LD (IY+2),0 …`), class 05h: it parses its own `#n` and line number. `FDD_LIST` hands it back to the hook for `LIST`, `LIST n` and `LIST #n`, on both passes |
| `H_RESTORE` | HOME 1E9Dh | HOME's RESTORE (`CALL 1F23h` first: the line number class 03h stacked). `FDD_RESTORE` stacks the number itself and hands it back at run time |
| `H_USE_ZERO` | HOME 1C51h | USE-ZERO: a 0 on the calculator stack at run time, nothing on the syntax pass (what class 03h does for a missing number). `HC_USE_ZERO` calls it |
| `T_LIST` | 19B0h | not a routine: T-ADDR during a LIST statement, its parameter list (19AFh) + 1, where class 05h leaves it. `FDD_ENTRY` tells LIST by it (LIST and RESTORE reach the hook with no token in B) |
| `T_RESTORE` | 19D1h | the same for RESTORE (list 19D0h) |
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
| `TV_FLAG` | 5C3Ch | bit 3: echo the edit line at the next key read. HOME's RDCH (11CFh) sets it before each character, the keyboard's IN_K clears it (0C83h). ROM 2.5's `MB_IN` clears it for every read from a record (#446) |
| `TADDR` | 5C74h | T-ADDR: its low byte is the pre-header's TADDR |
| `STKEND` | 5C65h | the calculator stack's end: strings are popped from below it, commands built above it |
| `FRAMES` | 5C78h | the session id's seed |
| `SESSION_ID` | 5DD1h | where the session id is kept |
| `IY_SYSVARS` | 5C3Ah | what HOME expects in IY (the bank switch clobbers IY) |
| `BANK_SV` | 5DCFh | pre-header byte 2 up to ROM 2.2 (always FFh); no longer read by the module |
| `ROM_ID` | 24h | 25h with `-DMEGABANK` (ROM 2.5). Not a variable: what ROM 2.4 sends (2.3 sent 23h) as byte 2 of a command pre-header instead of `BANK_SV`, the same value as its version marker (HOME 0065h). `SEND_FOPEN` and `CH_SEND` send it, and `build-rom.py` patches `BUILD_PREHEADER_B` (1BB5h) to send it too, so the firmware knows which ROM sent each command (`rom_id`, shown by `tpi:info`, [../firmware/tspico-state.md](../firmware/tspico-state.md#rom_id), #227) |
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
| `R_FLAGS` | 10 | bit 0: a record file (OPEN # gave a length); bit 1: send at each CR (speech `v:`, #375; commands `x:`, #404); bit 2: commands (`x:`): `CH_OUT` drops what was read ahead at each write. Bit 0 or bit 1 makes `CH_OUT` send at each CR |
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
| `TOK_INKEY` | A6h | INKEY$: `STR_NEXT` takes it for the start of a string |
| `TOK_FN` | A8h | FN: `STR_NEXT` looks past it for `a$` |
| `TOK_SCREEN` | AAh | SCREEN$ (`SAVE … SCREEN$`; and a string start for `STR_NEXT`) |
| `TOK_VALS` | AEh | VAL$, a string start for `STR_NEXT` |
| `TOK_STRS` | C1h | STR$, the same |
| `TOK_CHRS` | C2h | CHR$, the same |
| `TOK_CODE` | AFh | CODE |
| `TOK_LINE` | CAh | LINE |
| `TOK_DATA` | E4h | DATA |
| `MAX_ARG` | 64 | the longest argument; longer is Report F |
| `ROOM` | 160 | workspace a command may need: 2 × MAX_ARG + 32 |
| `CR` | 0Dh | BASIC's end of line |
| `SEP` | `'\|'` | COPY's and MOVE's source/destination separator: cannot occur in a FAT name |
| `TOK_TO` | CCh | TO |
| `TOK_CAT` | CFh | CAT |
| `TOK_FORMAT` | D0h | FORMAT |
| `TOK_MOVE` | D1h | MOVE |
| `TOK_ERASE` | D2h | ERASE |
| `TOK_COPY` | FFh | COPY (`LD B,FFh` at HOME 25E0h) |

## The vector table

### `FDD_DISPATCH` (3000h)

The first of ten `JP`s; `build-rom.py` refuses a build where this label is
not at 3000h. The patches point at these vectors, never at routines:

| Name | EXROM | Jumps to | Reached from |
|---|---|---|---|
| `FDD_DISPATCH` | 3000h | `G_MAIN` | HOME 25D6h, the disk keywords and COPY |
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
| `G_MAIN` | `FDD_ENTRY` (which calls `FDD_MAIN`) |
| `G_OUT` | `CH_OUT` |
| `G_IN` | `CH_IN` |
| `G_OPEN` | `CH_OPEN_HOOK` |
| `G_OSYN` | `OPEN_SYNTAX` |
| `G_CLOSE` | `CH_CLOSE_HOOK` |

**`INPUT #` and TV_FLAG bit 3** (#446). The comment above `G_MAIN` says why
ROM 2.5's `MB_IN` (not `G_IN`) clears it. HOME's RDCH (11CFh), the editor's read, sets
TV_FLAG bit 3 before every character, to echo the keyboard. Only the
keyboard clears it: IN_K's echo at 0C83h, which copies the edit line to the
lower screen. INPUT's own end calls that echo only when the channel is K
(230Bh). So `INPUT #` from a record left the bit set, and the next key read
from the keyboard, the `scroll?` prompt, echoed the edit line after the
prompt (`scroll?RUN`, the last command typed) and left the print position
and colors wrong for what came next: control codes on the next line, even
Report K. The stock 2068 does the same after an `INPUT #` from any channel
other than K. In ROM 2.5 `MB_IN` clears the bit for every read from an `F`
or `R` record, the fast entry's reads too, so it is clear after the last
character and after Report 8. `G_IN` is still `LD HL,CH_IN` in the build
without `-DMEGABANK`: that is ROM 2.4, the shipped image, which keeps the
bug.

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
other way to hand over the syntax check), with B = the token, from
`FDD_ENTRY`, which has set IX for `FDD_MOVE`.

1. `LD IY,IY_SYSVARS`: the bank call clobbers IY, and HOME routines need it.
2. `EI`: HOME's hook entered under `DI`, and CAT's "Scroll?" and the Y/N
   prompts wait with `HALT`.
3. CAT → `FDD_CAT`; MOVE → `FDD_MOVE`; ERASE → `FDD_ONE_ARG` with HL =
   `CMD_ERASE`; FORMAT → `FDD_ONE_ARG` with `CMD_FORMAT`; any other token →
   `RET` (no-op; nothing else reaches it: COPY, the one other token at 25D6h,
   goes to `FDD_COPY` first).

After it, at 30A8h, `"FDDCMD",0` — a signature nothing checks;
`build-rom.py` checks `FDD_DISPATCH`'s address instead, as the comment says
(until #181 it claimed "build.py verifies this").

### `FDD_VERSION` (30AFh)

One byte, 9: the module's revision number (8 until COPY joined and MOVE
became rename). Nothing reads it; the
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
| `CAT ""` | `tpi:idir` (ROM 2.4: `tpi:tapdir`) | [`IDIR`](../firmware/tspico-commands.md#idirpre-cmd) |
| `CAT ">"` | `tpi:dir >`, as any `CAT x` | [`DIR`](../firmware/tspico-commands.md#dirpre-cmd), which chains to `TAPDIR` |
| `CAT x` | `tpi:dir x` | [`CATALOG`](../firmware/tspico-disk.md#catalogarg) |
| `MOVE TO x` | `tpi:cd x` (`"-"`: `tpi:cd -`, back to the previous folder) | [`CDIR`](../firmware/tspico-commands.md#cdirpre-cmd) |
| `MOVE TO ""` | `tpi:cd` (the menu of folders) | the same |
| `MOVE a TO b` | `tpi:ren a\|b` | [`DISK_REN`](../firmware/tspico-disk.md#disk_renpre-cmd) |
| `COPY a TO b` | `tpi:copy a\|b` | [`DISK_COPY`](../firmware/tspico-disk.md#disk_copypre-cmd) |
| `COPY` | nothing: HOME's COPY, the printer ([home.md](home.md#25d6h25e3h-the-disk-keywords)) | [`PRINT_IO`](../firmware/printer.md) with `tpi:picopt` |
| `ERASE x` | `tpi:erase x` | [`DISK_ERASE`](../firmware/tspico-disk.md#disk_erasepre-cmd) |
| `FORMAT x` | `tpi:format x` | [`DISK_FORMAT`](../firmware/tspico-disk.md#disk_formatpre-cmd) |
| `LIST x`, x a string | `tpi:list x` | [`DISK_LIST`](../firmware/tspico-disk.md#disk_listpre-cmd) |
| `LIST`, `LIST n`, `LIST #n` | nothing: HOME's LIST (`FDD_LIST`) | |
| `RESTORE #n` | `tpi:chwr` with TAB 1 (23, 1, 0) on stream n | [`Channels._seek`](../firmware/channels.md#channels_seekself-ch-n) |
| `RESTORE`, `RESTORE n` | nothing: HOME's RESTORE (`FDD_RESTORE`) | |

MOVE renames (or moves into a folder) and COPY copies, the way DOS and Unix
use the words; no 1980s 2068 disk system agreed on either
([DISK_COMMANDS_SPEC.md](../../DISK_COMMANDS_SPEC.md), #341).

### `FDD_CAT`

`CAT_HASH` first, in `AT_END`'s place: for `CAT #n` and `CAT #n;"x"` it does
the whole statement and returns from `FDD_CAT` itself (#404); for anything
else it is `AT_END`. Then: a bare `CAT` → `.bare`: `RUNTIME`, return on the syntax pass, else
`SEND_PREFIX` with `CMD_DIR`. Otherwise `EXPT_STR_END` (one string
expression that ends the statement; return on the syntax pass), `POP_STR`;
an empty string → `SEND_PREFIX` with `CMD_CAT_EMPTY`: `tpi:idir`, the menu
of files to mount, as `MOVE TO ""` is the menu of folders (#444; ROM 2.4
sends `tpi:tapdir` here, the mounted tape); anything else →
`SEND_ONE` with `CMD_DIR_ARG`.

### `FDD_ONE_ARG`

ERASE and FORMAT; HL = the prefix. The argument is required: `AT_END` →
`NONSENSE`. `EXPT_STR_END`, return on the syntax pass; `POP_STR`;
`NOT_EMPTY` (an empty name is Report F); `SEND_ONE`.

### `FDD_MOVE`

`SKIP_SPACES`; `TO` straight away → `MOVE_TO`. Otherwise it falls into
`TWO_NAMES` with IX = `CMD_REN`, set by `FDD_ENTRY`.

### `TWO_NAMES`

`string TO string` with IX = the prefix: `CMD_REN` from MOVE, `CMD_COPY`
from `FDD_COPY`. A source is required (`AT_END` → `NONSENSE`):
`HC_EXPT_STR` (the source), `TO` required (else `NONSENSE`), `NEXT_CHAR`
past it, `EXPT_STR_END` (the destination); return on the syntax pass. At
run time pop the destination (on top) then the source, both `NOT_EMPTY`;
`PUSH IX / POP HL` and `BUILD_START` with that prefix, then the source,
`SEP` (`|`), the destination; `SEND_TAIL`.

Why IX: COPY's code is at the end of the module, and the prefix had to
reach this body without moving anything below it (`PS_READ` is pinned at
377Fh, and the chapters cite these addresses). `PUSH IX / POP HL` is three
bytes, as the `LD HL,CMD_COPY` it replaced. IX survives the calls into
HOME: `CALL_HOME` pushes the caller's IX and pops it on the way back
([exrom-driver.md](exrom-driver.md#call_home-03ddh)); nothing else here
touches it.

### `MOVE_TO`

`NEXT_CHAR` past `TO`, `EXPT_STR_END`, return on the syntax pass, `POP_STR`;
an empty string → `SEND_PREFIX` with `CMD_CD_MENU` (`tpi:cd`, the
firmware's menu of folders); else `SEND_ONE` with `CMD_CD`, so `MOVE TO
"-"` sends `tpi:cd -` (the previous folder). The empty case can't go
through `SEND_ONE`: its `LDIR` with BC = 0 would copy 64K.

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
prefix (`tpi:dir`, `tpi:idir` or `tpi:tapdir`, `tpi:cd`).

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
(137 characters with the prefix; a `COPY`, 138) goes through. The anchors at 1A73h and
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
([../firmware/tspico-messages.md](../firmware/tspico-messages.md#send_msg_prompt_ynprompt-echotrue-lowerfalse)). After the
key, nothing may make the lower screen a third line: a CR there scrolls the
picture up one line before SAVE's "Start tape…" (#447). The firmware sends
`AT 1,1`, a backspace, 32 spaces and the same again, which blanks the line
and leaves the cursor at its start; the loop's text cannot hold a `00h`, so
`AT 1,0` is out.

## The channel driver

`OPEN #n,"f:path"[,"mode"[,reclen]]` builds an `F` record in CHANS and
points stream n at it; `PRINT #n`, `INPUT #n`, `LIST #n`, `INKEY$ #n` go
through the record's routines; `CLOSE #n` flushes it, tells the Pico and
takes the record out again. `OPEN #n,"d:[pattern]"` does the same with a
read-only listing of names, `OPEN #n,"v:"` (#375) the v3 card's
speech: the Pico says each line printed to it, and `OPEN #n,"x:"` (#404)
commands: each line printed to it is a command, and `INPUT #n` reads its
answer. Modes: `r` read, `w` write (truncate), `a`
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
   K, S or P as before. Ours (`SPEC_KIND`, past the `:` test): `d:` (any
   case, any length ≥ 2, the rest a pattern), `v:` or `x:` (any case and
   length; the Pico refuses anything after the colon) or `f:` with at
   least one more character.
2. A spec over 64 characters after the prefix → `TOO_LONG` (F).
   `HC_TEST_ROOM` with `CH_ALLOC + ROOM`: Report 4 now, before the Pico
   hears of it, if the record and the command will not fit.
3. The mode and length: none → mode `"r"` (`MODE_R`), length 0. Otherwise
   `,` (else `NONSENSE`), `HC_EXPT_STR` (the mode); optionally `,` and
   `HC_EXPT_1NUM`, `HC_FIND_INT2` (the record length into BC); the
   statement must end (else `NONSENSE`). The mode is popped: `""` is `r`;
   1–3 characters are passed on; 4 or more is Report Q.
4. **`tpi:chopen <mode> <path>`**, built at STKEND: `CMD_CHOPEN`, the mode,
   a space, then the spec — without its `f:`, or whole for `d:`, `v:` and
   `x:` (`DV_TEST`: the Pico lists, speaks or runs commands for them). A zero-length path is skipped (an `LDIR` with BC = 0 would
   copy 64K). PMR2 = the record length, or FFh if it is over 255 (the Pico
   answers Q). `CH_SEND` with A = the stream, no payload; `CH_STATUS` (F,
   Q … raise their reports; nothing has been allocated yet).
5. `PUSH_LETTER` keeps the spec's first letter on the stack, then the spec
   is dropped from the calculator stack (STKEND − 5), as 1465h's
   STK-FETCH would have. (Step 6 moves memory, so the spec can't be looked
   at again later.)
6. **The allocation**: it goes where CHANS' closing 80h is (PROG − 1, or
   PROG − 2 when one spare byte sits between that 80h and PROG, as on the
   2068). The pad: if the offset the record would have (record − CHANS + 1)
   has its low byte's bit 7 set, the record is moved in by 256 − L bytes
   so both bytes of the offset are below 80h — CHAN-OPEN would otherwise
   take it for a SYSCON channel. `HC_MAKE_ROOM` opens `CH_ALLOC` bytes after
   (start − 1) so the 80h moves up past them; the allocation is zeroed.
7. **The record**, IX = start + pad: `R_OUT` = 14A0h, `R_IN` = 14A9h,
   `R_LETTER` = `'F'`, `R_PAD`, `R_STRM` = the stream; then `REC_FLAGS` with
   the letter and the record length: `R_FLAGS` bit 1 for `v:`, bits 1 and 2
   for `x:`, bit 0 if a record length was given. A speech or command record
   is an `'F'` record in every other way, so `CH_CLOSE_HOOK`, `G_BEEP` and
   the rest need nothing new.
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
   ahead is no longer next: `CP 23 / CALL Z,IN_DROP`. On an `x:` stream
   (`R_FLAGS` bit 2) any byte written starts a new command, whose answer
   replaces the last: `BIT 2,(IX+R_FLAGS) / CALL NZ,IN_DROP` (#404). The
   two calls take the 12 bytes the inline `JR NZ` and two `LD`s took, so
   nothing between here and `PS_READ` moved.
3. The byte goes into `R_OUTBUF` at `R_OUTN`, which goes up.
4. `CH_FLUSH` when the buffer is full (64), or — on a record file or a
   speech or command stream (`R_FLAGS` bits 0–1) — at every CR, so a record
   that is too long is Report Q on the PRINT that made it, a line printed to
   `v:` is said as soon as it is printed, and a line printed to `x:` reaches
   the Pico as a command before the `INPUT #` that reads its answer.

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
| `CMD_CAT_EMPTY` | `tpi:idir` and two more NULs with `-DMEGABANK` (ROM 2.5); `tpi:tapdir` without (ROM 2.4) | `CAT ""`. The same 11 bytes in both, so nothing after it moves (#444); ROM 2.4 keeps its old text because CI compares that image byte for byte |
| `CMD_CD` | `tpi:cd ` | `MOVE TO x` |
| `CMD_REN` | `tpi:ren ` | `MOVE a TO b` (through IX) |
| `CMD_COPY` | `tpi:copy ` | `COPY a TO b` (through IX) |
| `CMD_ERASE` | `tpi:erase ` | `ERASE` |
| `CMD_FORMAT` | `tpi:format ` | `FORMAT` |
| `CMD_LIST` | `tpi:list ` | `LIST x` (at the end of the module, `CMD_LIST`) |
| `CMD_CHWR` | `tpi:chwr ` | `CH_FLUSH` |
| `CMD_CHRD` | `tpi:chrd` | `CH_FETCH` |
| `CMD_CHCLOSE` | `tpi:chclose` | `CH_CLOSE_HOOK` |
| `CMD_CHOPEN` | `tpi:chopen ` | `CH_OPEN_HOOK` |
| `CMD_CHCAT` | `tpi:chcat ` | `CAT_HASH` (`CAT #n`; at the end of the module, `CMD_CHCAT`) |
| `MODE_R` | `r` (not NUL-ended: copied with a length of 1) | OPEN # with no mode |

### `PRELOAD` (376Ah)

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
runs it from the committed image. It was at 3778h until #375 made the
channel driver 14 bytes shorter; the free bytes after it keep `PS_READ` put.

The `BLOCK $377F-$,$FF` after it fills the gap up to `PS_READ`, whose
address HOME's 045Fh patch jumps to (`build-rom.py`'s `FIXED_SYMS` checks
it). Code before it that gets shorter leaves room here; code that grows
must be balanced, or `PS_READ` and the patch move together.

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

### `FDD_ENTRY` (37B5h)

`G_MAIN`'s routine since COPY joined the disk keywords: every disk keyword,
COPY, LIST and RESTORE, on both passes. `PUSH IX`, then `CALL .run`, `POP
IX`, `RET`: the caller's IX back, the flags as `.run` left them.

`.run` first looks at T_ADDR. LIST's and RESTORE's parameter lists point
straight at 25D6h, not at 25E0h's `LD B,FFh` as COPY's does, so B holds
whatever the statement loop left in it and can't say which keyword this is.
Class 05h leaves T_ADDR one past the class byte, so it can: `T_LIST`
(19B0h) → `FDD_LIST`, `T_RESTORE` (19D1h) → `FDD_RESTORE`. The two share a
high byte, which is compared first (19h; COPY's 19D8h has it too, and falls
through on the low byte). Anything else (`.tok`): IX = `CMD_REN` (MOVE's
two-name form renames); COPY (B = `TOK_COPY`) → `FDD_COPY`; any other token
→ `CALL FDD_MAIN`, then `AND A` and `RET`.

It returns carry clear, except where HOME has to finish the statement: a
bare COPY at run time, LIST that isn't `LIST x` (both passes), and
`RESTORE` or `RESTORE n` at run time. HOME's hook is
`CALL 03FCh / EI / RET NC / JP (HL)` ([home.md](home.md#25d6h25e3h-the-disk-keywords)),
so carry set with HL = `H_COPY` sends the statement on to HOME's own COPY,
and the `AND A` keeps whatever flags a `tpi:` command left from reaching
that test. Why HOME has to do it: the stock COPY (EXROM 1781h) ends with a
no-return jump to HOME (17B3h → 0A30h), whose `RET` must find the
statement loop's return address, not the module's. Jumping to 0A02h from
the hook is what class 00h did, on the same stack and with T-ADDR still
19D8h, which is how the printer path at 1781h tells COPY from LPRINT
(D8h → TADDR 4, [exrom-chunk1.md](exrom-chunk1.md#the-printer-path-1630h183bh)).

### `FDD_COPY` (37DDh)

COPY, with B = FFh. `LD IY,IY_SYSVARS` and `EI`, as `FDD_MAIN`. `AT_END`:

- **bare** (`.bare`): `RUNTIME`; the syntax pass returns, carry clear from
  its `AND 80h`, and the statement is accepted; at run time HL =
  `H_COPY`, `SCF`, `RET`: the hook goes on to HOME's COPY, the screen to
  the printer (or to the Pico with `tpi:picopt`, [../flows/printer.md](../flows/printer.md)).
- **otherwise**: IX = `CMD_COPY`, `CALL TWO_NAMES`, `AND A`, `RET`. So
  `COPY "a" TO "b"` sends `tpi:copy a|b`. `COPY "a"`, `COPY TO "b"` and
  `COPY "a" TO` are Report C on the syntax pass: the line is refused at
  entry with the `?` marker.

### `FDD_LIST` (37F9h)

LIST, with T_ADDR = 19B0h. `LD IY,IY_SYSVARS` and `EI`, as `FDD_MAIN`.
Bare `LIST`, `LIST #n`, and anything `STR_NEXT` says is not a string, go to
`.home`: HL = `H_LIST` (1545h), `SCF`, `RET`, on **both** passes. HOME's
LIST routine does its own syntax check (it runs under `SYNTAX-Z` like any
class 05h routine), so handing it the statement at the syntax pass is what
class 05h with 1545h did, and the `?` marker lands where HOME puts it.

A string (`LIST "x"`, `LIST a$`, `LIST STR$ n` …): `FDD_ONE_ARG` with HL =
`CMD_LIST`, so the syntax pass checks the string and the end of the
statement and returns, and at run time **`tpi:list x`** goes to the Pico
([../firmware/tspico-disk.md](../firmware/tspico-disk.md#disk_listpre-cmd));
`AND A`, `RET`.

Why not scan the expression and look at its type: a scan in syntax mode
done at run time inserts a second hidden number after each number in the
line (the line has them already), and a scan in run mode evaluates the
expression a second time (the comment at 1632–1636). So the test is lexical, and `LIST (a$)` counts as a number:
HOME's LIST then says Report C at the syntax pass.

### `FDD_RESTORE` (3819h)

RESTORE, with T_ADDR = 19D1h. The list was class 03h with 1E9Dh; it is
class 05h with 25D6h, so the module does class 03h's part.

- **`RESTORE`**: the syntax pass returns (`RUNTIME`); at run time
  `HC_USE_ZERO` stacks 0, then `.home`: HL = `H_RESTORE` (1E9Dh), `SCF`,
  `RET`, and the hook jumps to HOME's RESTORE, which takes the number off
  the stack as class 03h left it.
- **`RESTORE n`**: `HC_EXPT_1NUM`, then the end of the statement
  (`NONSENSE` if not), then the syntax pass returns; at run time `.home`.
- **`RESTORE #n`** (`.strm`): `NEXT_CHAR` past the `#`, `HC_EXPT_1NUM`,
  the end of the statement; the syntax pass returns. At run time
  `STRM_REC` (Report O unless n is a stream open to an `f:` file; what was
  printed to it goes out first), then:
  1. `R_INN` = `R_INP` = 0: what was read ahead is dropped, as `CH_OUT`
     does for a TAB.
  2. `R_OUTBUF` = 23, 1, 0, `R_OUTN` = 3, `CH_FLUSH`: **`tpi:chwr 170100`**,
     TAB 1. The firmware's `Channels.write` takes a TAB in every mode and
     `Channels._seek` puts the channel at byte 0, closing an open record
     first and resetting what it had read ahead
     ([../firmware/channels.md](../firmware/channels.md#channels_seekself-ch-n)).
  3. `AND A`, `RET`.

  A Report from the Pico comes through `CH_STATUS` as for any `tpi:chwr`.
  Until #404 the stream checks were inline here; they moved to `STRM_REC`
  when `CAT #n` came to need them too.

Before this, `RESTORE #4` was Report C at the syntax pass (class 03h wants a
number or the end of the statement).

### `STRM_REC` (3870h)

The number on the calculator stack is a stream open to an `OPEN #`
channel; IX = its record, and what was printed to it has been sent. Used by
`RESTORE #n` and `CAT #n`. `HC_FIND_INT2` gives BC = n, and n above 15 is
`.bad`. Stream n's STRMS entry is `STRMS + 6 + 2n` (streams −3 to −1 come
first); 0 (not open) or bit 7 of the high byte set (a SYSCON channel) is
`.bad`. IX = CHANS + the offset − 1 is the record; `'F'` in `R_LETTER` ends
with `JP Z,CH_FLUSH`, anything else falls into `.bad`: `RST 8` with 17h,
**Report O Invalid stream**. A Report from the Pico on the flush comes
through `CH_STATUS`.

### `STR_NEXT` (389Fh)

Z if the expression at CH_ADD starts the way a string does; CH_ADD is not
moved. `SKIP_SPACES`, then Z for a quote, `INKEY$` (A6h), `SCREEN$` (AAh),
`VAL$` (AEh), `STR$` (C1h) or `CHR$` (C2h). `FN` (A8h) moves to the next
non-space character, the function's letter. A letter (either case: `OR
20h`) followed, after any spaces, by `$` is Z (a string variable, or `FN
a$`); anything else is NZ (`.no`: `OR 1`). `.next` steps HL past spaces
and returns the character.

A number that starts with a letter (`LIST a`, `LIST a(2)`) is NZ: the
letter isn't followed by `$`. A string in parentheses (`LIST (a$)`) is NZ
too, and goes to HOME's LIST, which says Report C.

### `HC_USE_ZERO` (38D3h)

`PUSH IX / EXX / LD HL,H_USE_ZERO / JP CALL_HOME`: HOME's USE-ZERO (1C51h),
which stacks 0 at run time (its `CALL SYNTAX-Z / RET Z` makes it nothing at
the syntax pass). Bare `RESTORE` at run time, as class 03h did.

### `CMD_LIST` (38DCh)

`tpi:list `, NUL-ended: `LIST x`'s prefix. Here with the code that came with
it, as `CMD_CD_MENU`.

### `CMD_CD_MENU` (38E6h)

`tpi:cd`, NUL-ended: what `MOVE TO ""` sends, the text of `SAVE "tpi:cd"`.
At the end of the module with the code that came with it, so the string
table above kept its length (`CMD_REN` took `CMD_CD_BACK`'s nine bytes).

### The speech and command channels' helpers (#375, #404)

`OPEN #n,"v:"` needed four small routines; they are here, past `PS_READ`, so
the hook's call sites could shrink instead of grow. `OPEN #n,"x:"` added a
letter to `DV_TEST` and to `REC_FLAGS`, and `IN_DROP`.

#### `SPEC_KIND` (38EDh)

DE = the spec (already known to have `:` second), C = its length: Z if it is
ours — `d:`, `v:` or `x:` (`DV_TEST`), or `f:` with at least one character more
(`CP 3 / SBC A,A / AND A`: FFh, NZ, for a bare `f:`) — else NZ. A is lost.
Called once, by `CH_OPEN_HOOK` (`JP NZ,STRMS_NC` after it).

#### `DV_TEST` (38FAh)

Z if the spec at DE starts with `d`, `v` or `x` in either case; A = the
letter in upper case. Called by `SPEC_KIND` and by `CH_OPEN_HOOK` when it
builds the command (`d:`, `v:` and `x:` go whole).

#### `PUSH_LETTER` (3906h)

Pushes the spec's first letter, upper case, in AF under its own return
address (`POP HL / PUSH AF / JP (HL)`); HL is lost. `CH_OPEN_HOOK` calls it
just before it drops the spec, because the allocation that follows moves
memory, and pops it again for `REC_FLAGS`.

#### `REC_FLAGS` (390Fh)

IX = the new record, A = the letter, BC = the record length: `SET 2` and
`SET 1` of `R_FLAGS` for `'X'`, `SET 1` for `'V'`, `SET 0` for a length
that is not 0. HL (the record) is kept, for the offset `CH_OPEN_HOOK`
works out next. A `v:` or `x:` with a length never gets this far: the
Pico answers Q first.

#### `IN_DROP` (3929h)

IX = the record: `R_INN` and `R_INP` = 0, so `CH_IN` forgets what it read
ahead and its next read fetches. Called by `CH_OUT` for a TAB (a seek) and
for every byte written to an `x:` stream (#404): a program that reads only
part of an answer (the first screen of a `dir`) and prints the next
command reads that command's answer, not what was left of the last one in
`R_INBUF`. The Pico starts the new answer from its start at the same time
(`Channels._command`, [../firmware/channels.md](../firmware/channels.md)).
`CAT_HASH` calls it too, so a `CAT #n` into a file that was being read
leaves nothing stale.

### `CAT_HASH` (3932h)

`CAT #n`, `CAT #n;"x"` (or `,"x"`): the listing `CAT` or `CAT "x"` would
show, written into the `f:` file open on stream n instead of the screen
(#404). `FDD_CAT`'s first call, in `AT_END`'s place: `AT_END`, and Z (the
end of the statement) or anything but `#` returns as `AT_END` would, so
`CAT` and `CAT "x"` go on in `FDD_CAT` as before.

For `#` it does the whole statement. `POP HL` drops the return into
`FDD_CAT`, so its own `RET`s return from `FDD_CAT` (NC, as `FDD_CAT` does).
`NEXT_CHAR` past the `#`, `HC_EXPT_1NUM` (the stream), then the end of the
statement (`.bare`), or `;` or `,` and `EXPT_STR_END` (`.str`); anything
else is `NONSENSE`. The syntax pass returns. At run time `.str` pops the
string (`POP_STR`: DE, BC; over 64 characters is Report F) with A = 1; `.bare` has BC = 0, A = 0. `.run`:
`STRM_REC` (IX = the record, Report O, and what was printed sent first),
`IN_DROP`, then `BUILD_START` with `CMD_CHCAT` and the string copied after
it (`.none` skips the `LDIR` for an empty one: BC = 0 would copy 64K), a
NUL, and `CH_SEND` with A = `R_STRM` (PMR1), C = A from before (PMR2: 1 when
a string came, so the Pico can refuse `CAT #n;""` with Q, as `CAT ""` is a
menu; `CAT #n;">"` is the mounted tape), B = 0
(no payload). `CH_STATUS` raises the Pico's report: Q (not a file open to
be written), F (what `CAT "x"` would refuse), J (no card). `AND A`, `RET`.

Why the Pico writes the file: printing a reply into an `f:` stream
mid-transaction can't work, because the stream's flush (`CH_SEND`) waits
for IDLE and sends the SYNC that ends the reply being printed. The firmware
side is `CH_CAT` ([../firmware/tspico-disk.md](../firmware/tspico-disk.md)).

Tested in the emulator, not yet on hardware. *(Seen there:)* the first
line typed or run after boot that has an `OPEN #` and a flush in it (a
`RESTORE #n` or a `CAT #n` after a `PRINT #n`) can give Report C on one
run and not the next; ROM 2.3 before this change does the same with
`RESTORE #n`, so it is not `CAT_HASH`'s. It looks like the emulator's
timing (inferred).

### `CMD_CHCAT` (398Dh)

`tpi:chcat `, NUL-ended: `CAT #n`'s prefix, the argument after it.

### `FDD_END`

The end of the module, 3998h (377Fh in ROM 2.2, before `PS_READ`; 37EEh
before LIST and RESTORE joined; 38ECh before the speech channel; 391Bh
before the command channel; 3931h before `CAT #n`); `SAVEBIN` writes `FDD_BASE` to here as
`fddcmd.bin`, which `build-rom.py` splices in after checking that the
region is all `FFh`.

## The Megabank build (`-DMEGABANK`, ROM 2.5)

`tools/build-rom.py --megabank` assembles the module with `-DMEGABANK` and
gives `src/rom/TSPICO-25.ROM`, ROM 2.5, the release ROM and flash slot 1's
image. It runs with or without the TS-2068 Megabank
([PROTOCOL.md §6.3](../../PROTOCOL.md) has the wire format). Without the
define the module is byte-for-byte ROM 2.4's. With it, four same-size edits
change 2.4's code and everything else is appended after `CMD_CHCAT`, at
3998h–3E52h (1211 bytes; 429 free to 3FFFh), so no 2.4 address moves:

- `ROM_ID` is 25h (with the patches that carry the version: banner "v2.5",
  HOME 0065h, `G_VERS`, 1BB5h);
- `F_HOOK` tests the prefix with `FR_TEST` (`f:` or `r:`) and stores TPMODE
  through `SET_MODE`;
- `SEND_FOPEN` takes its command text from `OPEN_TXT`;
- for the `r:` channels (phase 9, [below](#the-r-channels-rchanasm-phase-9)):
  `G_OUT` and `G_IN` go to `MB_OUT` and `MB_IN`; `G_BEEP`'s `POP HL / CP 'F'`
  is `CALL BEEP_LT`; `CH_OPEN_HOOK`'s `CALL SPEC_KIND` is `CALL RCH_KIND`;
  `CH_CLOSE_HOOK`'s `LD A,(IX+R_LETTER) / CP 'F'` is `CALL RCH_CLTEST`
  and two NOPs, and its `CALL HC_RECLAIM` is `CALL RCH_RECL` (the `R`
  records above the one closed have moved, and each holds its own output
  routine's address); `TPI_SEND`'s opening (`PUSH HL / PUSH DE / LD HL,(FRAMES)`)
  is `CALL MB_TPRE` and two NOPs; and `SET_MODE`'s store is `JP SET_MODE_R`
  and a filler byte, so `R_SA` stays at 39F5h.

The `r:` channel code doesn't fit in the module's 4K: `rchan.asm` is
assembled with it, in the same pass, at EXROM 2400h (`RCH_BASE`, free in the
base ROM and in the same chunk), and `build-rom.py --megabank` splices
`rchan.bin` there.

The patches that reach it (`MB_PATCHES` in build-rom.py, each with the bytes it
replaces): EXROM 0A3Eh `2A BC 5C` → `JP MB_BOOT`, 0068h `JP 1879h` → `JP R_SA`,
00FCh `JP 196Dh` → `JP R_LD`, and 2213h (2.4's `CP 87h / JP Z,3006h / RET`) →
`JP FN_EXT`. `MB_FIXED_SYMS` holds MB_BOOT, R_SA, R_LD, FN_EXT,
MB_CALL_HOME and FX_ENTRY at the addresses the patches use. The fast
channel entry's patches are with [the `r:` channels](#the-r-channels-rchanasm-phase-9). The rest of `MB_PATCHES`, and the splice of
`bankapi.asm` over the RAM bank code, are the Timex bank API
([below](#the-timex-bank-api-bankapiasm-phase-8)).

The board model all of this assumes (the Megabank spec): port FDh selects a
register, FCh is its data; a chunk is the board's when its OWNn names a bank
the board has, but writes to it reach HOME RAM too unless HSR (port F4h) bit n
is set, so the mover maps OWN first, then the HSR bit, and unmaps the other
way round.

### The board's registers and the 2068 addresses

| Name | Value | What |
|---|---|---|
| `MB_SEL` | FDh | port: select a board register |
| `MB_DATA` | FCh | port: the selected register |
| `MB_OWN` | 00h | OWN0–OWN7: the bank in chunk n; writing it sets SUBn = n |
| `MB_SUB` | 08h | SUB0–SUB7: which 8K of the bank chunk n shows |
| `MB_WPROT` | 10h | write protect, a bit a chunk |
| `MB_STATUS` | 11h | status |
| `MB_ID` | 12h | A5h |
| `MB_IDCOMP` | 13h | 5Ah |
| `MB_BASE` | 14h | the first bank number the board answers |
| `MB_SIZE` | 15h | how many 64K banks it has |
| `MB_VERSION` | 16h | the board's version |
| `HSR` | F4h | the 2068's horizontal select register |
| `SYSCON` | 5CBCh | the pointer to the bank table |
| `SYSCON_END` | 2082h | the bank search's exit (marks the table's end, CLEAR-PRB) |
| `SA_RET` | 00E5h | the tape routines' exit: border, BREAK test, EI, POP AF, RET |
| `PICO_SA` | 1879h | the Pico SAVE block (§6.2), what 0068h jumped to |
| `PICO_LD` | 196Dh | the Pico LOAD block (§6.1), what 00FCh jumped to |
| `R_BIT` | 5 | TPMODE's `r:` bit |

### `MB_BOOT` (3998h)

Reached by the `JP` at EXROM 0A3Eh, where the 2068 started its bank search
(both entries, from 09F4h's fall-through and from 1CA8h's `CALL`, arrive
there). Writes OWN7 … OWN0 = 0 and WPROT = 0 through `MB_WR`, then
HL = (SYSCON) + 0Dh and `JP MB_DETECT`, which sets the bank count from the
board and ends at `SYSCON_END`, the old search's own exit. The firmware
asks the board's state with mover op 7, not from here. The old renumbering
call (0CFBh) is dropped. The old body, 0A41h–0DAFh, is unreachable.

### `MB_DETECT`

The end of `MB_BOOT` (its `JP`, the same size as the old `JP SYSCON_END`):
the bank count for the Timex bank API ([below](#the-timex-bank-api-bankapiasm-phase-8)).
If ID and IDCOMP read A5h and 5Ah and BASE is 1–253, BASE goes to 6404h
(`MB_MBBASE`, the API's `MBBASE`) and the count to MAXBNK (5CBEh) and 6315h
(`MB_NBANKS`): SIZE, cut so the last bank is 253 at most (FEh and FFh are the
EXROM and HOME; BASE 193 with 64 banks gives 61). Otherwise the count stays
the 0 that 221Fh, 09F4h and 1C8Dh stored. The boot has copied the bank code to
6200h by now (HOME 0E15h); the 64-column copy is made later from that copy,
so it carries both. DE is kept, and HL (SYSCON + 0Dh) for `JP SYSCON_END`.

| Name | Value | What |
|---|---|---|
| `MB_NBANKS` | 6315h | the bank code's count (`NBANKS` in bankapi.asm) |
| `MB_MBBASE` | 6404h | the board's BASE (`MBBASE` in bankapi.asm) |
| `MAXBNK` | 5CBEh | the 2068's bank count |

### `MB_CALL_HOME`

`CALL_HOME` (EXROM 03DDh) with HOME in chunks 0–1 only. 03DEh's `LD HL,FF00h`
is patched to `JP MB_CALL_HOME`, which pushes the bank word FFFCh and the two
zero words, then goes on as the thunk did (`EXX`, `CALL BANK_SWITCH`,
`POP IX`, `RET`). It can't be patched in place: the thunk's `LD H,0` makes
its zeros from FF00h's L, so FFFCh would push a parameter count of FCh, and
CALL_BANK's copy of 266 bytes from SP, which on the 2068 sits just below
6200h, moves the bank code (the interrupt handler at 62AEh included) for the
whole call: a hang and reset, found by the ZEsarUX smoke test
(`SAVE "tpi:ram"`) and now caught by `rom_bankapi_hosttest.py`. Reached from EXROM code, where
chunk 1 is the EXROM.

### `FR_TEST`

A = the prefix's first letter: Z if it is F or R (either case).

### `SET_MODE`

A = TPMODE with bits 4–5 cleared, from `F_HOOK`: stores it with bit 5 set
when the name is `r:` (looks again through `PEEK_NAME`), else as it is.

### `OPEN_TXT`

HL = `FOPEN_TXT` or `ROPEN_TXT` for the name `PEEK_NAME` finds; BC and DE kept.

### `ROPEN_TXT`

`"tpi:ropen "`, the same length as `FOPEN_TXT` (an `ASSERT`).

### `R_SA` (39F5h), `R_LD` (3A06h)

The SAVE and LOAD block entries (from 0068h and 00FCh). TPMODE bit 5 clear:
on to `PICO_SA` / `PICO_LD`. Set: C = the direction (0 SAVE; 1 LOAD when
carry is set, 2 VERIFY when not) and on to `R_BLOCK`.

### `R_BLOCK`

Pushes `SA_RET` as the return, DI, and sends `tpi:rblk` with IX and DE as
four hex bytes (through `CH_SEND`, its payload on the stack), PMR1 = the
direction, PMR2 = the flag; then `BIOS_C_END` takes the answer, function 89h
and the status after it. Done: carry set, bit 5 cleared after a data block
(kept after a header, for the data block to follow). Failed: bit 5 cleared,
`C_FAIL` raises the report.

### `R_OFF`

Clears TPMODE bit 5; AF kept.

### `CMD_RBLK`

`"tpi:rblk ",0`.

### `FN_EXT` (3A61h)

The response functions past 87h, from 2213h: A = code − 1; 87h →
`LOWER_LOOP` (function 88h), 88h → `MOVER` (function 89h), else `RET` (the
chain's Report D).

### `MOVER` (3A6Bh)

Function 89h. Saves IX and the IFF (`LD A,I`), DI, makes the frame
(`MV_FRAME` bytes, IX = SP) and probes the board (`MB_PROBE`). Then reads
operations: the first at once, each later one after `BIOS_WF_NPH`. Op 0 ends:
the frame and the IFF are put back and `C_END_TAIL` reads the answer. Op 7 is
`MV_INFO`; 1–6 take `MV_PARAMS` and `MV_RUN`; their reply goes out through
`MV_TX`. An op of 8 or more ends with carry and A = 9 (Report J).

The frame, at IX:

| Name | Offset | What |
|---|---|---|
| `MV_BASE` | 0 | BASE |
| `MV_LIM` | 1 | SIZE × 8, the first page past the board (word) |
| `MV_OK` | 3 | 1 if `MB_PROBE` found the board |
| `MV_ADDR` | 4 | the 2068 address (ops 1–3) |
| `MV_LEN` | 6 | the length left |
| `MV_PAGE` | 8 | the board page |
| `MV_OFF` | 10 | the offset in it |
| `MV_PAGE2` | 12 | op 6's destination page |
| `MV_OFF2` | 14 | and offset |
| `MV_OP` | 16 | the operation |
| `MV_RES` | 17 | the reply so far |
| `MV_XOR` | 18 | ops 4–5's running XOR |
| `MV_N` | 19 | this piece's length |
| `MV_W1` | 21 | the first window's saved state: chunk, OWN, SUB, HSR |
| `MV_W2` | 25 | op 6's second window's |
| `MV_FRAME` | 29 | the frame's size |

### `MB_PROBE`

`MV_OK` = 1 if ID and IDCOMP read A5h and 5Ah; then `MV_BASE` and `MV_LIM`.

### `MB_RD`, `MB_WR`

A = a register: `MB_RD` reads it into A; `MB_WR` writes E to it.

### `MV_PARAMS`

Reads an op's parameters into the frame: ops 1–3 eight bytes from
`MV_ADDR`, ops 4–5 six from `MV_LEN`, op 6 ten from `MV_LEN`.

### `FRAME`

HL = IX + E.

### `MV_INFO`

Op 7: sends found, BASE, SIZE, STATUS; A = VERSION, the reply.

### `MV_RX`, `MV_TX`

A byte from / to the Pico, after `MV_PACE`.

### `MV_PACE`

A delay of (`READ_DELAY` + 4) DJNZ loops, about 75 µs with the call, so the
Pico can keep its FIFO fed (as `CH_FETCH` paces).

### `MV_RUN`

Ops 1–6. Refuses with reply 3 (no board) or 4 (`MV_RANGE`) through
`MV_REFUSE`. Otherwise one piece at a time: the piece is as long as fits in
the page (`MV_ROOM`), in the 2068 address's chunk (ops 1–3) and in op 6's
destination page; maps a window (`MV_WIN`, `MV_MAP`; two for op 6), runs
`MV_DO`, unmaps (`MV_UNMAP`, the second window first) and advances
(`MV_ADV`). After the last piece op 4 sends the XOR, op 5 reads the Pico's
and replies 5 if they differ.

### `MV_REFUSE`

A = the reply. Keeps the stream in step: op 4 sends len + 1 zeros, op 5 reads
len + 1 bytes and drops them.

### `MV_DO`

One piece, HL = the board side in the window, DE the other: op 1 LDIR
2068 → board, 2 board → 2068, 3 compare (reply 2 on a difference), 4 send,
5 receive (both keeping `MV_XOR`), 6 board → board.

### `MV_ROOM`

HL = min(HL, 2000h − DE), DE an offset in a chunk (callers mask an address first).

### `MV_RANGE`

Carry if the offset is 2000h or more, or the run's last page, page + ((off +
len − 1) >> 13) worked out to 17 bits, is `MV_LIM` or beyond.

### `MV_ADV`

Adds the piece to an offset and carries into its page.

### `MV_WIN`

A = the first chunk of 4–7 not in B's mask, after adding the chunks of
SP − 32 and SP + 48 to it (the stack and the frame).

### `CHUNK_BIT`, `CHUNK_MASK`

A = an address's high byte (`CHUNK_BIT`) or a chunk (`CHUNK_MASK`): A = the
chunk's bit. BC kept.

### `MV_MAP`

A = the window chunk, HL = page: saves the chunk, its OWN, SUB and the HSR
at (DE), sets OWNw = BASE + page / 8, SUBw = page AND 7, then the HSR bit;
HL = w × 2000h.

### `MV_UNMAP`

Puts back what `MV_MAP` saved, at (HL): the HSR first when the chunk was the
2068's own (OWN 0), then OWN and SUB, then the HSR.

### The Timex bank API (`bankapi.asm`, phase 8)

`src/rom/fdd/bankapi.asm`, assembled only by `build-rom.py --megabank`,
replaces the 2068's bank code at RAM 6316h–6571h (EXROM 1116h–1371h: HOME's
boot copies EXROM 1000h–162Fh to 6200h, [home.md](home.md#0e0ch-a-16k-exrom))
so that BANK_ENABLE and the rest drive the board. Every entry point the 2068
documented stays where it was:

| Routine | RAM | What |
|---|---|---|
| `GET_WORD` | 6316h | genuine: HL = the word at HL in bank B |
| `PUT_WORD` | 633Bh | the word in DE to HL in bank B; the Technical Manual's fix (6.5.3): `PUSH DE`, so DE survives `LD D,B` |
| (WRITE_BS_REG, READ_BS_REG) | 635Ch–6403h | was WRITE_BS_REG/READ_BS_REG, Timex's nibble-wide expansion-bus registers: nothing uses them (the boot's search is gone, there is no such hardware), so the space holds the helpers below |
| `MBBASE` | 6404h | data: the board's BASE (`MB_DETECT`) |
| `GET_STATUS` | 6405h | B = a bank; C = its chunks, low active (bit n clear: it has chunk n); A, B, DE, HL kept. HOME: the HSR's clear bits. DOCK (FFh bit 7 clear) and EXROM (set): the HSR's set bits less the board's, FFh if the other is selected. A board bank: `OWNMAP`; other banks FFh. B is kept for every bank (6.5.2) |
| `GET_CHUNK` | 644Dh | genuine: A = the bit of HL's chunk |
| `GET_NUMBER` | 645Eh | A = the bank in control of HL's chunk: its OWNn if a board bank, else FFh (HSR bit clear), FEh (set, FFh bit 7 set) or 0. BC, DE, HL kept. The genuine loop lost its count to GET_STATUS's B and never found the EXROM (6.5.7). It must end by 648Bh (an `ASSERT`): RAM 648Bh–6496h is EXROM 128Bh–1296h, the fast entry's switch loops and landing |
| `BANK_ENABLE` | 6499h | B = the bank, C = its chunks low active; all registers kept |
| `SAVE_STATUS` | 651Eh | IX = a 19-byte frame: FFh, F4h, OWN0–7, SUB0–7, the select (FDh); IX ends on the last byte. AF, BC, DE kept |
| `RESTORE_STATUS` | 654Ah | the frame back, IX on its last byte, interrupts off and then as they were (6.5.4); FFh: only bit 7 (6.5.5) |

**`BANK_ENABLE`.** Interrupts off throughout (`LD A,I` twice for the NMOS
Z80's IFF2 slip, then `DI`) and back as they were, never an unconditional
`EI`. `TIMEX_HSR` first gives the HSR (in H) and FFh bit 7 as Timex's code
would, without the board. Then, if there is a board, `ISBOARD` decides
whether B is one of its banks, and two passes over OWN0–OWN7 apply
`NEWOWN`: a chunk asked for goes to B (or to no board bank, if B isn't
one); a chunk B owns and isn't asked for goes back to HOME, its HSR bit
cleared; other banks' chunks are untouched. Pass A works out the chunks the
board will own (they keep their HSR bits) and clears the given-up ones' bits
in H; then the HSR is written with the bits that go cleared, pass B writes
each OWNn that changes (and each one asked for, which resets its SUB), and
last the HSR whole. That is the HSR rule: OWN before its bit on the way in,
the bit before OWN on the way out. With no board (count 0) only the HSR and
FFh change.

**DOCK and EXROM get exactly the chunks asked for.** Timex's code tied the
EXROM to chunks 0–1 (chunk 0 asked for meant both, and HOME taking chunk 0
back also selected the DOCK). `TIMEX_HSR` doesn't: the EXROM can be put in
any chunk, as Charlie Day's LEAP ROMs put it in chunk 6, and HOME taking a
chunk back changes nothing else, but for one thing: when HOME (or an
expansion bank) leaves no chunk to the DOCK or the EXROM, `TO_HOME` clears
FFh bit 7. Timex's rule kept it clear at rest, and a Spectrum ROM in the DOCK
needs that: without it every EXROM call left the bit set, and `OUT 244,3`
(the TS-Pico's ZX48 mode) put the EXROM in chunks 0–1 instead of the DOCK,
and the 2068 crashed back to its own start. The DOCK and the EXROM still
share FFh bit 7, so one of them at a time. The crossings ask for both chunks (FEFCh, and
FFFCh after the patches below), so they are unaffected.

**The frame.** SAVE_STATUS's frame was the bank count + 2 bytes; it is 19
now whatever the count, and `build-rom.py` patches the three places that
made room for it to constants (the interrupt handler at 62B7h, CALL_BANK
at 65F8h, XFER_BYTES at 672Fh). With no board the 17 board bytes are saved
all the same (whatever the bus gives), but `RESTORE_BOARD` skips the 16
registers (`NOBOARD`) and writes only the select (FDh, which `MB_DETECT`
writes on any 2068) and the HSR. Earlier 2.5 builds sent the 16 to the
select port as well: harmless, but about 1300 T-states with interrupts
off on every crossing, enough to lose frame interrupts in the folder menu's
key loop.

**64 columns.** The video-mode service copies 6000h–683Fh to F7C0h and
adds 97C0h to each word the table at EXROM 1D00h lists. `build-rom.py`
assembles bankapi.asm twice, with `RB` = 0 and 97C0h, and every word that
differs by 97C0h goes in the table: 33 from bankapi.asm, plus the old
entries outside 6316h–6571h, less the three frame operands, with the
genuine table's wrong entry 674Fh (a `CALL`'s opcode) corrected to 6744h
(SAVE_STATUS's call in XFER_BYTES): 66 entries, ending 1D85h, in zeros that
run to 1EDBh. `rom_bankapi_hosttest.py` runs the API from both copies.

**Other bytes it patches** (`MB_PATCHES`):

- 6315h's image byte FFh → 0: the boot clears it, but the code trusts it.
- XFER_BYTES, Wes Brzozowski's fixes: no `PUSH AF`/`POP AF` (6722h,
  67FFh) so A returns 0 or 1, with the parameter offset 0Ah → 08h (672Bh);
  the same-bank mask to E (676Ah, the Technical Manual's 6.5.8); the
  no-room exit keeps A = 1 (67C2h); the copier stores the destination from
  DE (66DFh, 66E2h); the end address is start + length − 1 and the
  direction is FFh (66F3h).
- The EXROM's crossings into HOME ask for chunks 0–1 (FFFCh), not every
  chunk (FF00h), which took the chunks of any board bank mapped elsewhere:
  08DFh and 001Eh in place (`LD L,0` → `LD L,FCh`), and `CALL_HOME`
  through `MB_CALL_HOME` (below).

What it doesn't change: the bank stack (65CEh's pointer, starting at 65CEh
and growing down through the FFh bytes 658Eh–65CDh, which only look free),
GOTO_BANK, CALL_BANK and XFER_BYTES apart from the bytes above, and HOME's
own `LD BC,FF00h / CALL 6499h` sites (HOME taking all chunks, as Timex
meant). The ROM writes the HSR directly only at boot (HOME 0E0Bh, 0E25h,
EXROM 0049h, before `MB_BOOT` clears the owners) and in the mover. LEAP's
own direct writes (F4h = 40h, then 0) would break the HSR rule for a board
bank mapped elsewhere: a matter for a LEAP build for the board.

#### Its constants and helpers

| Name | What |
|---|---|
| `RB` | 0, or 97C0h for the 64-column assembly (`-DRB=`) |
| `PORT_SEL`, `PORT_DAT` | FDh and FCh, the board's ports (`MB_SEL`, `MB_DATA`) |
| `HSR`, `DEC` | F4h and FFh |
| `NBANKS` | RB + 6315h, the count |
| `ISBOARD` | B = a bank: kept if BASE ≤ B < BASE + count, else 0 |
| `OWNMAP` | A = a bank (0: any): the chunks it owns, bit n for chunk n; 0 with no board. OWNn of FEh or FFh counts as none |
| `NEWOWN` | BANK_ENABLE's rule for one chunk: A = its OWNn, B the board bank (or 0), D its bit, E the chunks asked for; A = what OWNn must be |
| `TIMEX_HSR` | BANK_ENABLE's first half (above): H = the HSR, FFh bit 7 set or cleared. Sits in SAVE_STATUS's slot |
| `TO_HOME` | TIMEX_HSR's HOME and expansion-bank tail, in GET_STATUS's spare bytes (RAM 6440h): with H = 0, no DOCK or EXROM chunk left, FFh bit 7 cleared (the DOCK selected, as Timex's code left it); otherwise nothing |
| `SAVE_BOARD` | SAVE_STATUS's second half: the 16 registers and the select. Reads only, but for the select |
| `RESTORE_BOARD` | RESTORE_STATUS's second half: FFh bit 7, the 16 registers (OWN0–7 first, each setting its SUB, then SUB0–7), the select, then the HSR whole. With no board (count 0) it jumps to `NOBOARD` before the registers |
| `RESTORE_TAIL` | RAM 63F0h, inside RESTORE_BOARD: from here on the select and the HSR, IX stepped to the frame's last byte. Both paths, the board's and `NOBOARD`'s, end through it |
| `NOBOARD` | RAM 6566h, in RESTORE_STATUS's spare bytes after its `JP RESTORE_BOARD`: IX += 16, past the registers no board needs, then `JP RESTORE_TAIL`. Without it the 16 went to the select port (FDh) with interrupts off, about 1300 T-states every bank crossing; the folder menu's key loop (POLL_KEYPRESS to KEY-SCAN through CALL_HOME) crosses without a pause, and in ZEsarUX with no board half the frame interrupts were lost (`FRAMES` up 24 a second; 52 with `NOBOARD`), enough to miss a key (`tools/emu/smoke.py`) |

### The `r:` channels (`rchan.asm`, phase 9)

`src/rom/fdd/rchan.asm`, assembled only with `-DMEGABANK`, at EXROM
2400h–2C77h (2168 bytes; the run 23D4h–2FFFh is free in 2.4, and an `ASSERT`
keeps it below 2C8Ch, where the fast entry lands): `OPEN #n,"r:name"[,"mode"[,reclen]]`, `PRINT #`,
`INPUT #`, `INKEY$ #` and `CLOSE #` on the Megabank's RAM disk, as `f:`
does them on the card (the Megabank spec, "Channels"). Modes `r`, `w`, `a`,
`u`, with `b` for binary; a record length makes a record file; `"r:"` alone or
a name with `*` or `?` opens a listing, one 10-byte name a record.

The split: the firmware keeps the file system ([ramdisk.md](../firmware/ramdisk.md#channels-the-open-stream-slots));
the ROM keeps an open file's bytes. OPEN sends `tpi:rchopen`; the firmware
finds or makes the file, gives it an extent on the board, writes the
stream's slot in the RAM disk's top page, and copies the slot's 15-byte block
into 2068 memory with the mover's op 2. The record in CHANS is built from
it. From then on every character is read or written by the ROM itself,
straight to the board through chunk 0 (`BOARD_IO`, `RCH_SYNC`: all the code
here is in chunk 1, so chunk 0 is free while it runs): no exchange with the
TS-Pico. Past the extent
`PRINT #` sends `tpi:rchgrow`; `CLOSE #` writes the length and position back
to the slot and sends `tpi:rchclose`, which puts the length in the directory.

The record is an ordinary channel record, letter `R`. Its input routine is
an `F` record's HOME stub (14A9h) and its output routine, a stub in the
record itself, passes what it doesn't keep to the other (14A0h), so `G_OUT`
and `G_IN` send it here by its letter and `r:` needs no HOME bytes of its
own. It takes `R_ALLOC` bytes in CHANS,
padded as an `F` record is.

**The fast entry** (the Megabank spec, open question 21). In the Megabank
ROM both stubs, and the BEEPER thunk at 03F3h, go to HOME's `FASTH` (1265h,
a build-rom.py patch) instead of Timex's bank call (03FCh). Under DI, with
chunks 0–1 HOME (otherwise it takes 03FCh, as before), `FASTH` sets FFh bit 7,
keeps FFh as it was on the stack and jumps to the switch loop at 128Bh with
F4h's bits 0–1 set in A; `FX_ENTRY` comes back through the loop at 128Fh
(`FX_BACK`) and `FASTH` puts FFh back (all of it, where `RESTORE_STATUS`
puts back bit 7 only) and does EI.

**The switch loops.** The F4h writes run from ROM, and the TS-Pico, which
serves both ROMs, follows a write to F4h some time after it: a v3 card
applies it from a polled loop on core 1 ([tsbus.md](../firmware/tsbus.md)),
about a microsecond after the write and with nothing to bound it. Timex's
bank code switches from RAM and never notices. The first fast entry (PR
#433) put its `OUT` at HOME 002Eh and expected the next fetch, 0030h, to
come from the EXROM; on a 2068 the card sometimes served one more read from
HOME (BC-SPACES is there), and the editor dropped keys. So the rule: **no
bank switch from ROM unless the code after the `OUT` is the same in both
ROMs until one read tells them apart.** 128Bh–1292h is free in both ROMs
(`FASTH`'s spare bytes in HOME; bankapi.asm's padding before `BANK_ENABLE`
in the EXROM) and holds two loops, the same bytes in both but for each
`JR`'s displacement:

| Address | HOME | EXROM | |
|---|---|---|---|
| 128Bh (in) | `D3 F4 18 FC` | `D3 F4 18 04` | `OUT (F4h),A / JR`: HOME's goes back to 128Bh, the EXROM's on to 1293h |
| 128Fh (out, `FX_BACK`) | `D3 F4 18 E9` | `D3 F4 18 FC` | `OUT (F4h),A / JR`: the EXROM's goes back to 128Fh, HOME's to `FASTH`'s tail at 127Ch |

Whichever ROM a read comes from, the Z80 repeats the `OUT` (23 T-states a
turn) until the displacement, one read, comes from the ROM it wants. Coming
in, chunk 1 is checked too, since `FX_ENTRY` is there and the card writes
its chunk table an entry at a time: the EXROM's 1293h is `LD HL,2C8Ch /
JP (HL)`. HOME's byte at 2C8Ch is `E9h`, a `JP (HL)` that jumps to itself
while chunk 1 is still HOME; the EXROM's bytes there are `JP FX_ENTRY`.
Going out only chunk 0 is checked: `FASTH`'s tail is all in chunk 0. If the
card never followed the write the Z80 would loop with interrupts off. The
round trip costs 4 T-states more than #433's. No
`SAVE_STATUS`/`BANK_ENABLE`/`RESTORE_STATUS` (16 board registers each), no
frame on the bank stack and no error trap per character: an error raised
in the EXROM goes through its RST 8, which pages HOME with `GOTO_BANK` and
needs no frame. The exchanges that can reach HOME code (`f:`'s buffer,
`r:`'s growth) run under `GUARD0`, once an exchange.

The bytes (`MB_PATCHES` and two `mb_after`s in build-rom.py, each with the
bytes it replaces):

| Where | Was | Now |
|---|---|---|
| HOME 14A0h, 14A9h | `DI / LD HL,vec / CALL 03FCh / EI / RET` | `LD HL,vec / JP 1265h` and three `FFh` |
| HOME 041Ch (03F3h's tail) | `CALL 03FCh / EI / RET` | `JP 1265h / EI / RET` |
| HOME 1241h | `JR NC,1265h` (CHAN-OPEN's banked-channel branch) | `JR NC,123Dh`: Report O, as an unknown letter; nothing makes such a channel |
| HOME 1265h–1292h | that branch (46 bytes) | `FASTH`: `DI / LD C,A / LD B,L / IN A,(F4h) / AND 3 / JR NZ,slow / IN A,(FFh) / PUSH AF / OR 80h / OUT (FFh),A / IN A,(F4h) / OR 3 / JP 128Bh`; 127Ch, the tail: `POP DE / POP AF / OUT (FFh),A / PUSH DE / POP AF / EI / RET`; 1284h, slow: `LD A,C / CALL 03FCh / EI / RET`; one `FFh`; 128Bh `OUT (F4h),A / JR 128Bh`; 128Fh `OUT (F4h),A / JR 127Ch` |
| EXROM 128Bh–1296h | twelve `00h`, bankapi.asm's padding (RAM 648Bh–6496h in the boot's copy, where nothing reads them) | 128Bh `OUT (F4h),A / JR 1293h`; 128Fh `OUT (F4h),A / JR 128Fh` (`FX_BACK`); 1293h `LD HL,2C8Ch / JP (HL)` |
| EXROM 2C8Ch | `FF FF FF` | `JP FX_ENTRY`; HOME 2C8Ch is `E9h`, `JP (HL)`, already (an `MB_ANCHORS` entry) |

`rom_rchan_hosttest.py` runs `PRINT #` and `INPUT #` through 14A0h and
14A9h with HOME and the EXROM modelled, and faults any fetch outside these
bytes, then again with the card following each F4h and FFh write 0 to 200
memory reads late, at random, and with chunk 1 behind chunk 0; `tools/emu/chan_speed.py` times `RST 10h` to a stream in ZEsarUX.

**The stub and its buffer.** An `R` record's output routine is in the record
itself (`RR_STUB`, copied from `STUB_IMG` by `RCH_OPEN`), so most characters
never leave RAM. After each byte `RCH_OUT` handles, `RCH_FILL` works out how
many of the next bytes the stub may keep: a stream file open for writing, at
its end, with no TAB in progress; up to the next 256-byte boundary, the
extent's end, the 8K page's end or the buffer's size (`RR_FMAX`, 57). The
stub puts a byte of 32 or more in `RR_FBUF` with interrupts on and no bank
switch; a CR, a control or a full buffer goes through `FASTH` to `RCH_OUT`,
whose `RCH_SYNC` writes the buffer to the board with one map of chunk 0 and
one `LDIR`, then adds it to the position, length and column before any other
path uses them. `RST 10h` to an `r:` stream costs about 400 T-states a byte
this way (396 with the flushes shared out: `tools/emu/chan_speed.py`),
against about 830 with a ROM switch for every byte and about 13 300 through
Timex's bank call. The buffer never crosses a 256-byte boundary and is
written at every CR, so the write-backs to the slot (each CR and each 256th
byte) and what NEW or a reset keeps are as they were: bytes after the last
CR were never in the file's length.

The record's `R_OUT` is the one address in it that depends on where the
record is. `CLOSE #` of an earlier `F` or `R` record moves the later ones
down, so both closes reclaim through `RCH_RECL`, whose `RCH_FIX` points every
`R` record's `R_OUT` at its own stub again.

**The open-stream mask.** Every `r:` command tells the firmware which streams
0–15 point at an `R` record (bit *n*: stream *n*), so it closes the slots of
streams that NEW, a reset or a POKE took away and their lengths reach the
directory. The channel commands carry it in their payload; `tpi:rmask`
carries it before the commands that have none (from `TPI_SEND` through
`MB_TPRE`, for ERASE, MOVE, COPY, FORMAT and CAT `"r:…"`; from `SET_MODE`, for
SAVE, LOAD, VERIFY and MERGE `"r:…"`).

**Where it differs from `f:`.** A record that overflows is Q with the position
back at the record's start, but the bytes already written stay (`f:` writes
nothing). `RESTORE #` and `CAT #` on an `r:` stream are Report O: `STRM_REC`
takes only `F` records. A channel file holds at most 65535 bytes (a tape
header's length): Q past it.

`rom_rchan_hosttest.py` runs OPEN, PRINT, INPUT, TAB, records, growth, the
listing and CLOSE in the Z80 interpreter against the firmware's own `Disk`
over a model board; `tools/emu/megabank_smoke.py` runs them from BASIC in
ZEsarUX with the real firmware.

| Name | Value | What |
|---|---|---|
| `RCH_BASE` | 2400h | where `rchan.asm` is assembled (fddcmd.asm) |
| `RCH_END` | 2C78h | its end; `ASSERT`ed at most 2C8Ch, the fast entry's `JP FX_ENTRY` (build-rom.py) |
| `R_ALLOC` | 100h | an `R` record's allocation in CHANS |
| `BLOCK_LEN` | 15 | the slot's block, as ramdisk.py's |
| `SLOT_OFF`, `SLOT_LEN` | 0200h, 32 | the slots in the RAM disk's top page, one a stream |
| `SLOT_LP` | 22 | the length and position in a slot (its block at +16, then +6) |

The record (IX), after the 7 bytes of a channel record (the two routines, the
letter, its length):

| Name | Offset | What |
|---|---|---|
| `RR_FL` | 7 | the flags (below) |
| `RR_REC` | 8 | the record length; 0: a stream file |
| `RR_OST` | 9 | output state: 0; 1 after 23 (TAB), 2 after its low byte |
| `RR_TLO` | 10 | TAB's low byte |
| `RR_BUF` | 11–18 | = `R_OUTBUF`: a channel command's payload; TAB 0's count as digits |
| `RR_SPG` | 19–20 | the block: the extent's start page |
| `RR_SOF` | 21–22 | its offset in that page |
| `RR_EXT` | 23–24 | the extent in bytes |
| `RR_LEN` | 25–26 | the length |
| `RR_POS` | 27–28 | the position |
| `RR_MPG` | 29–30 | the slot's page |
| `RR_BREC` | 31 | the block's record length |
| `RR_BFL` | 32 | the block's flags |
| `RR_BMODE` | 33 | the block's mode |
| `RR_COL` | 34 | writing: the column (a stream file), or the record's bytes so far |
| `RR_RCOL` | 35 | reading a record file: its bytes given so far |
| `RR_DIG` | 36 | reading TAB 0's count: the next digit's offset |
| `RR_FBNK` | 37 | the cursor: OWN0 for the position's page (BASE + page / 8) |
| `RR_FSUB` | 38 | SUB0 for it (page MOD 8) |
| `RR_FPTR` | 39–40 | the position's address in chunk 0, where `RCH_SYNC` writes the buffer |
| `RR_FCNT` | 41 | bytes the stub may still take; 0: none |
| `RR_FDONE` | 42 | bytes the stub holds in `RR_FBUF` since the last `RCH_SYNC` |
| `RR_FBUF` | 43 | the stub's buffer, `RR_FMAX` bytes. `RR_FCNT`, `RR_FDONE` and the buffer are in the order the stub steps through |
| `RR_FMAX` | 57 | the buffer's size: what is left between `RR_FBUF` and `RR_STUB` |
| `RR_STUB` | 100 | the record's output routine, `STUB_LEN` bytes copied from `STUB_IMG`; `R_OUT` is its address |
| `STUB_LEN` | 28 | the stub's size |
| `RR_SIZE` | 128 | the record's used size: all that the padding leaves of `R_ALLOC` |

| Flag | Bit | Meaning |
|---|---|---|
| `F_REC` | 0 | a record file |
| `F_BIN` | 1 | binary: no text translation |
| `F_RD` | 2 | may be read (`r`, `u`) |
| `F_WR` | 3 | may be written (`w`, `a`, `u`) |
| `F_QRY` | 4 | TAB 0 came: the next read is the count |
| `F_NCR` | 5 | a text line is open: the end gives a CR |
| `F_LCR` | 6 | the last byte read was a CR: drop an LF |

#### The fast entry

| Name | Value | What |
|---|---|---|
| `THUNK_HL` | 5DCDh | where HOME's thunks leave the caller's HL (BEEPER's, for `G_BEEP`) |
| `FX_BACK` | 128Fh | `SW_OUT`, in both ROMs: `OUT (F4h),A / JR`. The EXROM's `JR` goes back to 128Fh, HOME's to `FASTH`'s tail (127Ch): the `OUT` is repeated until the displacement is read from HOME |

| Routine | Address | What |
|---|---|---|
| `FX_ENTRY` | 2400h | (pinned: `MB_FIXED_SYMS`) from `FASTH` through the switch loop at 128Bh and the landing (EXROM 1293h, 2C8Ch): B = the low byte of the stub's vector, C = the character, on the stack FFh as it was. It leaves by pushing AF, the result, and jumping to `FX_BACK` with A = F4h, bits 0–1 clear. Output to an `R` record (what its stub didn't keep) goes to `RCH_OUT` and to an `F` record to `CH_OUT` (MB_OUT's letter test, inline); input to `MB_IN`; `BEEP_VEC` to `G_BEEP` with `THUNK_HL`. AF goes back under `FASTH`'s return, then `FX_BACK` |
| `G_FLUSH`, `G_FETCH` | 2433h, 2438h | `CH_OUT`'s and `CH_IN`'s exchanges (`CH_FLUSH`, `CH_FETCH`) under `GUARD0`: their status can run a response function that prints through HOME |
| `GUARD0` | 243Bh | `GUARDED` (fddcmd.asm) for a routine HL called under the fast entry, which pushed no frame on the bank stack: the trap joins `GUARDED` at `.bs` with (`BANK_SP`) as it is now |

#### The hooks

| Routine | Address | What |
|---|---|---|
| `MB_OUT`, `MB_IN` | 2447h, 2455h | `G_OUT` and `G_IN`: the current channel's record by its letter, on to `RCH_OUT`/`RCH_IN` for `R`, else `CH_OUT`/`CH_IN`. A, the character, is kept. `MB_IN` first clears TV_FLAG bit 3, which RDCH set (#446, [`G_IN`](#g_main-g_out-g_in-g_open-g_osyn-g_close)): here, so the fast entry's reads clear it too |
| `RCH_LETTER` | 2463h | Z if the current channel's letter is `R` |
| `BEEP_LT` | 246Eh | `G_BEEP`'s test for `F` and `R` records (replaces `POP HL / CP 'F'`; the saved HL is under the return address). Z: no click |
| `RCH_KIND` | 2478h | `CH_OPEN_HOOK`'s `CALL SPEC_KIND`: `"r:…"` is answered here in full (`RCH_OPEN`); anything else goes on to `SPEC_KIND` |
| `RCH_CLTEST` | 2484h | `CH_CLOSE_HOOK`'s letter test: an `R` record is closed here in full (`RCH_CLOSE`); otherwise A = the letter compared with `F` |
| `MB_TPRE` | 2492h | `TPI_SEND`'s opening, after a `tpi:rmask` when the command (its descriptor on top of the calculator stack) names `r:` |
| `SET_MODE_R` | 24C3h | the end of `SET_MODE`: TPMODE := A; an `r:` statement (bit 5) sends the mask first |
| `RMASK_SEND` | 24C9h | `tpi:rmask` with the mask, PMR1 0; its status, then a wait for IDLE (as `CH_SEND`'s), since `TPI_SEND`'s stock session code sends its SYNC without one. IX kept |
| `RCH_MASK` | 24F7h | DE = the mask: bit *n* set if stream *n* (0–15) points at an `R` record |

#### OPEN and CLOSE

| Routine | Address | What |
|---|---|---|
| `RCH_OPEN` | 2525h | the stream in 5CCBh, the spec on the calculator stack, `CH_ADD` on a `,` if a mode follows. Parses as `f:` does; sends `tpi:rchopen` (PMR1 the stream, PMR2 the record length, FFh for 255 or more) with the mask, the address the block goes to (16 bytes made on the stack), the mode, a space, the name. Then `R_ALLOC` bytes at CHANS' end, filled from the block. Out: C, DE = the offset, HL = the STRMS entry, as `CH_OPEN_HOOK` |
| `RCH_CLOSE` | 2691h | IX = the record, BC = the stream's offset. An open record is padded, the length and position written back, `tpi:rchclose` sent; a refusal raises its report and leaves the stream open. Then the allocation goes as an `F` record's does, every later offset moved down `R_ALLOC`. Out: C, HL = the STRMS entry, which HOME 13A8h clears |

#### Writing

| Routine | Address | What |
|---|---|---|
| `RCH_OUT` | 271Bh | the output routine (`MB_OUT`, or `FX_ENTRY` with what the record's stub didn't keep), A = the character: `RCH_SYNC`, `RCH_PUTC`, then `RCH_FILL` |
| `STUB_IMG` | 2731h | the image of an `R` record's output routine, which `RCH_OPEN` copies to the record's `RR_STUB`. PRINT-A-2 calls the copy in RAM with A = the character, interrupts on: while `RR_FCNT` is not 0, a byte of 32 or more goes into `RR_FBUF`, `RR_FCNT` down and `RR_FDONE` up, with no bank switch and no port written. Anything else goes on to HOME 14A0h, so to `FASTH`, `FX_ENTRY` and `RCH_OUT`. Position-independent: it finds the record through CURCHL. BC, DE, HL (PRINT-A-2's alternate set) and AF lost |
| `RCH_RECL` | 274Dh | `HC_RECLAIM` for a channel record's allocation, then `RCH_FIX`. From `RCH_CLOSE` and, in the Megabank build, `CH_CLOSE_HOOK`'s `f:` close |
| `RCH_FIX` | 2750h | after a record's allocation has gone and the records above it have moved down: `R_OUT` of every `R` record on streams 0–15 set to the record's own `RR_STUB`. AF, BC, DE, HL lost |
| `RCH_SYNC` | 277Eh | the `RR_FDONE` bytes in `RR_FBUF` copied to `RR_FPTR` through chunk 0 (OWN0 `RR_FBNK`, SUB0 `RR_FSUB`, one `LDIR`, then OWN0 0); `RR_FDONE` added to the position, length (equal while there is a cursor, and below a 256-byte boundary, so only their low bytes move) and column; the cursor ended. From `RCH_OUT`, `RCH_IN` and `RCH_CLOSE`. All registers kept |
| `RCH_FILL` | 27D0h | a new cursor, if a stream file (not a record file) open for writing, with no TAB in progress, has its position at its length and inside the extent: `RR_FCNT` the bytes before the next 256-byte boundary, the extent's end or the 8K page's end, or `RR_FMAX`, the first of them; `RR_FBNK`, `RR_FSUB`, `RR_FPTR` from `RCH_PAGE` |
| `RCH_PUTC` | 2847h | as `f:` does: TAB arrives as 23, low, high and is the position (a record file: record *n*); mode `r` drops what is printed (INPUT #'s prompt); TAB 0 then anything but a read is Q. Text: 16–21 and their parameter, 22 and its two, and other controls but CR and comma are dropped; the comma is spaces to the next 16-column stop; keywords stay one byte. A record file: a CR ends the record and pads it and isn't stored; more than the record holds is Q |
| `RCH_DATA` | 28D2h | C, a byte to store: at the position, the column on |
| `RCH_ENDREC` | 28FDh | the open record padded to its length; the column 0 |
| `RCH_PADC` | 2915h | C = the pad: a space, or 0 in binary |
| `RCH_PUT` | 291Fh | C written at the position, which steps on; a gap from the length up to the position (a TAB past the end) is padded first; a step onto a 256-byte boundary writes the length and position back |
| `RCH_WAT` | 296Ah | C written at file position HL (kept); past the extent, `RCH_GROW` first |
| `RCH_GROW` | 297Ch | `tpi:rchgrow` with the mask, the block's address (16 bytes on the stack) and the length needed; the new extent from the block. Past 65535 bytes: Q. BC kept |
| `RCH_GSEND` | 29C7h | `RCH_GROW`'s exchange (`tpi:rchgrow`, then its status), called under `GUARD0` |
| `RCH_IO` | 29D0h | file position HL (kept): B = 1 writes C there, 0 reads it into A; `RCH_PAGE`, then `BOARD_IO` |
| `RCH_PAGE` | 29DFh | file position HL: HL = its board page, DE = its offset in that page (from the block's start page and offset) |
| `BOARD_IO` | 2A05h | board page HL, offset DE (below 2000h): B = 1 writes C, 0 reads into A (and C). Through chunk 0: OWN0 = BASE + page / 8, SUB0 = page MOD 8, the byte at DE, then OWN0 = 0. Chunk 0 is the EXROM's first half, and nothing here runs from it or keeps data in it; the HSR rule holds because F4h bit 0 is set while the module runs. B and IX kept |
| `RCH_WB` | 2A37h | a writable stream's length and position back to its slot (4 bytes, page `RR_MPG`). The write-protect switch on: J, and first the length and position go back to the slot's, the last ones written back: the board refused every byte since, so the ROM's own length would count bytes the file hasn't got and `CLOSE #` would write it once the switch was off (an 8-byte file for `"one"`, then J on `"two"`, on the board). The column follows: a record file's is the position MOD the record length, a stream's 0 |
| `RCH_SLOT` | 2A63h | B = 1: `RR_LEN` and `RR_POS` to the stream's slot (offset `SLOT_OFF` + 32 × the stream + `SLOT_LP`, page `RR_MPG`) through `BOARD_IO`; B = 0: from it |
| `RCH_TAB` | 2A96h | TAB HL: an open record is padded; TAB 0 asks for the count (the next read); otherwise the position is byte HL − 1, or record HL's start in a record file. A gap past the end is padded by the next write |
| `MUL16X8` | 2AE0h | HL = HL × E; C if it overflows 16 bits |
| `DIV16X8` | 2AF2h | HL = HL / E, A = the remainder (E not 0). B lost |

#### Reading

| Routine | Address | What |
|---|---|---|
| `RCH_IN` | 2B01h | the input routine (HOME 14A9h → `G_IN` → `MB_IN`): C with A = the next byte, or NC NZ at the end of the file (Report 8 from WAIT-KEY) |
| `RCH_GETC` | 2B14h | as `f:` does: a stream opened `w` or `a` is Q; TAB 0 makes the next read the count (records, or bytes) and a CR; a record file gives one record (padded past the end) and a CR. Text: LF and CRLF read as CR, other controls dropped, and a last line with no newline ends with a CR. Binary: every byte as it is |
| `RCH_RAW` | 2C01h | the byte at the position, the position on: C with A; NC at the length |
| `RCH_NUM` | 2C20h | HL in decimal at `RR_BUF`, then a CR; `RR_DIG` points at it |

| String | Address | Text |
|---|---|---|
| `CMD_RCHOPEN` | 2C45h | `"tpi:rchopen ",0` |
| `CMD_RCHGROW` | 2C52h | `"tpi:rchgrow ",0` |
| `CMD_RCHCLOSE` | 2C5Fh | `"tpi:rchclose ",0` |
| `CMD_RMASK` | 2C6Dh | `"tpi:rmask ",0` |

## Where comments, documents and the code disagree

None known. The last, `SEND_FOPEN` and `CH_SEND` reading the pre-load
without checking it, is `PRELOAD` since #179.

