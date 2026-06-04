"""Test harness starter template — copy this when writing a new bus-level test.

Why this exists:
  Every protocol observer needs the same ~100 lines of boilerplate setup
  before you can see a single byte cross the wire. Re-creating that from
  scratch each time risks subtle errors that produce confusing failures
  (forgetting to start ROM_SM means TS-2068 won't boot; forgetting to
  flush boot noise means RX has stale bytes; etc).

  Copy this file, rename it to `protocol_observer_<your-purpose>.py`,
  fill in the TODO sections, and you've got a working harness in minutes.

============================================================================
CRITICAL: TWO-PHASE CAPTURE PATTERN — read this before changing the loop.
============================================================================

The PIO RX FIFO is only 4 entries deep. The Z80 OUTs bytes at ~30us each.
Any Python work between successive `MQ.get()` calls — conditionals, math,
callbacks, even attribute lookups — risks letting the FIFO overflow.
PIO `push noblock` then silently drops the overflowing byte. The Z80 is
unaware and keeps going. You see a truncated capture and chase a ghost.

This bit us in `protocol_observer_crc.py` when we did per-byte CRC math
inside a callback. The harness saw 9 of 10 pre-header bytes; the
"missing" 10th byte wasn't missing on the wire — it was a FIFO overflow
caused by per-byte Python work. Production's `TS2068_IO()` (lines
4060-4061 in `TS/tspico.py`) does NO per-byte work — it's just:

    for i in r1:
        pre[i] = MQ.get()      # tight blocking read of N bytes

That's the pattern. Match it.

The fix is to split every harness into two phases:

  PHASE 1 (CAPTURE) — tight, no per-byte work:
      for i in range(N):
          buf[i] = MQ.get()    # blocking; matches production exactly
      # That's it. No conditionals, no math, no callbacks.

  PHASE 2 (DECISION) — runs AFTER the burst is over:
      Compute CRC, format response, MQ.put() bytes, log analysis, etc.
      You have a 2.8ms WAIT EXECUTION budget per spec — ample time
      for any reasonable Python work. Don't steal from the capture
      budget to do work that belongs in the response budget.

If the protocol exchange is multi-phase (request → response → request
→ response), wrap PHASE 1 + PHASE 2 in an outer loop so each iteration
handles exactly one burst.

If you're writing a pure observer (no responses), just drain RX FIFO
into the buffer with NOTHING else in the loop body. Decision work
(decoding, dumping) happens after Ctrl-C.

============================================================================

Usage:
  1. Copy:   cp test/_harness_template.py test/protocol_observer_<purpose>.py
  2. Edit:   replace the TODO sections with your test logic
  3. Run:    copy your file to the Pico via Thonny, exec it
  4. Test:   power on TS-2068, do whatever triggers the protocol exchange
  5. Stop:   Ctrl-C in Thonny — your dump prints

Boilerplate this template handles:
  - CPU clock at 270 MHz (production setting)
  - All board pin setup (matches main.py production path exactly)
  - ROM_SM / BANK_SM started (TS-2068 can boot via EXROM)
  - MQ (TS_IO_DUAL) started, Y = 0xFFFFFFFF (READY)
  - Boot-noise flush from RX FIFO (~300ms)
  - Pre-allocated capture buffers (no GC pauses in hot path)
  - Two-phase capture: tight burst-read + separate decision step
  - Ctrl-C handler that prints a clean dump

What you customize (the TODO sections):
  - PRE_RESPONSE: bytes to put in TX FIFO at startup before any Z80 activity
  - BURST_LEN: how many bytes per Z80 burst (10 for the standard pre-header)
  - decide_and_respond(): runs ONCE PER BURST, AFTER the burst completes
  - decode_and_dump(): how to format the captured log on Ctrl-C

Don't customize:
  - The hardware setup (unless your test specifically needs different pins)
  - The Y register initialization (V6 pattern requires READY at idle)
  - The boot-noise flush (Z80 emits stray bytes during its own boot)
  - The shape of the capture loop (the two-phase pattern is non-negotiable —
    if you put work inside it, you will lose bytes)

See docs/DUAL_PORT_DEVELOPMENT.md §5 for examples of harnesses built on
top of this pattern, and what each one taught us.
"""

import os
import time
import gc
from rp2 import StateMachine, asm_pio, PIO
from machine import Pin, freq

# ============================================================================
# Hardware setup (DON'T MODIFY — these settings match production main.py)
# ============================================================================

freq(270_000_000)

from TS.tspico_io import TS_IO_DUAL, set_ctrl, sel_bank


print("=" * 60)
print("HARNESS — starter template (rename me!)")
print("=" * 60)

# Board pin configuration. These names and roles match what
# main.py + TS/tspico.py do in the production firmware.
U6_EN   = Pin(12, Pin.OUT, Pin.PULL_UP)   # U6 buffer enable (sideset by PIO)
WAIT    = Pin(14, Pin.OUT, Pin.PULL_DOWN) # /PICOSEL wait gpio (input to PIO)
U10_ENA = Pin(19, Pin.OUT, Pin.PULL_UP)   # flash chip enable
U13_ENA = Pin(20, Pin.OUT, Pin.PULL_UP)   # flash chip enable
BE      = Pin(21, Pin.OUT, Pin.PULL_UP)   # /BE — driven by ROM_SM
ROSCS   = Pin(26, Pin.IN,  Pin.PULL_DOWN) # ROM_SM jmp_pin (must be input!)
U10_WE  = Pin(27, Pin.OUT, Pin.PULL_UP)   # flash write-enable
for p in (U6_EN, WAIT, U10_ENA, U13_ENA, BE, U10_WE):
    p.value(1)


# Start ROM_SM / BANK_SM IMMEDIATELY — without these, the TS-2068 cannot
# read its boot ROM (which lives in the TS-Pico's external flash) and
# therefore cannot boot at all. /BE has to be actively routed by the
# set_ctrl PIO program from before the moment the Z80 starts looking for
# instructions.
rom_sm = StateMachine(4, set_ctrl, freq=150_000_000,
                      in_base=Pin(0, Pin.IN), jmp_pin=Pin(26),
                      set_base=Pin(21, Pin.OUT),
                      out_base=Pin(19, Pin.OUT))
rom_sm.active(1)
bank_sm = StateMachine(5, sel_bank, freq=150_000_000,
                       jmp_pin=Pin(26),
                       out_base=Pin(15, Pin.OUT))
bank_sm.active(1)
rom_sm.put(0x0A)        # both DCK and ROM mapped to flash
bank_sm.put(0x01)       # DCK_SLOT=0 + ROM_SLOT=1 (TS-Pico ROM)
print("[SETUP] ROM_SM/BANK_SM running (TS-2068 can boot)")


# Start the main I/O state machine. TS_IO_DUAL is the dual-port PIO
# program in TS/tspico_io.py — handles both $0E (data) and $0F (status).
MQ = StateMachine(0, TS_IO_DUAL, freq=30_000_000,
                  out_base=Pin(2, Pin.OUT),
                  in_base=Pin(2, Pin.IN),
                  jmp_pin=Pin(11),
                  sideset_base=Pin(12, Pin.OUT))
MQ.active(1)

# Y = 0xFFFFFFFF means port $0F always returns 0xFF (D6=1=ready). The
# Z80's WF_NPH polling loop will see "ready" instantly. This is the
# "ready forever" pattern — see docs/PROTOCOL.md §3.
MQ.exec("mov(y, invert(null))")
print("[SETUP] MQ active, Y=READY")


# Drain any stray bytes the Z80 emitted during its own boot or while we
# were setting things up. Failure to do this means your first "real"
# RX events are mixed in with garbage.
n = 0
last = time.ticks_ms()
while time.ticks_diff(time.ticks_ms(), last) < 300:
    if MQ.rx_fifo() > 0:
        MQ.get()
        n += 1
        last = time.ticks_ms()
print("[SETUP] flushed %d boot byte(s) from RX FIFO" % n)


# ============================================================================
# TODO: pre-response bytes
# ============================================================================
# If your test needs Pico to respond to the Z80's first $0E read, put
# the response bytes here. Common patterns:
#   - PRE_RESPONSE = (0x01,)       # status OK pre-loaded for next command
#   - PRE_RESPONSE = ()            # silent observer — no response
#   - PRE_RESPONSE = (0x01, 0xFF)  # status + start of header
#
# These are written to TX FIFO once at startup, before any Z80 activity.
PRE_RESPONSE = (0x01,)

for b in PRE_RESPONSE:
    MQ.put(b)
print("[SETUP] TX FIFO pre-loaded with %d byte(s): %s" % (
    len(PRE_RESPONSE), [hex(b) for b in PRE_RESPONSE]))


# ============================================================================
# TODO: burst length
# ============================================================================
# How many bytes the Z80 sends in one burst before pausing for our
# response. The standard TS-Pico pre-header is 10 bytes (per Gustavo's
# spec; see docs/PROTOCOL.md). For most harnesses you want 10 here.
#
# If the protocol you're observing has multiple burst sizes, see the
# "multi-phase" comment under the capture loop below.
BURST_LEN = 10


# ============================================================================
# Capture buffers — pre-allocated to avoid GC pauses in the hot loop
# ============================================================================

CAP = 256                    # max bytes captured (resize if needed)
rx_buf = bytearray(CAP)      # captured byte values
rx_t   = [0] * CAP           # microsecond timestamp at end of each burst

events = []                  # extra notes (phase boundaries, errors, etc.)


# ============================================================================
# TODO: define your decision logic
# ============================================================================
# This runs ONCE PER BURST, after BURST_LEN bytes have been captured. Put
# all CRC math, response logic, and analysis HERE — never inside the
# capture loop.
#
# Args:
#   buf:        the full capture buffer (bytearray, length CAP)
#   start:      index of the first byte of the just-captured burst
#   length:     number of bytes captured in this burst (== BURST_LEN)
#   burst_num:  zero-based burst index (0 = first burst, etc.)
#
# Common patterns:
#   - Compute CRC over buf[start:start+length-1] and compare to
#     buf[start+length-1]; respond with status via MQ.put(...).
#   - Inspect buf[start] (block_type) to decide which response to send.
#   - Append a label to `events` recording what this burst was.
#
# Remember: you have a 2.8ms WAIT EXECUTION budget here per spec. That's
# ample for normal Python work, but DON'T do file I/O or sleep() inside
# this function — those can take longer than the budget.

def decide_and_respond(buf, start, length, burst_num):
    """Process one captured burst. Default: do nothing (pure observer)."""
    pass


# ============================================================================
# Two-phase capture loop — DON'T MODIFY this structure.
# ============================================================================
#
# The structure here is non-negotiable: PHASE 1 is a tight blocking read,
# PHASE 2 is everything else. If you find yourself wanting to do work
# inside PHASE 1, you almost certainly want to do it in decide_and_respond
# instead. See the docstring at the top of this file for why.
#
# Multi-phase note: if your protocol has DIFFERENT burst sizes for
# successive bursts (e.g., 10-byte pre-header → 26-byte header block →
# variable-length data), you'll need to make BURST_LEN dynamic. The
# simplest way is to set it inside decide_and_respond based on what you
# just received, and read it back here as `current_burst_len`. Keep the
# tight-read invariant intact: nothing in the for-loop body but the get.

print("=" * 60)
print('READY. Power on TS-2068 (or trigger your test condition).')
print('Ctrl-C in Thonny when done — events will be dumped.')
print("=" * 60)

T0 = time.ticks_us()
total_bytes = 0
burst_num = 0

# Local-name the hot-path methods to skip attribute lookups.
mq_rx_fifo = MQ.rx_fifo
mq_get     = MQ.get
ticks_us   = time.ticks_us
ticks_diff = time.ticks_diff

gc.collect()                 # prime GC before entering the hot loop

try:
    while True:
        # Outer poll: wait for the Z80 to start a burst.
        if mq_rx_fifo() == 0:
            continue

        # ====================================================================
        # PHASE 1 — tight blocking burst read. NOTHING ELSE IN HERE.
        # Matches production TS2068_IO() lines 4060-4061 verbatim.
        # ====================================================================
        if total_bytes + BURST_LEN > CAP:
            # Buffer would overflow — stop capturing.
            events.append(("CAP_HIT", "buffer full at burst %d" % burst_num))
            break
        start = total_bytes
        for i in range(BURST_LEN):
            rx_buf[start + i] = mq_get()        # blocking
        # ONE timestamp at end of burst (cheap; not per-byte).
        t = ticks_diff(ticks_us(), T0)
        for i in range(BURST_LEN):
            rx_t[start + i] = t                 # same timestamp per burst
        total_bytes += BURST_LEN

        # ====================================================================
        # PHASE 2 — decision & response. Do all your work here.
        # ====================================================================
        decide_and_respond(rx_buf, start, BURST_LEN, burst_num)
        burst_num += 1

except KeyboardInterrupt:
    pass


# ============================================================================
# TODO: dump format
# ============================================================================
# Customize this to format the captured log however your test needs.
# Default: one line per RX byte with timestamp, hex value, ASCII hint,
# and the burst it belongs to.

def decode_and_dump():
    print("")
    print("=" * 60)
    print("RX captured: %d byte(s) across %d burst(s)" % (
        total_bytes, burst_num))
    print("=" * 60)
    if total_bytes == 0:
        print("(no RX activity — Z80 didn't OUT anything)")
        return
    print("%4s  %5s  %8s  %5s  %3s  %s" % (
        "idx", "burst", "us", "val", "asc", "note"))
    print("-" * 60)
    for i in range(total_bytes):
        t   = rx_t[i]
        val = rx_buf[i]
        asc = "'%s'" % chr(val) if 0x20 <= val < 0x7F else "   "
        b   = i // BURST_LEN
        note = ""    # ← add labels for known offsets if you like
        print("%4d  %5d  %8d  0x%02X  %3s  %s" % (
            i, b, t, val, asc, note))
    print("=" * 60)
    if events:
        print("EVENTS:")
        for ev in events:
            print("  " + repr(ev))
        print("=" * 60)


decode_and_dump()

# Don't deactivate ROM_SM/BANK_SM on exit — the TS-2068 needs them to
# keep accessing its ROM. Only the MQ state machine can be turned off.
MQ.active(0)
print("MQ deactivated. ROM_SM/BANK_SM left running.")
