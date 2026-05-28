# TS-Pico Communication Protocol — v2 Design Proposal

**Status:** Discussion draft for the team. Not scheduled. The current
(v1 / dual-port) protocol is what we're shipping to users now; this
document captures a more robust design for a future revision.

**Ownership of the moving parts:**
- **Gustavo** — Z80-side ROM code (the EXROM/HOME ROM that drives the
  protocol from the 2068).
- **Ricardo** — Pico-side lead (MicroPython firmware + PIO).
- Cross-cutting changes (the status-bit definitions, framing format)
  need both, plus a shared vocabulary in the protocol docs.

---

## 1. Why revisit the protocol

The current dual-port protocol works, and we're shipping it. But a run
of hardware testing surfaced a cluster of weaknesses that all trace
back to the same few design gaps. Every item below is something we hit
in practice, not a hypothetical:

1. **Empty-FIFO is indistinguishable from a real `0x00`.** When the Z80
   reads the data port (`$0E`) and the Pico's TX FIFO is empty, the PIO
   drives `0x00` onto the bus. The Z80 can't tell "the Pico sent a real
   zero byte" from "the Pico had nothing ready yet." Because `0x00`
   reaching the Z80 at the wrong moment is interpreted as **Report J
   (Invalid I/O Device)**, this single ambiguity is the root of most of
   our intermittent J errors and the SEND_MSG2 timing races.

2. **Writes from the Z80 can be silently dropped.** When the Z80 writes
   to the data port, the byte lands in the Pico's RX FIFO via a
   non-blocking push. If that FIFO is full (it's only 4 bytes deep), the
   byte is **discarded with no indication to either side.** A Z80 that
   writes faster than MicroPython drains loses data.

3. **One "ready" bit is overloaded.** Status-port (`$0F`) bit 6 currently
   means "Pico is ready," "you may continue," and "ack received" all at
   once. The recently-diagnosed `0x86 PRINT_STRING_LOOP` bug (the Z80's
   per-page continue-ack getting conflated with the always-asserted
   ready level) is purely a symptom of this overload.

4. **No framing, no resync.** If the two sides ever disagree about where
   they are in a byte stream — a dropped byte, a miscount — there is no
   marker to recover to. The exchange just hangs. We band-aided the worst
   case with a 1-second body-read timeout on the Pico, but there is no
   systematic recovery.

5. **CRC is specified but not verified.** The protocol carries an XOR
   checksum, but the firmware does not currently validate it.

---

## 2. Guiding principle

> **The PIO state machine should be a dumb, fast, _honest_ byte-mover.
> All framing, retry, and recovery logic belongs in software — the
> MicroPython firmware and the Z80 ROM. The PIO's only added
> responsibility should be exposing _accurate, real-time_ FIFO state.**

This split matters because FIFO occupancy changes faster than
MicroPython can poll. A status bit that means "TX FIFO has a byte right
now" has to be produced by the PIO (which can branch on FIFO
conditions), not by MicroPython setting a register it can't keep
current between back-to-back Z80 reads.

---

## 3. Tier 1 — Richer status bits (the highest-leverage change)

This is where Gustavo's proposal (using additional bits on port `$0F`
for flow control) fits, and it directly removes failure modes #1, #2,
and #3.

Proposed `$0F` status byte layout (Pico → Z80, read via `IN $0F`):

| Bit | Name | Driven by | Meaning |
|-----|------|-----------|---------|
| 7 | `TX_VALID` | **PIO (real-time)** | TX FIFO is non-empty: the byte the Z80 would read from `$0E` is real data, not a fallback `0x00`. **The Z80 must check this before trusting an `IN $0E`.** Removes failure #1. |
| 6 | `READY` | MicroPython (Y reg) | Pico is in a state to communicate. Existing semantic, retained for compatibility. |
| 5 | `RX_SPACE` | **PIO (real-time)** | RX FIFO has room. **The Z80 must check this before `OUT $0E`.** Removes failure #2 (gives the Z80 real backpressure). |
| 4 | `ACK` | MicroPython | The per-step continue/acknowledge signal — distinct from `READY`, so the two stop being conflated. Removes failure #3 (the `0x86` bug). |

New Z80-side discipline, in one sentence: **poll `$0F`; only `IN $0E`
when `TX_VALID` is set; only `OUT $0E` when `RX_SPACE` is set.** That
alone converts the byte channel from "mostly works, races sometimes"
into "reliable," because it eliminates the empty-FIFO guesswork and the
silent write drops at their source.

### Addressing "the PIO is already tight"

The data-path state machine is near its instruction budget, so adding
real-time status composition to the `$0F`-read path may not fit. Two
ways around it:

- **Preferred: a second, dedicated status state machine.** The RP2040
  has 8 PIO state machines across two blocks. A tiny status SM can
  continuously compute `TX_VALID` / `RX_SPACE` from the shared FIFOs and
  drive `$0F`, leaving the data SM lean on `$0E`. This decouples the
  instruction budget completely.
- Alternatively, fold the FIFO tests into the existing `$0F` path if a
  few instructions can be reclaimed elsewhere.

The real-time bits (`TX_VALID`, `RX_SPACE`) **must** be PIO-driven. The
slower-moving bits (`READY`, `ACK`) can stay MicroPython-driven via the
Y register exactly as today.

---

## 4. Tier 2 — A framing layer

Even a perfect byte channel can desync if a byte is miscounted. Give
both sides a frame structure they agree on:

```
[SYNC] [TYPE] [LEN_lo] [LEN_hi] [payload ...] [CRC]
```

- **SYNC** — a recognizable lead byte (or short pattern). The receiver
  runs a small state machine:

  ```
  IDLE → hunt-for-SYNC → read-header → read-payload → check-CRC
       → deliver (good)  or  NAK (bad) → back to hunt-for-SYNC
  ```

  "hunt-for-SYNC" is the universal recovery point: any error drops the
  receiver back to it.

- **LEN** — a length-prefixed payload means the receiver knows _exactly_
  how many bytes to expect. This eliminates the "read until `0x00`"
  pattern, which is fragile and is also what currently breaks the
  user-extensible command mechanism (extcmd). Incomplete frames become
  detectable: if fewer than `LEN` bytes arrive before the per-frame
  timeout, the frame is incomplete → NAK → resync.

- **CRC** — actually validate it. On mismatch: NAK, the sender
  retransmits, both sides resync.

Because a SYNC value could appear inside payload data, either reserve
the SYNC byte and byte-stuff/escape it in the payload, or (simpler and
cheaper on the Z80) rely on `LEN`: once locked onto a valid header,
trust `LEN` and do not re-hunt for SYNC until the frame completes or
times out.

---

## 5. Tier 3 — Recovery and liveness

- **Per-frame timeout on both sides.** Generalize the body-read timeout
  the Pico already has. A stalled exchange resolves in bounded time
  rather than hanging until reset.
- **A universal ABORT / RESYNC signal.** One reserved status-bit state
  (or a short reserved byte sequence) meaning "drop whatever you're
  doing and return to IDLE." Either side may assert it. This is the
  explicit out-of-sync escape hatch; today the only recovery is a
  timeout or the physical reset button.
- **Protocol-version handshake at session start.** The Pico reports a
  protocol version in its first status exchange and the ROM adapts.
  Because the ROM and the Pico firmware ship separately, this lets
  mismatched versions coexist and degrade gracefully instead of
  failing mysteriously.
- **Optional heartbeat / keepalive** so a wedged side is _detected_
  rather than silently dead. (We have repeatedly observed the
  "LED stopped blinking, Pico unresponsive" symptom with no signal to
  the Z80.)

---

## 6. Recommended sequencing

1. **Software-only hardening first (no ROM or PIO change — shippable on
   the current hardware):** enforce CRC validation, length-prefix Pico
   responses, add per-frame timeouts, and give the Pico's command
   processor a receiver resync state. This removes a large fraction of
   the fragility without touching Gustavo's ROM or the PIO.

2. **Tier-1 status bits (coordinate Gustavo + Ricardo):** `TX_VALID` and
   `RX_SPACE` are the highest-leverage hardware-level changes — they
   remove the empty-FIFO ambiguity and the silent RX drops at the root.
   Splitting `READY` and `ACK` (bits 6 and 4) fixes the `0x86` class of
   bug. Pitch the **dedicated status state machine** as the answer to
   the PIO-budget concern.

3. **Tier-2 framing** as the umbrella that turns incomplete-frame and
   out-of-sync handling from ad-hoc into systematic.

---

## 7. On Gustavo's bits 4 / 5 / 7 proposal

Gustavo proposed using bits 4, 5, and 7 of port `$0F` for flow control —
one bit a signal to the Z80, one a signal reflecting the Z80, and a
third. That instinct maps cleanly onto the Tier-1 table above:

- **Bit 7 → `TX_VALID`** — the "data available to the Z80" signal.
- **Bit 5 → `RX_SPACE`** — gates writes _from_ the Z80 (backpressure).
- **Bit 4 → `ACK`** — the dedicated acknowledge that un-overloads bit 6.

The one design note to carry into that conversation: **the real-time
FIFO-state bits (`TX_VALID`, `RX_SPACE`) should be PIO-driven, and if
the data state machine is too tight to also compose status, a dedicated
status state machine solves the budget problem cleanly.**

---

## 8. Related work

- CRC verification — already tracked as a separate item.
- Extcmd protocol contract — the "read until `0x00`" fragility this
  design removes is the same one that currently breaks extcmd.
- `0x86` bit-6 acknowledge bug — the poster child for the overloaded
  `READY` bit.
- Naming the ROM function codes / control bytes — the v2 vocabulary
  (`TX_VALID`, `SYNC`, `LEN`, etc.) should be defined once and shared
  across Gustavo's spec, our protocol docs, and the firmware constants.

See the GitHub issue tracker for live status on each.
