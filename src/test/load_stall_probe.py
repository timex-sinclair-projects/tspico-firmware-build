"""LOAD stall probe -- run on the Pico from Thonny, no 2068 needed.

WHY THIS EXISTS (issue #51, stage 2 hardware test, 2026-09-26)
LOAD "" of nofile.tap's second program ("tc", a 16,096-byte data block)
failed with Report R. The watchdog log said "15772 of 16096 bytes
queued": the 2068 read all 16,096 bytes but the Pico only supplied
15,772, so ~324 of the 2068's reads found the TX FIFO empty and got 0x00.

The ROM's LOAD byte loop (EXROM 19DDh..19F4h, 1.8b) has NO handshake:
IN A,(0Eh) every 178 T-states = 50.5 us at 3.528 MHz. With a 4-deep TX
FIFO the Pico can fall behind by only ~150-200 us before the Z80 reads an
empty FIFO. Run 1 of this probe showed the one-byte file read alone has
gaps of 133-193 us -- right at that limit.

This version times LOAD_TS's per-byte loop two ways -- one-byte readinto
from the file (what LOAD_TS does) and indexing a bytearray already in RAM
-- for both nofile.tap data blocks, then replays each timing trace
against a simulated Z80 reading every 50.5 us from a 4-deep FIFO and
counts the reads that would have found it empty. Any count > 0 = Report R.

Run: stop main.py (Stop button in Thonny), then
    exec(open("/load_stall_probe.py").read())
"""

import gc
import time
from array import array

TAP = "/assets/nofile.tap"
# (name, file offset of the first byte AFTER the flag, bytes after the flag)
# LOAD_TS puts the flag itself, then streams totbytes - 1 bytes from the file.
BLOCKS = (("No file! (4970)", 21 + 3, 4970 - 1),
          ("tc (16096)", 5014 + 3, 16096 - 1))
Z80_US = 50.5              # 178 T-states per byte at 3.528 MHz
DEPTH = 4                  # PIO TX FIFO
EXTRA_US = (0, 10, 25)     # txf() / TX_ROOM() / put() cost the probe leaves out
PASSES = 3

MAXN = 16096
gaps = array("H", bytes(2 * MAXN))
ram = bytearray(MAXN)


def time_file(arch, off, n):
    arch.seek(off)
    el = bytearray(1)
    rd = arch.readinto
    tick = time.ticks_us
    diff = time.ticks_diff
    t_prev = tick()
    for i in range(n):
        rd(el)
        t = tick()
        d = diff(t, t_prev)
        gaps[i] = d if d < 65535 else 65535
        t_prev = t


def time_ram(n):
    tick = time.ticks_us
    diff = time.ticks_diff
    x = 0
    t_prev = tick()
    for i in range(n):
        x = ram[i]
        t = tick()
        d = diff(t, t_prev)
        gaps[i] = d if d < 65535 else 65535
        t_prev = t
    return x


def underruns(n, extra):
    """Replay gaps[0:n] against a Z80 reading every Z80_US from a DEPTH-deep
    FIFO. Like LOAD_TS: the FIFO starts full (READY is raised only once TX
    is full), the next byte is read from the file BEFORE waiting for room,
    and a blocked producer puts the moment the Z80's read frees a slot.
    Returns (empty reads, Z80 read index of the first one or -1)."""
    q = DEPTH                       # FIFO starts full
    pi = DEPTH                      # next byte to put
    t_last = 0.0                    # when the producer last put
    empty = 0
    first = -1
    k = 0
    while k < n:
        now = k * Z80_US
        while pi < n and q < DEPTH:           # catch up to the Z80's read
            r = t_last + gaps[pi] + extra
            if r > now:
                break
            t_last = r
            q += 1
            pi += 1
        if q:
            q -= 1
            if pi < n and q == DEPTH - 1 and t_last + gaps[pi] + extra <= now:
                t_last = now                    # was blocked on a full FIFO
                q += 1
                pi += 1
        else:
            empty += 1                          # the Z80 reads 0x00, counts it
            if first < 0:
                first = k
        k += 1
    return empty, first


def stats(n):
    big = [0, 0, 0]
    for i in range(n):
        g = gaps[i]
        if g >= 100:
            big[0] += 1
        if g >= 150:
            big[1] += 1
        if g >= 200:
            big[2] += 1
    return max(gaps[:n]) if n else 0, big


def report(label, n):
    worst, big = stats(n)
    runs = []
    for e in EXTRA_US:
        emp, first = underruns(n, e)
        runs.append("+%dus: %d%s" % (e, emp, (" (first at byte %d)" % first) if emp else ""))
    print("  %-22s worst %4d us | gaps >=100/150/200 us: %d/%d/%d | empty Z80 reads %s"
          % (label, worst, big[0], big[1], big[2], ", ".join(runs)))


def main():
    arch = open(TAP, "rb")
    try:
        for p in range(PASSES):
            print("pass %d" % (p + 1))
            for name, off, n in BLOCKS:
                gc.collect()
                time_file(arch, off, n)
                report(name + " file", n)
                arch.seek(off)
                arch.readinto(memoryview(ram)[:n])
                gc.collect()
                time_ram(n)
                report(name + " RAM", n)
    finally:
        arch.close()


main()
