"""Host-side test for LOAD_TS (issue #51 stage 2) -- CPython, no Pico.

Runs the PRODUCTION TS/tspico_io.LOAD_TS against a real TAP file and a Z80
that follows the EXROM's LOAD sequence (v1.7, and the 1.8b ROM's BREAK
abort). The simulated PIO has 4-deep FIFOs, A0 in bit 8 of every Z80 write,
auto-busy on every write, and FAILS the test on any put() into a full TX
FIFO -- which blocks forever on a Pico. Z80 and LOAD_TS run interleaved:
every FIFO call LOAD_TS makes advances the Z80 one step.

What it pins:
  * header and data blocks still load (flag, content, CRC, both echoes,
    final status + one pre-load, tape position advanced);
  * BREAK mid-block: the abort is heard in the send loop, no put() into a
    full TX, straight back to idle (TX = [01], status FF) -- the 1.8b ROM
    then raises Report D -- and the next LOAD works first time;
  * BREAK in the ready-wait before the data: same, "read 0-4 bytes";
  * the Z80 going silent mid-block: RECOVERED (FB) after the stall, no hang;
  * the watchdog path (kill) is unchanged;
  * a v1.7 LOAD, which never writes 0Fh, behaves exactly as before.

Run:  python3 src/test/load_ts_hosttest.py
"""

import os
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from sync_io_hosttest import install_fakes, FakeTime          # noqa: E402

READY, IDLE, RECOVERED = 0x40, 0x08, 0x04


class PutWouldBlock(AssertionError):
    pass


class FakePIO:
    """TS_IO_DUAL + a Z80 script, advanced one step per FIFO call."""

    def __init__(self):
        self.tx, self.rx = [], []
        self.y = 0xFFFFFFFF
        self.dropped = 0
        self.script = None
        self.pending = None
        self.result = None
        self.tx_at_ready = []       # TX contents each time a READY wait passed

    def rx_fifo(self):
        self.pump()
        return min(len(self.rx), 4)

    def tx_fifo(self):
        self.pump()
        return len(self.tx)

    def get(self):
        for _ in range(100000):
            if self.rx:
                return self.rx.pop(0)
            self.pump()
        raise AssertionError("get() on an RX FIFO that never filled")

    def put(self, b):
        if len(self.tx) >= 4:
            raise PutWouldBlock("put() into a full TX FIFO blocks forever on a Pico")
        self.tx.append(b & 0xFF)
        self.pump()

    def exec(self, s):
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
        elif t in ("mov(osr,null)",):
            pass
        else:
            raise AssertionError("unexpected exec %r" % s)

    def status(self):
        return self.y & 0xFF

    def run(self, gen):
        self.script, self.result = gen, None
        self._advance(None)

    def _advance(self, v):
        try:
            self.pending = self.script.send(v)
        except StopIteration as e:
            self.result, self.script, self.pending = e.value, None, None

    def pump(self):
        if self.script is None:
            return
        op = self.pending
        k = op[0]
        if k == "out":
            if len(self.rx) < 4:
                self.rx.append(op[2] | (0x100 if op[1] == 0x0F else 0))
            else:
                self.dropped += 1
            self.y = 0
            self._advance(None)
        elif k == "in":
            if self.tx:
                self._advance(self.tx.pop(0))
        elif k == "wait":
            need, left = op[1], op[2]
            if (self.status() & need) == need:
                self.tx_at_ready.append(list(self.tx))
                self._advance(self.status())
            elif left <= 0:
                self._advance(None)
            else:
                self.pending = ("wait", need, left - 1)
        elif k == "call":
            op[1]()
            self._advance(None)
        elif k == "stop":
            pass                                    # the Z80 has gone away
        else:
            raise AssertionError(op)

    def finish(self, steps=200000):
        for _ in range(steps):
            if self.script is None or self.pending == ("stop",):
                return
            self.pump()


def out(port, v):
    return ("out", port, v)


def ready_wait():
    st = yield ("wait", READY, 20000)
    if st is None:
        return "J"
    if not st & RECOVERED:
        return "T"
    return None


def z80_load(flag, length, break_at=None, stop_at=None, on_byte=None):
    """The EXROM after the dispatcher has taken the pre-header: 19C7 status
    read (no wait), 19D4 ready-wait, 1924 echo, the data loop with the 1.8b
    BREAK check every 256 bytes, CRC, 1A02 echo, 1A05 ready-wait, status."""
    st = yield ("in",)
    if st != 0x01:
        return "st%02X" % st
    if break_at == 0:                               # BREAK in the ready-wait
        yield out(0x0F, 0x03)
        yield ("wait", READY | IDLE, 3000)
        return "D"
    r = yield from ready_wait()
    if r:
        return r
    yield out(0x0E, flag)
    got = yield ("in",)
    if got != flag:
        return "R"
    parity = flag
    for i in range(length):
        if stop_at is not None and i == stop_at:
            yield ("stop",)
        if break_at is not None and i >= break_at and ((length - 1 - i) & 0xFF) == 0xFF:
            yield out(0x0F, 0x03)                   # BRK_ABORT
            yield ("wait", READY | IDLE, 3000)
            return "D"
        if on_byte is not None and i == on_byte[0]:
            yield ("call", on_byte[1])
        b = yield ("in",)
        parity ^= b
    crc = yield ("in",)
    if crc != parity:
        return "R"
    yield out(0x0E, crc)
    r = yield from ready_wait()
    if r:
        return r
    st = yield ("in",)
    return "ok" if st == 0x01 else "st%02X" % st


def tap_block(flag, content):
    body = bytes([flag]) + bytes(content)
    c = 0
    for b in body:
        c ^= b
    body += bytes([c])
    return bytes([len(body) & 0xFF, len(body) >> 8]) + body


results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg)


def main():
    install_fakes()
    sys.path.insert(0, SRC)
    import TS.tspico_io as io
    io.time = FakeTime()

    data = bytes((i * 7 + 3) & 0xFF for i in range(3000))
    header = bytes([3]) + b"loadtest  " + bytes([len(data) & 0xFF, len(data) >> 8, 0, 0x80, 0, 0])
    tap = tap_block(0x00, header) + tap_block(0xFF, data)
    tmp = tempfile.NamedTemporaryFile(suffix=".tap", delete=False)
    tmp.write(tap)
    tmp.close()
    real_open = open
    io.open = lambda path, mode="r": real_open(tmp.name if path == "/TMP/temp.tap" else path, mode)

    tsp = types.SimpleNamespace(f_name="test.tap", totlen=len(tap), offset=0, tap_idx=0,
                                LOG_LEVEL=0, ld_start=-1, ld_wrapped=False)

    def load(pio, flag, length, **kw):
        """The dispatcher's side: pre-load staged, READY after the pre-header,
        then LOAD_TS; the Z80 script runs alongside."""
        pio.tx = [0x01]
        pio.y = 0          # BUSY: the pre-header OUTs dropped it, and the
        pio.rx = []        # dispatcher no longer says READY for a LOAD
        pio.tx_at_ready = []
        io.log_entries = ""
        io.kill = False
        io.dead = True
        io.busy = False
        pio.run(z80_load(flag, length, **kw))
        pre = bytearray([flag, 1, 0xFF, 0x34, 0x12, 0, 0x80, 0, 0, 0])
        io.LOAD_TS(pre, pio, tsp)
        pio.finish()
        return pio.result, io.log_entries

    def idle(pio, st=0xFF):
        return pio.tx == [0x01] and not pio.rx and pio.status() == st

    pio = FakePIO()
    try:
        print("READY only once the block is queued (the R-after-BREAK race)")
        r, _ = load(pio, 0x00, len(header))
        first = pio.tx_at_ready[0] if pio.tx_at_ready else None
        check(r == "ok" and first and first[0] == 0x00 and len(first) == 4,
              "header: when the Z80 first sees READY, TX already holds the flag + 3 bytes (%s)" % first)
        tsp.offset, tsp.tap_idx = 0, 0
        for name in ("TS/tspico.py", "dev_tspico.py"):
            src = open(os.path.join(SRC, name), encoding="utf-8").read().replace("\r", "")
            body = src[src.index("got = RX_CAPTURE(MQ, pre_raw, 10, 1000)"):src.index("_pre_snapshot = list(pre)")]
            check("if not ((pre[0] == 0 or pre[0] == 255) and pre[1] < 10" in body and "MQ_READY()" in body,
                  "%s: the dispatcher skips READY after a LOAD pre-header (LOAD_TS says it)" % name)

        print("normal LOAD (header, then data)")
        r, _ = load(pio, 0x00, len(header) + 0)
        check(r == "ok" and tsp.offset == len(header) + 4 and tsp.tap_idx == 1 and idle(pio),
              "header block: loaded, one pre-load left, status FF, tape at the data block (%s)" % r)
        r, _ = load(pio, 0xFF, len(data))
        first = pio.tx_at_ready[0] if pio.tx_at_ready else None
        check(r == "ok" and tsp.offset == 0 and idle(pio) and first and first[0] == 0xFF,
              "data block: loaded, flag waiting at READY, tape wrapped to the start (%s, offset %d)"
              % (r, tsp.offset))

        print("BREAK mid-block (1.8b ROM)")
        load(pio, 0x00, len(header))
        off = tsp.offset
        r, log = load(pio, 0xFF, len(data), break_at=1000)
        check(r == "D", "the Z80 gets READY + IDLE and raises Report D (%s)" % r)
        check(idle(pio), "harness state: TX = [01], RX empty, status FF (%s %s %02X)"
              % (pio.tx, pio.rx, pio.status()))
        check("stopped by BREAK" in log and "of 3002 bytes" in log,
              "logged: " + log.strip().split("] ", 1)[-1])
        check(tsp.offset == off, "tape left at the data block the user broke out of")
        r1, _ = load(pio, 0x00, len(header))
        check(r1 == "ok", "next LOAD \"\" (a header) works first time, searching past the data block (%s)" % r1)
        r2, _ = load(pio, 0xFF, len(data))
        check(r2 == "ok" and pio.tx_at_ready and pio.tx_at_ready[0][0] == 0xFF,
              "...and its data block too, flag waiting at READY -- the step that failed on hardware (%s)" % r2)

        print("BREAK in the ready-wait before the data")
        load(pio, 0x00, len(header))
        r, log = load(pio, 0xFF, len(data), break_at=0)
        read = int(log.split("read ")[1].split(" of")[0]) if "read " in log else -1
        check(r == "D" and idle(pio) and 0 <= read <= 4,
              "Report D, idle, and the log says the Z80 read %d bytes (0-4 = before the data)" % read)
        load(pio, 0x00, len(header))
        load(pio, 0xFF, len(data))

        print("the Z80 goes silent mid-block (2068 reset, old ROM)")
        load(pio, 0x00, len(header))
        r, log = load(pio, 0xFF, len(data), stop_at=1500)
        check(idle(pio, 0xFB) and "stalled -> RECOVERED" in log,
              "TX_ROOM's own stall bound ends it: RECOVERED (FB), one pre-load, no hang")
        tsp.offset, tsp.tap_idx = 0, 0

        print("watchdog path unchanged")
        load(pio, 0x00, len(header))

        def fire():
            io.kill = True
        r, log = load(pio, 0xFF, len(data), stop_at=2000, on_byte=(1999, fire))
        check("LOAD_TS failed" in log and "re-armed" in log,
              "kill during the block takes ABORT_TX + REARM_AFTER_LOAD_ABORT as before")
        tsp.offset, tsp.tap_idx = 0, 0

        print("v1.7 LOAD: no port-0Fh writes, nothing changes")
        r0, _ = load(pio, 0x00, len(header))
        r1, _ = load(pio, 0xFF, len(data))
        check(r0 == r1 == "ok" and idle(pio), "header + data load as before (%s, %s)" % (r0, r1))

        check(pio.dropped == 0, "no RX overflow anywhere (%d)" % pio.dropped)
        print("  PASS  no put() into a full TX FIFO (FakePIO raises if one happens)")
    except PutWouldBlock as e:
        check(False, str(e))
    finally:
        os.unlink(tmp.name)

    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
