"""Minimal dual-port PIO test harness with full telemetry.

Run this directly on the Pico (no TS package needed). It sets up the
dual-port PIO and prints every event with timing, FIFO state, and
scratch Y state so we can see exactly what the hardware is doing.

Usage:
  1. Save this file to the Pico as /test_dual.py via Thonny
  2. From the Pico REPL:
       exec(open('/test_dual.py').read())
  3. From the TS-2068, send a few I/O instructions:
       OUT 14, 65       (sends 0x41 'A' to port $0E)
       OUT 15, 99       (sends 0x63 'c' to port $0F)
       PRINT IN(14)     (reads port $0E — gets next byte from FIFO)
       PRINT IN(15)     (reads port $0F — gets scratch Y)
  4. Watch the Pico REPL for what was received

Expected behavior:
  - Every Z80 OUT prints "RX: port=$0E val=0x41" or similar
  - Every Z80 IN $0E gets a byte from the pre-loaded TX FIFO
  - Every Z80 IN $0F returns scratch Y (set to 0xFFFFFFFF below)
"""

import time
import gc
from rp2 import StateMachine, asm_pio, PIO
from machine import Pin, freq

# Set CPU clock — same as production firmware
freq(270_000_000)


@asm_pio(
    sideset_init=PIO.OUT_HIGH,
    out_init=(PIO.OUT_LOW,) * 8,
    out_shiftdir=PIO.SHIFT_RIGHT,
    in_shiftdir=PIO.SHIFT_LEFT,
)
def TS_IO_DUAL():
    wait(0, gpio, 14)       .side(1)
    jmp(pin, "z80_out")     .side(1)

    in_(pins, 9)            .side(0)
    mov(osr, isr)           .side(0)
    mov(isr, null)          .side(0)
    out(null, 8)            .side(0)
    out(x, 1)               .side(0)
    jmp(not_x, "rd_data")   .side(0)

    mov(osr, y)             .side(0)
    out(pins, 8)            .side(0)
    jmp("fin")              .side(0)

    label("rd_data")
    pull(noblock)           .side(0)
    out(pins, 8)            .side(0)
    jmp("fin")              .side(0)

    label("z80_out")
    nop()                   .side(0)
    in_(pins, 9)            .side(0) [2]
    push(noblock)           .side(0)

    label("fin")
    wait(1, gpio, 14)       .side(0)
    mov(null, osr)          .side(1)


# ---- Telemetry ----

_t_last  = 0          # last telemetry timestamp (us)
_t_start = 0          # session start (us)


def TLM_RESET():
    """Reset telemetry timers and print a banner."""
    global _t_last, _t_start
    gc.collect()
    _t_start = time.ticks_us()
    _t_last  = _t_start
    print("=" * 60)
    print("[TLM %d] === SESSION START ===" % _t_start)
    print("=" * 60)


def TLM(action, detail=""):
    """Log one event with delta-time and FIFO/Y state."""
    global _t_last
    now = time.ticks_us()
    dt  = time.ticks_diff(now, _t_last)
    _t_last = now

    try:
        tx = sm.tx_fifo()
        rx = sm.rx_fifo()
        fifo = "tx=%d rx=%d" % (tx, rx)
    except:
        fifo = "tx=? rx=?"

    head = "[TLM %d dt=%d %s]" % (now, dt, fifo)
    if detail:
        print("%s %s: %s" % (head, action, detail))
    else:
        print("%s %s" % (head, action))


# ---- Board setup ----

TLM_RESET()
TLM("setting up board pins")

U6_EN   = Pin(12, Pin.OUT, Pin.PULL_UP)
WAIT    = Pin(14, Pin.OUT, Pin.PULL_DOWN)
U10_ENA = Pin(19, Pin.OUT, Pin.PULL_UP)
U13_ENA = Pin(20, Pin.OUT, Pin.PULL_UP)
BE      = Pin(21, Pin.OUT, Pin.PULL_UP)
U10_WE  = Pin(27, Pin.OUT, Pin.PULL_UP)

U6_EN.value(1)
WAIT.value(1)
U10_ENA.value(1)
U13_ENA.value(1)
BE.value(1)
U10_WE.value(1)
TLM("board pins configured", "GPIO 12,14,19,20,21,27 set high; GPIO 14 will be /PICOSEL")


# ---- PIO setup ----

TLM("creating StateMachine", "freq=30MHz, TS_IO_DUAL, 19 instructions")
sm = StateMachine(0, TS_IO_DUAL, freq=30_000_000,
                  out_base=Pin(2, Pin.OUT),
                  in_base=Pin(2, Pin.IN),
                  jmp_pin=Pin(11),
                  sideset_base=Pin(12, Pin.OUT))
TLM("StateMachine created (inactive)")

# Set scratch Y to all-1s. Z80 IN $0F → 0xFF → bit 6 set = "ready"
TLM("setting scratch Y = 0xFFFFFFFF (port $0F → 0xFF, bit 6 set = READY)")
sm.exec("mov(y, invert(null))")
TLM("Y set")

# Pre-load TX FIFO with sentinel values. Z80 IN $0E reads consume these.
# IMPORTANT: PIO TX FIFO is only 4 entries deep. Putting more than 4
# while the SM is inactive blocks forever (no consumer).
seed = (0xAA, 0x55, 0x42, 0xC3)
TLM("pre-loading TX FIFO", "values=%s" % [hex(v) for v in seed])
for v in seed:
    sm.put(v)
TLM("TX FIFO loaded", "tx=%d / 4" % sm.tx_fifo())

# Activate the state machine — GPIO 12 will go HIGH (sideset_init),
# but PIO is waiting on /PICOSEL so no bus activity yet.
TLM("activating StateMachine")
sm.active(1)
TLM("StateMachine ACTIVE — ready for Z80 bus traffic")

print("")
print("┌──────────────────────────────────────────────────────────┐")
print("│ Test commands to send from TS-2068 BASIC:                │")
print("│                                                          │")
print("│   PRINT IN(15)         expect 255 (port \\$0F = ready)     │")
print("│   PRINT IN(14)         expect 170 (0xAA from FIFO)       │")
print("│   PRINT IN(14)         expect  85 (0x55 from FIFO)       │")
print("│   OUT 14, 65           sends 'A' to port \\$0E             │")
print("│   OUT 15, 1            sends 1 to port \\$0F               │")
print("│                                                          │")
print("│ Pico REPL will show every byte the Z80 sends, plus a     │")
print("│ heartbeat every 5 seconds with FIFO state.               │")
print("└──────────────────────────────────────────────────────────┘")
print("")


# ---- Main monitor loop ----

seen_rx = 0
seen_tx_drained = 0
last_heartbeat = time.ticks_ms()
last_tx_seen = sm.tx_fifo()

try:
    while True:
        # Watch for Z80 OUT instructions (bytes arrive in RX FIFO)
        if sm.rx_fifo() > 0:
            raw  = sm.get()
            data = raw & 0xFF
            port = (raw >> 8) & 1
            seen_rx += 1
            TLM("RX byte #%d" % seen_rx,
                "port=%s val=0x%02X (%d) raw=0x%X" % (
                    "$0F" if port else "$0E",
                    data, data, raw,
                ))

        # Watch for Z80 IN $0E reads (TX FIFO drains)
        cur_tx = sm.tx_fifo()
        if cur_tx < last_tx_seen:
            drained = last_tx_seen - cur_tx
            for _ in range(drained):
                seen_tx_drained += 1
                TLM("TX drained (Z80 read $0E) #%d" % seen_tx_drained,
                    "tx_remaining=%d" % cur_tx)
        last_tx_seen = cur_tx

        # Heartbeat every 5 seconds — confirms Pico is alive
        now = time.ticks_ms()
        if time.ticks_diff(now, last_heartbeat) > 5000:
            TLM("heartbeat",
                "rx_total=%d tx_drained=%d" % (seen_rx, seen_tx_drained))
            # Refill TX FIFO with as many values as fit (max 4 entries)
            while sm.tx_fifo() < 4:
                sm.put(seed[sm.tx_fifo() % len(seed)])
            if sm.tx_fifo() != last_tx_seen:
                TLM("TX FIFO refilled", "tx=%d" % sm.tx_fifo())
                last_tx_seen = sm.tx_fifo()
            last_heartbeat = now

except KeyboardInterrupt:
    sm.active(0)
    TLM("session stopped (Ctrl-C)",
        "total RX=%d TX=%d" % (seen_rx, seen_tx_drained))
    print("=" * 60)
