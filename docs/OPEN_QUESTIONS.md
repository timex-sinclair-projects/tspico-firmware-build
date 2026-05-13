# Open questions for the team

Catch-all for low-traffic "we should think about this someday" items.
**For anything with a real decision path, open a GitHub issue instead** —
issues notify the team, support discussion threads, are linkable from
PRs, and have a real status field that doesn't drift.

This file is for items that aren't quite issue-worthy yet (vague hunches,
half-formed ideas, things waiting for more data before they can be
articulated as a concrete question).

Add new entries at the top. When something graduates to a GitHub issue,
remove it from here and link the issue.

---

## Open

### SEND_MSG2 produces a blank-screen-then-keypress-wait for short messages

**Symptom.** When `SEND_MSG2` is invoked with a relatively short message
(observed: 214 chars for `tpi:cd ..` directory refresh; 350 chars for
`tpi:help border`), the 2068's screen stays blank and the Pico's
`MQ.put()` blocks for several seconds. Only when the user presses a key
on the 2068 does the message finally render and `SEND_MSG2` complete
normally. Trace pattern:

```
SEND_MSG2 enter: msg_len=214 st=1 expand=True rom_ver=1.2
   ... ~5.9 second gap, screen blank, Pico blocked in MQ.put ...
SEND_MSG2 end_char written: 0x03    (after user keypress)
SEND_MSG2 exit: drain_loops=996 rx_drained=1 tx=0 rx=0
```

**Working theory (unverified).** TX FIFO underflow:

- PIO TX FIFO is 4 entries deep.
- SEND_MSG2 loads `0x86, 0x01, 0x0D, 0x0D` (4 bytes = full), then
  `MQ_READY()` lets the Z80 start reading.
- Z80 reads at ~47µs/byte; FIFO drops to empty in ~190µs.
- MicroPython's per-char loop body (ord + multiple branches + wrt +
  line-end logic) can be 30-80µs/iter; on a slow path, Python is
  slower than the Z80's read rate.
- Empty FIFO → PIO returns `0x00` to the Z80 → Z80 interprets as
  "end of page" (0x00 in the `0x86 PRINT_STRING_WITH_LOOP` protocol)
  → display whatever was rendered (nothing if underflow happened
  immediately) + wait for keypress.
- While waiting, Python continues to refill TX. By the time the user
  presses a key, the rest of the message is in TX. Z80 reads it,
  Pico's `wrt(end_char=0x03)` finally returns, function exits.

**Why it's not a recent regression.** `SEND_MSG2` in our reference
`TS/tspico.py` is byte-for-byte identical (modulo TLM and comments) to
the migrated `dev_tspico.py` version. If the timing-underflow theory is
correct, production has the same latent bug — possibly masked by users
not consciously noticing the keypress was a scroll prompt rather than
end-of-message.

**Not yet investigated.**
- Whether the bug reproduces on production firmware (the user's
  earlier "flawless" tests of `tpi:dir` were on production but didn't
  pay attention to whether a keypress was needed).
- Whether the bug reproduces for `SAVE_MSG2` invocations of all sizes
  or only short messages (a long message gives Pico time to build a
  buffer ahead before the loop overhead matters).
- Whether MicroPython 1.20.0's interpreter speed is actually slower
  than Z80's 47µs/byte read rate.

**Possible fixes (if confirmed).**
1. Pre-build the whole message into a bytearray (handling line wraps
   and scroll points during build), then dump in a tight `for b in
   buf: MQ.put(b)` loop. Eliminates per-char branch overhead from the
   bus-facing path.
2. Disable GC during the loop (`gc.disable() / gc.enable()`) to avoid
   stop-the-world pauses mid-message.
3. Move line-wrap logic to occur ONLY at column 32 (a rare event,
   maybe 1/32 of iterations), with the regular-char path stripped to
   the minimum (one `ord`, one comparison, one `wrt`).

**Next data to collect.** Run on dev_tspico with telemetry on:
- `SAVE "tpi:dir"` (short msg via SEND_MSG2)
- `SAVE "tpi:dir" CODE 2,0` (longer dir-listing msg)
- `SAVE "tpi:idir"`
- `SAVE "tpi:help"` (no arg — general help is the longest output)

If the keypress wait happens for ALL of them, the timing bug is in
SEND_MSG2 itself. If only short ones, the underflow theory is likely
correct. If only some, there's a specific message-content trigger.

---

## Graduated to GitHub issues

- **Should we implement true CRC verification on incoming messages?** —
  [#2](https://github.com/timex-sinclair-projects/tspico-firmware-build/issues/2)

---

## Resolved

*(none yet)*
