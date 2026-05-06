# Working on this codebase — orientation for AI agents (and humans)

If you're an AI assistant being pointed at this repo, or a contributor
looking for the "what should I read first" answer, this file is for you.
It captures the working style and gotchas that took us a while to learn
the hard way.

## TL;DR

1. **Read the docs in this order**:
   - [`README.md`](README.md) — what this project is and how to flash it
   - [`docs/GUSTAVO_PROTOCOL.md`](docs/GUSTAVO_PROTOCOL.md) — protocol design
   - [`docs/PROTOCOL.md`](docs/PROTOCOL.md) — firmware implementation
   - [`docs/DUAL_PORT_DEVELOPMENT.md`](docs/DUAL_PORT_DEVELOPMENT.md) —
     how the current code came to be, including all the wrong turns
2. **When investigating any wire-level bug, write a test harness first**.
   This is the pattern that unblocked the original dual-port work.
   Details below.
3. **Don't trust your protocol intuition until the bytes confirm it**.
   The spec, the Z80 disassembly, and the running ROM disagree in places.

---

## The harness-first methodology

When something on the protocol layer breaks, **don't start by editing
production code**. Start by isolating the failure in a standalone test
harness. We learned this the hard way during the dual-port migration —
chapter and verse in [`docs/DUAL_PORT_DEVELOPMENT.md`](docs/DUAL_PORT_DEVELOPMENT.md)
§4 onwards.

### Why harnesses are worth the upfront cost

- Production firmware mixes 30+ concerns into a single dispatch loop.
  Bugs caused by one concern manifest as failures in another. A harness
  isolates ONE thing.
- A harness that captures every byte with microsecond timestamps shows
  you what's *actually* on the wire — not what the spec says should be,
  not what the disassembly suggests, not what your mental model expects.
- Iterating on a 200-line standalone file is faster than iterating on a
  4,000-line dispatcher and reflashing the UF2 each time. (Harnesses
  run from Thonny's REPL — copy-paste, exec, observe.)
- When something works in the harness but not in production, the diff
  between them tells you exactly what's wrong.

### How to start a new harness

There's a starter template at [`test/_harness_template.py`](test/_harness_template.py).
**Copy this**, don't recreate from scratch:

```bash
cp test/_harness_template.py test/protocol_observer_<purpose>.py
```

The template handles all the boring boilerplate — pin setup, ROM_SM /
BANK_SM startup (without these the TS-2068 won't boot — easy to forget),
MQ activation, Y=READY initialization, boot-noise drain, pre-allocated
buffers, hot-path-friendly capture loop, Ctrl-C dump format. You fill
in three TODOs:

1. `PRE_RESPONSE` — bytes to put in TX FIFO at startup before any Z80
   activity (commonly just `(0x01,)` for the status pre-load chain)
2. `on_rx(idx, val, port, t)` — called for each Z80 OUT byte; this is
   where your response logic goes
3. `decode_and_dump()` — how to format the captured log on Ctrl-C

### Examples to study before writing your own

The `test/protocol_observer_v*.py` series in increasing capability:

- `protocol_observer_silent.py` — pure observation, no response at all
- `protocol_observer_v3.py` — capture-then-respond (showed the timing
  constraint we initially had wrong)
- `protocol_observer_v4.py` — pre-load status, capture full transaction
- `protocol_observer_v5.py` — first real LOAD response from a TAP file
- `protocol_observer_v6.py` — full LOAD (header + data), gold standard
- `protocol_observer_v7.py` — V6 + LOAD/VERIFY rewind support
- `protocol_observer_v8.py` — V7 + embedded test TAP, no SD card

Each one tested ONE new hypothesis vs the previous. That cadence is
exactly what made progress possible.

### When NOT to write a new harness

- The bug reproduces in an existing harness — modify that one, don't
  fork a new file.
- The bug is purely in Pico-side logic that doesn't depend on protocol
  timing (e.g., a string-formatting bug in a command handler). Just fix
  the production code.

## After the harness teaches you something

Once a harness reveals the actual behavior:

1. **Make the harness pass cleanly** — establish the bug-free behavior
   in isolation first.
2. **Fold the proven pattern into production** — copy the byte sequence,
   the Y register treatment, the FIFO ordering, etc.
3. **Re-test the same scenario through production firmware** — there
   are always production-only concerns the harness doesn't see (the
   dispatcher, MOUNT_FILE, watchdog, etc.).
4. **Document the gotcha** — `docs/PROTOCOL.md` §7 has a "pitfalls"
   list. If your debugging found a non-obvious trap, add it. Future
   contributors will thank you.
5. **Keep the harness in `/test/`** — even if it's purpose-built for
   one bug, leave it. It's documentation of how to think about that
   class of problem.

## Common gotchas (the orphan-byte family)

The dual-port architecture is correct, but its design has a property
worth respecting: **every byte in the TX FIFO will be consumed by the
Z80 at some specific protocol moment**. Putting a byte in the wrong
place doesn't cause an immediate error; it gets misinterpreted at a
later moment, often a phase or two downstream. Three real bugs of this
shape are documented in `docs/DUAL_PORT_DEVELOPMENT.md` §8.

### Symptom-to-cause mapping

- **`Report J - Invalid I/O Device`** appears immediately or after a
  short delay → status byte is missing or zero. Check that the
  pre-load chain is intact (every handler ends with `MQ.put(0x01)`),
  that no extra `MQ.put` got added between the dispatch and the response,
  and that the cached `_nofile_arch` (if applicable) is initialized.

- **`Report R - Tape Loading Error`** during data block of a LOAD that
  succeeded at the header phase ("Bytes:" displayed first) → there's a
  stray byte in TX between iterations that shifted the data block by
  one byte. Usual culprits: an extra `END_MSG()` call after a V6-pattern
  handler tail, or a stale `wrt(0x40)` left from single-port days.

- **`Report J` after a long delay (~3-5 seconds)** → handler was stuck
  on `MQ.put` (TX full, Z80 not reading) or `MQ.get` (RX empty, Z80 not
  writing); watchdog fired and killed the operation. Check whether the
  Z80 actually completed the previous protocol phase before you tried
  to receive an echo.

### Things to NEVER do without thinking carefully

- `MQ.put(0x40)` anywhere in dual-port code. The 0x40 was the single-
  port continue flag; in dual-port that role is played by the Y
  register. A 0x40 in TX is an orphan byte that will corrupt the next
  read.
- `END_MSG()` at the end of LVM handlers (LOAD_TS, SAVE_TS) that already
  do the V6 final-status-and-pre-load chain. END_MSG writes its own
  status byte — adding it after the V6 writes injects a third one that
  becomes an orphan.
- Pre-loading status bytes inside `ACTIVATE_MQ()`. That function is
  called both at boot AND mid-command (after SD operations); a pre-
  load there pollutes the TX FIFO during the second case. Boot-time
  pre-load goes in `TS2068_IO()` instead, ONCE.
- Open files inside `LOAD_TS()` for the time-critical path. Cold flash
  metadata makes the open take 1-5ms, during which the Z80 reads stale
  bytes. Pre-open at boot or at mount time, cache the handle.

## Structural conventions

- **`TS/`** — frozen modules, baked into the UF2 by `manifest.py`.
  Modifying these requires a rebuild + reflash.
- **`/main.py`, `/config.ini`, `/assets/*.tap`** — live on the Pico's
  flash filesystem, NOT frozen. Edit-and-reboot, no rebuild needed.
- **`/dev_tspico.py`** — optional development override. If present on
  the Pico's flash, `main.py` will use it instead of `TS.tspico`.
  Useful for iterating on `tspico.py` without rebuilds. (The override
  trick only works for `tspico.py`.)
- **`/test/`** — bus-level test harnesses (this guide).
- **`/docs/`** — three layers: protocol design, firmware implementation,
  development history.

## Telemetry

Set `TLM_ENABLED = False` in `/main.py` (line near top, after
`import TS.tspico`) to silence all `TLM()` and `TLM_RESET()` calls.
Default is `True` for development. Diagnostic prints over USB serial
take ~5-10ms each — long enough to disrupt protocol timing if they
fire in a hot path.

## When you're stuck

1. **Re-read your most recent change** carefully. The dual-port pattern
   is unforgiving of off-by-one byte counts; a one-character typo in
   `MQ.put` placement can cause distant CRC failures.
2. **Write or modify a test harness** to reproduce the failure in
   isolation. Don't keep flashing UF2s into a complex multi-handler
   environment hoping the bug surfaces.
3. **Look at the actual bytes**. The harness's microsecond timestamp
   log tells you exactly what happened in what order. Spec docs and
   disassembly are useful but secondary.
4. **Check `docs/DUAL_PORT_DEVELOPMENT.md` §6 (insights)** — there are
   nine non-obvious facts about the system written down explicitly so
   you don't re-derive them.

## Ground rules for AI agents

If you are an AI assistant working on this repo:

- **Don't fabricate.** If you're not sure what byte the Z80 expects at
  some position, write a harness and capture it. Don't guess from spec.
- **Be honest about what you tested.** If you migrated a handler but
  didn't run it on hardware, say so. Don't claim "tested and working"
  unless someone actually flashed and saw it work.
- **Reference real artifacts.** When you say "see V6 for this pattern,"
  link or quote the actual code. Don't paraphrase from memory.
- **Add to the pitfalls list.** If you found a new gotcha, add it to
  `docs/PROTOCOL.md` §7. Even if it seems obvious in retrospect, it
  wasn't obvious before someone hit it.
- **Trust the empirical evidence over the spec.** The TPI spec PDF is
  Gustavo's design intent; the real ROM is what's running. When they
  disagree, follow the ROM (which means write a harness to confirm).
