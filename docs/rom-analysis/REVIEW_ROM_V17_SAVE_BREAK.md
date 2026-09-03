# Review: ROM V17 (`TSPICO-STORAGE-V15WSB.ROM`) — BREAK at the SAVE prompt

**Status: resolved.** Gustavo's follow-up build (`TSPICO-STORAGE-V17.ROM`,
crc32 `09D4CA63`) fixes all three findings and adopts the SPACE-preserving
design in §4. That ROM is what `src/rom/TSPICO.ROM` now ships. §10 records what
changed and what was verified; §§1-9 stay as the record of why.

**What this is:** a read of Gustavo's first V17 change against the V15W image it
was built from, plus a recommended respin. Written as a self-contained handoff.
Addresses are **EXROM** addresses; the shipped image is 32K (HOME 16K at file
`0x0000`, EXROM 16K at file `0x4000`), so *file offset = EXROM address + `0x4000`*.

**Images**

| Image | CRC32 | MD5 |
|---|---|---|
| `TSPICO-STORAGE-V15W.rom` (baseline) | `88A9DC63` | `AE8AF8F4C683CA539AFDA315C9170B95` |
| `TSPICO-STORAGE-V15WSB.ROM` (first V17) | `874252B8` | `96FDE1D88D47208276201176F3381D5C` |
| `TSPICO-STORAGE-V17.ROM` (**shipped**) | `09D4CA63` | `e70f6d70e8369a75914d0d072ba065ff` |
| original TS2068 HOME, `TS2068_U16.BIN` | `BF44EC3F` | `55d462fccc6c536037404ef4ced08bec` |
| original TS2068 EXROM, `TS2068_U20.BIN` | `AE16233A` | `575d203c6e15e679fba0b73f854ec7a2` |

**Summary**

V17 identifies and fixes the right thing: on V15W the break is noticed *after* the
21-byte header has already gone to the Pico, which leaves the Pico holding a
transaction it has to time out of. Testing for the abort **before** `$0893` is
exactly right, and the call-site shape Gustavo chose (`CALL $22AE` / `JR C` /
`RST 8` / `DEFB $0C`) is the right way to do it. Keep both.

Three things need changing before this ships:

1. **SPACE must remain a break key.** V17 retires SPACE as the tape BREAK and
   requires CAPS SHIFT + SPACE instead. We don't want that — see §2.
2. **The abort path has a stack-balance slip** that makes it jump into the block
   being saved instead of reporting `D BREAK` — §5.
3. **One substitution lands inside the cassette loader's timing loop** and should
   break standard-speed tape LOAD — §6.

§4 gives a 13-byte routine that keeps everything V17 got right, keeps SPACE as
BREAK, and makes all three problems go away.

---

## 1. What V17 changes

84 bytes, six hunks.

| File | EXROM | Was | Now | What it is |
|---|---|---|---|---|
| `0x0065` | HOME `$0065` | `15` | `17` | version byte |
| `0x40D7` | `$00D7` | `DB FE 1F` | `CD 09 20` | break test in the stock **SA-BYTES** byte loop |
| `0x40F0` | `$00F0` | `3E 7F DB FE 1F` | `00 CD 09 20 00` | break test in **SA/LD-RET** (`$00E5`) |
| `0x4197` | `$0197` | `DB FE 1F` | `CD 09 20` | break test inside stock **LD-EDGE** |
| `0x4886` | `$0886` | `FD CB 02 EE CD AA 08` | `CD AE 22 38 02 CF 0C` | SAVE-prompt call site |
| `0x5853` | `$1853` | `15` | `17` | version byte |
| `0x62AE` | `$22AE` | `FF` filler | 65 bytes | new routine |

`$2009` is `BREAK_KEY` — the TS2068's **CAPS SHIFT + SPACE** test, with a
suppression flag:

```asm
2009  3E 7F        LD A,$7F
200B  DB FE        IN A,($FE)
200D  1F           RRA
200E  D8           RET C            ; SPACE up  -> carry set = no break
200F  FD CB 7D 76  BIT 6,(IY+$7D)   ; $5CB7, the break-inhibit flag
2013  28 02        JR Z,$2017
2015  37 C9        SCF : RET        ; inhibited -> carry set = no break
2017  3E FE        LD A,$FE
2019  DB FE        IN A,($FE)
201B  1F           RRA              ; CAPS SHIFT
201C  D8 C9        RET C : RET      ; CAPS+SPACE -> carry CLEAR = BREAK
```

New call site and routine:

```asm
0886  CD AE 22     CALL $22AE
0889  38 02        JR C,$088D       ; carry set = no break -> carry on
088B  CF 0C        RST 8 : DEFB $0C ; Report D, BREAK - CONT repeats
088D  DD E5        PUSH IX          ; (stock from here: header send at $0893)

22AE  FD CB 02 EE  SET 5,(IY+$02)   ; TV-FLAG: lower screen will be cleared
22B2  37 F5        SCF : PUSH AF    ; pre-load the "no break" carry for the exit
22B4  C5 D5        PUSH BC : PUSH DE
22B6  01 40 9C     LD BC,$9C40      ] verbatim copy of $08AA:
22B9  0B 79 B0     DEC BC/LD A,C/OR B ]  ~40000-iteration debounce
22BC  20 FB        JR NZ,$22B9      ]
22BE  AF DB FE     XOR A/IN A,($FE) ]  any-key wait (all rows at once)
22C1  E6 1F FE 1F  AND $1F/CP $1F   ]
22C5  28 F7        JR Z,$22BE       ]
22C7  06 0C        LD B,$0C         ; 12-frame grace so both BREAK keys land
22C9  76 10 FD     HALT : DJNZ $22C9
22CC  CD 09 20     CALL $2009       ; BREAK_KEY
22CF  DA BE 08     JP C,$08BE       ; no break -> stock tail, RET with carry set
22D2  CD E6 22     CALL $22E6       ; break -> clear lower screen
22D5  D1 C1 F1     POP DE/POP BC/POP AF
22D8  E1           POP HL           ; <-- Finding 1, §5
22D9  3A 48 5C     LD A,($5C48)     ] copy of $00E5's border restore
22DC  E6 38 0F0F0F AND $38 / RRCA x3]
22E1  A7           AND A            ; clear carry = "break happened"
22E2  D3 FE FB C9  OUT ($FE),A / EI / RET

22E6  DD E5 D9     PUSH IX : EXX    ; standard EXROM->HOME call thunk
22E9  21 A9 08     LD HL,$08A9      ; HOME $08A9 = clear the lower screen
22EC  C3 DD 03     JP $03DD
```

## 2. SPACE has to stay a break key

**This is the one design point we want changed, and it isn't negotiable from our
side.** SPACE has been the way to stop a tape operation on this family of machines
since 1983 — it is 40-plus years of muscle memory for every Timex/Sinclair user
who ever loaded a cassette. Requiring CAPS SHIFT + SPACE means retraining people
who have been doing it one way their whole lives, and that is not a trade we want
to make for an internal implementation convenience. Whatever we ship should feel
like the machine has always felt.

That is not just sentiment — it is what the hardware does. Checked against the
original chip dumps (`TS2068_U16.BIN` and `TS2068_U20.BIN`, both byte-identical to
the baseline images used throughout this review, so this is read off genuine
silicon):

**Every tape break test in the original EXROM is SPACE alone.** A census of every
keyboard read in all 8K:

| Pattern | Meaning | Occurrences |
|---|---|---|
| `3E 7F DB FE` | `LD A,$7F / IN A,($FE)` — half-row `B`–`SPACE` | `$00D5`, `$00F0`, `$0195` |
| `3E FE DB FE` | `LD A,$FE / IN A,($FE)` — half-row `CAPS`–`V` | **none** |
| `AF DB FE` | `XOR A / IN A,($FE)` — all rows at once | `$08B5` (the prompt's any-key wait) |
| `CD 09 20` | `CALL $2009` (`BREAK_KEY`) | **none** |

The original EXROM never reads the CAPS SHIFT row at all. The three SPACE tests
are the SA-BYTES loop (`$00D5`), SA/LD-RET (`$00F0`) and LD-EDGE (`$0195`), each
`RRA`-ing bit 0 of row `$7F`. `BREAK_KEY` lives in HOME and, in the original ROM,
is called from exactly two places — `$1AB9` (the interpreter's between-statement
check, `RST 8 / DEFB $14` = `L BREAK into program`) and `$0A53` (the printer
driver). So the stock machine runs **two break conventions on purpose**:

| Context | Keys | Report |
|---|---|---|
| Running BASIC, printing | CAPS SHIFT + SPACE | `L BREAK into program` |
| Tape SAVE / LOAD / VERIFY | **SPACE alone** | `D BREAK - CONT repeats` |

After V17, SPACE aborts nothing — not at the SAVE prompt, not during a cassette
`LOAD`, not on the way out of a block. And because `BREAK_KEY` honours the
inhibit flag (bit 6 of `$5CB7`, set by HOME at `$0E9B`), tape aborts become
suppressible in a way the stock tape code never was.

The good news: keeping SPACE costs nothing. The real bug was never *which key* —
it was **when the key is tested**. Stock tests it too late:

```
prompt  ->  keypress  ->  header sent to the Pico  ->  break noticed
```

The header goes out *because* a key was pressed, and `$00E5` only notices the
SPACE afterwards. On a cassette that was harmless — the tape isn't listening, and
a partial header is just noise on the medium. The TS-PICO is a stateful receiver,
so the same sequence leaves it waiting for a data block that never comes.

Fix the ordering, keep the key. §4.

## 3. What V17 gets right, and should keep

- **The ordering fix itself** — testing for the abort at `$0886`, before
  `CALL $0068` at `$0893`, is the correct place and the whole point.
- **The call-site shape.** Moving `SET 5,(IY+$02)` into the new routine frees
  exactly the 4 bytes needed for `JR C` / `RST 8` / `DEFB $0C`, so the routine can
  answer with the carry flag and the familiar Report D comes from the call site.
  That is a tidy piece of work and §4 keeps those 7 bytes at `$0886` byte for byte.
- **Putting new code at `$22AE`**, where 7.5K of `$FF` is free and nothing has to
  move.
- Reusing the stock tail at `$08BE` via `JP C` is clever; §4 doesn't need it, but
  it is not wrong.

## 4. Recommended: keep SPACE, fix the ordering — 13 bytes

Replace the routine at `$22AE` with the stock key wait followed by the stock SPACE
test, and revert the three tape-path substitutions. The `$0886` call site stays
exactly as V17 ships it.

```asm
22AE  FD CB 02 EE  SET 5,(IY+$02)   ; as before: lower screen will be cleared
22B2  CD AA 08     CALL $08AA       ; the stock any-key wait, unchanged; it
                                    ;   preserves AF/BC/DE/IX and clears the
                                    ;   lower screen itself via HOME $08A9
22B5  3E 7F        LD A,$7F         ; the stock SPACE test, run immediately
22B7  DB FE        IN A,($FE)
22B9  1F           RRA              ; carry set = SPACE up = proceed
22BA  C9           RET              ; carry clear -> RST 8 at $088B -> Report D
```

No stack arithmetic, no duplicated key wait, no grace delay needed: the test runs
microseconds after the key was detected, so the key is still down and the abort is
deterministic. CAPS+SPACE aborts too, because SPACE is part of it.

**Byte patch, relative to V17:**

| File offset | EXROM | V17 | Recommended |
|---|---|---|---|
| `0x40D7` | `$00D7` | `CD 09 20` | `DB FE 1F` (revert to stock) |
| `0x40F0` | `$00F0` | `00 CD 09 20 00` | `3E 7F DB FE 1F` (revert to stock) |
| `0x4197` | `$0197` | `CD 09 20` | `DB FE 1F` (revert to stock) |
| `0x4886` | `$0886` | `CD AE 22 38 02 CF 0C` | **unchanged** |
| `0x62AE` | `$22AE` | 65-byte routine | `FD CB 02 EE CD AA 08 3E 7F DB FE 1F C9`, rest back to `FF` |

Expected checksums for that image (version bytes left at `17`; bump them if this
respins as V18):

```
32K image   CRC32  73B80953   MD5 7e73f6e481dba4a5dd939768015d1ae5
EXROM half  CRC32  9176F1AD
HOME half   CRC32  C2B6CBF6   (unchanged from V17)
```

**Resulting behaviour**, compared with stock and with V17:

| Action | Original TS2068 | V17 | Recommended |
|---|---|---|---|
| SPACE at the prompt | save starts; header written; Report D only if SPACE still held | save runs to completion, no abort | **abort, Report D, nothing sent to the Pico** |
| CAPS+SPACE at the prompt | same as SPACE | abort (but see §5) | **abort, Report D, nothing sent** |
| Any other key at the prompt | save proceeds | save proceeds | save proceeds |
| SPACE during a cassette LOAD | abort, Report D | no abort | **abort, Report D** (stock) |
| SPACE during a cassette SAVE | abort, Report D | no abort | **abort, Report D** (stock) |
| Cassette pulse timing | stock | altered (§6) | **stock** |

Still out of scope, and unchanged by any of this: a break *during* a Pico transfer
(after `$0893`) still leaves the Pico mid-transaction. The firmware bounds that
itself now, and signalling it in ROM is a separate piece of work.

**Verifying a rebuilt image:**

```bash
python3 - <<'PY'
import zlib
rom = open("TSPICO-STORAGE-V18.ROM","rb").read()
def chk(off, hexs, what):
    want = bytes.fromhex(hexs.replace(" ",""))
    got  = rom[off:off+len(want)]
    print("%-4s 0x%04X %-34s %s" % ("OK" if got==want else "BAD", off, what,
          "" if got==want else "got "+got.hex(" ")))
chk(0x40D7, "DB FE 1F",                      "SA-BYTES break test back to stock")
chk(0x40F0, "3E 7F DB FE 1F",                "SA/LD-RET break test back to stock")
chk(0x4197, "DB FE 1F",                      "LD-EDGE break test back to stock")
chk(0x4886, "CD AE 22 38 02 CF 0C",          "call site as V17")
chk(0x62AE, "FD CB 02 EE CD AA 08 3E 7F DB FE 1F C9", "new prompt routine")
chk(0x62BB, "FF FF FF FF",                   "old routine cleared")
print("crc32 %08X (expect 73B80953)" % zlib.crc32(rom))
PY
```

## 5. Finding 1 — `POP HL` at `$22D8` unbalances the stack

This applies to V17 as it stands. §4 removes the routine entirely, so it goes away
with it — but it is worth recording, because it means **the abort path in V17 has
never actually run to completion**: anyone testing it would have seen a crash, not
a Report D.

**Symptom:** aborting with CAPS+SPACE does not report `D BREAK - CONT repeats`. It
transfers control to the start of the block being saved and executes it. For
`SAVE "x"` that is `PROG` — your BASIC program text run as Z80 code.

**Why.** The routine pushes three words and the break path pops four:

```
CALL $22AE from $0886        stack:  [ret $0889] [X] ...
  SCF / PUSH AF                      [AF] [ret $0889] [X]
  PUSH BC / PUSH DE                  [DE] [BC] [AF] [ret $0889] [X]
  ...
  CALL $22E6 ... returns             (balanced: PUSH IX + $03DD's POP IX / RET)
  POP DE / POP BC / POP AF           [ret $0889] [X]
  POP HL          <-- takes $0889    [X]
  RET             <-- takes X
```

`X` is the data pointer pushed at `$0851`:

```asm
04C9  3A 74 5C   LD A,($5C74)      ; 0 for SAVE
04CC  A7         AND A
04CD  CA 51 08   JP Z,$0851
0851  E5         PUSH HL           ; <-- X = start address of the data
0852  3E FD      LD A,$FD
0854  18 12      JR $0868          ; the prompt sequence
...
08A5  DD E1      POP IX            ; <-- where stock code consumes X
08A7  C3 68 00   JP $0068
```

`$04CD` is the only reference to `$0851`, and `$0851`'s `JR` is the only way into
`$0868`, so this stack shape holds for every SAVE. The `$0426` call and the
`$086F`–`$0884` HOME thunk are both balanced, which the stock tail at `$08BE`
independently proves — it pops exactly IX, DE, BC, AF and returns.

The no-break path (`JP C,$08BE`) is correct. Only the break path is wrong, and it
looks like a slip rather than a design: `AND A` at `$22E1` clears carry, which is
only meaningful if control reaches the `JR C` at `$0889`, and the `RST 8 / DEFB $0C`
at `$088B` is unreachable as things stand.

**If V17's routine is kept for any reason,** the fix is one byte — `$22D8`
(file `0x62D8`) `E1` → `00`. `RET` then returns to `$0889` with carry clear,
`RST 8` reports D, and the leftover data pointer is discarded when the error
handler restores `SP` from `ERR_SP`, as every other `RST 8` in the ROM relies on.
That image is CRC32 `B4B58654` (EXROM half `567B7EAA`).

**Confirming it on hardware in 30 seconds:** type

```
SAVE "t" CODE 0,10
```

and hold CAPS+SPACE at the prompt. The pushed pointer is `$0000`, so V17 as shipped
should **reset the machine**; a corrected ROM reports `D BREAK - CONT repeats`.

## 6. Finding 2 — `$0197` sits inside LD-EDGE's timing loop

`$0193` is the stock pulse-measurement loop of the cassette loader, and `B` counts
its iterations:

```asm
0193  04         INC B
0194  C8         RET Z
0195  3E 7F      LD A,$7F
0197  DB FE      IN A,($FE)     ; V17: CD 09 20  CALL $2009
0199  1F         RRA            ;
019A  D0         RET NC
019B  A9         XOR C
019C  E6 20      AND $20
019E  28 F3      JR Z,$0193
```

Per-iteration cost, computed from the instruction stream:

| | T-states |
|---|---|
| stock | 4+5+7+11+4+5+4+7+12 = **59** |
| V17 | 4+5+7+**(17+7+11+4+11)**+5+4+7+12 = **94** |

**+59%**, so every pulse measures ~37% low, against thresholds that are absolute
constants calibrated to the stock loop — `LD B,$9C` / `CP $C6` at `$0126`,
`LD B,$C9` / `CP $D4` at `$0135`, `LD B,$B0` at `$014B`. Standard-speed tapes
should stop loading.

This path is live, not dead code: `$196D` (`LOAD`) tests `$5DDB` bit 1 and, if the
Pico is not the active device, does `JP Z,$1A4D` straight into the genuine loader
at `$00FF`. `SAVE` has the mirror-image fallback at `$1879 → $1872 → JP $006B`.

Reverting `$0197` (§4) removes this entirely. Worth recording so it doesn't get
reintroduced: **any break test inside LD-EDGE has to cost the same T-states as the
one it replaces.**

## 7. Smaller things

- **`$00D7` (SA-BYTES) costs ~35 T-states per byte** in V17 — stock
  `LD A,$7F / IN / RRA / RET NC` is 27 T, the V17 form is 62 T. It lands in the gap
  between bytes rather than inside a pulse, so it is far less dangerous than §6,
  but tape output stops being cycle-exact. §4 reverts it.
- **`$00D5` and `$0195` keep a now-dead `LD A,$7F`** in V17 — `$2009` loads `A`
  itself. Reverting removes the oddity.
- **`$22AE` duplicates 14 bytes of `$08AA`** in V17, leaving two copies of the same
  wait to drift apart. §4 calls the original instead.
- **The 12-frame grace (~0.2 s)** exists only because V17 needs a *second* key to
  be detected. With a SPACE-only test it is unnecessary, and dropping it makes the
  abort deterministic rather than dependent on how long the user holds the keys.

## 8. What was and was not verified

- **Verified against the original chips:** `TS2068_U16.BIN` / `TS2068_U20.BIN` are
  byte-identical to the baseline images used here, and §2's census of keyboard
  reads and `BREAK_KEY` callers was run on those dumps.
- **Verified statically from the images:** the byte diff, all disassembly quoted
  above, the call-graph claims (`$04CD` is the only reference to `$0851`; `$08AA`
  had exactly one caller; `$196D`/`$1879` fall back into the stock tape routines),
  the T-state counts, and every CRC32/MD5 in this document — including the §4
  image, which was assembled and disassembled back to confirm it says what it
  should.
- **Not verified on hardware or in an emulator.** The ZEsarUX bridge (issue #35)
  boots this ROM — all three copyright lines, including "(C) 2024 Timex Pico
  Interface" — but the SAVE path is not yet exercised end-to-end there (milestone
  M3), so §5's crash was derived, not observed. The `SAVE "t" CODE 0,10` test
  settles it in seconds on a real machine.

## 9. Suggested order of work

1. Revert `$00D7`, `$00F0` and `$0197` to stock — SPACE goes back to being the
   tape break key everywhere.
2. Replace the routine at `$22AE` with the 13 bytes in §4, leaving the `$0886`
   call site exactly as V17 has it.
3. Rebuild, check against CRC32 `73B80953` (or re-run the snippet in §4), bump the
   version bytes at file `0x0065` and `0x5853` if this ships as V18.
4. Test on hardware: `SAVE "t"` and press SPACE at the prompt → `D BREAK - CONT
   repeats`, and the Pico should show no sign of a started transaction. Then
   `SAVE "t"` and press any other key → a clean save. Then a cassette
   `LOAD ""` / `SAVE` round trip to confirm the tape paths are back to stock.

---

## 10. V17h — what the follow-up build changed

Compared with the first V17, `TSPICO-STORAGE-V17.ROM` (03-09-2026) makes four
changes, and they close every finding above.

| Site | First V17 | V17h |
|---|---|---|
| `$00D7` SA-BYTES break test | `CALL $2009` | **stock** `IN A,($FE) / RRA` |
| `$00F0` SA/LD-RET break test | `CALL $2009` | **stock** |
| `$0197` LD-EDGE break test | `CALL $2009` | **stock** |
| Prompt break test | `CALL $2009` (CAPS+SPACE) | `CALL $22F0`, a new local routine |
| Abort-path stack | `POP HL` then `RET` | `POP HL` / `EX (SP),HL` then `RET` |
| `$1C70` | `(C) 2024` | `(C) 2025` |

All three tape sites are now **byte-identical to `GENUINE-2068-exrom.bin`**, so
LD-EDGE's 59-T sampling loop (§6) and SA-BYTES' per-byte timing (§7) are back to
stock, and SPACE stays the tape BREAK key everywhere it always was (§2).

**The stack fix (§5) is correct, and tidier than the one proposed here:**

```asm
22D7  POP AF        ; carry set, from the SCF at $22B2
22D8  POP HL        ; HL = $0889, the return address    stack: [data ptr]
22D9  EX (SP),HL    ; HL = data ptr (dead); stack: [$0889]
...
22E2  A7            AND A                ; carry clear = break happened
22E6  C9            RET                  ; -> $0889, carry clear
                                         ; -> JR C not taken
                                         ; -> RST 8 / DEFB $0C = Report D
```

§5 suggested simply neutralising the `POP HL` and letting the `RST 8` handler
reset `SP` from `ERR_SP`. V17h instead consumes the data pointer explicitly,
which is what `POP IX` at `$08A5` would have done on the normal path — the same
result with the stack left tidy either way.

**The new break test does what §2 asked for:**

```asm
22F0  FD CB 7D 76  BIT 6,(IY+$7D)   ; the break-inhibit flag, checked first
22F4  28 02        JR Z,$22F8
22F6  37 C9        SCF : RET        ; inhibited -> never breaks
22F8  3E 7F        LD A,$7F
22FA  DB FE        IN A,($FE)
22FC  1F C9        RRA : RET        ; carry clear = SPACE down = BREAK
```

SPACE alone, honouring the inhibit flag — and CAPS+SPACE aborts too, since SPACE
is part of it. The ordering fix survives: the test runs at `$0886`, before the
`CALL $0068` at `$0893`, so an abort reaches the Pico as nothing at all.

### Behaviour note: tap vs hold

The 12-frame (~0.2 s) `HALT` grace between the key detection and the break test
is still there. It existed because CAPS needed time to land alongside SPACE; with
a SPACE-only test it now means:

- **tap SPACE** → the save proceeds (and because `$00E5` is stock again, no
  spurious Report D follows — the key is up by the time it is tested);
- **hold SPACE** → abort, Report D, nothing sent to the Pico.

That is a coherent reading of the prompt — tap is "press any key", hold is BREAK
— but it is a choice worth being explicit about, since a user who taps SPACE
*intending* to abort will get a save. Dropping the `LD B,$0C / HALT / DJNZ`
(4 bytes) would make the abort deterministic.

### Checksum discrepancy in the release note

`TSPICO-STORAGE-V17.TXT` heads its listing with

```
TSPICO-STORAGE-V17.ROM   32768   CRC32 115C9102   MD5 BB8DCFBEFA92DC8DA05355C6E4D0B854
```

but the accompanying `.ROM` is crc32 `09D4CA63` / md5
`e70f6d70e8369a75914d0d072ba065ff`. Applying the 90 byte edits that the same TXT
lists to `TSPICO-STORAGE-V15W.ROM` reproduces the supplied `.ROM` exactly, and
the TXT's own V15W checksum (`88A9DC63`) agrees with ours — so this is not a
tooling difference, and the binary matches its own documented diff. The header
checksum appears to be stale from an earlier pass. **Worth confirming with
Gustavo which build is canonical before this ships**, since a release ROM
identified by a checksum that doesn't match it is a support problem later.

### Not verified

Still static analysis: the disassembly, the stack trace, the byte-for-byte
comparison against the genuine EXROM, and every checksum here. Not run on
hardware. `SAVE "t"`, hold SPACE at the prompt: expect `D BREAK - CONT repeats`,
no transaction at the Pico, and no reset.
