"""SAVE observer — captures everything the Z80 sends during SAVE.

Use:
  1. Boot Pico, run this script via Thonny.
  2. Power on TS-2068 (boots via EXROM).
  3. Type a small program on TS-2068:
       10 PRINT "HELLO"
       20 GOTO 10
  4. Type:  SAVE "test"
  5. Wait for the SAVE to complete on TS-2068.
  6. Ctrl-C in Thonny → see captured bytes + decoded fields.

What we expect:
  Phase 1: Z80 OUTs 10-byte pre-header (TADDR=0x00 = SAVE).
           Pre-loaded 0x01 status drained when Z80 reads $0E.
  Phase 2: Z80 OUTs 21-byte HEADER block:
             [0]    block_type (0x00 = header)
             [1,2]  session ID (LE)
             [3]    HDTYPE (0x00=BASIC, 0x01=numbers, 0x02=chars, 0x03=code)
             [4-13] filename (10 ASCII chars)
             [14,15] BLEN (LE) — size of upcoming data block
             [16,17] memory address (LE)
             [18,19] HDVARS (LE)
             [20]   CRC (XOR of preceding bytes)
           Pico writes 0x01 after capturing all 21.
  Phase 3: Z80 OUTs DATA block of size (BLEN+4):
             [0]    block_type (0xFF = data)
             [1,2]  session ID (LE)
             [3..N+2] data bytes (N=BLEN)
             [N+3]  CRC
           Pico writes 0x01 final status + 0x01 next-iter pre-load.

Optional: at the end, save the reconstructed TAP block to /TMP/saved.tap
so you can inspect it (or copy to SD and try LOADing it back).
"""

import os
import time
import gc
from rp2 import StateMachine, asm_pio, PIO
from machine import Pin, freq

freq(270_000_000)

from TS.tspico_io import TS_IO_DUAL, set_ctrl, sel_bank


# ============================================================================
# Hardware setup — same as other observers
# ============================================================================

print("=" * 60)
print("SAVE OBSERVER — capture Z80 SAVE protocol")
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

n = 0
last = time.ticks_ms()
while time.ticks_diff(time.ticks_ms(), last) < 300:
    if MQ.rx_fifo() > 0:
        MQ.get()
        n += 1
        last = time.ticks_ms()
print("[SETUP] flushed %d boot byte(s)" % n)

MQ.put(0x01)
print("[SETUP] TX FIFO pre-loaded with 0x01 (initial status)")


# ============================================================================
# Big buffer for the captured data block (max 65535 + slack)
# ============================================================================

PRE_LEN = 10
HDR_LEN = 21
DATA_MAX = 65540   # max data block size; pre-allocated to avoid GC

pre_buf  = bytearray(PRE_LEN)
hdr_buf  = bytearray(HDR_LEN)
data_buf = bytearray(DATA_MAX)

events = []      # high-level phase events for the dump


# ============================================================================
# Phase-aware capture loop
# ============================================================================

print("=" * 60)
print('READY. On the TS-2068, type a program then SAVE "name".')
print("Pico will capture all bytes Z80 sends, write status between phases,")
print("then dump everything when you hit Ctrl-C in Thonny.")
print("=" * 60)

T0 = time.ticks_us()
phase = "wait_pre"
pre_count = 0
hdr_count = 0
data_count = 0
data_expected = 0
done_iters = 0    # full SAVE transactions completed

mq_rx_fifo = MQ.rx_fifo
mq_get     = MQ.get
mq_put     = MQ.put
ticks_us   = time.ticks_us
ticks_diff = time.ticks_diff

gc.collect()

try:
    while True:
        if mq_rx_fifo() > 0:
            raw = mq_get()
            t   = ticks_diff(ticks_us(), T0)
            byt = raw & 0xFF

            if phase == "wait_pre":
                pre_buf[pre_count] = byt
                pre_count += 1
                if pre_count == PRE_LEN:
                    events.append((t, "pre_done",
                                   "10-byte pre-header captured"))
                    phase = "wait_hdr"
                    hdr_count = 0

            elif phase == "wait_hdr":
                hdr_buf[hdr_count] = byt
                hdr_count += 1
                if hdr_count == HDR_LEN:
                    events.append((t, "hdr_done",
                                   "21-byte header captured"))
                    # BLEN at hdr[14:16] gives the upcoming data block size
                    blen = hdr_buf[14] + 256 * hdr_buf[15]
                    data_expected = blen + 4   # type + 2 sess + N + crc
                    events.append((t, "data_size",
                                   "expecting %d data bytes (BLEN=%d)" % (
                                       data_expected, blen)))
                    # Send mid-status so Z80 proceeds to data phase
                    mq_put(0x01)
                    events.append((ticks_diff(ticks_us(), T0), "tx_mid_status",
                                   "wrote 0x01 between header and data"))
                    phase = "wait_data"
                    data_count = 0

            elif phase == "wait_data":
                if data_count < DATA_MAX:
                    data_buf[data_count] = byt
                data_count += 1
                if data_count == data_expected:
                    events.append((t, "data_done",
                                   "%d data bytes captured" % data_count))
                    # Send final status + next-iter pre-load
                    mq_put(0x01)
                    mq_put(0x01)
                    events.append((ticks_diff(ticks_us(), T0), "tx_final",
                                   "wrote 0x01 final + 0x01 pre-load"))
                    done_iters += 1
                    # Reset for next SAVE
                    phase = "wait_pre"
                    pre_count = 0

except KeyboardInterrupt:
    pass


# ============================================================================
# Dump
# ============================================================================

print("")
print("=" * 60)
print("Completed SAVE transactions: %d" % done_iters)
print("Current phase at exit: %s" % phase)
if phase == "wait_pre":
    print("  partial pre-header: %d/%d bytes" % (pre_count, PRE_LEN))
elif phase == "wait_hdr":
    print("  partial header: %d/%d bytes" % (hdr_count, HDR_LEN))
elif phase == "wait_data":
    print("  partial data: %d/%d bytes" % (data_count, data_expected))
print("=" * 60)
print("\n--- EVENTS ---")
for t, kind, note in events:
    print("[%9dus] %-15s %s" % (t, kind, note))


# ----------------------------------------------------------------------------
# Decode pre-header
# ----------------------------------------------------------------------------
if pre_count == PRE_LEN:
    print("\n--- PRE-HEADER (10 bytes) ---")
    pre_crc = 0
    for i in range(9):
        pre_crc ^= pre_buf[i]
    fields = [
        ("BLOCK_TYPE", pre_buf[0], "0x00=header, 0xFF=data"),
        ("TADDR",      pre_buf[1], "0=SAVE, 1=LOAD, 2=VERIFY, 3=MERGE"),
        ("BANK",       pre_buf[2], "0xFF=HOME"),
        ("SESS_LO",    pre_buf[3], ""),
        ("SESS_HI",    pre_buf[4], ""),
        ("MADDR_LO",   pre_buf[5], ""),
        ("MADDR_HI",   pre_buf[6], ""),
        ("BLEN_LO",    pre_buf[7], ""),
        ("BLEN_HI",    pre_buf[8], ""),
        ("CRC",        pre_buf[9],
            "XOR of [0..8] = 0x%02X  %s" % (
                pre_crc,
                "MATCH" if pre_crc == pre_buf[9] else "MISMATCH")),
    ]
    for name, val, note in fields:
        asc = "'%s'" % chr(val) if 0x20 <= val < 0x7F else "   "
        print("  %-10s = 0x%02X %3s  %s" % (name, val, asc, note))
    print("  → TADDR=%d → %s" % (pre_buf[1],
        ["SAVE","LOAD","VERIFY","MERGE","COPY","LPRINT"][pre_buf[1]] if pre_buf[1]<6 else "?"))
    addr = pre_buf[5] + 256*pre_buf[6]
    blen = pre_buf[7] + 256*pre_buf[8]
    print("  → MEMORY_ADDR = 0x%04X (%d)" % (addr, addr))
    print("  → BLOCK_LEN   = %d bytes" % blen)


# ----------------------------------------------------------------------------
# Decode header block
# ----------------------------------------------------------------------------
if hdr_count == HDR_LEN:
    print("\n--- HEADER BLOCK (21 bytes) ---")
    # Hex dump
    print("  hex: " + " ".join("%02X" % b for b in hdr_buf))
    # Decoded fields
    name = bytes(hdr_buf[4:14]).decode("ascii", "replace")
    blen = hdr_buf[14] + 256 * hdr_buf[15]
    addr = hdr_buf[16] + 256 * hdr_buf[17]
    hdvars = hdr_buf[18] + 256 * hdr_buf[19]
    hdtypes = {0:"BASIC PROGRAM", 1:"NUMBER ARRAY",
               2:"CHARACTER ARRAY", 3:"CODE/SCREEN"}
    print("  block_type  = 0x%02X" % hdr_buf[0])
    print("  session     = 0x%02X%02X" % (hdr_buf[2], hdr_buf[1]))
    print("  HDTYPE      = 0x%02X (%s)" % (
        hdr_buf[3], hdtypes.get(hdr_buf[3], "?")))
    print("  filename    = '%s'" % name)
    print("  BLEN (data) = %d bytes" % blen)
    print("  ADDR        = 0x%04X" % addr)
    print("  HDVARS      = 0x%04X" % hdvars)
    print("  CRC byte    = 0x%02X" % hdr_buf[20])
    # TPI CRC: XOR of [0] + [3..19] (skip 2 session bytes at [1],[2])
    hdr_crc = hdr_buf[0]
    for i in range(3, 20):
        hdr_crc ^= hdr_buf[i]
    print("  CRC verify  = 0x%02X  %s  (XOR of [0] + [3..19], session skipped)" % (
        hdr_crc,
        "MATCH" if hdr_crc == hdr_buf[20] else "MISMATCH"))


# ----------------------------------------------------------------------------
# Data block summary
# ----------------------------------------------------------------------------
if data_count > 0:
    print("\n--- DATA BLOCK (%d bytes captured, %d expected) ---" % (
        data_count, data_expected))
    # Show first 32 and last 16 bytes
    n_show = min(data_count, 32)
    print("  first %d bytes: %s" % (n_show,
        " ".join("%02X" % data_buf[i] for i in range(n_show))))
    if data_count > 32:
        n_tail = min(16, data_count)
        start = data_count - n_tail
        print("  last %d bytes:  %s" % (n_tail,
            " ".join("%02X" % data_buf[i] for i in range(start, data_count))))
    if data_count == data_expected and data_count >= 4:
        print("  block_type  = 0x%02X (expected 0xFF)" % data_buf[0])
        print("  session     = 0x%02X%02X" % (data_buf[2], data_buf[1]))
        print("  CRC byte    = 0x%02X" % data_buf[data_count - 1])
        # The TPI protocol's CRC formula SKIPS the 2 session-ID bytes at
        # [1] and [2] — those are TPI extensions, not part of the original
        # ZX tape CRC. Skip them when verifying.
        crc = data_buf[0]                    # block_type
        for i in range(3, data_count - 1):   # data bytes only, no session, no CRC
            crc ^= data_buf[i]
        print("  CRC verify  = 0x%02X  %s  (XOR of [0] + [3..%d], session skipped)" % (
            crc,
            "MATCH" if crc == data_buf[data_count-1] else "MISMATCH",
            data_count - 2))


# ----------------------------------------------------------------------------
# Optional: write reconstructed TAP block to /TMP for inspection
# ----------------------------------------------------------------------------
if done_iters >= 1 and hdr_count == HDR_LEN and data_count == data_expected:
    try:
        os.mkdir("/TMP")
    except OSError:
        pass
    out_path = "/TMP/saved.tap"
    print("\n--- Writing reconstructed TAP to %s ---" % out_path)
    # TAP format: each block is [len_lo, len_hi, type, content..., crc]
    # The header block: 19 bytes (1 type + 17 content + 1 CRC) — but Z80
    # sent us 21 bytes (with 2 session-ID bytes inserted between type and
    # HDTYPE). We need to strip those session bytes for a valid TAP.
    # TAP header = type(1) + HDTYPE(1) + name(10) + BLEN(2) + ADDR(2) + HDVARS(2) + CRC(1) = 19
    # SAVE'd header = type(1) + sess(2) + HDTYPE(1) + name(10) + BLEN(2) + ADDR(2) + HDVARS(2) + CRC(1) = 21
    tap_hdr_content = bytearray()
    tap_hdr_content.append(hdr_buf[0])              # block_type
    tap_hdr_content.extend(hdr_buf[3:20])           # HDTYPE..HDVARS (skip session)
    # Recompute CRC on the stripped 18 bytes (block_type + 17 content)
    crc = 0
    for b in tap_hdr_content:
        crc ^= b
    tap_hdr_content.append(crc)                     # parity byte
    tap_hdr_len = len(tap_hdr_content)              # = 19
    # Data block: same 2-session-byte stripping
    tap_data_content = bytearray()
    tap_data_content.append(data_buf[0])            # block_type 0xFF
    tap_data_content.extend(data_buf[3:data_count-1])
    crc = 0
    for b in tap_data_content:
        crc ^= b
    tap_data_content.append(crc)
    tap_data_len = len(tap_data_content)

    with open(out_path, "wb") as f:
        f.write(bytes([tap_hdr_len & 0xFF, (tap_hdr_len >> 8) & 0xFF]))
        f.write(tap_hdr_content)
        f.write(bytes([tap_data_len & 0xFF, (tap_data_len >> 8) & 0xFF]))
        f.write(tap_data_content)
    sz = os.stat(out_path)[6]
    print("  wrote %d bytes (header block %d, data block %d)" % (
        sz, tap_hdr_len, tap_data_len))
    print("  copy this off the Pico via Thonny to inspect / re-LOAD")

print("=" * 60)
MQ.active(0)
print("MQ deactivated. ROM_SM/BANK_SM left running.")
