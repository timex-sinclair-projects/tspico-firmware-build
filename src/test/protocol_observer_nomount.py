"""Observer for LOAD "" with NO prior mount — capture exact byte exchange.

Purpose:
  The user reports `LOAD ""` (without a prior `LOAD "tpi:filename.tap"`)
  intermittently produces Report J on the TS-2068. The expected behavior
  is that LOAD_TS detects no file is mounted and streams /assets/nofile.tap
  as a "no file mounted" help message. The agent's "file-open race"
  theory doesn't hold up to scrutiny — same code path worked under
  single-port v1.5. So we don't actually know what's failing.

  This harness captures EVERYTHING that crosses the wire when a no-mount
  LOAD "" is issued, with no LOAD_TS in the loop. We get ground truth
  about what the Z80 does and what state the Pico is in.

Setup matches production exactly:
  - ROM_SM/BANK_SM running (TS-2068 boots normally)
  - MQ active, Y = 0xFFFFFFFF (always ready)
  - TX FIFO pre-loaded with 0x01 (matches the boot pre-load chain in
    TS2068_IO())

Then we do NOTHING. We just log events:
  - Every Z80 OUT (RX byte) with timestamp, value, port indicator
  - Every TX-drain (when MQ.tx_fifo() decreases — Z80 read from TX)
  - Periodic FIFO state snapshots so we can see slow drift
  - Whatever's left in TX/RX at Ctrl-C

Use:
  1. Copy this file to the Pico via Thonny.
  2. Run it.
  3. Power on (or reset) the TS-2068.
  4. Wait until Pico is in the "READY" state (per the print).
  5. On TS-2068: type `LOAD ""` and press ENTER.
  6. Observe: what does the TS-2068 display? Report J? Hang?
  7. Wait a couple seconds for any post-failure activity.
  8. Ctrl-C in Thonny to dump.

Things we're trying to find out:
  Q1: Does the Z80 actually OUT the full 10-byte pre-header?
      (If not, the failure is upstream of LOAD_TS.)
  Q2: Does the Z80 successfully drain the pre-loaded 0x01 from TX?
      (If yes, the initial status read works — failure is later.)
  Q3: Does the Z80 OUT a block_type ack after status read?
      (If yes, status was OK; failure is in the data loop.)
  Q4: How many bytes does Z80 read from TX (i.e., how far does it
      get before giving up)?
  Q5: Does Z80 OUT a computed CRC at the end of its data loop?
      (If yes, Z80 thought the data was valid up through CRC verify.)
  Q6: At what point does the Z80 stop OUTting things?
      (The last OUT is the moment Z80 gave up.)

Once we have answers to these, the failure mode is identifiable.
"""

import time
import gc
from rp2 import StateMachine, asm_pio, PIO
from machine import Pin, freq

freq(270_000_000)

from TS.tspico_io import TS_IO_DUAL, set_ctrl, sel_bank


# ============================================================================
# Hardware setup (matches production main.py)
# ============================================================================

print("=" * 60)
print("NO-MOUNT LOAD OBSERVER")
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
print("[SETUP] ROM_SM/BANK_SM running")

MQ = StateMachine(0, TS_IO_DUAL, freq=30_000_000,
                  out_base=Pin(2, Pin.OUT),
                  in_base=Pin(2, Pin.IN),
                  jmp_pin=Pin(11),
                  sideset_base=Pin(12, Pin.OUT))
MQ.active(1)
MQ.exec("mov(y, invert(null))")
print("[SETUP] MQ active, Y=READY")

# Drain boot noise.
n = 0
last = time.ticks_ms()
while time.ticks_diff(time.ticks_ms(), last) < 300:
    if MQ.rx_fifo() > 0:
        MQ.get()
        n += 1
        last = time.ticks_ms()
print("[SETUP] flushed %d boot byte(s) from RX" % n)

# Pre-load 0x01 in TX FIFO. This matches what TS2068_IO() does at boot
# in production firmware. We deliberately do NOT pre-load anything else
# — we want to observe what happens with ONLY the boot status pre-load
# in place (which is the Pico state at the moment a no-mount LOAD ""
# would fire in production).
MQ.put(0x01)
print("[SETUP] TX FIFO pre-loaded with 0x01 (matches production boot state)")
print("[SETUP] tx_fifo=%d  rx_fifo=%d" % (MQ.tx_fifo(), MQ.rx_fifo()))


# ============================================================================
# Capture buffers (pre-allocated — no GC pauses in hot loop)
# ============================================================================

CAP = 128

# RX events (Z80 → Pico)
rx_buf = bytearray(CAP)         # byte values
rx_a0  = bytearray(CAP)         # port (0 = $0E, 1 = $0F)
rx_t   = [0] * CAP              # microsecond timestamps

# TX-drain events (Z80 reads from TX)
# When MQ.tx_fifo() decreases between two polls, that's a Z80 IN $0E.
# We can't easily capture WHICH byte was drained (the value is gone),
# but we DO know exactly when the drain happened.
tx_t   = [0] * CAP              # timestamp of detection
tx_n   = bytearray(CAP)         # how many bytes drained at this event
tx_after = bytearray(CAP)       # tx_fifo level AFTER the drain

# Periodic FIFO snapshots (slow drift — every 100ms)
snap_t = []
snap_tx = []
snap_rx = []


# ============================================================================
# Tight observation loop
# ============================================================================

print("=" * 60)
print("READY.")
print("  1. Power on TS-2068 (or it should already be on)")
print("  2. On TS-2068, type:  LOAD \"\"")
print("  3. Press ENTER")
print("  4. Watch the TS-2068 screen — does it show Report J?")
print("  5. Wait ~2 seconds for any post-failure activity")
print("  6. Ctrl-C here to dump the captured log")
print("=" * 60)
print("(Initial TX state captured. tx_fifo=%d rx_fifo=%d)" % (
    MQ.tx_fifo(), MQ.rx_fifo()))

T0 = time.ticks_us()
rx_count = 0
tx_count = 0
last_tx = MQ.tx_fifo()
last_snap = time.ticks_ms()

mq_rx_fifo = MQ.rx_fifo
mq_tx_fifo = MQ.tx_fifo
mq_get     = MQ.get
ticks_us   = time.ticks_us
ticks_ms   = time.ticks_ms
ticks_diff = time.ticks_diff

gc.collect()

try:
    while True:
        now_us = ticks_us()
        t = ticks_diff(now_us, T0)

        # ---- RX events: capture every Z80 OUT ----
        if mq_rx_fifo() > 0:
            raw = mq_get()
            if rx_count < CAP:
                rx_buf[rx_count] = raw & 0xFF
                rx_a0[rx_count]  = (raw >> 8) & 1
                rx_t[rx_count]   = t
                rx_count += 1

        # ---- TX-drain detection: tx_fifo went down ----
        cur_tx = mq_tx_fifo()
        if cur_tx < last_tx:
            drained = last_tx - cur_tx
            if tx_count < CAP:
                tx_t[tx_count]     = t
                tx_n[tx_count]     = drained
                tx_after[tx_count] = cur_tx
                tx_count += 1
        last_tx = cur_tx

        # ---- Periodic FIFO snapshots (every 100ms) ----
        now_ms = ticks_ms()
        if ticks_diff(now_ms, last_snap) >= 100:
            snap_t.append(t)
            snap_tx.append(cur_tx)
            snap_rx.append(mq_rx_fifo())
            last_snap = now_ms

except KeyboardInterrupt:
    pass


# ============================================================================
# Dump
# ============================================================================

print("")
print("=" * 60)
print("CAPTURE COMPLETE")
print("=" * 60)
print("RX events (Z80 OUTs):    %d" % rx_count)
print("TX-drain events (Z80 INs): %d" % tx_count)
print("Final tx_fifo: %d" % MQ.tx_fifo())
print("Final rx_fifo: %d" % MQ.rx_fifo())
print("=" * 60)


# Build a unified timeline of all events sorted by timestamp.
events = []
for i in range(rx_count):
    events.append((rx_t[i], "RX", rx_buf[i], rx_a0[i]))
for i in range(tx_count):
    events.append((tx_t[i], "TX-DRAIN", tx_n[i], tx_after[i]))
events.sort(key=lambda e: e[0])

if events:
    print("")
    print("UNIFIED TIMELINE:")
    print("%4s  %10s  %8s  %-9s  %s" % ("idx", "us", "delta", "kind", "detail"))
    print("-" * 60)
    prev_t = 0
    for i, (t, kind, a, b) in enumerate(events):
        delta = t - prev_t
        prev_t = t
        if kind == "RX":
            val, port = a, b
            asc = "'%s'" % chr(val) if 0x20 <= val < 0x7F else "   "
            port_s = "$0F" if port else "$0E"
            detail = "0x%02X %3s  port=%s" % (val, asc, port_s)
        else:
            n_drained, after = a, b
            detail = "%d byte(s) read by Z80, tx_fifo now %d" % (n_drained, after)
        print("%4d  %10d  %8d  %-9s  %s" % (i, t, delta, kind, detail))


# Decoded RX-only summary (treat as pre-header if first 10 bytes).
if rx_count > 0:
    print("")
    print("RX BYTES (Z80 OUTs only):")
    pre_labels = [
        "BLOCK_TYPE", "TADDR", "BANK",
        "SESS_LO", "SESS_HI",
        "MADDR_LO", "MADDR_HI",
        "BLEN_LO", "BLEN_HI",
        "PRE_CRC",
    ]
    for i in range(rx_count):
        val = rx_buf[i]
        port = rx_a0[i]
        asc = "'%s'" % chr(val) if 0x20 <= val < 0x7F else "   "
        if i < 10:
            label = pre_labels[i]
        elif i == 10:
            label = "block_type ack (Z80 echoes its expected type)"
        elif i == 11:
            label = "Z80 computed CRC over received content"
        else:
            label = "(post-CRC byte #%d)" % (i - 12)
        port_s = "$0F" if port else "$0E"
        print("  [%2d]  0x%02X  %3s  port=%s  %s" % (
            i, val, asc, port_s, label))

    if rx_count >= 10:
        crc = 0
        for i in range(9):
            crc ^= rx_buf[i]
        print("")
        print("Pre-header CRC verify: computed XOR=0x%02X  byte[9]=0x%02X  %s" % (
            crc, rx_buf[9], "MATCH" if crc == rx_buf[9] else "MISMATCH"))


# FIFO snapshots — show slow drift over time.
if snap_t:
    print("")
    print("FIFO SNAPSHOTS (every ~100ms):")
    print("%10s  %4s  %4s" % ("us", "tx", "rx"))
    print("-" * 30)
    # Only show snapshots where state changed (or first/last).
    last_state = None
    for i, (t, tx, rx) in enumerate(zip(snap_t, snap_tx, snap_rx)):
        state = (tx, rx)
        if state != last_state or i == 0 or i == len(snap_t) - 1:
            print("%10d  %4d  %4d" % (t, tx, rx))
            last_state = state


# Closing analysis hints.
print("")
print("=" * 60)
print("ANALYSIS HINTS:")
print("=" * 60)
print("Q1: Did Z80 OUT all 10 pre-header bytes?")
if rx_count >= 10:
    print("    YES (rx_count = %d)" % rx_count)
else:
    print("    NO (only %d bytes captured) — failure is upstream of LOAD_TS" % rx_count)

print("Q2: Did Z80 drain the pre-loaded 0x01 from TX?")
if tx_count > 0 and tx_t[0] < 1_000_000:
    print("    YES (first drain at +%dus)" % tx_t[0])
elif MQ.tx_fifo() == 0:
    print("    PROBABLY (tx_fifo is 0 at end — but couldn't pinpoint when)")
else:
    print("    NO (tx_fifo still has %d bytes — initial status read didn't happen)" % MQ.tx_fifo())

print("Q3: Did Z80 OUT a block_type ack? (would be index 10)")
if rx_count >= 11:
    print("    YES — 0x%02X" % rx_buf[10])
else:
    print("    NO (only %d RX bytes — Z80 didn't get past status check)" % rx_count)

print("Q4: Did Z80 OUT a computed CRC? (would be index 11)")
if rx_count >= 12:
    print("    YES — 0x%02X" % rx_buf[11])
else:
    print("    NO — Z80 either errored before CRC verify or didn't enter data loop")

print("Q5: How many bytes did Z80 try to read from TX?")
total_drained = sum(tx_n[i] for i in range(tx_count))
print("    %d total drains across %d events" % (total_drained, tx_count))

print("=" * 60)

MQ.active(0)
print("MQ deactivated. ROM_SM/BANK_SM left running.")
