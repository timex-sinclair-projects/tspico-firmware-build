# EXROM 2300h: SYNC, BREAK and recovery (ROM 2.0)

Source: [`src/rom/patches/tspico-sync.asm`](../../../src/rom/patches/tspico-sync.asm)
(318 lines); listing
[`tspico-21-exrom.labelled.asm`](../../rom-analysis/disasm/tspico-21-exrom.labelled.asm)
at 2300h–23D3h. Host test:
[`src/test/rom_sync_hosttest.py`](../../../src/test/rom_sync_hosttest.py).

ROM 2.0 is Gustavo Pane's v1.7 ROM (`src/rom/TSPICO.ROM`, crc32 09D4CA63)
with this one source applied on top. sjasmplus reads the 32 K image with
`INCBIN`, seeks to each patch site with `FPOS`, sets the assembly address with
`ORG`, overwrites the bytes, and writes `TSPICO-SYNC.ROM`. The file is HOME at
offset 0 and EXROM at 4000h, so a file offset equals the Z80 address within
each half. Fifteen sites change: two version bytes, the HOME report printer,
the boot line, and eleven redirected instructions in the EXROM that reach the
new code at 2300h, which sits in the FFh filler after v1.7's last routine
(22FDh). ROM 2.1 is built from this image by
[`tools/build-rom.py`](../../../tools/build-rom.py), so everything here is in
ROM 2.1 too, with one exception: 2.1 re-points the BIOS C_END entry at 184Fh
from `BIOS_C_END` (23CDh) to the module's `C_END2`
([exrom-fdd.md](exrom-fdd.md)). The listing cited is 2.1's; its 2300h block is
byte for byte 2.0's.

What it adds, and why: v1.7 has no way to get the Z80 and the Pico back in
step after a BREAK, a crash or a dropped byte; the result was a 20 s wait and
Report J, and the same again on every command after it
([ROM_CHANGES.md](../../ROM_CHANGES.md), [BREAK_AND_ABORT.md](../../rom-analysis/BREAK_AND_ABORT.md)
proves the v1.7 ROM never tells the Pico about a BREAK). 2.0 opens every
transaction with a SYNC byte on the status port, sends the same byte on BREAK
and raises Report D, checks BREAK inside the byte loops and the key waits,
raises a new Report T when the Pico has dropped a transaction by itself, and
keeps the Pico Interface BIOS's carry contract. The firmware side is
[tspico_io.md](../firmware/tspico_io.md) (`RX_CAPTURE`, `MQ_TO_IDLE`,
`MQ_STATUS`) and [tspico-dispatch.md](../firmware/tspico-dispatch.md)
(`TS2068_IO`); the wire rules are [PROTOCOL.md §4.1](../../PROTOCOL.md).
ROM 2.0 requires firmware 2.0: older firmware reads the SYNC byte as the first
byte of a pre-header.

## Map

| Where | What |
|---|---|
| HOME 0065h | version marker 20h |
| HOME 0F12h–0F1Fh | the report printer hands the text to `EX_REPORT_MSG` |
| EXROM 0479h | `CALL KEYWAIT` (key wait of functions 82h, 84h, 86h) |
| EXROM 06AAh | `JP BRK_ABORT` (BREAK seen by a ready-wait) |
| EXROM 1651h, 16F6h, 189Ah, 1998h, 1BAAh | `CALL SYNC_WRITE` (the first write of each transaction) |
| EXROM 184Ch, 184Fh | BIOS WF_NPH and C_END → `BIOS_WF_NPH`, `BIOS_C_END` |
| EXROM 1853h | BIOS G_VERS byte 20h |
| EXROM 18FDh, 19EFh | `CALL STEP` (SAVE and LOAD byte loops) |
| EXROM 1A58h | `CALL RD_STATUS` (WAIT_PICO_READY's status read) |
| EXROM 1C6Ch–1C85h | boot line |
| EXROM 2300h | `SYNC_WRITE` |
| 230Eh | `SYNC_WAIT` |
| 231Eh | `BRK_ABORT` |
| 2327h | `BRK_TEST` |
| 2339h | `STEP` |
| 2346h | `KEYWAIT` |
| 234Fh | `RD_STATUS` |
| 235Ah | `EX_REPORT_MSG` |
| 237Dh | `EX_HOME_PRINT` |
| 2386h | `MSG_PICO_RESET` (24 bytes of text) |
| 239Eh | `BIOS_WF_NPH` |
| 23CDh | `BIOS_C_END` |
| 23D4h | `NEW_CODE_END` |

## Protocol constants

| Name | Value | What it is | Who uses it |
|---|---|---|---|
| `ABORT_BYTE` | 03h | Ctrl-C. Written to the status port it means "abandon whatever you were doing": the SYNC that opens every transaction, and the BREAK abort. The PIO tags a write to port 0Fh with bit 8 of the RX word (`PORT_0F` in tspico_io.py), so the firmware sees 103h | `SYNC_WRITE`, `BRK_ABORT`, `BIOS_WF_NPH` |
| `PORT_DATA` | 0Eh | the data port | named only; the writes go through `TSPICO_WRITE` |
| `PORT_STATUS` | 0Fh | the status port: `IN` reads the status byte, `OUT` is the abort byte | every routine here |
| `ST_READY` | 6 | bit 6 of the status: 1 = ready. The only bit ROMs up to 1.7 test | `SYNC_WAIT`, `RD_STATUS`, `BIOS_WF_NPH` |
| `ST_IDLE` | 3 | bit 3: 1 = no transaction open (firmware 2.0) | `SYNC_WAIT` |
| `ST_RECOVERED` | 2 | bit 2, active low: 0 = the Pico dropped a transaction by itself. Cleared by the next SYNC | `RD_STATUS`, `BIOS_WF_NPH` |

Old firmware always showed FFh: ready, idle, not recovered. So on old
firmware `SYNC_WAIT` returns at once and `RD_STATUS` never fires; the new
tests cannot misfire on a missing bit. The firmware's four values are FFh
idle, F7h mid (READY without IDLE), FBh recovered and 00h busy
(`MQ_STATUS` in [tspico_io.md](../firmware/tspico_io.md)). Busy has bit 2
clear too, which is why both readers of `ST_RECOVERED` test `ST_READY` first.

## Report codes

RST 8's inline byte is ERR_NR, which holds the report index minus one
([ERROR_TRAPPING.md](../../rom-analysis/ERROR_TRAPPING.md)). HOME prints the
letter from the index: 0–9, then A onward.

| Name | Value | Report | Raised by |
|---|---|---|---|
| `ERR_D_BREAK` | 0Ch | D BREAK - CONT repeats | `BRK_ABORT`; returned in A by `BIOS_WF_NPH` |
| `ERR_T_PICO` | 1Ch | T TS-Pico reset, try again (new in 2.0) | `RD_STATUS`; returned in A by `BIOS_WF_NPH` |

1Ch is the first code after R (1Ah) that HOME can print as a letter (S, 1Bh,
is skipped). HOME's text table has no entry for it, which is what the 0F12h
patch and `EX_REPORT_MSG` are for. The firmware's status-to-report map is in
[appendix/ports-and-status.md](../appendix/ports-and-status.md).

## The v1.7 routines the patch names

These are EQUs for code that already exists in v1.7 and is unchanged. The
curated names of the same addresses live in
[exrom-driver.md](exrom-driver.md), [exrom-chunk1.md](exrom-chunk1.md) and
[home.md](home.md); this table gives the source's names.

| Name | Address | What it is (curated name) | Who calls it |
|---|---|---|---|
| `READ_STATUS` | 0655h | EXROM: `CALL CHECK_BREAK / JP NC,06AAh / IN A,(0Fh) / RET`. The ROM's only status read (`READ_STATUS`) | `RD_STATUS` |
| `CHECK_BREAK` | 069Fh | EXROM: ten debounced scans of row 7Fh, then CAPS SHIFT on row FEh; carry clear = both held (`CHECK_BREAK`) | `BIOS_WF_NPH` |
| `C_END_TAIL` | 227Fh | EXROM: `PICO_TRANSACT`'s read-status tail after its ready-wait: read the status, `DEC A`, run the function chain, A = status−1 and carry on failure | `BIOS_C_END` |
| `POLL_KEYPRESS` | 0546h | EXROM: one keyboard poll, Z = no key (`POLL_KEYPRESS`) | `KEYWAIT` |
| `TSPICO_WRITE` | 229Dh | EXROM: `OUT (0Eh),A / AND A / RET` (`TSPICO_WRITE_DATA`), the ROM's only write to the data port | `SYNC_WRITE` |
| `EX_PO_MSG` | 03EDh | EXROM→HOME PO-MSG: A = entry number, DE = table | `EX_REPORT_MSG` |
| `EX_TO_HOME` | 03DDh | EXROM→HOME returning thunk (`CALL_HOME`): the caller does `PUSH IX / EXX / LD HL,target / JP 03DDh`; the thunk pops IX back on return | `EX_HOME_PRINT` |
| `HOME_TO_EX` | 03FCh | HOME→EXROM returning thunk: `LD (5DCDh),HL / LD HL,target / CALL 03FCh` | the 0F12h patch |
| `HOME_MSG_TABLE` | 0F65h | HOME's report text table. Its first entry is a dummy so that A = ERR_NR+1 indexes it | `EX_REPORT_MSG` |
| `HOME_MSG_SEP` | 1115h | HOME's ", " separator, also behind a dummy first entry | `EX_REPORT_MSG` |
| `HOME_RST10` | 0010h | HOME's RST 10: print A to the current channel | `EX_HOME_PRINT` |

## File layout

| Name | Value | What it is |
|---|---|---|
| `EXROM` | 4000h | file offset of the EXROM half of the 32 K image |

Two macros place the patches. `HOMEAT addr` is `FPOS addr / ORG addr`;
`EXAT addr` is `FPOS EXROM+addr / ORG addr`. `FPOS` moves the output
position in the file, `ORG` sets the address labels take, so a `CALL` emitted
under `EXAT 189Ah` is assembled for Z80 address 189Ah and lands at file offset
589Ah. `OUTPUT "TSPICO-SYNC.ROM"` and `INCBIN "TSPICO.ROM"` come first, so
the whole of v1.7 is written and the patches overwrite it in place. Every
`ASSERT` in the source pins a patch's length to the bytes it replaces.

## Patch sites

Each row is one site. The v1.7 column is what the host test checks before
the build is trusted; the 2.0 column is what the source writes; the listing
confirms the 2.1 image still holds it. The table agrees with
[ROM_CHANGES.md](../../ROM_CHANGES.md).

| Bank | Addr | v1.7 | 2.0 | Why |
|---|---|---|---|---|
| HOME | 0065h | `db 17h` | `db 20h` | The version marker, `PEEK 101`. 2.1 writes 21h here. |
| HOME | 0F12h–0F1Fh | `LD A,B / LD DE,0F65h / CALL 073Fh / XOR A / LD DE,1115h / CALL 073Fh` | `LD A,B / LD (5DCDh),HL / LD HL,EX_REPORT_MSG / CALL 03FCh / 4×NOP` | The report printer. B holds ERR_NR+1. HOME's table has no text for 1Ch, so the text and the ", " are printed by EXROM code that knows it; every other code prints from the HOME table as before. The four NOPs fill the 14 bytes exactly (`ASSERT $ == 0F20h`). |
| EXROM | 1853h | `db 17h` | `db 20h` | The byte of BIOS G_VERS's `LD BC,0017h` at 1852h. 2.1 makes it 21h. |
| EXROM | 1C6Ch–1C85h | the v1.7 boot line | `" 2026 TS-Pico ROM v2.0   "` + `" "│80h` | Same 26 bytes, bit 7 on the last. 2.1 edits the four bytes at 1C7Eh to `v2.1`. |
| EXROM | 189Ah | `CALL 229Dh` | `CALL SYNC_WRITE` | SAVE: the first byte of the header's pre-header. |
| EXROM | 1998h | `CALL 229Dh` | `CALL SYNC_WRITE` | LOAD, VERIFY, MERGE: the first byte of every block's pre-header. |
| EXROM | 1BAAh | `CALL 229Dh` | `CALL SYNC_WRITE` | `tpi:` and `net:` commands: the 'B' of the pre-header. |
| EXROM | 1651h | `CALL 229Dh` | `CALL SYNC_WRITE` | LPRINT and LLIST: each character is its own transaction. |
| EXROM | 16F6h | `CALL 229Dh` | `CALL SYNC_WRITE` | COPY in Pico printer mode. |
| EXROM | 06AAh | `POP BC / JP 1A61h` | `JP BRK_ABORT / NOP` | `READ_STATUS` jumps here when `CHECK_BREAK` says BREAK. v1.7 went to WAIT_PICO_READY's failure exit (A = 02h) and so to Report J after the caller laundered it; 2.0 tells the Pico and raises D. |
| EXROM | 18FDh | `INC IX / DEC DE` | `CALL STEP` | The SAVE byte loop. |
| EXROM | 19EFh | `INC IX / DEC DE` | `CALL STEP` | The LOAD byte loop. |
| EXROM | 0479h | `CALL 0546h` | `CALL KEYWAIT` | The key wait in `GET_KEY_AND_SEND`, used by response functions 82h, 84h and 86h: `CALL KEYWAIT / JR Z,0479h / JP SEND_KEY`. |
| EXROM | 1A58h | `CALL 0655h` | `CALL RD_STATUS` | `WAIT_PICO_READY`'s status read, so every ready-wait in the ROM sees RECOVERED. |
| EXROM | 184Ch | `JP 1A54h` | `JP BIOS_WF_NPH` | The BIOS WF_NPH entry no longer shares the ROM's own wait, which now raises reports. |
| EXROM | 184Fh | `JP 2279h` | `JP BIOS_C_END` | The BIOS C_END entry (184Ah is `JR 184Fh`). 2.1 patches this again to `JP 301Bh`. |

The 2.0 image differs from v1.7 only at these sites and in 2300h–23D3h; the
host test fails on any stray byte.

## `SYNC_WRITE` (2300h)

Starts a transaction: SYNC, wait, then the write the call site used to do.

1. `PUSH AF / PUSH BC`.
2. `LD A,ABORT_BYTE / OUT (PORT_STATUS),A`: the SYNC. The PIO tags the write
   with bit 8 and drops READY (auto-busy, PROTOCOL.md §3.2).
3. `CALL SYNC_WAIT`.
4. `POP BC / POP AF / JP TSPICO_WRITE`: the original `OUT (0Eh),A / AND A /
   RET`, so the caller gets exactly what it got from v1.7, including the
   flags `AND A` sets.

Takes A = the first byte of the pre-header. Preserves every register; only
the flags change, as before. DE, HL, IX and AF' are never touched. AF' is
live in the LOAD loop (`EX AF,AF'` at 19E3h and 19EBh carries the LOAD/VERIFY
flag), which is why this routine saves AF and BC on the stack instead of
using the alternate set.

On the Pico, `RX_CAPTURE` sees the 103h word and returns a negative count;
`TS2068_IO` calls `MQ_TO_IDLE(status=False, first=FIRST_STATUS())`, which
empties both FIFOs and stages one byte — 01h, or the error of a header LOAD
just refused (`FIRST_STATUS`); the dispatcher itself then waits up to 800 ms
for a flash write on the other core to finish, re-arms the pre-header DMA
channel when there is one, and sets the status idle (FFh) (tspico.py
6457–6476). So after a SYNC the link is normally TX = `[01]`, RX empty, whatever state an earlier
client left it in ([tspico-dispatch.md](../firmware/tspico-dispatch.md)).

Beware: the SYNC is sent before the ready-wait of the transaction it opens,
so a Pico that never answers still costs this routine's ~1 s plus the
caller's ~20 s before Report J. On old firmware the byte is read as the
first byte of a pre-header and every later command is misaligned.

## `SYNC_WAIT` (230Eh)

Polls the status port until READY and IDLE are both set, or gives up.

1. `LD BC,0`.
2. `.poll`: `IN A,(PORT_STATUS) / AND 48h / CP 48h / RET Z`: bits 6 and 3.
3. `DEC BC / LD A,B / OR C / JR NZ,.poll`: 65536 polls. The loop is 56 T, so
   the budget is 3,670,016 T, ~1.05 s at 3.5 MHz.
4. `RET`.

Returns Z with A = 48h when the Pico is idle, NZ after the timeout. Clobbers
A, F and BC. It carries on either way: a Pico that never answers still gets
Report J from the next ready-wait, so this routine need not know how to
raise a report, and it can be called from `BRK_ABORT` and `BIOS_WF_NPH` with
nothing on the stack to unwind.

The Pico must say IDLE within this window. `MQ_TO_IDLE`'s slow work (the
log flush) happens before the status is set, never after, because the
pre-header follows within microseconds of IDLE
([PROTOCOL.md §4.1](../../PROTOCOL.md)). A SYNC sent while the Pico is READY
but not yet IDLE (the channel commands' F7h) would be lost with the
pre-header behind it, which is why ROM 2.1's `CH_SEND` waits for IDLE before
calling `SYNC_WRITE` ([exrom-fdd.md](exrom-fdd.md)).

## `BRK_ABORT` (231Eh)

The user pressed BREAK mid-transaction: tell the Pico, let it clean up, then
Report D.

1. `LD A,ABORT_BYTE / OUT (PORT_STATUS),A`.
2. `CALL SYNC_WAIT`: up to ~1 s for READY and IDLE.
3. `RST 8 / DB ERR_D_BREAK`.

Reached by `JP` from 06AAh (BREAK found by `READ_STATUS`, which every
`WAIT_PICO_READY` poll goes through), from `STEP` and from `KEYWAIT`. It never
returns. RST 8 reloads SP from ERR_SP and the HOME handler re-enables
interrupts, so it is safe from any stack depth and from code running under
DI, which the byte loops do. The Pico hears the 0Fh write wherever it is
listening (`RX_CAPTURE`, `RX_BLOCK`, `TX_ROOM`, `CMD_PUT`, `CMD_KEY`,
`CMD_DRAIN`), raises `CmdAbort`, and `PROCESS_CMD`'s tail or the transfer
routine goes idle ([tspico-bus.md](../firmware/tspico-bus.md)).

Beware: v1.7 reported J here after laundering A = 02h through ERR_9, and
left the Pico mid-transaction with no word sent
([BREAK_AND_ABORT.md](../../rom-analysis/BREAK_AND_ABORT.md)). A RAM program
that calls the BIOS gets `BIOS_WF_NPH`'s carry-and-code instead, never this
report.

## `BRK_TEST` (2327h)

Carry clear = CAPS SHIFT and SPACE both held. Reads the keyboard port
directly, so it works with interrupts off, and makes no debounce.

1. `BIT 6,(IY+7Dh) / SCF / RET NZ`: (IY+7Dh) is 5CB7h, the high byte of
   ERRLN. Bit 6 set means BREAK is inhibited: return carry set (no BREAK).
2. `LD A,7Fh / IN A,(0FEh) / RRA / RET C`: row 7FFEh, bit 0 = SPACE; up
   means carry set.
3. `LD A,0FEh / IN A,(0FEh) / RRA / RET`: row FEFEh, bit 0 = CAPS SHIFT;
   carry = its state.

Clobbers A and F only. The inhibit test copies v1.7's 22F0h
(`BIT 6,(IY+7Dh) / JR Z / SCF / RET`, then the SPACE read), so the new checks
obey the same flag the old ones did. The source calls that bit the
break-inhibit flag; [ERROR_TRAPPING.md](../../rom-analysis/ERROR_TRAPPING.md)
describes the same bit as the `ON ERR` handler's "an error was taken" mark,
set at HOME 0E9Bh and never cleared by the handler. The code tests the bit
whatever it is called; the consequence is that after an `ON ERR` trap has
fired, BREAK is not seen by this routine until the program re-arms
`ON ERR GO TO` (inferred from the two descriptions; not checked on hardware).

## `STEP` (2339h)

Replaces `INC IX / DEC DE` in the SAVE loop (18FDh) and the LOAD loop
(19EFh), and tests BREAK every 256 bytes.

1. `INC IX / DEC DE`: the pointer and the count, as before.
2. `LD A,E / OR A / RET NZ`: only when the low byte of the count reaches 0.
3. `CALL BRK_TEST / RET C`: not held: carry on.
4. `JP BRK_ABORT`.

Clobbers A and F only. Both loops do `LD A,D / OR E / JR NZ` straight after
the call, so they recompute A and F themselves. H holds the running XOR and
is untouched. The `CALL`/`RET` costs 52 T per byte where the two replaced
instructions cost 16, about 10 µs more at 3.5 MHz by instruction count;
whether the ~43 µs SAVE cadence in PROTOCOL.md §3.3 was measured with or
without it is not recorded (unverified).

Beware: the loops run under DI, which is why `BRK_TEST` reads the port
itself rather than relying on the interrupt-driven KSTATE. Between tests
up to 255 more bytes go out or come in; the abort then lands mid-block, and
the SYNC in `BRK_ABORT` is what puts the Pico back.

## `KEYWAIT` (2346h)

A BREAK test in front of `POLL_KEYPRESS`, with the same Z contract.

1. `CALL BRK_TEST / JP NC,BRK_ABORT`.
2. `JP POLL_KEYPRESS`: Z = no key yet.

Called from 0479h inside `GET_KEY_AND_SEND`, which response functions 82h,
84h and 86h use to wait for a key (`CALL KEYWAIT / JR Z,0479h /
JP SEND_KEY`). Before 2.0 a user at a "Scroll?" or "(Y/N)" prompt could not
BREAK out; now the abort byte is sent, the Pico's key wait raises `CmdAbort`,
and Report D follows.

## `RD_STATUS` (234Fh)

`WAIT_PICO_READY`'s status read, with the RECOVERED test.

1. `CALL READ_STATUS`: v1.7's `CHECK_BREAK`, `JP NC,06AAh` (now
   `BRK_ABORT`), then `IN A,(0Fh)`.
2. `BIT ST_READY,A / RET Z`: not ready: back to the poll.
3. `BIT ST_RECOVERED,A / RET NZ`: ready and bit 2 high: ready.
4. `RST 8 / DB ERR_T_PICO`: ready with bit 2 low.

Returns A = the status byte, flags from the `BIT`. `WAIT_PICO_READY` (1A54h)
is `PUSH AF / PUSH BC / LD B,0E2h / CALL RD_STATUS / BIT 6,A / JR NZ,ok /
DJNZ`, so the T report comes from inside every ready-wait the ROM's own code
makes: the SAVE and LOAD block paths and `PICO_TRANSACT` (2279h). The Pico sets
FBh (`MQ_TO_IDLE(recovered=True)`) when a pre-header stops short or is
unrecognised ([tspico-dispatch.md](../firmware/tspico-dispatch.md)); the next
SYNC clears it. Before 2.0 that case waited the full ~19.9 s for J.

Beware: the test order matters. Busy (00h) has bit 2 clear too, so testing
RECOVERED before READY would raise T on every poll.

## `EX_REPORT_MSG` (235Ah)

Prints a report's text and the ", " that follows it, for HOME's report
printer. Entered from HOME 0F12h through `HOME_TO_EX` with A = ERR_NR+1 (B
in HOME's printer).

1. `CP ERR_T_PICO+1 / JR Z,.pico`: 1Dh is the new report.
2. Otherwise `LD DE,HOME_MSG_TABLE / CALL EX_PO_MSG`: HOME's PO-MSG prints
   entry A of the table, as v1.7 did with `CALL 073Fh`; then `JR .sep`.
3. `.pico`: `LD HL,MSG_PICO_RESET`; `.chr`: `LD A,(HL) / AND 7Fh / PUSH HL /
   CALL EX_HOME_PRINT / POP HL / BIT 7,(HL) / INC HL / JR Z,.chr`: one
   character at a time through HOME's RST 10, until the byte with bit 7 set.
4. `.sep`: `XOR A / LD DE,HOME_MSG_SEP / JP EX_PO_MSG`: entry 0 of the
   separator table is ", ".

Why entry A and entry 0: both HOME tables start with a dummy entry, so the
index is ERR_NR+1 for the report table and 0 for the one-entry separator
table. The routine ends with a `JP`, so PO-MSG's `RET` goes back through the
thunk to 0F1Ch in HOME, where the printer continues with the line number.
HOME still computes the letter itself, and prints 1Ch as "T".

## `EX_HOME_PRINT` (237Dh)

Prints A through HOME's RST 10.

`PUSH IX / EXX / LD HL,HOME_RST10 / JP EX_TO_HOME`: the `CALL_HOME`
convention. The thunk at 03DDh pushes a frame, switches banks, calls HL, and
on return pops IX; that is why the caller pushes IX first and uses the
alternate HL for the target. A, F, BC and DE reach HOME's routine; the
current channel is whatever the report printer left selected.

## `MSG_PICO_RESET` (2386h)

`db "TS-Pico reset, try agai", "n" | 80h`: 24 bytes, the last with bit 7
set, which `EX_REPORT_MSG.chr` uses as the terminator. The listing
disassembles the text as instructions. The host test checks the text and
the bit.

## `BIOS_WF_NPH` (239Eh)

`WAIT_PICO_READY` for machine-code callers of the Pico Interface BIOS
(entry 184Ch): the same ~19.9 s budget and the same debounced BREAK test as
v1.7, but it never raises a report.

1. `PUSH AF / PUSH BC / LD B,0E2h`: 226 polls.
2. `.poll`: `CALL CHECK_BREAK / JR NC,.brk`.
3. `IN A,(PORT_STATUS) / BIT ST_READY,A / JR NZ,.ready / DJNZ .poll`.
4. Timeout: `LD C,02h / JR .fail`.
5. `.ready`: `BIT ST_RECOVERED,A / LD C,ERR_T_PICO / JR Z,.fail`: ready with
   bit 2 low is the T case. Otherwise `POP BC / POP AF / SCF / CCF / RET`: carry
   clear, A and BC as on entry.
6. `.brk`: `LD A,ABORT_BYTE / OUT (PORT_STATUS),A / CALL SYNC_WAIT /
   LD C,ERR_D_BREAK`: the Pico is told, as `BRK_ABORT` tells it, and is idle
   when this returns.
7. `.fail`: `LD A,C / POP BC / INC SP / INC SP / SCF / RET`: the two `INC SP`
   drop the saved AF without disturbing A.

Returns carry clear when ready (A, BC preserved); carry set with A = 02h on
a timeout (v1.7's code), 0Ch on BREAK, 1Ch on RECOVERED; BC preserved in
every case. DE, HL, IX untouched. Each poll costs ~88 ms *(inferred: 19.9 s / 226)*
because `CHECK_BREAK` runs ten debounced keyboard scans, which is where the 19.9 s
comes from and why the ROM 2.1 channel driver never uses this for byte-level
I/O ([FDD_COMMANDS_DESIGN.md §6.2](../../FDD_COMMANDS_DESIGN.md)). The
contract is documented in [PROTOCOL.md §9](../../PROTOCOL.md) and the
programmer's manual ch 8. 0Ch and 1Ch can never be confused with a status−1
value from `C_END`, because the firmware's highest status is 11.

Beware: the ROM's own `WAIT_PICO_READY` at 1A54h is not this routine. It
still raises D and T from inside (`RD_STATUS`), which is what the ROM's
commands want and a RAM program does not. The host test checks that 2279h
still calls 1A54h and that this routine contains no `RST 8`.

## `BIOS_C_END` (23CDh)

C_END for the BIOS (entry 184Ah → 184Fh), with the BIOS wait.

`CALL BIOS_WF_NPH / RET C / JP C_END_TAIL`: on failure the carry and code
come from `BIOS_WF_NPH`; otherwise v1.7's tail at 227Fh runs unchanged: read
the status, `AND A` (00h is ERR_9: A = 09h), `DEC A`, `RET Z` for status 1,
else the function chain, then carry set with A = status−1.

The flaw: a timeout comes back as A = 02h, which is also status 3 (Report F),
so a caller could not tell a silent Pico from a bad file name. ROM 2.1's
`C_END2` fixes it by returning 09h (J) for the timeout; the 2.1 table entry
at 184Fh jumps there, and no `CALL` or `JP` in the 2.1 listing targets
23CDh, so this routine is dead in 2.1 though its bytes remain
(`build-rom.py` checks them as an anchor). [rom_cend_hosttest.py](../../../src/test/rom_cend_hosttest.py)
runs both for contrast.

## `NEW_CODE_END` (23D4h)

The first byte after the new code; `ASSERT NEW_CODE_END < 4000h`. The host
test derives the end of the new code from the last byte that differs from
v1.7 and checks the whole range was FFh. ROM 2.1's module starts at 3000h,
leaving 23D4h–2FFFh free.
