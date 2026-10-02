# Per-operation timings for the paths the Z80 reads blind (no handshake).
#
# Run at the REPL with the firmware stopped (tools/pico-serial.py break, then
# run --file this), on each MicroPython version to compare. Uses a spare
# state machine on PIO1 that only drains its TX FIFO -- no pins -- so put()
# never blocks and nothing touches the 2068's bus.
#
# The Z80 sides these feed: the ZX v3 ROM reads a tpi: reply ~45 us a byte
# (TPI_DLY), fddcmd's INPUT # reads ~75 us a byte (READ_DELAY), and
# romupdate's BLKRCV loop ~33 us a byte.

import sys, time, machine, rp2, gc

machine.freq(270_000_000)


@rp2.asm_pio()
def drain():
    pull()


sm = rp2.StateMachine(4, drain, freq=30_000_000)
sm.active(1)

N = 2000


def bench(name, fn):
    gc.collect()
    t0 = time.ticks_us()
    fn()
    dt = time.ticks_diff(time.ticks_us(), t0)
    print("%-28s %6.2f us" % (name, dt / N))


def empty():
    for _ in range(N):
        pass


def ticks():
    for _ in range(N):
        time.ticks_ms()


def txf():
    for _ in range(N):
        sm.tx_fifo()


def put():
    for _ in range(N):
        sm.put(0x41)


def f():
    pass


def call():
    for _ in range(N):
        f()


TX_DEPTH = 4


def zx_room(MQ, stall_ms):                       # tspico_io.ZX_ROOM, as it is
    t0 = time.ticks_ms()
    while MQ.tx_fifo() >= TX_DEPTH:
        if MQ.rx_fifo():
            return MQ.get()
        if time.ticks_diff(time.ticks_ms(), t0) >= stall_ms:
            return -2
    return -1


out = bytearray(N)


def zx_reply():                                  # ZX_TPI's reply loop, per byte
    i = 0
    while i < N:
        w = zx_room(sm, 1000)
        if w != -1:
            break
        sm.put(out[i])
        i += 1


def zx_tight():                                  # the same, with no call per byte
    put = sm.put
    txf = sm.tx_fifo
    i = 0
    while i < N:
        if txf() >= TX_DEPTH:
            continue
        put(out[i])
        i += 1


print("MicroPython", sys.implementation.version, "at", machine.freq())
bench("empty loop", empty)
bench("time.ticks_ms()", ticks)
bench("sm.tx_fifo()", txf)
bench("sm.put()", put)
bench("call an empty function", call)
bench("ZX_TPI reply, per byte", zx_reply)
bench("tight reply, per byte", zx_tight)
sm.active(0)
