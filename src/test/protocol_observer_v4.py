"""Protocol observer V4 — pre-loaded status, capture post-status sequence.

Difference from V3: pre-loads 0x01 in TX FIFO at startup, instead of writing
it after detecting byte 10. Z80's status read happens ~8us after byte 9 hits
the bus; MicroPython is too slow to react in that window. Pre-loading is
safe because Z80 does no $0E reads during the pre-header OUT phase (only
after byte 9 = CRC, per EXROM l196dh disassembly).

Expected events for a successful protocol traversal:
  RX[0..9]   — 10 pre-header bytes (Z80 OUTs)
  Z80 reads $0E status (drains pre-loaded 0x01)        — invisible (no log)
  Z80 polls $0F (sees Y=0xFFFFFFFF = ready)            — invisible
  RX[10]     — block_type ack (Z80 OUTs H register)
  Z80 enters data loop, reads $0E DE times             — gets 0x00 stale
  Z80 reads $0E for file CRC                            — gets 0x00 stale
                                                          (XOR matches if
                                                           all data was 0)
  RX[11]     — Z80 OUTs computed CRC (sub_1924h)
  Z80 polls $0F (ready)                                 — invisible
  Z80 reads $0E for final status — gets 0x00 → R Tape error or J error

So we expect ~12 RX events: 10 pre-header + 1 block_type ack + 1 computed CRC
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
print("PROTOCOL OBSERVER V4 — pre-loaded status, post-status capture")
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
MQ.exec("mov(y, invert(null))")     # Y=READY always
print("[SETUP] MQ active, Y=READY")

n = 0
last = time.ticks_ms()
while time.ticks_diff(time.ticks_ms(), last) < 300:
    if MQ.rx_fifo() > 0:
        MQ.get()
        n += 1
        last = time.ticks_ms()
print("[SETUP] flushed %d boot byte(s)" % n)

# Pre-load 0x01 status. Z80 reads $0E for status ~8us after byte 9 OUT,
# so it must already be in the FIFO when LOAD command fires.
MQ.put(0x01)
print("[SETUP] TX FIFO pre-loaded with 0x01 (status)")


# ============================================================================
# Pre-allocated capture buffers
# ============================================================================

CAP = 64
rx_buf  = bytearray(CAP)
rx_a0   = bytearray(CAP)
rx_t    = [0] * CAP


# ============================================================================
# Tight capture loop
# ============================================================================

print("=" * 60)
print('READY. Power on TS-2068, then LOAD "".')
print("Wait ~1 second after the error appears, then Ctrl-C.")
print("=" * 60)

T0 = time.ticks_us()
rx_count = 0

mq_rx_fifo = MQ.rx_fifo
mq_get = MQ.get
ticks_us = time.ticks_us
ticks_diff = time.ticks_diff

try:
    while True:
        if mq_rx_fifo() > 0:
            raw = mq_get()
            t = ticks_diff(ticks_us(), T0)
            if rx_count < CAP:
                rx_buf[rx_count] = raw & 0xFF
                rx_a0[rx_count]  = (raw >> 8) & 1
                rx_t[rx_count]   = t
                rx_count += 1

except KeyboardInterrupt:
    pass


# ============================================================================
# Dump
# ============================================================================

print("")
print("=" * 60)
print("RX LOG  (%d byte(s) captured)" % rx_count)
print("=" * 60)

if rx_count == 0:
    print("(no RX activity — Z80 didn't OUT anything)")
else:
    print("%4s  %8s  %8s  0x%-2s  %3s  %4s  %s" % (
        "idx", "us", "delta", "vl", "asc", "port", "label"))
    print("-" * 70)

    pre_labels = [
        "BLOCK_TYPE",
        "TADDR (5C74h)",
        "BANK (5DCFh)",
        "5DD1h E (SESS_LO)",
        "5DD1h D (SESS_HI)",
        "IX E (MADDR_LO)",
        "IX D (MADDR_HI)",
        "DE E (BLEN_LO)",
        "DE D (BLEN_HI)",
        "CRC TIMEX (XOR of 0-8)",
    ]
    post_labels = [
        "block_type ack (H reg)",
        "Z80 computed CRC (after data loop)",
    ]

    prev_t = 0
    for i in range(rx_count):
        t = rx_t[i]
        delta = t - prev_t
        prev_t = t
        val = rx_buf[i]
        port = rx_a0[i]
        if 0x20 <= val < 0x7F:
            asc = "'%s'" % chr(val)
        else:
            asc = "   "
        port_s = "$0F" if port else "$0E"
        if i < 10:
            lbl = "[%d] %s" % (i, pre_labels[i])
        else:
            p_idx = i - 10
            if p_idx < len(post_labels):
                lbl = "[%d] %s" % (i, post_labels[p_idx])
            else:
                lbl = "[%d] post-status #%d (unexpected)" % (i, p_idx)
        print("%4d  %8d  %8d  0x%02X  %3s  %4s  %s" % (
            i, t, delta, val, asc, port_s, lbl))

print("=" * 60)
print("Pre-header (10 expected): captured %d byte(s)" % min(rx_count, 10))
if rx_count >= 10:
    crc = 0
    for i in range(9):
        crc ^= rx_buf[i]
    print("Computed XOR of bytes 0-8: 0x%02X    Z80's byte 9: 0x%02X    %s" % (
        crc, rx_buf[9], "MATCH" if crc == rx_buf[9] else "MISMATCH"))
print("Post-status RX: %d byte(s)" % max(0, rx_count - 10))
if rx_count >= 11:
    print("  [10] block_type ack: 0x%02X  (expected = pre-header[0] = 0x%02X)  %s" % (
        rx_buf[10], rx_buf[0],
        "MATCH" if rx_buf[10] == rx_buf[0] else "DIFFERS"))
if rx_count >= 12:
    print("  [11] Z80 computed CRC: 0x%02X" % rx_buf[11])
print("=" * 60)
print("Note: Z80 will error out (R Tape or J) since we sent zeros for content.")
print("That is expected — we are observing the protocol shape, not loading.")
print("=" * 60)

MQ.active(0)
print("MQ deactivated. ROM_SM/BANK_SM left running.")
