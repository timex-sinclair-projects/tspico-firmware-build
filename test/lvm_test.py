"""Standalone LVM LOAD test harness for TS-Pico.

Runs on the Pico in place of the normal main.py. Sets up everything
needed so that on the TS-2068 you can type:

    LOAD ""

...and it'll exercise the dual-port LVM LOAD path with rich telemetry.

It does the same setup the production firmware does:
  1. Configure GPIOs and clock
  2. Mount SD card via SPI
  3. Copy /sd/TAP/pt.tap to /TMP/temp.tap (simulates a tpi:pt.tap mount)
  4. Switch from SPI back to PIO with the dual-port state machine
  5. Set scratch Y to 'ready' (port $0F bit 6 set)
  6. Wait for the Z80 to send the LVM LOAD pre-header
  7. Read pre[] and dispatch to LOAD_TS()
  8. Loop forever — every LOAD "" triggers another transfer

To use:
  1. Copy this file to Pico flash as /main.py (or run via exec())
  2. Reboot Pico
  3. On TS-2068: LOAD ""
  4. Watch Pico REPL for telemetry

To stop: Ctrl-C in Thonny.
"""

import gc
import os
import time
import _thread
import utime

from machine import Pin, freq, SPI
from rp2 import StateMachine, asm_pio, PIO

from TS.sdcard import SDCard
from TS.tspico_io import TS_IO_DUAL, LOAD_TS, END_MSG, WATCHDOG
from TS.tspico_io import set_ctrl, sel_bank   # PIO programs that map the EXROM in


# ============================================================================
# Boot — match main.py setup
# ============================================================================

freq(270_000_000)
print("=" * 60)
print("LVM TEST HARNESS — CPU clock %d Hz" % freq())
print("=" * 60)

U6_EN   = Pin(12, Pin.OUT, Pin.PULL_UP)
WAIT    = Pin(14, Pin.OUT, Pin.PULL_DOWN)
U10_ENA = Pin(19, Pin.OUT, Pin.PULL_UP)
U13_ENA = Pin(20, Pin.OUT, Pin.PULL_UP)
BE      = Pin(21, Pin.OUT, Pin.PULL_UP)
ROSCS   = Pin(26, Pin.IN,  Pin.PULL_DOWN)
U10_WE  = Pin(27, Pin.OUT, Pin.PULL_UP)
led     = Pin(25, Pin.OUT)

U6_EN.value(1)
WAIT.value(1)
U10_ENA.value(1)
U13_ENA.value(1)
BE.value(1)
U10_WE.value(1)
led.value(0)


# ============================================================================
# Minimal TSP (PICO_STATUS) for LOAD_TS
# ============================================================================

class TSP_Simple:
    f_name      = ""
    totlen      = 0
    offset      = 0
    tap_idx     = 0
    offset_tbl  = []
    append      = False
    VERBOSE     = False
    LOG_LEVEL   = 0     # 0 = INFO and above; LOG_ADD prints if level >= LOG_LEVEL

    # Bank/ROM mapping config — controls which Flash/SRAM slots the
    # set_ctrl and sel_bank state machines route Z80 ROM/DCK accesses to.
    ROM_SM      = 0x0A  # 1010: both DCK and ROM mapped to Flash
    DCK_SLOT    = 0
    ROM_SLOT    = 1     # slot 1 = TS-Pico modified EXROM (with TPI support)
    bank_sm     = 0     # set below to (DCK_SLOT << 4) | ROM_SLOT

TSP = TSP_Simple()
TSP.bank_sm = (TSP.DCK_SLOT << 4) | TSP.ROM_SLOT


# ============================================================================
# ROM / BANK state machines — map TS-Pico flash in for the original ROM
# ============================================================================
# Without these, Z80 sees the original (unmodified) TS-2068 ROM, which has
# no TPI protocol intercepts. LOAD "" then runs the original tape routine
# instead of dispatching to the Pico via TPI.

print("[SETUP] starting ROM control state machine (set_ctrl @ 150MHz, drives /BE on GPIO 21)")
ROM_SM_HW = StateMachine(4, set_ctrl, freq=150_000_000,
                         in_base=Pin(0, Pin.IN), jmp_pin=Pin(26),
                         set_base=Pin(21, Pin.OUT),
                         out_base=Pin(19, Pin.OUT))
ROM_SM_HW.active(1)

print("[SETUP] starting BANK selection state machine (sel_bank @ 150MHz)")
BANK_SM_HW = StateMachine(5, sel_bank, freq=150_000_000,
                          jmp_pin=Pin(26),
                          out_base=Pin(15, Pin.OUT))
BANK_SM_HW.active(1)

# Feed config to the SMs — tells them which Flash/SRAM slots to route
# DCK and ROM accesses to.
ROM_SM_HW.put(TSP.ROM_SM)
BANK_SM_HW.put(TSP.bank_sm)
print("[SETUP] ROM_SM=0x%02X, bank_sm=0x%02X (EXROM should now be mapped)" % (
    TSP.ROM_SM, TSP.bank_sm))


# ============================================================================
# Dummy NULL_SM for swapping pins between PIO and SPI
# ============================================================================

@asm_pio(autopull=True, pull_thresh=8)
def NULL_SM():
    nop()


# ============================================================================
# SD card mount
# ============================================================================

def activate_sd():
    """Switch shared GPIO 2-4 from PIO to SPI, mount SD."""
    print("[SETUP] activating SD")
    null = StateMachine(0, NULL_SM, freq=15_000_000)
    null.active(1)
    null.active(0)

    U3_CS = Pin(28, Pin.OUT, Pin.PULL_UP)
    D0 = Pin(2, Pin.IN)
    D1 = Pin(3, Pin.IN)
    D2 = Pin(4, Pin.IN)

    spi = SPI(0, sck=D0, mosi=D1, miso=D2)
    sd = SDCard(spi, U3_CS)
    os.mount(sd, "/sd")
    print("[SETUP] SD mounted at /sd")
    return spi


def deactivate_sd():
    """Unmount SD, deselect chip, clamp shared pins LOW."""
    print("[SETUP] deactivating SD")
    try:
        os.umount("/sd")
    except:
        pass
    Pin(28, Pin.OUT, Pin.PULL_UP).value(1)
    for p in (2, 3, 4):
        Pin(p, Pin.OUT).value(0)


# ============================================================================
# Copy SD TAP file to internal flash (simulates a tpi:pt.tap mount)
# ============================================================================

SOURCE_FILE = "/sd/TAP/pt.tap"
DEST_FILE   = "/TMP/temp.tap"


def mount_test_file():
    """Copy SOURCE_FILE → DEST_FILE and set up TSP state."""
    global TSP

    # Make sure /TMP exists
    try:
        os.mkdir("/TMP")
    except:
        pass

    try:
        os.remove(DEST_FILE)
    except:
        pass

    print("[SETUP] copying %s → %s" % (SOURCE_FILE, DEST_FILE))
    src_size = os.stat(SOURCE_FILE)[6]
    print("[SETUP] source size: %d bytes" % src_size)

    buf = bytearray(4096)
    copied = 0
    with open(SOURCE_FILE, "rb") as src, open(DEST_FILE, "wb") as dst:
        while True:
            n = src.readinto(buf)
            if not n:
                break
            dst.write(buf[:n])
            copied += n

    print("[SETUP] copied %d bytes" % copied)

    TSP.f_name  = SOURCE_FILE
    TSP.totlen  = os.stat(DEST_FILE)[6]
    TSP.offset  = 0
    TSP.tap_idx = 0
    print("[SETUP] TSP: f_name=%s totlen=%d offset=0 tap_idx=0" % (
        TSP.f_name, TSP.totlen))


# ============================================================================
# Activate dual-port MQ
# ============================================================================

MQ = None  # set by activate_mq()


def activate_mq():
    """Create and activate the dual-port TS_IO state machine."""
    global MQ
    print("[SETUP] activating MQ (TS_IO_DUAL @ 30MHz)")
    MQ = StateMachine(0, TS_IO_DUAL, freq=30_000_000,
                      out_base=Pin(2, Pin.OUT),
                      in_base=Pin(2, Pin.IN),
                      jmp_pin=Pin(11),
                      sideset_base=Pin(12, Pin.OUT))
    MQ.active(1)
    print("[SETUP] MQ active. Y=0 (busy until MQ_READY)")


def mq_ready():
    """Set scratch Y to all-1s → port $0F = 0xFF (bit 6 set = ready)."""
    MQ.exec("mov(y, invert(null))")


def mq_busy():
    """Set scratch Y to 0 → port $0F = 0x00 (bit 6 clear = not ready)."""
    MQ.exec("set(y, 0)")


# ============================================================================
# Boot noise flush
# ============================================================================

def flush_boot_noise(ms=500):
    """Drain any spurious bytes that arrived during reset / boot."""
    print("[SETUP] flushing boot noise (%dms)..." % ms)
    n = 0
    start = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start) < ms:
        if MQ.rx_fifo() > 0:
            MQ.get()
            n += 1
            start = time.ticks_ms()    # reset timer when we get a byte
    print("[SETUP] flushed %d boot byte(s)" % n)


# ============================================================================
# Setup sequence
# ============================================================================

print("\n--- SETUP PHASE ---")
activate_sd()
mount_test_file()
deactivate_sd()
activate_mq()
mq_ready()
flush_boot_noise(500)

print("")
print("=" * 60)
print("READY. Type LOAD \"\" on the TS-2068 now.")
print("Pico will wait, dispatch to LOAD_TS, and print telemetry.")
print("Loops forever — Ctrl-C in Thonny to stop.")
print("=" * 60)
print("")


# ============================================================================
# Main loop
# ============================================================================

# Globals that LOAD_TS / WATCHDOG expect to exist as MODULE GLOBALS in
# tspico_io. We set them here. (LOAD_TS uses `global dead`, `global kill`,
# `global busy`, `global log_entries` from the tspico_io module scope.)
import TS.tspico_io as tio
tio.dead = True
tio.kill = False
tio.busy = False
tio.log_entries = ""


pre = bytearray(10)
r1 = range(10)

iteration = 0
try:
    while True:
        if MQ.rx_fifo() > 0:
            t_start = time.ticks_us()

            # --- Tight receive loop — drain pre-header ASAP ---
            for i in r1:
                pre[i] = MQ.get()

            # --- Status byte into FIFO ---
            # NOTE: do NOT call mq_ready() here. For LVM commands, Pico must
            # stay BUSY (D6 low on port $0F) until LOAD_TS has prepared the
            # data. LOAD_TS will explicitly set Y=ready after block_type is
            # in the FIFO. Calling mq_ready() here would let the Z80 exit
            # its WF_NPH poll prematurely and read stale OSR.
            mq_busy()        # ensure busy
            MQ.put(0x01)     # status byte into $0E FIFO

            iteration += 1
            print("\n[LOOP %d] @ %dus  RX trigger" % (iteration, t_start))
            print("[LOOP %d] pre = %s" % (iteration, list(pre)))
            print("[LOOP %d] interpreting:" % iteration)
            print("  pre[0] = 0x%02X (block_type expected: 0=header, 0xFF=data, 0xFE=PRINT)" % pre[0])
            print("  pre[1] = 0x%02X (TADDR: 0=SAVE, 1=LOAD, 2=VERIFY, 3=MERGE)" % pre[1])
            print("  pre[2] = 0x%02X (BANK: 0xFF=HOME)" % pre[2])
            print("  pre[3:5] = session_id 0x%02X%02X" % (pre[4], pre[3]))
            print("  pre[5:7] = mem_addr  0x%02X%02X" % (pre[6], pre[5]))
            print("  pre[7:9] = blk_len   %d" % (pre[7] + 256*pre[8]))
            print("  pre[9]   = 0x%02X (CRC)" % pre[9])

            # --- Dispatch ---
            if (pre[0] == 0 or pre[0] == 255) and pre[1] < 10:
                print("[LOOP %d] LVM LOAD path → calling LOAD_TS" % iteration)
                t_load = time.ticks_us()
                result = LOAD_TS(pre, MQ, TSP)
                t_load_end = time.ticks_us()
                # LOAD_TS returns (MQ, TSP, log_entries)
                MQ_new, TSP_new, log_str = result
                print("[LOOP %d] LOAD_TS returned in %dus" % (
                    iteration, time.ticks_diff(t_load_end, t_load)))
                print("[LOOP %d] TSP after: tap_idx=%d offset=%d totlen=%d" % (
                    iteration, TSP.tap_idx, TSP.offset, TSP.totlen))
                if log_str:
                    print("[LOOP %d] log_entries:\n%s" % (iteration, log_str))
                # Make sure ready is set for next round
                mq_ready()
            else:
                print("[LOOP %d] non-LVM pre — ignoring (this harness is LVM-only)" % iteration)
                # Drain anything else and stay ready
                while MQ.rx_fifo() > 0:
                    _ = MQ.get()
                mq_ready()

except KeyboardInterrupt:
    print("\n[STOP] interrupted by user")
    led.value(0)
