"""CRC-aware observer — comparison case: NAMED LOAD instead of bare LOAD "".

Companion to protocol_observer_crc.py. Same CRC logic, same pre-load
strategy, but you type:

    LOAD "TEST"     (or any other non-empty name)

instead of bare LOAD "". The point is to capture a pre-header from a
LOAD command the ROM treats as "real" and compare it against the
9-byte stub we got from `LOAD ""`.

Hypothesis being tested:
  - If named LOAD also produces 9 bytes that stop early at the same
    position, then the truncation isn't bare-LOAD-specific — the
    pre-loaded 0x01 status is short-circuiting EVERY LOAD command and
    we've been getting away with it on production only because the
    rest of the protocol exchange covers up the early termination.
  - If named LOAD produces a clean 10-byte pre-header with byte 9 = a
    valid CRC (XOR of bytes 0..8), then bare LOAD "" really is
    producing a different/shorter command structure and we need to
    handle that case explicitly.

Either outcome is informative. Diff this trace against the bare-LOAD
trace and the truth will fall out.

Notes:
  - The file you name doesn't need to exist on the SD card. The ROM
    forms and sends the pre-header before it has any way to know
    whether the Pico can find the file. We're capturing the pre-header
    only — the LOAD itself will fail downstream (no header block from
    us), and that's fine.
  - CAP raised to 128 to capture post-pre-header bytes too. Per spec
    p.11, after the Pico responds OK to the pre-header CRC, the Z80
    OUTs 0x00 (REQUEST BLOCK TYPE ID) and then the Pico responds with
    the header block. The Z80 will keep sending bytes until it times
    out waiting for our header response.
"""

import os
import time
import gc
from rp2 import StateMachine, asm_pio, PIO
from machine import Pin, freq

freq(270_000_000)

from TS.tspico_io import TS_IO_DUAL, set_ctrl, sel_bank


print("=" * 60)
print("HARNESS — CRC + named LOAD (comparison)")
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

# Same boot pre-load as bare-LOAD harness — this IS the variable
# we're holding constant for the comparison.
MQ.put(0x01)
print("[SETUP] TX FIFO pre-loaded with 0x01")


# ============================================================================
# Capture
# ============================================================================
CAP = 128                          # extra room for post-pre-header bytes
rx_buf = bytearray(CAP)
rx_a0  = bytearray(CAP)
rx_t   = [0] * CAP
events = []

PREHEADER_LEN = 10
running_xor = 0
sent_status = None
received_crc = None


def on_rx(idx, val, port, t):
    global running_xor, sent_status, received_crc
    if idx < PREHEADER_LEN - 1:
        running_xor ^= val
    elif idx == PREHEADER_LEN - 1:
        received_crc = val
        total = (running_xor ^ val) & 0xFF
        status = (total + 1) & 0xFF
        sent_status = status
        MQ.put(status)
        events.append(
            ("CRC_CHECK",
             "local_xor=0x%02X received_crc=0x%02X "
             "total=0x%02X -> status=0x%02X" %
             (running_xor, val, total, status)))


print("=" * 60)
print('READY. Power on TS-2068, then type:  LOAD "TEST"')
print('(or any non-empty filename — file does not need to exist)')
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


def label_for(idx):
    """Best-guess label per spec p.3 + p.11 (LOAD command)."""
    PH = ["BLOCK_TYPE", "TADDR", "BANK",
          "SESS_LO", "SESS_HI",
          "MADDR_LO", "MADDR_HI",
          "BLEN_LO", "BLEN_HI",
          "CRC"]
    if idx < PREHEADER_LEN:
        return PH[idx]
    # Post-pre-header — per LOAD spec p.11:
    #   12: 0x00 REQUEST BLOCK TYPE ID
    # ...then the Pico is supposed to send the header block, but we
    # don't, so the next bytes are whatever the ROM does on timeout.
    if idx == PREHEADER_LEN:
        return "REQ_BLOCK_TYPE? (or post-status-poll)"
    return "post-header"


def decode_and_dump():
    print("")
    print("=" * 60)
    print("RX captured: %d byte(s)" % rx_count)
    print("=" * 60)
    if rx_count == 0:
        print("(no RX — Z80 didn't OUT anything)")
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
        print("%4d  %8d  %8d  0x%02X  %3s  %4s  %s" % (
            i, t, delta, val, asc, port_s, label_for(i)))
    print("=" * 60)

    if rx_count >= PREHEADER_LEN:
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
        print("  meaning per spec  : 0x%02X = %s" %
              (status, names.get(status, "(unmapped)")))
        print("=" * 60)
    else:
        print("PRE-HEADER ANALYSIS: incomplete — only %d byte(s) received "
              "(expected 10)" % rx_count)
        print("=" * 60)

    if events:
        print("EVENTS:")
        for ev in events:
            print("  " + repr(ev))
        print("=" * 60)


decode_and_dump()
MQ.active(0)
print("MQ deactivated. ROM_SM/BANK_SM left running.")
