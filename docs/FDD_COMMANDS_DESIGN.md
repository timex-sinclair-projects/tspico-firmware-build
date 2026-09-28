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
| Why the ROM hook is a 7-byte patch, not a trampoline | [§2](#2-the-hook-the-home-rom-already-does-most-of-the-work) |
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
> decode of the command table is in [§10.3](#103-fdd-3000-command-table-fully-decoded).

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

Timex loads **the token into `B` and then raises an error** — Report J,
*Invalid I/O device* (§10.6). `B` is of no use to an error handler. That stub was staged as an extension point — almost certainly
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
| EXROM `$3000`–`$3FFF` | **4,096 bytes** (proposed base) | all new Z80 code |
| EXROM `$22A1`–`$2FFF` | 3,423 bytes | left free for Gustavo |
| HOME ROM | effectively none | 7 bytes of hook patches only (§2) |
| RAM below `RAMTOP` | allocated at install | channel driver + per-channel buffers (§6) |

Current EXROM code ends at `$22A0`; everything above is `$FF` filler. Rather than
appending at the first free byte, the proposal (§9 item 7) is to base our code at
**`$3000`**, which reserves a clean 4 KB region for the disk feature and leaves
Gustavo the 3.4 KB immediately after his current code — his natural append point.
4 KB is ample: the FDD 3000's entire disk OS fit in 4 KB, and we reuse Gustavo's
TPI send path rather than carrying a low-level driver. Keep the base a single
assembler `EQU` so it can move in one line. Per
[`rom-analysis/MEMORY_MAP.md`](rom-analysis/MEMORY_MAP.md), nothing in that region
is occupied, so this displaces no existing address.

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

**Prerequisite, done and verified.** The ROM-side hook is wired. The 4-byte
syntax-offset patch (`$1946`–`$1949`) makes a bare keyword reach the routine, and
the `$25D6` stub (14 bytes, which all of CAT/FORMAT/MOVE/ERASE fall into) is
repurposed: the syntax pass returns to accept the statement; the runtime pass does
`LD HL,$3000` / `JP $03FC` — the returning HOME→EXROM thunk — landing in
`FDD_DISPATCH` (our module) with the EXROM paged and `B` = the token. Confirmed in
ZEsarUX: runtime `CAT` reaches `$3000` with `B = $CF`, `BC` survives the bank call,
and control returns to BASIC with the machine alive.

**All four commands are implemented** (`src/rom/fdd/fddcmd.asm`). Each builds a
`tpi:<verb> <arg>` command string in the calculator-stack workspace, pushes a
string descriptor for it, sets `T-ADDR = 0`, and jumps to the shipping TPI send
entry (`$1A73`) — reusing the entire `SAVE "tpi:..."` machinery (send + scrolling
display of the response):

| Statement | TPI command built | Pico verb |
|---|---|---|
| `CAT` | `tpi:dir` | `DIR` |
| `ERASE "name"` | `tpi:rm name` | `RM` |
| `FORMAT "name"` | `tpi:newtap name` | `NEWTAP` |
| `MOVE "path"` | `tpi:cd path` | `CD` |

The verbs map to Pico commands that exist today. The argument is read from the
BASIC line and appended after the verb. Both the syntax-check and runtime pass
reach the module (via the always-transfer hook, §2); the module tests FLAGS bit 7
(read directly — the bank call clobbers `IY`): the syntax pass consumes the
argument so the statement is accepted, the runtime pass builds and sends.

Verified in ZEsarUX, each command producing the exact string above (`CAT` → `tpi:dir`,
`ERASE "AB"` → `tpi:rm AB`, `FORMAT "X"` → `tpi:newtap X`, `MOVE "Y"` → `tpi:cd Y`),
with the `'B'` pre-header going out port `$0E`.

**End-to-end through the real firmware (issue-#35 bridge).** `CAT` was then run
against the real `TS/tspico.py` command logic, using a new bridge runtime
(`tspico_runtime.py` in the ZEsarUX lab) that mocks the MicroPython environment
and points the "SD card" at a host directory. The full round trip works: `CAT`
sends the `'B'` `tpi:dir` command, the real `DIR` handler reads the host SD
directory, builds its 288-char listing, and streams all 304 response bytes back;
the Z80 consumes them, the ROM dispatches its print handler with output aimed at
the main-screen channel (`CURCHL` = the `S` channel), and the command completes
cleanly. So the command path is proven against the actual firmware.

The listing does not yet *render* on the emulated screen: the ROM's function-`$86`
handler (`$21E3`, "print string with loop") reads an empty string from the stream
and prints nothing. This is a byte-alignment gap in the func-`$86` streaming
handshake between `SEND_MSG2` and the ROM **over the bridge** — the same path
`SAVE "tpi:..."` uses on real hardware, where it works — so it is bridge-fidelity
work (the socket model not fully replicating the PIO FIFO backpressure the
streamed display relies on), not a defect in the disk-command ROM code. Finishing
it is the lab's M2b/M3 milestone; a real Pico or hardware renders the listing
directly.

Open polish items: `MOVE` currently means change-directory (single arg) rather than
the rename in §9 item 4 — that needs a Pico `move` verb; and `ERASE` maps to `rm`,
which has its own confirmation prompt. The argument is taken as a string *literal*
from the line; a string *expression* (`ERASE a$`) would need the ROM's evaluator
(class `$0A`) instead of the line scan.

Proposed mapping (syntax is ours to choose; this is a starting point):

| Statement | Becomes | Notes |
|---|---|---|
| `CAT` | `TPI:DIR` | SD directory of the current path |
| `CAT "*.tap"` | `TPI:DIR *.TAP` | filtered |
| `CAT #` | `TPI:TAPDIR` | blocks inside the mounted TAP — see below |
| `ERASE "name"` | new `TPI:ERASE name` | **not** the existing select-then-`RM` two-step |
| `MOVE "a" TO "b"` | new `TPI:MOVE a b` | rename/move — we define the syntax (see below) |
| `MOVE "path"` | `TPI:CD path` | debatable; see §9 |
| `FORMAT "name"` | `TPI:NEWTAP name` | create + mount a TAP |

**`CAT` needs a context rule.** There are two directories in play — the SD path
(`TPI:DIR`) and the contents of the mounted TAP (`TPI:TAPDIR`). Making bare `CAT`
mean "the SD path" and requiring a marker for the TAP listing is the least
surprising split, but this is a UX decision, not a technical one.

**`ERASE` should be one round trip.** The existing `TPI:` flow for deleting is
select-then-delete, which is racy when a statement issues both halves. Add a
Pico-side handler that takes the name directly.

**`MOVE`'s syntax is ours to invent.** The FDD 3000 is no reference here: its own
`MOVE` table entry (`$D1`) is malformed — a `$04`→`$06` substitution that would
mis-parse its arguments (§10.3). So there is no prior-art parse to match; define
`MOVE "a" TO "b"` cleanly. The `TO` token (`$CC`) is parsed by our own routine.

**Reserve Report J for a dead device — don't inherit the stub's meaning.** Today
the `$25D6` stub raises **Report J, "Invalid I/O device"** (§10.6), and that is
*also* what a TS-PICO comms failure raises (the internal error-9 path). So on a
stock machine "there are no disk commands" and "the Pico didn't answer" are
indistinguishable. The new handlers must not perpetuate that: map handler-level
failures onto the specific reports the Pico already returns — F *Invalid file
name*, Q *Parameter error*, 8 *End of file*, and so on (the full status→report
table is in [`rom-analysis/PROTOCOL_FROM_ROM.md`](rom-analysis/PROTOCOL_FROM_ROM.md))
— and leave J to mean the device is genuinely absent or unresponsive. This is
almost free: the `'B'`-block path already surfaces the Pico's status byte as a
report, so it is a matter of the handlers returning the right status.

Pico-side work in this phase is small: a few handlers in `SA_funct`, most of them
thin wrappers over `DIR`, `RM`, `CD`, `TAPDIR`, `NEW_TAP`. Each must honour the
V6 tail pre-load contract in `PROCESS_CMD` — handlers write their response and
return; they do **not** write their own `0x01`. See
[`EXTCMD_PROTOCOL.md`](EXTCMD_PROTOCOL.md) §3a.

**Deliverable:** the hook mechanism is already proven in the emulator (§2), so the
first end-to-end command instead proves the two things still unverified — the
build pipeline that assembles at `$22AE`, splices the EXROM code and the seven
HOME-ROM patch bytes, and passes `romdiff.py` (§8); and a Pico `SA_funct` handler
returning a real result with the right report. Everything after that is
repetition.

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
**[verified on a live boot]**: `CHANS` (`$5C4F`), `CURCHL` (`$5C51`) and `STRMS`
(`$5C10`) are all live. So the Interface 1 approach works: install a channel
record carrying output and input routine addresses, point a `STRMS` entry at it,
and stock `PRINT #`, `INPUT #`, `LIST #` and `INKEY$ #` route to us with no
statement interception whatsoever.

What the live machine confirms (booted TS-PICO, ZEsarUX):

- **A channel record is 5 bytes** — `out_addr(2), in_addr(2), letter(1)`. The
  default `CHANS` at `$6840` holds K (`$0500`/`$0C0E`), S, R (`$0AE7`/`$11BF`) and
  P, then `$80`. A disk channel is one of these records **extended** past the
  letter with its buffer and handle state (the Interface-1 `M`-channel trick);
  `PRINT #`/`INPUT #` call the out/in routine with `CURCHL` pointing at the record,
  so the driver finds its buffer at a fixed offset past the header.
- **Twelve user streams are free.** `STRMS` pre-opens 0–3 (K/S/S/P); streams
  **4–15 are all closed and available**. So opening several disk channels at once
  — one for read, one for write, and copying between them — is directly supported;
  the real limit is Pico-side handles and buffer RAM, not the stream table.
- **Read/write (`R`) mode is feasible.** The 2068 already carries a bidirectional
  `R` channel; a disk channel whose out *and* in routines both point to our driver,
  backed by a MicroPython `r+`/`w+` file, gives it. The one subtlety is flushing
  and re-`seek`-ing on a read↔write direction change on the same handle.

This is exactly where we part ways with the FDD 3000. Its command table has
dedicated entries for the `PRINT` (`$F5`) and `INPUT` (`$EE`) tokens, each with an
inline `"#"` list (§10.3) — i.e. it re-implements the statements. That is a large
amount of fragile work (PRINT item lists, `AT`/`TAB`, INPUT's line editor and
assignment) for a strictly worse result than the channel record, which gets all
of it from stock ROM for free.

**Placement constraint:** channel routines are called with **HOME paged in**, so
they cannot live in the EXROM. Put the driver in RAM below `RAMTOP` — the FDD
3000 does the same thing with the code it downloads to `$6880`. This is not a
hardship: the TPI wire protocol from the Z80 side is `OUT ($0E),A` and a `BIT 6`
poll of `$0F`. A few hundred bytes covers the driver and its buffers.

`OPEN #` already parses (§2), so the ROM-side change is at `$142A`: accept a new
channel specifier (`"d"`, by analogy with Interface 1's `"m"`), allocate a
channel record and buffer, issue `TPI:OPEN`, and wire the `STRMS` entry.
`CLOSE #` at `$139F` flushes, issues `TPI:CLOSE`, and reclaims.

**Do it via `CHANS`, not `SYSCON`.** The TS-2068 has a *second*, Timex-specific
channel mechanism — `SYSCON` (`$5CBC`) — and it is the "proper" extension point
that stock `OPEN #`/`CLOSE #` consult for any non-K/S/P letter. It is fully
reverse-engineered in [§10.7](#107-syscon-channel-format--reverse-engineered), and
the conclusion there is that **`SYSCON` is a banked-device-driver ABI**: entries
carry a bank byte and handlers invoked through the RAM dispatcher `$65D0` with
subfunction codes (`$88` open, `$02` close), not plain out/in vectors. That is the
right vehicle for a DOCK-cartridge disk and it unlocks the ≥128 system-stream
space, but it is heavier than we need. So the primary path is **a direct `CHANS`
channel record with a small hook on `OPEN #`'s letter dispatch** (Route B);
`SYSCON` registration (Route A) stays documented as the fully-native alternative.
Either way `SYSCON` is empty at boot (`$5EEA`, header + `$80`), so nothing there
constrains us.

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

**The build pipeline now exists** (`tools/build-rom.py` + `src/rom/fdd/`). It
closes what used to be the two blocking gaps here:

```bash
python3 tools/build-rom.py --verify      # -> build/TSPICO-fdd.ROM
```

The pipeline: assemble `src/rom/fdd/fddcmd.asm` with **sjasmplus** (the assembler,
`brew install sjasmplus` — checked at start, matching the `z80dasm` dependency in
`romdisasm.sh`); copy the crc-checked base `src/rom/TSPICO-SYNC.ROM` (ROM 2.0 = v1.7 + `patches/tspico-sync.asm`); splice the module
into free EXROM at **`$3000`** (file `$7000`), asserting the region is `$FF`; apply
the declarative `PATCHES` manifest (each patch asserts the bytes it overwrites, so
a moved ROM fails loudly); and, with `--verify`, assert that **only** the module
region and enabled patches changed. Because file offset == Z80 address in both
banks, the report reads in Z80 addresses. This is the reproducible, diffable
append-and-patch pattern the v1.5w fix used, mechanised.

First build is proven end to end: it assembles the `$3000` skeleton, applies the
verified 4-byte syntax-offset patch, produces `build/TSPICO-fdd.ROM` changing
exactly 17 bytes in 2 hunks (HOME `$1946`, EXROM `$3000`), **boots in ZEsarUX**, and
bare `CAT` reaches the disk stub in the built image. The `$25D6` disk-token hook is
staged in the manifest (disabled) pending its HOME→EXROM thunk stub.

> **There is still no Gustavo ROM source**, and we don't need one. `gus-home.asm`/
> `gus-exrom.asm` in the reference library are `z80dasm` linear sweeps, not sources
> (same caveat as [`rom-analysis/disasm/`](rom-analysis/disasm/)). We never
> reassemble the whole ROM — we splice our own module into free space and patch a
> handful of named bytes, all verified against the base.

**Testing uses the emulator.** Iterating on ROM patches against hardware only would
be miserable. This is where the ZEsarUX TS-PICO work pays for itself; note that the
emulator's EXROM must be widened from 8K to 16K, since the TS-PICO EXROM occupies
TS-2068 chunks 0 and 1 simultaneously.

---

## 9. Open questions and things to verify

Ordered by how much they could change the design.

1. ~~**What does bare `CAT` do on a stock TS-2068?**~~ **RESOLVED** — it is a
   syntax error and never reaches the command routine; the syntax offset table
   needs four one-byte patches alongside the `$25D6` hook. Measured in ZEsarUX;
   see [§2](#but-the-parameter-table-has-to-be-patched-too-verified-in-zesarux)
   and [§10.5](#105-how-the-zesarux-measurements-were-made).
2. ~~**What report does `$2567` raise?**~~ **RESOLVED — Report J, "Invalid I/O
   device".** `RST $08` with error byte `$12` sets `ERR_NR = 18`, and the report
   printed is entry `n+1` = 19 in the message table at `$0F67`. Confirmed two
   ways: statically from the table, and by capturing `ERR_NR` in ZEsarUX
   (`$25D6` → `$25E1` → `$2567` → `ERR_NR = 18`), on the patched image via bare
   `CAT` and on the **unpatched** shipping ROM via `CAT "x",`. See
   [§10.6](#106-what-the-stock-rom-reports-and-why-it-matters).
3. **Block type and sub-op numbering** for §6.3 — needs Gustavo.
4. **`MOVE` meaning.** Mapping it to `CD` is convenient but semantically odd;
   `MOVE "a" TO "b"` as rename is the better fit and leaves `CD` to a separate
   statement or to `TPI:CD`. (The FDD 3000 is no guide — its own `MOVE` entry is
   malformed, §10.3.)
5. **Handle lifetime across resets.** What happens to open handles when the 2068
   is reset, the path changes, or a command aborts mid-transfer? The Pico must
   not leak file objects, and BASIC must not hold a stream pointing at a closed
   handle. Related: **`NEW`/`CLEAR` destroy appended `CHANS` channels** (and any
   `SYSCON` entry we add), so disk channels must be re-established afterwards —
   design the setup to be idempotent per-`OPEN`, or hook the `NEW` path.
6. **`SYSCON` vs `CHANS` for the channel hook** — **RESOLVED toward `CHANS`
   (Route B).** `SYSCON` is now fully reverse-engineered (§10.7) and turns out to
   be a banked-driver ABI, heavier than we need; Route A stays documented as the
   fully-native alternative. Reopen only if disk streams must work in banked
   contexts or in the ≥128 system-stream space.
7. **EXROM base address.** Proposal: assemble our code at **`$3000`**, giving us
   `$3000–$3FFF` (4 KB — ample; the FDD 3000's *entire* disk OS fit in 4 KB) and
   leaving Gustavo `$22A1–$2FFF` (3.4 KB, ~5× his current footprint). Keep the base
   a single `EQU` so it is trivially movable; Gustavo may prefer we take the top
   instead. Needs his sign-off.
8. **AROS scope.** An AROS runs in the DOCK bank with its own ROM, so it cannot use
   our EXROM handlers or the HOME stream layer; it *can* still drive the TS-PICO
   ports directly (they are bank-independent) if it speaks TPI itself. The design
   targets BASIC-under-HOME and promises AROS nothing beyond that — but our RAM
   driver/buffers must not assume persistence across an AROS session, and vice
   versa.
9. **Does direct-to-SD `SAVE`/`LOAD` belong in this work?** Saving a program to a
   real file rather than into a mounted TAP is clearly wanted, but it changes the
   meaning of `SAVE`. An Interface-1-style `SAVE *"name"` or an explicit mode is
   less disruptive than redefining the bare statement. Out of scope here; flagged
   so the channel design doesn't accidentally foreclose it.
10. ~~**The tail of the FDD 3000 command table is undecoded.**~~ **RESOLVED** — it
   decodes completely; see the full 20-entry table in
   [§10.3](#103-fdd-3000-command-table-fully-decoded). The apparent desync was a
   flaw in a descriptor-walking script, not the table. Two residual curiosities,
   neither affecting this design: two bodies (RESTORE, MOVE) are malformed
   (`$04`→`$06` substitution), and eight entries carry standard-BASIC token values
   that read as reused opcodes rather than disk verbs.

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

### 10.3 FDD 3000 command table, fully decoded

Corrects the annotations in `fdd3000_annotated.asm`. **Entry grammar:**
`token, descriptor..., $FE, stack_adjust, exec_lo, exec_hi`. The ROM enumerates
entries purely by scanning to the next `$FE` and skipping 3 bytes (`TABLE_SKIP`,
`$007D`) — it does *not* parse the descriptors to find boundaries — so that scan
is the ground truth for where each entry begins. Descriptors index the
parse-function table at `$00DA` by *byte offset*.

Parse-function table (`$00DA`, read from the binary):

| Off | → | | Off | → | | Off | → | | Off | → |
|---|---|---|---|---|---|---|---|---|---|---|
| `$00` | `$00FD` | | `$08` | `$0182` | | `$10` | `$0202` | | `$18` | `$0952` |
| `$02` | `$010E` | | `$0A` | `$01B9` | | `$12` | `$0219` | | `$1A` | `$0B7F` |
| `$04` | `$0129` | | `$0C` | `$01C5` | | `$14` | `$01F0` | | `$1C` | `$0867` |
| `$06` | `$0158` | | `$0E` | `$01D0` | | `$16` | `$01F7` | | `$1E` | `$079E` |

**Exactly one descriptor consumes inline table bytes: `$04` (`$0129`,
`PARSE_CHAR_PARAM`).** It reads the caller's saved table pointer off the stack
(`LD HL,0; ADD HL,SP`), matches the input character against the NUL-terminated
list that follows the `$04` byte, and writes the advanced pointer back so the
parse loop resumes past the list. This is the *only* `ADD HL,SP` in the whole
parse region, and `$0158` (`$06`) in particular is a straight expression/`LINE`
parse (`CALL $025E; JR Z,…; CALL $0219; CALL $0222; …`) that never touches the
stack. So the earlier claim that `$06` also consumes inline was wrong.

The complete table — 20 entries, ending exactly at `$0304 = $FF`:

| Token | Keyword | Off | Descriptor body | Exec |
|---|---|---|---|---|
| `$CF` | CAT | `$0264` | `0C` | `$0715` |
| `$EF` | LOAD | `$026A` | `1A` | `$0C08` |
| `$F8` | SAVE | `$0270` | `18` | `$09C9` |
| `$D3` | OPEN # | `$0276` | `00 12 02 12 04+"IOAR" 06` | `$08CE` |
| `$D4` | CLOSE # | `$0286` | `0A` | `$08BE` |
| `$F5` | PRINT | `$028C` | `04+"#" 00 08` | `$0744` |
| `$EE` | INPUT | `$0296` | `04+"#" 00 12 1E` | `$0000` |
| `$F0` | LIST | `$02A1` | `1C` | `$0871` |
| `$E5` | RESTORE | `$02A7` | `06 ⚠23 00 00` | `$0848` |
| `$D5` | MERGE | `$02B0` | `02` | `$0C76` |
| `$EC` | GO TO | `$02B6` | `02 14` | `$0839` |
| `$ED` | GO SUB | `$02BD` | `0C 16` | `$0829` |
| `$FC` | DRAW | `$02C4` | *(none)* | `$0A43` |
| `$D0` | FORMAT | `$02C9` | `02 10 16` | `$0E6D` |
| `$D2` | ERASE | `$02D1` | `02 0E` | `$08A6` |
| `$F1` | LET | `$02D8` | `02 04+"¬" 02` | `$094E` |
| `$D1` | MOVE | `$02E2` | `02 06 ⚠AC 00 02` | `$0916` |
| `$E9` | DIM | `$02EC` | `02` | `$08AF` |
| `$AB` | ATTR | `$02F2` | `02 04+"PUVI"` | `$0E89` |
| `$F3` | NEXT | `$02FE` | `0C` | `$0853` |

Four things to carry away:

- **The decode is complete.** The earlier "tail does not decode" was a flaw in a
  descriptor-walking script, not in the table. The ROM's own scan-to-`$FE`
  boundary logic lands on a valid token every time and terminates exactly at the
  `$FF`. 18 of 20 descriptor bodies are also clean descriptor streams.

- **SAVE and LOAD parse/exec pairs are swapped** relative to the annotated
  listing: `$F8` SAVE = parse `$0952` / exec `$09C9`; `$EF` LOAD = parse `$0B7F`
  / exec `$0C08`.

- **`PRINT` and `INPUT` are in the table**, each with an inline `"#"` list — the
  FDD 3000 re-implements the statements rather than installing a channel record.
  This is the design decision §6.1 rejects. (INPUT's exec is `$0000`; its `$1E` →
  `$079E` parser takes over and the entry's exec field is never read — dead
  filler, not a decode failure.)

- **Two bodies are malformed (⚠): RESTORE and MOVE.** Each carries a `$06` exactly
  where the structurally-parallel entry carries `$04`, followed by the identical
  NUL-terminated list:

  | | body | vs | |
  |---|---|---|---|
  | PRINT / INPUT | `04 23 00` = `04+"#"` | ↔ | RESTORE `06 23 00` |
  | LET | `04 AC 00` = `04+"¬"` | ↔ | MOVE `02 06 AC 00 02` |

  Since `$06` provably does not consume inline, the byte after it (`$23` / `$AC`)
  would be read as a descriptor and mis-index the parse table. In practice
  `$0158`'s semicolon check error-exits (`JP NZ,$043E`) before the bad byte is
  reached for most inputs, so the defect is usually masked rather than fatal — but
  it is a genuine anomaly in the ROM data (a `$04`→`$06` substitution), not a gap
  in this decode. That `MOVE`, a headline disk command, is one of the two is
  itself notable.

**On the keyword-vs-function mismatch.** The table matches raw TS-2068 BASIC token
*values*, and the intercept fires on `‹token› *` (`CP '*'` at `$00A3`). Eight of
the twenty (RESTORE, GO TO, GO SUB, DRAW, DIM, ATTR, NEXT, LET) are not plausible
disk verbs, and their exec targets do not correspond to the keyword's meaning
(e.g. GO SUB → `$0829`, ATTR → `$0E89` = the P/U/V/I drive-select handler). The
FDD 3000 appears to have reused convenient token byte-values as opcodes for its
own Interface-1-derived command set rather than as their BASIC keywords.
Identifying each one's intent is FDD archaeology and is **not** a prerequisite for
this design — noted only so nobody re-derives it and assumes the decode is wrong.

```bash
python3 - <<'EOF'
p = "TS2068 Ref Library/3000_2068.ROM"   # adjust to your reference library
b = open(p, 'rb').read()
TOK = {0xCF:'CAT',0xD0:'FORMAT',0xD1:'MOVE',0xD2:'ERASE',0xD3:'OPEN#',0xD4:'CLOSE#',
       0xD5:'MERGE',0xEE:'INPUT',0xEF:'LOAD',0xF0:'LIST',0xF1:'LET',0xF3:'NEXT',
       0xF5:'PRINT',0xF8:'SAVE',0xFC:'DRAW',0xE5:'RESTORE',0xE9:'DIM',0xEC:'GOTO',
       0xED:'GOSUB',0xAB:'ATTR'}
p2 = 0x0264
while b[p2] != 0xFF:                        # exact TABLE_SKIP: scan to $FE, +3
    tok = b[p2]; s = p2 + 1
    while b[s] != 0xFE: s += 1
    ex = b[s+2] | (b[s+3] << 8)
    print("$%04X %-8s exec=$%04X body=%s" % (
        p2, TOK.get(tok,'?'), ex, ' '.join('%02X'%x for x in b[p2+1:s])))
    p2 = s + 4
EOF
```

### 10.4 Constants this design depends on

| Value | Meaning | Source |
|---|---|---|
| `$22A1`–`$3FFF` | free EXROM (last code byte `$22A0`); we base at `$3000` | §2, `rom-analysis/MEMORY_MAP.md` |
| `$25D6` | HOME ROM disk-token hook site (**not** `$25D4`) | §10.2 |
| `$142A` / `$139F` | HOME ROM `OPEN #` / `CLOSE #` | §10.2 |
| `$5C4F` / `$5C51` / `$5C10` | `CHANS` / `CURCHL` / `STRMS` (streams 4–15 free) | live boot |
| 5 bytes | channel record: `out(2) in(2) letter(1)` | live `CHANS` $6840 |
| `$5CBC` → `$5EEA` | `SYSCON` ptr → table (empty at boot); banked-driver ABI | §10.7 |
| `$65D0` / `$6499` | RAM banked-dispatch / `BANK_ENABLE` (SYSCON path) | §10.7 |
| `$1A73` | TPI filename prefix parse (`TPI:` / `NET:`) | `rom-analysis/SYMBOLS.md` |
| `$1BA0` | `'B'` pre-header builder | `rom-analysis/PROTOCOL_FROM_ROM.md` |
| `$1840` | TPI BIOS jump table | `rom-analysis/PROTOCOL_FROM_ROM.md` |
| `$5DD3` / `$5DD5` | command-string address / length | `rom-analysis/PROTOCOL_FROM_ROM.md` |
| `$1946`–`$1949` | syntax offset table bytes to patch | §2, §10.5 |
| `$0F67` | report message table (29 entries) | §10.6 |
| `$2567` = `CF 12` | stub's `RST 08` → Report J | §10.6 |
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

### 10.6 What the stock ROM reports, and why it matters

The disk-command stub ends at `$2567` = `CF 12` — `RST $08` with error byte
`$12`. The report table lives at `$0F67` (29 entries, TS-2068 adds *Missing
LROS* at index 28), and `RST $08; DEFB n` prints entry **`n+1`**. So:

| | |
|---|---|
| `DEFB $12` | `ERR_NR = 18` → index 19 → **Report J — Invalid I/O device** |
| `DEFB $0B` | `ERR_NR = 11` → index 12 → *Nonsense in BASIC* (the classic Report C — sanity check on the `n+1` rule) |

Verified on the machine, not just in the table: `ERR_NR` captured at the instant
HOME `$0055` (`LD (IY+0),L`) stores it gives **18** both for bare `CAT` on the
§2-patched image and for `CAT "x",` on the **unpatched** shipping ROM — so it is
the stub's own report, not an artefact of the patch. Control: `RETURN` with no
`GOSUB` captures 6 → Report 7 *RETURN without GOSUB*, as it must.

**Why this matters for the design.** Report J is *already* what a TS-PICO comms
failure produces — the ROM's internal "error 9" enters the dispatcher at
`$1BF3` as `A=9` = status 10 = Report J (see
[`rom-analysis/PROTOCOL_FROM_ROM.md`](rom-analysis/PROTOCOL_FROM_ROM.md#internal-error-9-surfaces-as-report-j-not-report-9)).
So today "this machine has no disk commands" and "the Pico did not answer" are
**the same report**, and a user cannot tell them apart. The new handlers should
not inherit that: reserve J for a genuinely absent or unresponsive device and
map handler-level failures onto the more specific reports the Pico already
returns (F *Invalid file name*, Q *Parameter error*, 8 *End of file*, and so on
— the status→report table is in `PROTOCOL_FROM_ROM.md`).

Two further gotchas for anyone repeating this, on top of §10.5's:

- **Error reports cannot be read off the screen.** The report is printed to the
  lower screen and then wiped as soon as the editor redraws its input line, so
  `get-ocr` almost always shows a bare `K`. Control: `RETURN` with no `GOSUB` —
  a guaranteed instant error — also leaves no trace on screen. (`LOAD ""`
  *appears* to persist only because it takes ~20 s to time out, so the OCR lands
  inside the window.) Capture `ERR_NR` at `$0055` instead.
- **Arm that breakpoint after boot, not on the command line.** Passing
  `--set-breakpoint 1 PC=0058H` at launch hangs startup with a blank screen;
  setting the same breakpoint over ZRCP once the editor is up works fine.

### 10.7 SYSCON channel format — reverse-engineered

`SYSCON` (`$5CBC`) is the TS-2068's **system-configuration table**: the
Timex-designed mechanism for registering channels beyond the built-in K/S/P.
Reverse-engineered from the genuine HOME ROM's own consumers, cross-checked
against a live boot and against the Zebra OS-64 reimplementation.

**Live state on a booted TS-PICO:** `SYSCON = $5EEA` (in RAM, above the sysvars),
and the table is **empty** — a 12-byte header then an immediate `$80` terminator
(`FF 00 FF FF FF FF FF FF 00 FF FF FF 80 …`). Nothing registers extension
channels today, so the mechanism is dormant and free for us to use.

**How streams reach SYSCON.** The per-stream word in `STRMS` (`$5C10`) is an offset
with a flag in its **high byte**:

- `$0000` → stream closed.
- high bit **clear** → offset into `CHANS`; the channel record is `CHANS+offset-1`
  (the ordinary K/S/P/R path).
- high bit **set** → offset into `SYSCON`; the record is `SYSCON+(offset & $7FFF)`.
  Set at `$123F` (`CP $80` on the offset's high byte → `$1265`).

**Table shape.** Header is **12 bytes**; entries begin at `SYSCON+12`; the scanner
(`FIND_SYSCON`, `$1374`) strides **22 bytes** per entry and stops at a `+0 == $80`.
Two header fields are used by the banked-output path: **header+2..3** is a pointer
to a secondary bank-map table (`$17CF`), and **header+4** is a bank number fed to
`BANK_ENABLE` (`$6499`) at `$17C0`.

**Entry layout (type `$01`, a code-letter channel)** — the offsets each consumer
actually reads:

| Off | Field | Read by |
|---|---|---|
| `+0` | tag: `$01` = code channel, `$00` = empty slot, `$80` = end of table | scanner `$1374` (`CP $01`), close `$13DF` (`CP $00/$80`) |
| `+1` | **bank** number for the handler | open `$1499` (`LD B`), close `$13E7` |
| `+2` | **channel code letter** (what `OPEN #n,"X"` matches) | scanner `$1387` (`CP C`) |
| `+3..4` | **OPEN** handler pointer | open `$149E–$14A0` |
| `+5..6` | **CLOSE** handler pointer | close `$13EC–$13EE` |
| `+7..21` | handler-private (further bank/pointer pairs for the other subfunctions) | — |

**The catch: SYSCON handlers are banked device drivers, not plain vectors.** They
are not called like a CHANS out/in routine. They are invoked through the RAM
bank-dispatcher **`$65D0`** with the entry's `bank` (`+1`) and a **subfunction code**
in `C`:

| Subfunction | `C` | Call site |
|---|---|---|
| OPEN | `$88` | `$149A` |
| CLOSE | `$02` | `$13FA` |

So registering a disk channel in SYSCON means **conforming to the `$65D0`
banked-driver ABI** — a bank byte, handlers reachable in that bank, and dispatch
by subfunction — with `$6499`/`$65D0` (both RAM-resident, copied from EXROM at
boot) in the loop. This is exactly how a DOCK-cartridge disk system would
integrate, and it also unlocks the ≥128 "system console" stream space. It is
**not** a simple "add a row of vectors" table.

**Consequence for the design (resolves the Route A/B choice in §6.1).** Because
SYSCON is a banked-driver ABI, the pragmatic path is **Route B — a direct `CHANS`
channel record** (5-byte `out/in/letter` header, extended Interface-1-style with
buffer + handle state), reached by a small hook on `OPEN #`'s letter dispatch, with
out/in routines in a HOME-paged RAM driver. Route A (a real SYSCON entry) is now
fully characterized and remains open as the "fully native" option — worth it only
if we want disk streams to behave identically to a Timex peripheral, including in
banked contexts, and are willing to implement the `$65D0` subfunction ABI.

```bash
# Re-derive the entry field offsets from the genuine ROM's own consumers.
z80dasm -a -g 0 ROMs/GENUINE-2068-home.bin > /tmp/home.asm 2>/dev/null
sed -n '/;1374/,/;139e/p; /;13d8/,/;1406/p; /;1488/,/;14c6/p' /tmp/home.asm
```
