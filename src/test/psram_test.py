# PSRAM test for the TS-Pico v3 (U22, APS6404L on QMI CS1, GP47).
#
# Needs a firmware built with MICROPY_HW_ENABLE_PSRAM (mpconfigboard.cmake).
# Run at the REPL with the firmware stopped:
#   python3 tools/pico-serial.py break
#   python3 tools/pico-serial.py run --file src/test/psram_test.py
#
# 1. Was it found: the QMI's CS1 setup, GP47's function, the heap's size.
# 2. Fills every PSRAM block the heap will give with patterns tied to the
#    address (addr ^ seed, then its inverse, then walking ones), and reads
#    them back. A stuck or crossed address line shows as a block holding
#    another block's words; a data line as one bit wrong everywhere.
# 3. Reads the same words through the uncached alias (0x15xxxxxx), so the
#    data is known to be in the chip and not only in the XIP cache.

import gc
import machine
import time
import uctypes

QMI = 0x400D0000
M1 = QMI + 0x20     # M1_TIMING, RFMT, RCMD, WFMT, WCMD
IO_BANK0 = 0x40028000
PSRAM_BASE = 0x11000000
UNCACHED = 0x15000000 - 0x11000000

print("clock", machine.freq() // 1000000, "MHz")
names = ("TIMING", "RFMT", "RCMD", "WFMT", "WCMD")
for i, n in enumerate(names):
    print("QMI M1_%-6s %08x" % (n, machine.mem32[M1 + 4 * i]))
t = machine.mem32[M1]
clkdiv = t & 0xFF
rxdelay = (t >> 8) & 7
print("  clkdiv", clkdiv, "-> PSRAM clock", machine.freq() // max(clkdiv, 1) // 1000000, "MHz, rxdelay", rxdelay)
fn = machine.mem32[IO_BANK0 + 47 * 8 + 4] & 0x1F
print("GP47 function", fn, "(9 = XIP_CS1)" if fn == 9 else "(NOT XIP_CS1)")
gc.collect()
print("heap free", gc.mem_free(), "bytes")


@micropython.viper
def fill(a: uint, n: uint, seed: uint, inv: uint):
    p = ptr32(a)
    i = 0
    while i < int(n):
        v = (a + uint(i) * 4) ^ seed
        if inv:
            v = v ^ 0xFFFFFFFF
        p[i] = v
        i += 1


@micropython.viper
def check(a: uint, n: uint, seed: uint, inv: uint, base: uint) -> int:
    # a: where to read (cached or uncached); base: the cached address the
    # pattern was made from. Returns the number of bad words.
    p = ptr32(a)
    bad = 0
    i = 0
    while i < int(n):
        v = (base + uint(i) * 4) ^ seed
        if inv:
            v = v ^ 0xFFFFFFFF
        if uint(p[i]) != v:
            bad += 1
        i += 1
    return bad


@micropython.viper
def first_bad(a: uint, n: uint, seed: uint, inv: uint, base: uint) -> int:
    p = ptr32(a)
    i = 0
    while i < int(n):
        v = (base + uint(i) * 4) ^ seed
        if inv:
            v = v ^ 0xFFFFFFFF
        if uint(p[i]) != v:
            return i
        i += 1
    return -1


@micropython.viper
def walk(a: uint, n: uint) -> int:
    # Walking ones on each data bit, every 8th word, 32 passes.
    p = ptr32(a)
    bad = 0
    b = 0
    while b < 32:
        v = uint(1) << b
        i = 0
        while i < int(n):
            p[i] = v
            i += 8
        i = 0
        while i < int(n):
            if uint(p[i]) != v:
                bad += 1
            i += 8
        b += 1
    return bad


# Take PSRAM from the heap in 256 KB blocks until it is used up.
BLOCK = 256 * 1024
blocks = []
sram = []
while True:
    try:
        b = bytearray(BLOCK)
    except MemoryError:
        break
    a = uctypes.addressof(b)
    if PSRAM_BASE <= a < PSRAM_BASE + 0x1000000:
        blocks.append(b)
    else:
        sram.append(b)      # held so the next one comes from PSRAM
del sram
gc.collect()
if not blocks:
    print("FAIL: no heap block in PSRAM (not detected?)")
    raise SystemExit
addrs = sorted(uctypes.addressof(b) for b in blocks)
total = len(blocks) * BLOCK
print("testing", len(blocks), "blocks,", total // 1024, "KB, %08x..%08x" % (addrs[0], addrs[-1] + BLOCK))

words = BLOCK // 4
fails = 0
for seed, inv in ((0x5A3C96E1, 0), (0x5A3C96E1, 1), (0, 0)):
    t0 = time.ticks_ms()
    for a in addrs:
        fill(a, words, seed, inv)
    tw = time.ticks_diff(time.ticks_ms(), t0)
    t0 = time.ticks_ms()
    bad = 0
    for a in addrs:
        n = check(a, words, seed, inv, a)
        if n:
            i = first_bad(a, words, seed, inv, a)
            got = machine.mem32[a + 4 * i]
            want = (a + 4 * i) ^ seed ^ (0xFFFFFFFF if inv else 0)
            print("  %08x: %d bad words, first at %08x got %08x want %08x" % (a, n, a + 4 * i, got, want & 0xFFFFFFFF))
        bad += n
    tr = time.ticks_diff(time.ticks_ms(), t0)
    # Uncached reads of the same pattern.
    ubad = 0
    for a in addrs:
        ubad += check(a + UNCACHED, words, seed, inv, a)
    print("seed %08x inv %d: %d bad cached, %d bad uncached  (write %d KB/s, read+check %d KB/s)"
          % (seed, inv, bad, ubad, total * 1000 // 1024 // max(tw, 1), total * 1000 // 1024 // max(tr, 1)))
    fails += bad + ubad

wbad = 0
for a in addrs:
    wbad += walk(a, words)
print("walking ones:", wbad, "bad")
fails += wbad

print("PASS" if fails == 0 else "FAIL (%d bad words)" % fails)
del blocks
gc.collect()
