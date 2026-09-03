# Native disk commands for the TS-PICO

**Status: design proposal. Nothing here is implemented.**

Adds `CAT`, `FORMAT`, `MOVE`, `ERASE` and — the harder half —
`OPEN #`/`CLOSE #`/`PRINT #`/`INPUT #` file I/O as native BASIC statements
on the TS-2068, backed by the SD card rather than by a mounted TAP image.

The reference point is the **FDD 3000** (TMX Portugal, 1985), whose 4K DOCK
cartridge ROM added exactly these commands to TS-2068 BASIC. This document says
what to take from that design, what to reject, and what has to be built on each
side of the wire.

> **Scope note.** We are *not* reproducing the FDD 3000's command syntax, which
> is derived from the ZX Interface 1 and carries a device-type argument
> (`"m";1;"name"`). The TS-PICO has one storage device. Syntax is ours to choose.

## Start here

| If you want… | Read |
|---|---|
| Why the ROM hook is three bytes and not a trampoline | [§2](#2-the-hook-the-home-rom-already-does-most-of-the-work) |
| The overall split of work | [§3](#3-architecture) |
| The cheap first milestone | [§4](#4-phase-1--statement-shortcuts) |
| The part that needs real design | [§6](#6-phase-3--channel-io) |
| The number that will wreck a naive implementation | [§6.2](#62-the-load-bearing-constraint-handshake-latency) |
| What we don't know yet | [§9](#9-open-questions-and-things-to-verify) |
| Every claim's provenance | [§10](#10-appendix--verified-facts) |

Conventions from [`rom-analysis/README.md`](rom-analysis/README.md) apply: file
offset == Z80 address in every ROM image, and **where docs and the ROM disagree,
the ROM wins**. Facts below are marked **[verified]** (derived from a shipping
binary in this repo, reproducible via the appendix) or **[inferred]**.

---

## 1. What the FDD 3000 did, and what we take from it

The FDD 3000's DOCK ROM works like this **[verified]**:

1. At boot it overwrites 7 bytes of **RAM** at `$658C` — inside the TS-2068's
   RAM-resident bank-dispatch block — replacing `JP (IX)` with a relay that
   fires `RST $08` to page the DOCK cartridge in (`INSTALL_HOOK`, `$0EF6`; the
   `DD E9` is restored later at `$0F10`).
2. Once paged in, `CMD_INTERCEPT` (`$0045`) scans **backwards** from `CH_ADD`
   for the first token ≥ `$A5`, and looks it up in a command table at `$0264`.
3. A matched token must be followed by `*` (`CP '*'` at `$00A3`) — the Interface 1
   convention, `CAT *`, `LOAD *"name"`.
4. Parsing then runs a tiny descriptor VM. Each table entry is

   ```
   token, descriptor..., $FE, stack_adjust, exec_lo, exec_hi
   ```

   where each descriptor byte is a *byte offset* into a 16-entry jump table of
   parse routines at `$00DA`. Descriptor `$04` additionally consumes an inline
   NUL-terminated character list from the table itself (`"IOAR"`, `"PUVI"`,
   `"#"`): its routine at `$0129` recovers the saved table pointer off the
   stack, walks the list, and writes the advanced pointer back.

**Take:** the table-driven statement dispatcher. It is compact, it keeps parsing
declarative, and adding a command is a table row plus a handler.

**Reject, in order of importance:**

- **The RAM patch and the `RST $08` trampoline.** Those exist because a DOCK
  cartridge physically cannot modify the HOME ROM. We ship the HOME ROM. See §2.
- **Intercepting the `PRINT` and `INPUT` tokens.** The FDD 3000 has table entries
  for `$F5` (PRINT) and `$EE` (INPUT), each with an inline `"#"` character list
  **[verified]** — it re-implements the statements rather than installing a
  channel. That means re-implementing PRINT item lists, separators, `AT`/`TAB`,
  and INPUT's line editor and variable assignment. Sinclair BASIC already routes
  `PRINT #`/`INPUT #` through channels; we should use that. See §6.1.
- **The `keyword *` syntax.** It exists to disambiguate a bolt-on device. We have
  no such need, and `CAT` reading better than `CAT *` is worth something.

> **Do not trust `fdd3000_annotated.asm`'s annotations.** The comments in that
> listing are machine-generated and wrong in load-bearing places: the command
> table decode is garbage, the SAVE and LOAD parse/exec pairs are swapped, one
> parse-table entry is transcribed as `$089E` when the ROM says `$079E`, and
> `CLOSE_HANDLER`'s "restores STRMS entries" comment is wrong (`$5C82`/`$5C86`/
> `$5C8A` are `ECHO_E`/`DF_CCL`/`SPOSNL`, screen-position variables). The
> `DEFB` bytes are faithful to `3000_2068.ROM`; the prose is not. A corrected
> decode of the command table is in [§10.3](#103-fdd-3000-command-table-decoded).

---

## 2. The hook: the HOME ROM already does most of the work

This is the finding that makes Phase 1 cheap.

`CAT`, `FORMAT`, `MOVE` and `ERASE` are **already in the TS-2068 token table** at
`$CF`–`$D2`, and the statement dispatcher already routes them **[verified]**.
Statement dispatch subtracts `$CE` from the token (`1A71: sub 0ceh`) and indexes
a syntax offset table at `$1945`; the resulting parameter-table entries send the
four commands to `$25C8`, `$25CC`, `$25D0` and `$25D4`. Those four addresses are
one routine:

```asm
25C8: 06 CF     LD B,$CF      ; CAT     ─┐
25CA: 18 0A     JR $25D6       │
25CC: 06 D0     LD B,$D0      ; FORMAT ─┤  all fall through
25CE: 18 06     JR $25D6       │          to the same stub
25D0: 06 D1     LD B,$D1      ; MOVE   ─┤
25D2: 18 02     JR $25D6       │
25D4: 06 D2     LD B,$D2      ; ERASE  ─┘ (falls through)
25D6: CD 89 28  CALL $2889    ; = BIT 7,(IY+1); RET   -- run-time?
25D9: 20 06     JR NZ,$25E1
25DB: CD 69 25  CALL $2569    ; syntax pass: skip to end of statement
25DE: CD 44 1B  CALL $1B44
25E1: C3 67 25  JP  $2567     ; RST $08 + error byte
```

Timex loads **the token into `B` and then raises an error**. `B` is of no use to
an error handler. That stub was staged as an extension point — almost certainly
for the FDD 3000 — and it is **byte-identical in `GENUINE-2068-home.bin` and
`TSPICO-11-home`**, so nothing in the TS-PICO ROM has claimed it.

**The hook is therefore a 3-byte patch at `$25D6`**, redirecting `CALL $2889`
into the EXROM with the token already in `B`. No RST trampoline, no RAM patch,
no error-path interception, no backward token scan.

### But the parameter table has to be patched too **[verified in ZEsarUX]**

The stub is only reached if the statement's *syntax classes* are satisfied first,
and they are not satisfied by a bare keyword. The parameter-table entry for `CAT`
is `0A 2C 05 C8 25`: class `$0A`, then a literal `,` (any table byte ≥ `$20` is a
separator that must be present — `1AA2: CP 20h` / `1AB2: RST 18h; CP C; JP NZ,1BED`),
then class `$05` with routine `$25C8`. Measured on the shipping ROM by counting
arrivals at `$25C8`:

| Line | reaches `$25C8`? | result |
|---|---|---|
| `CAT` | **no** | `CAT ?` — syntax error |
| `CAT "x"` | **no** | `CAT "x"?` — syntax error |
| `CAT "x",` | **yes** (2×) | accepted |

So bare `CAT` never gets near the hook. The fix is one byte per command, in the
**syntax offset table**, advancing each entry two bytes past the `0A 2C` prefix so
it starts at the `class $05 + routine` pair — class `$05` means *the routine checks
its own syntax*, which is exactly what our handler wants:

| Addr | Command | Offset | Entry becomes |
|---|---|---|---|
| `$1946` | CAT | `$D0` → `$D2` | `$1A18` = `05 C8 25` |
| `$1947` | FORMAT | `$C0` → `$C2` | `$1A09` = `05 CC 25` |
| `$1948` | MOVE | `$C4` → `$C6` | `$1A0E` = `05 D0 25` |
| `$1949` | ERASE | `$C8` → `$CA` | `$1A13` = `05 D4 25` |

Nothing moves and no table grows — the target bytes already exist inside the
current entries. Verified in ZEsarUX on a patched image: bare `CAT` now reaches
`$25C8` twice (syntax pass and run pass) and the line is accepted; bare `ERASE`
reaches `$25D4`; `LOAD ""` still parses and runs unchanged.

**Total HOME ROM footprint: 7 bytes** — 3 at `$25D6`, 4 in the offset table.

`OPEN #` (`$D3`) and `CLOSE #` (`$D4`) are better still: they already *parse*,
routing to `$142A` and `$139F` respectively **[verified]**, both unmodified in
the TS-PICO HOME ROM. Their parameter-table entries are

| Token | Entry | Bytes | Reading **[inferred]** |
|---|---|---|---|
| `$D3` OPEN # | `$19FD` | `06 2C 0A 05 2A 14` | numeric, `,`, string, routine `$142A` |
| `$D4` CLOSE # | `$1A03` | `06 00 9F 13` | numeric, routine `$139F` |

So for streams we do not add a statement at all — we extend which channel
specifier strings `$142A` accepts, exactly as the Interface 1 does for `"m"`.

### Where the code goes

| Region | Space | Use |
|---|---|---|
| EXROM `$22AE`–`$3FFF` | **7,506 bytes free** | all new Z80 code |
| HOME ROM | effectively none | 7 bytes of hook patches only (§2) |
| RAM below `RAMTOP` | allocated at install | channel driver + per-channel buffers (§6) |

Per [`rom-analysis/MEMORY_MAP.md`](rom-analysis/MEMORY_MAP.md), appending at
`$22AE` displaces nothing and moves no existing address — the same
append-and-retarget pattern the v1.5w fix used.

---

## 3. Architecture

```
   BASIC statement                    TS-PICO firmware (MicroPython)
   ───────────────                    ──────────────────────────────
   CAT / ERASE / MOVE / FORMAT
        │ HOME hook: 3 bytes @ $25D6 + 4 in the syntax offset table
        ▼
   EXROM $22AE+  parse args
        │  synthesise "TPI:DIR ..." etc.
        │  point $5DD3/$5DD5 at it, set T-ADDR
        ▼
   existing $1A73 → $1BA0 'B' block ──────────►  PROCESS_CMD  →  SA_funct{}
                                                      │
   PRINT #4 / INPUT #4                                ▼
        │ stock BASIC channel dispatch          open-file table
        ▼                                       {handle: (file, mode, pos)}
   RAM channel driver  ◄── buffered blocks ───────────┘
        (direct port $0E/$0F, own wait loop)
```

Phase 1 adds **no new wire protocol at all**: the commands become synthesised
`TPI:` strings on the existing `'B'` BASIC-command path, which the Pico already
parses in `PROCESS_CMD` and dispatches through the `SA_funct` table. Only
Phase 3's bulk transfers need anything new.

---

## 4. Phase 1 — statement shortcuts

Scope: `CAT`, `ERASE`, `MOVE`, `FORMAT` become statements that build a `TPI:`
command string and hand it to the existing send path.

Proposed mapping (syntax is ours to choose; this is a starting point):

| Statement | Becomes | Notes |
|---|---|---|
| `CAT` | `TPI:DIR` | SD directory of the current path |
| `CAT "*.tap"` | `TPI:DIR *.TAP` | filtered |
| `CAT #` | `TPI:TAPDIR` | blocks inside the mounted TAP — see below |
| `ERASE "name"` | new `TPI:ERASE name` | **not** the existing select-then-`RM` two-step |
| `MOVE "a" TO "b"` | new `TPI:MOVE a b` | rename/move |
| `MOVE "path"` | `TPI:CD path` | debatable; see §9 |
| `FORMAT "name"` | `TPI:NEWTAP name` | create + mount a TAP |

**`CAT` needs a context rule.** There are two directories in play — the SD path
(`TPI:DIR`) and the contents of the mounted TAP (`TPI:TAPDIR`). Making bare `CAT`
mean "the SD path" and requiring a marker for the TAP listing is the least
surprising split, but this is a UX decision, not a technical one.

**`ERASE` should be one round trip.** The existing `TPI:` flow for deleting is
select-then-delete, which is racy when a statement issues both halves. Add a
Pico-side handler that takes the name directly.

Pico-side work in this phase is small: a few handlers in `SA_funct`, most of them
thin wrappers over `DIR`, `RM`, `CD`, `TAPDIR`, `NEW_TAP`. Each must honour the
V6 tail pre-load contract in `PROCESS_CMD` — handlers write their response and
return; they do **not** write their own `0x01`. See
[`EXTCMD_PROTOCOL.md`](EXTCMD_PROTOCOL.md) §3a.

**Deliverable:** one command working end to end proves the `$25D6` hook, the
EXROM append, the string synthesis, and the build pipeline (§8). Everything after
that is repetition.

---

## 5. Phase 2 — real files on the Pico

Today the Pico's storage model is tape-shaped: `MOUNT_FILE` mounts a `.tap` and
`SAVE`/`LOAD` move blocks in and out of it. Direct SD file access exists only for
management commands.

Channel I/O needs a genuine file-handle table:

```python
# handle -> record
open_files = {}   # {h: {"f": <file>, "mode": "I"|"O"|"A"|"R", "path": str}}
```

MicroPython's `open()` plus `seek()`/`tell()` gives sequential and random access
directly. The work is bookkeeping, not I/O: handle allocation, mode enforcement,
flush-on-close, closing everything on reset or on an aborted command, and
deciding what happens to open handles when the mounted TAP or current path
changes.

Control operations can ride the **existing** `'B'` string-command path with no
protocol change:

| Command | Meaning |
|---|---|
| `TPI:OPEN <h>,<mode>,<name>` | open, return status |
| `TPI:CLOSE <h>` | flush and close |
| `TPI:SEEK <h>,<pos>` | absolute byte offset |
| `TPI:EOF <h>` | end-of-file test |

Only bulk `READ`/`WRITE` need a data phase, which is Phase 3's problem. Splitting
it this way means Phase 2 is testable from BASIC with plain `SAVE "tpi:..."`
statements before any new Z80 code exists.

**Random access model:** implement absolute byte `SEEK` as the primitive and
build fixed-length records on top of it (`record N` → `seek(N * reclen)`).
Baking a record length into the protocol buys nothing and constrains later use.

---

## 6. Phase 3 — channel I/O

This is the part with real design content.

### 6.1 A channel record, not statement interception

The TS-2068 HOME ROM retains the full Sinclair stream/channel machinery
**[verified]**: `CHANS` (`$5C4F`), `CURCHL` (`$5C51`) and `STRMS` (`$5C10`) are
all live and referenced throughout the ROM. So the Interface 1 approach works:
install a channel record carrying output and input routine addresses, point a
`STRMS` entry at it, and stock `PRINT #`, `INPUT #`, `LIST #` and `INKEY$ #`
route to us with no statement interception whatsoever.

**Placement constraint:** channel routines are called with **HOME paged in**, so
they cannot live in the EXROM. Put the driver in RAM below `RAMTOP` — the FDD
3000 does the same thing with the code it downloads to `$6880`. This is not a
hardship: the TPI wire protocol from the Z80 side is `OUT ($0E),A` and a `BIT 6`
poll of `$0F`. A few hundred bytes covers the driver and its buffers.

`OPEN #` already parses (§2), so the ROM-side change is at `$142A`: accept a new
channel specifier (`"d"`, by analogy with Interface 1's `"m"`), allocate a
channel record and buffer, issue `TPI:OPEN`, and wire the `STRMS` entry.
`CLOSE #` at `$139F` flushes, issues `TPI:CLOSE`, and reclaims.

### 6.2 The load-bearing constraint: handshake latency

**Do not reuse `WF_NPH` for byte-level I/O.**

`WAIT_PICO_READY` (`$1A54`) costs **~88 ms per poll** — not because the counter
is large (`B = $E2`, 226) but because every status read routes through a
debounced keyboard scan for the BREAK check. The Z80 samples port `$0F` roughly
**11 times per second**, and *every* wait costs at least 88 ms even when the Pico
was ready immediately. Full timeout is ~19.9 s. All of this is derived and
reproducible — see [`rom-analysis/PROTOCOL_FROM_ROM.md`](rom-analysis/PROTOCOL_FROM_ROM.md)
and `tools/wf_nph_timing.py` **[verified]**.

That is perfectly fine for "one command, one message." It is fatal for
`PRINT #4;a$` inside a loop. Two consequences, both mandatory:

1. **The RAM driver polls `IN A,($0F)` directly**, with its own BREAK check on a
   sane interval rather than on every poll.
2. **Every channel is buffered.** `PRINT #` fills a RAM record buffer and flushes
   only when full or on `CLOSE #`; `INPUT #` pulls a block and serves bytes from
   RAM. This amortises one handshake over a whole block instead of over one byte,
   and it makes random access fall out for free — a seek is "give me block N."

MicroPython on the Pico side needs the same amortisation for the same reason: a
per-byte round trip through the FIFO and the interpreter will not keep up.

The Interface 1 precedent is the sanity check here — its microdrive channel is
595 bytes, most of it a 512-byte record buffer, for exactly this reason.

### 6.3 Wire format for bulk transfer

The existing pre-header already carries the right fields **[verified]**:

| Field | Reuse as |
|---|---|
| `BLOCK_TYPE` (byte 0) | a new type for channel I/O |
| `TADDR` (byte 1) | sub-op: READ / WRITE |
| `SESSION_ID` (bytes 3–4) | the file handle |
| `BLOCK_LEN` (bytes 7–8) | byte count |
| `CRC` (byte 9) | unchanged |

The spec reserves `'X'`, `'Y'` and `'Z'` for user-defined block types; taking one
keeps channel traffic cleanly separate from the `'B'` command path and from the
SLVM `0x00`/`0xFF` SAVE/LOAD path.

Note the documented trap: the `'B'` pre-header puts **PMR1/PMR2** in bytes 3–6,
*not* `SESSION_ID`/`MEMORY_ADDR` — two layouts share byte positions, and
`GUSTAVO_PROTOCOL.md` presents the SLVM one as universal. A new block type must
state its own layout explicitly.

**This needs Gustavo's sign-off** before implementation, so the block-type and
sub-op numbering doesn't fork the protocol.

---

## 7. What already exists

`TS2068 Ref Library/fdd_tpi_bridge.asm` (~970 lines) and
`fdd_tpi_bridge_design.txt` are an earlier draft of Phase 1. Usable as a starting
point, with corrections:

- **Wrong token equates.** `TOK_SAVE EQU $C9` and `TOK_LOAD EQU $CA` are both
  wrong. From the token table in the ROM: `SAVE = $F8`, `LOAD = $EF`,
  `VERIFY = $D6`, `MERGE = $D5`. The `CAT`/`FORMAT`/`MOVE`/`ERASE`/`OPEN #`/
  `CLOSE #` equates at `$CF`–`$D4` are correct.
- **Hooks the RST 8 error path.** Use `$25D6` instead (§2). The draft's own design
  note already flags the error path as the weaker of its two options.
- **`ERASE` as select-then-`DELETE`** is a two-statement race; make it one
  round trip (§4).
- `FORMAT → TPI:FRESET` (reset configuration) is a surprising meaning for
  `FORMAT`. `NEWTAP` fits the word better.

---

## 8. Build and test infrastructure

Two gaps have to close before any of this can ship.

**There is no ROM source.** `gus-home.asm` and `gus-exrom.asm` in the reference
library are `z80dasm` linear sweeps, not Gustavo's sources — the same class of
artefact as [`rom-analysis/disasm/`](rom-analysis/disasm/), and subject to the
same caveat that data and filler decode as nonsense instructions. Every ROM
change is therefore *append new code at `$22AE`, patch a handful of bytes at the
hook sites, verify with `tools/romdiff.py`*. That is workable — it is exactly the
v1.5w pattern — but it means the build must be reproducible and diffable, not
hand-edited.

**There is no Z80 assembler in the toolchain.** `tools/` carries `zmakebas` only.
Phase 1 needs an assembler (`z80asm` or `sjasmplus`), vendored the way `zmakebas`
is, plus a build step that assembles to `$22AE`, splices the result and the hook
patches into a ROM image, and re-runs `romdiff.py` so every byte changed is
accounted for.

**Testing wants the emulator.** Iterating on ROM patches against hardware only
would be miserable. This is where the ZEsarUX TS-PICO work pays for itself; note
that the emulator's EXROM must be widened from 8K to 16K, since the TS-PICO EXROM
occupies TS-2068 chunks 0 and 1 simultaneously.

---

## 9. Open questions and things to verify

Ordered by how much they could change the design.

1. ~~**What does bare `CAT` do on a stock TS-2068?**~~ **RESOLVED** — it is a
   syntax error and never reaches the command routine; the syntax offset table
   needs four one-byte patches alongside the `$25D6` hook. Measured in ZEsarUX;
   see [§2](#but-the-parameter-table-has-to-be-patched-too-verified-in-zesarux)
   and [§10.5](#105-how-the-zesarux-measurements-were-made).
2. **What report does `$2567` raise?** It is `RST $08` with error byte `$12`.
   Worth knowing, because it is what users see today and what we are replacing.
3. **Block type and sub-op numbering** for §6.3 — needs Gustavo.
4. **`MOVE` meaning.** Mapping it to `CD` is convenient but semantically odd;
   `MOVE "a" TO "b"` as rename is the better fit and leaves `CD` to a separate
   statement or to `TPI:CD`.
5. **Handle lifetime across resets.** What happens to open handles when the 2068
   is reset, the path changes, or a command aborts mid-transfer? The Pico must
   not leak file objects, and BASIC must not hold a stream pointing at a closed
   handle.
6. **Does direct-to-SD `SAVE`/`LOAD` belong in this work?** Saving a program to a
   real file rather than into a mounted TAP is clearly wanted, but it changes the
   meaning of `SAVE`. An Interface-1-style `SAVE *"name"` or an explicit mode is
   less disruptive than redefining the bare statement. Out of scope here; flagged
   so the channel design doesn't accidentally foreclose it.
7. **The tail of the FDD 3000 command table is undecoded** (§10.3). At least one
   parse descriptor consumes inline operands in a way that isn't pinned down, so
   the walk desynchronises partway through. Nothing in this design depends on it;
   noted so nobody re-derives it and assumes the earlier rows are wrong.

---

## 10. Appendix — verified facts

Everything in this section is reproducible from images in this repo, except
§10.3 which needs `3000_2068.ROM` from the reference library.

### 10.1 TS-2068 BASIC tokens

Identical to the ZX Spectrum for `$A5`–`$FF`; `DELETE`, `ON ERR`, `STICK`,
`SOUND`, `FREE`, `RESET` follow as extended tokens.

| Token | Keyword | | Token | Keyword |
|---|---|---|---|---|
| `$CF` | CAT | | `$D4` | CLOSE # |
| `$D0` | FORMAT | | `$D5` | MERGE |
| `$D1` | MOVE | | `$D6` | VERIFY |
| `$D2` | ERASE | | `$EF` | LOAD |
| `$D3` | OPEN # | | `$F8` | SAVE |

```bash
python3 - <<'EOF'
b = open('ROMs/GENUINE-2068-home.bin','rb').read()
j = b.find(b'RN\xc4'); tok = 0xA5; cur = ''
for ch in b[j:j+520]:
    cur += chr(ch & 0x7F)
    if ch & 0x80:
        print(hex(tok), cur); cur = ''; tok += 1
EOF
```

### 10.2 Statement dispatch for the disk tokens

Dispatch subtracts `$CE` and indexes the syntax offset table at `$1945`; the
parameter-table entry address is `$1945 + (token - $CE) + offset_byte`.

| Token | Entry | Bytes | Routine |
|---|---|---|---|
| `$CF` CAT | `$1A16` | `0A 2C 05 C8 25` | `$25C8` |
| `$D0` FORMAT | `$1A07` | `0A 2C 05 CC 25` | `$25CC` |
| `$D1` MOVE | `$1A0C` | `0A 2C 05 D0 25` | `$25D0` |
| `$D2` ERASE | `$1A11` | `0A 2C 05 D4 25` | `$25D4` |
| `$D3` OPEN # | `$19FD` | `06 2C 0A 05 2A 14` | `$142A` |
| `$D4` CLOSE # | `$1A03` | `06 00 9F 13` | `$139F` |
| `$EF` LOAD | `$19E1` | `0B` | (class-0B tape path) |
| `$F8` SAVE | `$19E0` | `0B` | (class-0B tape path) |

The four disk routines converge at `$25D6` — note the `JR` displacements land
*past* `$25D4`, which is only ERASE's own `LD B`. `$2889` is `BIT 7,(IY+1); RET`.
All of it is byte-identical in `GENUINE-2068-home.bin` and `TSPICO-11-home`.

```bash
python3 - <<'EOF'
for f in ('ROMs/GENUINE-2068-home.bin', 'ROMs/TSPICO-11-home'):
    b = open(f, 'rb').read()
    base = 0x1945
    for idx, name in ((1,'CAT'), (2,'FORMAT'), (3,'MOVE'), (4,'ERASE'),
                      (5,'OPEN #'), (6,'CLOSE #')):
        ent = base + idx + b[base + idx]
        print(f, name, hex(ent), ' '.join(f'{x:02X}' for x in b[ent:ent+6]))
    print(f, '25C8:', ' '.join(f'{x:02X}' for x in b[0x25C8:0x25E4]))
EOF
```

### 10.3 FDD 3000 command table, decoded

Corrects the annotations in `fdd3000_annotated.asm`. Entry grammar:
`token, descriptor..., $FE, stack_adjust, exec_lo, exec_hi`; descriptors index
the parse-function table at `$00DA` by *byte offset*; descriptors `$04` and `$06`
consume an inline NUL-terminated character list from the table.

Parse-function table (`$00DA`, read from the binary, not from the listing):

| Off | → | | Off | → | | Off | → | | Off | → |
|---|---|---|---|---|---|---|---|---|---|---|
| `$00` | `$00FD` | | `$08` | `$0182` | | `$10` | `$0202` | | `$18` | `$0952` |
| `$02` | `$010E` | | `$0A` | `$01B9` | | `$12` | `$0219` | | `$1A` | `$0B7F` |
| `$04` | `$0129` | | `$0C` | `$01C5` | | `$14` | `$01F0` | | `$1C` | `$0867` |
| `$06` | `$0158` | | `$0E` | `$01D0` | | `$16` | `$01F7` | | `$1E` | `$079E` |

The first six entries decode cleanly, and their exec addresses all land on
identifiable handlers:

| Token | Keyword | Descriptors | Exec |
|---|---|---|---|
| `$CF` | CAT | `0C` | `$0715` |
| `$EF` | LOAD | `1A` | `$0C08` |
| `$F8` | SAVE | `18` | `$09C9` |
| `$D3` | OPEN # | `00 12 02 12 04+"IOAR"` `06` | `$08CE` |
| `$D4` | CLOSE # | `0A` | `$08BE` |
| **`$F5`** | **PRINT** | `04+"#"` `00 08` | `$0744` |
| **`$EE`** | **INPUT** | `04+"#"` `00 12 1E` | — |

Two things worth carrying away, and they are the only two this design depends on:

- The **SAVE and LOAD parse/exec pairs are swapped** relative to the annotated
  listing. `$F8` SAVE uses parse `$0952` / exec `$09C9`; `$EF` LOAD uses parse
  `$0B7F` / exec `$0C08`. The listing has it the other way round.
- **`PRINT` and `INPUT` are in the table**, each with an inline `"#"` character
  list — the FDD 3000 re-implements the statements rather than installing a
  channel record. This is the design decision §6.1 rejects.

**The tail of the table does not decode under this grammar.** From the `INPUT`
row onward the walk produces impossible descriptor values (`$23`, `$AC`) and one
exec address of `$0000`, which means at least one further descriptor consumes
inline operands the way `$04` does. `$06` was the obvious candidate and is ruled
out — its routine at `$0158` never touches the saved table pointer (it is
`CALL $025E; JR Z,$017B; CALL $0219; CALL $0222; ...`, a straight parse). The
remaining suspect is `$1E` → `$079E`. Resolving this is FDD archaeology, not a
prerequisite for anything here, so it is left open.


```bash
python3 - <<'EOF'
p = "TS2068 Ref Library/3000_2068.ROM"   # adjust to your reference library
b = open(p, 'rb').read()
print(' '.join(f'{x:02X}' for x in b[0x0264:0x0305]))   # command table
print(' '.join(f'{x:02X}' for x in b[0x00DA:0x00FA]))   # parse-function table
EOF
```

### 10.4 Constants this design depends on

| Value | Meaning | Source |
|---|---|---|
| `$22AE`–`$3FFF` | 7,506 free bytes in the EXROM | `rom-analysis/MEMORY_MAP.md` |
| `$25D6` | HOME ROM disk-token hook site (**not** `$25D4`) | §10.2 |
| `$142A` / `$139F` | HOME ROM `OPEN #` / `CLOSE #` | §10.2 |
| `$5C4F` / `$5C51` / `$5C10` | `CHANS` / `CURCHL` / `STRMS` | HOME ROM, live |
| `$1A73` | TPI filename prefix parse (`TPI:` / `NET:`) | `rom-analysis/SYMBOLS.md` |
| `$1BA0` | `'B'` pre-header builder | `rom-analysis/PROTOCOL_FROM_ROM.md` |
| `$1840` | TPI BIOS jump table | `rom-analysis/PROTOCOL_FROM_ROM.md` |
| `$5DD3` / `$5DD5` | command-string address / length | `rom-analysis/PROTOCOL_FROM_ROM.md` |
| `$1946`–`$1949` | syntax offset table bytes to patch | §2, §10.5 |
| ~88 ms | cost of one `WF_NPH` poll | `tools/wf_nph_timing.py` |

### 10.5 How the ZEsarUX measurements were made

Setup is the issue-#35 lab: `~/Documents/github/zesarux-tspico-lab`, whose
`work/zesarux-tspico` is a ZEsarUX 13.0 build patched to give the TS2068 a full
16K EXROM (stock ZEsarUX mirrors segment 0, which breaks any TS-PICO image —
see that repo's `NOTES.md`). Driven over ZRCP on port 10000 via `work/zrcp.py`.

**Two gotchas cost real time here; both are worth knowing before the next
ROM experiment.**

1. **Breakpoints do not halt the CPU under `--vo null`.** A ZRCP breakpoint whose
   default action is "break" opens the debugger *menu*, and with no video driver
   that is a no-op — the CPU keeps running and polling `get-registers` shows
   nothing. `get-breakpointspasscount` also stays at `0 0` unless a pass count is
   configured, so it is not a hit indicator either. Use a **breakpoint action**
   with an observable side effect instead:

   ```
   --enable-breakpoints
   --set-breakpoint 1 PC=25C8H
   --set-breakpointaction 1 "let var0=var0+1"
   ```

   then read it back with ZRCP `evaluate var0` before and after the event. Always
   run a positive control (a breakpoint on `$1A71`, the statement dispatcher,
   which any line must reach) — that is what caught the non-halting behaviour.

2. **Typing a keyword token is unnecessary.** Disk keywords are buried in extended
   mode, but the edit line can be built directly: press one key that yields a
   single-token keyword (`J` → `LOAD`, ASCII 106), type any remaining ASCII, then
   overwrite the first byte of the edit line with the token under test. The buffer
   length never changes, so no `WORKSP` bookkeeping is disturbed. Read `E_LINE`
   (`$5C59`) *immediately* before the write and assert the first byte is still
   `$EF` — the editor reallocates, and a stale address silently pokes the wrong
   place. `read-memory`/`write-memory` take **decimal** addresses and values;
   breakpoint conditions take hex with an `H` suffix.

Harnesses used for this round are throwaway (`multi.py`, `trial.py`); if this
becomes a regular activity they belong in `tools/` alongside `wf_nph_timing.py`.

Results, on `src/rom/TSPICO.ROM`, counting arrivals at each checkpoint for one
immediate-mode line:

| Line | `$1A71` | `$25C8` | `$25D4` | `$2567` | screen |
|---|---|---|---|---|---|
| `CAT` | 17 | 0 | 0 | 0 | `CAT ?` |
| `CAT "x"` | 16 | 0 | 0 | 0 | `CAT "x"?` |
| `CAT "x",` | 2 | 2 | 0 | 1 | accepted |
| `LOAD ""` (control) | 2 | 0 | 0 | 0 | runs |

(The high `$1A71` counts on the rejected lines are the editor re-checking syntax
on every keystroke and redraw; the accepted lines show the expected 2 = one
syntax pass plus one run pass.)

And on the same image with the four offset-table bytes patched per §2:

| Line | `$1A71` | `$25C8` | `$25D4` | screen |
|---|---|---|---|---|
| `CAT` | 2 | **2** | 0 | accepted |
| `ERASE` | 2 | 0 | **2** | accepted |
| `LOAD ""` (regression) | 2 | 0 | 0 | runs, unchanged |
