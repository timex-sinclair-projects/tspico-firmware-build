# DMA send harness: can a DMA channel keep the TX FIFO fed while core0 is
# busy, where a Python put() loop lets it run dry?
#
# Why: the 2068 and ZX ROMs read a LOAD block blind, a byte every ~47 us,
# from TS_IO_DUAL's 4-deep TX FIFO -- ~190 us of slack. #126 removed the
# file reads from the stream (the big stalls); a GC, a USB interrupt or a
# flash write can still outlast 190 us (dma_rx_harness measured those on the
# receive side). A DMA channel streaming the RAM buffer into the FIFO, paced
# by the state machine's "TX not full" request, shouldn't care.
#
# No 2068 needed. A stand-in "Z80 reader" state machine takes a word from its
# TX FIFO every ~47 us with `pull noblock` -- which, on an empty FIFO, hands
# back X, set to a sentinel -- and pushes what it got into its RX FIFO. A
# second DMA channel collects those (dma_rx_harness showed DMA collection
# loses nothing). A sentinel in the result is a read that found the FIFO dry.
# Sent: 1, 2, 3 ... N. Checked: every value arrives, in order, no sentinels.
#
#   poll   today's shape: a Python loop, put() when the FIFO has room
#   dma    a DMA channel sends the buffer; core0 only does the stalls
#
# Stalls as in dma_rx_harness: busy (300 us every 40 words), gc, usb (a
# 200-character print), flash (a 512-byte write). Plus "none".
#
# Run at the REPL with the firmware stopped:
#   python3 tools/pico-serial.py break
#   python3 tools/pico-serial.py run --file src/test/dma_tx_harness.py
#   python3 tools/pico-serial.py softreset     (2068 off: it resets the PIO)
# Never touches state machines 0, 4 or 5.

import gc, os, time, machine, rp2
from rp2 import PIO, asm_pio
from array import array

machine.freq(270_000_000)

N = 2000                  # words a run: ~94 ms of Z80 reading
PERIOD_US = 47
SENTINEL = 0xFFFFFFFF


@asm_pio(in_shiftdir=PIO.SHIFT_LEFT, out_shiftdir=PIO.SHIFT_RIGHT)
def z80_reader():
    # One read every ~47 us: pull (X if TX is empty), hand it back on RX.
    wrap_target()
    pull(noblock)
    mov(isr, osr)
    push(noblock)
    set(y, 31)              [31]
    label("w")
    jmp(y_dec, "w")         [31]
    wrap()


CYCLES = 3 + 32 + 32 * 32               # per read, from the program above
FREQ = int(CYCLES * 1_000_000 // PERIOD_US)


def make_sm():
    for n in (7, 6, 3, 2, 1):           # never 0, 4 or 5
        try:
            return rp2.StateMachine(n, z80_reader, freq=FREQ), n
        except Exception:
            continue
    raise OSError("no spare state machine with room for the program")


def dreq(n, rx):
    return ((n // 4) << 3) + (n % 4) + (4 if rx else 0)


def fresh(sm):
    sm.active(0)
    while sm.rx_fifo():
        sm.get()
    sm.restart()
    sm.exec("mov(x, invert(null))")     # the sentinel an empty pull hands back


def check(words, got):
    """(dry reads seen once streaming began, values missing, out of order)."""
    vals = words[:got]
    start = 0
    while start < len(vals) and vals[start] == SENTINEL:
        start += 1                       # the reader ran before the first word
    dry = 0
    expect = 1
    missing = 0
    order = 0
    for v in vals[start:]:
        if v == SENTINEL:
            if expect <= N:
                dry += 1
            continue
        if v != expect:
            if v > expect:
                missing += v - expect
            else:
                order += 1
        expect = v + 1
    missing += max(0, N + 1 - expect)
    return dry, missing, order


def collect(sm, n, words):
    """A DMA channel that collects everything the reader pushes."""
    d = rp2.DMA()
    ctrl = d.pack_ctrl(size=2, inc_read=False, inc_write=True, treq_sel=dreq(n, True))
    d.config(read=sm, write=words, count=len(words), ctrl=ctrl, trigger=True)
    return d


def run(sm, n, mode, stall):
    every, fn = stall
    src = array("I", range(1, N + 1))
    words = array("I", bytes(4 * (N + 400)))   # room for dry reads after the end
    fresh(sm)
    rx = collect(sm, n, words)
    tx = None
    try:
        if mode == "dma":
            tx = rp2.DMA()
            ctrl = tx.pack_ctrl(size=2, inc_read=True, inc_write=False, treq_sel=dreq(n, False))
            tx.config(read=src, write=sm, count=N, ctrl=ctrl, trigger=True)
            sm.active(1)
            t0 = time.ticks_ms()
            while tx.active() and time.ticks_diff(time.ticks_ms(), t0) < 2000:
                if every and fn:
                    time.sleep_us(every * PERIOD_US)
                    fn()
        else:
            sm.active(1)
            put = sm.put
            txf = sm.tx_fifo
            i = 0
            while i < N:
                if txf() < 4:
                    put(src[i])
                    i += 1
                    if every and fn and i % every == 0:
                        fn()
        time.sleep_ms(5)                 # the reader's last reads
        sm.active(0)
        got = len(words) - rx.count
    finally:
        rx.close()
        if tx:
            tx.close()
    return check(words, got)


def main():
    sm, n = make_sm()
    print("z80 reader on state machine %d, ~%d us a read, DREQ tx %d rx %d"
          % (n, PERIOD_US, dreq(n, False), dreq(n, True)))
    try:
        os.mkdir("/TMP")
    except OSError:
        pass
    f = open("/TMP/dma.bin", "wb")
    blob = bytes(512)

    def flash():
        f.write(blob)
        f.flush()
    stalls = {"none": (0, None), "busy": (40, lambda: time.sleep_us(300)),
              "gc": (150, gc.collect), "usb": (60, lambda: print("~" * 200)),
              "flash": (300, flash)}
    print("%-6s %-5s %6s %8s %6s" % ("stall", "mode", "dry", "missing", "order"))
    try:
        for name in ("none", "busy", "gc", "usb", "flash"):
            for mode in ("poll", "dma"):
                gc.collect()
                dry, missing, order = run(sm, n, mode, stalls[name])
                print("%-6s %-5s %6d %8d %6d" % (name, mode, dry, missing, order))
    finally:
        f.close()
        try:
            os.remove("/TMP/dma.bin")
        except OSError:
            pass
        sm.active(0)


main()
