# TS-PICO ROM analysis

Reverse-engineering resources for the TS-PICO's modified TS2068 HOME and EXROM
images: what Gustavo changed relative to the genuine ROMs, what changed between the shipping
ROM (v1.1) and the next one (v1.5w), and how the Z80↔Pico protocol is actually
implemented in silicon rather than as documented.

**These are troubleshooting references.** When ROM behaviour and
[`docs/`](../) protocol notes disagree, the ROM is ground truth — the disassembly
here is what the hardware actually runs.

## Start here

| If you want to know… | Read |
|---|---|
| What's different about v1.5w, and should I ship it | [DIFF_V11_vs_V15W.md](DIFF_V11_vs_V15W.md) |
| How the ROMs are laid out, banked, and how HOME calls EXROM | [MEMORY_MAP.md](MEMORY_MAP.md) |
| The Z80↔Pico wire protocol as implemented | [PROTOCOL_FROM_ROM.md](PROTOCOL_FROM_ROM.md) |
| What TS-PICO changed in the EXROM vs genuine | [DIFF_EXROM_vs_STOCK.md](DIFF_EXROM_vs_STOCK.md) |
| What TS-PICO changed in the HOME ROM vs genuine | [DIFF_HOME_vs_STOCK.md](DIFF_HOME_vs_STOCK.md) |
| Whether a baseline ROM is trustworthy | [DIFF_HOME_vs_STOCK.md#baseline](DIFF_HOME_vs_STOCK.md#baseline) |
| A specific address — what lives there | [SYMBOLS.md](SYMBOLS.md) |

## The findings that matter most

1. **v1.1 → v1.5w is 15 bytes.** The HOME ROMs are byte-identical; the EXROM
   differs by two hunks. It closes a half-duplex synchronization hole in the Pico's
   Y/N prompt (function `0x86`): the Z80 sends the user's keypress and then
   immediately reads the Pico's next string back without waiting for ready. v1.5w
   inserts the missing wait and adds a bounded (~20 s), BREAK-abortable exit
   reporting `J Invalid I/O device`. It contains the failure; it does not fix the
   root cause.

2. **The TS-PICO EXROM is 16K, not 8K**, and needs TS2068 chunks 0 **and** 1
   mapped simultaneously — the two halves call each other directly, 48 times one
   way and 34 the other. Any tool that models the EXROM as 8K will break. This is
   why ZEsarUX's EXROM has to be widened.

3. **Chunk 0 is 98% full; chunk 1 is 92% empty.** The genuine EXROM's 1024-byte
   hole at `0x1800-0x1BFF` was filled with the core Pico driver, the repeated stock
   call-into-HOME thunk was factored down from 21 bytes to 9 to reclaim ~600 more,
   and only then was the ROM widened. New code should go at `0x22AE`+, where 7.5K
   is free and nothing needs to move.

4. **The ready-wait timeout is ~19.9 seconds** — and it is the most misread number
   in the ROM. `LD B,0E2h` is only 226 polls, but **each poll costs ~88 ms** because
   the status read goes through a debounced keyboard scan. So the Z80 samples port
   `0x0F` only ~11×/second, and every wait costs ≥88 ms even on success. Run
   `python3 tools/wf_nph_timing.py`. Ten more doc-vs-ROM discrepancies are in
   [PROTOCOL_FROM_ROM.md](PROTOCOL_FROM_ROM.md#doc-vs-rom-discrepancies).

5. **A dispatch bug leaves status `0x88` unhandled**, in *both* v1.1 and v1.5w.
   `CP 86h` appears twice in the function chain (`0x21FD`, `0x2213`); the second can
   never match, so its handler at `0x2216` is dead code. The obvious "should be
   `CP 87h`" fix doesn't quite fit — the dead handler *beeps* rather than clearing
   the screen. Ask Gustavo before patching.

6. **The reference "stock" ROMs are not stock.** Both images in
   `TS2068 Ref Library/2068 ROMS/` are a modified EPROM dump. Everything here has
   been re-based on genuine images; see the caveat below, because this likely
   affects other analyses too.

## Reading conventions

Two things trip up every reader of this ROM:

- **The Pico's status byte is decremented before dispatch** (`DEC A` at `0x228A`),
  so every `CP nn` in the function chain matches status **`nn+1`**. `CP 85h` is
  function `0x86`.
- **File offset == Z80 address** in all six images. No headers, no relocation.

## Files

```
docs/rom-analysis/
  README.md                  this file
  MEMORY_MAP.md              image layout, banking, cross-ROM thunks, I/O ports
  DIFF_V11_vs_V15W.md        the 15-byte shipping-vs-next delta, fully decoded
  DIFF_EXROM_vs_STOCK.md     36 chunk-0 hunks + the all-new chunk 1
  DIFF_HOME_vs_STOCK.md      10 hunks: tape/printer hooks, 16K banking, thunk
  PROTOCOL_FROM_ROM.md       ports, handshake, functions, errors, sysvars
  SYMBOLS.md                 address -> name/purpose, for both ROMs
  tspico-exrom-symbols.sym   curated symbol names, as z80dasm input
  hunks.json                 machine-readable diff hunks
  disasm/                    generated listings (see caveat below)
    tspico-1{1,5w}-exrom.labelled.asm   <- read these: named, not bare addresses
    *.asm / *.sym                       <- raw linear sweeps
```

Regenerate everything:

```bash
python3 tools/romdiff.py --json docs/rom-analysis/hunks.json   # diff hunks
./tools/romdisasm.sh                                           # disassemblies
```

The `.labelled.asm` listings apply `tspico-exrom-symbols.sym`, so the v1.5w fix
reads as `jp nz,YN_LOOP_GUARD` / `call WAIT_PICO_READY` rather than raw addresses.
Add names to that file and re-run to improve them.

## ROM images

Copied into [`ROMs/`](../../ROMs/) so this analysis is self-contained and
reproducible.

| File | Size | md5 | Provenance |
|---|---|---|---|
| `TSPICO-11-home` | 16384 | `620d6ded106839b73dd6dac9f98f7ed9` | Shipping today |
| `TSPICO-15w-home` | 16384 | `620d6ded106839b73dd6dac9f98f7ed9` | Identical to v1.1 |
| `TSPICO-11-exrom` | 16384 | `b4a1596823dfda0f9b8dc3d2dec816cb` | Shipping today |
| `TSPICO-15w-exrom` | 16384 | `639c62742fa388750a0624e1270e1583` | Planned next |
| `GENUINE-2068-exrom.bin` | 8192 | crc32 `ae16233a` | `zesarux/src/ts2068.rom` bytes 16384-24575 |
| `GENUINE-2068-home.bin` | 16384 | crc32 `bf44ec3f` | `zesarux/src/ts2068.rom` bytes 0-16383 |
| `WJ-2068-exrom.bin` | 8192 | `e3863481d1273af637922415e96dbb0b` | `2068Exrom.BIN` — **not stock**, reference only |
| `WJ-2068-home.bin` | 16384 | `6843dfddc231083e2220b6b11424eb8d` | `2068Home.BIN` — **not stock**, reference only |

`tools/romdiff.py` verifies every image's crc32 on each run and shouts if one is
wrong, so a swapped baseline cannot silently corrupt the analysis again.

## Reproducing

```bash
python3 tools/romdiff.py                          # hunk report for every pair
python3 tools/romdiff.py --json docs/rom-analysis/hunks.json
```

Disassemblies were produced with `z80dasm` (Homebrew), org 0 for every image
since file offset == Z80 address throughout:

```bash
z80dasm -a -l -t -g 0x0000 -o out.asm -s out.sym ROMs/TSPICO-11-exrom
```

## Caveats — read before trusting anything here

- **`disasm/*.asm` are linear sweeps.** z80dasm disassembles straight through, so
  data tables, text, and `0xFF` filler decode as nonsense instructions, and a
  misaligned start can desynchronise a whole region. Treat them as a raw index for
  locating code, and trust the hand-verified listings in the Markdown docs over
  them. Always re-derive alignment from a known-good anchor before believing a
  disassembly line.

- **Naive `IN`/`OUT` scans lie.** Searching for `DB xx`/`D3 xx` opcode bytes finds
  mostly false positives — `db 5d` is nearly always the low byte of a
  `LD (5Dxx),A` referencing a TS-PICO system variable. The genuine TS-PICO port
  I/O sites are `0x0E` at `0x2298`/`0x229D` and `0x0F` at `0x065B`, `0x2020`,
  `0x2023`, `0x2236`.

- **The ROMs in `TS2068 Ref Library/2068 ROMS/` are NOT stock**, despite their
  names — both are a modified, partly bit-rotted EPROM dump ("W.J."). This was
  discovered mid-analysis and everything here has been re-based on the genuine
  images. **If you find older TS-PICO ROM analysis — anywhere — check what it used
  as its baseline.** Diffing against the W.J. images invents ~150 phantom bytes of
  "TS-PICO changes" in HOME (a redrawn font, a rewritten copyright message, FP
  bug-fixes) and fabricates alarming ones in the EXROM (e.g. that TS-PICO
  bank-switches with interrupts enabled — it does not). Full story and proof:
  [DIFF_HOME_vs_STOCK.md#baseline](DIFF_HOME_vs_STOCK.md#baseline).

- **Command names and semantics are inferred** from the ROM's own dispatch
  structure and cross-referenced against [`docs/`](../); where the ROM and the docs
  disagree, the disagreement is flagged rather than reconciled. Speculation is
  marked as such throughout.
