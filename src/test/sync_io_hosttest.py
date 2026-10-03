"""Host-side test for the issue-#51 SYNC / BREAK helpers in TS/tspico_io.py
-- CPython, no Pico.

Imports the PRODUCTION module with the device-only modules faked (the same
approach as zx48_hosttest.py) and exercises:

  RX_CAPTURE   the tight burst read: complete burst, SYNC (a lone port-0Fh
               write), a partial burst then silence, a SYNC right behind a
               partial burst, and 9-bit words kept intact;
  MQ_TO_IDLE   TX and RX emptied, exactly one 0x01 pre-load, status idle or
               recovered, or left alone;
  MQ_STATUS    the three Y values the 1.8b ROM reads (FF / F7 / FB).

It also checks the dispatcher in BOTH TS/tspico.py and dev_tspico.py reads
the pre-header through RX_CAPTURE and no longer has the old blocking loop.

The same patterns ran on real hardware in src/test/abort_harness.py; this
pins the production copies. Nothing here watches the Z80 bus.

Run:  python3 src/test/sync_io_hosttest.py
"""

import ast
import builtins
import os
import re
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)


class FakeMQ:
    """TS_IO_DUAL as the helpers see it: 4-deep FIFOs, 9-bit RX words, Y."""

    def __init__(self, rx=(), tx=()):
        self.rx = list(rx)
        self.tx = list(tx)
        self.y = 0
        self.execs = []

    def rx_fifo(self):
        return min(len(self.rx), 4)

    def tx_fifo(self):
        return len(self.tx)

    def get(self):
        return self.rx.pop(0)

    def put(self, b):
        assert len(self.tx) < 4, "put() into a full TX FIFO blocks forever on a Pico"
        self.tx.append(b)

    def exec(self, s):
        self.execs.append(s)
        t = s.replace(" ", "")
        if t == "mov(y,invert(null))":
            self.y = 0xFFFFFFFF
        elif t.startswith("set(y,"):
            self.y = int(t[6:-1])
        elif t == "mov(y,invert(y))":
            self.y = ~self.y & 0xFFFFFFFF
        elif t == "pull(noblock)":
            if self.tx:
                self.tx.pop(0)
        elif t == "mov(osr,null)":
            pass
        else:
            raise AssertionError("unexpected exec %r" % s)

    def status(self):
        return self.y & 0xFF


class FakeTime:
    """Each clock read is 1 ms later, so a 1000 ms stall is 1000 reads."""

    def __init__(self):
        self.ms = 0

    def ticks_ms(self):
        self.ms += 1
        return self.ms

    @staticmethod
    def ticks_diff(a, b):
        return a - b

    def ticks_us(self):
        return self.ms * 1000


def install_fakes():
    builtins.const = lambda x: x
    machine = types.ModuleType("machine")

    class _Pin:
        OUT, IN, PULL_UP = 0, 1, 2

        def __init__(self, *a, **k):
            pass

        def value(self, *a):
            return 0

    machine.Pin = _Pin
    machine.SPI = lambda *a, **k: None
    machine.freq = lambda *a, **k: None
    sys.modules["machine"] = machine
    rp2 = types.ModuleType("rp2")
    rp2.StateMachine = lambda *a, **k: FakeMQ()
    rp2.asm_pio = lambda *a, **k: (lambda f: f)
    rp2.PIO = types.SimpleNamespace(OUT_HIGH=0, OUT_LOW=1, SHIFT_RIGHT=2,
                                    SHIFT_LEFT=3, IN_HIGH=4)
    sys.modules["rp2"] = rp2
    utime = types.ModuleType("utime")
    utime.sleep = utime.sleep_ms = lambda *a: None
    sys.modules["utime"] = utime
    thread = types.ModuleType("_thread")
    thread.start_new_thread = lambda fn, args: None
    sys.modules["_thread"] = thread
    ts = types.ModuleType("TS")
    ts.__path__ = [os.path.join(SRC, "TS")]
    sys.modules["TS"] = ts
    sdc = types.ModuleType("TS.sdcard")
    sdc.SDCard = lambda *a, **k: None
    sys.modules["TS.sdcard"] = sdc


results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg)


def main():
    install_fakes()
    sys.path.insert(0, SRC)
    import TS.tspico_io as io
    from array import array
    io.time = FakeTime()

    raw = array("H", [0] * 10)
    pre = [0x00, 0x01, 0xFF, 0x34, 0x12, 0x00, 0x80, 0x11, 0x00, 0x7C]

    print("RX_CAPTURE")
    mq = FakeMQ(rx=pre)
    check(io.RX_CAPTURE(mq, raw, 10, 1000) == 10 and list(raw) == pre,
          "a whole pre-header: returns 10, words stored in order")

    mq = FakeMQ(rx=[0x103])
    check(io.RX_CAPTURE(mq, raw, 10, 1000) == -1 and raw[0] == 0x103,
          "a lone port-0Fh write (SYNC 03h): returns -1, 9-bit word kept")

    mq = FakeMQ(rx=pre[:4])
    t0 = io.time.ms
    n = io.RX_CAPTURE(mq, raw, 10, 1000)
    check(n == 4 and 1000 <= io.time.ms - t0 <= 1010,
          "4 words then silence: returns 4 after the 1000 ms stall, not a hang")

    mq = FakeMQ(rx=pre[:3] + [0x103])
    check(io.RX_CAPTURE(mq, raw, 10, 1000) == -4,
          "3 words then a SYNC (2068 reset mid pre-header): returns -4")

    mq = FakeMQ(rx=pre[:9] + [0x103])
    check(io.RX_CAPTURE(mq, raw, 10, 1000) == -10,
          "a 0Fh write as the 10th word is still caught (returns -10)")

    print("RxDMA (the pre-header by DMA, v1.29)")

    class FakeChannel:
        """rp2.DMA reading RX into memory, paced by the "RX not empty" DREQ:
        it takes whatever the FakeMQ has whenever it is looked at."""

        def __init__(self):
            self.on, self.n, self.i = False, 0, 0

        def pack_ctrl(self, **kw):
            assert kw == dict(size=2, inc_read=False, inc_write=True, treq_sel=4), kw
            return 7

        def config(self, read, write, count, ctrl, trigger):
            self.mq, self.buf, self.n, self.i, self.on = read, write, count, 0, bool(trigger)
            self.stopped = False

        def active(self, v=None):
            if v is not None:
                self.on = bool(v)
                self.stopped = not v        # as on hardware: a stopped channel's
            return self.on                  # count no longer says how far it got

        @property
        def count(self):
            if self.stopped:
                return 0
            while self.on and self.i < self.n and self.mq.rx:
                self.buf[self.i] = self.mq.rx.pop(0)
                self.i += 1
            if self.i >= self.n:
                self.on = False
            return self.n - self.i

    io._DMA = FakeChannel
    raw32 = array("I", [0] * 10)
    rxd = io.RX_DMA(raw32)
    check(rxd is not None, "RX_DMA gives a capture when rp2.DMA is there")

    def dma_take(words):
        mq = FakeMQ()
        rxd.arm(mq)
        quiet = rxd.waiting()
        mq.rx.extend(words)
        return quiet, rxd.waiting(), rxd.take(1000), mq

    q, w, r, mq = dma_take(pre)
    check(q == 0 and w == 10 and r == 10 and list(raw32) == pre and not rxd.armed,
          "a whole pre-header: waiting() 0 while quiet, then 10; take() returns 10, in order")
    q, w, r, mq = dma_take(pre + [0x41, 0x42])
    check(r == 10 and mq.rx == [0x41, 0x42],
          "the command body after it stays in the FIFO for the handler")
    q, w, r, mq = dma_take([0x103])
    check(r == -1 and raw32[0] == 0x103 and not rxd.armed,
          "a lone port-0Fh write (SYNC 03h): -1, channel stopped")
    t0 = io.time.ms
    q, w, r, mq = dma_take(pre[:4])
    check(r == 4 and 1000 <= io.time.ms - t0 <= 1010 and not rxd.armed,
          "4 words then silence: 4 after the 1000 ms stall, channel stopped")
    q, w, r, mq = dma_take(pre[:3] + [0x103])
    check(r == -4, "3 words then a SYNC (2068 reset mid pre-header): -4")
    q, w, r, mq = dma_take(pre[:9] + [0x103])
    check(r == -10, "a 0Fh write as the 10th word is still caught (-10)")
    mq = FakeMQ()
    rxd.arm(mq)
    ch = rxd.d
    rxd.arm(mq)
    check(rxd.armed and ch.on and rxd.waiting() == 0,
          "arm() twice is one arming (the idle loop calls it every pass)")
    rxd.stop()

    def no_channel():
        raise OSError("no free DMA channel")
    io._DMA = no_channel
    check(io.RX_DMA(raw32) is None, "no free channel: None, and the dispatcher polls")
    io._DMA = None
    check(io.RX_DMA(raw32) is None, "no rp2.DMA (v1.20): None")
    fn = [n for n in ast.parse(open(os.path.join(SRC, "TS", "tspico_io.py"), encoding="utf-8").read())
          .body if isinstance(n, ast.ClassDef) and n.name == "RxDMA"][0]
    take = [n for n in fn.body if isinstance(n, ast.FunctionDef) and n.name == "take"][0]
    bad = [n.lineno for n in ast.walk(take)
           if isinstance(n, (ast.List, ast.Dict, ast.ListComp, ast.JoinedStr))
           or (isinstance(n, ast.Assign) and isinstance(n.value, ast.Attribute)
               and n.value.attr in ("get", "rx_fifo", "active", "stop", "ticks_ms"))]
    check(not bad, "take() builds nothing and stores no bound methods (%s)" % bad)

    print("RX_RING (RX_BLOCK / RX_CAPTURE by DMA, v1.29)")

    class FakeRing:
        """A DMA channel writing RX words into a 1024-word ring at ADDR."""
        ADDR = 0x20010000

        def __init__(self):
            self.mem = {}
            self.on = False
            self.burst = 4          # words the Z80 writes between two looks from core0

        def config(self, read, write, count, ctrl, trigger):
            assert write == self.ADDR and ctrl == "ring"
            self.mq, self.n, self.i, self.on = read, count, 0, bool(trigger)

        def active(self, v=None):
            if v is not None:
                self.on = bool(v)
            return self.on

        @property
        def count(self):
            k = self.burst
            while self.on and self.i < self.n and self.mq.rx and k:
                k -= 1
                self.mem[self.ADDR + ((self.i & 1023) << 2)] = self.mq.rx.pop(0)
                self.i += 1
            if self.i >= self.n:
                self.on = False
            return self.n - self.i

    ch = FakeRing()
    ring = (ch, FakeRing.ADDR, "ring", None, ch.mem)
    blk = bytearray(3000)
    data = [(i * 7) & 0xFF for i in range(3000)]
    mq = FakeMQ(rx=data)
    code, got = io.RX_RING(ring, mq, blk, False, 3000, 1000, 1000)
    check(code == io.RXB_OK and got == 3000 and list(blk) == data and not ch.on,
          "a 3000-byte block through the 1024-word ring: every byte, in order, channel stopped")
    mq = FakeMQ(rx=data[:500] + [0x103])
    code, got = io.RX_RING(ring, mq, blk, False, 3000, 1000, 1000)
    check(code == io.RXB_ABORT and got == 501, "BREAK mid-block: RXB_ABORT after 501 words (%d)" % got)
    t0 = io.time.ms
    mq = FakeMQ(rx=data[:700])
    code, got = io.RX_RING(ring, mq, blk, False, 3000, 1000, 1000)
    check(code == io.RXB_STALL and got == 700 and io.time.ms - t0 >= 1000,
          "the Z80 stops: RXB_STALL after stall_ms, 700 taken")
    mq = FakeMQ(rx=data + data)
    ch.burst = 6000                                      # all at once: core0 away ~260 ms
    code, got = io.RX_RING(ring, mq, bytearray(6000), False, 6000, 1000, 1000)
    ch.burst = 4
    check(code == io.RXB_STALL and got == 0,
          "more than the ring holds before core0 looks: refused, not silently wrong")
    raw = array("H", [0] * 10)
    mq = FakeMQ(rx=pre + [0x41])
    code, got = io.RX_RING(ring, mq, raw, True, 10, 1000, 1000)
    check(code == io.RXB_OK and list(raw) == pre and mq.rx == [0x41],
          "wide (RX_CAPTURE): 9-bit words kept; the word after the n stays in the FIFO")
    name = b"AutoLyzer.tap"
    mq = FakeMQ(rx=[1, len(name)] + list(name) + [0x4C])
    both = bytearray(257)
    code, got = io.RX_RING(ring, mq, both, False, 257, 1000, 1000, 1)
    check(code == io.RXB_OK and got == 2 + len(name) and bytes(both[2:got]) == name
          and mq.rx == [0x4C],
          "len_at=1 (ZX tpi: op, length, name in one run): exactly 2 + 13 words, the rest left (%d)" % got)
    mq = FakeMQ(rx=[1, 0, 0x4C])
    code, got = io.RX_RING(ring, mq, both, False, 257, 1000, 1000, 1)
    check(code == io.RXB_OK and got == 2 and mq.rx == [0x4C], "len_at with a length of 0: 2 words")
    io._ring = ring
    mq = FakeMQ(rx=pre[:3] + [0x103])
    check(io.RX_CAPTURE(mq, raw, 10, 1000) == -4, "RX_CAPTURE by ring: a SYNC after 3 words gives -4")
    mq = FakeMQ(rx=data[:100])
    check(io.RX_BLOCK(mq, blk, 100, 1000, 1000) == (io.RXB_OK, 100), "RX_BLOCK by ring: 100 bytes")
    io._ring = None

    print("MQ_STATUS")
    for st, want in (("idle", 0xFF), ("mid", 0xF7), ("recovered", 0xFB)):
        mq = FakeMQ()
        io.MQ_STATUS(mq, st)
        check(mq.status() == want, "%-9s -> port 0Fh reads %02X" % (st, want))
    check(io.PORT_0F == 0x100 and io.TX_DEPTH == 4, "PORT_0F = 0x100, TX_DEPTH = 4")

    print("MQ_TO_IDLE")
    mq = FakeMQ(rx=[0x41, 0x42], tx=[0x86, 0x01, 0x41, 0x42])
    io.MQ_TO_IDLE(mq)
    check(mq.tx == [0x01] and not mq.rx and mq.status() == 0xFF,
          "stale TX + RX -> TX = [01], RX empty, status FF")
    mq = FakeMQ(tx=[0x01, 0x01])
    io.MQ_TO_IDLE(mq, recovered=True)
    check(mq.tx == [0x01] and mq.status() == 0xFB,
          "recovered=True -> exactly one pre-load, status FB")
    mq = FakeMQ()
    mq.y = 0
    io.MQ_TO_IDLE(mq, status=False)
    check(mq.tx == [0x01] and mq.status() == 0x00,
          "status=False -> pre-load staged, Y left BUSY (the Z80 stays held)")

    print("dispatcher (source)")
    for name in ("TS/tspico.py", "dev_tspico.py"):
        src = open(os.path.join(SRC, name), encoding="utf-8").read().replace("\r", "")
        body = src[src.index("def TS2068_IO"):]
        check("got = RX_CAPTURE(MQ, pre_raw, 10, 1000)" in body,
              "%s: the main loop reads the pre-header through RX_CAPTURE" % name)
        loop = body[body.index("    failures = []"):]
        check("rxd.arm(MQ)" in loop and "rxd.waiting()" in loop and "got = rxd.take(1000)" in loop,
              "%s: ...or, where there is DMA, through RxDMA: armed while idle, taken" % name)
        sync = loop[loop.index("if got < 0:"):loop.index("if got != 10:")]
        check(sync.index("rxd.arm(MQ)") < sync.index('MQ_STATUS(MQ, "idle")'),
              "%s: after a SYNC the channel is armed BEFORE IDLE (the pre-header follows at once)" % name)
        exc = loop[loop.index("except Exception as err:"):]
        check(exc.index("rxd.stop()") < exc.index("MQ_TO_IDLE(MQ, recovered=True)"),
              "%s: a service-loop restart stops the channel before draining RX" % name)
        check(not re.search(r"for i in r1:\s*\n\s*pre\[i\] = MQ\.get\(\)", body),
              "%s: the old blocking pre-header loop is gone" % name)
        sync = body[body.index("if got < 0:"):body.index("if got != 10:")]
        order = [sync.find("MQ_TO_IDLE(MQ, status=False)"), sync.find("LOG("),
                 sync.find('MQ_STATUS(MQ, "idle")'), sync.find("continue")]
        check(-1 not in order and order == sorted(order),
              "%s: on SYNC it resets, logs, THEN says IDLE, then loops straight back" % name)

    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
