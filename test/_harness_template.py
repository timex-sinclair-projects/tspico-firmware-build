"""Test harness starter template — copy this when writing a new bus-level test.

Why this exists:
  Every protocol observer needs the same ~100 lines of boilerplate setup
  before you can see a single byte cross the wire. Re-creating that from
  scratch each time risks subtle errors that produce confusing failures
  (forgetting to start ROM_SM means TS-2068 won't boot; forgetting to
  flush boot noise means RX has stale bytes; etc).

  Copy this file, rename it to `protocol_observer_<your-purpose>.py`,
  fill in the TODO sections, and you've got a working harness in minutes.

Usage:
  1. Copy:   cp test/_harness_template.py test/my_test.py
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
  - Tight RX-drain loop with microsecond timestamps
  - Ctrl-C handler that prints a clean dump

What you customize (the TODO sections):
  - PRE_RESPONSE: bytes to put in TX FIFO at startup before any Z80 activity
  - on_rx(): what to do when each Z80 OUT byte arrives (write back? log only?)
  - decode_and_dump(): how to format the captured log on Ctrl-C

Don't customize:
  - The hardware setup (unless your test specifically needs different pins)
  - The Y register initialization (V6 pattern requires READY at idle)
  - The boot-noise flush (Z80 emits stray bytes during its own boot)

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
# Capture buffers — pre-allocated to avoid GC pauses in the hot loop
# ============================================================================

CAP = 64                     # max events to capture (resize if needed)
rx_buf = bytearray(CAP)      # captured byte values
rx_a0  = bytearray(CAP)      # port indicator (0=$0E, 1=$0F)
rx_t   = [0] * CAP           # microsecond timestamps from session start

events = []                  # extra notes (TX-fill, phase transitions, etc.)


# ============================================================================
# TODO: define your protocol logic
# ============================================================================
# This is where the test-specific behavior goes. The simplest pattern is
# "log every Z80 OUT, do nothing else" — but you can build up to whole
# command exchanges from here.
#
# The capture loop below calls on_rx(idx, val, port, t) for every Z80 OUT.
# Use that to drive whatever response logic your test needs.

def on_rx(idx, val, port, t):
    """Called once for each Z80 OUT byte received in RX FIFO.

    Args:
        idx:  zero-based index of this byte (0 = first byte received)
        val:  the byte value (0..255)
        port: 0 if Z80 wrote to $0E, 1 if $0F
        t:    microseconds since the test started

    Add your response logic here. To send bytes back to the Z80,
    call MQ.put(byte). The PIO state machine handles the actual
    bus driving — you just write to TX FIFO.

    Common patterns:
      - rx_count == 9 → just captured the 10th byte of a pre-header,
        time to send response status: MQ.put(0x01)
      - rx_count == 11 → captured Z80's echo (block_type ack +
        computed CRC), time to send final status: MQ.put(0x01)
    """
    pass


# ============================================================================
# Tight capture loop — DON'T MODIFY (this is what made V6 work)
# ============================================================================

print("=" * 60)
print('READY. Power on TS-2068 (or trigger your test condition).')
print('Ctrl-C in Thonny when done — events will be dumped.')
print("=" * 60)

T0 = time.ticks_us()
rx_count = 0

# Local-name the hot-path methods to skip attribute lookups.
mq_rx_fifo = MQ.rx_fifo
mq_get     = MQ.get
ticks_us   = time.ticks_us
ticks_diff = time.ticks_diff

gc.collect()                 # prime GC before entering the hot loop

try:
    while True:
        if mq_rx_fifo() > 0:
            raw = mq_get()
            t = ticks_diff(ticks_us(), T0)
            if rx_count < CAP:
                val = raw & 0xFF
                a0 = (raw >> 8) & 1
                rx_buf[rx_count] = val
                rx_a0[rx_count]  = a0
                rx_t[rx_count]   = t
                # Hand off to the user's logic (TODO above).
                on_rx(rx_count, val, a0, t)
                rx_count += 1
except KeyboardInterrupt:
    pass


# ============================================================================
# TODO: dump format
# ============================================================================
# Customize this to format the captured log however your test needs.
# Default: one line per RX byte with timestamp, delta, hex value, ASCII
# hint, port, and (if you defined it) a label.

def decode_and_dump():
    print("")
    print("=" * 60)
    print("RX captured: %d byte(s)" % rx_count)
    print("=" * 60)
    if rx_count == 0:
        print("(no RX activity — Z80 didn't OUT anything)")
        return
    print("%4s  %8s  %8s  %5s  %3s  %4s  %s" % (
        "idx", "us", "delta", "val", "asc", "port", "note"))
    print("-" * 60)
    prev_t = 0
    for i in range(rx_count):
        t     = rx_t[i]
        delta = t - prev_t
        prev_t = t
        val   = rx_buf[i]
        port  = rx_a0[i]
        asc = "'%s'" % chr(val) if 0x20 <= val < 0x7F else "   "
        port_s = "$0F" if port else "$0E"
        note = ""    # ← add labels for known offsets if you like
        print("%4d  %8d  %8d  0x%02X  %3s  %4s  %s" % (
            i, t, delta, val, asc, port_s, note))
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
