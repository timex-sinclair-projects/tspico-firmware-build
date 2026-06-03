"""LVM LOAD test harness V3 — match v1.5 architecture, dual-port style.

Architecture:
  PIO TS_IO_DUAL with pull(noblock) on $0E (matches v1.5 timing model).
  $0F decoded separately, returns Y register (decoupled from FIFO).

  Y = BUSY (0) initially. When Pico has data ready, Y = READY (0xFFFFFFFF).
  Z80 polls $0F bit 6 — 2.8ms WF_NPH window per spec page 2.

Mirrors v1.5 LOAD_TS byte sequence, minus the 0x40 (replaced by Y=READY):
  v1.5 single-port writes: 0x01 + 0x40 + block_type + (totbytes-1) bytes
  dual-port  writes:       0x01 +        block_type + (totbytes-1) bytes

  The Z80 ROM does:
    - reads $0E status (gets 0x01)
    - polls $0F (gets Y; must be 0xFF to exit poll)
    - reads $0E content N times (gets block_type + content + CRC)
    - OUTs block_type ack + computed CRC
    - polls $0F + reads $0E for final status (handled by next-iter pre-load)

Pico flow per LOAD:
  1. Drain pre[] (10 bytes)
  2. wrt(0x01) — pre-load status byte ASAP (Z80 reads $0E status soon)
  3. Read TAP block from file
  4. wrt(block_type) — first content byte of response
  5. Stream (totbytes-1) more bytes (TX FIFO 4-deep paces via Z80 reads)
  6. mov(y, ~null) — Y=READY (Z80's $0F poll unblocks)
  7. Drain Z80's 2-byte echo (block_type ack + computed CRC)
  8. wrt(0x01) — for next iteration's status pre-load (and Z80's final status)
  9. set(y, 0) — Y=BUSY for next iter's poll

Critical timing: steps 2-6 must complete within ~2.8ms from RX detection.
Steps 5 inherent pacing: MQ.put blocks when FIFO full, but Z80 starts reading
as soon as we set Y=READY. So step 6 needs FIFO already partially seeded.
"""

import os
import time
import gc
from rp2 import StateMachine, asm_pio, PIO
from machine import Pin, SPI, freq

freq(270_000_000)

from TS.tspico_io import set_ctrl, sel_bank
from TS.sdcard import SDCard


# ============================================================================
# PIO: dual-port with pull(noblock) — matches v1.5 timing semantics
# ============================================================================

@asm_pio(
    sideset_init=PIO.OUT_HIGH,
    out_init=(PIO.OUT_LOW,) * 8,
    out_shiftdir=PIO.SHIFT_RIGHT,
    in_shiftdir=PIO.SHIFT_LEFT,
)
def TS_IO_DUAL():
    wait(0, gpio, 14)       .side(1)
    jmp(pin, "z80_out")     .side(1)

    # Z80 IN — decode A0 to choose port
    in_(pins, 9)            .side(0)
    mov(osr, isr)           .side(0)
    mov(isr, null)          .side(0)
    out(null, 8)            .side(0)
    out(x, 1)               .side(0)
    jmp(not_x, "rd_data")   .side(0)

    # $0F (A0=1): drive Y onto bus
    mov(osr, y)             .side(0)
    out(pins, 8)            .side(0)
    jmp("fin")              .side(0)

    # $0E (A0=0): drive TX FIFO byte (or stale OSR if FIFO empty)
    label("rd_data")
    pull(noblock)           .side(0)
    out(pins, 8)            .side(0)
    jmp("fin")              .side(0)

    # Z80 OUT — capture
    label("z80_out")
    nop()                   .side(0)
    in_(pins, 9)            .side(0) [2]
    push(noblock)           .side(0)

    label("fin")
    wait(1, gpio, 14)       .side(0)
    mov(null, osr)          .side(1)


@asm_pio(autopull=True, pull_thresh=8)
def NULL_SM():
    nop()


# ============================================================================
# Constants
# ============================================================================

SD_TAP_PATH = "/sd/TAP/pt.tap"
LOCAL_TAP   = "/TMP/temp.tap"
ROM_SM_VAL  = 0x0A
BANK_SM_VAL = 0x01

STAT_OK       = 0x01
STAT_TAPE_ERR = 0x02


# ============================================================================
# Board pins
# ============================================================================

print("=" * 60)
print("LVM TEST HARNESS V3 — v1.5-style timing, dual-port Y")
print("=" * 60)

print("\n[SETUP] configuring board pins (matching production main.py)")
U6_EN   = Pin(12, Pin.OUT, Pin.PULL_UP)
WAIT    = Pin(14, Pin.OUT, Pin.PULL_DOWN)
U10_ENA = Pin(19, Pin.OUT, Pin.PULL_UP)
U13_ENA = Pin(20, Pin.OUT, Pin.PULL_UP)
BE      = Pin(21, Pin.OUT, Pin.PULL_UP)
ROSCS   = Pin(26, Pin.IN,  Pin.PULL_DOWN)   # ROM_SM jmp_pin (input!) — must
                                            # be pulled DOWN. Without this it
                                            # floats and ROM_SM never decodes
                                            # the ROM read window correctly.
U10_WE  = Pin(27, Pin.OUT, Pin.PULL_UP)
for p in (U6_EN, WAIT, U10_ENA, U13_ENA, BE, U10_WE):
    p.value(1)


# ============================================================================
# SD: mount, copy, unmount
# ============================================================================

def sd_copy_test_file():
    print("[SETUP] activating SD")
    null = StateMachine(0, NULL_SM, freq=15_000_000)
    null.active(1)
    null.active(0)

    U3_CS = Pin(28, Pin.OUT, Pin.PULL_UP)
    D0 = Pin(2, Pin.IN); D1 = Pin(3, Pin.IN); D2 = Pin(4, Pin.IN)

    spi = SPI(0, sck=D0, mosi=D1, miso=D2)
    sd = SDCard(spi, U3_CS)
    os.mount(sd, "/sd")
    print("[SETUP] SD mounted")

    try:
        os.mkdir("/TMP")
    except OSError:
        pass

    src_size = os.stat(SD_TAP_PATH)[6]
    print("[SETUP] copying %s (%d bytes) -> %s" % (SD_TAP_PATH, src_size, LOCAL_TAP))
    with open(SD_TAP_PATH, "rb") as src, open(LOCAL_TAP, "wb") as dst:
        copied = 0
        while True:
            buf = src.read(512)
            if not buf:
                break
            dst.write(buf)
            copied += len(buf)
    print("[SETUP] copied %d bytes" % copied)

    try: os.umount("/sd")
    except: pass
    Pin(28, Pin.OUT, Pin.PULL_UP).value(1)
    for p in (2, 3, 4):
        Pin(p, Pin.OUT).value(0)
    return src_size


# ============================================================================
# ROM/BANK SMs
# ============================================================================

def start_rom_bank():
    print("[SETUP] ROM_SM (set_ctrl @ 150MHz, /BE GPIO 21)")
    rom_sm = StateMachine(4, set_ctrl, freq=150_000_000,
                          in_base=Pin(0, Pin.IN), jmp_pin=Pin(26),
                          set_base=Pin(21, Pin.OUT),
                          out_base=Pin(19, Pin.OUT))
    rom_sm.active(1)
    print("[SETUP] BANK_SM (sel_bank @ 150MHz)")
    bank_sm = StateMachine(5, sel_bank, freq=150_000_000,
                           jmp_pin=Pin(26),
                           out_base=Pin(15, Pin.OUT))
    bank_sm.active(1)
    rom_sm.put(ROM_SM_VAL)
    bank_sm.put(BANK_SM_VAL)
    print("[SETUP] ROM_SM=0x%02X bank_sm=0x%02X" % (ROM_SM_VAL, BANK_SM_VAL))
    return rom_sm, bank_sm


# ============================================================================
# MQ — TS_IO_DUAL, Y starts BUSY
# ============================================================================

def start_mq():
    print("[SETUP] MQ (TS_IO_DUAL @ 30MHz)")
    sm = StateMachine(0, TS_IO_DUAL, freq=30_000_000,
                      out_base=Pin(2, Pin.OUT),
                      in_base=Pin(2, Pin.IN),
                      jmp_pin=Pin(11),
                      sideset_base=Pin(12, Pin.OUT))
    sm.active(1)
    # Y = 0xFFFFFFFF → port $0F always returns 0xFF → D6=1=ready.
    # MUST be ready at idle: TS-2068 LOAD command does a WF_NPH probe on
    # $0F BEFORE OUT-ing pre-header. Y=0 at idle → instant Report J.
    sm.exec("mov(y, invert(null))")
    print("[SETUP] MQ active. Y=READY (always)")
    return sm


def flush_boot_noise(MQ, ms=500):
    print("[SETUP] flushing %dms" % ms)
    n = 0
    last = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), last) < ms:
        if MQ.rx_fifo() > 0:
            _ = MQ.get()
            n += 1
            last = time.ticks_ms()
    print("[SETUP] flushed %d byte(s)" % n)


# ============================================================================
# CLEAN_LOAD — v1.5 byte sequence, dual-port Y handshake
# ============================================================================

def CLEAN_LOAD(pre, MQ, arch, offset, dbg):
    """One block. Matches v1.5 byte count: 0x01 + block_type + (totbytes-1).

    Y starts BUSY when called (set BUSY at startup or end of previous iter).
    Z80 polls $0F sees BUSY → waits up to 2.8ms.
    Pico fills TX FIFO with response, then sets Y=READY.
    """
    # Step 1: write 0x01 status IMMEDIATELY. Z80's first $0E read after
    # OUT-ing pre[] gets this. (pull(noblock) means stale OSR if empty.)
    MQ.put(STAT_OK)

    # Step 2: read TAP block prefix (3 bytes from pre-opened file)
    arch.seek(offset)
    prefix = bytearray(3)
    arch.readinto(prefix)
    blk_len  = prefix[0] + 256 * prefix[1]
    blk_type = prefix[2]

    # Step 3: validate
    if pre[0] != blk_type:
        # Mismatch — overwrite the OK we just put (FIFO already has 0x01;
        # adding 0x02 leaves Z80 reading 0x01 then 0x02. Caller decides.)
        dbg.append("  MISMATCH pre[0]=0x%02X != type=0x%02X" % (pre[0], blk_type))
        MQ.put(STAT_TAPE_ERR)
        # Set Y=READY so Z80 unblocks, sees the error
        MQ.exec("mov(y, invert(null))")
        return STAT_TAPE_ERR, offset

    # Step 4: read entire block into hdr buffer (for type=header) or stream
    # later (for type=data). Header blocks are tiny (~20 bytes) so buffering
    # is fine. Data blocks could be large, stream byte-by-byte.
    if blk_type == 0x00:
        hdr = bytearray(blk_len - 1)
        arch.readinto(hdr)
        # Optional: autorun-bit patch (v1.5 does this for non-autorun progs)
        if hdr[0] == 0x00 and hdr[14] >= 0x80:
            hdr[14] = 0x28
            hdr[17] = hdr[17] ^ 0x80 ^ hdr[14]

    # Step 5: write block_type — FIFO now has [0x01, block_type]
    MQ.put(blk_type)

    # Y stays READY (set once at startup). Z80's $0F polls always succeed
    # immediately. Pico paces data flow via TX FIFO blocking on .put() when
    # full — Z80's $0E reads drain the FIFO at its own speed.

    # Step 7: stream content+CRC bytes. For header, from hdr buffer.
    # For data, from file. MQ.put blocks when TX full; Z80 paces via reads.
    if blk_type == 0x00:
        for b in hdr:
            MQ.put(b)
    else:
        el = bytearray(1)
        for _ in range(blk_len - 1):
            arch.readinto(el)
            MQ.put(el[0])

    # Step 8: drain Z80's two-byte echo (block_type ack + computed CRC)
    blq_ack = MQ.get() & 0xFF
    crc_z   = MQ.get() & 0xFF
    dbg.append("  Z80 echo: ack=0x%02X crc=0x%02X" % (blq_ack, crc_z))

    # Step 9: pre-load 0x01 for next iteration's status (and serves as final
    # status if Z80 reads one more $0E in this transaction).
    MQ.put(STAT_OK)

    # Y stays READY for next iteration's pre-LOAD WF_NPH probe.
    return STAT_OK, offset + blk_len + 2


# ============================================================================
# Main
# ============================================================================

print("\n--- SETUP PHASE ---")
gc.collect()

# CRITICAL: start ROM_SM/BANK_SM FIRST. The TS-2068's ROM is in the
# TS-Pico's external flash; /BE must be actively routed by ROM_SM for the
# TS-2068 to boot at all. If we delay ROM_SM until after SD ops (~5s), the
# TS-2068 cannot boot during that window.
# Pin usage: ROM_SM uses GPIO 19/20/21/22/26, BANK_SM uses GPIO 15/26.
# SD uses GPIO 2/3/4/28 — no conflict, safe to start ROM_SM first.
rom_sm, bank_sm = start_rom_bank()

totlen = sd_copy_test_file()
MQ = start_mq()
flush_boot_noise(MQ, 500)

arch = open(LOCAL_TAP, "rb")
print("[SETUP] pre-opened %s (totlen=%d)" % (LOCAL_TAP, totlen))

print("")
print("=" * 60)
print('READY. Type LOAD "" on the TS-2068 now.')
print("=" * 60)

pre = bytearray(10)
r10 = range(10)
offset = 0
iteration = 0
last_heartbeat = time.ticks_ms()

try:
    while True:
        now = time.ticks_ms()
        if time.ticks_diff(now, last_heartbeat) > 3000:
            print("[HB] alive  rx=%d tx=%d  iter=%d  offset=%d" % (
                MQ.rx_fifo(), MQ.tx_fifo(), iteration, offset))
            last_heartbeat = now

        if MQ.rx_fifo() > 0:
            t_start = time.ticks_us()

            # Drain pre[] — 10 bytes
            for i in r10:
                pre[i] = MQ.get() & 0xFF

            iteration += 1
            dbg = []
            dbg.append("\n[L %d] @%dus pre=%s" % (
                iteration, t_start, list(pre)))
            dbg.append("  pre[0]=0x%02X (block_type)  pre[1]=0x%02X (TADDR)" % (
                pre[0], pre[1]))

            if (pre[0] == 0x00 or pre[0] == 0xFF) and pre[1] < 10:
                t_call = time.ticks_us()
                status, new_offset = CLEAN_LOAD(pre, MQ, arch, offset, dbg)
                t_done = time.ticks_us()
                dbg.append("[L %d] returned status=0x%02X offset %d->%d in %dus" % (
                    iteration, status, offset, new_offset,
                    time.ticks_diff(t_done, t_call)))
                if status == STAT_OK:
                    offset = new_offset
            else:
                dbg.append("[L %d] non-LVM pre — draining" % iteration)
                while MQ.rx_fifo() > 0:
                    _ = MQ.get()

            for line in dbg:
                print(line)

except KeyboardInterrupt:
    print("\n[STOP] interrupted")
    arch.close()
    MQ.active(0)
    # Leave rom_sm and bank_sm RUNNING — they hold /BE so the TS-2068
    # can keep reading its ROM (which lives in TS-Pico external flash).
    # Killing them here would freeze the TS-2068.
    print("=" * 60)
    print("[STOP] ROM_SM and BANK_SM left active so TS-2068 keeps booting")
