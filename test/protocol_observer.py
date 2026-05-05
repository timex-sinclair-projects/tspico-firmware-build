"""TPI Protocol Observer — Gustavo v2.4 spec verifier.

Goal: show EXACTLY what bytes cross the wire during a LOAD attempt, in
order, with us-resolution timestamps. No live prints (they'd break the
2.8ms WF_NPH timing). All events buffered, dumped on Ctrl-C.

What it does:
  - Sets up ROM_SM, BANK_SM, MQ — TS-2068 boots normally
  - Y = 0xFFFFFFFF always (port $0F D6=1=ready). Z80 WF_NPH probes
    succeed instantly.
  - Pre-loads canned LOAD-header response into TX FIFO per spec page 11
  - Refills TX as Z80 drains it; logs every Z80 OUT
  - Ctrl-C dumps the full event log

Canned LOAD response (phase 2, "TEST" block):
   1. 0x01  status OK
   2. 0x00  REQUEST BLOCK TYPE ID (echo of pre[0])
   3. 0x00  BLOCK TYPE FROM FILE
   4. 0x03  HDTYPE (code block)
   5-14.    "TEST      " (10 bytes)
  15-16.    BLOCK LEN (0x0002)
  17-18.    MEMORY ADDR (0x0000)
  19-20.    HDVARS (0x8000)
   21.      CRC FROM FILE (0x80, fake)
   22.      0x01 final status

Use:
  1. Boot Pico, run this script via Thonny
  2. Power on TS-2068 (it should boot via the EXROM)
  3. Type LOAD "" on TS-2068
  4. Watch the screen for whatever error / behavior
  5. Ctrl-C in Thonny → see the byte-by-byte event log
"""

import time
import gc
from rp2 import StateMachine, asm_pio, PIO
from machine import Pin, freq

freq(270_000_000)

from TS.tspico_io import TS_IO_DUAL, set_ctrl, sel_bank


# ============================================================================
# Hardware setup
# ============================================================================

print("=" * 60)
print("TPI PROTOCOL OBSERVER — Gustavo v2.4 spec verifier")
print("=" * 60)

# Board pins (matching production main.py exactly)
U6_EN   = Pin(12, Pin.OUT, Pin.PULL_UP)
WAIT    = Pin(14, Pin.OUT, Pin.PULL_DOWN)
U10_ENA = Pin(19, Pin.OUT, Pin.PULL_UP)
U13_ENA = Pin(20, Pin.OUT, Pin.PULL_UP)
BE      = Pin(21, Pin.OUT, Pin.PULL_UP)
ROSCS   = Pin(26, Pin.IN,  Pin.PULL_DOWN)
U10_WE  = Pin(27, Pin.OUT, Pin.PULL_UP)
for p in (U6_EN, WAIT, U10_ENA, U13_ENA, BE, U10_WE):
    p.value(1)
print("[SETUP] pins configured")

# ROM_SM + BANK_SM — required for TS-2068 to boot via TS-Pico flash EXROM
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

# MQ — Y = 0xFFFFFFFF so $0F always returns 0xFF (D6=1=ready)
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
print("[SETUP] flushed %d boot byte(s)" % n)


# ============================================================================
# Canned LOAD-header response per spec page 11
# ============================================================================

CANNED = [
    (0x01, "status OK"),
    (0x00, "REQUEST BLOCK TYPE ID"),
    (0x00, "BLOCK TYPE FROM FILE (header)"),
    (0x03, "HDTYPE (code)"),
    (ord('T'), "name[0] T"),
    (ord('E'), "name[1] E"),
    (ord('S'), "name[2] S"),
    (ord('T'), "name[3] T"),
    (ord(' '), "name[4] sp"),
    (ord(' '), "name[5] sp"),
    (ord(' '), "name[6] sp"),
    (ord(' '), "name[7] sp"),
    (ord(' '), "name[8] sp"),
    (ord(' '), "name[9] sp"),
    (0x02,    "BLOCK LEN low"),
    (0x00,    "BLOCK LEN high"),
    (0x00,    "MEMORY ADDR low"),
    (0x00,    "MEMORY ADDR high"),
    (0x00,    "HDVARS low"),
    (0x80,    "HDVARS high"),
    (0x80,    "CRC FROM FILE"),
    (0x01,    "final status OK"),
]


# ============================================================================
# Event log (buffered — no live prints)
# ============================================================================

events = []           # list of (us_timestamp, kind, value, note)
T0 = time.ticks_us()

def log(kind, value, note=""):
    events.append((time.ticks_diff(time.ticks_us(), T0), kind, value, note))


# Pre-load TX FIFO with first 4 bytes of canned response
tx_idx = 0
while MQ.tx_fifo() < 4 and tx_idx < len(CANNED):
    val, note = CANNED[tx_idx]
    MQ.put(val)
    log("TX-pre", val, "[%d] %s" % (tx_idx, note))
    tx_idx += 1

last_tx_seen = MQ.tx_fifo()
print("=" * 60)
print('READY. Power on TS-2068 (boot from TS-Pico EXROM), then LOAD "".')
print("Ctrl-C in Thonny when done to see the byte log.")
print("=" * 60)


# ============================================================================
# Main loop — drain RX, refill TX, log everything
# ============================================================================

last_activity = time.ticks_ms()

try:
    while True:
        # --- Drain RX (Z80 OUTs land here) ---
        if MQ.rx_fifo() > 0:
            raw = MQ.get()
            data = raw & 0xFF
            a0 = (raw >> 8) & 1
            log("RX", data, "port=%s" % ("$0F" if a0 else "$0E"))
            last_activity = time.ticks_ms()

        # --- Detect TX drains (Z80 INs) ---
        cur_tx = MQ.tx_fifo()
        if cur_tx < last_tx_seen:
            drained = last_tx_seen - cur_tx
            log("TX-drain", drained, "tx_fifo now %d" % cur_tx)
            last_activity = time.ticks_ms()

        # --- Refill TX from canned ---
        if cur_tx < 4 and tx_idx < len(CANNED):
            val, note = CANNED[tx_idx]
            MQ.put(val)
            log("TX-fill", val, "[%d] %s" % (tx_idx, note))
            tx_idx += 1

        last_tx_seen = MQ.tx_fifo()

        # --- Heartbeat (rare, console-only, NOT in event log) ---
        # Skipped — we don't want USB serial activity during the protocol.

except KeyboardInterrupt:
    pass


# ============================================================================
# Dump the event log
# ============================================================================

print("")
print("=" * 60)
print("EVENT LOG (%d events)" % len(events))
print("=" * 60)

if not events:
    print("(no events — Z80 never touched the bus)")
else:
    print("%8s  %-9s %5s  %s" % ("us", "kind", "val", "note"))
    print("-" * 60)
    for t, kind, val, note in events:
        if isinstance(val, int):
            print("%8d  %-9s 0x%02X  %s" % (t, kind, val, note))
        else:
            print("%8d  %-9s %5s  %s" % (t, kind, val, note))

print("=" * 60)
print("RX summary:  %d byte(s)" % sum(1 for e in events if e[1] == "RX"))
print("TX sent:     %d / %d" % (tx_idx, len(CANNED)))
print("TX drains:   %d" % sum(1 for e in events if e[1] == "TX-drain"))
print("=" * 60)

# Leave ROM_SM and BANK_SM running so TS-2068 stays alive
MQ.active(0)
print("MQ deactivated. ROM_SM/BANK_SM left running.")
