# EXROM 1800h–1BFFh: the Pico driver

Source: [`tspico-21-exrom.labelled.asm`](../../rom-analysis/disasm/tspico-21-exrom.labelled.asm),
EXROM 1800h–1C8Fh and the chunk-0 routines the driver stands on (0000h–
0060h, 00F8h, 03DDh, 0655h–06B0h, 0F99h); names from
[`docs/rom-analysis/tspico-exrom-symbols.sym`](../../rom-analysis/tspico-exrom-symbols.sym).
ROM 2.1. Every routine was read in the listing; the bytes of the 1.x
versions are in [DIFF_EXROM_vs_STOCK.md](../../rom-analysis/DIFF_EXROM_vs_STOCK.md).

The genuine 2068 EXROM had a 1K hole at 1800h–1BFFh. Gustavo Pane put the
core of the Pico driver there: the BIOS table that machine code calls, the
two tape routines' replacements (SAVE at 1879h, LOAD at 196Dh), the
ready-wait every exchange uses, the routine that decides whether a
`SAVE`/`LOAD` name is a `tpi:` command and sends it, and the status →
report translation. This chapter follows that region in address order,
after the handful of chunk-0 primitives it calls. The function chain, the
accessors at 2298h/229Dh, the command-body sender and the printer path are
in [exrom-chunk1.md](exrom-chunk1.md); ROM 2.0's SYNC and BREAK code, which
the driver now calls at every transaction, is [exrom-sync.md](exrom-sync.md);
the firmware on the other end is [../firmware/](../firmware/), and the wire
format [PROTOCOL.md](../../PROTOCOL.md).

Conventions used below. **A = status − 1**: the ROM reads a status byte,
tests it for 0 (`AND A`), and decrements it before deciding, so most
comparisons and the report table work on status − 1. **The running XOR**:
the pre-header's checksum is kept in L, a data block's in H, a command's in
D. **Carry** is the error flag of almost every routine here: set =
failed, with A saying why.

## Map

| EXROM | Symbol / what | Since |
|---|---|---|
| 0000h, 0049h | reset entry; `BOOT_MAP_16K` | 1.1 (one byte) |
| 00F8h | `RPT_D_BREAK_CONT` | genuine |
| 03DDh | `CALL_HOME`, the EXROM→HOME returning thunk | 1.1 |
| 0655h | `READ_STATUS` | 1.1 |
| 069Fh | `CHECK_BREAK` | 1.1 |
| 06AAh | `BREAK_ABORT` | 1.1; 2.0 |
| 0F99h | `BANK_SWITCH` (CALL_B) | genuine |
| 1800h–183Bh | the tail of the printer path (COPY-LINE's loop, the UDG sender, 1828h) | 1.1; [exrom-chunk1.md](exrom-chunk1.md) |
| 183Ch–183Fh | `FFh` | |
| 1840h | `BIOS_TABLE` | 1.1; 2.0, 2.1 |
| 1852h | `BIOS_G_VERS` | 1.1 |
| 1856h–1871h | G_MODE, S_MODE, RX_A, TX_A bodies | 1.1 |
| 1872h–1935h | the SAVE path (SA-BYTES via 0068h) | 1.1; 2.0 |
| 1936h–196Ch | the byte senders with XOR | 1.1 |
| 196Dh–1A38h | the LOAD path (LD-BYTES via 00FCh) | 1.1; 2.0 |
| 1A39h–1A53h | `SESSION_SETUP`'s exits; LOAD to tape | 1.1 |
| 1A54h | `WAIT_PICO_READY`, `WAIT_PICO_READY_FAIL` (1A61h), `WAIT_PICO_READY_OK` (1A6Eh) | 1.1; 2.0 |
| 1A73h | `SESSION_SETUP` (SESSION_NAMED at 1AACh) | 1.1 |
| 1B6Bh | end-of-statement test | 1.1 |
| 1B7Eh | `SEND_BYTE_CRC` | 1.1 |
| 1B8Dh–1B9Fh | a command: the name fetched | 1.1 |
| 1BA0h | `BUILD_PREHEADER_B` | 1.1; 2.0 |
| 1BEEh | a no-op remnant | 1.1 |
| 1BF3h | `STATUS_TO_REPORT` and the report targets (1C16h–1C3Fh) | 1.1 |
| 1C23h | `STATUS_OK` | 1.1 |
| 1C40h | `SEND_KEY` | 1.1 |
| 1C49h–1C8Fh | the boot message | 1.1; 2.0, 2.1 |

The listing also shows names at some of these addresses from the 2.0 and
2.1 sources (`C_END_VEC`, `BIOS_WF_NPH`, `F_HOOK_VEC`, `SYNC_WRITE`,
`STEP`, `RD_STATUS`, and `H_EXPT_STR` at 1BEFh, which is a HOME address
the label file wrongly applies here); those belong to
[exrom-sync.md](exrom-sync.md) and [exrom-fdd.md](exrom-fdd.md).

## The chunk-0 primitives

### `BOOT_MAP_16K` (0049h)

The EXROM's reset entry is `DI` at 0000h then `JR 0049h`. At 0049h the
genuine ROM had `LD A,01h / OUT (F4h),A`: the HSR selecting chunk 0 only.
The TS-Pico changed the 01h to 03h — chunks 0 and 1, the 16K EXROM — then,
as before, `JR 005Ah` → `JP 1CAEh`, the rest of the boot. It is the EXROM
twin of HOME's 0E0Ch change ([home.md](home.md#0e0ch-a-16k-exrom)): both
boot paths must page both chunks, or the first `CALL` from chunk 0 into
chunk 1 lands in the DOCK.

### `CALL_HOME` (03DDh)

The EXROM → HOME thunk that returns:

```text
caller:  PUSH IX / EXX / LD HL,home_target / JP 03DDh
03DDh    PUSH HL               ; the target
         LD HL,FF00h / PUSH HL ; bank FFh (HOME), every chunk
         LD H,0 / PUSH HL / PUSH HL
         EXX                   ; the caller's registers back
         CALL BANK_SWITCH      ; 0F99h
         POP IX                ; the caller's IX
         RET
```

The genuine EXROM repeated a 21-byte inline sequence at every call into
HOME; v1.1 factored 17 of them down to a 9-byte preamble jumping here,
which with the 1K hole is how chunk 0 found room for the driver
([SYMBOLS.md](../../rom-analysis/SYMBOLS.md#cross-rom-machinery) lists the
sites and their HOME targets; 11 genuine inline copies remain). The caller
pushes IX because the RAM bank code uses it; the main registers travel
through the `EXX` pair as in HOME's 3CE3h. Every "call HOME routine X"
in the TS-Pico EXROM — the expression evaluator, PO-MSG, MAKE-ROOM,
CHAN-OPEN — goes through it. 08DDh is the no-return twin (genuine bytes,
reused). `build-rom.py` checks these 16 bytes as an anchor.

### `BANK_SWITCH` (0F99h)

The genuine CALL_B: `PUSH AF / LD A,(5CC2h) / AND A / JR Z / POP AF /
JP FD90h` (64-column video) or `POP AF / JP 65D0h` — the RAM copy of the
2068's CALL_BANK. Touches no ports itself. 0F8Ah is the no-return
GOTO_B (to FD32h/6572h). HOME keeps a byte-for-byte copy at 040Dh
([home.md](home.md#03fch-into-the-exrom-and-back-v11)).

### `READ_STATUS` (0655h)

```text
0655h   CALL CHECK_BREAK
        JP NC,BREAK_ABORT     ; BREAK held: abandon the transaction
        IN A,(0Fh)
        RET
```

Every ready-wait reads the Pico's status through here — there is no bare
`IN A,(0Fh)` in 1.x code — so every wait is also a BREAK check. Returns A =
the status byte (READY is bit 6; ROM 2.0 adds IDLE bit 3 and RECOVERED bit
2, [PROTOCOL.md §3](../../PROTOCOL.md#3-the-status-byte)). ROM 2.0 wraps
it in RD_STATUS (234Fh) for the RECOVERED test.

Beware the name: `src/rom/fdd/fddcmd.asm` has an `EQU` called READ_STATUS
that is **02B9h**, the routine this reference calls `READ_STATUS_BYTE`
(the response function's own status, [exrom-chunk1.md](exrom-chunk1.md)),
not this one. `tspico-sync.asm`'s READ_STATUS is this one (0655h).

### `CHECK_BREAK` (069Fh)

`CALL 0856h` (ten passes of the keyboard scan at 07F6h, a debounce) /
`RRA` / `RET C` (no SPACE: carry set) / `LD A,FEh` / `IN A,(FEh)` / `RRA`
/ `RET`: carry clear only when SPACE and CAPS SHIFT are both down — BREAK.
The ten scans are what make each status poll cost about 88 ms, and so
what turns the ready-wait's 226 polls into ~19.9 s
([`tools/wf_nph_timing.py`](../../../tools/wf_nph_timing.py);
[PROTOCOL_FROM_ROM.md](../../rom-analysis/PROTOCOL_FROM_ROM.md#the-timeout-is-20-seconds-and-this-is-the-most-misread-number-in-the-rom)).
It also means the Z80 looks at port 0Fh only about eleven times a second
while it waits, and every wait takes at least one poll, ~88 ms, even when
the Pico is already READY.

### `BREAK_ABORT` (06AAh)

Where `READ_STATUS` goes on BREAK. In 1.x: `POP BC / JP 1A61h` — out
through WAIT_PICO_READY's failure exit, so a BREAK during a wait became
Report J after the caller's cleanup, and the Pico was never told. ROM 2.0:
`JP BRK_ABORT` (2320h) and four `NOP`s: the abort byte 03h is written to
port 0Fh, the Pico cleans up, and Report D follows
([exrom-sync.md](exrom-sync.md),
[BREAK_AND_ABORT.md](../../rom-analysis/BREAK_AND_ABORT.md)).

### `RPT_D_BREAK_CONT` (00F8h)

`RST 8 / DEFB 0Ch`: "D BREAK - CONT repeats", genuine code in the EXROM's
tape routines. `STATUS_TO_REPORT` jumps here for any status of 11 or more.

## The Pico Interface BIOS

### `BIOS_TABLE` (1840h)

A table of 2- and 3-byte jumps at a fixed address, for machine code that
talks to the Pico without knowing where the routines are. No EXROM code
calls through it; it is the interface for programs in RAM, which call it
with the EXROM paged ([PROTOCOL.md §9](../../PROTOCOL.md#9-the-pico-interface-bios-exrom-1840);
the programmer's manual's chapter 8 is the tutorial).

| Entry | Name | Jumps to | Contract |
|---|---|---|---|
| 1840h | G_MODE | 1856h | BC = TPMODE AND 0Fh; AF kept |
| 1842h | S_MODE | 1862h | TPMODE = A AND 0Fh; AF kept |
| 1844h | G_VERS | 1852h | BC = the ROM version: 0021h in 2.1 |
| 1846h | TX_A | 186Dh → 229Dh | `OUT (0Eh),A`, carry clear |
| 1848h | RX_A | 186Ah → 2298h | `IN A,(0Eh)`, carry clear |
| 184Ah | C_END | 184Fh → C_END_VEC (301Bh) | the end of a command: wait for READY, read the status, run any response function. NC = status 1; C with A = status − 1, or 09h for a timeout (2.1), 0Ch BREAK, 1Ch the Pico dropped it |
| 184Ch | WF_NPH | BIOS_WF_NPH (239Eh) | wait for READY: NC ready; C with A = 02h timeout, 0Ch BREAK, 1Ch reset |

TPMODE's bits are in [sysvars.md](sysvars.md#5ddbh-tpmode-peek-24027). The
entries are `JR`s except the last two, which are `JP`s placed so that
184Ch and 184Fh are each three bytes. What changed: in v1.1–v1.7, WF_NPH
jumped to WAIT_PICO_READY (1A54h) and C_END to 2279h, both of which raise
reports from inside — a RAM program lost control on a BREAK or a Pico
reset. ROM 2.0 pointed both at new code that returns carry with a reason
instead ([exrom-sync.md](exrom-sync.md#bios_wf_nph-239eh)); ROM 2.1 points
C_END at C_END2, which reports a timeout as 09h (J) because 2.0's 02h was
also status 3 (Report F) ([exrom-fdd.md](exrom-fdd.md)). The bytes at
1840h–1855h, by version: identical `JR`s throughout; 184Ch `JP 1A54h` and
184Fh `JP 2279h` in v1.1–v1.7, `JP 239Eh` / `JP 23CDh` in 2.0, `JP 239Eh` /
`JP 301Bh` in 2.1. 184Eh is the last byte of 184Ch's `JP`, not an entry:
[SYMBOLS.md](../../rom-analysis/SYMBOLS.md) lists an "EWAIT" there, which
does not exist ([PROTOCOL_FROM_ROM.md](../../rom-analysis/PROTOCOL_FROM_ROM.md#the-real-api-table-tpi-bios-at-0x1840)
has it right).

### `BIOS_G_VERS` (1852h)

`LD BC,0021h / RET`: the version, matching HOME 0065h (`PEEK 101`). 0015h
in v1.1 and v1.5w (which it cannot tell apart), 0017h in v1.7, 0020h in 2.0, 0021h in 2.1; each release patches it with 0065h
([overview.md](overview.md#which-rom-is-this)). The `RET` at 1855h is also
used as a landing point: HOME's helpers 255Bh and 3CDCh jump into the EXROM
at 1855h so that the `RET` returns to their EXROM caller with the EXROM
paged ([home.md](home.md#2548h2560h-save-load-verify-merge-v11)).

The other bodies: G_MODE (1856h) `PUSH AF / LD A,(5DDBh) / AND 0Fh / LD B,0
/ LD C,A / POP AF / RET`; 1861h `XOR A` falls into S_MODE (1862h) `PUSH AF
/ AND 0Fh / LD (5DDBh),A / POP AF / RET` — 1861h, "TPMODE = 0", is what
`tpi:tape` calls, and 081Dh (`LD A,2 / JP 1862h`) is the power-on value;
RX_A and TX_A are `JP`s to the accessors. 1870h–1871h (`AND A / RET`)
follow TX_A unreferenced.

## SAVE (1879h)

The EXROM's SA-BYTES entry (0068h) is `JP 1879h`. Entered with A = the
flag byte (00h header, FFh data), IX = the start, DE = the length, as the
stock routine.

1. **Tape or Pico?** `PUSH AF`; TPMODE bit 1 clear (`tpi:tape`) → 1872h:
   `POP AF / LD HL,00E5h / JP 006Bh`, the stock SA-BYTES body. Otherwise:
2. `POP AF`, push 00E5h (the stock SA/LD-RETURN, which the routine returns
   through, restoring the border and the interrupts), `PUSH AF`, `DI`, L =
   the flag. C is set to a phase number: 1 for a header, 3 for a data
   block, 9 for any other flag.
3. **A data block (FFh) has no pre-header**: straight to step 6. A header or
   other block:
4. **The pre-header** (189Ah–18BEh), ten bytes, L the running XOR:
   SYNC_WRITE sends the flag (2.0: preceded by the SYNC, `OUT (0Fh),03h`,
   and a wait for READY + IDLE, [exrom-sync.md](exrom-sync.md#sync_write-2300h));
   then T_ADDR (0 for SAVE), BANK (5DCFh, always FFh), the session id
   (5DD1h), IX, DE, and L.
5. **The pre-load**: read one byte. Carry or 0: Report J (1C1Fh). Not 1: it
   is the Pico's refusal, status − 1 → `STATUS_TO_REPORT` (1930h): this is
   where an F (no card, a name the Pico will not take) or A arrives before
   any data is sent. Then `WAIT_PICO_READY` (failure: J).
6. **The block** (18D8h–1904h): the flag; the session id (whose bytes go
   into L, not into the block's XOR in H); then, if the flag was not 0, the
   session is ended (5DD1h = 0, 04E8h) — the data block is the last of
   the statement. Then the bytes from IX, H the running XOR, ROM 2.0's
   `STEP` after each (`INC IX / DEC DE`, and a BREAK test every 256 bytes,
   [exrom-sync.md](exrom-sync.md#step-2339h)); then H.
7. **The status**: `WAIT_PICO_READY` (J on failure), read (carry or 0: J),
   `DEC A`; not OK → the function chain (`FN_CHAIN_HEAD`,
   [exrom-chunk1.md](exrom-chunk1.md)), which runs a response function or
   comes back with the status; `EI`; still not OK → `STATUS_TO_REPORT`.
   OK: carry set (SA-BYTES's "saved") and `RET` through 00E5h.

For a header this status is the **mid-phase** status of
[PROTOCOL.md §6.2](../../PROTOCOL.md#62-save): the firmware's last chance
to refuse the SAVE (03h F, 08h A) before the data is sent. The stock code
between header and data block then pauses about a second (`HALT`s), and
calls 1879h again with the flag FFh. Every byte goes out with no ready-wait
between bytes: the Pico's capture keeps up (~43 µs a byte;
[../firmware/tspico_io.md](../firmware/tspico_io.md#save_tsmq-tsp-prenone)).
Interrupts are off from step 2 to the final `EI`.

The phase number in C goes up at each step (`INC C` at 18C3h, 18D1h,
190Ah) and is never read by anything in the driver or its report targets
*(inferred: a diagnostic left from development)*.

### The byte senders (1924h–196Ch)

Small helpers the SAVE and LOAD paths share. Each sends a byte with
`TSPICO_WRITE_DATA` and folds it into L with `XOR L / LD L,A` (1956h); on a
write failure (carry, which the accessor never returns, so this is dead
in practice *(inferred)*) they unwind to `STATUS_TO_REPORT` through
192Dh–1930h, which pop one, two or three levels first.

| EXROM | Sends |
|---|---|
| 1924h | H (the block XOR: LOAD's echoes), C bumped and restored |
| 1936h | E then D, into L |
| 1947h | E then D, into L (another unwind depth) |
| 1951h | A, into L |
| 1959h | E then D, into L (another unwind depth) |
| 1963h | A, into L (another unwind depth) |

1930h: `POP HL / AND A / RET Z / JP STATUS_TO_REPORT`.

## LOAD (196Dh)

The EXROM's LD-BYTES entry (00FCh) is `JP 196Dh`. Entered with A = the
expected flag, carry set for LOAD and clear for VERIFY, IX = the
destination, DE = the length.

1. **Tape or Pico?** TPMODE bit 1 clear → 1A4Dh: `POP AF / INC D / EX
   AF,AF' / DEC D / JP 00FFh`, the stock LD-BYTES's opening and body.
2. Push 00E5h, `DI`, keep the flags in AF' (with bit 6, Z, cleared), L =
   the flag. C: 5 for a header, 7 for data, 0Ah for any other flag.
3. **The pre-header**: SYNC_WRITE with the flag, then T_ADDR (1 LOAD, 2
   VERIFY, 3 MERGE), BANK, the session id — ended here (5DD1h = 0) when
   the flag is FFh, the data block — IX, DE, L.
4. **The pre-load**: carry or 0 → J; not 1 → **Report R** (1A35h). Then
   `WAIT_PICO_READY`.
5. **Echo 1**: H (= the flag) is sent (19DAh, 1924h) **before** the data,
   which older documents put after the loop.
6. **The block**, read blind (19DDh–19F4h): each byte read with no
   ready-wait (the Pico streams it, ~47 µs a byte, by DMA where it can,
   [../firmware/tspico_io.md](../firmware/tspico_io.md#load_tspre-mq-tsp)),
   folded into H. The first byte is the flag, compared as the stock
   LD-BYTES does (1A20h: a mismatch returns at once, carry clear: the stock
   caller's Report R, or for a header the search goes on). Then each byte is
   stored at IX (LOAD) or compared with it (VERIFY, 1A2Dh: a difference
   returns, carry clear). `STEP` after each.
7. **The checksum**: one more byte, XORed with H. Not 0 → 0815h: H is sent
   as echo 2 (the Pico sees the mismatch), `AND A` clears carry, `EI`,
   `RET`: Report R from the stock code.
8. **Echo 2**: H (now 0) via 1924h; `WAIT_PICO_READY`; the final status
   (carry or 0 → J); not 1 → `FN_CHAIN_HEAD`; carry set if OK, clear
   otherwise; `EI`; `RET`.

The checksum covers the flag and the data, not the session bytes, so a
block converts to a TAP block unchanged. A header that is not the one
wanted (another name) is handled by the stock caller, which calls 196Dh
again: each call is a new transaction with its own pre-header, and the
Pico serves the next block of the mounted tape
([../firmware/tspico_io.md](../firmware/tspico_io.md),
[../flows/load.md](../flows/load.md)).

## Waiting for the Pico

### `WAIT_PICO_READY` (1A54h)

The ready-wait every exchange the ROM makes uses: after the pre-load, after
a block, before a key is sent, at the end of a command (PICO_TRANSACT,
2279h).

```text
1A54h   PUSH AF / PUSH BC
        LD B,E2h              ; 226 polls
1A58h   CALL RD_STATUS        ; 2.0: READ_STATUS + the RECOVERED test
        BIT 6,A               ; READY?
        JR NZ,WAIT_PICO_READY_OK
        DJNZ 1A58h
```

Returns carry clear when READY, A and BC as they were; carry set with A =
02h after 226 polls. **226 polls take about 19.9 s**, not 226 × a few
microseconds: each poll goes through `CHECK_BREAK`'s ten debounced keyboard
scans, ~88 ms. That is the budget every Pico operation must fit inside
(an SD mount, a folder listing) before the 2068 gives up with J, and why
the firmware keeps the Z80 in a ready-wait, never in a blind read, while it
does slow work ([../firmware/tspico-bus.md](../firmware/tspico-bus.md)).

It does not always return. A BREAK during the wait goes to `BREAK_ABORT`
(Report D in 2.0), and since 2.0 a READY with RECOVERED low raises Report T
from inside RD_STATUS (234Fh, [exrom-sync.md](exrom-sync.md#rd_status-234fh)).
In v1.1–v1.7 the status read was `CALL READ_STATUS` at 1A58h.

#### `WAIT_PICO_READY_FAIL` (1A61h)

`LD A,40h` followed by five `NOP`s, then `POP BC / POP AF / LD A,02h /
SCF / RET`. The `LD A,40h` is overwritten at once: a remnant of a removed
patch (the 40h is the single-port firmware's "ready" byte), dead. Every
internal caller turns the carry into Report J and discards the 02h; only
machine code calling the BIOS saw it, and since 2.0 the BIOS has its own
wait.

#### `WAIT_PICO_READY_OK` (1A6Eh)

`POP BC / POP AF / SCF / CCF / RET`: carry clear, A as on entry.

## `SESSION_SETUP` (1A73h): is this name a command?

Reached from SAVE-ETC (01D2h: in 2.1 by way of F_HOOK, which first takes
`f:` names, [exrom-fdd.md](exrom-fdd.md)) on **both** the syntax pass and
the run-time pass of every `SAVE`, `LOAD`, `VERIFY` and `MERGE`, with the
name's string on the calculator stack. It decides: a `tpi:` command (sent
from here, and the statement ends), or an ordinary name (back to the stock
SAVE-ETC).

1. **The session id**: `FRAMES` + 1, incremented again while it is 0 →
   5DD1h. Not random: it is the frame counter, never 0, so 0 can mean "not
   from a BASIC statement" ([sysvars.md](sysvars.md#5dd1h-session-id)).
2. The name's length BC and address DE, read from the top of the
   calculator stack (STKEND − 4). **The gate**: a length of 256 or more, an
   operation other than SAVE or LOAD (T_ADDR ≥ 2: VERIFY, MERGE), or a
   length outside 5–31, is an ordinary name → 1A45h. A length of 32–255 is
   different: in the syntax pass it is accepted (STATUS_OK), at run time
   it is Report C (1C2Fh) *(the second length test at 1AA1h, `CP 20h`, can
   never succeed after the first; inferred dead)*.
3. **SESSION_NAMED (1AACh)** — where ROM 2.1's module enters to send its
   own commands of up to 64 characters past the gate: 5DD3h = the address,
   5DD5h = the length. The first three characters, upper-cased with
   `AND 5Fh`: `TPI` → TPMODE bit 7 set, bit 6 cleared; `NET` → bits 7 and 6
   set; anything else → 1A3Ah. The fourth must be `:` and the length at
   least 6, else 1A3Ah.
4. **LOAD "tpi:…"** (T_ADDR ≠ 0) → 210Eh → 1B8Dh: sent as a command with
   TADDR 1, the mount request ([../firmware/tspico-files.md](../firmware/tspico-files.md#load_tpiname-only_tapfalse-freshfalse)).
5. **SAVE "tpi:…"**: PMR1 and PMR2 (5DD7h, 5DD9h) cleared; the next
   character fetched (through HOME). `CODE` (AFh): evaluate a number into
   PMR1, demand a comma (else 1C27h: Report C), evaluate the second into
   PMR2. Then the statement must end (1B6Bh: CR or `:`); if it does not, →
   1A39h, the ordinary-name exit *(so `SAVE "tpi:x" LINE 1` saves a
   program named "tpi:x" by the normal route; inferred from the code, not
   tried)*.
6. **Syntax pass** (FLAGS bit 7 clear, `IY+1`): STATUS_OK — the statement
   is accepted and nothing is sent.
7. **Run time**: `tpi:tape`, `tpi:sdcard`, `tpi:picopt`, `tpi:ts2040` are
   handled here and never sent (208Eh–2191h,
   [sysvars.md](sysvars.md#5ddbh-tpmode-peek-24027)); anything else →
   1B8Dh.

The exits:

| EXROM | What |
|---|---|
| 1A39h | `POP HL`, then: |
| 1A3Ah | TPMODE AND 0Fh (the prefix bits cleared) |
| 1A45h | `POP DE / POP HL / LD BC,0011h / JP 01D5h`: back to the stock SAVE-ETC (SAVE_ETC_BODY) with BC = 17, the header's length. F_HOOK copies these bytes (anchor) |
| 1A4Dh | LOAD to tape (above) |

### 1B6Bh

`CP 0Dh / RET Z / CP 3Ah / RET`: Z at the end of a statement.

### 1B8Dh–1B9Fh: fetching the command

TPMODE's bits 7 and 6 cleared; `CALL 042Fh` (→ HOME STK-FETCH through
CALL_HOME: DE = the text, BC = its length); a length of 0 → Report R
(1B88h). Then into `BUILD_PREHEADER_B`.

### `SEND_BYTE_CRC` (1B7Eh)

`CALL TSPICO_WRITE_DATA / XOR D / LD D,A / RET`: send A and fold it into
D, a command's running XOR. 1B76h is a variant that jumps to Report J on a
carry. Used by `BUILD_PREHEADER_B` and SEND_DATA_BLOCK_D.

### `BUILD_PREHEADER_B` (1BA0h)

A `tpi:` command's pre-header, then its body, then the answer.

```text
1BA0h   LD (5DCDh),BC          ; the text's length
        LD B,C / LD C,0Dh
        LD A,'B' / LD D,A      ; D = the XOR, seeded with the first byte
1BAAh   CALL SYNC_WRITE        ; 2.0: SYNC, wait READY+IDLE, then OUT 'B'
        T_ADDR    (0 SAVE, 1 LOAD: the mount)
        BANK      (5DCDh's neighbour 5DCFh: FFh)
        PMR1 lo, hi
        PMR2 lo, hi
        length lo (B), length hi (5DCEh)
        D          (the XOR)
1BE1h   LD HL,(5DD3h)          ; the text
        CALL SEND_DATA_BLOCK_D
```

The ten bytes are [PROTOCOL.md §4.3](../../PROTOCOL.md#43-the-pre-header-and-the-dispatcher)'s
`'B'` layout; the Pico does not check this XOR for commands. SEND_DATA_BLOCK_D
(223Eh, [exrom-chunk1.md](exrom-chunk1.md)) reads the pre-load (must be 1),
waits for READY, sends `'D'`, the length, the text and their XOR, waits,
reads the answer and runs any response function; it returns:

- carry clear, A = 0: OK;
- carry clear, A = status − 1: the pre-load was not 1 (the Pico refused
  the command before its body);
- carry set, A = status − 1: the answer was a report (after any response
  function);
- carry set, A = 09h: no answer, or a timeout (ERR_9).

Then: carry → 1BF1h → `STATUS_TO_REPORT`; A = 0 → `STATUS_OK`; otherwise
`PUSH AF / XOR A / POP AF` (1BEEh, a no-op: the `XOR A` is undone at once —
a remnant), then `STATUS_TO_REPORT`.

So a command ends in one of: "0 OK", the report the Pico chose, J when it
did not answer, D for BREAK, T for a Pico reset. The 1BEFh label in the
listing (`H_EXPT_STR`) is a mis-applied HOME name; the code is this remnant.

## Reports

### `STATUS_TO_REPORT` (1BF3h)

Entered with A = status − 1 (≥ 1). `EI`, then `DEC A` and a jump per
value:

| A | Status | Target | Report |
|---|---|---|---|
| 1 | 2 | `RPT_R_TAPE_ERROR` | R Tape loading error |
| 2 | 3 | `RPT_F_BAD_FILENAME` | F Invalid file name |
| 3 | 4 | `RPT_Q_PARAM_ERROR` | Q Parameter error |
| 4 | 5 | `RPT_C_NONSENSE` | C Nonsense in BASIC |
| 5 | 6 | `RPT_6_NUM_TOO_BIG` | 6 Number too big |
| 6 | 7 | `RPT_8_END_OF_FILE` | 8 End of file |
| 7 | 8 | `RPT_A_INVALID_ARG` | A Invalid argument |
| 8 | 9 | `RPT_9_STOP` | 9 STOP statement |
| 9 | 10 (and the internal ERR_9) | `RPT_J_INVALID_IO` | J Invalid I/O device |
| ≥ 10 | ≥ 11 | `RPT_D_BREAK_CONT` (00F8h) | D BREAK - CONT repeats |

The order is not the order of the targets in memory, and status 8 → A,
status 9 → 9: the chain at 1C0Ah–1C0Eh tests A = 7 for A Invalid argument
and A = 8 for 9 STOP. The firmware's status constants are named for the
report they produce (`_8_A_Invalid_arg` = 8), which is what matters;
[PROTOCOL.md §5.3](../../PROTOCOL.md#53-the-answer-a-status) and
[../firmware/tspico-state.md](../firmware/tspico-state.md#the-status-codes)
have the same table. **Internal error 9** — the ROM's own "no answer"
(ERR_9, A = 09h) — therefore lands on J, not on 9 STOP
([PROTOCOL_FROM_ROM.md](../../rom-analysis/PROTOCOL_FROM_ROM.md#internal-error-9-surfaces-as-report-j-not-report-9)).
Status 0 never gets here: every reader tests `AND A` first and turns 0 into
J. A response function (status ≥ 80h) is run by the function chain before
this point.

The targets (ERR_NR is the byte after `RST 8`, the report's code − 1):

| Symbol | EXROM | Code |
|---|---|---|
| `RPT_6_NUM_TOO_BIG` | 1C16h | `RST 8 / 05h` |
| `RPT_8_END_OF_FILE` | 1C18h | `RST 8 / 07h` |
| `RPT_9_STOP` | 1C1Ah | `RST 8 / 08h` |
| `RPT_A_INVALID_ARG` | 1C1Ch | `RST 8 / 09h` |
| `RPT_J_INVALID_IO` | 1C21h | `RST 8 / 12h`; 1C1Eh–1C20h are three `POP HL`s in front of it, entry points 1C1Fh and 1C20h that drop two or one stack levels first (the SAVE and LOAD paths use them) |
| `RPT_C_NONSENSE` | 1C35h | `EI / JP 08D9h`: through the no-return thunk to HOME 1BEDh, so Report C is raised by HOME, which sets the error marker in the BASIC line |
| `RPT_F_BAD_FILENAME` | 1C39h | `JP 0228h`: `RST 8 / 0Eh` in the genuine tape code |
| `RPT_Q_PARAM_ERROR` | 1C3Ch | `RST 8 / 19h` |
| `RPT_R_TAPE_ERROR` | 1C3Eh | `RST 8 / 1Ah` |

`RST 8` in the EXROM is its own error restart (anchored by `build-rom.py`),
which ends with HOME paged and the stack at ERR_SP, so `ON ERR` traps
these like any report ([ERROR_TRAPPING.md](../../rom-analysis/ERROR_TRAPPING.md)).

### `STATUS_OK` (1C23h)

`POP DE / POP HL / XOR A / RET`: the two words SESSION_SETUP pushed, A = 0,
and back to the statement: "0 OK". 1C27h (five `POP`s, then Report C) is
the `CODE a` with no comma exit; 1C2Fh (FLAGS bit 7: syntax → STATUS_OK,
run time → Report C) the over-long name.

### `SEND_KEY` (1C40h)

`CALL WAIT_PICO_READY / JP C,1B87h / JP TSPICO_WRITE_DATA`: wait for READY,
then send the key in A. GET_KEY_AND_SEND (0471h) tail-calls it for response
functions 82h, 84h and 86h ([exrom-chunk1.md](exrom-chunk1.md)). On a
timeout, 1B87h pops three levels and raises Report R. The key is sent
upper-case (the keyboard routines produce it that way), which is what the
firmware compares against ([../firmware/tspico-messages.md](../firmware/tspico-messages.md#the-answer-on-the-wire)).

## The boot message (1C49h)

The EXROM's boot path reaches here from 03FBh (after EXTINIT has set
TPMODE and BANK, [sysvars.md](sysvars.md)):

1. `LD HL,1C5Dh / LD DE,5B00h / LD BC,0029h / LDIR`: 41 bytes into the
   printer buffer in RAM.
2. `CALL 5B00h`: `XOR A / CALL 5B05h / RET`, and 5B05h is `LD DE,5B0Bh /
   JP EX_PO_MSG` (03EDh, HOME's PO-MSG through the thunk): print message 0
   of the table at 5B0Bh.
3. The table (1C68h): `80h` (the dummy entry), `0Dh 0Dh`, `7Fh` (©), and
   " 2026 TS-Pico ROM v2.1   " with bit 7 set on the last space.
4. `LD HL,5EEAh / JP 1C86h`: the rest of the genuine EXTINIT, displaced
   from 08E7h when that became `JP 01BCh`.

The text is copied to RAM because PO-MSG runs in HOME and reads the table
with HOME paged: a table in the EXROM would be invisible to it. ROM 2.0
rewrote the text (1C70h–1C85h, from "2025 Timex Pico Interface"); 2.1
changed "v2.0" to "v2.1" at 1C7Eh.

## Where comments, documents and the code disagree

Tracked in the [`reference-followup` issues](https://github.com/timex-sinclair-projects/tspico-firmware-build/issues?q=label%3Areference-followup).

- [SYMBOLS.md](../../rom-analysis/SYMBOLS.md) lists an EWAIT entry at
  184Eh (`JP 2279h`); 184Eh is the last byte of 184Ch's `JP`.
- SYMBOLS.md describes `BREAK_ABORT` (06AAh) as `POP BC / JP 1A61h`; that
  is 1.x. ROM 2.0 made it `JP BRK_ABORT`.
- SYMBOLS.md says G_VERS returns 0015h (v1.1).
- The labelled listing names EXROM 1BEFh `H_EXPT_STR`, a HOME routine's
  name from `fddcmd.asm` ([#183](https://github.com/timex-sinclair-projects/tspico-firmware-build/issues/183), R2).
