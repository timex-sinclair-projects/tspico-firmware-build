# Per-operation timings for the paths the Z80 reads blind (no handshake).
#
# Run at the REPL with the firmware stopped (tools/pico-serial.py break, then
# run --file this), on each MicroPython version to compare. Uses a spare
# state machine (7: PIO1's last; the firmware uses 0, 4 and 5 -- 4 and 5
# drive the 2068's ROM lines, so never borrow those with the 2068 on) that
# only drains its TX FIFO -- no pins -- so put() never blocks and nothing
# touches the 2068's bus.
# Soft-reset between runs: the drain program stays in PIO1's instruction
# memory, and a second run in the same session fails with ENOMEM.
#
# The Z80 sides these feed: the ZX v3 ROM reads a tpi: reply ~45 us a byte
# (TPI_DLY), fddcmd's INPUT # reads ~75 us a byte (READ_DELAY), and
# romupdate's BLKRCV loop ~33 us a byte.
#
# The last three lines time the status writes: StateMachine.exec() with the
# instruction as text (MicroPython runs its Python PIO assembler on every
# call), exec() with the instruction already encoded, and the MQX shape from
# tspico_io (the encoding cached, written straight to the SM's INSTR
# register). MQX is PIO0 SM0 by address; the copy here, mqx(), is SM 7's.

import sys, time, machine, rp2, gc
from micropython import const

machine.freq(270_000_000)


@rp2.asm_pio()
def drain():
    pull()


sm = rp2.StateMachine(7, drain, freq=30_000_000)
sm.active(1)

N = 2000


def bench(name, fn, n=N):
    gc.collect()
    t0 = time.ticks_us()
    fn()
    dt = time.ticks_diff(time.ticks_us(), t0)
    print("%-28s %8.2f us" % (name, dt / n))


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


TAP = "/assets/nofile.tap"                       # on every Pico's flash, ~21 KB


def load_bytewise():                             # LOAD_TS's data loop before 2026-10-02
    f = open(TAP, "rb")
    rd = f.readinto
    txf = sm.tx_fifo
    put = sm.put
    el = bytearray(1)
    for _ in range(N):
        rd(el)
        if txf() >= TX_DEPTH:
            continue
        put(el[0])
    f.close()


CHUNK = 256
_buf = bytearray(CHUNK)


def load_chunked():                              # the same, a chunk per readinto()
    f = open(TAP, "rb")
    rd = f.readinto
    txf = sm.tx_fifo
    put = sm.put
    buf = _buf
    left = N
    while left:
        got = rd(buf) if left >= CHUNK else rd(memoryview(buf)[:left])
        left -= got
        i = 0
        while i < got:
            if txf() >= TX_DEPTH:
                pass
            put(buf[i])
            i += 1
    f.close()


N_EXEC = 50                                     # exec() as text is ~10 ms a call
_SM7_EXECCTRL = const(0x50300114)                # PIO1 SM3: SM0's registers + 3 * 0x18
_SM7_INSTR = const(0x50300120)
_SM7_PINCTRL = const(0x50300124)
_ENCODED = {}
_mem32 = machine.mem32                          # bound once, as tspico_io does
STATUS = "mov(y, invert(null))"                 # the READY write, MQX's most common


def mqx(instr):                                  # tspico_io.MQX, for SM 7
    ss = (_mem32[_SM7_PINCTRL] >> 29) | (((_mem32[_SM7_EXECCTRL] >> 30) & 1) << 3)
    by_ss = _ENCODED.get(instr)
    if by_ss is None:
        by_ss = _ENCODED[instr] = {}
    code = by_ss.get(ss)
    if code is None:
        code = by_ss[ss] = rp2.asm_pio_encode(instr, ss & 7, ss >> 3)
    _mem32[_SM7_INSTR] = code


def exec_text():
    for _ in range(N_EXEC):
        sm.exec(STATUS)


_STATUS_CODE = rp2.asm_pio_encode(STATUS, 0)


def exec_encoded():
    for _ in range(N):
        sm.exec(_STATUS_CODE)


def exec_mqx():
    for _ in range(N):
        mqx(STATUS)


print("MicroPython", sys.implementation.version, "at", machine.freq())
bench("empty loop", empty)
bench("time.ticks_ms()", ticks)
bench("sm.tx_fifo()", txf)
bench("sm.put()", put)
bench("call an empty function", call)
bench("ZX_TPI reply, per byte", zx_reply)
bench("tight reply, per byte", zx_tight)
bench("LOAD loop, 1 byte per read", load_bytewise)
bench("LOAD loop, 256 per read", load_chunked)
bench("sm.exec(text)", exec_text, N_EXEC)
bench("sm.exec(encoded)", exec_encoded)
bench("MQX (cached, INSTR write)", exec_mqx)
sm.active(0)
