"""Protocol observer V5 — REAL LOAD response from pt.tap.

Sends real header content for the FIRST block in pt.tap. If the TS-2068
accepts it, you'll see "Bytes: <name>" on screen as it tries to LOAD the
data block. The data block phase will fail (we only handle one block in
this version), but the header acceptance is the milestone we're after.

Protocol per disassembly trace + v1.5 behavior:
  Pico writes (via $0E):
    1. 0x01 status (pre-loaded at startup)
    2. block_type byte (after Z80 OUTs ack, Z80's data loop starts here)
    3. 17 content bytes (HDTYPE + name + len + addr + hdvars)
    4. 1 CRC byte (parity, XOR of preceding 18 bytes)
    5. 0x01 final status (after Z80 OUTs computed CRC)

  Z80 reads (via $0E):
    a. status byte (= 0x01)
    b. (polls $0F, sees Y=ready)
    c. (OUTs block_type ack)
    d. data loop: DE+1 bytes (= flag + 17 content + 1 CRC)
    e. (OUTs Z80's computed CRC)
    f. (polls $0F, sees Y=ready)
    g. final status byte (= 0x01)

Setup order (matches V3-V4):
  1. Pin config + ROM_SM/BANK_SM IMMEDIATELY (TS-2068 boot capability)
  2. SD mount → copy pt.tap → unmount (avoid pin conflict during run)
  3. Pre-open /TMP/temp.tap, read first block prefix + content
  4. Start MQ, Y=READY, pre-load 0x01 status
  5. Wait for LOAD; respond; capture echo; write final status
"""

import os
import time
import gc
from rp2 import StateMachine, asm_pio, PIO
from machine import Pin, SPI, freq

freq(270_000_000)

from TS.tspico_io import TS_IO_DUAL, set_ctrl, sel_bank
from TS.sdcard import SDCard


# ============================================================================
# Pin setup + ROM_SM/BANK_SM (so TS-2068 can boot)
# ============================================================================

print("=" * 60)
print("PROTOCOL OBSERVER V5 — REAL header response from pt.tap")
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


# ============================================================================
# SD mount + copy pt.tap to /TMP
# ============================================================================

@asm_pio(autopull=True, pull_thresh=8)
def NULL_SM():
    nop()

SD_TAP_PATH = "/sd/TAP/pt.tap"
LOCAL_TAP   = "/TMP/temp.tap"

print("[SETUP] mounting SD")
null = StateMachine(0, NULL_SM, freq=15_000_000)
null.active(1); null.active(0)
U3_CS = Pin(28, Pin.OUT, Pin.PULL_UP)
D0 = Pin(2, Pin.IN); D1 = Pin(3, Pin.IN); D2 = Pin(4, Pin.IN)
spi = SPI(0, sck=D0, mosi=D1, miso=D2)
sd = SDCard(spi, U3_CS)
os.mount(sd, "/sd")

try: os.mkdir("/TMP")
except OSError: pass

src_size = os.stat(SD_TAP_PATH)[6]
print("[SETUP] copying %s (%d bytes) -> %s" % (SD_TAP_PATH, src_size, LOCAL_TAP))
with open(SD_TAP_PATH, "rb") as src, open(LOCAL_TAP, "wb") as dst:
    while True:
        buf = src.read(512)
        if not buf:
            break
        dst.write(buf)
print("[SETUP] copy done, unmounting SD")

os.umount("/sd")
spi.deinit()
Pin(28, Pin.OUT, Pin.PULL_UP).value(1)
for p in (2, 3, 4):
    Pin(p, Pin.OUT).value(0)


# ============================================================================
# Read first block from TAP file
# ============================================================================

arch = open(LOCAL_TAP, "rb")
prefix = bytearray(3)
arch.readinto(prefix)
blk_len  = prefix[0] + 256 * prefix[1]
blk_type = prefix[2]
print("[SETUP] TAP block 0: len=%d type=0x%02X" % (blk_len, blk_type))

# Read content + CRC (blk_len - 1 bytes after the type byte)
content = bytearray(blk_len - 1)
arch.readinto(content)
print("[SETUP] read %d bytes of content+CRC" % (blk_len - 1))

# Optional: decode header for sanity
if blk_type == 0x00 and len(content) >= 17:
    hdtype = content[0]
    name = bytes(content[1:11]).decode("ascii", "replace")
    blen = content[11] + 256 * content[12]
    addr = content[13] + 256 * content[14]
    print("[SETUP] header: HDTYPE=0x%02X name='%s' BLEN=%d ADDR=0x%04X CRC=0x%02X" % (
        hdtype, name, blen, addr, content[-1]))

# Verify the file's CRC matches XOR of (block_type + content[:-1])
calc_crc = blk_type
for b in content[:-1]:
    calc_crc ^= b
print("[SETUP] CRC: file=0x%02X computed=0x%02X  %s" % (
    content[-1], calc_crc, "OK" if calc_crc == content[-1] else "MISMATCH"))


# ============================================================================
# Start MQ, pre-load 0x01 status
# ============================================================================

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
print("[SETUP] TX FIFO pre-loaded with 0x01 status")


# ============================================================================
# Capture buffers + tight loop
# ============================================================================

CAP = 64
rx_buf = bytearray(CAP)
rx_t   = [0] * CAP
events = []           # list of (us, kind, value, note)

gc.collect()           # prime GC before critical phase

print("=" * 60)
print('READY. Power on TS-2068, then LOAD "".')
print('Expect: "Bytes: <name>" on TS-2068 screen, then data-block error.')
print("Ctrl-C in Thonny when transaction settles.")
print("=" * 60)

T0 = time.ticks_us()
rx_count   = 0
sent_data  = False
sent_final = False

mq_rx_fifo = MQ.rx_fifo
mq_get     = MQ.get
mq_put     = MQ.put
ticks_us   = time.ticks_us
ticks_diff = time.ticks_diff

try:
    while True:
        if mq_rx_fifo() > 0:
            raw = mq_get()
            t = ticks_diff(ticks_us(), T0)
            if rx_count < CAP:
                rx_buf[rx_count] = raw & 0xFF
                rx_t[rx_count]   = t
                rx_count += 1

                # After 10-byte pre-header captured: push real header response
                if rx_count == 10 and not sent_data:
                    # Push block_type + content (= blk_len bytes total)
                    mq_put(blk_type)
                    for b in content:
                        mq_put(b)   # blocks if TX full, paced by Z80 reads
                    events.append((ticks_diff(ticks_us(), T0),
                                   "tx_data", blk_len,
                                   "block_type + %d content+CRC" % len(content)))
                    sent_data = True

                # After 12 bytes total (10 pre-header + ack + Z80 CRC), send
                # final status to complete the transaction
                if rx_count == 12 and not sent_final:
                    mq_put(0x01)
                    events.append((ticks_diff(ticks_us(), T0),
                                   "tx_final", 0x01,
                                   "final status OK"))
                    sent_final = True

except KeyboardInterrupt:
    pass


# ============================================================================
# Dump
# ============================================================================

print("")
print("=" * 60)
print("RX captured: %d byte(s)" % rx_count)
print("=" * 60)

if rx_count > 0:
    print("%4s  %8s  %8s  0x%-2s  %3s  %s" % ("idx","us","delta","vl","asc","label"))
    print("-" * 70)
    pre_labels = ["BLOCK_TYPE","TADDR","BANK","SESS_LO","SESS_HI",
                  "MADDR_LO","MADDR_HI","BLEN_LO","BLEN_HI","CRC_TIMEX"]
    prev_t = 0
    for i in range(rx_count):
        t = rx_t[i]; delta = t - prev_t; prev_t = t
        v = rx_buf[i]
        asc = "'%s'" % chr(v) if 0x20 <= v < 0x7F else "   "
        if i < 10:
            lbl = pre_labels[i]
        elif i == 10:
            lbl = "block_type ack (expect 0x%02X)  %s" % (
                rx_buf[0],
                "MATCH" if v == rx_buf[0] else "DIFFERS")
        elif i == 11:
            lbl = "Z80 computed CRC (expect 0x%02X)  %s" % (
                content[-1],
                "MATCH" if v == content[-1] else "DIFFERS")
        else:
            lbl = "(post-final-status #%d)" % (i - 12)
        print("%4d  %8d  %8d  0x%02X  %3s  %s" % (i, t, delta, v, asc, lbl))

print("=" * 60)
print("Events:")
for ev in events:
    print("  [%dus] %s = 0x%02X  %s" % (ev[0], ev[1], ev[2], ev[3]))
print("=" * 60)

# CRC verifications
if rx_count >= 10:
    crc = 0
    for i in range(9): crc ^= rx_buf[i]
    print("Pre-header CRC:  computed=0x%02X  byte9=0x%02X  %s" % (
        crc, rx_buf[9], "MATCH" if crc == rx_buf[9] else "MISMATCH"))
if rx_count >= 12:
    print("Z80's computed CRC after data loop: 0x%02X (expected 0x%02X = %s)" % (
        rx_buf[11], content[-1],
        "MATCH" if rx_buf[11] == content[-1] else "MISMATCH"))
print("=" * 60)
print("If TS-2068 displayed 'Bytes: <name>' then errored on the data block,")
print("THE HEADER LOADED SUCCESSFULLY. Next step: V6 to handle data block too.")
print("=" * 60)

arch.close()
MQ.active(0)
print("MQ deactivated. ROM_SM/BANK_SM left running.")
