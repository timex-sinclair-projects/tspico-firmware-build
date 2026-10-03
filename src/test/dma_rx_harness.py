# DMA receive harness: can a DMA channel catch every byte the Z80 sends while
# core0 is busy, where today's Python polling loses one?
#
# Why (hardware, 2026-10-02, MicroPython v1.29): the first command after a
# 2068 power-on gave Report T. The log had the 2068's CAT pre-header with ONE
# byte missing from the middle -- 42 00 FF 00 00 00 07 00 BA, ten sent, nine
# kept -- so core0 stopped reading for a moment and TS_IO_DUAL's `push
# noblock` dropped a byte off the full 4-deep RX FIFO. rp2.DMA (v1.22+, not in
# v1.20) can drain that FIFO into RAM in hardware, paced by the state
# machine's own "RX not empty" request, whatever core0 is doing.
#
# No 2068 needed. A stand-in "Z80" state machine pushes a counting sequence
# into its own RX FIFO every ~30 us -- the Z80's OUT pace -- with `push
# noblock`, so a full FIFO drops words exactly as the bus program does. A gap
# in the numbers collected is a lost byte. Each mode runs while core0 is
# deliberately stalled:
#
#   busy     a 300 us busy-wait every 40 words  (> 4 words at 30 us)
#   gc       gc.collect() every 150 words
#   usb      a 200-character print every 60 words  (a telemetry flood)
#   flash    a 512-byte append to /TMP/dma.bin every 300 words  (XIP stalls)
#
#   poll     today's shape: a Python loop reading sm.get(), stalls in-line
#   dma      a DMA channel drains the FIFO into an array; core0 does only
#            the stalls, then checks the array
#
# Run at the REPL with the firmware stopped:
#   python3 tools/pico-serial.py break
#   python3 tools/pico-serial.py run --file src/test/dma_rx_harness.py
#   python3 tools/pico-serial.py softreset
# It uses one spare state machine and one free DMA channel; it never touches
# state machines 0, 4 or 5 (the bus, and the 2068's ROM lines), so the 2068 can
# stay on. (Still: the firmware is stopped while it runs.)

import gc, os, sys, time, machine, rp2
from rp2 import PIO, asm_pio
from array import array

machine.freq(270_000_000)

N = 3000                  # words per run: ~90 ms of Z80 traffic
PERIOD_US = 30


@asm_pio(in_shiftdir=PIO.SHIFT_LEFT)
def z80():
    # Push x, then x-1, ... one word every ~1059 cycles (35.3 MHz: ~30 us).
    wrap_target()
    mov(isr, x)
    push(noblock)                       # full FIFO: the word is dropped
    jmp(x_dec, "d")
    label("d")
    set(y, 31)              [31]
    label("w")
    jmp(y_dec, "w")         [31]
    wrap()


CYCLES = 4 + 31 + 32 * 32               # per word, from the program above
FREQ = int(CYCLES * 1_000_000 // PERIOD_US)


def make_sm():
    """A spare state machine, never 0, 4 or 5. Returns (sm, its number)."""
    for n in (7, 6, 3, 2, 1):
        try:
            sm = rp2.StateMachine(n, z80, freq=FREQ)
            return sm, n
        except Exception:                # its PIO's instruction memory is full
            continue
    raise OSError("no spare state machine with room for the program")


def dreq_rx(n):
    return ((n // 4) << 3) + (n % 4) + 4


STALLS = {
    "none":  (0, None),
    "busy":  (40, lambda: time.sleep_us(300)),
    "gc":    (150, gc.collect),
    "usb":   (60, lambda: print("~" * 200)),
    "flash": (300, None),               # set up per run (needs the file open)
}


def gaps(words):
    """Lost words: wherever consecutive values don't step down by one. A
    step the wrong way (a stale word) counts as -1, so it can't hide."""
    lost = 0
    for i in range(1, len(words)):
        d = (words[i - 1] - words[i]) & 0xFFFFFFFF
        if d == 0 or d > 0x7FFFFFFF:
            return -1
        lost += d - 1
    return lost


def fresh(sm):
    """Stopped, FIFOs empty (restart() doesn't empty them), counter at 0."""
    sm.active(0)
    while sm.rx_fifo():
        sm.get()
    sm.restart()
    sm.exec("set(x, 0)")


def run_poll(sm, stall):
    every, fn = stall
    got = array("I", bytes(4 * N))
    fresh(sm)
    sm.active(1)
    i = 0
    get = sm.get
    rx = sm.rx_fifo
    t0 = time.ticks_ms()
    while i < N:
        if rx():
            got[i] = get()
            i += 1
            if every and fn and i % every == 0:
                fn()
        elif time.ticks_diff(time.ticks_ms(), t0) > 2000:
            break
    sm.active(0)
    return gaps(got[:i]), i


def run_dma(sm, n, stall):
    every, fn = stall
    got = array("I", bytes(4 * N))
    d = rp2.DMA()
    try:
        ctrl = d.pack_ctrl(size=2, inc_read=False, inc_write=True, treq_sel=dreq_rx(n))
        fresh(sm)
        d.config(read=sm, write=got, count=N, ctrl=ctrl, trigger=True)
        sm.active(1)
        t0 = time.ticks_ms()
        k = 0
        while d.active() and time.ticks_diff(time.ticks_ms(), t0) < 2000:
            if every and fn:
                time.sleep_us(every * PERIOD_US)   # the same stall rate as poll
                fn()
                k += 1
        sm.active(0)
        done = N - d.count
    finally:
        d.close()
    return gaps(got[:done]), done


def main():
    sm, n = make_sm()
    print("z80 stand-in on state machine %d at %d Hz (~%d us a word), DMA DREQ %d"
          % (n, FREQ, PERIOD_US, dreq_rx(n)))
    try:
        os.mkdir("/TMP")
    except OSError:
        pass
    f = open("/TMP/dma.bin", "wb")
    blob = bytes(512)

    def flash():
        f.write(blob)
        f.flush()
    STALLS["flash"] = (300, flash)
    print("%-6s %-5s %8s %8s" % ("stall", "mode", "words", "lost"))
    try:
        for name in ("none", "busy", "gc", "usb", "flash"):
            for mode, fn in (("poll", run_poll), ("dma", run_dma)):
                gc.collect()
                if mode == "poll":
                    lost, got = fn(sm, STALLS[name])
                else:
                    lost, got = fn(sm, n, STALLS[name])
                print("%-6s %-5s %8d %8d" % (name, mode, got, lost))
    finally:
        f.close()
        try:
            os.remove("/TMP/dma.bin")
        except OSError:
            pass
        sm.active(0)


main()
