# HOME ROM: genuine TS2068 → TS-PICO

**The TS-PICO HOME ROM is the genuine TS2068 HOME ROM with 242 bytes changed
across 10 hunks.** Every change is one of three things: redirect tape/printer I/O
to the Pico, switch the EXROM from 8K to 16K, or install the thunk that makes
HOME→EXROM calls possible.

`TSPICO-11-home` and `TSPICO-15w-home` are **byte-identical** — there is only one
TS-PICO HOME ROM.

| | Genuine | TS-PICO |
|---|---|---|
| crc32 | `bf44ec3f` | `e8714bed` |
| md5 | `55d462fccc6c536037404ef4ced08bec` | `620d6ded106839b73dd6dac9f98f7ed9` |
| Changed | — | 242 bytes / 10 hunks |

## Baseline

> **The image previously used as "stock" here was not stock.** This is worth
> reading before you trust any older analysis.

`2068Home.BIN` in `TS2068 Ref Library/2068 ROMS/` (crc32 `7d411fe9`) is a
**modified, partly bit-rotted EPROM dump**, not a genuine TS2068 HOME ROM. Diffing
TS-PICO against it produces **389 bytes / 26 hunks — 147 bytes of which are pure
phantom**, artefacts of the baseline rather than anything Gustavo did.

It is deliberately **not** copied into `ROMs/`: a file sitting next to the real
ROMs is a file someone eventually flashes. Instead `tools/romdiff.py` carries both
bad crc32s in a `KNOWN_BAD` map and names them on sight:

```
genuine-home  GENUINE-2068-home.bin  16384 B  crc32=7d411fe9  !! this is the W.J.
              modified HOME dump (TS2068 Ref Library/2068 ROMS/2068Home.BIN)
!! WRONG IMAGE(S): genuine-home
!! Every hunk count below is meaningless until this is fixed.
```

The genuine image (crc32 `bf44ec3f`) is `ROMs/GENUINE-2068-home.bin`, extracted
from `~/Documents/github/zesarux-tspico-lab/zesarux/src/ts2068.rom` (bytes
0-16383).

**The proof is that TS-PICO matches genuine where the "stock" image doesn't:**

| Test | Genuine | TS-PICO | `2068Home.BIN` (W.J.) |
|---|---|---|---|
| Character set `0x3D00-0x3FFF` | — | **identical to genuine** | 38 bytes differ |
| Copyright `0x1118` | `© 1982 Sinclair Research Ltd` / `© 1983 Timex Computer Corp` | **identical to genuine** | `T/S 2068 Computer The Superior Machine. (W.J.)` |
| `BIN` token `0x0101` | `0x49` (`'I'`) | **`0x49`** | `0x01` — **token corrupted** |

A modified ROM does not coincidentally restore the genuine font in all 768 bytes
and the genuine copyright string. TS-PICO was built *from* the `bf44ec3f` image;
therefore `bf44ec3f` is the baseline. The `BIN`-token corruption is a functional
regression no one would introduce deliberately — evidence that image is both hacked
*and* degraded.

Verify:

```bash
python3 tools/romdiff.py    # checks crc32 of every image and refuses to be quiet
```

### What the W.J. image actually is

A competent one-off custom EPROM — someone's personal TS2068 ROM, later dumped and
mislabelled. It carries the Sinclair NMI bug fix at `0x006D` (`JR NZ` → `JR Z`),
kills the DELETE auto-repeat delay at `0x0352` (`LD BC,20000` → `LD BC,1`), swaps
the boot colours at `0x0D33`/`0x0DB0` into a dark theme, patches a genuine
`INT(-65536)` floating-point bug, redraws nine lowercase glyphs, and signs the
startup message `(W.J.)`. It is a curiosity, and **not** related to the TS-PICO.
`W.J.` is unidentified.

`2068Exrom.BIN` (crc32 `526f5676`) is likewise **not** genuine — 99 bytes / 22
hunks off `ae16233a`.

## The 10 hunks

### Banking — the one byte that makes the 16K EXROM work

| Hunk | Change |
|---|---|
| **`0x0E0C`** | `01` → `03` |

`0x0E0B-0x0E27` is a boot stub that gets `LDIR`'d to RAM `0x6000` and run:

```asm
0E0B: 3E 03       LD A,003h      ; TS-PICO: HSR = 0000_0011 -> chunks 0+1 = 16K
                                 ; genuine: 3E 01           -> chunk 0 only = 8K
0E0D: D3 F4       OUT (0F4h),A
0E0F: DB FF       IN A,(0FFh)
0E11: CB FF       SET 7,A        ; bit 7 = 1 -> EXROM (not DOCK)
0E13: D3 FF       OUT (0FFh),A
0E15: 21 00 10    LD HL,1000h    ; EXROM 0x1000 = bank-switch code template
0E18: 11 00 62    LD DE,6200h    ; -> RAM 0x6200  (offset +0x5200)
0E1B: 01 30 06    LD BC,0630h
0E1E: ED B0       LDIR
```

**This single byte is why the EXROM can be 16K**, and it mirrors the EXROM's own
`0x004A` patch. It is the change behind the requirement that ZEsarUX's EXROM be
widened 8K→16K. See [MEMORY_MAP.md](MEMORY_MAP.md).

The `LDIR` also explains the mysterious `CALL 6572` / `CALL 0FD32h` in the thunk
below: the bank switcher lives in **RAM**, copied out of EXROM `0x1000-0x162F` at
boot with a `+0x5200` offset.

### Tape, printer and screen-dump redirection

| Hunk | Genuine routine | What TS-PICO does |
|---|---|---|
| `0x0A02-0x0A2F` (46) | `K_DUMP` / `DUMPPTR` — the `COPY` screen dump (`DI; LD B,0B0h; LD HL,4000h; …`) | Replaced with `EXX; LD HL,1630h; JP 3CE3` into the EXROM, plus a new `TP_MODE` character handler at `0x0A09` (`LD C,A; LD A,(5DDB); RRCA; LD A,C; JP NC,061A`). Screen dump now goes to the Pico's virtual printer. |
| `0x0A4A-0x0A81` (56) | `PRSCAN` — the ZX-Printer bit-banging loop on port `0xFB` | Entirely replaced. Adds token expansion at `0x0A68` (`CP 0A5h; SUB 0A5h; CALL 0745h`), converting printer output from a ZX-Printer **bitmap** to **ASCII with BASIC tokens expanded**. |
| `0x04E8-0x0502` (27) | Tail of the SAVE/LOAD/MERGE filename evaluator | `LD DE,5C92h; LD (5DD7),DE; JP 0A1D` plus trampolines at `0x04F2`/`0x04F8`. **`0x0500` `SENDTV`: `CALL 061A` → `CALL 0A09`** — all character output now passes the `TP_MODE` check. |
| `0x2548-0x2560` (25) | `DOSAVE` — stock 8-push `LD BC,SLVM; PUSH BC; …` dispatcher | `POP AF; EXX; LD HL,01AB; JP 3CE3` — ~13 bytes saved, plus entries for `0x01CC` and `0x1855`. |
| `0x03F3-0x041D` (43) | **`BEEPER`** — the `BEEP`/key-click tone generator (`DI; LD A,L; SRL L; SRL L; CPL; AND 03h; LD C,A; LD B,0; LD IX,040Fh`) | Overwritten with a `CALL`-style thunk to **EXROM `0x2000`**, plus a shared dispatcher helper at `0x040D`. **BEEPER itself was relocated verbatim to EXROM `0x203F`** — the only changes are the two `IX` operands (`040F`→`205B`, `0414`→`2060`), preserving the same relative offsets. Bytes `0x041E-0x0421` are now dead remnants. |

The `BEEPER` relocation is a neat trick: HOME needed the 43 bytes, the EXROM had
room, and the routine is self-contained. It also explains EXROM `0x2000`'s entry
table — its first live entry is `JP 203F`, i.e. "beep".

### New code in former filler

| Hunk | What |
|---|---|
| `0x3CDC-0x3CFF` (36) | Written into `0xFF` filler after the "Bytes:" message. Contains **`CALL_EXROM`, the HOME→EXROM thunk at `0x3CE3`** — see below. Also `0x3CF8: LD (5DCD),HL; JP 04F8` (a post-return handler entered from `0x0A23`) and two trailing `NOP`s. |
| `0x0065` (1) | `ff` → `15` in `RST` filler. `0x15` = 21 = the **TPI BIOS version** (`0x0015`). *Medium confidence* — the value matches, but nothing in HOME reads it. |

### Small, less-certain changes

| Hunk | What |
|---|---|
| `0x25C0` (1) | `CALL 0F09` → `CALL 0F43` in `PASSEM`. `0x0F43` = `INC (IY+SUBPPC)`, entering past the `CP 09h`/`CP 15h` dispatch checks. |
| `0x24C5-0x24CE` (10) | Tail of the AROS-cartridge stream dispatch. **Unreferenced from HOME in both ROMs** — likely reclaimed dead space called from the EXROM. **Least certain hunk here**; entry points can't be determined from HOME alone. |

## `CALL_EXROM` — the HOME→EXROM thunk at `0x3CE3`

This address is `0xFF` filler in the genuine ROM. The whole thing is a TS-PICO
addition.

```asm
3CDC: CD 23 1F    CALL 1F23          ; a caller, entered from the EXROM via 08DD
3CDF: D9          EXX
3CE0: 21 55 18    LD HL,1855h
                                     ; ---- thunk entry ----
3CE3: E5          PUSH HL            ; ADDR = EXROM target
3CE4: 21 FC FE    LD HL,0FEFCh
3CE7: E5          PUSH HL            ; B=FE = EXROM bank, C=FC = horizontal select
3CE8: F5          PUSH AF
3CE9: 3A C2 5C    LD A,(5CC2)        ; VIDMOD
3CEC: A7          AND A
3CED: D9          EXX                ; restore caller's regs (EXX doesn't touch flags)
3CEE: 20 04       JR NZ,3CF4
3CF0: F1          POP AF
3CF1: CD 72 65    CALL 6572          ; GOTO_BANK, normal video   -- NEVER RETURNS
3CF4: F1          POP AF
3CF5: CD 32 FD    CALL 0FD32h        ; GOTO_BANK, expanded video -- NEVER RETURNS
                                     ; ---- separate routine, not fall-through ----
3CF8: 22 CD 5D    LD (5DCD),HL
3CFB: C3 F8 04    JP 04F8
```

Three things make this look broken until you know them:

- **`CALL 6572` targets RAM and is correct.** `GOTO_BANK` was copied there from
  EXROM `0x1372` by the `0x0E15` `LDIR` (`+0x5200`). It **never returns**: its
  first act is `LD IX,0; ADD IX,SP; LD (IX+0),C; LD (IX+1),B` — it deliberately
  overwrites the pushed return address to use as scratch, then
  `POP BC; POP IX; POP IX; JP (IX)`. The `CALL` exists purely to *reserve that
  2-byte slot*. (EXROM `0x0F8A` uses `JP` instead, because it is itself reached by
  a `CALL` and already has a slot.)
- **`0x3CF4` is not fall-through** — only the `JR NZ` at `0x3CEE` reaches it.
- **`0x3CF8` is a separate routine**, entered only via `JP 3CF8` from `0x0A23`.

**`0xFEFC` decoded:** `B` = bank, `C` = horizontal select. Bank `0xFE` = EXROM
(`0x00` = DOCK, `0xFF` = HOME). Horizontal select is **active-low** — a `0` bit
means "take this 8K chunk from the named bank". `0xFC` = `1111_1100` → chunks 0+1
→ **`0x0000-0x3FFF` = the 16K TS-PICO EXROM**. The genuine ROM uses `0xFEFE`
(chunk 0 only, 8K) — see genuine `0x254C: 01 FE FE`.

**`LD A,(5CC2)` = `VIDMOD`** picks *which copy* of the RAM dispatcher to use: `0` =
normal video → `0x6572`; non-zero = expanded 64-column video → `0xFD32`, where the
code was relocated to high RAM to clear the second display file.

### Sibling thunks

Same job, different HL-passing convention (via sysvar `0x5DCD` instead of `EXX`):

| Entry | Kind | Convention |
|---|---|---|
| `0x3CE3` | GOTO | `EXX; LD HL,tgt; JP 3CE3` |
| `0x0A50` | GOTO | `LD (5DCD),HL; LD HL,tgt; JP 0A50` |
| `0x03FC` | CALL (returns) | `LD (5DCD),HL; LD HL,tgt; JP 03FC` |
| `0x040D` | CALL_B | **byte-identical copy of EXROM `0x0F99`** |

### Every HOME→EXROM call site

| Site | Preamble | → EXROM |
|---|---|---|
| `0x0A06` | `0A02: EXX; LD HL,1630` | `0x1630` |
| `0x254C` | `2548: EXX; LD HL,01AB` | `0x01AB` |
| `0x2556` (`JR 254C`) | `2552: EXX; LD HL,01CC` | `0x01CC` |
| `0x255F` (`JR 254C`) | `255B: EXX; LD HL,1855` | `0x1855` |
| `0x3CE0` (fall-through) | `3CDC: CALL 1F23; EXX; LD HL,1855` | `0x1855` |
| `0x0A2C` → `0A50` | `0A26: LD (5DCD),HL; LD HL,163C` | `0x163C` |
| `0x0A4D` fall-through | `0A4A: LD (5DCD),HL; LD HL,1633` | `0x1633` |
| `0x04F5` → `0A50` | `04F2: LD HL,1639` | `0x1639` |
| `0x04FB` → `04F5` | `04F8: LD HL,1636` | `0x1636` |
| `0x03F9` → `03FC` | `03F3: LD (5DCD),HL; LD HL,2000` | `0x2000` (CALL, returns) |

There is **no `CALL 3CE3`** anywhere — entry is always `JP`/`JR`/fall-through.

The EXROM side of these lands on a jump table at `0x1630`, which is zero-filled in
the genuine 8K EXROM:

```
1630: C3 81 17   JP 1781    <- from HOME 0A02 (K_DUMP)
1633: C3 C3 17   JP 17C3    <- from HOME 0A4D (PRSCAN)
1636: C3 CD 17   JP 17CD    <- from HOME 04F8
1639: C3 68 16   JP 1668    <- from HOME 04F2
163C: C3 0F 18   JP 180F    <- from HOME 0A29
```

## What TS-PICO did *not* change

Worth stating, because the bad baseline made it look otherwise:

- **The character set is untouched** — all 768 bytes match genuine.
- **The startup copyright message is untouched.**
- **The Sinclair NMI bug at `0x006D` is faithfully preserved** (`JR NZ`), bug and
  all.
- **The `BIN` token is intact.**
- **No floating-point routines were touched.**

## Cross-references

- `TS2068 Ref Library/gus-rom-analysis.md` already documents this ROM (it is
  byte-identical to `gus-home.rom`). **Two errors in it:** it calls `0x0A02` "TPI
  initialization during startup" — it is `K_DUMP`, the screen dump; and it lists
  only three EXROM entry points (`0x01AB`, `0x01CC`, `0x1855`) — there are ten,
  missing the whole `0x163x` table.
- The EXROM side: [DIFF_EXROM_vs_STOCK.md](DIFF_EXROM_vs_STOCK.md).
- Symbols: [SYMBOLS.md](SYMBOLS.md).
