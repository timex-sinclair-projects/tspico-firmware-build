# The HOME ROM

Source: [`src/rom/TSPICO-21.ROM`](../../../src/rom/TSPICO-21.ROM) bytes
0000h–3FFFh, read in
[`tspico-21-home.asm`](../../rom-analysis/disasm/tspico-21-home.asm); the
genuine HOME ROM [`ROMs/GENUINE-2068-home.bin`](../../../ROMs/GENUINE-2068-home.bin)
and its listing [`genuine-2068-home.asm`](../../rom-analysis/disasm/genuine-2068-home.asm);
the 2.0 HOME site in [`src/rom/patches/tspico-sync.asm`](../../../src/rom/patches/tspico-sync.asm);
the 2.1 HOME patches in [`tools/build-rom.py`](../../../tools/build-rom.py)'s
`PATCHES`.

The TS-Pico's HOME ROM is the genuine TS2068 HOME ROM with hooks. It has no
room of its own, so every hook is short: it hands the work to the EXROM,
where the TS-Pico's code lives, through a thunk. This chapter takes every
place the TS-Pico's HOME differs from the genuine ROM, in address order,
and says what the genuine bytes were, what is there now, what reaches it,
which BASIC statement passes through it and where it leads. The EXROM ends
of these hooks are in [exrom-chunk1.md](exrom-chunk1.md),
[exrom-driver.md](exrom-driver.md), [exrom-sync.md](exrom-sync.md) and
[exrom-fdd.md](exrom-fdd.md); banking in general is
[overview.md](overview.md#banking-how-home-and-the-exrom-reach-each-other).

All differences were measured on the images in the repository (bytes that
differ, with runs closer than five bytes merged into one hunk):

| From → to | Bytes changed | Hunks |
|---|---|---|
| genuine → v1.1 (= v1.5w) | 242 | 10 |
| v1.1 → v1.7 | 1 | 1 (0065h) |
| v1.7 → 2.0 | 14 | 2 (0065h, 0F13h–0F1Fh) |
| 2.0 → 2.1 | 100 | 9 |
| genuine → 2.1 | 346 | 17 |

The older account of the genuine → v1.1 hunks, with the bytes, is
[DIFF_HOME_vs_STOCK.md](../../rom-analysis/DIFF_HOME_vs_STOCK.md); the 2.0
and 2.1 ones are in [ROM_CHANGES.md](../../ROM_CHANGES.md). This chapter
follows the code and links to them for the history.

## Map of HOME

| HOME | Contents |
|---|---|
| 0000h–3CDBh | the genuine ROM, with the hooks below |
| 3CDCh–3CFFh | TS-Pico code in the genuine ROM's `FFh` filler after the "Bytes:" message: the HOME→EXROM thunk |
| 3D00h–3FFFh | the character set, untouched |

What the TS-Pico did **not** change: the character set, the start-up
copyright message, the floating-point code, the keyword tokens, and the
HOME NMI routine at 0066h, whose inherited Spectrum bug (it jumps through
NMIADD only when it is zero) is still there. The EXROM's NMI routine is
the fixed one ([sysvars.md](sysvars.md#5d37h-the-nmi-vector)).

## Every hunk

| HOME | Since | Genuine | Now | What | Statement |
|---|---|---|---|---|---|
| 0065h | 1.1 | `FFh` | the version (21h) | `PEEK 101` | — |
| 03F3h–0420h | 1.1, 2.1 | BEEPER | BEEPER thunk, the returning thunk 03FCh, a CALL_B copy at 040Dh | BEEPER moved to EXROM 203Fh | BEEP, key click |
| 04E8h–0502h | 1.1 | the tail of a syntax routine; SENDTV `CALL 061Ah` | printer helpers; SENDTV `CALL 0A09h` | every printed character passes the TPMODE test | PRINT, LPRINT, LLIST |
| 0A02h–0A2Fh | 1.1 | COPY (K_DUMP) and COPY-BUFF | COPY → EXROM 1630h; the character router 0A09h; COPY-BUFF → EXROM 1636h | COPY and the printer buffer | COPY, LPRINT |
| 0A4Ah–0A81h | 1.1 | COPY-LINE (the ZX Printer loop) | the 0A50h thunk; token expansion | the printer sends text, not dots | LPRINT, LLIST |
| 0E0Ch | 1.1 | `01h` | `03h` | the HSR mask at boot: a 16K EXROM | power-on |
| 0F13h–0F1Fh | 2.0 | print a report's text from HOME's table | hand it to EXROM 235Ah | Report T has text | any report |
| 13A6h–13A7h | 2.1 | `CALL 13BEh` | `CALL 1494h` | CLOSE # through the module | CLOSE # |
| 1439h–143Ah | 2.1 | `CALL 2569h` | `CALL 14BDh` | OPEN # syntax parses `,mode[,reclen]` | OPEN # |
| 145Fh | 2.1 | `CALL 1465h` | `CALL 1488h` | OPEN # through the module | OPEN # |
| 1488h–14C5h | 2.1 | dead SYSCON code | five trampolines and the error trap | the module's HOME entries | OPEN #, CLOSE #, PRINT #, INPUT # |
| 1946h–1949h | 2.1 | syntax offsets `d0 c0 c4 c8` | `d2 c2 c6 ca` | a bare CAT/FORMAT/MOVE/ERASE is accepted | the disk keywords |
| 24C5h–24CEh | 1.1 | part of the AROS stream dispatch | helpers the EXROM's SAVE path calls | | SAVE etc. |
| 2548h–2560h | 1.1 | DOSAVE, the class-0Bh dispatcher | jumps to EXROM 01ABh, 01CCh, 1855h | SAVE, LOAD, VERIFY, MERGE go to the EXROM | SAVE, LOAD, VERIFY, MERGE |
| 25C0h | 1.1 | `CALL 0F09h` | `CALL 0F43h` | | *(uncertain)* |
| 25D6h–25E3h | 2.1 | the disk-keyword stub | `DI / LD HL,3000h / CALL 03FCh / EI / RET` | the disk keywords enter the module | CAT, FORMAT, MOVE, ERASE |
| 3CDCh–3CFFh | 1.1 | `FFh` filler | the HOME→EXROM thunk 3CE3h and two helpers | | everything |

## The thunks

HOME has three ways into the EXROM. All push the target and the bank word
`FEFCh` (bank FEh, the EXROM; chunk mask FCh, chunks 0 and 1), test
VIDMOD (5CC2h) to choose the copy of the 2068's bank-switch code in RAM
(at 65xxh with normal video, FDxxh with 64-column video), and go there
([overview.md](overview.md#banking-how-home-and-the-exrom-reach-each-other)).

### 3CE3h: into the EXROM, no return (v1.1)

```text
caller:  EXX / LD HL,target / JP 3CE3h
3CE3h    PUSH HL               ; the target
         LD HL,FEFCh / PUSH HL ; the bank word
         PUSH AF
         LD A,(5CC2h) / AND A  ; VIDMOD
         EXX                   ; the caller's registers back (flags kept)
         JR NZ,3CF4h
         POP AF / CALL 6572h   ; GOTO_BANK in RAM: never returns
3CF4h    POP AF / CALL FD32h   ; the same, 64-column video
```

The `CALL`s never return. The RAM routine overwrites the return address
the `CALL` pushed and uses the slot as scratch, then pops the bank word and
the target and jumps (DIFF_HOME_vs_STOCK.md, from the routine at EXROM
1372h, copied to 6572h). The `CALL` exists to reserve those two bytes.
3CF4h is reached only by the `JR NZ`, not by falling through. The caller's
registers travel in the alternate set: the caller's `EXX` hides them while
HL carries the target, and the thunk's `EXX` brings them back, so the
main registers arrive at the EXROM intact and the alternate HL holds the
target.

Callers: 0A02h (COPY), 2548h, 2552h, 255Bh (SAVE etc.), and 3CDCh by
falling in. There is no `CALL 3CE3h` anywhere.

Two helpers share the filler:

- **3CDCh**: `CALL 1F23h` (FIND-INT2: the number on the calculator stack
  → BC) / `EXX` / `LD HL,1855h` / falls into 3CE3h. The EXROM reaches it
  from 040Eh through the 08DDh thunk: it is a way for EXROM code to borrow
  a HOME routine and come back. EXROM 1855h is the `RET` after BIOS G_VERS,
  so arriving there returns to whatever called into HOME — now with the
  EXROM paged.
- **3CF8h**: `LD (5DCDh),HL` / `JP 04F8h`, entered only from 0A23h (the
  printer buffer flush, below).

### 0A50h: into the EXROM, no return, HL through 5DCDh (v1.1)

```text
caller:  LD (5DCDh),HL / LD HL,target / JP 0A50h
0A50h    PUSH HL / LD HL,FEFCh / PUSH HL / PUSH AF
         LD A,(5CC2h) / AND A
         LD HL,(5DCDh)         ; the caller's HL
         JP NZ,0A64h
         POP AF / CALL 6572h
0A64h    POP AF / CALL FD32h
```

As 3CE3h, but the caller's HL is passed through 5DCDh instead of the
alternate set. Callers: 04F5h (and 04FBh through it), 0A2Ch, and 0A4Ah by
falling in.

### 03FCh: into the EXROM and back (v1.1)

```text
caller:  [DI] / LD (5DCDh),HL / LD HL,target / CALL 03FCh [/ EI]
03FCh    PUSH HL               ; the target
         LD HL,FEFCh / PUSH HL ; the bank word
         LD HL,0 / PUSH HL / PUSH HL
         LD HL,(5DCDh)         ; the caller's HL
         CALL 040Dh
         RET
040Dh    PUSH AF / LD A,(5CC2h) / AND A
         JR Z,0418h
         POP AF / JP FD90h     ; CALL_BANK, 64-column video
0418h    POP AF / JP 65D0h     ; CALL_BANK in RAM
```

The returning thunk. 040Dh is a byte-for-byte copy of the EXROM's
CALL_B (0F99h). The RAM CALL_BANK pages the EXROM, calls the target, and
on its return pages HOME back, keeping a frame on the RAM bank stack
(pointer at 65CEh) for the way back. The two zero words are that frame's
room *(inferred from the frame GUARDED expects: [exrom-fdd.md](exrom-fdd.md))*.

v1.1 used it only for BEEPER. ROM 2.1 enters its module this way from
every hook (25D6h, 1488h–14BDh, 03F3h via 041Ch) and always under `DI`:
the bank switch writes port FFh then F4h with interrupts on, and an
interrupt between the two finds the empty DOCK at 0038h. Stock code
switches banks a few times per command; a file channel switches for every
character, and hit the window within a few hundred characters in ZEsarUX.
The 2.1 callers do not store HL in 5DCDh first (the module needs nothing in
HL), so the HL that reaches the module is whatever 5DCDh held.

Beware: 5DCDh is also the EXROM's block counter ([sysvars.md](sysvars.md#5dcdh-a-byte-counter-and-the-thunks-hl)).
A report raised inside a call made through 03FCh unwinds the Z80 stack
but not the bank stack; see 14B2h below.

## The hooks, in address order

### 0065h: the version byte

`FFh` filler in the genuine ROM, between the restarts and the NMI routine
at 0066h. The TS-Pico ROMs put their version there: 15h (v1.1, v1.5w), 17h
(v1.7), 20h (2.0), 21h (2.1). `PEEK 101` reads it; nothing in either ROM
does. BIOS G_VERS returns the same number in BC
([overview.md](overview.md#which-rom-is-this)). Each release changes this
byte and G_VERS together.

### 03F3h–0420h: BEEPER, moved out

The genuine BEEPER (the tone loop behind BEEP and the keyboard click)
filled 03F3h–041Dh. v1.1 moved it, unchanged except for its two `IX`
operands (040Fh → 205Bh, 0414h → 2060h, the same offsets from its new
start), to EXROM 203Fh, and used the 43 bytes for the returning thunk.
What is there now:

| HOME | Bytes | Since |
|---|---|---|
| 03F3h | `DI / LD (5DCDh),HL / LD HL,3015h / JR 041Ch` | 2.1 (v1.1: `LD (5DCDh),HL / LD HL,2000h / JP 03FCh`) |
| 03FCh | the returning thunk (above) | v1.1 |
| 040Dh | the CALL_B copy (above) | v1.1 |
| 041Ch | `CALL 03FCh / EI / RET` | 2.1 (v1.1: `00 00` and three bytes left from BEEPER) |

The callers still `CALL 03F3h` with BEEPER's arguments (HL the pitch, DE
the duration): 04A7h, 0A9Ah, 0BF7h, 0CD5h. HL goes through 5DCDh, DE
travels in its register. In v1.1 the target was EXROM 2000h, a `JP 203Fh`.
2.1 calls the module's G_BEEP (vector 3015h) instead, under `DI`: BEEPER
ends with `EI`, so the switch back to HOME ran with interrupts on and could
take an interrupt with the DOCK paged; the editor clicks once per
character, so `INPUT #` from a file crashed within a few hundred
characters in ZEsarUX. G_BEEP calls BEEPER at EXROM 2000h and disables
interrupts again after its `EI`; 041Ch's `EI` restores them once HOME is
back ([exrom-fdd.md](exrom-fdd.md)). The patch fits because the 2.1 bytes
at 03F3h are one longer (the `DI`) and the jump to 041Ch is a 2-byte `JR`.

### 04E8h–0502h: the printer's character helpers, and SENDTV

| HOME | Now | Reached from |
|---|---|---|
| 04E8h | `LD DE,5C92h / LD (5DD7h),DE / JP 0A1Dh` | 0A7Eh: a block-graphics character, its pattern built at MEMBOT (5C92h) |
| 04F2h | `LD HL,1639h` / 04F5h `JP 0A50h` | 0A20h: send one character to the Pico (EXROM 1639h → 1668h) |
| 04F8h | `LD HL,1636h / JR 04F5h` | 3CFBh: flush the printer buffer (EXROM 1636h → 17CDh) |
| 0500h | `CALL 0A09h` (genuine: `CALL 061Ah`) | the 2068's character output routine |

The genuine bytes at 04E8h–04FFh were the tail of a syntax routine
(DIFF_HOME_vs_STOCK.md: the SAVE/LOAD/MERGE name evaluator); no `CALL`
or `JP` in either ROM names 04E8h, 04F2h or 04F8h *(so the code they
replaced was reached by falling through, from code the TS-Pico also
changed; inferred)*.

**0500h** is the 2068's PRINT-OUT, through which every character printed
on any channel passes. Its first act was `CALL 061Ah`, which fetches the
print position (the printer's if FLAGS bit 1 says the printer is in use,
the screen's otherwise). Now it calls 0A09h first, which decides whether
the character goes to the Pico.

### 0A02h–0A2Fh: COPY, the character router, COPY-BUFF

The genuine K_DUMP (COPY: the screen to the ZX Printer, 176 pixel lines)
and COPY-BUFF (the 256-byte printer buffer at 5B00h to the printer) are
gone; their callers are kept.

| HOME | Now | What |
|---|---|---|
| 0A02h | `EXX / LD HL,1630h / JP 3CE3h` | COPY. The syntax table's COPY entry (19D7h: class 00h, routine 0A02h) still points here. EXROM 1630h → 1781h: with TPMODE bit 0 set, the COPY goes to the Pico as a printer transaction; clear, the stock dump, now at EXROM 1794h, runs ([exrom-chunk1.md](exrom-chunk1.md)) |
| 0A09h | `LD C,A / LD A,(5DDBh) / RRCA / LD A,C / JP NC,061Ah` | the character router, from 0500h. TPMODE bit 0 clear (printer to the 2068): the stock 061Ah, exactly as before |
| 0A12h | `BIT 1,(IY+1) / JP Z,061Eh` | printer to the Pico, but this character is not for the printer (FLAGS bit 1 clear): into 061Ah after its own test, which therefore takes the screen path |
| 0A19h | `CP 80h / JR NC,0A68h` | a printer character: 80h and above to 0A68h |
| 0A1Dh | `LD (5DCDh),HL / JP 04F2h` | below 80h: to the Pico, one character (EXROM 1668h) |
| 0A23h | `JP 3CF8h` | COPY-BUFF's entry, called by the stock code at 056Ah, 06C3h, 0EDCh (a printed newline, the end of LPRINT/LLIST, and so on): 3CF8h → 04F8h → EXROM 1636h → 17CDh, the stock COPY-BUFF moved to the EXROM unchanged. It prints the buffer at 5B00h on a ZX Printer (port FBh) and returns at once when there is none; nothing goes to the Pico ([exrom-chunk1.md](exrom-chunk1.md#the-printer-path-1630h183bh)) |
| 0A26h | `LD (5DCDh),HL / LD HL,163Ch / JP 0A50h` | a UDG (90h–A4h): EXROM 163Ch → 180Fh, which sends its 8-byte pattern (PMR1 = code × 8 + UDG) |
| 0A2Fh | `NOP` | |

So with `tpi:picopt` every LPRINT and LLIST character is a separate
transaction with the Pico ([../flows/printer.md](../flows/printer.md)):
plain characters as themselves, keywords expanded to their text (below),
block graphics and UDGs as their patterns.

### 0A4Ah–0A81h: COPY-LINE, the 0A50h thunk, token expansion

| HOME | Now | What |
|---|---|---|
| 0A4Ah | `LD (5DCDh),HL / LD HL,1633h` (falls into 0A50h) | COPY-LINE's entry → EXROM 1633h → 17C3h, the stock COPY-LINE moved unchanged |
| 0A50h | the no-return thunk (above) | |
| 0A68h | `CP A5h / JP C,0A73h / SUB A5h / CALL 0745h / RET` | a keyword token (A5h and above): the stock PO-TOKENS prints its text, which comes back through 0500h one character at a time |
| 0A73h | `CP 90h / JP NC,0A26h` | 90h–A4h: a UDG |
| 0A78h | `LD B,A / PUSH AF / CALL 066Dh / POP AF / JP 04E8h` | 80h–8Fh: a block graphic. 066Dh builds its 8×8 pattern at MEMBOT (5C92h); 04E8h passes that address as PMR1 |
| 0A81h | `NOP` | |

The genuine bytes were COPY-LINE, the loop that clocked a line of pixels
into the ZX Printer on port FBh. In ROM 2.1 nothing calls 0A4Ah: its two
genuine callers were inside K_DUMP and COPY-BUFF, which are gone. A program
that called the stock COPY-LINE directly would now reach the EXROM
*(inferred: kept for that reason or by accident)*. Printer output becomes
text with the keywords spelled out, where the ZX Printer received dots.

### 0E0Ch: a 16K EXROM

Part of the boot code at 0E0Bh–0E27h, which pages the EXROM in and copies
EXROM 1000h–162Fh to RAM 6200h (`LDIR`, BC = 0630h): the 2068's
bank-switch code, run from RAM ever after. 0E0Bh `LD A,01h` (HSR: chunk 0)
became `LD A,03h` (chunks 0 and 1), so the copy is made with both halves of
the 16K EXROM paged. With the same change in the EXROM's own boot path and
in BANK_ENABLE, this one byte is why the TS-Pico EXROM can be 16K.

### 0F12h–0F1Fh: the report printer (2.0)

```text
genuine:  LD A,B / LD DE,0F65h / CALL 073Fh / XOR A / LD DE,1115h / CALL 073Fh
2.0:      LD A,B / LD (5DCDh),HL / LD HL,235Ah / CALL 03FCh / 4 × NOP
```

When a report is printed, B holds ERR_NR + 1. The genuine code printed the
message from HOME's table at 0F65h and then ", " from 1115h. HOME's table
has no text for ROM 2.0's new report 1Ch, "T TS-Pico reset, try again", so
the whole job moved to EXROM 235Ah (EX_REPORT_MSG), which prints the new
text itself and every other code from HOME's table as before. The four
`NOP`s pad the patch to the original 14 bytes. Details:
[exrom-sync.md](exrom-sync.md).

### 13A5h, 1438h, 145Eh: OPEN # and CLOSE # (2.1)

Three `CALL`s in the stock OPEN # and CLOSE # code are redirected to
trampolines at 1488h–14BDh:

| HOME | Genuine | 2.1 | Why |
|---|---|---|---|
| 13A5h | `CALL 13BEh` | `CALL 1494h` | CLOSE #: the module closes an `F` stream itself (and returns carry); anything else goes on to 13BEh. Stock CLOSE # on an unknown channel letter ran off the end of its table and crashed |
| 1438h | `CALL 2569h` | `CALL 14BDh` | OPEN #'s syntax: the module parses `,mode[,reclen]`. The stock code skipped everything after the comma in the syntax pass, which also skipped storing each number's hidden five-byte form, so a record length could not be evaluated at run time (Report C) |
| 145Eh | `CALL 1465h` | `CALL 1488h` | OPEN # at run time: the module opens `f:` and `d:` specs and returns carry with DE = the stream offset, which 1461h stores in STRMS; anything else goes on to 1465h, whose only caller this was |

2569h and 13BEh keep their other callers. The module side:
[exrom-fdd.md](exrom-fdd.md); the bytes these rely on are anchors in
`build-rom.py` (1461h, 13A8h, 140Fh; [overview.md](overview.md#the-anchors)).

### 1488h–14C5h: the module's HOME entries (2.1)

55 bytes of an unreferenced remnant of a SYSCON open path — no `CALL`,
`JP`, `LD` or `JR` in either ROM reaches 1488h–14C6h — rewritten as:

| HOME | Bytes | Entry |
|---|---|---|
| 1488h | `DI / LD HL,300Fh / CALL 03FCh / EI / RET C / JP 1465h` | OPEN #: the module (G_OPEN), else the stock path |
| 1494h | `DI / LD HL,3012h / CALL 03FCh / EI / RET C / JP 13BEh` | CLOSE #: G_CLOSE, else stock |
| 14A0h | `DI / LD HL,3009h / CALL 03FCh / EI / RET` | the output routine of every `F` channel record (G_OUT) |
| 14A9h | `DI / LD HL,300Ch / CALL 03FCh / EI / RET` | the input routine of every `F` record (G_IN) |
| 14B2h | `POP HL / LD (65CEh),HL / POP HL / LD (5C3Dh),HL / LD SP,HL / EI / RET` | H_TRAP, the module's error trap |
| 14BDh | `DI / LD HL,3018h / CALL 03FCh / EI / RET` | OPEN #'s syntax (G_OSYN) |

The addresses are the module's vector table (3000h–301Eh), not its
routines, so a rebuilt module does not move them. An `F` record in CHANS
holds 14A0h and 14A9h as its output and input addresses: fixed HOME
addresses, so nothing in a record has to change when CHANS moves or the
module is rebuilt. `RST 10h` output through CURCHL calls 14A0h with the
character in A; the module finds its record through CURCHL
([sysvars.md](sysvars.md#channels-and-streams)).

**H_TRAP.** Every entry through these trampolines runs inside the module's
GUARDED frame, which sets ERR_SP to a frame holding H_TRAP's address, the
bank-stack pointer as it was before the thunk, and the old ERR_SP. A report
raised inside the module (`RST 8`) ends with `LD SP,(ERR_SP)` and `RET`,
with HOME paged — so the trap must be in HOME. It pops the bank-stack
pointer back into 65CEh (the thunk's frame is abandoned, not popped),
pops the old ERR_SP into 5C3Dh, sets SP to it and returns through it: on to
the previous handler, as the `RST 8` would have, with interrupts back on.
Without it each error inside a thunked call left the bank stack 4–8 bytes
lower, and after about 16 errors it overwrote the bank-switch code below it
([exrom-fdd.md](exrom-fdd.md), [ROM_CHANGES.md](../../ROM_CHANGES.md#guarded-and-the-home-trap)).

### 1946h–1949h: bare disk keywords (2.1)

The syntax table's offset bytes for CAT, FORMAT, MOVE and ERASE (tokens
CFh–D2h, entries 1946h–1949h). Each entry plus its offset is the
statement's parameter list:

| Keyword | Genuine: entry → list | 2.1 | The list there |
|---|---|---|---|
| CAT | 1946h + D0h → 1A16h | + D2h → 1A18h | `0A 2C` `05 25C8h` |
| FORMAT | 1947h + C0h → 1A07h | + C2h → 1A09h | `0A 2C` `05 25CCh` |
| MOVE | 1948h + C4h → 1A0Ch | + C6h → 1A0Eh | `0A 2C` `05 25D0h` |
| ERASE | 1949h + C8h → 1A11h | + CAh → 1A13h | `0A 2C` `05 25D4h` |

The genuine lists begin `0Ah` (a string expression) and `2Ch` (a comma),
so the 2068 demanded `CAT "name",` before handing over to the routine. The
2.1 offsets point two bytes on, at class 05h ("the routine does the rest")
and the routine's address, so a bare `CAT` is accepted and the module
parses whatever follows on both passes. The routines at 25C8h–25D4h are
`LD B,token / JR 25D6h`, unchanged.

### 24C5h–24CEh: helpers for the SAVE path (v1.1)

The genuine bytes were part of the AROS cartridge's stream dispatch
(`LD DE,(5CBCh) / ADD HL,DE / …`). v1.1 changed the operand of the
`LD DE,(nn)` at 24C3h and the bytes after it; from 24C5h they read:

```text
24C5h   RST 8 / DEFB 17h        ; Report "O Invalid stream"?   (not reached by anything found)
24C7h   CALL 1B44h / RET        ; the stock end-of-statement check
24CBh   LD BC,0014h / RET
```

24C7h is reached from the EXROM: SAVE-ETC pushes EXROM 01EAh as its return
address, and 01EAh is `EXX / LD HL,24C7h / JP 08DDh`, so a SAVE/LOAD/VERIFY/
MERGE statement ends with HOME's end-of-statement check. No reference to
24C5h or 24CBh was found in either ROM; the decoding of 24C5h as a report
is *(inferred)* from its bytes, and 24C3h's own instruction (`LD
DE,(17CFh)`) is not reachable as an instruction any more *(inferred)*.
This is the least certain hunk; DIFF_HOME_vs_STOCK.md says the same.

### 2548h–2560h: SAVE, LOAD, VERIFY, MERGE (v1.1)

The four statements share the syntax class 0Bh (their parameter lists at
19E0h–19E3h are runs of `0Bh`, so T_ADDR's low byte tells them apart:
E1h for SAVE … E4h for MERGE, before the EXROM subtracts E1h). The genuine
class-0Bh routine (DOSAVE) pushed SAVE-ETC's address (EXROM 01ABh),
`FEFEh` and two zero words, called the RAM CALL_BANK, and on return ran
the end-of-statement check (`CALL 1B44h`). v1.1 goes in with the
no-return thunk instead, and the end-of-statement check moved to 24C7h,
which the EXROM calls on its way out. v1.1:

| HOME | Now | Reached from |
|---|---|---|
| 2547h | `POP AF` (genuine) / 2548h `EXX / LD HL,01ABh / JP 3CE3h` | the class-0Bh routine: into the EXROM's SAVE-ETC (01ABh → 0210h) |
| 254Fh | `CALL 1BEFh` (a string expression) / 2552h `EXX / LD HL,01CCh / JR 254Ch` | EXROM 01B6h through 08DDh: the name is evaluated in HOME, then back to EXROM 01CCh |
| 2558h | `CALL 1BE5h` (a numeric expression) / 255Bh `EXX / LD HL,1855h / JR 254Ch` | EXROM 0393h through 08DDh: evaluate a number and return to the EXROM caller (1855h is a `RET`) |
| 2561h | `RET` (genuine) | |

So a tape statement goes HOME → EXROM 01ABh, which borrows HOME's
expression evaluator through these helpers, and at run time reaches 01D2h:
in 2.1 F_HOOK (the `f:` check), then SESSION_SETUP, which decides between
a `tpi:` command, the Pico's LOAD/SAVE and the tape (by TPMODE bit 1)
([exrom-driver.md](exrom-driver.md), [exrom-fdd.md](exrom-fdd.md),
[../flows/save.md](../flows/save.md), [../flows/command.md](../flows/command.md)).
The factoring saved about 13 bytes.

### 25C0h (v1.1)

`CALL 0F09h` → `CALL 0F43h`, in the routine at 25BCh–25C2h (`CALL
6499h` — BANK_ENABLE in RAM — then this call, then `LD BC,FF00h`).
DIFF_HOME_vs_STOCK.md reads 0F43h as entering a routine past its first
checks (`CP 09h`, `CP 15h`); what that changes for which statement is not
established *(unverified)*.

### 25D6h–25E3h: the disk keywords (2.1)

All four keyword routines (25C8h–25D4h) load B with their token and jump
here. The genuine 14 bytes were `CALL 2889h / JR NZ / CALL 2569h / CALL 1B44h /
JP 2567h`, the stock handling of keywords the 2068 had no disk to drive;
what each call did is not decoded here. 2.1:

```text
25D6h   DI
        LD HL,3000h        ; the module's G_MAIN vector
        CALL 03FCh         ; into the module and back
        EI
        RET
25DFh   5 × NOP
```

The module's FDD_MAIN runs on **both** passes — the syntax check, where it
consumes the argument and returns so the statement is accepted, and run
time, where it builds and sends `tpi:dir`, `tpi:copy`, `tpi:erase` or
`tpi:format` (it tests FLAGS bit 7; [exrom-fdd.md](exrom-fdd.md)). 2567h,
where the genuine stub jumped, is untouched.

## The HOME side of the protocol, by statement

| Statement | HOME path | EXROM |
|---|---|---|
| power-on | 0E0Bh (16K EXROM paged, bank code copied); EXTINIT | EXROM 08E7h → 01BCh: TPMODE = 2, BANK = FFh ([sysvars.md](sysvars.md)) |
| SAVE, LOAD, VERIFY, MERGE | class 0Bh → 2548h → 3CE3h; helpers 254Fh, 2558h, 24C7h | 01ABh … 01D2h ([exrom-driver.md](exrom-driver.md)) |
| `SAVE "tpi:…"` | the same | SESSION_SETUP → BUILD_PREHEADER_B |
| CAT, FORMAT, MOVE, ERASE | syntax offsets 1946h → 25C8h–25D4h → 25D6h | the module, 3000h |
| OPEN # | 1438h → 14BDh (syntax); 145Eh → 1488h (run time) | G_OSYN, G_OPEN |
| PRINT #, INPUT #, LIST #, INKEY$ # on an `F` stream | the record's 14A0h / 14A9h | G_OUT, G_IN |
| CLOSE # | 13A5h → 1494h | G_CLOSE |
| LPRINT, LLIST | 0500h → 0A09h → 04F2h / 0A26h / 04E8h; 0A23h at the end of a line (the stock ZX Printer flush) | 1639h, 163Ch; 1636h |
| COPY | 0A02h → 3CE3h | 1630h |
| BEEP, the key click | 03F3h → 041Ch → 03FCh | G_BEEP → BEEPER |
| any report | 0F12h → 03FCh | EX_REPORT_MSG |
| a report inside the module | `RST 8` → ERR_SP → 14B2h | |

Reports the Pico causes are raised by the EXROM (STATUS_TO_REPORT and its
targets, [exrom-driver.md](exrom-driver.md)), printed through 0F12h, and
trapped by `ON ERR` like any other ([ERROR_TRAPPING.md](../../rom-analysis/ERROR_TRAPPING.md)).

## Where comments, documents and the code disagree

None known: #182 corrected
[DIFF_HOME_vs_STOCK.md](../../rom-analysis/DIFF_HOME_vs_STOCK.md) (0065h is
the version byte `PEEK 101` reads; 041Ch–0420h is 2.1's BEEPER thunk tail)
and [SYMBOLS.md](../../rom-analysis/SYMBOLS.md) (G_VERS by release).
