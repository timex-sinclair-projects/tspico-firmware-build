"""ZX bootstrap harness -- can the ORIGINAL slot-0 Spectrum ROM load from the
current (dual-port) firmware? Run on the Pico, from the REPL.

Why: a board upgraded from 1.1 / 1.5 to the new firmware still has its old
TS-2068 ROM, which can't talk to the new firmware. Every shipped flash image
(Pico-v14, v15, v15w) has the same Spectrum ROM in slot 0 (crc32 A8E12A24),
and `OUT 244,3` switches to it whatever the 2068 ROM is. If that ROM can
LOAD from the new firmware, it can load an updater that rewrites the ROMs.

That ROM has no handshake at all (see docs/rom-analysis/PATCH_ZX48_HANDSHAKE.md
section 1). Its LD-BYTES:

    OUT (0Eh),'L'    ; then a fixed ~0.94 ms (LD B,FFh / DJNZ)
    IN  A,(0Eh)      ; the flag -- whatever is in TX, or 00h if it's empty
    ~0.94 ms, then one IN every ~43 us for the length the ROM expects, then
    ~0.94 ms, then the CRC

So this harness doesn't answer 'L' at all: TX is kept full with the whole
tape as ONE stream -- flag, content, CRC of each block, back to back -- so
the next block's flag is already queued behind the last one's CRC when the
next 'L' comes. It only works if the ROM asks for exactly the blocks, in
order, with exactly their lengths -- true for a tape made for it.

Per byte the loop only tests TX room and puts (allocation-free; see
alloc_probe.py). Every word the Z80 writes is logged with the stream
position at that moment, and "TX empty while streaming" is counted: each one
is a byte the Z80 may have read as 00h.

OBSERVE = True streams nothing and just logs what the Z80 writes -- for
seeing what an old 2068 ROM sends to the new firmware.

Use: let the firmware boot, stop it (tools/pico-serial.py break), copy the
tape to /boottest.tap, then:
    tools/pico-serial.py run --timeout 3600 --file src/test/zx_bootstrap_harness.py
On the 2068: OUT 244,3 (the Spectrum ROM), LOAD "", ... then OUT 14,14 to
end the harness and print the log. Then tools/pico-serial.py softreset.
"""
import gc
import time
from array import array
from machine import Pin
from rp2 import StateMachine
from TS.tspico_io import TS_IO_DUAL, MQX

TAPE = "/boottest.tap"
OBSERVE = False
LOGN = 400

# ---- the tape as one stream: each block's flag + content + CRC -----------
raw = open(TAPE, "rb").read()
starts = []
parts = []
o = 0
while o + 2 <= len(raw):
    n = raw[o] | (raw[o + 1] << 8)
    starts.append(sum(len(p) for p in parts))
    parts.append(raw[o + 2:o + 2 + n])
    o += 2 + n
stream = bytearray(b"".join(parts)) if not OBSERVE else bytearray()
del raw, parts
N = len(stream)
print("stream: %d bytes in %d blocks, starting at %s" % (N, len(starts), starts))

# ---- the bus -----------------------------------------------------------------
MQ = StateMachine(0, TS_IO_DUAL, freq=30_000_000, out_base=Pin(2, Pin.OUT),
                  in_base=Pin(2, Pin.IN), jmp_pin=Pin(11),
                  sideset_base=Pin(12, Pin.OUT))
MQ.active(1)
MQX(MQ, "mov(y, invert(null))")
while MQ.rx_fifo():
    MQ.get()

log_w = array("H", bytes(2 * LOGN))     # word the Z80 wrote (bit 8 = port 0Fh)
log_i = array("I", bytes(4 * LOGN))     # stream bytes queued at that moment
log_t = array("I", bytes(4 * LOGN))     # ms since start
nlog = 0
dry = 0
dry_at = array("I", bytes(4 * 16))      # stream positions of the first dries
i = 0
txf = MQ.tx_fifo
rxf = MQ.rx_fifo
put = MQ.put
get = MQ.get
t0 = time.ticks_ms()
gc.collect()
print("harness ready: OUT 244,3 then LOAD \"\" ; OUT 14,14 to finish")

while True:
    if i < N:
        k = txf()
        if k < 4:
            if k == 0 and i > 4:
                if dry < 16:
                    dry_at[dry] = i
                dry += 1
            put(stream[i])
            i += 1
            continue
    if rxf():
        w = get()
        if nlog < LOGN:
            log_w[nlog] = w
            log_i[nlog] = i
            log_t[nlog] = time.ticks_diff(time.ticks_ms(), t0)
            nlog += 1
        if w == 14:
            break

# ---- the report --------------------------------------------------------------
print("streamed %d of %d bytes; TX ran empty %d times%s" % (
    i, N, dry, (" (first at %s)" % list(dry_at[:min(dry, 16)])) if dry else ""))
for k in range(nlog):
    w = log_w[k]
    blk = sum(1 for s in starts if s <= log_i[k]) - 1
    print("%7d ms  %s %02X %-3s  queued %6d (block %d)" % (
        log_t[k], "0F" if w & 0x100 else "0E", w & 0xFF,
        repr(chr(w & 0xFF)) if 32 <= (w & 0xFF) < 127 else "", log_i[k], blk))
