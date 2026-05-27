# Dual-Port PIO — How We Got Here

A development narrative for contributors who weren't on the original
work, walking through how the dual-port PIO architecture came together,
what wrong turns we took, what the test harnesses unlocked, and what
the three "latent" bugs taught us.

This is *not* the architecture spec — that's [`PROTOCOL.md`](PROTOCOL.md).
This is the **journey**: why the code looks the way it does, what
alternatives were tried and rejected, and which moments in the work
shifted our understanding of the problem.

If you're going to extend or modify the dual-port code, read this
*after* PROTOCOL.md and GUSTAVO_PROTOCOL.md. The patterns will make a
lot more sense once you've seen how they were earned.

---

## 1. The starting point: the "Report D" problem

Production firmware (v1.5) had been shipping for a while with a known
intermittent bug: every so often a `LOAD ""` would fail with
**Report D — BREAK CONT repeats** on the TS-2068. Bigger files
triggered it more often, but small files weren't immune.

Investigation (see `tspico-d-error-team-summary.txt` and
`tspico-d-error-code-context.txt` in the TS2068 reference library)
traced the cause to a tri-state window during the SD-card↔PIO bus
mode transition. The TS-2068 has a pullup resistor on data line D6
(added at Gustavo's request). When the bus floats during the SPI→PIO
handover, D6 gets pulled high. The Z80's `WF_NPH` polling loop tests
`BIT 6,A` and interprets a floating-but-D6-high bus as "continue."
The Z80 then immediately reads the next byte for status — but the Pico
isn't driving valid data yet, so the Z80 reads garbage. Anything not
matching status code `1` (`0x01 = OK`) triggers Report D.

The intermittent nature came from the race between the Pico reclaiming
the bus and the Z80 issuing its next IN instruction.

## 2. The initial theory: dual-port architecture

The original v1.5 firmware uses a **single-port** PIO design where ports
`$0E` (data) and `$0F` (status) share the same TX FIFO — both Z80 IN
operations on either port drain the same queue. The firmware coordinates
status and data by interleaving specific values (`0x40` for "continue,"
`0x01` for "OK status," then the actual data bytes).

Per Gustavo's TPI v2.4 protocol spec, ports `$0E` and `$0F` are
*supposed* to be functionally separate. v1.5 collapses them; the spec
assumes them split. Splitting them at the PIO layer would:

- Decouple status timing from data timing (no more "0x40 in the FIFO
  has to come at the right moment")
- Eliminate the SD↔PIO transition race (status is no longer tied to
  whatever bytes happen to be in the FIFO)
- Bring the implementation back into alignment with Gustavo's spec

So the plan: write a new `TS_IO_DUAL` PIO program that decodes address
bit `A0` (at GPIO 10) to distinguish reads on `$0E` vs `$0F`, and route
`$0F` to a hardware status register independent of the FIFO.

## 3. First attempts, wrong turns, and what they taught us

The first weeks of dual-port work were rough. The PIO got written, but
real LOAD operations failed. We chased several theories:

### 3a. The "busy/ready" dance

Initial design: have the Pico's PIO `Y` register represent the
ready/busy flag. Set Y=0 (busy) when entering a handler, do prep work,
then set Y=0xFFFFFFFF (ready) when the response was queued in TX. The
Z80's `$0F` polls would see "busy" while we worked, then see "ready"
and proceed.

This was a port of the v1.5 single-port "wrt(0x40) only after prep"
pattern, naively. **It didn't work.** The Z80's `WF_NPH` loop was timing
out before our prep finished.

We thought the budget was 2.8ms (per the spec). It actually wasn't —
see §4 — but we didn't know that yet.

### 3b. The `pull(block)` experiment

Hypothesis: if the PIO state machine stalls on `pull(block)` when TX
FIFO is empty, that should hardware-wait the Z80 (via the `/WAIT`
line). Pico gets unlimited time; Z80 doesn't time out.

We swapped `pull(noblock)` → `pull(block)`. Result: **complete bus
freeze.** No protocol activity at all.

The lesson came in two parts. First: the TS-Pico hardware *doesn't*
route the SM's stall to the Z80's `/WAIT` line. There IS no hardware
WAIT mechanism on the parallel port. Second, more subtly: when the SM
stalls inside a transaction (mid `/PICOSEL`-low cycle), it can't
respond to subsequent bus cycles. The bus quietly hangs.

`pull(noblock)` is the right setting **even though it means an empty
FIFO causes the Z80 to read 0x00**. That zero is "Report J — Invalid
I/O Device," which is loud and obvious. The architecture's contract:
keep the FIFO populated at the right moments.

### 3c. The "race the 2.8ms" panic

Once we accepted `pull(noblock)`, we started obsessing over the spec's
2.8ms WF_NPH timeout. We tried buffering all telemetry prints, removing
GC pauses, pre-computing data ahead of time — anything to fit prep work
into 2.8ms.

Then the user dropped this insight:

> The spec says 2.8ms but Gustavo's actual ROM uses ~20 seconds. He
> extended the timeout years ago after we discussed it.

This single sentence reframed the entire problem. We had **20 seconds**,
not 2.8ms, to respond to any single status check. That's enough time to
mount an SD card, read a file, do anything reasonable.

The remaining timing constraint — keeping TX FIFO populated during the
data-loop reads — is governed by Z80's own ~47µs/byte read pace, which
is *much slower* than MicroPython's `MQ.put()`. So as long as we don't
inject orphan bytes (more on that in §8), the protocol just works.

## 4. The pivot: build observers before fixing code

After multiple failed attempts to debug live LOAD failures by reading
production code paths, we decided to step back and **observe**. What
exactly is the Z80 sending? When? What is it expecting back? We didn't
know with certainty — we had the spec and the disassembly, which
disagreed in places, and we had production firmware whose behavior we
couldn't trust.

So we built `test/protocol_observer_silent.py` — does nothing but log
every Z80 OUT to a buffer with microsecond timestamps, dumps the buffer
on Ctrl-C. From there, every subsequent harness was a deliberate small
extension to test one new hypothesis at a time. **This was the unlock.**

## 5. Walking through the test harness suite

Here's each harness in chronological order, what it tested, and what
it taught us. All live in `/test`. They're standalone — copy to the
Pico via Thonny, run, observe, Ctrl-C to dump.

### 5a. `test/protocol_observer_silent.py` — observe with zero response

**What it does:** Sets up ROM_SM/BANK_SM (so TS-2068 can boot), starts
MQ with Y=0xFFFFFFFF (always ready). Doesn't write a single byte to TX
FIFO. Just tight-loops draining RX into a pre-allocated buffer. Ctrl-C
dumps the buffer with timestamps + delta-times.

**What it taught us:** The pure shape of the pre-header.

- Z80 emits exactly **9-10 bytes** for the pre-header (we expected 10
  per spec; saw 9 in the silent log because the 10th was lost to PIO
  RX FIFO overflow during a Python `.append()` GC pause — which itself
  was a useful discovery).
- Inter-byte delta is consistently ~30µs — Z80's natural OUT rate.
- After the last pre-header byte, the Z80 immediately reads `$0E`
  for status. With nothing in TX, it gets 0x00 = Report J.

This observer eliminated all detection-order ambiguity ("did Pico see
the OUT before the IN? we don't know"). With *no* Pico response at
all, what we logged was what was actually on the wire.

### 5b. `test/protocol_observer_v3.py` — capture-then-respond

**What it does:** Tight pre-allocated capture (no `.append()`, no GC).
After 10 RX bytes captured, write `0x01` to TX as the status response.
Continue capturing. Dump on Ctrl-C.

**What it taught us:** Pico's reaction time is much too slow.

- All 10 pre-header bytes captured cleanly (no drops with the tight
  loop — confirmed the silent-observer's "9 bytes" was a GC artifact).
- The XOR of bytes 0-8 matched byte 9 exactly: **CRC formula confirmed**
  (`pre[9] = XOR of pre[0..8]`).
- Pico took **43µs** between capturing byte 10 and writing `0x01`.
  Z80 read `$0E` for status at **~8µs** after byte 9 hit the bus —
  35µs before our response. Z80 read stale 0x00 → Report J → never
  got to the OUT-block_type-ack phase.
- Zero post-status RX events: confirmation that Z80 had bailed out
  before the data phase.

This was the moment we realized the protocol contract is "the FIFO
must already have the right bytes when Z80 reads," not "respond fast."

### 5c. `test/protocol_observer_v4.py` — pre-load the status byte

**What it does:** Same as V3 but pre-loads `0x01` in TX FIFO at startup,
before the first Z80 transaction. The Pico has nothing to do at byte 10
because the response is already waiting.

**What it taught us:** The full LOAD-header round trip.

```
Pre-header (10 bytes), all CRC-MATCHing      ✓
Z80 reads our pre-loaded 0x01 status         ✓
Block_type ack:  88,059 µs after byte 9      (?!)
Z80 computed CRC: arrives just after ack     ✓
```

**The 88ms gap was a revelation.** The spec says 2.8ms; Gustavo's ROM
uses 20s. Empirically, Z80 takes ~88ms between status read and OUT-of-
ack on the actual hardware. That's not the timeout — that's just how
long Z80's BASIC and screen routines take internally between phases.

So Pico has 88ms+ of slack inside a single LOAD transaction. **We were
never timing-bound the way we thought.** Plenty of time for any
reasonable file I/O.

### 5d. `test/protocol_observer_v5.py` — first real LOAD response

**What it does:** Mounts SD, copies `pt.tap` to Pico flash, pre-opens
it. After capturing the 10-byte pre-header, reads the TAP file's first
block (header block) and streams it to TX in the spec-prescribed order:
`block_type, content[0..16], CRC`. Captures the Z80's two-byte echo
(block_type ack + computed CRC), writes `0x01` final status.

**What it taught us:** The header phase actually works end-to-end.

When run, the TS-2068 displayed **"Program: tspicotest"** on screen.
First time we'd seen anything other than an error. The header LOAD
fully succeeded; the Z80 ROM accepted our bytes, parsed the header,
displayed the loading message, and started a new pre-header asking for
the data block.

Z80's computed CRC matched the file CRC exactly (`0x05` in our test).
**End-to-end byte fidelity confirmed.**

This was the breakthrough moment. Protocol layer worked. Just needed
to extend to the data block.

### 5e. `test/protocol_observer_v6.py` — full LOAD (header + data)

**What it does:** Same as V5, but the dispatch loop handles **any**
pre-header (header OR data block). After completing one transaction,
it loops back, captures the next pre-header, advances the TAP file
offset, sends the next block.

**What it taught us:** The complete LOAD works.

When run with `LOAD ""` on the TS-2068:

```
Iter 1 (header, 19 bytes):  pre-CRC ✓  ack ✓  Z80-CRC ✓
Iter 2 (data, 14166 bytes): pre-CRC ✓  ack ✓  Z80-CRC ✓
```

The TS-2068 displayed "Program: tspicotest" and **ran the program**.
First fully working LOAD via dual-port PIO.

The data block transferred in ~666ms (14165 bytes × ~47µs/byte) — Pico
streamed via `MQ.put` paced by the Z80's read rate. Zero FIFO underruns,
zero lost bytes.

V6 became the **gold-standard reference implementation**. Every
subsequent firmware change was validated by ensuring V6 still worked.

### 5f. `test/protocol_observer_v7.py` — LOAD + VERIFY support

**What it does:** Same as V6 but resets the TAP file offset to 0
whenever a new HEADER pre-header arrives (`pre[0] == 0x00`). This
allows back-to-back commands like `LOAD ""` followed by `VERIFY ""` to
each start fresh from the top of the TAP.

**What it taught us:** VERIFY uses the same protocol as LOAD.

VERIFY's `TADDR` is 2 (vs LOAD's 1), but from the Pico's side the byte
sequence is identical. Z80 reads our header + data bytes and compares
them against memory instead of storing — but the wire-level transactions
look the same.

We also discovered an interaction issue: VERIFY against a *running*
auto-run program (like tspicotest) fails because the program has
modified memory since the LOAD. That's a Z80-side semantic, not our
protocol problem — but worth knowing.

### 5g. `test/protocol_observer_v8.py` — embedded test TAP, no SD needed

**What it does:** Same as V7 but the test TAP is **embedded** as a 51-
byte tuple right in the script. No SD card setup. The embedded program
is `10 PRINT "test" / 20 GO TO 10` with autorun OFF, so after LOAD the
TS-2068 sits at the BASIC ready prompt (memory unchanged), making it
safe to VERIFY without the running-program problem from V7.

**What it taught us:** VERIFY round-trip works cleanly in the absence
of program-induced memory mutation. Z80 reported `0 OK` after VERIFY.
**End-to-end confirmation that LOAD and VERIFY produce byte-identical
transfers.**

### 5h. `test/save_observer.py` — capture Z80 SAVE protocol

**What it does:** Captures every byte the Z80 sends during a SAVE
operation. Decodes the three phases (pre-header → 21-byte HEADER block
→ N-byte DATA block) and reconstructs a valid TAP file at
`/TMP/saved.tap` that you can copy off the Pico and re-LOAD elsewhere.

**What it taught us:** SAVE works, and the CRC formula has a quirk.

Initial CRC verification failed in our observer. Looking at v1.5's
`SAVE_TS` source revealed: the CRC formula on SAVE blocks **skips bytes
[1] and [2]**, which are the 2-byte session ID — a TPI extension, not
part of standard ZX TAP CRC. This makes saved blocks convertible to/from
standard TAP files (just strip session bytes). Once we updated the
observer's CRC verifier to skip bytes [1]/[2], everything matched.

This revealed a non-obvious protocol detail that's documented in
`PROTOCOL.md §6` and `GUSTAVO_PROTOCOL.md §6`. Anyone implementing a
new SAVE handler has to remember it.

### 5i. `test/make_test_tap.py` — TAP file generator

**What it does:** A standalone Python script (runs on host, not Pico)
that generates `test/test.tap` — a 51-byte TAP file containing the
"PRINT test / GO TO 10" program with the autorun bit OFF. Used by V8.

**What it taught us:** Useful as a template for anyone needing to
hand-craft test TAP files for new test scenarios.

### 5k. The 2026 follow-up series — bare LOAD investigation

After the dual-port migration shipped, a separate puzzle remained:
`LOAD ""` (without a prior MOUNT) was returning Report J on the 2068.
We built four more harnesses to dig into it, and **one of them taught
us a new lesson about how NOT to write a harness.**

#### 5k.i. `test/protocol_observer_nomount.py` — bare-LOAD observer

**What it does:** Same V8-style setup, but specifically targeted at the
`LOAD ""` (no prior mount) case. Tracks RX events AND TX-drain events
(when `MQ.tx_fifo()` decreases, i.e. when the Z80 reads our pre-loaded
status). Periodic FIFO snapshots every 100ms.

**What it taught us:** the bare-LOAD pre-header on the wire is a
properly-formed 10-byte pre-header with valid CRC — not a malformed
sentinel as we initially suspected. The Report J was caused by missing
`/assets/nofile.tap` on the Pico flash, not by anything wire-level.
(See the Open Questions doc for the resulting work; production now
pre-opens the no-file fallback at boot to avoid an open() race in the
hot path.)

#### 5k.ii. `test/protocol_observer_crc.py` — first CRC-checking harness ⚠️

**What it does:** After capturing each pre-header byte, computes a
running XOR. At byte 9 (the spec-defined CRC byte), checks the XOR
against the received CRC and responds with `(XOR_total + 1) & 0xFF`
per Gustavo's spec p.2 rule (`status = XOR(all received bytes) + 1`).

**What it taught us — the buffer-read mistake we want to make sure
nobody repeats:**

This harness produced a confusing result: the bare-LOAD trace showed
only **9 bytes** captured, with no CRC byte at index 9. We chased
several wrong theories from that data:

  - "Maybe the pre-header is actually 9 bytes for bare LOAD."
  - "Maybe the Z80 short-circuits the protocol after reading our
    boot-pre-loaded `0x01`."
  - "Maybe Gustavo's spec disagrees with the actual ROM."

When we finally compared against production telemetry, production was
seeing the full 10-byte pre-header with a valid CRC. **The bytes were
on the wire. Our harness was dropping one of them.**

The cause: the harness called an `on_rx(idx, val, port, t)` callback
once per byte, inside the capture loop. The callback did Python-level
work (XOR, conditional, `MQ.put` at byte 9). Combined with attribute
lookups, timestamp calls, and bounds checks, the per-iteration time
crept up enough that — combined with normal interpreter jitter — the
4-deep PIO RX FIFO occasionally overflowed. PIO `push noblock` then
silently dropped the overflowing byte. The Z80 kept going (it doesn't
know about the FIFO state), our trace just looked truncated.

The fix is the **two-phase capture pattern** now baked into the
template: PHASE 1 is a tight blocking burst-read with NO Python work
between gets (matching production's `for i in r1: pre[i] = MQ.get()`);
PHASE 2 runs after the burst completes and does all the math/response
work. The Z80's `WAIT EXECUTION` budget (2.8ms) is more than enough
time for PHASE 2 work.

**Lesson:** capture and decision are two different jobs. Don't
interleave them. If a harness sees fewer bytes than production, the
first thing to check is "am I doing per-byte Python work?" before
inventing protocol theories.

This is documented in `test/_harness_template.py`'s top docstring as
the "TWO-PHASE CAPTURE PATTERN" rule.

#### 5k.iii. `test/protocol_observer_crc_named.py` — comparison harness

**What it does:** Identical to 5k.ii but prompts you to type
`LOAD "TEST"` instead of bare `LOAD ""`. The intent was to compare a
named LOAD against the bare LOAD to see whether the difference
explained the observed truncation.

**What it taught us:** both produced the same 9-byte truncated
capture, in the same shape. That ruled out "bare LOAD is special" and
focused suspicion on the harness itself — which led us to 5k.ii's
diagnosis. The harness is kept as a record of the diff that pointed
us in the right direction.

#### 5k.iv. `test/protocol_observer_multicmd.py` — multi-command observer

**What it does:** Stays alive across multiple commands by auto-
refilling `0x01` whenever TX FIFO drains to empty (mimicking V6
production handler-tail behavior). Captures three event types: RX
bytes, TX-drains, auto-refills. Phase-grouped dump.

**What it taught us:** designed to capture a `LOAD "tpi:pt.tap"` →
`LOAD ""` sequence end-to-end, but never produced clean data because
it inherits the same per-byte hot-loop pattern as 5k.ii. A revised
version using the new template's two-phase capture pattern is on the
TODO list. Kept as a reference for the auto-refill technique.

### 5j. Earlier exploratory harnesses

Two earlier files in `/test` predate the observer series and are kept
for historical interest:

- `test/dual_port_test.py` — minimal harness that just sets up the
  dual-port PIO and prints raw events. Used early on to verify the PIO
  itself was working before we layered protocol logic on top.
- `test/lvm_test.py` — V3-era integration attempt that mounted SD and
  tried a real LVM LOAD with the busy/ready dance. Useful as a record
  of where we started.
- `test/protocol_observer.py` — earliest "buffered telemetry observer."
  Superseded by V3 onwards but kept since it has different setup logic
  worth comparing.

These aren't part of the proven test suite but they're checked in to
show the development arc.

## 6. Insights the harnesses unlocked

In rough order of "size of impact":

1. **`pull(noblock)` is the only correct setting for `$0E`.** The
   hardware doesn't HW-WAIT on `pull(block)` stalls. (3b)
2. **Z80's effective response budget is 20 seconds, not 2.8ms.** Removed
   all the timing panic. (3c, 5c)
3. **An 88ms gap between Z80's status read and block_type ack is
   normal** — internal Z80 ROM processing, not a timeout. (5c)
4. **The protocol contract is "right bytes in TX at the right time,"
   not "respond fast."** Pre-loading + the chained `MQ.put(0x01)` tail
   beats trying to react in microseconds. (5b → 5c)
5. **Pre-header CRC = XOR of all 10 bytes** (no skipping). (5b)
6. **Block-data CRC = XOR of all bytes EXCEPT session bytes [1][2]** —
   the TPI quirk. (5h)
7. **VERIFY uses the same wire protocol as LOAD.** No new code path
   needed. (5f)
8. **MicroPython is much faster than Z80's ~47µs/byte read rate.**
   `MQ.put` blocking when FIFO is full provides natural pacing. (5e)
9. **The PIO RX FIFO is 4 deep, and per-byte Python work in the capture
   loop will overflow it.** `push noblock` then silently drops bytes.
   Production's `for i in r1: pre[i] = MQ.get()` (lines 4060-4061 of
   `TS/tspico.py`) is non-negotiable: NO conditionals, math, or
   callbacks between successive gets. Decision work belongs in a
   separate phase that runs after the burst is complete. (5k.ii)
9. **Stray bytes in TX FIFO get consumed at the wrong protocol moment.**
   This pattern caused all three latent bugs in §8. (5a, 5b)

## 7. Folding the V6 pattern into production firmware

With V6 proven, the next phase was migrating the production handlers
in `TS/tspico_io.py` and `TS/tspico.py` to match.

**The V6 pattern**, distilled:

- Y register = `0xFFFFFFFF` always; never toggled to busy.
- Each handler ends with **two** `MQ.put(0x01)` writes:
  - first = this iteration's final status (Z80 reads it)
  - second = pre-load for the *next* iteration's initial status
- One-time `MQ.put(0x01)` at boot in `TS2068_IO()` to seed the chain.
- No `wrt(0x40)` anywhere — Y handles `$0F` continue.
- No `MQ_BUSY()` calls in the LVM path (legacy helpers retained but
  documented as "rarely needed").

We migrated:

- `LOAD_TS` (`TS/tspico_io.py`) — header + data block streaming
- `SAVE_TS` (`TS/tspico_io.py`) — three-phase receive (pre-header →
  21-byte header → BLEN+4 data) with CRC validation
- `PROCESS_CMD` (`TS/tspico.py`) — BASIC commands like `TPI:DIR`
- `PROCESS_ASM` (`TS/tspico.py`) — assembler commands (stub)
- `ACTIVATE_MQ` (`TS/tspico.py`) — sets Y=READY at MQ activation

Once each was migrated, we re-flashed the UF2 and re-ran the same
LOAD/VERIFY/SAVE tests through the real firmware (not just the
observers). All passed.

## 8. The three latent bugs we discovered post-migration

Within the first few real-firmware test runs, three bugs surfaced.
They're worth understanding because they all have the **same shape**:
a stray byte ends up in TX FIFO and gets consumed at the wrong
protocol moment.

### Bug 1: `ACTIVATE_MQ` pre-loaded a duplicate status

**Symptom:** First `LOAD "tpi:pt.tap"` worked. Second one hung in
`SEND_MSG` with TX still containing one byte after a million drain
loops. The TS-2068 displayed Report J.

**Cause:** I'd put `MQ.put(0x01)` at the end of `ACTIVATE_MQ`. That
worked at boot — Z80's first read of `$0E` found the byte. But
`ACTIVATE_MQ` is also called *mid-command* (after SD card access in
`MOUNT_FILE`). Mid-command, the next operation in the chain is
`SEND_MSG`, which writes its own `0x01` status. Result: TX = [0x01,
0x01]. Z80 reads ONE byte and considers the response complete; the
second sits in TX forever.

**Fix:** Remove the pre-load from `ACTIVATE_MQ`; do it once at boot
in `TS2068_IO()` instead.

### Bug 2: `kill` global referenced before initialization

**Symptom:** `NameError: name 'kill' isn't defined` on the first call
to `LOAD_TS`.

**Cause:** `LOAD_TS` spawns the `WATCHDOG` thread on core1 via
`_thread.start_new_thread`, then immediately enters the streaming loop
that checks `if kill:`. The watchdog thread's `global kill; kill = False`
hadn't run yet — race condition. v1.5 had the same race; it just usually
won on production silicon.

**Fix:** Initialize `kill`, `busy`, `dead`, `log_entries` at
*module level* in `TS/tspico_io.py` so the race is impossible.

### Bug 3: `END_MSG` left a phantom byte after the V6 writes

**Symptom:** Header LOAD succeeded ("Program: tspicotest" displayed),
then the data block transfer failed with **Report R — Tape Loading
Error**.

**Cause:** My migrated `LOAD_TS` / `SAVE_TS` wrote the V6 pattern
correctly — final status + pre-load — but then *also* called
`END_MSG()`, which writes its own `0x01` status byte. That third byte
sat in TX after the Z80 finished reading the final status; on the next
iteration's data-loop reads, it was consumed as the first content byte.
Z80's CRC accumulator drifted by one byte from the start, and the final
file-CRC byte didn't match. Hence Report R, but only on the data block.

**Fix:** Remove `END_MSG()` from `LOAD_TS` and `SAVE_TS`; they're
already complete via the V6 pre-load chain.

### The pattern across all three

- Bug 1: `ACTIVATE_MQ` injected a stray byte mid-command.
- Bug 2: not a stray-byte bug, but a race that prevented the streaming
  loop from running cleanly.
- Bug 3: `END_MSG` injected a stray byte at end-of-handler.

**Bugs 1 and 3 are the same shape**: a single extra byte in TX FIFO
gets consumed at a moment in the protocol where the Z80 was expecting
something specific. Z80 has no way to know it's the wrong byte — it
just XORs it into the CRC accumulator and proceeds, so the failure
shows up as a corrupt CRC at the *end* of a much later phase.

The lesson: **respect the byte chain.** Every `MQ.put()` you add to a
handler is a byte the Z80 will eventually read, in some order. There's
no way to "speculatively" load TX. If you put more bytes than the Z80
will consume in the current transaction, the leftovers corrupt the
next one.

`PROTOCOL.md §7` documents these three pitfalls (and a few related
ones) so future contributors don't repeat them.

## 9. Repo cleanup and audit

Once production firmware was working, we did several cleanup passes:

- **Move `src/TS/` → `TS/`** — the `src/` wrapper served no purpose
  for a frozen-modules build; flatter is clearer.
- **Prune `manifest.py`** — dropped 5 unused MicroPython freeze
  dependencies (`uasyncio`, `onewire`, `ds18x20`, `dht`, `neopixel`).
  The TS-Pico has none of those peripherals; saves ~6KB flash + ~20KB
  RAM.
- **End-to-end dual-port compliance scan** — found 5 latent
  `wrt(0x40)` calls in scrolling-output handlers (`SEND_MSG2`, `DIR`,
  `ChangeDirMenu`, `SEND_MSG_PROMPT_YN`, and `extcmd.py:RND_WORD`).
  These would have caused orphan-byte bugs the moment the user
  triggered a multi-page DIR or used the example external commands.
  Fixed before they bit anyone.
- **Flag legacy ZX-compat handlers** — `LOAD_ZX`, `LOAD_ZX_C`,
  `SAVE_ZX`, `ZX48_IO` are still single-port code. They're dormant
  (`ZX_TAPE_COMPAT=False` by default; entering ZX48 mode requires
  explicit user opt-in via `TPI:ZX48`). Banner docstrings warn anyone
  who enables those modes that migration is required first.
- **Comprehensive comment pass** — every PIO instruction in
  `TS_IO_DUAL` has line-by-line annotations of register effects;
  every helper function has a docstring; the dispatcher has a
  high-level overview at the top.
- **Two new contributor docs** — `docs/GUSTAVO_PROTOCOL.md` (design
  view: what Gustavo built and why) and `docs/PROTOCOL.md`
  (implementation view: what Pico does to honor the spec). The
  README points to both in reading order.
- **Single `TLM_ENABLED` switch** for telemetry — toggle at the top
  of `TS/tspico.py`, in `main.py` (most convenient — no UF2 rebuild),
  or at the REPL.

## 10. Workflow suggestions for future contributors

If you're going to extend or modify the dual-port code, here are the
patterns that worked for us:

### Don't trust the production firmware in isolation

The dual-port architecture is correct, but it's easy to break with a
single misplaced `MQ.put()`. The tight coupling between handler logic
and FIFO state means small changes can cause distant failures. Always
validate against:

1. **A protocol observer harness** — for any new wire-level work,
   start with `protocol_observer_v8.py` as a template, modify it to
   exercise just the path you're changing, and observe the actual
   bytes. Don't assume the spec describes reality.
2. **A repeatable test program** — `test/test.tap` (the embedded
   `PRINT "test"` loop) is intentionally tiny and non-autoruns, so
   you can LOAD, VERIFY, RUN, and BREAK in any order without memory
   drift.

### Commit incrementally; observers are cheap

A new observer harness is ~200 lines of mostly-boilerplate Python.
The protocol_observer chain (V3 → V4 → V5 → V6) was each ~30-50 lines
of *actual change* from the previous one, plus log analysis. Each
one tested exactly one new hypothesis. That cadence made it easy to
backtrack when something didn't work — we always knew exactly which
change introduced the new behavior.

### Suspect the byte chain when CRCs go wrong

If you get `Report R - Tape Loading Error` after you've already gotten
"Bytes:" or "Program:" displayed on screen, **odds are very high** that
you've got a stray byte in TX FIFO somewhere — usually one too many
status writes, often as the last line of a handler. The TS-2068 is
correctly reporting that the data didn't match its CRC; what it can't
tell you is that the data would have matched if there hadn't been an
extra byte at the start.

### Keep telemetry off in shipping builds

`TLM_ENABLED = False` in `main.py` is the recommended setting for
end-user installs. Diagnostic prints over USB serial are the single
biggest source of timing weirdness in this codebase — they take
~5-10ms each, which is enough to disrupt protocol timing if they fire
in the wrong place.

### Read these in order, then come back here

1. `docs/GUSTAVO_PROTOCOL.md` — design view
2. `docs/PROTOCOL.md` — implementation view (especially §7 pitfalls)
3. This file — context for *why*

The first two are reference material. This one is meant to convey the
*shape* of the problem and the kind of debugging that the codebase
rewards.

---

## Acknowledgments

The dual-port architecture as actually shipped is the work of:

- **Gustavo Pane** — the protocol design and the modified Z80 ROM
  that all of this implements.
- **David Anderson** — directing the work, providing the critical
  "20-second timeout" insight that reframed the timing problem,
  validating each iteration on real hardware, and the patience to
  let the harness-driven approach play out across a long series of
  small experiments.
- **Claude (Anthropic, Opus 4.7)** — pair-programming through the
  iterations, holding context across the long session, and generating
  the test harnesses, firmware migrations, and documentation passes
  as the work progressed.

The harness-first approach is the thing worth carrying forward. When
the next ambiguity comes along — a new command type, a hardware
quirk, an unexpected error report — write an observer first. Look at
the bytes. The code will write itself once you know what's actually
happening on the wire.
