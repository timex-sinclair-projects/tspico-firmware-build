"""Host-side test for abort_harness.py -- CPython, no Pico, no 2068.

A simulated PIO (FakePIO) models TS_IO_DUAL exactly where it matters here:
4-deep TX and RX FIFOs, A0 in bit 8 of every captured Z80 write, the
auto-busy (Y = 0) on every Z80 write, an empty-TX read returning 0x00, and
the PIO instructions the harness exec()s. A put() into a full TX FIFO -- which
blocks forever on the Pico -- fails the test outright.

The Z80 side is a script per command that follows the 1.8b ROM
(src/rom/patches/tspico-sync.asm on top of v1.7) byte for byte: SYNC
(OUT (0Fh),03h + wait for READY and IDLE), pre-header, the no-wait status read
of the pre-load, ready-waits, block transfers with a BREAK check every 256
bytes, the 0x86 key waits, and RECOVERED -> Report T in every ready-wait.

The two sides run interleaved and deterministically: every MQ call the
harness makes advances the Z80 script one step, and the harness's clock
advances one millisecond per read, so stalls and timeouts are exact.

What is proven here is the protocol logic. Timing on the real bus (can the
send loop keep up with the Z80?) is for hardware and the ZEsarUX lab.

Run:  python3 src/test/abort_harness_hosttest.py
"""

import os
import sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import abort_harness as H                      # noqa: E402  (no device imports at top level)


# ---------------------------------------------------------------------------
# The simulated PIO + Z80
# ---------------------------------------------------------------------------

class PutWouldBlock(AssertionError):
    pass


class Z80Done(Exception):
    pass


class FakePIO:
    """TS_IO_DUAL as seen from both sides, with a Z80 script driven by pumping."""

    def __init__(self):
        self.tx = deque()           # Pico -> Z80
        self.rx = deque()           # Z80 -> Pico, 9-bit words
        self.y = 0xFFFFFFFF
        self.dropped = 0            # RX overflow (push noblock)
        self.underruns = 0          # Z80 IN on an empty TX FIFO
        self.script = None
        self.pending = None         # op the script is blocked on
        self.result = None          # what the script returned
        self.trace = []
        self.clock = 0

    # ---- harness-facing (rp2.StateMachine API) ----
    def rx_fifo(self):
        self.pump()
        return len(self.rx)

    def tx_fifo(self):
        self.pump()
        return len(self.tx)

    def get(self):
        for _ in range(100000):
            if self.rx:
                return self.rx.popleft()
            self.pump()
        raise AssertionError("harness called get() on an empty RX FIFO that never filled")

    def put(self, b):
        if len(self.tx) >= H.TX_DEPTH:
            raise PutWouldBlock("put() into a full TX FIFO would block forever")
        self.tx.append(b & 0xFF)
        self.pump()

    def exec(self, s):
        s = s.replace(" ", "")
        if s == "mov(y,invert(null))":
            self.y = 0xFFFFFFFF
        elif s.startswith("set(y,"):
            self.y = int(s[6:-1])
        elif s == "mov(y,invert(y))":
            self.y = ~self.y & 0xFFFFFFFF
        elif s == "pull(noblock)":
            if self.tx:
                self.tx.popleft()
        else:
            raise AssertionError("unexpected exec %r" % s)

    # ---- clock for the harness ----
    def ticks_ms(self):
        # The clock advances, the Z80 doesn't: it moves only when the harness
        # touches the FIFOs, so a clock read in a wait loop can't make the
        # simulated Z80 outrun the harness's reads.
        self.clock += 1
        return self.clock

    @staticmethod
    def ticks_diff(a, b):
        return a - b

    # ---- Z80 side ----
    def status(self):
        return self.y & 0xFF

    def run(self, gen):
        self.script, self.pending, self.result = gen, None, None
        self._advance(None)

    def _advance(self, value):
        try:
            self.pending = self.script.send(value)
        except StopIteration as e:
            self.result = e.value
            self.script = None
            self.pending = None

    def pump(self):
        """Execute (at most) one Z80 operation."""
        if self.script is None:
            return
        op = self.pending
        kind = op[0]
        if kind == "out":
            port, v = op[1], op[2]
            if len(self.rx) < 4:
                self.rx.append(v | (0x100 if port == 0x0F else 0))
            else:
                self.dropped += 1
            self.y = 0                                  # issue #14 auto-busy
            self.trace.append(("out%02X" % port, v))
            self._advance(None)
        elif kind == "in":
            if self.tx:                                 # (the real Z80 doesn't
                self._advance(self.tx.popleft())        #  wait; see underruns)
            else:
                self.underruns += 1
        elif kind == "wait":                            # poll port 0Fh
            need, budget = op[1], op[2]
            st = self.status()
            if (st & need) == need:
                self._advance(st)
            elif budget <= 0:
                self._advance(None)                     # timed out
            else:
                self.pending = ("wait", need, budget - 1)


READY, IDLE, RECOVERED = 0x40, 0x08, 0x04
WAIT_POLLS = 20000        # "~20 s" in pump steps
SYNC_POLLS = 3000         # "~1 s"


def out(port, v):
    return ("out", port, v)


# ---------------------------------------------------------------------------
# Z80 scripts following the 1.8b ROM. Each returns a short outcome string:
# "ok", "D" (BREAK), "T" (RECOVERED), "J" (timeout / bad status).
# ---------------------------------------------------------------------------

def ready_wait():
    """WAIT_PICO_READY + RD_STATUS: returns None on success, else a report."""
    st = yield ("wait", READY, WAIT_POLLS)
    if st is None:
        return "J"
    if not st & RECOVERED:
        return "T"
    return None


def sync():
    yield out(0x0F, H.ABORT_BYTE)
    yield ("wait", READY | IDLE, SYNC_POLLS)            # carries on either way


def brk():
    """BRK_ABORT: abort byte, wait for READY+IDLE, Report D."""
    yield from sync()
    return "D"


def pre_header(b0, b1, lo=0, hi=0):
    p = [b0, b1, 0xFF, 0x34, 0x12, 0x00, 0x80, lo, hi]
    c = 0
    for b in p:
        c ^= b
    return p + [c]


def rom_load(flag, length, break_at=None, stop_at=None, sync_first=True):
    """One LOAD block. break_at: press BREAK at that byte (256-byte check).
    stop_at: the 2068 is reset there (just stops, no abort).
    sync_first=False: a v1.7-or-earlier ROM, which has no SYNC."""
    if sync_first:
        yield from sync()
    for b in pre_header(flag, 1, length & 0xFF, length >> 8):
        yield out(0x0E, b)
    st = yield ("in",)                                  # 19C7: no wait
    if st != 0x01:
        return "J"
    r = yield from ready_wait()                         # 19D4
    if r:
        return r
    yield out(0x0E, flag)                               # 1924: echo 1
    got = yield ("in",)                                 # flag byte
    if got != flag:
        return "R"
    parity = flag
    for i in range(length):                             # STEP every byte
        if stop_at is not None and i == stop_at:
            return "reset"
        if break_at is not None and i >= break_at and ((length - 1 - i) & 0xFF) == 0xFF:
            return (yield from brk())
        b = yield ("in",)
        parity ^= b
    crc = yield ("in",)
    if crc != parity:
        return "R"
    yield out(0x0E, 0x00)                               # 1A02: echo 2
    r = yield from ready_wait()                         # 1A05
    if r:
        return r
    st = yield ("in",)                                  # 1A0B
    return "ok" if st == 0x01 else "J"


def rom_save(blen, break_at=None, stop_after_header=False, sync_first=True,
             v17_break_after_header=False, header_session=(0x34, 0x12)):
    """A SAVE: header call then data call (the data call has no SYNC).
    v17_break_after_header: a v1.7 ROM whose ready-wait after the header
    block sees BREAK -- it gives up (Report J) without reading the status
    and without telling the Pico. header_session: the session bytes the
    header block carries (the pre-header's are 34 12)."""
    if sync_first:
        yield from sync()
    for b in pre_header(0x00, 0x00):
        yield out(0x0E, b)
    st = yield ("in",)                                  # 18C4: no wait
    if st != 0x01:
        return "J"
    r = yield from ready_wait()                         # 18D2
    if r:
        return r
    hdr = [0x00, header_session[0], header_session[1], 0x03] + list(b"savetest  ") + [
        blen & 0xFF, blen >> 8, 0x00, 0x80, 0x00, 0x00]
    c = hdr[0]
    for b in hdr[3:]:
        c ^= b
    for b in hdr + [c]:
        yield out(0x0E, b)
    if v17_break_after_header:
        return "J"                                      # 190B: BREAK, status unread
    r = yield from ready_wait()                         # 190B
    if r:
        return r
    st = yield ("in",)
    if st != 0x01:
        return "J"
    if stop_after_header:
        return "reset"
    data = [0xFF, 0x34, 0x12] + [(i * 7) & 0xFF for i in range(blen)]
    c = data[0]
    for b in data[3:]:
        c ^= b
    data.append(c)
    for i, b in enumerate(data):
        if break_at is not None and i >= break_at and (i & 0xFF) == 0:
            return (yield from brk())
        yield out(0x0E, b)
    r = yield from ready_wait()
    if r:
        return r
    st = yield ("in",)
    return "ok" if st == 0x01 else "J"


def rom_cmd(text, keys, bad_checksum=False):
    """A TPI: command whose reply is 0x86 paged output. keys: what the user
    presses at each "Scroll?" prompt -- 'Y', 'N' or 'BREAK'."""
    body = list(text.encode())
    yield from sync()
    for b in pre_header(0x42, 0x01, len(body) & 0xFF, len(body) >> 8):
        yield out(0x0E, b)
    st = yield ("in",)                                  # 223E: no wait
    if st != 0x01:
        return "J"
    r = yield from ready_wait()                         # 2247
    if r:
        return r
    d = [0x44, len(body) & 0xFF, len(body) >> 8] + body
    c = 0
    for b in d:
        c ^= b
    if bad_checksum:
        c ^= 0x5A
    for b in d + [c]:                                   # 224D-2274: 'D', len, text, XOR
        yield out(0x0E, b)
    r = yield from ready_wait()                         # 2279
    if r:
        return r
    st = yield ("in",)
    if st != 0x86:
        return "st%02X" % st                            # 2286-228C: status -> report
    rc = yield ("in",)                                  # 02B9: return code
    if rc == 0:
        return "silent"                                 # 192F: AND A / RET Z
    pages = 1
    keys = list(keys)
    while True:
        b = yield ("in",)                               # PRINT_STRING_FROM_PICO
        if b == 0x03:
            return "ok:%d" % pages
        if b != 0x00:
            continue
        key = keys.pop(0) if keys else "Y"              # key wait (KEYWAIT)
        if key == "BREAK":
            return (yield from brk())
        r = yield from ready_wait()                     # SEND_KEY 1C40
        if r:
            return r
        yield out(0x0E, ord(key))
        if key == "N":
            return "N:%d" % pages
        r = yield from ready_wait()                     # YN_LOOP_GUARD 22A1
        if r:
            return r
        pages += 1


def pio_body(path, name):
    """The instruction lines of PIO program `name` in a source file, with
    comments, whitespace and the docstring stripped, so the harness's
    embedded copies can be compared with the firmware's."""
    import re
    lines = open(path, encoding="utf-8").read().replace("\r", "").splitlines()
    for i, line in enumerate(lines):
        if line.split("#")[0].strip() == "def %s():" % name:
            indent = len(line) - len(line.lstrip())
            break
    else:
        return None
    body = []
    for line in lines[i + 1:]:
        if line.strip() and len(line) - len(line.lstrip()) <= indent:
            break                               # back out of the function
        body.append(line)
    text = re.sub(r'"""[\s\S]*?"""', "", "\n".join(body), count=1)
    out = []
    for line in text.splitlines():
        line = re.sub(r"\s+", "", line.split("#")[0])
        if line:
            out.append(line)
    return out


# ---------------------------------------------------------------------------
# Test plumbing
# ---------------------------------------------------------------------------

results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg)


def new_harness():
    pio = FakePIO()
    h = H.Harness(pio, pio.ticks_ms, pio.ticks_diff, log=lambda *a: None)
    h.start()
    return pio, h


def run(pio, h, script, serves=4):
    """Start a Z80 script and let the harness serve until it finishes."""
    pio.run(script)
    for _ in range(serves):
        if pio.script is None and not pio.rx:
            break
        h.serve_once(idle_ms=200)
    # Let any leftover Z80 steps (final reads, ready-waits) complete.
    for _ in range(50000):
        if pio.script is None:
            break
        pio.pump()
    return pio.result


def idle_ok(pio, recovered=False):
    want = 0xFB if recovered else 0xFF
    return list(pio.tx) == [0x01] and pio.status() == want and not pio.rx


# ---------------------------------------------------------------------------

def main():
    print("idle start")
    pio, h = new_harness()
    check(idle_ok(pio), "start(): TX = [01] pre-load, status FF, RX empty")

    print("SYNC while idle")
    r = run(pio, h, (lambda: (yield from sync()))())
    check(h.stats["sync"] == 1 and idle_ok(pio), "stray SYNC -> still exactly one pre-load, status FF")

    print("LOAD header + data, no BREAK")
    r1 = run(pio, h, rom_load(0x00, 17))
    r2 = run(pio, h, rom_load(0xFF, H.LOAD_PROG_LEN))
    check(r1 == "ok" and r2 == "ok", "header and %d-byte data block load (%s, %s)" % (H.LOAD_PROG_LEN, r1, r2))
    check(h.stats["load"] == 2 and idle_ok(pio), "after LOAD: one pre-load, status FF")
    print("  info  the simulated Z80 waited on an empty TX %d times; on the bus it can't wait,"
          " so whether the send loop keeps up is for hardware and the lab" % pio.underruns)

    print("LOAD data, BREAK mid-block")
    r = run(pio, h, rom_load(0xFF, H.LOAD_PROG_LEN, break_at=5000))
    check(r == "D", "Z80 sees Report D (got %s)" % r)
    check(h.events[-1] == ("abort", "load") and idle_ok(pio), "harness heard the abort in its send loop -> idle, one pre-load")
    r = run(pio, h, rom_load(0x00, 17))
    check(r == "ok", "next LOAD works first time (%s)" % r)

    print("SAVE, no BREAK")
    r = run(pio, h, rom_save(3000))
    check(r == "ok" and h.stats["save"] == 1 and idle_ok(pio), "SAVE of 3000 bytes completes (%s)" % r)
    check("dataCRC=True" in h.events[-1][1] and "hdrCRC=True" in h.events[-1][1], "header and data parity checked: " + h.events[-1][1])

    print("SAVE, BREAK mid-block")
    r = run(pio, h, rom_save(3000, break_at=1000))
    check(r == "D", "Z80 sees Report D (got %s)" % r)
    check(h.events[-1] == ("abort", "save") and idle_ok(pio), "harness heard the abort in its drain -> idle, nothing written")
    r = run(pio, h, rom_save(200))
    check(r == "ok", "next SAVE works first time (%s)" % r)

    print("TPI command -> 0x86 pages")
    r = run(pio, h, rom_cmd("tpi:dir", ["Y", "Y", "Y"]))
    check(r == "ok:%d" % H.PAGES and idle_ok(pio), "all %d pages, end-of-message 03 (%s)" % (H.PAGES, r))
    r = run(pio, h, rom_cmd("tpi:dir", [], bad_checksum=True))
    check(r == "st02" and idle_ok(pio) and "bad checksum" in h.events[-1][1],
          "damaged command body -> status 02 (Report R), then idle with one pre-load (%s)" % r)
    r = run(pio, h, rom_cmd("tpi:dir", ["N"]))
    check(r == "N:1", "and the next command works (%s)" % r)
    r = run(pio, h, rom_cmd("tpi:dir", ["Y", "N"]))
    check(r == "N:2" and idle_ok(pio), "'N' at the second prompt stops cleanly (%s)" % r)
    r = run(pio, h, rom_cmd("tpi:dir", ["BREAK"]))
    check(r == "D" and h.events[-1] == ("abort", "cmd") and idle_ok(pio),
          "BREAK at the Scroll? key wait -> Report D, harness idle (%s)" % r)
    r = run(pio, h, rom_cmd("tpi:dir", ["N"]))
    check(r == "N:1", "next command works first time (%s)" % r)

    print("2068 reset mid-LOAD (no abort), new LOAD straight away")

    def reset_then_load():
        r = yield from rom_load(0xFF, H.LOAD_PROG_LEN, stop_at=3000)
        assert r == "reset"
        return (yield from rom_load(0x00, 17))

    n = len(h.events)
    r = run(pio, h, reset_then_load())
    kinds = [e[0] for e in h.events[n:]]
    check(r == "ok" and kinds == ["sync", "abort", "load"] and h.events[n + 1][1] == "load",
          "the new LOAD's SYNC reaches the harness mid-send, aborts the stale LOAD, "
          "and the new one succeeds (%s: %s)" % (r, kinds))
    check(idle_ok(pio), "idle, one pre-load")

    print("2068 reset between SAVE header and data (silence, no SYNC)")
    stalls = h.stats["stall"]
    r = run(pio, h, rom_save(3000, stop_after_header=True))
    for _ in range(3):
        h.serve_once(idle_ms=10)
    check(h.stats["stall"] == stalls + 1 and idle_ok(pio, recovered=True),
          "harness times out -> idle with RECOVERED (status FB), one pre-load")
    r = run(pio, h, rom_load(0x00, 17))
    check(r == "ok" and pio.status() == 0xFF, "next command's SYNC clears RECOVERED and it works (%s)" % r)

    print("session ID: v1.7 ROM, BREAK after the SAVE header, then the next command")

    def v17_save_break_then_load():
        r = yield from rom_save(3000, sync_first=False, v17_break_after_header=True)
        assert r == "J"
        return (yield from rom_load(0x00, 17, sync_first=False))

    n = len(h.events)
    r = run(pio, h, v17_save_break_then_load())
    kinds = [e[0] for e in h.events[n:]]
    check(r == "ok" and kinds == ["stale", "load"],
          "the data-block check sees the LOAD pre-header instead of FF + session, keeps "
          "those bytes and serves the LOAD first time (%s: %s)" % (r, kinds))
    check(idle_ok(pio), "idle, one pre-load")

    print("session ID: header block from a different statement")
    r = run(pio, h, rom_save(3000, header_session=(0x99, 0x77)))
    check(r == "T" and h.events[-1][0] == "mismatch" and idle_ok(pio, recovered=True),
          "harness gives up as RECOVERED; the waiting Z80 raises Report T (%s: %s)" % (
              r, h.events[-1][1]))
    r = run(pio, h, rom_save(200))
    check(r == "ok" and "session=1234" in h.events[-1][1],
          "next SAVE (SYNC clears RECOVERED) works, session checked: %s" % h.events[-1][1])

    print("RECOVERED seen by a waiting Z80")
    pio2, h2 = new_harness()
    h2.link.set_status(H.ST_RECOVERED)
    pio2.run(ready_wait())
    for _ in range(10):
        pio2.pump()
    check(pio2.result == "T", "a ready-wait that sees FB raises Report T (%s)" % pio2.result)

    print("embedded PIO programs match src/TS/tspico_io.py")
    for mine, theirs in (("SEL_BANK", "sel_bank"), ("SET_CTRL", "set_ctrl"),
                         ("TS_IO_DUAL_COPY", "TS_IO_DUAL")):
        a = pio_body(os.path.join(HERE, "abort_harness.py"), mine)
        b = pio_body(os.path.join(os.path.dirname(HERE), "TS", "tspico_io.py"), theirs)
        check(a and a == b, "%s == %s (%d instructions)" % (mine, theirs, len(b)))

    print("MicroPython-safe exceptions")
    import ast
    tree = ast.parse(open(os.path.join(HERE, "abort_harness.py"), encoding="utf-8").read())
    exc_names = {"Exception"}
    bad = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            bases = {b.id for b in node.bases if isinstance(b, ast.Name)}
            if bases & exc_names or node.name in ("Abort", "Stall", "Mismatch", "NotOurs"):
                exc_names.add(node.name)
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                        bad.append("%s.__init__" % node.name)
        if isinstance(node, ast.Attribute) and node.attr == "__init__" and \
                isinstance(node.value, ast.Name) and node.value.id == "Exception":
            bad.append("Exception.__init__ call")
    check(not bad, "no exception class overrides __init__ or calls Exception.__init__ "
                   "(MicroPython raises AttributeError) %s" % (bad or ""))

    print("never blocked, never dropped")
    check(pio.dropped == 0, "no RX overflow in any scenario (%d dropped)" % pio.dropped)
    print("  PASS  no put() into a full TX FIFO (FakePIO raises PutWouldBlock if one happens)")

    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except PutWouldBlock as e:
        print("  FAIL  " + str(e))
        sys.exit(1)
