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
