# The TS-PICO protocol as the ROM actually implements it

Derived from the shipping binaries, cross-checked against
[`LOW-LEVEL-PROTOCOL-V5.TXT`](../LOW-LEVEL-PROTOCOL-V5.TXT),
[`GUSTAVO_PROTOCOL.md`](../GUSTAVO_PROTOCOL.md), [`PROTOCOL.md`](../PROTOCOL.md),
and [`EXTCMD_PROTOCOL.md`](../EXTCMD_PROTOCOL.md).

**Where the docs and the ROM disagree, the ROM wins** — that is
`GUSTAVO_PROTOCOL.md`'s own rule, and there are nine such disagreements. They are
listed at the bottom and are the most useful part of this file.

Addresses are EXROM offsets unless marked HOME. All are identical in v1.1 and
v1.5w except where noted.

## Ports

Exactly two ports beyond the genuine TS2068 set. Neither appears in the genuine EXROM.

| Port | Dir | Role |
|---|---|---|
| `0x0E` | in / out | **Data port** — commands, payload, status bytes, keys |
| `0x0F` | in | **Status port** |

Status bits, per `LOW-LEVEL-PROTOCOL-V5.TXT:91-129`:

| Bit | Meaning |
|---|---|
| D7 | reserved |
| **D6** | **0 = Pico busy, 1 = Pico ready to continue** ← the only bit the ROM tests |
| D5 | 0 = Pico RX queue full/not ready, 1 = accepting writes |
| D4 | 0 = Pico has nothing to send, 1 = data available to read |
| D3-D0 | reserved |

**D4 and D5 are documented but never tested anywhere in either ROM** — every status
check is `BIT 6,A`. The Pico firmware pins `0x0F` to `0xFF` permanently
(`PROTOCOL.md:131-136`), so they are dead in practice. Don't build anything on
them.

There are **no register-indirect (`IN r,(C)` / `OUT (C),r`) I/O instructions
anywhere in the EXROM**, so the port list is provably complete.

### The only accessors

```asm
2298: DB 0E  A7  C9     TSPICO_READ_DATA:   IN A,(0Eh) ; AND A ; RET   (carry clear)
229D: D3 0E  A7  C9     TSPICO_WRITE_DATA:  OUT (0Eh),A; AND A ; RET   (carry clear)

0655: CD 9F 06          READ_STATUS:  CALL 069F        ; BREAK guard
      D2 AA 06                        JP NC,06AA       ; key down -> abort
      DB 0F                           IN A,(0Fh)
      C9                              RET
```

Status is **never** read with a bare `IN A,(0Fh)` — always via `0x0655`, which
folds in the BREAK check. Three stray `OUT (0Fh),A` sites exist (`0x2020`,
`0x2023`, `0x2236`) despite the spec calling port 15 read-only; all three sit in
unreferenced regions and appear vestigial.

## The ready handshake

`WAIT_PICO_READY` (`0x1A54`) is the whole synchronization mechanism. The docs call
it `WF_NPH`.

```asm
1A54: PUSH AF / PUSH BC
1A56: LD B,0E2h          ; 226 attempts. Single loop. No outer retry wrapper.
1A58: CALL 0655          ; read status -- and this costs ~88 ms, see below
1A5B: BIT 6,A            ; ready?
1A5D: JR NZ,1A6E         ; yes -> success
1A5F: DJNZ 1A58
1A61: LD A,40h           ; dead - overwritten below
1A63: NOP ×5             ; patched-out code; see Open questions
1A68: POP BC / POP AF
1A6A: LD A,02h           ; internal timeout code
1A6C: SCF / RET          ; carry SET = failed
1A6E: POP BC / POP AF    ; .ready
1A70: SCF / CCF / RET    ; carry CLEAR = ok
```

**Carry set on return = timeout or BREAK.** The two are indistinguishable: `0x069F`
detects a keypress on row `0xFE` and routes to `0x06AA` → `POP BC; JP 1A61` — the
same exit as timeout.

### The timeout is ~20 seconds, and this is the most misread number in the ROM

`LD B,0E2h` looks like 226 quick polls. It is not — **each poll costs ~88 ms**,
because reading the status port goes through a debounced keyboard scan:

```
1A54 WF_NPH -> 0655 READ_STATUS -> 069F CHECK_BREAK -> 0856 -> 10x 07F6
                                                                 ^^^^^^^
                                            6x256 nested DJNZ before every IN
```

| | T-states | @3.528 MHz |
|---|---|---|
| `07F6` one debounced keyboard read | 30,980 | 8.78 ms |
| `0856` (10× `07F6`) | 310,133 | 87.91 ms |
| **one WF_NPH poll iteration** | 310,284 | **87.95 ms** |
| **full timeout (B=226)** | 70,124,184 | **19.88 s** |

```bash
python3 tools/wf_nph_timing.py     # recomputes this from the instruction stream
```

**Operational consequences, which matter more than the headline number:**

- The Z80 samples port `0x0F` only **~11 times per second**.
- The **first** poll lands ~88 ms *after* `WF_NPH` is entered — so **every**
  `WF_NPH` call costs ≥88 ms even when the Pico was ready immediately.
- BREAK is sampled at that same ~11 Hz.

So `GUSTAVO_PROTOCOL.md`'s "~20s" figure is **right**, but its stated reason ("the
counter is larger in the real ROM") is **wrong** — the counter really is `0xE2`. The
number and the explanation come apart, which is why this keeps getting rediscovered.

**The rule the ROM follows: wait for ready before touching the data port.** The
driver at `0x2274` is the canonical shape — *write, wait, read*:

```asm
2274: CALL 229D          ; OUT (0Eh),A  - send
2277: JR C,2294          ; -> error 9
2279: CALL 1A54          ; WAIT
227C: JP C,2294          ; -> error 9
227F: LD C,0Eh           ; dead (see Open questions)
2281: CALL 2298          ; IN A,(0Eh)   - read status byte back
2284: JR C,2294
2286: AND A
2287: JP Z,2294          ; status 0 -> error 9
228A: DEC A              ; *** A = status - 1 ***
228B: RET Z              ; status 1 = OK -> done
228C: CALL 026F          ; else dispatch the FUNCTION chain
228F: AND A
2290: JR NZ,2296
2292: AND A / RET
2294: LD A,09h / SCF / RET   ; shared "comms failed" exit
```

The one place that broke this rule is the function-`0x86` Y/N loop — fixed in
v1.5w. See [DIFF_V11_vs_V15W.md](DIFF_V11_vs_V15W.md).

## Status bytes and the `status - 1` convention

The Pico answers with a **status byte**. The ROM decrements it (`DEC A` at
`0x228A`) before dispatching, so **every downstream comparison is against
`status - 1`**. This trips people up constantly — it is why the Y/N handler tests
`CP 85h`.

- `status == 0` → error 9 (treated as "no answer")
- `status == 1` → OK, return
- `status 2..0x0A` → error report, via the dispatcher at `0x1BF3`
- `status >= 0x80` → a **FUNCTION request**: the Pico is asking the Z80 to do
  something on its behalf

## Error codes → BASIC reports

Dispatcher at `0x1BF3`, entered with `A = status - 1`. **Every entry matches the
spec table exactly** — this is the one part of the documentation that is fully
faithful to the ROM.

| Status | ROM target | Report |
|---|---|---|
| 0 | — | error 9 ("no answer") |
| 1 | `l1c23h` | OK |
| 2 | `l1c3eh` | **R** — Tape loading error |
| 3 | `l1c39h` | **F** — Invalid file name |
| 4 | `l1c3ch` | **Q** — Parameter error |
| 5 | `l1c35h` | **C** — Nonsense in BASIC |
| 6 | `l1c16h` | **6** — Number too big |
| 7 | `l1c18h` | **8** — End of file |
| 8 | `l1c1ch` | **A** — Invalid argument |
| **9** | `l1c1ah` | **9** — STOP statement |
| 10 | `l1c21h` | **J** — Invalid I/O device |
| 11-127 | `l00f8h` | **D** — BREAK-CONT repeats |

### Internal "error 9" surfaces as **Report J**, not Report 9

This is the trap. The ROM's own comms-failure code is `LD A,09h; SCF; RET`
(`0x2294`, `0x0414`, and v1.5w's `0x22A9`). But that `9` is **already in the
dispatcher's `status-1` representation** — so it enters `0x1BF3` as `A=9`, which is
**status 10 → Report J — Invalid I/O device**:

| A at `0x1BF3` | Status | Report |
|---|---|---|
| 8 | 9 | 9 — STOP statement |
| **9** | **10** | **J — Invalid I/O device** ← the internal error-9 path |

Verify by simulating the `DEC A` chain (see the table above, which was generated
that way). Semantically this is correct and reassuring: "the device did not
respond" *should* be Report J, not "STOP statement".

**So `LOW-LEVEL-PROTOCOL-V5.TXT:195-196` is right** when it promises "ERROR J -
INVALID I/O DEVICE (TIMEOUT CONDITION) IS RETURNED AUTOMATICALLY".

Note the code laundering: `WAIT_PICO_READY` returns `A=02h` on timeout, but callers
discard it and substitute 9. The `A=02h` value is only visible through the
documented BIOS entry `WF_NPH` at `0x184C`. One path differs: `0x1C40`'s timeout
goes `→ 0x1B87 → 0x1C3E` = **Report R — Tape loading error**. So a stalled Pico
reports **J** from most paths and **R** from the key-send path.

## FUNCTION requests (status ≥ 0x80)

The Pico can ask the Z80 to render output or collect input. Dispatch is a linear
`CP`/`JR NZ` chain starting at **`0x026F`** (chunk 0), continuing at `0x2194`
(chunk 1). Remember: **`A = status - 1`**.

| ROM test | A | Status | Documented function | Handler |
|---|---|---|---|---|
| `026F: CP 80h` | `0x80` | **0x81** | PRINT STRING IN MAIN SCREEN | `0274` |
| `2194: CP 81h` | `0x81` | **0x82** | PRINT STRING & RETURN A KEY | `2198` |
| `21A4: CP 82h` | `0x82` | **0x83** | PRINT CHARACTER | `21A8` |
| `21BA: CP 83h` | `0x83` | **0x84** | RETURN KEY | `21BE` |
| `21C7: CP 84h` | `0x84` | **0x85** | GET STATUS | `21CB` |
| `21DF: CP 85h` | `0x85` | **0x86** | PRINT STRING WITH LOOP (Y/N) | `21E3` ← v1.5w patch |
| `21FD: CP 86h` | `0x86` | **0x87** | PRINT n CHARACTERS | `2201` |
| `2213: CP 86h` | `0x86` | — (dup) | **BUG — unreachable; handler beeps** | `2216` — dead |

### Why we know the offset is `status - 1`

Four independent structural confirmations, not one:

1. **`DEC A` at `0x228A` literally precedes `CALL 026F` at `0x228C`.** Direct proof.
2. **The `0x82` handler is the `0x81` handler plus a key fetch.** `CP 80h` → `CALL
   02B9; CALL 04F1; JP 045F`. `CP 81h` → the same three, then `CALL 0471`. The docs
   define `0x82` as `0x81` *"& RETURN A KEY"*. Exact structural match.
3. **The `CP 83h` handler is nothing but `CALL 0471`** — matching `0x84` = "RETURN
   KEY".
4. **The `CP 84h` handler builds a 2-bit mask and sends it back** (`CALL 025E; LD
   L,A; CALL 026A; ADD A,A; OR L; CALL 229D`) — matching `0x85` = "GET STATUS
   (B0=KEYBOARD / B1=AUX / B2=PRINTER / B3=DISK)".

The same convention holds for the error dispatcher at `0x1BF3` (`status 2` → `A=1`
→ `DEC A` → Z → Report R).

### **BUG: the second `CP 86h` is unreachable**

Present in **both v1.1 and v1.5w** (bytes `fe 86 c0` at `0x2213` in each).

```asm
21FD: FE 86     CP 86h
21FF: 20 12     JR NZ,2213      ; only reached when A != 0x86
2201: CD B9 02  CALL 02B9
2204: F5        PUSH AF
2205: CD 0A 22  CALL 220A       ; -> thunk to HOME 08A6
2208: F1        POP AF
2209: C9        RET             ; <-- A == 0x86 always returns here

2213: FE 86     CP 86h          ; <-- can never be true: A != 0x86 by construction
2215: C0        RET NZ          ; <-- therefore always returns
2216: CD B9 02  CALL 02B9       ; <-- DEAD CODE
2219: F5        PUSH AF
221A: CD 3F 20  CALL 203F       ; BEEPER (relocated from HOME 0x03F3)
221D: F1        POP AF
221E: C9        RET
```

`0x2213` is only reached via `JR NZ` from `0x21FF`, i.e. when `A != 0x86`. So
`CP 86h` there is *necessarily false*, `RET NZ` always fires, and the handler at
`0x2216` can never execute. **The unreachability is mechanically certain.**

**What it *should* be is genuinely unclear**, and the obvious guess does not survive
scrutiny:

- The tidy hypothesis is `0x2213` should read `CP 87h` (= status `0x88` = CLEAR
  SCREEN & HOME CURSOR). The chain otherwise covers statuses `0x81`-`0x87`
  contiguously, and `0x88` is the only documented function missing.
- **But the dead handler calls `0x203F`, which is the `BEEPER`** — relocated
  verbatim from genuine HOME `0x03F3` (see
  [DIFF_EXROM_vs_STOCK.md](DIFF_EXROM_vs_STOCK.md#chunk-1-entirely-new-0x2000-0x22ad)).
  It reads `BORDCR` only to preserve the border while toggling the speaker. **A
  routine that beeps is not "CLEAR SCREEN & HOME CURSOR."**

So either the `CP` value is wrong, or the handler body is wrong, or this is an
unfinished "beep" function that never made it into the spec. **Don't patch it on the
strength of the `0x88` guess** — ask Gustavo what `0x2216` was meant to do.

This does partly answer `EXTCMD_PROTOCOL.md`'s open Q1 ("what does the 2068 ROM do
with status `0x80`, `0x87`-`0xFF`?"): `0x87` works; **status `0x88` reaches no
handler**; `0x89`+ falls through the chain entirely.

### `0x2000-0x203E` is a relocation landing pad, **not** an API table

Easy to misread as an entry-point table. It is not — it is filler around **one
address-pinned routine**.

Genuine HOME `0x0A4A` (the printer line driver) contains `CALL 2009` — a call to
HOME's own BREAK_KEY. Gustavo copied that driver verbatim into the EXROM at
`0x17DC`, **keeping `CALL 2009` untouched**. So EXROM `0x2009` *must* hold a copy of
BREAK_KEY, at exactly that address. It does.

```
genuine HOME 0A4A: 78 fe 03 9f e6 02 d3 fb 57 cd 09 20 ...
TSPICO EXROM 17DC: 78 fe 03 9f e6 02 d3 fb 57 cd 09 20 ...
                                              ^^^^^^^^ CALL 2009, copied verbatim
```

| Addr | Bytes | Meaning |
|---|---|---|
| `0x2000` | `C3 3F 20` | `JP 203F` → **`BEEPER`**. The only live entry. Called from HOME `0x03F6` via the `0x03FC` thunk; no EXROM-internal reference. |
| `0x2003`, `0x2006` | `JP` self | padding stub |
| `0x2009-0x201D` | 21 B | **`BREAK_KEY`** — address-pinned copy of HOME's. Called only from `0x17E5`. |
| `0x201E-0x2026` | 9 B | `LD A,20h; OUT (0Fh),A; XOR A; OUT (0Fh),A; POP AF; RET` — **dead, unreachable** |
| `0x2027`-`0x203C` | 8× `JP` self | padding stubs |
| `0x203F` | — | `BEEPER` |

The ten `JP`-to-self stubs are **padding that keeps `0x2009` at its required
address**, written to hang rather than run into garbage if ever called. They are not
unimplemented API slots.

### The real API table: TPI BIOS at `0x1840`

A `JR`/`JP` table, for HOME and user code — **zero EXROM-internal references**.
`G_VERS` at `0x1852` is `LD BC,0015h; RET`, so the **TPI BIOS version is `0x0015`
(21)** — matching the `0x15` byte planted at HOME `0x0065`.

| Addr | Name | → | Purpose |
|---|---|---|---|
| `0x1840` | `G_MODE` | `0x1856` | get TP_MODE |
| `0x1842` | `S_MODE` | `0x1862` | set TP_MODE |
| `0x1844` | `G_VERS` | `0x1852` | version → `BC = 0x0015` |
| `0x1846` | `TX_A` | `0x186D` → `JP 229D` | send byte |
| `0x1848` | `RX_A` | `0x186A` → `JP 2298` | receive byte |
| `0x184A` | `C_END` | `0x184F` | end command |
| `0x184C` | `WF_NPH` | `JP 1A54` | wait for ready |
| `0x184E` | `EWAIT` | `JP 2279` | wait + read status |

**`0x184C` is the only route by which `WAIT_PICO_READY`'s `A=02h` timeout code is
observable** — every internal caller discards it.

**Both v1.1 and v1.5w report BIOS version `0x0015`**, so the version byte **cannot**
distinguish them. Use the md5, or the byte at `0x21F5` (`e7` = v1.1, `a1` = v1.5w).

## Block types and TADDR

Byte 0 of the pre-header, `LOW-LEVEL-PROTOCOL-V5.TXT:282-296`:

| Value | Meaning |
|---|---|
| `0x00` | Pre-header block (SLVM) |
| `0xFF` | Data block (SLVM) |
| `0x42` `'B'` | BASIC command block |
| `0x43` `'C'` | CP/M CBIOS command |
| `0x44` `'D'` | Data block |
| `0x45` `'E'` | Extra data (reserved) |
| `'X'`/`'Y'`/`'Z'` | User-defined (reserved) |

> **Spec typo:** `'A'` (assembler command) is listed as `0x42`, but `'A'` is `0x41`
> and `0x42` is `'B'`. `GUSTAVO_PROTOCOL.md:160` copies the error. Trust neither for
> `'A'`.

Byte 1, TADDR — **not synthesized**; the ROM reads it straight from the stock
Spectrum `T-ADDR` sysvar (`0x5C74`) low byte, which stock `SAVE-ETC` already
populates. Gustavo extended the existing mechanism rather than replacing it.

| Value | Op | | Value | Op |
|---|---|---|---|---|
| `0x00` | SAVE | | `0x06` | NEW (reserved) |
| `0x01` | LOAD | | `0x07` | RUN (reserved) |
| `0x02` | VERIFY | | `0x08` | SET SNAP FILENAME |
| `0x03` | MERGE | | `0x09` | SAVE SNAP |
| `0x04` | COPY | | `0x0A` | LOAD SNAP |
| `0x05` | LPRINT | | | |

## The `'B'` pre-header, as actually built

Builder at `0x1BA0`. This emits bytes in spec order and matches the spec's own
`SAVE "TPI:DELETE" CODE 4386,13124` trace (PMR1 = `0x1122` = 4386, PMR2 = `0x3344`
= 13124):

| Byte | Source | Field |
|---|---|---|
| 00 | `LD A,42h` | BLOCK TYPE `'B'` |
| 01 | `(0x5C74)` | TADDR |
| 02 | `(0x5DCF)` | BANK |
| 03-04 | `(0x5DD7)` | PMR1 |
| 05-06 | `(0x5DD9)` | PMR2 |
| 07 | `B` | COMND LEN low |
| 08 | `(0x5DCE)` | COMND LEN high |
| 09 | `D` | CRC |

> **Doc trap:** `GUSTAVO_PROTOCOL.md:132-140` presents *one* pre-header layout
> (bytes 3-4 SESSION_ID, 5-6 MEMORY_ADDR, 7-8 BLOCK_LEN) as universal. That is the
> **SLVM** layout only. For `BLOCK_TYPE='B'` the ROM puts **PMR1/PMR2** in bytes
> 3-6 and there is **no session ID at all**. Two different layouts share byte
> positions.

**CRC** is register `D`, seeded with byte 0 and XOR-folded per byte by the send
helper:

```asm
1B7E: CD 9D 22   SEND_BYTE_CRC:  CALL 229D      ; OUT (0Eh),A
1B81: 38 03                      JR C,1B86
1B83: AA                         XOR D
1B84: 57                         LD D,A         ; D ^= byte
1B85: C9                         RET
```

## TS-PICO system variables

**The docs name none of these.** All recovered from the disassembly.

| Addr | Size | Holds |
|---|---|---|
| `0x5DCD`/`0x5DCE` | 16 | COMND/BLOCK LEN, decremented as the body streams |
| `0x5DCF` | 8 | BANK number (`0xFF` = HOME) |
| `0x5DD1` | 16 | SESSION ID |
| `0x5DD3` | 16 | command-string address |
| `0x5DD5` | 16 | command-string length |
| `0x5DD7` | 16 | PMR1 (e.g. `CODE` start) |
| `0x5DD9` | 16 | PMR2 (e.g. `CODE` length) |
| `0x5DDB` | 8 | device/mode flags — bit7 = TPI/NET active, bit6 = NET vs TPI |
| `0x5D37` | 16 | unclassified |

Stock sysvars the TS-PICO leans on:

| Addr | Stock name | Use |
|---|---|---|
| `0x5C74` | `T-ADDR` | low byte reused directly as TADDR |
| `0x5C78` | `FRAMES` | source of SESSION ID |
| `0x5C48` | `BORDCR` | read by `BEEPER` at `0x203F` to preserve the border |
| `0x5C65` | `STKEND` | fetch BASIC string param |
| `0x5C5D`/`0x5C5F` | `CH_ADD`/`X_PTR` | `RST 08` ERROR-1 |
| `0x5C3A` | `ERR_NR` | via `(IY+0)` |

**SESSION ID is not random.** `GUSTAVO_PROTOCOL.md:309` calls it "some random
16-bit value". It is `FRAMES` incremented until non-zero (`0x1A73`):

```asm
1A75: 2A 78 5C   LD HL,(5C78)     ; FRAMES
1A78: 23         INC HL
1A79: 7C         LD A,H
1A7A: B5         OR L
1A7B: 28 FB      JR Z,1A78        ; force non-zero
1A7D: 22 D1 5D   LD (5DD1),HL
```

The non-zero forcing is deliberate — `LOW-LEVEL-PROTOCOL-V5.TXT:173-176` reserves
session `0000` for "not generated from a BASIC command".

## An undocumented `NET:` device

Prefix parsing at `0x1A73`+ masks with `0x5F` (uppercase) and recognises **two**
device prefixes:

- `"TPI"` → `0x5DDB` bit 7 set, bit 6 clear
- `"NET"` → `0x5DDB |= 0xC0` (bits 7 and 6)

**`NET:` appears in no document in `docs/`.** Whether the Pico side implements it
is unknown from the Z80 side alone.

## Doc-vs-ROM discrepancies

Ranked by how likely they are to burn you.

1. **The `~20s` timeout figure is right; the *explanation* for it is wrong.**
   `GUSTAVO_PROTOCOL.md:285-288` says the shipped counter "is larger" than the
   disassembly's `B=0xE2`. It is not — the shipped binary has `06 e2` at `0x1A56`.
   The ~20s comes from each poll costing ~88 ms, not from a bigger counter. Anyone
   who checks the counter and concludes "milliseconds" (as this analysis initially
   did) is also wrong. Both facts are true at once. `DEVELOPER_GUIDE.md:320-322`'s
   "~700 ms (256 retries)" matches neither.
2. **`'B'` pre-header carries PMR1/PMR2 in bytes 3-6, not SESSION_ID/MEMORY_ADDR**
   (`GUSTAVO_PROTOCOL.md:132-140` shows the SLVM layout as universal).
3. **The second `CP 86h` at `0x2213` is unreachable**, so status `0x88` reaches no
   handler. Both versions. Documented nowhere. See above — the dead handler
   *beeps*, so the fix is not the obvious one-byte one.
4. **`'A'` block type listed as `0x42`; `'A'` is `0x41`**
   (`LOW-LEVEL-PROTOCOL-V5.TXT:289`, copied into `GUSTAVO_PROTOCOL.md:160`).
5. **Function codes `0x87`/`0x88` are missing from `GUSTAVO_PROTOCOL.md:245-252`**,
   which stops at `0x86` — they partly answer `EXTCMD_PROTOCOL.md`'s open Q1.
6. **`0xF4` is the horizontal *select* register, not "horizontal scroll"**
   (`GUSTAVO_PROTOCOL.md:86-87`).
7. **SESSION ID is `FRAMES`-derived, not random** (`GUSTAVO_PROTOCOL.md:309`).
8. **`NET:` device prefix exists in the ROM** and in no doc.
9. **No `0x43` `'C'` (CP/M) or `0x45` `'E'` frame is ever emitted** — those block
   types are unimplemented in this ROM.
10. **`0x5DCF` is BANK and `0x5DD1` is SESSION_ID.**
    `TS2068 Ref Library/gus-rom-analysis.md` calls them "TPTYPE" and "TPLEN" — both
    wrong.
11. **`OUT (0Fh),A` never executes.** All three sites sit in unreferenced code
    (verified by absolute-reference scan *and* exhaustive JR/DJNZ displacement scan
    at every alignment). Port `0x0F` is read-only in practice, as the spec says.

**Corrections to the corrections.** Two claims in earlier drafts of this file were
my own errors, now fixed above: that the timeout is milliseconds (it is ~20 s), and
that internal error 9 yields Report 9 (it yields Report J). Both came from reading
one instruction without following the call chain. If you are re-deriving any number
here, follow it all the way down.

Also: **debug ports 30/31 (`0x1E`/`0x1F`)** described at
`LOW-LEVEL-PROTOCOL-V5.TXT:198-209` have **zero hits in either binary** — both v1.1
and v1.5w are non-debug builds. And `OPEN_QUESTIONS.md:38-40`'s note that port
`0x0A` isn't routed through PICOSEL (issue #9) is consistent with the ROM: nothing
addresses `0x0A`.

## Open questions

- **The five NOPs at `0x1A63-0x1A67`** in `WAIT_PICO_READY`'s timeout exit,
  preceded by a dead `LD A,40h` (`0x40` = the READY bit pattern). ~5 bytes were
  deliberately removed. Not recorded in `docs/`.
- **`LD C,0Eh` at `0x227F` is dead** — `0x2298` uses the immediate form
  `IN A,(0Eh)`, not `IN A,(C)`. A remnant of a register-indirect version, matching
  the finding that no register-indirect I/O survives anywhere.
- **`PUSH AF; XOR A; POP AF` at `0x1BEE-0x1BF0`** is a no-op — another remnant.
- **Ten deliberate halt stubs**, each `JP <itself>`: `0x2003`, `0x2006`, and
  `0x2027`/`0x202A`/`0x202D`/`0x2030`/`0x2033`/`0x2036`/`0x2039`/`0x203C`. These are
  unimplemented slots in the chunk-1 entry table at `0x2000` — **calling one locks
  the machine hard** (no BREAK, no timeout). Only `0x2000` (`JP 203F`) is live.
  Worth knowing if you are chasing an unexplained freeze: an errant call into the
  entry table looks exactly like a crash.
- **Whether `0x0351`'s `LD HL,21E7`** is a live vector-table entry into the Y/N loop
  or coincidental data. If live, there may be a second path into the loop that the
  v1.5w patch also affects.
