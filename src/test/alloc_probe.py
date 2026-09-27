"""Heap-allocation probe for the per-byte transfer helpers -- run on the Pico.

WHY THIS EXISTS (issue #51, hardware 2026-09-27)
LOAD of any block over ~6 KB failed with Report R. The Z80's LOAD loop reads
a byte every ~55 us with no handshake, so any Pico pause longer than the
4-deep TX FIFO covers (~200 us) makes it read empty bytes. TX_ROOM, called
once per byte, did `rx = MQ.rx_fifo; txf = MQ.tx_fifo` -- storing a bound
method allocates it -- so every byte cost 32 bytes of heap. The heap filled
about every 6.5 KB, and each GC froze the Pico ~6 ms: ~110 bytes lost per GC,
at the same points (KB 7 and KB 13) on every run.

A direct call (`MQ.tx_fifo()`) allocates nothing. load_ts_hosttest.py now
rejects stored bound methods in TX_ROOM / ECHO_KEEP structurally; this probe
measures the real thing on the Pico.

Run (firmware stopped at the idle prompt, see tools/pico-serial.py):
    python3 tools/pico-serial.py break
    python3 tools/pico-serial.py run --file src/test/alloc_probe.py
Every line must read 0.0 bytes/call. Restart with `softreset` afterwards.

Measured with GC ON: each test collects first and makes 500 calls, far too
few to fill the heap, so no GC lands inside the measurement. (Don't use
gc.disable() for this: if anything does allocate, the firmware runs out of
heap and the REPL can't recover without a power cycle.)
"""

import gc
import time

import TS.tspico as T
import TS.tspico_io as io

N = 500
MQ = T.MQ


def cost(label, f):
    gc.collect()
    a = gc.mem_free()
    f()
    b = gc.mem_free()
    gc.collect()
    per = (a - b) / N
    print("%-30s %6.1f bytes/call%s" % (label, per, "" if per == 0 else "   <-- ALLOCATES"))


echo = bytearray(3)
el = bytearray(1)
arch = io._nofile_arch or open("/assets/nofile.tap", "rb")


def t_room():
    for _ in range(N):
        io.TX_ROOM(MQ, echo, 1)             # TX not full: returns 0 at once


def t_echo():
    for _ in range(N):
        echo[0] = 0
        io.ECHO_KEEP(echo, 0x55)


def t_rxword():
    for _ in range(N):
        io.RX_WORD(MQ, 0)                   # RX empty: returns -1 at once


def t_read():
    rd = arch.readinto
    arch.seek(0)
    for _ in range(N):
        rd(el)


def t_txf():
    for _ in range(N):
        MQ.tx_fifo()


cost("TX_ROOM", t_room)
cost("ECHO_KEEP", t_echo)
cost("RX_WORD", t_rxword)
cost("file readinto(1 byte)", t_read)
cost("MQ.tx_fifo()", t_txf)
