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
  * no watchdog: LOAD_TS starts no thread;
  * a v1.7 LOAD, which never writes 0Fh, behaves exactly as before;
  * a damaged or impossible block (bad checksum, wrong length, zero length,
    past the end of the file) is Report R and leaves the protocol idle with
    one pre-load: a data block at once; a header, which the ROM's search
    retries after any failure, via the error staged for that retry -- with
    and without SYNC -- and the tape moves past the block;
  * a search skips every block of the wrong type in one request, and one
    that never matches ends in R after a lap;
  * a BASIC header reaches the Z80 byte for byte as it is on the tape --
    "no autorun" (line >= 32768) included. The ROM itself skips the autorun
    for those (EXROM 06C3: AND 0C0h), so LOAD_TS no longer rewrites them;
    its old rewrite also broke the CRC of any header whose high byte wasn't
    exactly 80h (Report R).

Run:  python3 src/test/load_ts_hosttest.py
"""

import ast
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
    """TS_IO_DUAL + a Z80 script, advanced one step per FIFO call.

    DEPTH is the FIFOs' size: 4 for v2's PIO. deep_queue_hosttest.py sets it
    to 1024 for the v3 card's tsbus queues, whose tx_fifo()/rx_fifo() then
    report their real levels, and whose put_block() it models."""
    DEPTH = 4

    def __init__(self):
        self.tx, self.rx = [], []
        self.y = 0xFFFFFFFF
        self.dropped = 0
        self.script = None
        self.pending = None
        self.result = None
        self.tx_at_ready = []       # TX contents each time a READY wait passed
        self.z80_every = 1          # the Z80 reads once per this many FIFO calls
        self._tick = 0

    def rx_fifo(self):
        self.pump()
        return min(len(self.rx), self.DEPTH)

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
        if len(self.tx) >= self.DEPTH:
            raise PutWouldBlock("put() into a full TX FIFO blocks forever on a Pico")
        self.tx.append(b & 0xFF)
        self.pump()

    def put_block(self, buf, wait_ms=-1):
        """tsbus.MQ.put_block: queue what fits; with wait_ms, wait for room
        while the Z80 reads, and stop early when an OUT is in RX or the Z80
        makes no progress (wait_ms ran out). Returns the bytes queued."""
        mv = memoryview(buf)
        i = 0
        stuck = 0
        while i < len(mv):
            room = self.DEPTH - len(self.tx)
            if room:
                k = min(room, len(mv) - i)
                self.tx.extend(bytes(mv[i:i + k]))
                i += k
                stuck = 0
                continue
            if wait_ms == 0 or (wait_ms > 0 and self.rx):
                break
            before = len(self.tx)
            self.pump()
            if len(self.tx) == before:
                stuck += 1
                if stuck > 1000:
                    if wait_ms < 0:
                        raise PutWouldBlock("put_block() with no wait into a queue nobody reads")
                    break
        return i

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
            if len(self.rx) < self.DEPTH:
                self.rx.append(op[2] | (0x100 if op[1] == 0x0F else 0))
            else:
                self.dropped += 1
            self.y = 0
            self._advance(None)
        elif k == "in":
            self._tick += 1
            if self.tx and self._tick % self.z80_every == 0:
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


class FakeDMA:
    """rp2.DMA streaming bytes into FakePIO's TX FIFO, paced by its room --
    the "TX not full" DREQ. It moves whenever LOAD_TS looks at it (and at
    the trigger), which is when a real channel would have moved anyway."""

    made = []

    def __init__(self):
        self.buf, self.pio, self.i, self.n, self.on = None, None, 0, 0, False
        FakeDMA.made.append(self)

    def pack_ctrl(self, **kw):
        assert kw.get("size") == 0 and kw.get("inc_read") and not kw.get("inc_write"), kw
        assert kw.get("treq_sel") == 0, kw              # PIO0 SM0's TX DREQ
        return 1

    def config(self, read, write, count, ctrl, trigger):
        self.buf, self.pio, self.i, self.n = read, write, 0, count
        self.on = bool(trigger)
        self._move()

    def _move(self):
        while self.on and self.i < self.n and len(self.pio.tx) < getattr(self.pio, "DEPTH", 4):
            self.pio.tx.append(self.buf[self.i])
            self.i += 1
            self.pio.pump()
        if self.i >= self.n:
            self.on = False

    def active(self, v=None):
        if v is not None:
            self.on = bool(v)
            self.stopped = not v            # as on hardware: count is meaningless after
            return None
        self.pio.pump()
        self._move()
        return self.on

    @property
    def count(self):
        if getattr(self, "stopped", False):
            return 0
        self._move()
        return self.n - self.i

    def close(self):
        self.on = False
        self.closed = True


def out(port, v):
    return ("out", port, v)


def ready_wait():
    st = yield ("wait", READY, 20000)
    if st is None:
        return "J"
    if not st & RECOVERED:
        return "T"
    return None


def z80_load(flag, length, break_at=None, stop_at=None, on_byte=None, seen=None):
    """The EXROM after the dispatcher has taken the pre-header: 19C7 status
    read (no wait), 19D4 ready-wait, 1924 echo, the data loop with the 1.8b
    BREAK check every 256 bytes, CRC, 1A02 echo, 1A05 ready-wait, status.

    A block that fails -- its flag (1A20), its checksum (19FE -> 0815, which
    still echoes the checksum it computed) -- is Report R for a data block,
    but a header LOAD's search just asks again (04DD: CALL 00FC / JR NC):
    "retry". At 19C7 anything but 00/01 is Report R (1A35 -> 1C3E) and 00 is
    J (1C20), whatever the request."""
    st = yield ("in",)
    if st != 0x01:
        return "R" if st else "J"
    fail = "retry" if flag == 0x00 else "R"
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
        return fail
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
        if seen is not None:
            seen.append(b)
        parity ^= b
    crc = yield ("in",)
    if crc != parity:
        yield out(0x0E, parity)
        return fail
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
    # The one-shot tape a native file becomes (LOAD "f:..."): other lengths
    # than the mounted tape's, so a block served from the wrong tape fails
    # the Z80's checksum instead of passing by accident.
    from TS import native as N
    ndata = bytes((i * 13 + 1) & 0xFF for i in range(777))
    ntap = N.as_tap(N.T_PROGRAM, len(ndata), 10, len(ndata), ndata, "advent")
    ntmp = tempfile.NamedTemporaryFile(suffix=".tap", delete=False)
    ntmp.write(ntap)
    ntmp.close()
    real_open = open
    paths = {"/TMP/temp.tap": tmp.name, "/TMP/native.tap": ntmp.name}
    io.open = lambda path, mode="r": real_open(paths.get(path, path), mode)

    tsp = types.SimpleNamespace(f_name="test.tap", totlen=len(tap), offset=0, tap_idx=0,
                                LOG_LEVEL=0, ld_start=-1, ld_wrapped=False)

    def load(pio, flag, length, serve=False, sync=True, **kw):
        """The dispatcher's side: pre-load staged, READY after the pre-header,
        then LOAD_TS; the Z80 script runs alongside. sync: the 2.x ROM's
        SYNC flushed TX and staged FIRST_STATUS(); without it (older ROMs)
        whatever the last command left in TX is what the Z80 reads first."""
        if sync:
            pio.tx = [io.FIRST_STATUS()]
        pio.y = 0          # BUSY: the pre-header OUTs dropped it, and the
        pio.rx = []        # dispatcher no longer says READY for a LOAD
        pio.tx_at_ready = []
        io.log_entries = ""
        io.dead = True
        io.busy = False
        pio.run(z80_load(flag, length, **kw))
        pre = bytearray([flag, 1, 0xFF, 0x34, 0x12, 0, 0x80, length & 0xFF, length >> 8, 0])
        (io.LOAD_SERVE if serve else io.LOAD_TS)(pre, pio, tsp)
        pio.finish()
        return pio.result, io.log_entries

    def idle(pio, st=0xFF):
        return pio.tx == [0x01] and not pio.rx and pio.status() == st

    pio = FakePIO()
    try:
        print("READY only once the block is queued (the R-after-BREAK race)")
        r, _ = load(pio, 0x00, len(header))
        first = pio.tx_at_ready[0] if pio.tx_at_ready else None
        full = min(FakePIO.DEPTH, len(header) + 2)  # v2: flag + 3; v3's queue: the whole block
        check(r == "ok" and first and first[0] == 0x00 and len(first) == full,
              "header: when the Z80 first sees READY, TX already holds the first %d bytes (%s)" % (full, first))
        tsp.offset, tsp.tap_idx = 0, 0
        for name in ("TS/tspico.py", "dev_tspico.py"):
            src = open(os.path.join(SRC, name), encoding="utf-8").read().replace("\r", "")
            body = src[src.index("got = RX_CAPTURE(MQ, pre_raw, 10, 1000)"):src.index("_pre_snapshot = list(pre)")]
            i = body.index("if pre[0] not in (PRE_HEADER, PRE_DATA, PRE_CMD):")
            check("MQ_READY()" in body and "pre[1] < 10" not in body[i:body.index("MQ_READY()", i)],
                  "%s: the dispatcher skips READY after EVERY LOAD pre-header, headerless too"
                  " (LOAD_TS says it)" % name)

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

        print("no watchdog (stage 5)")
        load(pio, 0x00, len(header))
        r, _ = load(pio, 0xFF, len(data))
        gone = [f for f in ("START_WATCHDOG", "WATCHDOG", "ABORT_TX", "STOP_WATCHDOG") if hasattr(io, f)]
        check(r == "ok" and not gone, "header + data load; no watchdog left in tspico_io (%s)" % gone)
        tsp.offset, tsp.tap_idx = 0, 0
        load(pio, 0x00, len(header))

        r, log = load(pio, 0xFF, len(data), stop_at=2000)
        check(idle(pio, 0xFB) and "stalled -> RECOVERED" in log,
              "the Z80 stops reading mid-block: a stall, RECOVERED, one pre-load")
        tsp.offset, tsp.tap_idx = 0, 0

        print("no allocation while the Z80 streams (R at 15772 of 16096, 2026-09-26)")
        io_src = open(os.path.join(SRC, "TS", "tspico_io.py"), encoding="utf-8").read().replace("\r", "")
        tree = ast.parse(io_src)
        fns = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
        allocs = []
        for name in ("TX_ROOM", "ECHO_KEEP"):
            for n in ast.walk(fns[name]):
                if isinstance(n, (ast.List, ast.Dict, ast.ListComp, ast.JoinedStr, ast.BinOp)) and \
                        not (isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.BitAnd))):
                    allocs.append((name, n.lineno))
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "append":
                    allocs.append((name, n.lineno))
                # `txf = MQ.tx_fifo` allocates a bound method on every call:
                # 32 bytes/byte in TX_ROOM filled the heap every ~6.5 KB and
                # each GC cost a LOAD ~110 bytes (hardware, 2026-09-27).
                if isinstance(n, ast.Assign) and isinstance(n.value, ast.Attribute):
                    allocs.append((name, n.lineno, "bound method"))
        check(not allocs, "TX_ROOM / ECHO_KEEP build no lists, strings, appends or bound methods (%s)" % allocs)
        body = io_src[io_src.index("def LOAD_TS("):io_src.index("def LOAD_TS(") + 40000]
        loop = body[body.index("    primed = False"):body.index("# Phase 2")]
        check(".append(" not in loop and "LOG" not in loop and "%" not in loop,
              "LOAD_TS's stream loops: no append, no LOG, no string formatting")
        check(body.index("gc.collect()") < body.index("    primed = False"),
              "LOAD_TS collects garbage before streaming, while the Z80 waits for READY")
        zx = io_src[io_src.index("def LOAD_ZX("):io_src.index("def LOAD_ZX_C(")]
        check("rd(el)" not in loop and "rd(el)" not in zx and "rd(buf)" in loop and "rd(buf)" in zx,
              "LOAD_TS and LOAD_ZX read the file a chunk at a time, not a byte per call "
              "(v1.29: TX ran dry, hardware 2026-10-02)")

        print("TX-dry counter")
        load(pio, 0x00, len(header))
        pio.z80_every = 3                       # a Z80 slower than the Pico, as on hardware
        r, log = load(pio, 0xFF, len(data))
        pio.z80_every = 1
        check(r == "ok" and "ran dry" not in log,
              "Z80 slower than the Pico: TX never runs dry, nothing logged (%s)" % r)
        if FakePIO.DEPTH == 4:                  # v2's per-byte loop counts them; v3 streams in C
            load(pio, 0x00, len(header))
            r, log = load(pio, 0xFF, len(data))     # the fake Z80 keeps up with every put
            check("ERROR: LOAD TX ran dry" in log and "of 3002" in log,
                  "Z80 as fast as the Pico: the near-misses are logged with the first byte (%r)"
                  % log.strip().splitlines()[:1])

        print("v1.7 LOAD: no port-0Fh writes, nothing changes")
        r0, _ = load(pio, 0x00, len(header))
        r1, _ = load(pio, 0xFF, len(data))
        check(r0 == r1 == "ok" and idle(pio), "header + data load as before (%s, %s)" % (r0, r1))

        print("native one-shot tape (LOAD \"f:...\")")
        tsp.native = None
        r0, _ = load(pio, 0x00, len(header), serve=True)
        mounted = (tsp.f_name, tsp.totlen, tsp.offset, tsp.tap_idx)
        check(r0 == "ok" and tsp.offset == len(header) + 4,
              "nothing armed: LOAD_SERVE is LOAD_TS on the mounted tape (%s)" % r0)
        tsp.native = dict(op=1, session=0x1234, tap="/TMP/native.tap", totlen=len(ntap))
        r1, _ = load(pio, 0x00, 17, serve=True)
        check(r1 == "ok" and tsp.native is not None, "armed: the native header block is served (%s)" % r1)
        check((tsp.f_name, tsp.totlen, tsp.offset, tsp.tap_idx) == mounted and tsp.load_file is None,
              "  and the mounted tape's state is untouched between the blocks")
        r2, _ = load(pio, 0xFF, len(ndata), serve=True)
        check(r2 == "ok" and tsp.native is None and idle(pio),
              "the native data block is served, then the arm is used up (%s)" % r2)
        check((tsp.f_name, tsp.totlen, tsp.offset, tsp.tap_idx) == mounted,
              "  the mounted tape carries on exactly where it was")
        r3, _ = load(pio, 0xFF, len(data), serve=True)
        check(r3 == "ok", "the next LOAD reads the mounted tape again (%s)" % r3)
        tsp.native = dict(op=1, session=0x9999, tap="/TMP/native.tap", totlen=len(ntap))
        r4, _ = load(pio, 0x00, len(header), serve=True)
        check(r4 == "ok" and tsp.native is None,
              "an arm for another session is stale: dropped, the mounted tape served (%s)" % r4)
        tsp.native = dict(op=0, path="/sd/TAP/x", session=0x1234, refuse=False)
        r5, _ = load(pio, 0xFF, len(data), serve=True)
        check(r5 == "ok" and tsp.native is not None, "a SAVE arm doesn't touch a LOAD (%s)" % r5)
        tsp.native = None

        print("BASIC headers reach the Z80 exactly as on the tape (autorun patch removed)")
        saved_tap, saved_len = paths["/TMP/temp.tap"], tsp.totlen
        for name, hi, lo in (("saved without LINE (80h, as the 2068 ROM writes it)", 0x80, 0x00),
                             ("no autorun written as FFFFh (some tape tools)", 0xFF, 0xFF),
                             ("LINE 10 (a real autorun)", 0x00, 0x0A)):
            basic = bytes([0]) + b"autorun   " + bytes([10, 0, lo, hi, 10, 0])
            btap = tempfile.NamedTemporaryFile(suffix=".tap", delete=False)
            btap.write(tap_block(0x00, basic))
            btap.close()
            paths["/TMP/temp.tap"] = btap.name
            tsp.totlen = len(tap_block(0x00, basic))
            tsp.offset, tsp.tap_idx, tsp.ld_start, tsp.ld_wrapped = 0, 0, -1, False
            seen = []
            r, _ = load(pio, 0x00, len(basic), seen=seen)
            check(r == "ok" and bytes(seen) == basic,
                  "%s: CRC good, header unchanged (%s, autorun bytes %s)"
                  % (name, r, bytes(seen[13:15]).hex() if len(seen) >= 15 else seen))
        paths["/TMP/temp.tap"], tsp.totlen = saved_tap, saved_len
        tsp.offset, tsp.tap_idx, tsp.ld_start, tsp.ld_wrapped = 0, 0, -1, False

        print("the end of the tape, and blocks that can't be blocks (hardware, 2026-09-30)")
        tsp.offset, tsp.tap_idx = len(tap), 2
        r, _ = load(pio, 0x00, len(header))
        check(r == "ok" and tsp.tap_idx == 1 and idle(pio),
              "a LOAD that starts at the end of the tape rewinds and loads the header (%s)" % r)
        tsp.offset, tsp.tap_idx, tsp.ld_start, tsp.ld_wrapped = 0, 0, -1, False

        print("damaged and impossible blocks: Report R, then a clean protocol (archive tapes, 2026-10-04)")

        def mount(blob):
            f = tempfile.NamedTemporaryFile(suffix=".tap", delete=False)
            f.write(blob)
            f.close()
            paths["/TMP/temp.tap"] = f.name
            tsp.totlen = len(blob)
            tsp.offset, tsp.tap_idx, tsp.ld_start, tsp.ld_wrapped = 0, 0, -1, False
            return f.name

        def until_report(pio, flag, length, again=("retry",), **kw):
            """One LOAD statement: the ROM asks again while a header search
            fails (04DD) -- or, with again=("retry", "ok"), while the name
            doesn't match. Returns the outcomes and every call's log."""
            seq, logs = [], ""
            for _ in range(12):
                r, log = load(pio, flag, length, **kw)
                seq.append(r)
                logs += log
                if r not in again:
                    break
            return seq, logs

        def bad_crc(blk):
            return blk[:-1] + bytes([blk[-1] ^ 0x5A])

        prog = bytes([0]) + b"prog      " + bytes([4, 0, 0, 0x80, 4, 0])
        good = tap_block(0x00, prog) + tap_block(0xFF, b"\x01\x02\x03\x04")
        made = []
        for name, blob, flag, length in (
                ("one header-flag block, 7625 bytes, bad checksum",
                 bad_crc(tap_block(0x00, bytes(range(256)) * 29 + bytes(201))), 0x00, 17),
                ("the file starts 00 00 (a zero-length block)", b"\x00\x00" + good, 0x00, 17),
                ("a 17-byte header with a bad checksum", bad_crc(tap_block(0x00, prog)) + good, 0x00, 17),
                ("a 6-byte header-flag block (the length isn't 17)",
                 bad_crc(tap_block(0x00, b"\x01\x02\x03\x04")) + good, 0x00, 17),
                ("a length past the end of the file", b"\xff\x7f\x00" + bytes(40), 0x00, 17)):
            made.append(mount(blob))
            seq, log = until_report(pio, flag, length)
            check(seq == ["retry", "R"] and idle(pio) and "Report R" in log,
                  "%s: the ROM fails it, asks again, reads R first; then idle, TX = [01] (%s %s)"
                  % (name, seq, pio.tx))
        # The tape moved past the damaged block, as a real one would have:
        # after the zero-length block, the next LOAD "" loads the program.
        mount(b"\x00\x00" + good)
        until_report(pio, 0x00, 17)
        r0, _ = load(pio, 0x00, 17)
        r1, _ = load(pio, 0xFF, 4)
        check(r0 == r1 == "ok" and idle(pio),
              "after the R, the next LOAD \"\" goes on past the bad block and loads (%s, %s)" % (r0, r1))

        print("  without SYNC (ROMs before 1.8b): the error waits in TX for the retry")
        mount(bad_crc(tap_block(0x00, prog)) + good)
        seq, _ = until_report(pio, 0x00, 17, sync=False)
        check(seq == ["retry", "R"] and idle(pio), "retry, then R, idle (%s %s)" % (seq, pio.tx))
        r0, _ = load(pio, 0x00, 17, sync=False)
        r1, _ = load(pio, 0xFF, 4, sync=False)
        check(r0 == r1 == "ok" and idle(pio), "  and the next LOAD loads, nothing stray in TX (%s, %s)" % (r0, r1))

        print("  a damaged data block: R at once, nothing left behind")
        for name, blob in (("bad checksum", tap_block(0x00, prog) + bad_crc(tap_block(0xFF, b"\x01\x02\x03\x04"))),
                           ("longer than its header says", tap_block(0x00, prog) + tap_block(0xFF, bytes(10))),
                           ("shorter than its header says", tap_block(0x00, prog) + tap_block(0xFF, b"\x01"))):
            mount(blob)
            r0, _ = load(pio, 0x00, 17)
            r1, log = load(pio, 0xFF, 4)
            check(r0 == "ok" and r1 == "R" and idle(pio) and "Report R" in log,
                  "%s: header loads, the data block is Report R, idle (%s, %s %s)" % (name, r0, r1, pio.tx))
            r2, _ = load(pio, 0x00, 17)
            check(r2 == "ok", "  and the next LOAD \"\" is served normally (%s)" % r2)

        print("  the staged error is one-shot")
        mount(bad_crc(tap_block(0x00, prog)) + good)
        r, _ = load(pio, 0x00, 17)
        io.time.ms += 3000                      # no retry came (BREAK): it's stale
        r2, _ = load(pio, 0x00, 17)
        check(r == "retry" and r2 == "ok" and idle(pio),
              "seconds later the next LOAD gets 01, not the old R (%s, %s)" % (r, r2))

        print("  a search skips every block of the wrong type, not just one")
        made.append(mount(good + tap_block(0xFF, b"xx") + tap_block(0xFF, b"yy") + tap_block(0xFF, b"zz") + good))
        tsp.offset = len(good)                  # at the first stray data block
        seen = []
        r, _ = load(pio, 0x00, 17, seen=seen)
        check(r == "ok" and bytes(seen) == prog and tsp.offset == len(good) + 3 * 6 + 21,
              "three data blocks passed in one request, the header served (%s, offset %d)" % (r, tsp.offset))

        print("  a search that never matches ends in R (the 2.1 ROM can't show 8 there)")
        mount(good)
        seq, log = until_report(pio, 0x00, 17, again=("retry", "ok"))   # LOAD "nosuch"
        check(seq[-1] == "R" and len(seq) <= 4 and idle(pio) and "no matching block" in log,
              "after one lap: R, idle (%s)" % seq)
        tsp.offset, tsp.tap_idx, tsp.ld_start, tsp.ld_wrapped = 0, 0, -1, False

        print("  no block of the requested type in the whole file")
        mount(tap_block(0x00, prog))
        r, log = load(pio, 0xFF, 4)
        check(r == "R" and idle(pio) and "no block of type FFh" in log, "data request: R, idle (%s)" % r)
        paths["/TMP/temp.tap"], tsp.totlen = tmp.name, len(tap)
        for f in made:
            os.unlink(f)
        tsp.offset, tsp.tap_idx, tsp.ld_start, tsp.ld_wrapped = 0, 0, -1, False

        if FakePIO.DEPTH == 4:                  # v2 only: the v3 card has no DMA (deep_queue_hosttest)
            print("by DMA (rp2.DMA, MicroPython v1.22+): the same LOADs")
            io._DMA = FakeDMA
            FakeDMA.made.clear()
            tsp.offset, tsp.tap_idx, tsp.ld_start, tsp.ld_wrapped = 0, 0, -1, False
            r0, _ = load(pio, 0x00, len(header))
            first = pio.tx_at_ready[0] if pio.tx_at_ready else None
            r1, log = load(pio, 0xFF, len(data))
            check(r0 == r1 == "ok" and idle(pio) and len(FakeDMA.made) == 2,
                  "header + data load, each block by its own channel (%s, %s, %d)"
                  % (r0, r1, len(FakeDMA.made)))
            check(first and first[0] == 0x00 and len(first) == 4,
                  "  READY once TX is full: the flag + 3 bytes waiting (%s)" % first)
            check(all(getattr(d, "closed", False) for d in FakeDMA.made),
                  "  every channel closed afterwards (they are a shared resource)")
            load(pio, 0x00, len(header))
            off = tsp.offset
            r, log = load(pio, 0xFF, len(data), break_at=1000)
            check(r == "D" and idle(pio) and "stopped by BREAK" in log and tsp.offset == off,
                  "BREAK mid-block: heard while the DMA runs, Report D, idle (%s)" % r)
            check(FakeDMA.made[-1].i < len(data), "  the channel was stopped part way (%d of %d)"
                  % (FakeDMA.made[-1].i, len(data) + 1))
            read = int(log.split("read ")[1].split(" of")[0]) if "read " in log else -1
            check(0 < read < len(data), "  the log's byte count is where it stopped, not the whole block (%d)" % read)
            r1, _ = load(pio, 0x00, len(header))
            r2, _ = load(pio, 0xFF, len(data))
            check(r1 == r2 == "ok", "  and the next LOAD works first time (%s, %s)" % (r1, r2))
            load(pio, 0x00, len(header))
            r, log = load(pio, 0xFF, len(data), stop_at=1500)
            check(idle(pio, 0xFB) and "stalled -> RECOVERED" in log,
                  "the Z80 goes silent mid-block: the stall is seen, RECOVERED, no hang")
            tsp.offset, tsp.tap_idx = 0, 0
            load(pio, 0x00, len(header))
            pio.z80_every = 3
            seen = []
            r, log = load(pio, 0xFF, len(data), seen=seen)
            pio.z80_every = 1
            check(r == "ok" and bytes(seen) == data and "ran dry" not in log,
                  "a slow Z80 gets every byte, in order (%s)" % r)

            def no_channel():
                raise OSError("no free DMA channel")
            io._DMA = no_channel
            tsp.offset, tsp.tap_idx = 0, 0
            r0, _ = load(pio, 0x00, len(header))
            r1, _ = load(pio, 0xFF, len(data))
            check(r0 == r1 == "ok", "no free channel: the Python loop, as before (%s, %s)" % (r0, r1))
            io._DMA = None
            tsp.offset, tsp.tap_idx = 0, 0
        else:
            print("by DMA: skipped, the v3 card streams through tsbus put_block")

        check(pio.dropped == 0, "no RX overflow anywhere (%d)" % pio.dropped)
        print("  PASS  no put() into a full TX FIFO (FakePIO raises if one happens)")
    except PutWouldBlock as e:
        check(False, str(e))
    finally:
        os.unlink(tmp.name)
        os.unlink(ntmp.name)

    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
