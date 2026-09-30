"""Host-side test for PROCESS_CMD's V6 pre-load chain — issue #42.

Runs on CPython, no Pico required. Mocks machine/rp2/micropython and the
MQ state machine, then calls the REAL TS.tspico.PROCESS_CMD.

What it pins down:

  * a command handler that raises must NOT propagate out of PROCESS_CMD,
    and must still leave exactly one V6 pre-load (0x01) in TX — the
    regression that is issue #42;
  * the same for an undecodable command body, which took a second early
    `return` past the tail;
  * the happy path still writes exactly ONE pre-load (a `finally` that
    double-wrote would be the orphan-byte bug in reverse — Report R on
    the next data block);
  * the body-read timeout path, which is deliberately OUTSIDE the
    try/finally because it writes its own pre-load, still writes exactly
    one;
  * FAIL_CMD clears a partial handler response before staging its status
    byte, so the Z80 does not read half a response followed by a status.

NOTE ON SCOPE: this is a control-flow test. It proves the pre-load chain
is restored on every exit path. It does NOT prove the Z80 is happy — the
byte-level behaviour on real hardware still needs the harness treatment
described in src/CLAUDE.md.

Run:  python3 src/test/process_cmd_hosttest.py
"""

import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)


# ---------------------------------------------------------------------------
# Mock the device-only modules so `import TS.tspico` works on CPython.
# _thread is deliberately NOT mocked: CPython's own import machinery needs
# the real one (RLock, get_ident), and PROCESS_CMD never spawns a thread.
# ---------------------------------------------------------------------------

def install_fakes():
    machine = types.ModuleType("machine")
    machine.Pin = lambda *a, **k: types.SimpleNamespace(
        value=lambda *x: None, init=lambda *x, **y: None,
        toggle=lambda: None)
    machine.Pin.OUT = 0
    machine.Pin.IN = 1
    machine.Pin.PULL_UP = 2
    machine.Pin.PULL_DOWN = 3
    machine.SPI = lambda *a, **k: None
    machine.freq = lambda *a, **k: None
    sys.modules["machine"] = machine

    rp2 = types.ModuleType("rp2")
    rp2.StateMachine = lambda *a, **k: None
    rp2.asm_pio = lambda *a, **k: (lambda f: f)      # never executes the body
    rp2.PIO = types.SimpleNamespace(
        OUT_HIGH=0, OUT_LOW=1, SHIFT_RIGHT=2, SHIFT_LEFT=3,
        IN_HIGH=4, IN_LOW=5)
    sys.modules["rp2"] = rp2

    mp = types.ModuleType("micropython")
    mp.const = lambda x: x
    sys.modules["micropython"] = mp

    sys.modules["utime"] = __import__("time")

    sys.path.insert(0, SRC)


class FakeTime:
    """MicroPython ticks_* on top of a counter we control.

    Every ticks_ms()/ticks_us() call advances by 1, so the 1000 ms
    body-read timeout trips after ~1000 polls instead of a real second.
    """

    def __init__(self):
        self.t = 0

    def ticks_ms(self):
        self.t += 1
        return self.t

    def ticks_us(self):
        self.t += 1
        return self.t

    @staticmethod
    def ticks_diff(a, b):
        return a - b

    def sleep(self, *_a):
        pass

    def sleep_ms(self, *_a):
        pass


class FakeMQ:
    """TX drains instantly (a Z80 reading as fast as we write).

    tx_fifo() is PURE — TLM() calls it, so a side effect here would
    silently eat bytes and make every assertion below a lie.
    """

    def __init__(self, rx_bytes=b""):
        self.rx = list(rx_bytes)
        self.tx_log = []          # ordered record of every put()
        self.execs = []

    def rx_fifo(self):
        return len(self.rx)

    def tx_fifo(self):
        return 0                  # Z80 has always already read it

    def get(self):
        return self.rx.pop(0)

    def put(self, b):
        self.tx_log.append(b)

    def exec(self, s):
        self.execs.append(s)

    def active(self, *_a):
        pass


class StuckMQ(FakeMQ):
    """TX does NOT drain — models a Z80 that aborted mid-command."""

    def __init__(self, tx_pending=(), rx_bytes=b""):
        FakeMQ.__init__(self, rx_bytes)
        self.pending = list(tx_pending)

    def tx_fifo(self):
        return len(self.pending)

    def put(self, b):
        self.tx_log.append(b)
        self.pending.append(b)

    def exec(self, s):
        self.execs.append(s)
        if "pull" in s and self.pending:
            self.pending.pop(0)   # PIO pull(noblock) drains one TX entry


# ---------------------------------------------------------------------------
# Wire helpers
# ---------------------------------------------------------------------------

def make_pre(cmd_text, load_cmd=0):
    """Build the 10-byte pre-header for a 'B' (BASIC) command."""
    n = len(cmd_text)
    pre = bytearray(10)
    pre[0] = 66                   # 'B' — BASIC command
    pre[1] = load_cmd             # 0 = SAVE "tpi:..." (dispatches SA_funct)
    pre[7] = n & 0xFF
    pre[8] = (n >> 8) & 0xFF
    return pre


def make_body(cmd_text, good_checksum=True):
    """The body the Z80 OUTs (EXROM 224Dh-2274h): 'D', len lo, len hi, the
    command text, then an XOR of all of those -- len+4 bytes. PROCESS_CMD
    checks the XOR and slices cmd[3:] as the command."""
    n = len(cmd_text)
    body = bytearray(b"D") + bytes([n & 0xFF, (n >> 8) & 0xFF]) + cmd_text
    c = 0
    for b in body:
        c ^= b
    body.append(c if good_checksum else c ^ 0x5A)
    return bytes(body)


def fresh(mod, mq):
    """Point the module's globals at our fakes for one call."""
    mod.MQ = mq
    mod.TSP = types.SimpleNamespace(
        zx48=False, f_name="", append=False, cur_path="/sd/TAP",
        VERBOSE=False, LOG_LEVEL=2, offset=0, offset_tbl=[], tap_idx=0,
        sd_present=True, sd_cid=1, sd_listing_ok=True, save_no_card=False)
    mod.log_entries = []
    mod.log_to_serial = False
    mod.files = []
    mod.files_upper = []


# ---------------------------------------------------------------------------
# Assertions
# ---------------------------------------------------------------------------

FAILURES = []


def check(cond, msg):
    if cond:
        print("  ok   %s" % msg)
    else:
        print("  FAIL %s" % msg)
        FAILURES.append(msg)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_handler_exception_preserves_preload(t):
    print("test_handler_exception_preserves_preload")
    mq = FakeMQ(make_body(b"tpi:boom"))
    fresh(t, mq)

    def boom(pre, cmd):
        raise OSError("simulated: SD card pulled mid-command")

    raised = None
    try:
        t.PROCESS_CMD(make_pre(b"tpi:boom"), {"TPI:BOOM": boom}, {})
    except Exception as e:                       # noqa: BLE001
        raised = e

    check(raised is None,
          "PROCESS_CMD swallows the handler exception (got %r)" % raised)
    check(mq.tx_log[-1:] == [0x01],
          "last TX byte is the V6 pre-load 0x01 (got %r)" % (mq.tx_log[-4:],))
    check(mq.tx_log.count(0x01) == 1,
          "exactly one 0x01 pre-load (got %d)" % mq.tx_log.count(0x01))
    check(t._10_J_Invalid_IO in mq.tx_log,
          "an error status reached the Z80 (TX=%r)" % (mq.tx_log,))


def test_successful_handler_writes_one_preload(t):
    print("test_successful_handler_writes_one_preload")
    mq = FakeMQ(make_body(b"tpi:fine"))
    fresh(t, mq)
    seen = []

    def fine(pre, cmd):
        seen.append(cmd)
        mq.put(0x01)              # a well-behaved handler's own status

    t.PROCESS_CMD(make_pre(b"tpi:fine"), {"TPI:FINE": fine}, {})

    check(len(seen) == 1, "handler ran once")
    check(mq.tx_log == [0x01, 0x01],
          "handler status + exactly one tail pre-load (got %r)" % (mq.tx_log,))


def test_undecodable_body_preserves_preload(t):
    print("test_undecodable_body_preserves_preload")
    body = make_body(b"\xff\xfe\xff\xfe")        # good checksum, not valid UTF-8
    mq = FakeMQ(body)
    fresh(t, mq)

    raised = None
    try:
        t.PROCESS_CMD(make_pre(b"\xff\xfe\xff\xfe"), {}, {})
    except Exception as e:                       # noqa: BLE001
        raised = e

    check(raised is None, "no exception escapes (got %r)" % raised)
    check(mq.tx_log[-1:] == [0x01],
          "V6 pre-load restored after a decode failure (got %r)" % (mq.tx_log,))
    check(t._5_C_Nonsense in mq.tx_log,
          "an error status reached the Z80 (TX=%r)" % (mq.tx_log,))


def test_bad_checksum_reports_r(t):
    print("test_bad_checksum_reports_r")
    mq = FakeMQ(make_body(b"tpi:dir", good_checksum=False))
    fresh(t, mq)
    ran = []

    t.PROCESS_CMD(make_pre(b"tpi:dir"), {"TPI:DIR": lambda *a: ran.append(a)}, {})

    check(not ran, "the handler never runs on a damaged body")
    check(mq.tx_log == [t._2_R_Tape_load, 0x01],
          "Report R status, then exactly one V6 pre-load (got %r)" % (mq.tx_log,))
    check(mq.rx_fifo() == 0,
          "the whole body, checksum byte included, was consumed (RX left %d)" % mq.rx_fifo())


def test_checksum_byte_is_consumed(t):
    print("test_checksum_byte_is_consumed")
    mq = FakeMQ(make_body(b"tpi:fine") + b"\x42")  # + the NEXT command's first byte
    fresh(t, mq)
    seen = []

    def fine(pre, cmd):
        seen.append((cmd, mq.rx_fifo()))

    t.PROCESS_CMD(make_pre(b"tpi:fine"), {"TPI:FINE": fine}, {})

    check(seen and seen[0][0][3:] == "tpi:fine",
          "handler's cmd[3:] is exactly the text, no checksum byte on the end (%r)" % (seen,))
    check(seen and seen[0][1] == 1,
          "when the handler runs, only the next command's byte is in RX (%r)" % (seen,))


def test_body_read_timeout_writes_one_preload(t):
    print("test_body_read_timeout_writes_one_preload")
    mq = FakeMQ(b"")                             # Z80 sent nothing
    fresh(t, mq)

    t.PROCESS_CMD(make_pre(b"tpi:dir"), {}, {})

    # This path returns BEFORE the try/finally on purpose — it stages its
    # own pre-load. A second one from the finally would be an orphan byte.
    check(mq.tx_log == [0x01],
          "timeout path writes exactly one pre-load (got %r)" % (mq.tx_log,))


def test_fail_cmd_clears_partial_response(t):
    print("test_fail_cmd_clears_partial_response")
    mq = StuckMQ(tx_pending=[0x86, 0x01, 0x41])  # half a handler response
    t.MQ = mq
    t.FAIL_CMD(t._10_J_Invalid_IO)

    check(mq.pending == [t._10_J_Invalid_IO],
          "TX holds only the status byte (got %r)" % (mq.pending,))
    check(any("pull" in e for e in mq.execs),
          "drained TX via PIO pull (execs=%r)" % (mq.execs,))
    check(any("mov(y, invert(null))" in e.replace(" ", "")
              or "mov(y,invert(null))" in e.replace(" ", "")
              for e in mq.execs),
          "signalled Y=READY (execs=%r)" % (mq.execs,))


def test_long_command_decodes(t):
    """A command of 128+ bytes: its length byte is >= 0x80, which isn't valid
    UTF-8. PROCESS_CMD decodes only the text, so the handler gets it whole
    (tpi:chwr with 60+ bytes of hex, a 64-character path)."""
    print("test_long_command_decodes")
    text = b"tpi:long " + b"ab" * 70                  # 149 bytes
    mq = FakeMQ(make_body(text))
    fresh(t, mq)
    seen = []

    def long_(pre, cmd):
        seen.append(cmd)
        mq.put(0x01)

    t.PROCESS_CMD(make_pre(text), {"TPI:LONG": long_}, {})
    check(len(seen) == 1 and seen[0][3:] == text.decode() and len(seen[0]) == len(text) + 3,
          "a 149-byte command reaches its handler whole, cmd[3:] = the text (%r)"
          % (seen[0][:20] if seen else None,))
    check(mq.tx_log == [0x01, 0x01], "and the pre-load chain is intact (%r)" % (mq.tx_log,))


def main():
    install_fakes()
    import TS.tspico as t

    t.TLM_ENABLED = False                        # production setting; also
                                                 # keeps TLM off our FakeMQ
    ft = FakeTime()
    t.time = ft
    import TS.tspico_io as tio     # RX_CAPTURE / TX_ROOM / RX_WORD (stage 4)
    tio.time = ft
    t.utime = ft

    for fn in (test_handler_exception_preserves_preload,
               test_successful_handler_writes_one_preload,
               test_undecodable_body_preserves_preload,
               test_bad_checksum_reports_r,
               test_checksum_byte_is_consumed,
               test_body_read_timeout_writes_one_preload,
               test_fail_cmd_clears_partial_response,
               test_long_command_decodes):
        fn(t)

    print()
    if FAILURES:
        print("%d CHECK(S) FAILED" % len(FAILURES))
        for f in FAILURES:
            print("  - %s" % f)
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
