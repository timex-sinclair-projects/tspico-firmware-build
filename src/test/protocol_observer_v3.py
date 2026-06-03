"""Protocol observer V3 — tight capture, respond after pre-header.

Goal: capture all 10 pre-header bytes (no drops), respond with 0x01 status,
then capture the post-status sequence (block_type ack + whatever else).

Architecture:
  - Y = 0xFFFFFFFF always — Z80's $0F polls succeed instantly
  - Pre-allocated bytearray buffers for timestamps + data — NO list.append()
    in the capture loop, no GC pauses, no missed bytes
  - Capture loop is tight: ~10us per RX drain
  - After 10 bytes captured, write 0x01 to TX (Z80's status read succeeds)
  - Continue capturing — log block_type ack and any further OUTs

Per EXROM l196dh trace:
  Z80 OUTs 10 pre-header bytes (di disabled, contiguous, ~30us each)
    [0] block_type, [1] flag (sysvar 5C74h),  [2] flag (sysvar 5DCFh),
    [3,4] sysvar 5DD1h DE, [5,6] IX, [7,8] DE, [9] running XOR CRC
  Then IN $0E status, WF_NPH poll $0F, OUT block_type ack (H register)
  Then enters data loop (IN $0E many times)

Use:
  1. Run via Thonny
  2. Power on TS-2068 (boots via EXROM)
  3. LOAD ""
  4. Wait a couple seconds for the transaction to play out / time out
  5. Ctrl-C → dump
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
print("PROTOCOL OBSERVER V3 — tight capture + status response")
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
MQ.exec("mov(y, invert(null))")
print("[SETUP] MQ active, Y=READY")

n = 0
last = time.ticks_ms()
while time.ticks_diff(time.ticks_ms(), last) < 300:
    if MQ.rx_fifo() > 0:
        MQ.get()
        n += 1
        last = time.ticks_ms()
print("[SETUP] flushed %d boot byte(s)" % n)


# ============================================================================
# Pre-allocated capture buffers (avoid list.append GC stalls)
# ============================================================================

CAP = 64
rx_buf  = bytearray(CAP)         # captured byte values
rx_a0   = bytearray(CAP)         # port indicator (0=$0E, 1=$0F)
rx_t    = [0] * CAP              # timestamps (us from T0)
tx_log  = []                     # TX events (append OK — happens after Z80 done)
events_msg = []                  # extra notes


# ============================================================================
# Tight capture loop
# ============================================================================

print("=" * 60)
print('READY. Power on TS-2068, then LOAD "".')
print("Pico will respond with 0x01 status after byte 10 arrives.")
print("Ctrl-C in Thonny when transaction settles to see the log.")
print("=" * 60)

T0 = time.ticks_us()
rx_count = 0
status_sent = False

# Local refs for speed (avoid attribute lookups in hot loop)
mq_rx_fifo = MQ.rx_fifo
mq_get = MQ.get
mq_put = MQ.put
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
                # Send status response after all 10 pre-header bytes captured
                if rx_count == 10 and not status_sent:
                    mq_put(0x01)
                    tx_log.append((ticks_diff(ticks_us(), T0), 0x01,
                                   "status OK (response to 10-byte pre-header)"))
                    status_sent = True

except KeyboardInterrupt:
    pass


# ============================================================================
# Dump
# ============================================================================

print("")
print("=" * 60)
print("EVENT LOG  (RX=%d  TX=%d)" % (rx_count, len(tx_log)))
print("=" * 60)

if rx_count == 0 and not tx_log:
    print("(no activity)")
else:
    # Merge RX and TX events by timestamp
    merged = []
    for i in range(rx_count):
        merged.append((rx_t[i], "RX", rx_buf[i], rx_a0[i], i))
    for t, val, note in tx_log:
        merged.append((t, "TX", val, 0, note))
    merged.sort(key=lambda e: e[0])

    print("%4s  %8s  %8s  %-2s  0x%-2s  %3s  %4s  %s" % (
        "idx", "us", "delta", "kd", "vl", "asc", "port", "note"))
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
    ]

    rx_seen = 0
    prev_t = 0
    for i, (t, kind, val, port, note_or_idx) in enumerate(merged):
        delta = t - prev_t
        prev_t = t
        if 0x20 <= val < 0x7F:
            asc = "'%s'" % chr(val)
        else:
            asc = "   "
        port_s = "$0F" if port else "$0E"
        if kind == "RX":
            idx = note_or_idx
            if idx < 10:
                lbl = "[%d] %s" % (idx, pre_labels[idx])
            else:
                p_idx = idx - 10
                if p_idx < len(post_labels):
                    lbl = "[%d] %s" % (idx, post_labels[p_idx])
                else:
                    lbl = "[%d] post-status #%d" % (idx, p_idx)
            rx_seen += 1
            print("%4d  %8d  %8d  RX  0x%02X  %3s  %4s  %s" % (
                i, t, delta, val, asc, port_s, lbl))
        else:
            print("%4d  %8d  %8d  TX  0x%02X  %3s  ---   %s" % (
                i, t, delta, val, asc, note_or_idx))

print("=" * 60)
print("Pre-header (10 expected): captured %d byte(s)" % min(rx_count, 10))
if rx_count >= 10:
    crc = 0
    for i in range(9):
        crc ^= rx_buf[i]
    print("Computed XOR of bytes 0-8: 0x%02X    Z80's byte 9: 0x%02X    %s" % (
        crc, rx_buf[9], "MATCH" if crc == rx_buf[9] else "MISMATCH"))
print("Post-status RX: %d byte(s)" % max(0, rx_count - 10))
print("=" * 60)

MQ.active(0)
print("MQ deactivated. ROM_SM/BANK_SM left running.")
