"""CRC-aware observer for `LOAD ""` (no mount) — tests Gustavo's spec rule.

Spec reference (TS-PICO-TPI-PROTOCOL-SPECS_2.3.pdf, p.2, lines 100-107):

    "AS A GENERAL RULE, THE VALUE OF THE ERROR CODE CAN BE CALCULATED AS
     THE CRC OF ALL BYTES RECEIVED +01.
     IF THE RESULTING FINAL VALUE IS 0x01, NO INFORMATION TRANSMISSION
     ERROR HAS OCCURRED AND YOU SHOULD PROCEED WITH THE EXECUTION OF THE
     COMMAND NORMALLY."

CRC algorithm: simple XOR over all message bytes. Verified against the
two worked examples in the spec:
  - SAVE p.10: XOR(00 00 FF 63 10 A4 6C 11 00) = 0x55 = stated CRC ✓
  - LOAD p.11: XOR(00 01 FF 6A 86 B6 6C 11 00) = 0xD9 = stated CRC ✓

Status-byte rule for the Pico's response after the CRC:
    status = XOR(byte0..byte8, received_CRC) + 0x01
           = (local_xor XOR received_crc) + 1
    valid  -> 0 + 1 = 0x01 (OK)
    bad    -> some non-1 value mapped onto the error-code table

What this harness does differently from V6/V7/V8:
    Instead of unconditionally putting 0x01 after capturing the
    pre-header, we compute the spec-correct status and send THAT.
    On a clean LOAD with a real file, the pre-header CRC will be
    valid and we'll send 0x01 just like before — protocol unchanged.
    On `LOAD ""` with no prior mount, the prior nomount trace showed
    XOR(0..8)=0x05 vs received CRC=0x00 (mismatch). With this harness
    we'll send 0x06 (Report 6 — Number too big) per spec, and observe
    whether the 2068 cleanly aborts with that report or still issues
    Report J. Either outcome is informative:
      - Clean Report 6 -> the ROM honours the spec rule, and our
        production firmware should too.
      - Still Report J -> something else is going on with the bare
        LOAD case; we need a different theory.

Run it from Thonny exactly like the other observers. Type `LOAD ""`
on the 2068 (no MOUNT first) and Ctrl-C when done.
"""

import os
import time
import gc
from rp2 import StateMachine, asm_pio, PIO
from machine import Pin, freq

freq(270_000_000)

from TS.tspico_io import TS_IO_DUAL, set_ctrl, sel_bank


print("=" * 60)
print("HARNESS — CRC-aware response (spec p.2 rule)")
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
print("[SETUP] ROM_SM/BANK_SM running (TS-2068 can boot)")

MQ = StateMachine(0, TS_IO_DUAL, freq=30_000_000,
                  out_base=Pin(2, Pin.OUT),
                  in_base=Pin(2, Pin.IN),
                  jmp_pin=Pin(11),
                  sideset_base=Pin(12, Pin.OUT))
MQ.active(1)
MQ.exec("mov(y, invert(null))")
print("[SETUP] MQ active, Y=READY")

# Drain boot noise
n = 0
last = time.ticks_ms()
while time.ticks_diff(time.ticks_ms(), last) < 300:
    if MQ.rx_fifo() > 0:
        MQ.get()
        n += 1
        last = time.ticks_ms()
print("[SETUP] flushed %d boot byte(s) from RX FIFO" % n)

# Boot pre-load: a single 0x01 covers any pre-LOAD status poll the
# 2068 ROM might do (matches production V6 boot pattern).
MQ.put(0x01)
print("[SETUP] TX FIFO pre-loaded with 0x01")


# ============================================================================
# Capture buffers
# ============================================================================
CAP = 64
rx_buf = bytearray(CAP)
rx_a0  = bytearray(CAP)
rx_t   = [0] * CAP
events = []

# State for CRC computation across the pre-header.
PREHEADER_LEN = 10                # bytes 0..9 per spec (byte 9 = CRC)
running_xor = 0                   # XOR over bytes 0..8 as they arrive
sent_status = None                # what we put in TX FIFO at byte 9
received_crc = None               # byte 9 itself, for the dump


def on_rx(idx, val, port, t):
    """Compute and respond with the spec-correct status after byte 9."""
    global running_xor, sent_status, received_crc

    if idx < PREHEADER_LEN - 1:
        # Bytes 0..8 — accumulate XOR.
        running_xor ^= val
    elif idx == PREHEADER_LEN - 1:
        # Byte 9 — the CRC sent by Timex.
        received_crc = val
        # Spec rule: status = XOR(all received bytes incl. CRC) + 1
        total = (running_xor ^ val) & 0xFF
        status = (total + 1) & 0xFF
        sent_status = status
        MQ.put(status)
        events.append(
            ("CRC_CHECK",
             "local_xor=0x%02X received_crc=0x%02X "
             "total=0x%02X -> status=0x%02X" %
             (running_xor, val, total, status)))
    # idx >= PREHEADER_LEN: just observe whatever the ROM does next.


print("=" * 60)
print('READY. Power on TS-2068, then type:  LOAD ""')
print('(no MOUNT first — we want the bare-LOAD case)')
print('Ctrl-C in Thonny when done.')
print("=" * 60)

T0 = time.ticks_us()
rx_count = 0
mq_rx_fifo = MQ.rx_fifo
mq_get     = MQ.get
ticks_us   = time.ticks_us
ticks_diff = time.ticks_diff
gc.collect()

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
                on_rx(rx_count, val, a0, t)
                rx_count += 1
except KeyboardInterrupt:
    pass


def decode_and_dump():
    print("")
    print("=" * 60)
    print("RX captured: %d byte(s)" % rx_count)
    print("=" * 60)
    if rx_count == 0:
        print("(no RX — Z80 didn't OUT anything)")
        return

    # Pre-header field labels (spec p.3 / p.10-11).
    PH_LABELS = [
        "BLOCK_TYPE",
        "TADDR",
        "BANK",
        "SESS_LO",
        "SESS_HI",
        "MADDR_LO",
        "MADDR_HI",
        "BLEN_LO",
        "BLEN_HI",
        "CRC",
    ]

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
        note = PH_LABELS[i] if i < PREHEADER_LEN else "post-header"
        print("%4d  %8d  %8d  0x%02X  %3s  %4s  %s" % (
            i, t, delta, val, asc, port_s, note))
    print("=" * 60)

    if rx_count >= PREHEADER_LEN:
        # Recompute from the captured buffer for cross-check.
        x = 0
        for i in range(PREHEADER_LEN - 1):
            x ^= rx_buf[i]
        crc = rx_buf[PREHEADER_LEN - 1]
        total = (x ^ crc) & 0xFF
        status = (total + 1) & 0xFF
        match = "MATCH" if x == crc else "MISMATCH"
        print("PRE-HEADER CRC ANALYSIS")
        print("-" * 60)
        print("  bytes [0..8]      : %s" %
              " ".join("%02X" % rx_buf[i] for i in range(9)))
        print("  XOR over [0..8]   : 0x%02X" % x)
        print("  received CRC [9]  : 0x%02X" % crc)
        print("  result            : %s" % match)
        print("  XOR(all 10 bytes) : 0x%02X" % total)
        print("  status sent       : 0x%02X (= XOR_all + 1)" % status)
        print("  meaning per spec  :")
        # Map common status codes to spec error names (p.4).
        names = {
            0x00: "Report J - Invalid I/O Device",
            0x01: "OK (no transmission error)",
            0x02: "Report R - Tape Loading Error",
            0x03: "Report F - Invalid Filename",
            0x04: "Report Q - Parameter Error",
            0x05: "Report C - Non Sense in Basic",
            0x06: "Report 6 - Number Too Big",
            0x07: "Report 8 - End of File",
            0x08: "Report A - Invalid Argument",
            0x09: "Report 9 - Stop",
            0x0A: "Report J - Invalid I/O Device",
        }
        print("    0x%02X = %s" %
              (status, names.get(status, "(unmapped status code)")))
        print("=" * 60)

    if events:
        print("EVENTS:")
        for ev in events:
            print("  " + repr(ev))
        print("=" * 60)


decode_and_dump()
MQ.active(0)
print("MQ deactivated. ROM_SM/BANK_SM left running.")
