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

### Extension command (extcmd) protocol — postponed beyond this release

The `TPI:.XXX` user-extensible command mechanism has a structural
mismatch with the dual-port V6 pre-load chain. Symptoms during
picotest's `TPI:.RNDW` test:

  - `.RNDW` displays the word correctly (the response itself works).
  - The picotest BASIC's `IN 14` read-until-0 loop consumes the V6
    pre-load `0x01` that PROCESS_CMD writes for the next command.
  - Next `SAVE "tpi:..."` reads `0x00` from empty TX at its
    pre-header phase → Report J on the 2068.
  - Z80 aborts the command, never sends the body bytes.
  - PROCESS_CMD blocks forever in `MQ.get()` body-read.
  - Pico effectively halts (LED stops blinking, no commands
    processed).

Root cause is structural: the original extcmd design predates the
V6 pre-load chain, and "read until 0" patterns inherently consume
the pre-load byte.

**Decision: ship the dual-port release with extcmd marked as
under-development, then issue a new UF2 once the team ratifies a
new protocol contract.** Full design analysis, recommended response
shapes, and open questions for the team are in
[`docs/EXTCMD_PROTOCOL.md`](EXTCMD_PROTOCOL.md).

End users wanting to write extcmd handlers in the interim should
stick to status-only responses (`MQ.put(0x01)` and return) — those
work cleanly.

### `OUT 10,100` doesn't reach the Pico — ZX48 exit-by-byte unreachable

**Confirmed empirically** during ryan-dual-port-merge testing. After
`SAVE "tpi:zx48"`, the Pico enters ZX48_IO and listens for byte 76
(`'L'`), 83 (`'S'`), or 100 (decimal). The 2068 documentation says to
do `OUT 10,100` (send byte 100 to port `$0A`) to exit. User ran it
successfully on the 2068 side, but TLM trace showed nothing reached
the Pico's RX FIFO.

Root cause is hardware-side: port `$0A` (decimal 10) is NOT routed
through the /PICOSEL line on the TS-Pico board. Only `$0E` (data) and
`$0F` (status) trigger the PIO. So bytes sent to other ports go
nowhere from the Pico's perspective.

This means **the TS-Pico reset button is currently the only reliable
way to exit ZX48 mode.** The help text printed by the `ZX48` handler
has been updated to reflect this. The `elif a == 100: break` branch
in `ZX48_IO` is kept as defensive code (with `TSP.zx48 = False`
cleanup if ever reached), but is dead in practice.

**Questions worth asking Ryan:**
- Was `OUT 10,100` intended to work, or was it speculative code for
  a future hardware revision?
- Is there a small PIO/hardware change that could route additional
  ports (like `$0A`) through the Pico's bus handler so the by-byte
  exit could actually work?
- Should we add a UART-style "magic word on $0E" exit (e.g., a
  specific 4-byte sequence) as a software-only alternative to the
  reset button?

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
