# System variables

Source: the ROM 2.1 listings
[`tspico-21-exrom.labelled.asm`](../../rom-analysis/disasm/tspico-21-exrom.labelled.asm)
and [`tspico-21-home.asm`](../../rom-analysis/disasm/tspico-21-home.asm)
(every site below was found by scanning them and read in context); the
`EQU` blocks of [`src/rom/fdd/fddcmd.asm`](../../../src/rom/fdd/fddcmd.asm),
[`src/rom/patches/tspico-sync.asm`](../../../src/rom/patches/tspico-sync.asm)
and [`src/rom/patches/tspico-zx48-v3.asm`](../../../src/rom/patches/tspico-zx48-v3.asm).

The TS-Pico's ROM keeps its state in nine words and bytes of RAM at
5D37h–5DDBh, and leans on a dozen of the 2068's own system variables.
This chapter lists them by area, one row each: the address, the size, what
it holds, who writes it and who reads it. No document from the original
developers names the TS-Pico variables; the names here are the ones this
reference and [PROTOCOL_FROM_ROM.md](../../rom-analysis/PROTOCOL_FROM_ROM.md#ts-pico-system-variables)
use, and the module's `EQU`s where it has one. TPMODE (5DDBh) is the one a
BASIC program is meant to read, as `PEEK 24027`.

Addresses are those of ROM 2.1. "EXROM 1A7Dh" is a site in the EXROM half,
"HOME 0A0Ah" one in HOME. Where a site is in the routine of another
chapter, that chapter explains the routine; this one says what the
variable is for.

**Where they live.** The genuine 2068 ROMs reference no system variable
above 5CDAh (a scan of both genuine listings), and the TS-Pico's sit at
5D37h–5DDBh, between the 2068's system variables and the RAM it uses for
its bank-switching code (6000h–65FFh, below). What else, if anything, a
stock 2068 keeps in 5CDBh–5FFFh, and so why these addresses were safe to
take, is not established here *(unverified)*.

## The TS-Pico's variables

| Address | Size | Name here | Holds |
|---|---|---|---|
| 5D37h | 2 | NMI vector | where the EXROM's NMI routine jumps; 0 = none |
| 5DCDh | 2 | COMND/BLOCK LEN, and the thunks' HL | a byte count while a block is sent; otherwise the HL a HOME→EXROM thunk passes |
| 5DCFh | 1 | BANK (BANK_SV) | pre-header byte 2: the memory bank of the data, `FFh` = HOME |
| 5DD1h | 2 | SESSION ID | the session of the current LOAD/SAVE/command, 0 = none |
| 5DD3h | 2 | command address | where the command text (or the screen, for COPY) starts |
| 5DD5h | 2 | command length | the length of the name SESSION_NAMED accepted |
| 5DD7h | 2 | PMR1 | the first `CODE` number of a `tpi:` command |
| 5DD9h | 2 | PMR2 | the second `CODE` number |
| 5DDBh | 1 | TPMODE (MODE_SV) | the two switches, and two transient prefix flags |

### 5D37h, the NMI vector

The EXROM's NMI routine (1107h–1113h, ending `RETN`) does `LD HL,(5D37h)`
/ `LD A,H` / `OR L` / `JR Z` past / `JP (HL)`: it jumps through the word if
it is non-zero. The genuine EXROM has the same routine reading NMIADD
(5CB0h) with the test the other way round — `JR NZ` past, so it jumps only
when the vector is **zero**, the bug the 2068 inherited from the Spectrum.
The TS-Pico fixed the test and moved the vector. Nothing in either 2.1 half
writes 5D37h; a program that wants an NMI handler stores its address
there. Its value at power-on depends on what the 2068 leaves in that RAM
*(unverified)*.

### 5DCDh: a byte counter, and the thunks' HL

Two unrelated uses share the word.

**The HOME→EXROM thunks** pass HL through it: the caller does
`LD (5DCDh),HL` / `LD HL,target` and jumps to 03FCh or 0A50h, which load
HL back from it after pushing the bank word ([overview.md](overview.md#banking-how-home-and-the-exrom-reach-each-other)).
HOME writes it at 03F4h (the BEEPER thunk), 0A1Dh, 0A26h, 0A4Ah, 0F13h
(ROM 2.0's hook) and 3CF8h, and reads it at 0406h and 0A5Ah.

**A transfer's byte count.** BUILD_PREHEADER_B (EXROM 1BA0h) stores the
command text's length there, sends its low byte (from B) and high byte
(5DCEh) as pre-header bytes 7–8, and SEND_DATA_BLOCK_D (2255h–226Bh)
sends both bytes again at the head of the `'D'` block, then counts the
word down as it sends each byte of the text. The SAVE path (18DFh, 18EFh)
parks DE in it around a call, and the printer and COPY paths store their
byte counts there (16A8h, 16D9h/16E5h, 1769h: `1B00h` for a normal
screen, `3B00h` for the larger one, 17B3h)
([exrom-chunk1.md](exrom-chunk1.md), [exrom-driver.md](exrom-driver.md)).

Beware: any HOME→EXROM thunk overwrites it. The transfers keep it only
because nothing between the store and the last use goes through a
returning thunk *(inferred from the sites; no code guards it)*.

### 5DCFh, BANK

Pre-header byte 2, the bank the data block is in, sent by every
pre-header: SAVE (18A7h), LOAD (19A4h), a `tpi:` command (BUILD_PREHEADER_B,
1BB5h), the printer's (165Dh, 1718h), `f:` (SEND_FOPEN, 32B6h) and a
channel command (CH_SEND, 367Dh). The only write is at EXROM 03F6h–03F8h,
on the boot path from EXTINIT (`LD A,FFh` / `LD (5DCFh),A`), so it is
always `FFh`, HOME. The firmware ignores it for commands
([PROTOCOL.md §4.3](../../PROTOCOL.md#43-the-pre-header-and-the-dispatcher)).

### 5DD1h, SESSION ID

A 16-bit number that ties the blocks of one LOAD or SAVE together and lets
the Pico tell a new statement from a retry. Written by:

- **SESSION_SETUP** (1A75h–1A7Dh): `FRAMES` + 1, incremented again until
  it is not 0. So it is not random, as one design document says, and never
  0 for a BASIC statement: 0 is reserved for transfers not started from a
  BASIC command ([PROTOCOL_FROM_ROM.md](../../rom-analysis/PROTOCOL_FROM_ROM.md#ts-pico-system-variables)).
- **TPI_SEND** (31EFh) and **F_HOOK** (3231h) in the 2.1 module, the same
  way ([exrom-fdd.md](exrom-fdd.md)).
- **04E8h**, which stores 0: called after a SAVE's data block (18ECh, when
  the flag byte was not 0) and after a LOAD's (19B2h, flag FFh). The
  session ends with its data block.

Read by the SAVE and LOAD pre-headers (18ADh, 18E3h, 19AAh: pre-header
bytes 3–4) and by SEND_FOPEN (32C6h, 32CCh), which sends it in the
`tpi:fopen` text so the Pico can match the `f:` operation to the SAVE or
LOAD that follows ([../firmware/tspico-disk.md](../firmware/tspico-disk.md)).

### 5DD3h and 5DD5h, the command text

SESSION_NAMED (1AAFh, 1AB2h) records where the name is and how long: DE
and BC, from the string on the calculator stack. BUILD_PREHEADER_B sends
the text from 5DD3h (1BE1h); 1B50h reads the length back for the
`tpi:tape`/`sdcard`/`picopt`/`ts2040` checks (below). The COPY path puts
the screen's start there (175Dh: 4000h).

### 5DD7h and 5DD9h, PMR1 and PMR2

The two `CODE` numbers of `SAVE "tpi:…" CODE a,b`, pre-header bytes 3–6
of a command (1BBBh, 1BC6h; the firmware's `PARAMS`). SESSION_NAMED clears
both (1B0Ch, 1B0Fh), then, if the statement continues with `CODE`
(token AFh), evaluates `a` into 5DD7h (1B2Dh) and, after a comma, `b` into
5DD9h (1B3Ch). Without `CODE` both stay 0, which is why "no CODE" and
`CODE 0,0` are the same command to every handler.

The printer path reuses them: 5DD9h's low byte holds the printer
transaction's TADDR (1657h, read at 16D0h, where 5 is an LPRINT
character), and 5DD7h a buffer address (1820h: a character code × 8 +
`UDG`; HOME 04EBh stores 5C92h, MEMBOT) ([exrom-chunk1.md](exrom-chunk1.md),
[home.md](home.md)).

### 5DDBh, TPMODE (`PEEK 24027`)

| Bit | Meaning | Set by | Cleared by | Read by |
|---|---|---|---|---|
| 0 | printer output goes to the Pico | `SAVE "tpi:picopt"` (2151h) | `SAVE "tpi:ts2040"` (218Fh); `SAVE "tpi:tape"` too before ROM 2.1 | HOME 0A09h (every character of output: SENDTV now calls it), EXROM 1781h (COPY) |
| 1 | LOAD, SAVE, VERIFY, MERGE go to the Pico | `SAVE "tpi:sdcard"` (2103h); 1 at boot | `SAVE "tpi:tape"` (20BEh → TAPE_MODE) | 1879h (SA-BYTES), 196Dh (LD-BYTES); clear = the stock tape routines |
| 2–3 | unused | | | kept by S_MODE |
| 4–5 | unused | | SESSION_SETUP's non-command exit (1A3Ah), F_HOOK (325Fh) | |
| 6 | the name began `NET:` | SESSION_NAMED (1AD4h, with bit 7) | as bit 7 | the switch words (below) |
| 7 | the name began `TPI:` or `NET:` | SESSION_NAMED (1AEBh) | 1A3Ah, 1B8Dh (before a command is sent), the switch words, F_HOOK | the switch words |

**At power-on it is 2**: LOAD and SAVE to the Pico, printer to the 2068's
own. EXTINIT (EXROM 08E7h), the EXROM's boot entry, was patched to `JP
01BCh`, which calls 221Fh, which calls 081Dh: `LD A,2` / `JP 1862h`, the
BIOS S_MODE (221Fh also clears 5CBEh and 6315h, below). The user manual
gives the same values: 2 at switch-on, 3 after `tpi:picopt`, 1 after
`tpi:tape` from there ([user manual App. D.2](../../manual/user-manual.md#d2-tpmode)).

**The switch words.** SESSION_NAMED sets bit 7 (and bit 6 for `NET:`)
when the name starts with that prefix, upper-cased with `AND 5Fh`, followed
by `:`. At run time (FLAGS bit 7, `IY+1`) a `TPI:` name is compared with
four words that the ROM handles itself and never sends:

| Text | Length (C) | Effect | Code |
|---|---|---|---|
| `tpi:tape` | 8 | bit 1 cleared (2.1; 1.x and 2.0 set TPMODE to 0, both switches off) | 208Eh → 20BEh → TAPE_MODE (301Eh) |
| `tpi:sdcard` | 10 | bit 1 set | 20C3h |
| `tpi:picopt` | 10 | bit 0 set | 2111h |
| `tpi:ts2040` | 10 | bit 0 cleared | 2155h |

The letters are compared case-insensitively (`AND 5Fh`), the digits of
`2040` exactly. Each first clears bits 7 and 6; a `NET:` name, or a length
that does not match exactly, goes on to 210Eh and is sent to the Pico as an
ordinary command (where it is "Unrecognized"). A match ends the statement
with "0 OK" (1B72h → STATUS_OK). Each word changes one switch: after
`tpi:picopt` then `tpi:tape` then `tpi:sdcard` the value is 3, both on.
Before 2.1, `tpi:tape` cleared the printer switch too and the same sequence
gave 2 (#176; [exrom-fdd.md](exrom-fdd.md#tape_mode-3021h)).

**The BIOS** ([exrom-driver.md](exrom-driver.md)): G_MODE (1840h → 1856h)
returns BC = TPMODE AND 0Fh, keeping AF; S_MODE (1842h → 1862h) stores A AND
0Fh, keeping AF; 1861h is `XOR A` falling into it. Both mask to the low
nibble, so they never see or set the prefix flags.

The NET: device: SESSION_NAMED recognises it, and nothing else does — the
switch words ignore it and the command is sent to the Pico with no sign of
the prefix but the text; the firmware expects every command to start
`tpi:` ([PROTOCOL.md §5.2](../../PROTOCOL.md#52-the-body)) and answers
"Unrecognized command"
([PROTOCOL_FROM_ROM.md](../../rom-analysis/PROTOCOL_FROM_ROM.md#an-undocumented-net-device)).
Bits 6 and 7 are transient: they live from SESSION_NAMED to the point where
the name is classified, and are clear between statements.

## The 2068's variables the TS-Pico code uses

Only the uses in TS-Pico code are listed: the EXROM's printer code
(1630h–17FFh), 1800h–1BFFh and 2000h up, and the HOME sites the TS-Pico
changed. Addresses are the stock ones;
the names are the TS2068's (ZX Spectrum names where they are the same).

### BASIC and the interpreter

| Address | Name | Used for | Sites |
|---|---|---|---|
| 5C3Ah | ERR_NR | the report code; IY points here, and `IY+0` is ERR_NR | the module's reports (3087h, 335Ch, 348Eh, 34B3h, 3562h, 35A1h) |
| 5C3Bh | FLAGS | bit 7: 1 = run time, 0 = syntax check. The disk keywords run on both passes and test it ([exrom-fdd.md](exrom-fdd.md)); SESSION_NAMED tests it as `IY+1` | 3171h, 1B48h |
| 5C3Dh | ERR_SP | the error handler's stack frame: GUARDED installs H_TRAP and puts the old value back | 3062h, 3074h, 3081h; HOME H_TRAP (14B2h) |
| 5C5Dh | CH_ADD | the next character of the BASIC line: the module's argument parser | 3154h, 3158h, 315Ch, 3280h |
| 5C5Fh | X_PTR | where the error marker goes; the module's syntax errors | via `RST 8` |
| 5C65h | STKEND | the calculator stack's end: a string argument is fetched from below it (SESSION_SETUP 1A80h) and the module builds its command text above it | 1A80h, 3180h–341Fh (12 sites) |
| 5C74h | T_ADDR | its low byte is the pre-header's TADDR: 0 SAVE, 1 LOAD, 2 VERIFY, 3 MERGE (0 for a command) | 18A1h, 199Eh, 1A95h, 1B01h, 1BAFh, 31DFh, 3240h, 32BCh; 5C75h at 31E2h |
| 5C78h | FRAMES | the session id's seed | 1A75h, 31E7h, 3229h |
| 5C7Bh | UDG | the printer path's character address | 1817h |
| 5C92h | MEMBOT | stored in PMR1 by HOME 04EBh | HOME 04E8h |
| 5CB7h | ERRLN's high byte | bit 6 ("an ON ERR trap was taken"; [ERROR_TRAPPING.md](../../rom-analysis/ERROR_TRAPPING.md)) is tested as `IY+7Dh` by the copy of BREAK_KEY at 2009h and by the 2.0/1.7 BREAK paths | 200Fh, 22F0h, 2327h |
| 5C8Dh | ATTR_P | sent in the printer pre-header | 169Fh |

TV_FLAG (5C3Ch, `IY+2`) bit 5 is set by v1.7's SAVE-prompt BREAK routine
at 22AEh (clear the lower screen).

### Channels and streams

| Address | Name | Used for | Sites |
|---|---|---|---|
| 5C10h | STRMS | the stream table (−3…15, two bytes each): OPEN # and CLOSE # | 34F0h |
| 5C4Fh | CHANS | the channel area, where OPEN # adds an `F` record | 342Dh, 3480h, 34BBh |
| 5C51h | CURCHL | the current channel's record: the `F` record's routines find their record through it | 3033h, 350Dh, 3568h, 35A7h, 3641h, 3649h |
| 5C53h | PROG | the end of the channel area | 3422h |
| 5C48h | BORDCR | the border colour, which BEEPER keeps | 2051h, 22DAh |
| 5CCBh | (OPEN/CLOSE # stream) | the stream number the stock OPEN/CLOSE # code stores at 140Fh, which the module reads | 340Fh, 3471h, 34A9h |

The channel record's own layout is in [exrom-fdd.md](exrom-fdd.md).

### The 2068's RAM code

The 2068 copies its bank-switching code into RAM at boot; these addresses
are in that copy, not variables in the usual sense.

| Address | What | Used by |
|---|---|---|
| 5CC2h | VIDMOD: 0 normal video, non-zero 64-column video. Decides which copy of the RAM dispatcher a thunk jumps to (6572h/65D0h, or FD32h/FD90h in high RAM, moved there to clear the second display file) | the HOME thunks 3CE9h, 040Eh, 0A56h |
| 6499h | BANK_ENABLE, copied from EXROM 1299h at boot | the bank switch |
| 6572h, 65D0h | the RAM CALL_BANK/GOTO_BANK targets | the thunks |
| 65CEh | the bank stack pointer (BANK_SP) | the returning thunks push and pop through it; GUARDED (3067h) records it and H_TRAP (HOME 14B2h) restores it after an error ([overview.md](overview.md#banking-how-home-and-the-exrom-reach-each-other)) |
| 5CBEh, 6315h | two 2068 variables cleared at EXTINIT by 221Fh, together with the TPMODE set-up; 6315h is also tested by BANK_ENABLE (1299h). These are the genuine EXTINIT's displaced instructions *(inferred: the patched EXTINIT jumps here instead of doing them itself)*; their meaning on a stock 2068 is not established here | 2226h, 2229h |

## The ZX Spectrum ROM's variables

The ZX v3/v4 ROM ([zx48.md](zx48.md)) runs with the Spectrum's own system
variables, at the same addresses where the two machines agree: T_ADDR
(5C74h, the SA-ALL operation, 0 SAVE … 3 MERGE), CH_ADD (5C5Dh), X_PTR
(5C5Fh), ERR_SP (5C3Dh). It has no TPMODE and no session: in ZX48 mode the
Pico takes every LOAD and SAVE. Its patch source names them in its `EQU`
block, and [zx48.md](zx48.md) explains each use.

## Where comments and the code disagree

Tracked in the [`reference-followup` issues](https://github.com/timex-sinclair-projects/tspico-firmware-build/issues?q=label%3Areference-followup).

- `fddcmd.asm`'s comment on MODE_SV says SESSION_SETUP "clears bits 7–4 for
  a plain name": it clears bits 7–4 at 1A3Ah (`AND 0Fh`) on the non-command
  exit, which is the same thing, and bits 7–6 at 1B8Dh before a command.
  Consistent; noted so the two masks are not mistaken for a bug.
