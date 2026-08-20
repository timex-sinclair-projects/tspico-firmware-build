"""Host test for the ZX48-mode handlers — CPython, no Pico required.

The wire sequences below are transcribed from the customized Spectrum ROM
("Spectrum nuevo LD.rom": a stock 48K image whose SA-BYTES at $04C2 and
LD-BYTES at $0556 are replaced with TS-Pico stubs), not from the TPI spec.
ZX48 mode is NOT TPI, and the two protocols disagree in the places that
matter:

  * The ROM contains ZERO `IN A,($0F)`. Port $0F -- the Y register, the
    whole dual-port ready mechanism -- is never read in ZX mode.
  * There is no status byte and no STATUS_TO_REPORT path; $053F, the
    shared exit, RST-8's on BREAK and nothing else. So SAVE_TS's
    REFUSE_SAVE() pattern has no counterpart here.
  * LOAD *does* handshake, but on $0E (the DATA port), polling until it
    reads 0x40. That is what the dual-port compliance sweep in c649e69
    deleted as a "single-port continue flag".

SA-BYTES $04C2, per block (blind timed OUTs, no handshake):
    OUT $0E,'S' / len_lo / len_hi / flag / DE data bytes / parity
    DE is decremented AFTER the send, so DE=0 floods 65536 bytes.

LD-BYTES $0556, per block:
    OUT $0E,'L' ; poll IN $0E until 0x40 ; IN flag ; DE data ; IN parity

Run:  python3 src/test/zx48_hosttest.py
"""

import io
import os
import sys
import types
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)

PASS = 0
FAIL = 0


def check(cond, label):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  [PASS] %s" % label)
    else:
        FAIL += 1
        print("  [FAIL] %s" % label)


def install_fakes():
    import builtins
    if not hasattr(builtins, "const"):
        builtins.const = lambda x: x

    machine = types.ModuleType("machine")

    class _Pin:
        OUT, IN, PULL_UP, PULL_DOWN = 0, 1, 2, 3
        def __init__(self, *a, **k): pass
        def value(self, *a): return 0
        def toggle(self): pass
        def init(self, *a, **k): pass
    machine.Pin = _Pin
    machine.SPI = lambda *a, **k: None
    machine.freq = lambda *a, **k: None
    sys.modules["machine"] = machine

    rp2 = types.ModuleType("rp2")
    rp2.StateMachine = lambda *a, **k: FakeMQ()
    rp2.asm_pio = lambda *a, **k: (lambda f: f)
    rp2.PIO = types.SimpleNamespace(
        OUT_HIGH=0, OUT_LOW=1, SHIFT_RIGHT=2, SHIFT_LEFT=3, IN_HIGH=4)
    sys.modules["rp2"] = rp2

    import time as _rt
    utime = types.ModuleType("utime")
    utime.ticks_ms = lambda: int(_rt.monotonic() * 1000)
    utime.sleep = lambda s: None
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
    tspico = types.ModuleType("TS.tspico")
    tspico.TLM = lambda *a, **k: None
    sys.modules["TS.tspico"] = tspico


class FakeMQ:
    """Records TX and serves RX. ZX mode never touches $0F, so no Y here."""
    def __init__(self, rx_bytes=b""):
        self.rx = list(rx_bytes)
        self.tx = []
    def rx_fifo(self): return len(self.rx)
    def tx_fifo(self): return 0            # pretend the Z80 keeps reading
    def get(self): return self.rx.pop(0)
    def put(self, b):
        self.tx.append(b if isinstance(b, int) else b[0])
    def exec(self, _s): pass
    def active(self, *_a): pass


class FakeTSP:
    def __init__(self, cur_path, f_name="", totlen=0, offset=0):
        self.cur_path = cur_path
        self.f_name = f_name
        self.totlen = totlen
        self.offset = offset
        self.tap_idx = 0
        self.LOG_LEVEL = 3
        self.append = False


# ---------------------------------------------------------------------------
# Wire builders, straight from the disassembly
# ---------------------------------------------------------------------------

def sa_block(flag, payload):
    """One SA-BYTES block as it appears on the bus, 'S' included."""
    parity = flag
    for b in payload:
        parity ^= b
    return (bytes([0x53, len(payload) & 0xFF, (len(payload) >> 8) & 0xFF, flag])
            + bytes(payload) + bytes([parity]))


def zx_header(name, datalen, htype=0, p1=0, p2=0x8000):
    """The Spectrum 17-byte tape header."""
    h = bytearray(17)
    h[0] = htype
    h[1:11] = (bytes(name) + b" " * 10)[:10]
    h[11] = datalen & 0xFF
    h[12] = (datalen >> 8) & 0xFF
    h[13] = p1 & 0xFF
    h[14] = (p1 >> 8) & 0xFF
    h[15] = p2 & 0xFF
    h[16] = (p2 >> 8) & 0xFF
    return bytes(h)


def tap_block(flag, payload):
    """One block in .tap file form: [len_lo][len_hi][flag][payload][parity]."""
    parity = flag
    for b in payload:
        parity ^= b
    n = len(payload) + 2
    return bytes([n & 0xFF, (n >> 8) & 0xFF, flag]) + bytes(payload) + bytes([parity])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_save_zx_roundtrip(tio):
    """A full ZX SAVE must reconstruct a byte-exact .tap."""
    print("test_save_zx_roundtrip: header + data -> .tap")
    with tempfile.TemporaryDirectory() as d:
        data = bytes(range(64))
        hdr17 = zx_header(b"prog", len(data))
        wire = sa_block(0x00, hdr17) + sa_block(0xFF, data)
        # ZX48_IO consumes the header block's leading 'S' before dispatching.
        MQ = FakeMQ(wire[1:])
        TSP = FakeTSP(d)
        tio.ENA_SD = lambda: None
        tio.ENA_MQ_DUAL = lambda: MQ
        saved_umount, os.umount = getattr(os, "umount", None), lambda p: None
        try:
            tio.SAVE_ZX(MQ, TSP)
        finally:
            if saved_umount is None:
                del os.umount
            else:
                os.umount = saved_umount

        check(os.listdir(d) == ["prog.tap"],
              'saved as "prog.tap", got %r' % (os.listdir(d),))
        got = open(os.path.join(d, "prog.tap"), "rb").read()
        want = tap_block(0x00, hdr17) + tap_block(0xFF, data)
        check(got == want,
              ".tap byte-identical to the reference (%d vs %d bytes)"
              % (len(got), len(want)))
        check(MQ.rx_fifo() == 0, "consumed the whole wire, %d left" % MQ.rx_fifo())
        check(MQ.tx == [], "wrote NOTHING to TX -- ZX SAVE has no status byte, "
                           "got %r" % (MQ.tx,))


def test_save_zx_parity_seed(tio):
    """Parity is seeded from the FLAG byte (hdr[2]), not hdr[0]."""
    print("test_save_zx_parity_seed: XOR starts at the flag, not the length")
    data = bytes(range(16))
    hdr17 = zx_header(b"p", len(data))
    wire = sa_block(0x00, hdr17)
    hdr = wire[1:]                       # what SAVE_ZX drains: 21 bytes
    check(len(hdr) == 21, "header block is 21 bytes on the wire, got %d" % len(hdr))
    seeded_at_2 = hdr[2]
    for i in range(3, 20):
        seeded_at_2 ^= hdr[i]
    seeded_at_0 = hdr[0]
    for i in range(3, 20):
        seeded_at_0 ^= hdr[i]
    check(seeded_at_2 == hdr[20],
          "seeding from hdr[2] matches the ROM's parity (0x%02X)" % hdr[20])
    check(seeded_at_0 != hdr[20],
          "seeding from hdr[0] (the SAVE_TS rule) would NOT match -- 0x%02X"
          % seeded_at_0)


def test_save_zx_empty_flood(tio):
    """BLEN=0 must swallow the 64K flood and write nothing."""
    print("test_save_zx_empty_flood: SAVE of an empty program")
    with tempfile.TemporaryDirectory() as d:
        hdr17 = zx_header(b"empty", 0)
        # header block, then the data block's 'S' and its 64K flood
        wire = sa_block(0x00, hdr17)[1:] + bytes([0x53]) + bytes(3000)
        MQ = FakeMQ(wire)
        TSP = FakeTSP(d)
        tio.ENA_SD = lambda: None
        raised = None
        try:
            tio.SAVE_ZX(MQ, TSP)
        except Exception as e:
            raised = e
        check(raised is None,
              "handled the empty save (%s)" % ("clean" if raised is None else repr(raised)))
        check(os.listdir(d) == [], "wrote no file, got %r" % (os.listdir(d),))
        check(MQ.rx_fifo() == 0,
              "swallowed the flood so the FIFO stays in sync, %d left" % MQ.rx_fifo())


def test_load_zx_handshake(tio):
    """LOAD must lead with 0x40 or LD-BYTES' poll never exits."""
    print("test_load_zx_handshake: the 0x40 the compliance sweep deleted")
    with tempfile.TemporaryDirectory() as d:
        data = bytes(range(32))
        hdr17 = zx_header(b"prog", len(data))
        tap = tap_block(0x00, hdr17) + tap_block(0xFF, data)
        tmp = os.path.join(d, "temp.tap")
        open(tmp, "wb").write(tap)

        MQ = FakeMQ()
        TSP = FakeTSP(d, f_name="x.tap", totlen=len(tap))
        real_open = io.open

        # LOAD_ZX reads a fixed path; point it at our temp file.
        import builtins
        real_bopen = builtins.open
        builtins.open = lambda p, *a, **k: real_bopen(
            tmp if str(p).endswith(("temp.tap", "nofile.tap")) else p, *a, **k)
        try:
            tio.LOAD_ZX(MQ, TSP)
        finally:
            builtins.open = real_bopen

        check(MQ.tx and MQ.tx[0] == 0x40,
              "first byte on the wire is the 0x40 handshake, got %r"
              % (MQ.tx[0] if MQ.tx else None,))
        check(len(MQ.tx) >= 2 and MQ.tx[1] == 0x00,
              "then the flag byte that seeds the Z80's parity, got %r"
              % (MQ.tx[1] if len(MQ.tx) > 1 else None,))
        # LD-BYTES consumes 0x40 + flag + datalen + parity for this block.
        want_min = 1 + 1 + 17 + 1
        check(len(MQ.tx) >= want_min,
              "supplied at least the %d bytes LD-BYTES consumes, got %d"
              % (want_min, len(MQ.tx)))
        body = bytes(MQ.tx[1:1 + 19])
        check(body == tap[2:2 + 19],
              "flag+header+parity match the .tap block exactly")


def test_load_zx_c_handshake(tio):
    """Compatible mode handshakes per block, same as normal mode."""
    print("test_load_zx_c_handshake: 0x40 once per block")
    with tempfile.TemporaryDirectory() as d:
        data = bytes(range(24))
        hdr17 = zx_header(b"prog", len(data))
        tap = tap_block(0x00, hdr17) + tap_block(0xFF, data)
        tmp = os.path.join(d, "temp.tap")
        open(tmp, "wb").write(tap)

        MQ = FakeMQ()
        TSP = FakeTSP(d, f_name="x.tap", totlen=len(tap))
        import builtins
        real_bopen = builtins.open
        builtins.open = lambda p, *a, **k: real_bopen(
            tmp if str(p).endswith(("temp.tap", "nofile.tap")) else p, *a, **k)
        try:
            tio.LOAD_ZX_C(MQ, TSP, 65536)
        finally:
            builtins.open = real_bopen

        check(MQ.tx.count(0x40) >= 2,
              "one handshake per block (2 blocks), got %d" % MQ.tx.count(0x40))
        check(MQ.tx and MQ.tx[0] == 0x40,
              "stream opens with the handshake, got %r"
              % (MQ.tx[0] if MQ.tx else None,))
        # Each block is offered as 0x40 + [flag][data][parity], exactly what
        # LD-BYTES consumes -- no spare byte in compatible mode.
        want = ([0x40] + list(tap[2:2 + 19]) + [0x40] + list(tap[21 + 2:21 + 2 + len(data) + 2]))
        check(MQ.tx == want,
              "byte stream matches the ROM's consumption exactly (%d vs %d)"
              % (len(MQ.tx), len(want)))


def test_no_legacy_sm_swap(tio):
    """SAVE_ZX must not hand ZX48_IO back a single-port state machine."""
    print("test_no_legacy_sm_swap: structural check")
    src = io.open(os.path.join(SRC, "TS", "tspico_io.py"), encoding="utf-8").read()
    # Parsed, not grepped: the fix quotes the line it replaced in both a
    # comment and the docstring, and neither is a call.
    import ast
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "SAVE_ZX")
    called = {c.func.id for c in ast.walk(fn)
              if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
    check("ENA_MQ" not in called,
          "SAVE_ZX no longer calls the legacy single-port ENA_MQ")
    check("ENA_MQ_DUAL" in called,
          "SAVE_ZX rebuilds the dual-port SM instead")
    check("START_WATCHDOG" in called,
          "SAVE_ZX spawns its watchdog through the guard")


def test_zx_handlers_have_no_status_writes(tio):
    """ZX mode has no status channel; no handler may invent one."""
    print("test_zx_handlers_have_no_status_writes: structural check")
    # Parsed, not grepped: the docstring names REFUSE_SAVE to explain why
    # it does NOT apply here, and that mention is not a call.
    import ast
    src = io.open(os.path.join(SRC, "TS", "tspico_io.py"), encoding="utf-8").read()
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "SAVE_ZX")
    calls = [c for c in ast.walk(fn) if isinstance(c, ast.Call)]
    names = {c.func.id for c in calls if isinstance(c.func, ast.Name)}
    check("REFUSE_SAVE" not in names,
          "SAVE_ZX does not call REFUSE_SAVE (no status path in ZX mode)")

    def is_put(c):
        if isinstance(c.func, ast.Name):
            return c.func.id == "wrt"
        return isinstance(c.func, ast.Attribute) and c.func.attr == "put"
    status_writes = [c for c in calls if is_put(c) and c.args
                     and isinstance(c.args[0], ast.Constant)
                     and c.args[0].value == 1]
    check(not status_writes,
          "SAVE_ZX stages no 0x01 status byte, found %d" % len(status_writes))


def main():
    print("=" * 64)
    print("ZX48 mode host test")
    print("=" * 64)
    install_fakes()
    sys.path.insert(0, SRC)
    import TS.tspico_io as tio

    import time as _rt
    tio.time = types.SimpleNamespace(
        ticks_ms=lambda: int(_rt.monotonic() * 1000),
        ticks_us=lambda: int(_rt.monotonic() * 1_000_000),
        ticks_diff=lambda a, b: a - b)

    test_save_zx_roundtrip(tio)
    test_save_zx_parity_seed(tio)
    test_save_zx_empty_flood(tio)
    test_load_zx_handshake(tio)
    test_load_zx_c_handshake(tio)
    test_no_legacy_sm_swap(tio)
    test_zx_handlers_have_no_status_writes(tio)

    print("=" * 64)
    print("RESULT: %d passed, %d failed" % (PASS, FAIL))
    print("=" * 64)
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
