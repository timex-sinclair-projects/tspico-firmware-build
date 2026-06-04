"""Silent observer — no TX response, just log every Z80 OUT.

Goal: see the PURE pre-header OUT sequence with no Pico interference.

Setup:
  - ROM_SM, BANK_SM running so TS-2068 boots from EXROM
  - MQ active, Y = 0xFFFFFFFF so port $0F always returns 0xFF (D6=1=ready)
    → TS-2068's pre-LOAD WF_NPH probe succeeds instantly
  - TX FIFO LEFT EMPTY — when Z80 reads $0E for status, it gets stale OSR
    (0x00) which triggers Report J (status code 0). But by then Z80 has
    already OUT-ted the full pre-header per the sequential spec.

What we'll see in the log:
  - Every Z80 OUT to $0E or $0F (RX events with port indicator)
  - Timestamps in microseconds from session start
  - Whatever sequence Z80 ROM actually emits — no interleaving with our
    responses, no detection-order ambiguity

Use:
  1. Run this script via Thonny
  2. Power on TS-2068 (boots via EXROM)
  3. Type LOAD "" on TS-2068 (will error out, that's expected)
  4. Ctrl-C in Thonny → see the byte log
"""

import time
from rp2 import StateMachine, asm_pio, PIO
from machine import Pin, freq

freq(270_000_000)

from TS.tspico_io import TS_IO_DUAL, set_ctrl, sel_bank


# ============================================================================
# Hardware setup
# ============================================================================

print("=" * 60)
print("SILENT PROTOCOL OBSERVER — log Z80 OUTs only, no response")
print("=" * 60)

U6_EN   = Pin(12, Pin.OUT, Pin.PULL_UP)
WAIT    = Pin(14, Pin.OUT, Pin.PULL_DOWN)
U10_ENA = Pin(19, Pin.OUT, Pin.PULL_UP)
U13_ENA = Pin(20, Pin.OUT, Pin.PULL_UP)
BE      = Pin(21, Pin.OUT, Pin.PULL_UP)
ROSCS   = Pin(26, Pin.IN,  Pin.PULL_DOWN)
U10_WE  = Pin(27, Pin.OUT, Pin.PULL_UP)
for p in (U6_EN, WAIT, U10_ENA, U13_ENA, BE, U10_WE):
    p.value(1)

rom_sm = StateMachine(4, set_ctrl, freq=150_000_000,
                      in_base=Pin(0, Pin.IN), jmp_pin=Pin(26),
                      set_base=Pin(21, Pin.OUT),
                      out_base=Pin(19, Pin.OUT))
rom_sm.active(1)
bank_sm = StateMachine(5, sel_bank, freq=150_000_000,
                       jmp_pin=Pin(26),
                       out_base=Pin(15, Pin.OUT))
bank_sm.active(1)
rom_sm.put(0x0A)
bank_sm.put(0x01)
print("[SETUP] ROM_SM=0x0A bank_sm=0x01")

MQ = StateMachine(0, TS_IO_DUAL, freq=30_000_000,
                  out_base=Pin(2, Pin.OUT),
                  in_base=Pin(2, Pin.IN),
                  jmp_pin=Pin(11),
                  sideset_base=Pin(12, Pin.OUT))
MQ.active(1)
MQ.exec("mov(y, invert(null))")    # Y = 0xFFFFFFFF, $0F always ready
print("[SETUP] MQ active, Y=READY, TX FIFO EMPTY (no pre-load)")

# Drain boot noise (timestamps reset after this)
n = 0
last = time.ticks_ms()
while time.ticks_diff(time.ticks_ms(), last) < 300:
    if MQ.rx_fifo() > 0:
        MQ.get()
        n += 1
        last = time.ticks_ms()
print("[SETUP] flushed %d boot byte(s)" % n)


# ============================================================================
# Pure observer — RX-only logging
# ============================================================================

events = []
T0 = time.ticks_us()

print("=" * 60)
print('READY. Power on TS-2068 if not already, then type LOAD "".')
print("Z80 will time out / error out — that is expected.")
print("Ctrl-C in Thonny when done to see the byte log.")
print("=" * 60)

try:
    while True:
        if MQ.rx_fifo() > 0:
            raw = MQ.get()
            data = raw & 0xFF
            a0 = (raw >> 8) & 1
            t = time.ticks_diff(time.ticks_us(), T0)
            events.append((t, data, a0))

except KeyboardInterrupt:
    pass


# ============================================================================
# Dump the event log with delta times
# ============================================================================

print("")
print("=" * 60)
print("Z80 OUT LOG (%d byte(s))" % len(events))
print("=" * 60)

if not events:
    print("(no OUTs captured — Z80 never wrote to $0E or $0F)")
else:
    print("%4s  %8s  %8s  %5s  %3s  %4s  %s" % (
        "idx", "us", "delta", "val", "asc", "port", "label"))
    print("-" * 60)

    # Common pre-header field labels for first 10 bytes
    labels = [
        "BLOCK_TYPE",
        "TADDR",
        "BANK",
        "SESS_LO",
        "SESS_HI",
        "MADDR_LO",
        "MADDR_HI",
        "BLEN_LO",
        "BLEN_HI",
        "CRC_TIMEX",
    ]

    prev_t = 0
    for i, (t, data, a0) in enumerate(events):
        delta = t - prev_t
        prev_t = t
        port = "$0F" if a0 else "$0E"
        label = labels[i] if i < len(labels) else "(post-CRC)"
        # ASCII hint for printable bytes
        if 0x20 <= data < 0x7F:
            ascii_hint = "'%s'" % chr(data)
        else:
            ascii_hint = "   "
        print("%4d  %8d  %8d  0x%02X  %3s  %4s  %s" % (
            i, t, delta, data, ascii_hint, port, label))

print("=" * 60)
print("Total OUTs:  %d" % len(events))
print("To $0E:      %d" % sum(1 for e in events if e[2] == 0))
print("To $0F:      %d" % sum(1 for e in events if e[2] == 1))
print("Span:        %d us" % (events[-1][0] - events[0][0]) if events else 0)
print("=" * 60)

# Leave ROM_SM, BANK_SM running so TS-2068 stays alive
MQ.active(0)
print("MQ deactivated. ROM_SM/BANK_SM left running.")
