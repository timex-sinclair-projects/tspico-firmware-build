# SD Card Robustness — Graceful Degradation & Remount

**Status: PROPOSAL — not started, no code written.** Tracker: [#43](https://github.com/timex-sinclair-projects/tspico-firmware-build/issues/43).

Today the TS-Pico treats "no SD card" as a fatal condition and stops.
It should treat it as a *state*: note it, keep running, fail the
commands that genuinely need the card with a clear error, and give the
user a way to try again.

This stands on its own merits — a user whose card wasn't seated
properly currently gets a blinking LED and no explanation. It is also a
**prerequisite** for the USB file server
([`USB_FILESERVER_PROPOSAL.md`](USB_FILESERVER_PROPOSAL.md)), where
running without an SD card is the normal case rather than an error.

---

## 1. What happens today

### Boot

Two separate paths brick the Pico into an infinite blink loop:

- `ACTIVATE_SD()` — mount failure logs, saves the log, then
  `while True: BLINK_ERROR()`
  ([tspico.py:776-783](../src/TS/tspico.py:776)).
- `TS2068_IO()` — a failed `os.chdir(TSP.cur_path)` does the same
  ([tspico.py:4295](../src/TS/tspico.py:4295)), which is what you get
  if the card mounts but has no `/TAP` directory.

From the user's side both look identical: LED blinking, 2068 gets
Report J on everything, no diagnosis.

### Mid-session

Worse, and this is the part that needs fixing first. `ACTIVATE_SD()` is
called from eight places, and the callers assume it succeeded. The
clearest example is `MOUNT_FILE`, where `totlen = os.stat(f_name)[6]`
([tspico.py:1188](../src/TS/tspico.py:1188)) sits outside any `try`.
Pull the card mid-session and that raises.

**Where the exception goes is the real problem.** `PROCESS_CMD` writes
the V6 pre-load at its tail:

```python
MQ.put(0x01)   # pre-load for the NEXT command's status read
MQ_READY()
```

but the handler dispatch above it is unguarded:

```python
if cmd_word in SA_funct:
    EXEC = SA_funct[cmd_word]
    EXEC(pre, cmd)          # ← raises, and we never reach the tail
```

The exception propagates to the main loop, which catches it and
`continue`s ([tspico.py:4600](../src/TS/tspico.py:4600)) — skipping the
tail entirely. **Any handler exception silently breaks the V6 pre-load
chain**, so the *next* command reads `0x00` from an empty TX FIFO and
reports J, per the symptom-to-cause mapping in
[`../src/CLAUDE.md`](../src/CLAUDE.md).

This is a live bug independent of everything else in this document —
filed as [#42](https://github.com/timex-sinclair-projects/tspico-firmware-build/issues/42) — and
it is the reason "return an error to the 2068" isn't currently
something a handler can reliably do.

---

## 2. Proposed behaviour

### 2a. Fix the pre-load chain first

Wrap the `SA_funct` / `EXT_SA_FUNCT` dispatch in `try/finally` so the
V6 tail always runs, and send a real error status to the 2068 on the
exception path rather than leaving the Z80 to infer one.

Nothing else in this document works reliably until this lands. It is
also small, self-contained, and testable with a handler that raises on
purpose.

### 2b. `SD_PRESENT` as a first-class state

Add `TSP.sd_present` (and surface it in `tpi:info`). At boot:

- mount fails → log it, set `sd_present = False`, **continue booting**;
- mount succeeds but `/TAP` is missing → fall back to `/sd`, then to
  `/`, logging each step; only give up on the card entirely if the
  mount itself failed.

The LED should distinguish "degraded" from "dead" — a distinct blink
pattern for "running without a card" versus the existing error blink.

### 2c. Commands fail cleanly

Every command that needs the card checks `sd_present` first and returns
a proper status byte with an explanatory message rather than raising.
Which status code to use needs deciding (§4 Q1) — the candidates from
[`GUSTAVO_PROTOCOL.md`](GUSTAVO_PROTOCOL.md) §8 are `0x02` (Report R),
`0x04` (Report Q) or `0x08` (Report A), none of which means "device not
ready". The message text is where the real information lives.

Commands that do **not** need the card must keep working: `tpi:info`,
`tpi:help` (once help text can come from flash or the host),
`tpi:verbose`, `tpi:loglevel`, `tpi:boot`, `tpi:dock`, `tpi:zx48`, and
`LOAD ""` against an already-mounted `/TMP/temp.tap`.

### 2d. `tpi:remount`

Retry the mount on demand. On success it must **rebuild all the state
that assumes the old card**:

| State | Why it's stale | Action |
|---|---|---|
| `TSP.cur_path` | may not exist on the new card | validate → `/sd/TAP` → `/sd` → `/` |
| `TSP.f_name` | may point at a file that isn't there | validate; unmount if gone |
| `files` / `files_upper` | `DIR_FILES()` cache | rebuild |
| `alldirs` | `GET_DIRS()` cache | rebuild |
| `TSP.offset_tbl`, `.offset`, `.tap_idx` | tied to the old mount | reset unless `f_name` revalidated |
| `TSP.append` | target file may be gone | clear unless revalidated |

Hot-swapping to a *different* card is the interesting case and the one
most likely to be exercised in practice.

---

## 3. The dirty-`/TMP` question

David raised: what happens on remount if `/TMP/temp.tap` is dirty —
the user appended saves but never closed?

**Worth stating clearly: this state does not exist today, and we would
be choosing to create it.** With append ON, `SAVE_TS` writes
`mode="ab"` straight to the SD file and the main loop re-mounts,
refreshing `/TMP/temp.tap` from the card
([tspico_io.py:1210-1257](../src/TS/tspico_io.py:1210),
[tspico.py:4494](../src/TS/tspico.py:4494)). The card is always
authoritative; `/TMP/temp.tap` is never more current than it.

The dirty state only appears if we decide that a **no-SD `SAVE` stages
into `/TMP`** instead of failing. So the real decision is upstream of
remount semantics:

| Policy | Dirty state? | Trade-off |
|---|---|---|
| **A** — no-SD SAVE fails | never | Simplest. A user who just typed in a program loses it. Bad. |
| **B** — stage to `/TMP`, mark dirty | yes | Best UX; most states to reason about. |
| **C** — save to the host if a fileserver is connected | no | In the USB world "no SD" often isn't a dead end at all. |

**Recommendation: B, with C preferred when USB is available.**

If we take B, the rule falls out of existing behaviour: `tpi:close`
already deletes `/TMP/temp.tap` ([tspico.py:3653](../src/TS/tspico.py:3653)),
so it *is* the discard path. Therefore:

> A dirty staged file must be flushed to the card or explicitly
> discarded (`tpi:close`) before a remount is allowed to replace it.

`tpi:remount` with a dirty `/TMP` should refuse and say so, and a
`tpi:flush` (or `tpi:remount` taking a "flush first" argument) does the
write-back. Silently discarding the user's work is not acceptable;
silently overwriting a file on the newly-inserted card is worse.

---

## 4. Open questions

**Q1. Which status code for "no SD card"?** None of the existing codes
mean "device not ready" (`GUSTAVO_PROTOCOL.md` §8). Do we pick the
least-wrong one and lean on the message text, or is this an argument
for the richer status vocabulary in
[#18](https://github.com/timex-sinclair-projects/tspico-firmware-build/issues/18)?

**Q2. Command naming.** `tpi:remount`? Should it pair with the USB
side's `tpi:reconnect`, or should there be one `tpi:mount sd|usb`
verb that covers both?

**Q3. Dirty-save policy** — A, B or C from §3. This is the decision
that shapes everything else here.

**Q4. Auto-retry?** Should the Pico periodically re-probe for a card
in the idle branch of the main loop, or only on explicit
`tpi:remount`? Auto-retry is friendlier but means the card can appear
underneath a running session, which is another state transition to get
right.

**Q5. Should the degraded state be visible on the 2068 at boot?**
The Pico has no way to push a message to the 2068 unprompted — the
protocol is entirely Z80-initiated. So the first the user knows may be
an error from their first command. Is a distinct LED blink pattern
enough?

---

## 5. Sequencing

1. **`try/finally` on the dispatch** (§2a) — small, independent, fixes
   a live bug. Do this regardless of what else gets scheduled.
2. **`sd_present` + no-brick boot** (§2b) — makes the Pico survivable
   without a card.
3. **Per-command guards** (§2c) — the bulk of the work; mechanical.
4. **`tpi:remount` + cache rebuild** (§2d) — the state-heavy part.
5. **Dirty-save policy** (§3) — only once Q3 is decided.

Steps 1–2 are the prerequisite for
[`USB_FILESERVER_PROPOSAL.md`](USB_FILESERVER_PROPOSAL.md) Tier 1.
