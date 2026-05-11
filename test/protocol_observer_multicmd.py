"""Multi-command observer — captures across LOAD "tpi:pt.tap" then LOAD "".

Goal:
  See the byte sequences of two commands back-to-back. We particularly
  want to see the size and shape of each pre-header, and how the
  protocol stitches between commands.

How it stays alive across multiple commands:
  Production V6 firmware refills TX with 0x01 at the tail of every
  command handler so the next command's status poll has something to
  read. We can't run real handlers in a harness, so we fake the same
  effect: any time the TX FIFO drops to 0 AND there's been recent RX
  activity, we put another 0x01. This mimics the steady-state V6
  pattern without us having to dispatch real commands.

Caveat:
  The Z80 won't actually load any file content because we're not
  sending header/data blocks back. Each LOAD will eventually error on
  the 2068 (after pre-header timeout). That's fine — we want the
  bytes, not the success.

Procedure:
  1. Power on TS-2068 + run this harness.
  2. Type:  LOAD "tpi:pt.tap"
     -> wait for the 2068 to settle (it will likely error)
  3. Type:  LOAD ""
     -> wait for it to settle / error
  4. Ctrl-C in Thonny.
  5. Read the dump. The timeline is grouped by "phase" — each gap
     of >50ms between events starts a new phase block.

What to look for in the dump:
  - How many bytes before the first ~88ms gap in command 1?
  - How many bytes between the gap and the first auto-refill drain?
  - Same questions for command 2.
  - Compare to the earlier 9-byte truncation pattern. Does
    LOAD "tpi:pt.tap" follow the same shape, or does it look
    different (more bytes, different gap position, no gap)?
"""

import os
import time
import gc
from rp2 import StateMachine, asm_pio, PIO
from machine import Pin, freq

freq(270_000_000)

from TS.tspico_io import TS_IO_DUAL, set_ctrl, sel_bank


print("=" * 60)
print("HARNESS — multi-command observer (tpi mount + LOAD)")
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

# Drain boot noise.
n = 0
last = time.ticks_ms()
while time.ticks_diff(time.ticks_ms(), last) < 300:
    if MQ.rx_fifo() > 0:
        MQ.get()
        n += 1
        last = time.ticks_ms()
print("[SETUP] flushed %d boot byte(s) from RX FIFO" % n)

# Production V6 boot pre-load: a single 0x01.
MQ.put(0x01)
print("[SETUP] TX FIFO pre-loaded with 0x01 (V6 boot pattern)")


# ============================================================================
# Capture
# ============================================================================
CAP = 256                          # plenty for two full command exchanges
# Three event types: 'R' = RX byte, 'D' = TX-drain detected, 'F' = auto-refill
ev_kind = bytearray(CAP)           # ord('R'), ord('D'), ord('F')
ev_val  = bytearray(CAP)           # for R: the byte value
ev_port = bytearray(CAP)           # for R: 0=$0E, 1=$0F
ev_t    = [0] * CAP                # microsecond timestamp


print("=" * 60)
print('READY. On the TS-2068, type these in order:')
print('  1)  LOAD "tpi:pt.tap"     (let it settle / error out)')
print('  2)  LOAD ""               (let it settle / error out)')
print('Then Ctrl-C in Thonny to dump.')
print("=" * 60)

T0 = time.ticks_us()
ev_count = 0

mq_rx_fifo = MQ.rx_fifo
mq_tx_fifo = MQ.tx_fifo
mq_get     = MQ.get
mq_put     = MQ.put
ticks_us   = time.ticks_us
ticks_diff = time.ticks_diff
gc.collect()

# Track TX-FIFO level changes so we can see when the Z80 reads our
# response bytes. Initialize to current level.
prev_tx = mq_tx_fifo()
last_rx_us = T0                    # for "recent activity" check on refill

# Auto-refill policy: when TX FIFO hits 0 and we've had RX activity in
# the last 500ms, put another 0x01. Don't refill if there's been no
# recent activity (avoids piling up bytes during idle).
REFILL_WINDOW_US = 500_000
REFILL_BYTE = 0x01

try:
    while True:
        # 1) Drain any RX bytes
        while mq_rx_fifo() > 0 and ev_count < CAP:
            raw = mq_get()
            t = ticks_diff(ticks_us(), T0)
            ev_kind[ev_count] = ord('R')
            ev_val[ev_count]  = raw & 0xFF
            ev_port[ev_count] = (raw >> 8) & 1
            ev_t[ev_count]    = t
            ev_count += 1
            last_rx_us = ticks_us()

        # 2) Watch TX-FIFO transitions
        cur_tx = mq_tx_fifo()
        if cur_tx < prev_tx and ev_count < CAP:
            # Z80 just consumed a byte from $0E
            t = ticks_diff(ticks_us(), T0)
            ev_kind[ev_count] = ord('D')
            ev_val[ev_count]  = cur_tx        # store new level
            ev_port[ev_count] = 0
            ev_t[ev_count]    = t
            ev_count += 1
        prev_tx = cur_tx

        # 3) Auto-refill if TX is empty AND we've had recent RX
        if cur_tx == 0:
            if ticks_diff(ticks_us(), last_rx_us) < REFILL_WINDOW_US:
                mq_put(REFILL_BYTE)
                if ev_count < CAP:
                    t = ticks_diff(ticks_us(), T0)
                    ev_kind[ev_count] = ord('F')
                    ev_val[ev_count]  = REFILL_BYTE
                    ev_port[ev_count] = 0
                    ev_t[ev_count]    = t
                    ev_count += 1
                prev_tx = mq_tx_fifo()
except KeyboardInterrupt:
    pass


# ============================================================================
# Dump
# ============================================================================
def decode_and_dump():
    print("")
    print("=" * 60)
    print("Total events: %d (cap %d)" % (ev_count, CAP))
    print("=" * 60)
    if ev_count == 0:
        print("(no activity)")
        return

    GAP_US = 50_000   # 50ms gap = new phase block

    # First pass: collect RX-only sub-sequences for per-phase CRC analysis
    phases = []         # list of lists of indices into ev arrays
    cur = []
    prev_t = ev_t[0]
    for i in range(ev_count):
        if i > 0 and (ev_t[i] - prev_t) > GAP_US:
            if cur:
                phases.append(cur)
            cur = []
        cur.append(i)
        prev_t = ev_t[i]
    if cur:
        phases.append(cur)

    # Pretty-print
    print("%4s  %10s  %8s  %4s  %5s  %3s  %s" % (
        "ev#", "us", "delta", "kind", "val", "prt", "note"))
    print("-" * 70)
    prev_t = 0
    for pi, phase in enumerate(phases):
        # phase header
        rx_in_phase = [j for j in phase if ev_kind[j] == ord('R')]
        d_in_phase  = [j for j in phase if ev_kind[j] == ord('D')]
        f_in_phase  = [j for j in phase if ev_kind[j] == ord('F')]
        print("--- PHASE %d  (%d RX, %d TX-drain, %d auto-refill) ---" % (
            pi, len(rx_in_phase), len(d_in_phase), len(f_in_phase)))
        for i in phase:
            t = ev_t[i]
            delta = t - prev_t
            prev_t = t
            k = chr(ev_kind[i])
            if k == 'R':
                v = ev_val[i]
                asc = "'%s'" % chr(v) if 0x20 <= v < 0x7F else "   "
                port_s = "$0F" if ev_port[i] else "$0E"
                print("%4d  %10d  %8d  %4s  0x%02X  %3s  %s" % (
                    i, t, delta, "RX", v, asc, port_s))
            elif k == 'D':
                lvl = ev_val[i]
                print("%4d  %10d  %8d  %4s   ---       ---  TX-DRAIN -> level=%d" % (
                    i, t, delta, "DRN", lvl))
            elif k == 'F':
                v = ev_val[i]
                print("%4d  %10d  %8d  %4s  0x%02X       ---  AUTO-REFILL" % (
                    i, t, delta, "FILL", v))

        # CRC analysis on RX-only bytes within this phase, IF >= 10
        rx_vals = [ev_val[j] for j in rx_in_phase]
        if len(rx_vals) >= 10:
            x = 0
            for k in range(9):
                x ^= rx_vals[k]
            crc = rx_vals[9]
            match = "MATCH" if x == crc else "MISMATCH"
            print("    [phase CRC check: XOR(0..8)=0x%02X  byte9=0x%02X  %s]" % (
                x, crc, match))
        elif len(rx_vals) > 0:
            x = 0
            for v in rx_vals:
                x ^= v
            print("    [%d RX bytes, XOR=0x%02X — too short for 10-byte pre-header]" % (
                len(rx_vals), x))
        print("")

    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("-" * 70)
    total_rx = sum(1 for i in range(ev_count) if ev_kind[i] == ord('R'))
    total_d  = sum(1 for i in range(ev_count) if ev_kind[i] == ord('D'))
    total_f  = sum(1 for i in range(ev_count) if ev_kind[i] == ord('F'))
    print("  RX bytes        : %d" % total_rx)
    print("  TX-drains seen  : %d" % total_d)
    print("  Auto-refills    : %d" % total_f)
    print("  Phases (>50ms)  : %d" % len(phases))
    for pi, phase in enumerate(phases):
        rx_in_phase = sum(1 for j in phase if ev_kind[j] == ord('R'))
        first_t = ev_t[phase[0]]
        print("    phase %d: %d RX bytes, starts at %d us" % (
            pi, rx_in_phase, first_t))
    print("=" * 70)


decode_and_dump()
MQ.active(0)
print("MQ deactivated. ROM_SM/BANK_SM left running.")
