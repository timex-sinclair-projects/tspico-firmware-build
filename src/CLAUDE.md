# Working on this codebase — orientation for AI agents (and humans)

If you're an AI assistant being pointed at this repo, or a contributor
looking for the "what should I read first" answer, this file is for you.
It captures the working style and gotchas that took us a while to learn
the hard way.

## TL;DR

1. **Read the docs in this order**:
   - [`README.md`](README.md) — what this project is and how to flash it
   - [`docs/PROTOCOL_GUIDE.md`](docs/PROTOCOL_GUIDE.md) — the protocol in
     plain language
   - [`docs/PROTOCOL.md`](docs/PROTOCOL.md) — the byte-level reference
     (firmware 2.0, ROM 2.0/2.1), with the pitfalls list
   - [`docs/GUSTAVO_PROTOCOL.md`](docs/GUSTAVO_PROTOCOL.md) — the original
     design, as history (its opening note lists what has changed)
   - [`docs/DUAL_PORT_DEVELOPMENT.md`](docs/DUAL_PORT_DEVELOPMENT.md) —
     how the current code came to be, including all the wrong turns
2. **When investigating any wire-level bug, write a test harness first**.
   This is the pattern that unblocked the original dual-port work.
   Details below.
3. **Don't trust your protocol intuition until the bytes confirm it**.
   The spec, the Z80 disassembly, and the running ROM disagree in places.
4. **If a TS-Pico is plugged into this machine, talk to it yourself.**
   Flash UF2s, watch telemetry and use the REPL with
   [`tools/pico-serial.py`](../tools/pico-serial.py) -- don't ask the
   user to copy/paste from Thonny. See "Talking to the Pico directly".

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
2. `BURST_LEN` — bytes per Z80 burst (10 for the standard pre-header)
3. `decide_and_respond(buf, start, length, burst_num)` — runs ONCE PER
   BURST, AFTER the burst completes. CRC math, response logic, etc.
4. `decode_and_dump()` — how to format the captured log on Ctrl-C

### THE TWO-PHASE CAPTURE RULE — non-negotiable

**Never do per-byte Python work inside the capture loop.** The PIO RX
FIFO is 4 entries deep, the Z80 OUTs at ~30µs/byte, and any per-iteration
work (conditionals, math, callbacks, attribute lookups) risks letting
the FIFO overflow. PIO `push noblock` then silently drops bytes. The
Z80 doesn't notice. Your trace looks truncated and you chase ghosts.

This bit us in `test/protocol_observer_crc.py` — see
`docs/DUAL_PORT_DEVELOPMENT.md` §5k.ii for the full post-mortem.

The harness template enforces a two-phase pattern:

- **PHASE 1 (CAPTURE)** — tight blocking burst-read, NO Python work:
  ```python
  for i in range(BURST_LEN):
      buf[start + i] = MQ.get()    # blocking; matches production
  ```
- **PHASE 2 (DECISION)** — runs after the burst, in
  `decide_and_respond()`. This is where CRC math, response `MQ.put()`s,
  and analysis go. You have a 2.8ms `WAIT EXECUTION` budget here per
  spec — ample for any reasonable Python work.

Production's `RX_CAPTURE()` in `TS/tspico_io.py` (which `TS2068_IO()`
uses for every pre-header) is the canonical example: its loop only tests
the FIFO, gets and stores; the 1 s stall clock and the SYNC test run only
while the FIFO is empty. Match it.

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

Plus the 2026 follow-up series (documented in
`docs/DUAL_PORT_DEVELOPMENT.md` §5k):

- `protocol_observer_nomount.py` — bare-LOAD investigation
- `protocol_observer_crc.py` — the harness whose buffer-read mistake
  taught us the two-phase rule above. Read its post-mortem before
  writing any new harness.
- `protocol_observer_crc_named.py` — comparison harness for named LOAD
- `protocol_observer_multicmd.py` — multi-command auto-refill pattern

Each one tested ONE new hypothesis vs the previous. That cadence is
exactly what made progress possible.

### When NOT to write a new harness

- The bug reproduces in an existing harness — modify that one, don't
  fork a new file.
- The bug is purely in Pico-side logic that doesn't depend on protocol
  timing (e.g., a string-formatting bug in a command handler). Just fix
  the production code.

## After the harness teaches you something

Once a harness reveals the actual behavior, follow this sequence
**strictly** — each step has a real reason and skipping ahead has
historically caused regressions:

1. **Make the harness pass cleanly** — establish the bug-free behavior
   in isolation first.
2. **Get explicit user confirmation that the harness result is what
   they expected.** Use `AskUserQuestion` liberally here. "Does this
   trace match what you'd expect?" is a real question with real
   consequences — the user often has context the harness can't show
   (state of the 2068, contents of a mounted TAP, expected error
   reports). Do not propose moving anything to production until they
   say the harness is satisfying.
3. **Propose folding the proven pattern into production** — copy the
   byte sequence, the Y register treatment, the FIFO ordering, etc.
   Wait for user approval before editing production code.
4. **It's OK to put production-side changes on a branch for the user
   to test on real hardware.** Do this on a branch, not on main —
   see "GitHub workflow" below for the rules.
5. **Re-test the same scenario through production firmware** — there
   are always production-only concerns the harness doesn't see (the
   dispatcher, MOUNT_FILE, watchdog, etc.). Iterate on the branch
   until the user confirms it's working.
6. **Get explicit user confirmation again** — same as step 2, but for
   the production version. `AskUserQuestion`: "Does this fully
   resolve the issue?" Don't open a PR until they say yes.
7. **Open the PR.** GitHub's diff view automatically shows only the
   changes — no need to do anything special; that's the default.
8. **Document the gotcha** — `docs/PROTOCOL.md` §13 has a "pitfalls"
   list. If your debugging found a non-obvious trap, add it. Future
   contributors will thank you.
9. **Keep the harness in `src/test/`** — even if it's purpose-built for
   one bug, leave it. It's documentation of how to think about that
   class of problem.

## GitHub workflow — required for AI agents

All non-trivial code changes go through this flow. AI agents working
on this repo MUST follow these rules.

### Branches

- **Always work on a branch off `main`, never on main directly.** Even
  for "small" changes — a small change can still break something on
  the user's hardware, and main needs to stay shippable.
- **Branch names are descriptive, no convention prefix required.** Use
  short kebab-case names that say what the branch does:
  `crc-verification`, `nofile-tap-preopen`, `fix-bare-load-report-j`.
- Create the branch BEFORE making any production code edits:
  `git checkout -b crc-verification`.

### CI / UF2 builds

- **CI builds a UF2 for every pushed branch.** That's how the user
  tests your changes on real hardware without affecting anyone using
  the production UF2 from main.
- This means: push your branch early. Even before you're "done." The
  user can test as soon as CI builds. Iterate on the same branch.
- **Never push directly to main**, even for "trivial" doc-only
  changes. Main is what the production UF2 builds from.

### Pull requests

- **Open a PR only after the user confirms the change works.** Use
  `AskUserQuestion`: "Are you satisfied this is ready to merge?"
- The PR's diff view automatically shows only the changes. Don't
  worry about "submitting just the changes" — that's how PRs work.
- **PR description should explain WHY, not WHAT.** The diff says
  what; the description says why this is the right change and what
  alternatives were considered.
- **Link to the GitHub issue if there is one** ("fixes #N") so the
  issue auto-closes when the PR merges.

### Merging

- **Squash and merge** is the chosen strategy for this repo. Each PR
  becomes one clean commit on main, regardless of how messy the
  branch history was during iteration. Use this in `gh pr merge`:
  `gh pr merge --squash`.
- Do not use "Merge commit" or "Rebase and merge" without the user's
  explicit say-so.
- After merge, delete the branch: `gh pr merge --squash --delete-branch`.

### Line endings: set `merge.renormalize` once, before you merge anything

**Do this in every clone of this repo:**

```bash
git config merge.renormalize true
```

Without it, any branch created before `c897e91` conflicts with main on
**every line** of `src/TS/*.py`, `src/main.py` and `src/dev_tspico.py` —
a whole-file conflict in files that have no real overlap at all.

Why: those files are CRLF on disk but LF in the repo, pinned by
`.gitattributes`. `c897e91` added that and renormalized them, so older
branches still hold CRLF blobs and git finds no common lines to anchor on.
`merge.renormalize=true` normalizes both sides before comparing and the
merge comes out clean.

**Never hand-resolve one of these.** A whole-file conflict offers you two
complete copies of the file and no guidance; picking one silently discards
everything the other side did — in these files, potentially an entire PR's
worth of firmware changes. If a merge conflicts in a file you did not
expect, check for this before touching anything:

```bash
git show HEAD:src/TS/tspico_io.py | file -   # repo side: no CRLF
file src/TS/tspico_io.py                     # working tree: "with CRLF line terminators"
```

Storage LF + working tree CRLF is correct and healthy. It also means an
editor that rewrites a file as LF produces **no diff**, which is the point:
the accident that caused this (`79f12a1`, which made a 48-line fix read as
2425 insertions / 794 deletions and then blocked its own merge) can no
longer be committed.

The same trap applies to `git rebase` and `git cherry-pick`, which replay
commits through the same machinery and honour the config once it is set.
Verified: cherry-picking `8e896d2` (a pre-`c897e91` commit) onto main
conflicts in both `src/TS/tspico.py` and `src/dev_tspico.py` with the
config unset, and applies cleanly with it set.

### Quick reference

```bash
git config merge.renormalize true            # 0. once per clone (see above)
git checkout -b descriptive-branch-name      # 1. branch
# ... make changes, harness-test, etc.
git push -u origin descriptive-branch-name   # 2. push (triggers CI)
# ... user tests UF2 on hardware, iterate ...
gh issue create ...                          # 3. (if needed) open issue
gh pr create ...                             # 4. open PR after user OK
# ... review, fix, push more commits ...
gh pr merge --squash --delete-branch         # 5. merge after user OK
```

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
  one byte. Usual culprits: an extra status write after a V6-pattern
  handler tail (the removed `END_MSG()` helper was the classic one), or a stale `wrt(0x40)` left from single-port days.

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
- An extra status write at the end of LVM handlers (LOAD_TS, SAVE_TS),
  which already do the V6 final-status-and-pre-load chain. A third status
  byte after the V6 writes becomes an orphan. (The old `END_MSG()` helper
  did exactly this; it was removed by the 2026-09-30 audit.)
- Pre-loading status bytes inside `ACTIVATE_MQ()`. That function is
  called both at boot AND mid-command (after SD operations); a pre-
  load there pollutes the TX FIFO during the second case. Boot-time
  pre-load goes in `TS2068_IO()` instead, ONCE.
- Open files inside `LOAD_TS()` for the time-critical path. Cold flash
  metadata makes the open take 1-5ms, during which the Z80 reads stale
  bytes. Pre-open at boot or at mount time, cache the handle.

## Structural conventions

All firmware sources live under the repo's `src/` folder; paths below
are relative to that. This file (`src/CLAUDE.md`) also lives there.

- **`src/TS/`** — frozen modules, baked into the UF2 by `src/manifest.py`.
  Modifying these requires a rebuild + reflash.
- **`src/main.py`, `src/config.ini`, `src/assets/*.tap`** — copied to
  the Pico's flash filesystem (as `/main.py`, `/config.ini`,
  `/assets/*.tap`), NOT frozen. Edit-and-reboot, no rebuild needed.
- **`src/dev_tspico.py`** — optional development override. Deployed to
  the Pico as `/dev_tspico.py` (or `/dev_tspico.mpy`); if present,
  `main.py` will use it instead of the frozen `TS.tspico`. Useful for
  iterating on `tspico.py` without rebuilds. (The override trick only
  works for `tspico.py`; `src/dev_extcmd.py` does the same for
  `TS/extcmd.py`.) **Both copies are kept identical to their sources:**
  `src/test/dev_sync_hosttest.py` fails CI when they drift, so after editing
  `src/TS/tspico.py` or `src/TS/extcmd.py` run
  `cp src/TS/tspico.py src/dev_tspico.py` (and the same for extcmd).
- **`src/TS/tspico_io.py` is also built into the upgrade UF2**
  (`src/upgrade/manifest.py`, the web updater's ROM step), which freezes
  only `TS/__init__`, `tspico_io`, `sdcard` and `native`. A new module-level
  `TS` import in `tspico_io.py` must be added to that manifest **and** to the
  `modules-upgrade/TS/` copy line in both `build.yml` and `release.yml`.
  Otherwise the upgrade UF2 dies at boot with ImportError and the 2068 just
  beeps; that shipped from #82 until 2026-10-01. `src/test/upgrade_hosttest.py`
  checks it. Details: `docs/DEVELOPER_GUIDE.md`, "The upgrade UF2 is a second
  build of tspico_io.py".
- **`src/test/`** — bus-level test harnesses (this guide).
- **`docs/`** at the repo root — three layers: protocol design,
  firmware implementation, development history.

## Telemetry

Set `TLM_ENABLED = False` in `/main.py` (line near top, after
`import TS.tspico`) to silence all `TLM()` and `TLM_RESET()` calls.
Default is `True` for development. Diagnostic prints over USB serial
take ~5-10ms each — long enough to disrupt protocol timing if they
fire in a hot path.

## Talking to the Pico directly

When the user's TS-Pico is connected over USB (`ls /dev/cu.usbmodem*` on
macOS, `/dev/ttyACM*` on Linux), **do the Pico-side work yourself** with
[`tools/pico-serial.py`](../tools/pico-serial.py): flashing, watching
telemetry, reading files and state at the REPL. The user's job is the
2068 side -- typing the BASIC commands and telling you what the screen
shows. Relaying tracebacks and REPL output through Thonny copy/paste is
slow, lossy, and (see below) easy to get wrong.

```bash
python3 tools/pico-serial.py flash --branch my-branch   # CI UF2 -> Pico, no buttons
python3 tools/pico-serial.py watch --seconds 900        # passive telemetry capture
python3 tools/pico-serial.py break                      # Ctrl-C -> REPL
python3 tools/pico-serial.py run "import TS.tspico as T; print(T.files)"
python3 tools/pico-serial.py run --file snippet.py      # multi-line, paste mode
python3 tools/pico-serial.py softreset                  # Ctrl-D -> main.py again
```

- **`watch` is always safe.** It opens the port read-only and never
  writes, so it can't disturb the firmware; it reattaches if the Pico is
  unplugged. Run it in the background (it's a long-lived process) before
  the user types a command. `main.py` sets `TLM_ENABLED = True`, so every
  command prints its trace. Plugging USB into a Pico the 2068 is already
  powering does not reset it, and the 2068 boots fine with the Pico
  already powered from USB.
- **`flash` needs no buttons.** It drops to the REPL and calls
  `machine.bootloader()`, which reboots the RP2040 into BOOTSEL; then it
  copies the UF2 and waits for the reboot (~10 s). With `--branch` it
  takes the `tspico-firmware-uf2` artifact from the build.yml run for that
  branch's *current head commit*, and refuses one that hasn't finished or
  didn't pass. `--run N` refuses anything but a successful firmware build:
  a Pages deploy run on the same commit has an id just like it. (Before
  2026-10-01 `--branch main` could flash a months-old build, because
  `gh run list --branch` doesn't return the newest run first for `main`.) (By hand:
  hold BOOTSEL, tap the TS-Pico's reset button, release BOOTSEL.)
- **`break` stops the firmware** -- the 2068 has no TS-Pico until
  `softreset` or a power cycle. Only send it when the Pico is idle, never
  mid-SD access: a half-finished block transfer can wedge the card until
  power-cycle (`docs/DEVELOPER_GUIDE.md`, "If the SD card won't mount
  after a soft reboot"). Tell the user before you do it.
- **Only one program can own the port.** Every subcommand refuses to
  start while something else has it open. That's usually Thonny, and
  Thonny interrupts `main.py` when it connects. `KeyboardInterrupt`
  isn't an `Exception`, so `main.py` logs nothing and the 2068 just gets
  a long pause and Report J. Ask the user to disconnect Thonny.
- **"Long pause, then J, and no telemetry at all"** means the dispatcher
  never got a whole pre-header. Suspect Thonny, or a ROM/firmware
  mismatch, before the change under test. A 1.8b "sync" EXROM opens every
  command with `OUT (0Fh),03h`, and firmware without the SYNC-aware
  capture (`f5ff48e`, #51) blocks forever in the pre-header `MQ.get()`.
  `break` shows where it's stuck; test such a branch on a throwaway build
  that includes the SYNC fix.
- `/activity.log` only records `TSP.LOG_LEVEL` and above (ERROR by
  default); the full story is in the telemetry `watch` captures.

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
  `docs/PROTOCOL.md` §13. Even if it seems obvious in retrospect, it
  wasn't obvious before someone hit it.
- **Trust the empirical evidence over the spec.** The TPI spec PDF is
  Gustavo's design intent; the real ROM is what's running. When they
  disagree, follow the ROM (which means write a harness to confirm).
