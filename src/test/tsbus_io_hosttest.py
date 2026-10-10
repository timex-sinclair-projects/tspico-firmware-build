#!/usr/bin/env python3
"""tspico_io on the v3 card (step 4.2 of the board layer,
docs/v3-board-layer-proposal.md): with the tsbus module present, MQ is
tsbus.MQ(), a 1 KB queue core 1 feeds to the Z80, not a PIO state machine.

Checks, against a fake tsbus and a model Z80 that reads the queue:
  - the PIO paths are off even though mem32 and rp2.DMA exist (they do on
    the RP2350): MQX goes through MQ.exec, no RX ring, no DMA;
  - DRAIN_MAX covers a full queue; ENA_MQ_DUAL keeps MQ and says READY;
  - STREAM_DMA streams through the queue (STREAM_QUEUE) with STREAM_DMA's
    contract: why 0 (all queued), 1 (BREAK), 3 (stall, with first_ms's
    grace), 4 (any word in ZX48 mode); `sent` is bytes queued, and the Z80
    has read sent - tx_fifo().

Run:  python3 src/test/tsbus_io_hosttest.py
"""

import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, SRC)
sys.path.insert(0, HERE)

import sync_io_hosttest as S

FAILS = []


def check(ok, what):
    print(("  ok   " if ok else "  FAIL ") + what)
    if not ok:
        FAILS.append(what)


class Z80:
    """Reads `rate` bytes from the queue each time the firmware waits on it,
    stops after `stop_at` bytes, and writes `word` to RX after `write_at`."""

    def __init__(self, rate=64, stop_at=None, write_at=None, word=0x103):
        self.rate, self.stop_at, self.write_at, self.word = rate, stop_at, write_at, word
        self.got = bytearray()
        self.wrote = False

    def step(self, mq):
        for _ in range(self.rate):
            if not mq.tx or (self.stop_at is not None and len(self.got) >= self.stop_at):
                break
            self.got.append(mq.tx.pop(0))
        if (self.write_at is not None and not self.wrote and len(self.got) >= self.write_at):
            mq.rx.append(self.word)
            self.wrote = True


class QueueMQ:
    """tsbus.MQ: a 1024-byte TX queue, an RX queue of 9-bit words, the
    status byte, and put_block(buf[, wait_ms]) as in tsbus.c."""
    CAP = 1024

    def __init__(self, z80):
        self.z80 = z80
        self.tx, self.rx = [], []
        self.status = 0
        self.execs = []

    def _fill(self, mv):
        k = min(self.CAP - len(self.tx), len(mv))
        self.tx.extend(bytes(mv[:k]))
        return k

    def put_block(self, buf, wait_ms=-1):
        mv = memoryview(buf)
        got = self._fill(mv)
        if wait_ms == 0:
            return got
        while got < len(mv) and not self.rx:
            before = len(self.z80.got)
            self.z80.step(self)
            k = self._fill(mv[got:])
            got += k
            if not k and len(self.z80.got) == before:
                break                                   # no room and no progress: wait_ms ran out
        return got

    def tx_fifo(self):
        return len(self.tx)

    def rx_fifo(self):
        self.z80.step(self)
        return len(self.rx)

    def get(self):
        return self.rx.pop(0)

    def put(self, b):
        self.tx.append(b & 0xFF)

    def exec(self, instr):
        self.execs.append(instr)
        t = instr.replace(" ", "")
        if t == "mov(y,invert(null))":
            self.status = 0xFF
        elif t == "pull(noblock)":
            if self.tx:
                self.tx.pop(0)


def main():
    S.install_fakes()
    sys.modules["machine"].mem32 = {}                   # the RP2350 has both:
    sys.modules["rp2"].DMA = object                     # they must be switched off
    tsbus = types.ModuleType("tsbus")
    tsbus.MQ = QueueMQ
    sys.modules["tsbus"] = tsbus
    import TS.tspico_io as io
    io.time = S.FakeTime()

    print("the PIO paths are off on the v3 card")
    check(io._tsbus_mq is QueueMQ, "tsbus found")
    check(io._DMA is None and io._mem32 is None and io._ring is None,
          "no DMA, no mem32 register writes, no RX ring (%r %r %r)" % (io._DMA, io._mem32, io._ring))
    check(io.CAN_STREAM(), "CAN_STREAM: blocks still go out without Python per byte")
    check(io.DRAIN_MAX >= QueueMQ.CAP, "DRAIN_MAX covers a full queue (%d)" % io.DRAIN_MAX)

    mq = QueueMQ(Z80(rate=0))
    io.MQX(mq, "mov(y, invert(null))")
    check(mq.execs == ["mov(y, invert(null))"] and mq.status == 0xFF, "MQX goes through MQ.exec")
    mq.tx = list(range(300))
    io.MQ_TO_IDLE(mq)
    check(mq.tx == [0x01], "MQ_TO_IDLE empties a 300-byte queue, then stages 01h (%d left)" % len(mq.tx))
    mq.execs = []
    check(io.ENA_MQ_DUAL(mq) is mq and mq.execs == ["mov(y, invert(null))"],
          "ENA_MQ_DUAL keeps MQ (the bus is never given up on v3) and says READY")

    data = bytes((i * 7) & 0xFF for i in range(6912))

    print("STREAM_DMA through the queue: a whole SCREEN$-sized block")
    z = Z80(rate=64)
    mq = QueueMQ(z)
    echo = []
    r = io.STREAM_DMA(mq, data, echo, 3000, True)
    check(r is not None and r[0] == 0 and r[1] == len(data), "why 0, all 6912 queued (%r)" % (r[:2],))
    check(mq.execs and mq.execs[0] == "mov(y, invert(null))", "READY said once the queue was filled")
    while mq.tx:
        z.step(mq)
    check(bytes(z.got) == data, "the Z80 read every byte, in order")

    print("BREAK in the middle")
    z = Z80(rate=64, write_at=2000, word=0x103)
    mq = QueueMQ(z)
    r = io.STREAM_DMA(mq, data, [], 3000, True)
    check(r[0] == 1, "why 1 on a port-0Fh write (%r)" % (r[:2],))
    check(r[1] - mq.tx_fifo() == len(z.got) and bytes(z.got) == data[:len(z.got)],
          "the Z80 read sent - tx_fifo() bytes, the start of the block (%d)" % len(z.got))

    print("the Z80 stops reading")
    z = Z80(rate=64, stop_at=3000)
    mq = QueueMQ(z)
    io.time = S.FakeTime()
    r = io.STREAM_DMA(mq, data, [], 500, True)
    check(r[0] == 3 and r[1] < len(data), "why 3 after the stall (%r)" % (r[:2],))
    check(len(z.got) == 3000, "the Z80 had read 3000")

    print("first_ms: a slow start is not a stall")
    z = Z80(rate=0)
    mq = QueueMQ(z)
    io.time = S.FakeTime()
    r = io.STREAM_DMA(mq, data, [], 50, True, first_ms=5000)
    check(r[0] == 3 and io.time.ms >= 5000, "it waits first_ms before giving up (%d ms)" % io.time.ms)

    print("ZX48 mode: any word ends it")
    z = Z80(rate=64, write_at=100, word=0x4C)
    mq = QueueMQ(z)
    r = io.STREAM_DMA(mq, data, None, 3000, True)
    check(r[0] == 4 and r[2] == 0x4C, "why 4 with the word (%r)" % (r,))

    print()
    if FAILS:
        print("%d FAILED" % len(FAILS))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
