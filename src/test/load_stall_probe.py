"""LOAD stall probe -- run on the Pico from Thonny, no 2068 needed.

WHY THIS EXISTS (issue #51, stage 2 hardware test, 2026-09-26)
LOAD "" of nofile.tap's second program ("tc", a 16,096-byte data block)
failed with Report R. The watchdog log said "15772 of 16096 bytes
queued": the 2068 read all 16,096 bytes but the Pico only supplied
15,772. For ~324 byte-times (~24 ms at the ROM's ~74 us/byte) the Pico
stopped feeding the 4-deep TX FIFO, the Z80 read 0x00 from the empty
FIFO, and the block checksum failed. The ROM has no per-byte handshake,
so ANY Pico-side pause longer than ~300 us corrupts a LOAD.

This probe runs LOAD_TS's data-block loop -- one-byte readinto from the
cached nofile.tap handle -- with the same busy-waiting WATCHDOG thread on
core1, minus the PIO, and records the gap between consecutive bytes. If
the ~24 ms pause is in the read path (littlefs, threading, GC) it shows
up here with the file offset where it happened.

Run: stop main.py (Stop button in Thonny), then
    exec(open("/load_stall_probe.py").read())
Output: per pass, the slowest gaps with the byte index and file offset.
"""

import _thread
import gc
import time
from array import array

TAP = "/assets/nofile.tap"
OFFSET = 5014 + 2          # "tc" data block: skip the 2-byte TAP length
COUNT = 16096 - 1          # LOAD_TS streams totbytes - 1 after the flag
PASSES = 3
SLOW_US = 300              # longer than the TX FIFO covers (4 x ~74 us)

gaps = array("H", bytes(2 * COUNT))
spin = [False]


def watchdog_like(secs):
    """Same shape as WATCHDOG's wait: a tight ticks_diff loop on core1."""
    secs = secs * 1_000_000
    t0 = time.ticks_us()
    while time.ticks_diff(time.ticks_us(), t0) < secs:
        if not spin[0]:
            break


def one_pass(arch, with_thread):
    arch.seek(OFFSET)
    el = bytearray(1)
    rd = arch.readinto
    tick = time.ticks_us
    diff = time.ticks_diff
    if with_thread:
        spin[0] = True
        _thread.start_new_thread(watchdog_like, (10,))
        time.sleep_ms(5)
    t_prev = tick()
    t_start = t_prev
    for i in range(COUNT):
        rd(el)
        t = tick()
        d = diff(t, t_prev)
        gaps[i] = d if d < 65535 else 65535
        t_prev = t
    total = diff(tick(), t_start)
    spin[0] = False
    time.sleep_ms(20)                      # let core1 finish
    return total


def report(label, total):
    slow = [(gaps[i], i) for i in range(COUNT) if gaps[i] >= SLOW_US]
    slow.sort(reverse=True)
    worst = max(gaps)
    print("%s: %d bytes in %d ms (%.1f us/byte), worst gap %d us, %d gaps >= %d us"
          % (label, COUNT, total // 1000, total / COUNT, worst, len(slow), SLOW_US))
    for g, i in slow[:10]:
        print("    %6d us before byte %5d (file offset %d)" % (g, i, OFFSET + i))


def main():
    arch = open(TAP, "rb")
    try:
        for p in range(PASSES):
            gc.collect()
            report("pass %d, no thread     " % (p + 1), one_pass(arch, False))
            gc.collect()
            report("pass %d, watchdog core1" % (p + 1), one_pass(arch, True))
        t = time.ticks_us()
        gc.collect()
        print("for scale: one gc.collect() takes %d us"
              % time.ticks_diff(time.ticks_us(), t))
    finally:
        spin[0] = False
        arch.close()


main()
