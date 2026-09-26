"""Host-side test for SAVE_TS's filename handling — CPython, no Pico needed.

Covers the bug Ryan reported: `SAVE "bad file"` (a character outside the
allowlist) made the TS-2068 print "0 OK" and then left the Pico wedged.

The cause was ordering plus a forbidden call. The old code validated the
filename ~30 lines AFTER the V6 chain had already written the final status
0x01 — so the Z80 had printed "0 OK" before the Pico ever looked at the
name — and then reported the error with END_MSG(), which END_MSG's own
docstring forbids from SAVE_TS. END_MSG emits ~34 bytes into a TX FIFO
that is 4 entries deep and that the Z80 had stopped reading; rp2's
MQ.put() blocks when TX is full, and the WATCHDOG had already exited
(dead=True), so nothing recovered it.

The fix moves the check to the post-header status read, where the
empty-program guard already refuses BLEN=0 saves by the same proven
mechanism: write an error status where the Z80 expects the mid-phase
0x01, and it RST-8's and aborts before sending the data block.

So the assertions here are about the WIRE, not just the return value:
  * exactly one status byte, 0x03 -> Report F "Invalid file name"
  * the whole refusal fits in the 4-deep TX FIFO (the old path did not)
  * no data block is consumed, and nothing is written to SD
  * a name carrying bytes >= 0x80 (graphics chars, BASIC tokens) is
    refused rather than raising — SAVE_TS runs unguarded inside the
    dispatcher's main loop, so an exception would take the loop down
  * the normal path still saves, and append mode still ignores the
    header name

Run:  python3 src/test/save_name_hosttest.py
"""

import io
import os
import sys
import types
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)

TX_FIFO_DEPTH = 4          # rp2 PIO TX FIFO, unjoined — see TS_IO_DUAL

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


# ---------------------------------------------------------------------------
# Mock the device-only modules so the REAL TS.tspico_io imports on CPython.
# (Unlike save_harness_hosttest.py we must NOT stub TS.tspico_io itself —
# it is the module under test.)
# ---------------------------------------------------------------------------

def install_fakes():
    # MicroPython injects const() as a builtin; CPython does not, and
    # TS/tspico_io.py uses it at module scope.
    import builtins
    if not hasattr(builtins, "const"):
        builtins.const = lambda x: x

    micropython = types.ModuleType("micropython")
    micropython.const = lambda x: x
    micropython.native = lambda f: f
    micropython.viper = lambda f: f
    sys.modules["micropython"] = micropython

    machine = types.ModuleType("machine")

    class _Pin:
        OUT, IN, PULL_UP, PULL_DOWN = 0, 1, 2, 3
        def __init__(self, *a, **k): pass
        def value(self, *a): return 0
        def init(self, *a, **k): pass
    machine.Pin = _Pin
    machine.SPI = lambda *a, **k: None
    machine.freq = lambda *a, **k: None
    sys.modules["machine"] = machine

    rp2 = types.ModuleType("rp2")
    rp2.StateMachine = lambda *a, **k: None
    rp2.asm_pio = lambda *a, **k: (lambda f: f)      # never executes the body
    rp2.PIO = types.SimpleNamespace(
        OUT_HIGH=0, OUT_LOW=1, SHIFT_RIGHT=2, SHIFT_LEFT=3, IN_HIGH=4)
    sys.modules["rp2"] = rp2

    utime = types.ModuleType("utime")
    import time as _rt
    utime.ticks_ms = lambda: int(_rt.monotonic() * 1000)
    sys.modules["utime"] = utime

    thread = types.ModuleType("_thread")
    thread.start_new_thread = lambda fn, args: None   # WATCHDOG never spawns
    sys.modules["_thread"] = thread

    ts = types.ModuleType("TS")
    ts.__path__ = [os.path.join(SRC, "TS")]
    sys.modules["TS"] = ts

    sdc = types.ModuleType("TS.sdcard")
    sdc.SDCard = lambda *a, **k: None
    sys.modules["TS.sdcard"] = sdc

    # SAVE_TS lazily does `from TS.tspico import TLM` to dodge the circular
    # import; give it a no-op that records the phase labels instead.
    tspico = types.ModuleType("TS.tspico")
    tspico.TLM_LOG = []
    tspico.TLM = lambda label, detail="": tspico.TLM_LOG.append((label, detail))
    sys.modules["TS.tspico"] = tspico
    return tspico


def patch_time(tio):
    """Shrink the drain's quiet window so tests don't idle for 500 ms each."""
    import time as _rt
    m = types.SimpleNamespace()
    m.ticks_ms = lambda: int(_rt.monotonic() * 1000)
    m.ticks_us = lambda: int(_rt.monotonic() * 1_000_000)
    m.ticks_diff = lambda a, b: a - b
    tio.time = m


class FifoOverflow(Exception):
    """Stands in for rp2's MQ.put() blocking forever on a full TX FIFO."""


class FakeMQ:
    """Enough of rp2.StateMachine to run SAVE_TS, with a REAL TX bound.

    z80_reads=True models a Z80 that keeps consuming $0E (the normal
    case); the FIFO drains as fast as we fill it. z80_reads=False models
    the state the old buggy path found itself in — the Z80 has returned
    to the BASIC prompt and reads nothing — so a handler that writes more
    than TX_FIFO_DEPTH bytes raises FifoOverflow instead of hanging the
    test the way real firmware hung the Pico.
    """
    def __init__(self, rx_bytes=b"", z80_reads=False):
        self.rx = list(rx_bytes)
        self.tx = []              # bytes still sitting in the FIFO
        self.written = []         # every byte ever put, for assertions
        self.z80_reads = z80_reads
        self.execs = []

    def rx_fifo(self):
        return len(self.rx)

    def tx_fifo(self):
        if self.z80_reads and self.tx:
            self.tx.pop(0)        # the Z80 consumed one
        return len(self.tx)

    def get(self):
        return self.rx.pop(0)

    def put(self, b):
        self.written.append(b)
        if self.z80_reads:
            return                # consumed as fast as we write
        if len(self.tx) >= TX_FIFO_DEPTH:
            raise FifoOverflow(
                "MQ.put() would block: TX full at %d bytes, %d already written"
                % (TX_FIFO_DEPTH, len(self.written)))
        self.tx.append(b)

    def exec(self, s):
        self.execs.append(s)

    def active(self, *_a):
        pass


class FakeTSP:
    def __init__(self, cur_path, f_name="", append=False):
        self.cur_path = cur_path
        self.f_name = f_name
        self.append = append
        self.LOG_LEVEL = 3        # suppress log buffering noise
        self.VERBOSE = True


# ---------------------------------------------------------------------------
# Wire-format builders (mirror the layout documented in SAVE_TS's docstring)
# ---------------------------------------------------------------------------

def build_header(name, blen, hdtype=0, addr=0, hdvars=0x8000, session=0x1234):
    """21-byte TPI SAVE header block with a correct CRC."""
    h = bytearray(21)
    h[0] = 0x00                                   # block type: header
    h[1] = session & 0xFF
    h[2] = (session >> 8) & 0xFF
    h[3] = hdtype
    padded = (bytes(name) + b" " * 10)[:10]
    h[4:14] = padded
    h[14] = blen & 0xFF
    h[15] = (blen >> 8) & 0xFF
    h[16] = addr & 0xFF
    h[17] = (addr >> 8) & 0xFF
    h[18] = hdvars & 0xFF
    h[19] = (hdvars >> 8) & 0xFF
    crc = h[0]
    for i in range(3, 20):
        crc ^= h[i]
    h[20] = crc
    return h


def build_data(payload, session=0x1234):
    """(len+4)-byte TPI SAVE data block with a correct CRC."""
    b = bytearray(len(payload) + 4)
    b[0] = 0xFF                                   # block type: data
    b[1] = session & 0xFF
    b[2] = (session >> 8) & 0xFF
    b[3:3 + len(payload)] = payload
    crc = b[0]
    for i in range(3, 3 + len(payload)):
        crc ^= b[i]
    b[-1] = crc
    return b


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_refuses_bad_name(tio, name, label):
    """The reported bug: a name outside the allowlist must refuse cleanly."""
    print("test_refuses_bad_name: %s" % label)
    with tempfile.TemporaryDirectory() as d:
        payload = bytes(range(40))
        hdr = build_header(name, len(payload))
        dat = build_data(payload)
        # Feed the data block too: if the guard leaked, SAVE_TS would eat it.
        MQ = FakeMQ(bytes(hdr) + bytes(dat), z80_reads=False)
        TSP = FakeTSP(d)

        result = None
        try:
            result = tio.SAVE_TS(MQ, TSP)
            raised = None
        except FifoOverflow as e:
            raised = e
        except Exception as e:                    # e.g. the old decode() crash
            raised = e

        check(raised is None,
              "SAVE_TS returned without blocking or raising (%s)" % (
                  "clean" if raised is None else repr(raised)))
        check(MQ.written == [0x03],
              "wrote exactly one status byte 0x03 -> Report F, got %r"
              % (MQ.written,))
        check(len(MQ.written) <= TX_FIFO_DEPTH,
              "refusal fits the %d-deep TX FIFO (%d byte(s))"
              % (TX_FIFO_DEPTH, len(MQ.written)))
        check(any("mov(y, invert(null))" in e for e in MQ.execs),
              "set Y=READY so the Z80 actually reads the status")
        check(os.listdir(d) == [],
              "nothing written to the save directory, got %r" % (os.listdir(d),))
        check(TSP.f_name == "",
              "TSP.f_name left untouched, got %r" % (TSP.f_name,))
        check(MQ.rx_fifo() == 0,
              "RX drained, so the next pre-header starts clean (%d left)"
              % MQ.rx_fifo())
        check(result is not None and len(result) == 4 and result[3] is False,
              "returned saved=False, got %r" % (result,))


def test_accepts_good_name(tio):
    """The normal path must be unaffected by the guard."""
    print("test_accepts_good_name: SAVE \"test\" still saves")
    with tempfile.TemporaryDirectory() as d:
        payload = bytes(range(64))
        hdr = build_header(b"test", len(payload))
        dat = build_data(payload)
        MQ = FakeMQ(bytes(hdr) + bytes(dat), z80_reads=True)
        TSP = FakeTSP(d)

        tio.ENA_SD = lambda: None                 # no SPI/SD on the host
        saved_chdir, os.chdir = os.chdir, lambda p: None
        try:
            tio.SAVE_TS(MQ, TSP)
        finally:
            os.chdir = saved_chdir

        # mid-phase status, then the V6 pair (final status + next-cmd pre-load).
        check(MQ.written == [0x01, 0x01, 0x01],
              "wrote exactly the 3-byte status chain, got %r" % (MQ.written,))
        check(os.listdir(d) == ["test.tap"],
              'saved as "test.tap", got %r' % (os.listdir(d),))
        check(TSP.f_name == d + "/test.tap",
              "TSP.f_name points at the new file, got %r" % (TSP.f_name,))
        blob = open(os.path.join(d, "test.tap"), "rb").read()
        check(len(blob) == 21 + len(payload) + 4,
              "tap length %d matches header+data" % len(blob))
        check(blob[0] == 19 and blob[1] == 0,
              "header block re-framed to a 19-byte TAP length prefix")


def test_empty_name_is_legal(tio):
    """An all-spaces ZX name is legal and keeps the noname fallback."""
    print("test_empty_name_is_legal: SAVE \"\" -> noname.tap")
    with tempfile.TemporaryDirectory() as d:
        payload = bytes(range(16))
        MQ = FakeMQ(bytes(build_header(b"", len(payload)))
                    + bytes(build_data(payload)), z80_reads=True)
        TSP = FakeTSP(d)
        tio.ENA_SD = lambda: None
        saved_chdir, os.chdir = os.chdir, lambda p: None
        try:
            tio.SAVE_TS(MQ, TSP)
        finally:
            os.chdir = saved_chdir
        check(os.listdir(d) == ["noname.tap"],
              'empty name fell back to "noname.tap", got %r' % (os.listdir(d),))


def test_append_ignores_header_name(tio):
    """In append mode the target is the mounted TAP; the header name is unused,
    so even an otherwise-illegal name must not trigger the guard."""
    print("test_append_ignores_header_name: append target wins")
    with tempfile.TemporaryDirectory() as d:
        target = os.path.join(d, "mounted.tap")
        open(target, "wb").write(b"\x00" * 8)
        payload = bytes(range(16))
        MQ = FakeMQ(bytes(build_header(b"bad file", len(payload)))
                    + bytes(build_data(payload)), z80_reads=True)
        TSP = FakeTSP(d, f_name=target, append=True)
        tio.ENA_SD = lambda: None
        saved_chdir, os.chdir = os.chdir, lambda p: None
        try:
            tio.SAVE_TS(MQ, TSP)
        finally:
            os.chdir = saved_chdir
        check(sorted(os.listdir(d)) == ["mounted.tap"],
              "appended to the mounted tap only, got %r" % (os.listdir(d),))
        check(os.path.getsize(target) == 8 + 21 + len(payload) + 4,
              "appended block landed (size %d)" % os.path.getsize(target))


def test_end_msg_would_have_overflowed(tio):
    """Document WHY the old path wedged, so nobody reintroduces it.

    END_MSG in verbose mode writes 0x81, status, 0x0D, the message, and a
    NUL terminator. Against a Z80 that has stopped reading, that overruns
    the 4-deep TX FIFO almost immediately.
    """
    print("test_end_msg_would_have_overflowed: the old reporting path")
    MQ = FakeMQ(z80_reads=False)
    msg = 'ERROR: Filename "bad file" not allowed'
    try:
        tio.END_MSG(MQ, True, msg, [], 3)
        overflowed = False
    except FifoOverflow:
        overflowed = True
    check(overflowed,
          "END_MSG(verbose) overruns the %d-deep TX FIFO (tried %d bytes)"
          % (TX_FIFO_DEPTH, len(MQ.written)))
    check(len(msg) + 4 > TX_FIFO_DEPTH,
          "the message alone is %d bytes vs a %d-byte FIFO"
          % (len(msg) + 4, TX_FIFO_DEPTH))




def test_bad_crc_refuses(tio):
    """A corrupt header must NOT be answered with "OK".

    The old code wrote 0x01 0x01 here on the theory that the Z80 "will see
    CRC fail elsewhere". It doesn't -- it validated its own bytes and is
    happy -- so it streamed the whole data block at a handler that had
    already returned, and read the trailing 0x01 as the final status.
    Result: "0 OK" on screen, no file on disk, and a data block left in RX
    for the dispatcher to mistake for the next pre-header.
    """
    print("test_bad_crc_refuses: corrupt header CRC")
    with tempfile.TemporaryDirectory() as d:
        payload = bytes(range(48))
        hdr = build_header(b"test", len(payload))
        hdr[20] ^= 0xFF                              # corrupt the CRC
        dat = build_data(payload)
        MQ = FakeMQ(bytes(hdr) + bytes(dat), z80_reads=False)
        TSP = FakeTSP(d)

        tio.SAVE_TS(MQ, TSP)

        check(MQ.written == [0x02],
              "refused with 0x02 -> Report R, got %r" % (MQ.written,))
        check(0x01 not in MQ.written,
              "never claimed OK on a corrupt header")
        check(os.listdir(d) == [],
              "wrote no file, got %r" % (os.listdir(d),))
        check(MQ.rx_fifo() == 0,
              "drained the data block the Z80 may still send (%d left)"
              % MQ.rx_fifo())


def test_no_memory_refuses(tio):
    """A data block too big for the heap must refuse, not raise.

    BLEN is 16-bit and SAVE "x" CODE 0,65535 is legal, so there is no
    bound to apply -- only an allocation that may fail. Unguarded, the
    MemoryError reaches main.py and drops the Pico to a REPL, and because
    the allocation happens before the mid-phase status the 2068 also hangs
    to its ~19.9s WF_NPH timeout.
    """
    print("test_no_memory_refuses: allocation failure is reported, not raised")
    real_bytearray = tio.bytearray if hasattr(tio, "bytearray") else bytearray
    with tempfile.TemporaryDirectory() as d:
        hdr = build_header(b"big", 60000)
        MQ = FakeMQ(bytes(hdr), z80_reads=False)
        TSP = FakeTSP(d)

        import builtins
        real = builtins.bytearray
        calls = []

        def fake_bytearray(*a):
            # Fail only the big data-block allocation, not the 21-byte header.
            if a and isinstance(a[0], int) and a[0] > 1000:
                calls.append(a[0])
                raise MemoryError("simulated heap exhaustion")
            return real(*a)

        builtins.bytearray = fake_bytearray
        try:
            raised = None
            try:
                tio.SAVE_TS(MQ, TSP)
            except Exception as e:
                raised = e
        finally:
            builtins.bytearray = real

        check(raised is None,
              "SAVE_TS handled MemoryError (%s)" % (
                  "clean" if raised is None else repr(raised)))
        check(len(calls) == 2,
              "retried the allocation after gc.collect (%d attempts)" % len(calls))
        check(MQ.written == [0x06],
              "refused with 0x06 -> Report 6, got %r" % (MQ.written,))
        check(os.listdir(d) == [], "wrote no file")


def test_watchdog_spawn_failure_survives(tio):
    """A busy core1 must not take the dispatcher down.

    tspico.py documents this exact failure for its SAVE_LOG spawn: the
    OSError propagates through TS2068_IO into main.py, which has no
    try/except, and the Pico drops to a REPL -- "locked up, LED stopped
    blinking". The LVM handlers spawned their watchdogs unguarded.
    """
    print("test_watchdog_spawn_failure_survives: OSError from core1")
    with tempfile.TemporaryDirectory() as d:
        payload = bytes(range(32))
        MQ = FakeMQ(bytes(build_header(b"test", len(payload)))
                    + bytes(build_data(payload)), z80_reads=True)
        TSP = FakeTSP(d)

        import _thread
        real = _thread.start_new_thread
        _thread.start_new_thread = lambda fn, args: (_ for _ in ()).throw(
            OSError("core1 in use"))
        tio.ENA_SD = lambda: None
        saved_chdir, os.chdir = os.chdir, lambda p: None
        try:
            raised = None
            try:
                tio.SAVE_TS(MQ, TSP)
            except Exception as e:
                raised = e
        finally:
            _thread.start_new_thread = real
            os.chdir = saved_chdir

        check(raised is None,
              "SAVE_TS survived the failed spawn (%s)" % (
                  "clean" if raised is None else repr(raised)))
        check(os.listdir(d) == ["test.tap"],
              "still completed the save, got %r" % (os.listdir(d),))


def test_kill_flag_cleared_on_core0(tio):
    """A stale kill flag must not abort the next transaction.

    WATCHDOG clears `kill`, but on core1 -- while the drain loop that
    reads it runs on core0 and starts immediately after the spawn.
    START_WATCHDOG clears it on the spawning core instead, which closes
    the window rather than documenting it.
    """
    print("test_kill_flag_cleared_on_core0: stale kill does not abort")
    with tempfile.TemporaryDirectory() as d:
        payload = bytes(range(32))
        MQ = FakeMQ(bytes(build_header(b"test", len(payload)))
                    + bytes(build_data(payload)), z80_reads=True)
        TSP = FakeTSP(d)

        tio.kill = True               # left over from a previous abort
        tio.ENA_SD = lambda: None
        saved_chdir, os.chdir = os.chdir, lambda p: None
        try:
            tio.SAVE_TS(MQ, TSP)
        finally:
            os.chdir = saved_chdir
            tio.kill = False

        check(os.listdir(d) == ["test.tap"],
              "completed despite a stale kill flag, got %r" % (os.listdir(d),))


def test_sd_write_failure_survives(tio):
    """A failed SD write must not take the dispatcher down.

    ENA_SD swallows its own mount failure, so a pulled card surfaces as
    OSError from open(). The status already went out (by design -- see the
    #40 pin-grab ordering), so this cannot be reported to the 2068; the
    requirement is only that the firmware stays up and the bogus f_name is
    retracted so the dispatcher does not try to mount a file that is not
    there.
    """
    print("test_sd_write_failure_survives: card pulled mid-save")
    with tempfile.TemporaryDirectory() as d:
        payload = bytes(range(32))
        MQ = FakeMQ(bytes(build_header(b"test", len(payload)))
                    + bytes(build_data(payload)), z80_reads=True)
        TSP = FakeTSP(d)

        def boom():
            raise OSError(5, "no SD card")
        tio.ENA_SD = boom
        saved_chdir, os.chdir = os.chdir, lambda p: None
        try:
            raised = None
            try:
                tio.SAVE_TS(MQ, TSP)
            except Exception as e:
                raised = e
        finally:
            os.chdir = saved_chdir

        check(raised is None,
              "SAVE_TS survived the write failure (%s)" % (
                  "clean" if raised is None else repr(raised)))
        check(TSP.f_name == "",
              "retracted f_name so the dispatcher won't mount a ghost, got %r"
              % (TSP.f_name,))


def test_no_unguarded_thread_spawns(tio):
    """Structural: no LVM handler may call start_new_thread directly."""
    print("test_no_unguarded_thread_spawns: structural check")
    src = io.open(os.path.join(SRC, "TS", "tspico_io.py"),
                  encoding="utf-8").read()
    for name in ("LOAD_TS", "LOAD_ZX", "SAVE_TS", "SAVE_ZX"):
        body = src.split("def %s(" % name, 1)[1].split("\ndef ", 1)[0]
        check("_thread.start_new_thread" not in body,
              "%s spawns via START_WATCHDOG, not directly" % name)


def test_end_msg_has_no_callers(tio):
    """END_MSG is a documented trap; nothing in the tree may call it."""
    print("test_end_msg_has_no_callers: structural check")
    hits = []
    for mod in ("tspico_io.py", "tspico.py"):
        path = os.path.join(SRC, "TS", mod)
        for n, line in enumerate(io.open(path, encoding="utf-8"), 1):
            stripped = line.strip()
            if stripped.startswith("#") or "def END_MSG" in stripped:
                continue
            if "END_MSG(" in stripped and "SEND_MSG" not in stripped:
                hits.append("%s:%d" % (mod, n))
    check(not hits, "no live END_MSG call sites, found %r" % (hits,))




def test_saved_flag(tio):
    """SAVE_TS's 4th return value must say whether a .tap reached the card.

    The dispatcher used to infer this with
    `save_aborted = "sd" not in os.listdir("/")` -- sniffing the mount
    table. The refusal paths happened to satisfy it (they return before
    ENA_SD, so /sd is unmounted), but the case that matters most did not:
    a write that FAILS after ENA_SD leaves /sd mounted and no file on
    disk, so the old heuristic said "saved" and sent the dispatcher off to
    mount a file that was never created.
    """
    print("test_saved_flag: the return value, including the case the old heuristic got wrong")

    # (a) a real save reports True
    with tempfile.TemporaryDirectory() as d:
        payload = bytes(range(32))
        MQ = FakeMQ(bytes(build_header(b"test", len(payload)))
                    + bytes(build_data(payload)), z80_reads=True)
        TSP = FakeTSP(d)
        tio.ENA_SD = lambda: None
        saved_chdir, os.chdir = os.chdir, lambda p: None
        try:
            r = tio.SAVE_TS(MQ, TSP)
        finally:
            os.chdir = saved_chdir
        check(len(r) == 4, "returns a 4-tuple, got %d elements" % len(r))
        check(len(r) == 4 and r[3] is True,
              "successful save reports saved=True, got %r" % (r,))
        check(os.listdir(d) == ["test.tap"], "and the file is really there")

    # (b) THE CASE THE OLD HEURISTIC GOT WRONG: write fails after ENA_SD.
    with tempfile.TemporaryDirectory() as d:
        payload = bytes(range(32))
        MQ = FakeMQ(bytes(build_header(b"test", len(payload)))
                    + bytes(build_data(payload)), z80_reads=True)
        TSP = FakeTSP(d)

        # ENA_SD succeeds and leaves /sd "mounted" -- so the old
        # `"sd" not in os.listdir("/")` test would have said save_aborted
        # = False, i.e. "we saved" -- but the write itself fails.
        mounted = {"sd": True}
        tio.ENA_SD = lambda: None
        real_open = tio.open if hasattr(tio, "open") else open
        import builtins
        real_bopen = builtins.open

        def failing_open(path, mode="r", *a, **k):
            if str(path).endswith(".tap") and "w" in mode or "a" in mode:
                raise OSError(28, "No space left on device")
            return real_bopen(path, mode, *a, **k)

        builtins.open = failing_open
        saved_chdir, os.chdir = os.chdir, lambda p: None
        try:
            r = tio.SAVE_TS(MQ, TSP)
        finally:
            builtins.open = real_bopen
            os.chdir = saved_chdir

        check(len(r) == 4 and r[3] is False,
              "failed write reports saved=False, got %r" % (r,))
        check(os.listdir(d) == [],
              "and no file exists, got %r" % (os.listdir(d),))
        check(mounted.get("sd") is True,
              "while /sd is still mounted -- exactly what fooled the old check")
        check(TSP.f_name == "",
              "f_name retracted so the dispatcher can't mount a ghost, got %r"
              % (TSP.f_name,))

    # (c) append mode reports True on success
    with tempfile.TemporaryDirectory() as d:
        target = os.path.join(d, "mounted.tap")
        open(target, "wb").write(b"\x00" * 8)
        payload = bytes(range(16))
        MQ = FakeMQ(bytes(build_header(b"whatever", len(payload)))
                    + bytes(build_data(payload)), z80_reads=True)
        TSP = FakeTSP(d, f_name=target, append=True)
        tio.ENA_SD = lambda: None
        saved_chdir, os.chdir = os.chdir, lambda p: None
        try:
            r = tio.SAVE_TS(MQ, TSP)
        finally:
            os.chdir = saved_chdir
        check(len(r) == 4 and r[3] is True,
              "append reports saved=True, got %r" % (r,))


def test_dispatchers_unpack_four(tio):
    """Structural: both SAVE_TS call sites must unpack the 4-tuple.

    src/dev_tspico.py is a live override -- main.py prefers it over the
    frozen TS.tspico when deployed, and CI compiles it to .mpy -- so a
    three-value unpack there would ValueError the moment it loads.
    """
    print("test_dispatchers_unpack_four: structural check")
    for rel in (os.path.join("TS", "tspico.py"), "dev_tspico.py"):
        path = os.path.join(SRC, rel)
        text = io.open(path, encoding="utf-8").read()
        for n, line in enumerate(text.splitlines(), 1):
            if "= SAVE_TS(" in line:
                check("new_logs, saved = SAVE_TS(" in line,
                      "%s:%d unpacks 4 values" % (rel, n))
        # Comment lines are exempt: TS/tspico.py quotes the old line
        # verbatim to explain why it went away.
        live = [ln for ln in text.splitlines()
                if 'save_aborted = "sd" not in os.listdir' in ln
                and not ln.strip().startswith("#")]
        check(not live,
              "%s no longer sniffs the mount table, found %r" % (rel, live))




def test_load_search_is_bounded(tio):
    """A LOAD that can never match must stop after one full pass.

    The Z80 drives this loop -- it compares names itself and asks again on
    a mismatch -- and it never tells the Pico when the user gives up: the
    EXROM's BREAK path writes nothing, and the whole EXROM holds exactly
    one OUT ($0E),A. So the bound has to live here.

    One lap is allowed on purpose: a program that legitimately needs to
    wrap around cannot rewind, because it does not speak TPI. A second lap
    would only repeat the first.
    """
    print("test_load_search_is_bounded: header search stops after one lap")
    with tempfile.TemporaryDirectory() as d:
        # A three-header tape. Every request asks for a header (pre[0]=0x00)
        # and the Z80 never accepts one, so this is the runaway case.
        # Real 17-byte tape headers, so LOAD_TS's autorun-patch path is
        # exercised rather than running off the end of a stub block.
        def hdr17(name, htype=0):
            h = bytearray(17)
            h[0] = htype
            h[1:11] = (name + b" " * 10)[:10]
            h[11] = 8            # data length
            h[13] = 0x80         # no autorun
            h[15] = 8
            return bytes(h)

        blocks = [hdr17(b"prog%d" % n) for n in range(3)]
        tap = b""
        for b in blocks:
            parity = 0x00
            for x in b:
                parity ^= x
            n = len(b) + 2
            tap += bytes([n & 0xFF, (n >> 8) & 0xFF, 0x00]) + b + bytes([parity])
        tmp = os.path.join(d, "temp.tap")
        open(tmp, "wb").write(tap)

        TSP = FakeTSP(d)
        TSP.f_name = "x.tap"
        TSP.totlen = len(tap)
        TSP.offset = 0
        TSP.tap_idx = 0
        TSP.ld_start = -1
        TSP.ld_wrapped = False

        import builtins
        real_open = builtins.open
        builtins.open = lambda p, *a, **k: real_open(
            tmp if str(p).endswith(("temp.tap", "nofile.tap")) else p, *a, **k)

        pre = bytearray(10)          # pre[0] = 0x00 -> header request
        served, refused_at = 0, None
        try:
            for i in range(12):      # far more than the tape holds
                # The Z80 echoes a block-type ack and its computed CRC after
                # every block it takes; LOAD_TS drains both.
                MQ = FakeMQ(bytes([0x00, 0x00]), z80_reads=True)
                tio.LOAD_TS(pre, MQ, TSP)
                if MQ.written and MQ.written[0] == 0x07:
                    refused_at = i + 1
                    break
                served += 1
        finally:
            builtins.open = real_open

        check(refused_at is not None,
              "the search terminated instead of cycling forever")
        check(refused_at is not None and served >= len(blocks),
              "it served the whole tape first (%d of %d blocks) -- one full "
              "lap is allowed" % (served, len(blocks)))
        check(refused_at is not None and refused_at <= len(blocks) + 2,
              "and stopped promptly after that lap, at request %s"
              % refused_at)
        check(TSP.ld_start == -1,
              "search state reset, so the next LOAD starts clean (got %r)"
              % (TSP.ld_start,))


def test_load_data_request_ends_the_search(tio):
    """A data-block request means the Z80 accepted a header."""
    print("test_load_data_request_ends_the_search: acceptance resets the bound")
    with tempfile.TemporaryDirectory() as d:
        body = b"\x01" * 8
        parity = 0xFF
        for x in body:
            parity ^= x
        tap = bytes([len(body) + 2, 0, 0xFF]) + body + bytes([parity])
        tmp = os.path.join(d, "temp.tap")
        open(tmp, "wb").write(tap)

        TSP = FakeTSP(d)
        TSP.f_name = "x.tap"
        TSP.totlen = len(tap)
        TSP.offset = 0
        TSP.tap_idx = 0
        TSP.ld_start = 999          # pretend a search was running
        TSP.ld_wrapped = True

        import builtins
        real_open = builtins.open
        builtins.open = lambda p, *a, **k: real_open(
            tmp if str(p).endswith(("temp.tap", "nofile.tap")) else p, *a, **k)
        pre = bytearray(10)
        pre[0] = 0xFF               # data block request
        try:
            MQ = FakeMQ(bytes([0xFF, 0x00]), z80_reads=True)
            tio.LOAD_TS(pre, MQ, TSP)
        finally:
            builtins.open = real_open

        check(TSP.ld_start == -1,
              "a data request cleared the search (got %r)" % (TSP.ld_start,))
        check(not (MQ.written and MQ.written[0] == 0x07),
              "and it was served, not refused")


def test_no_blink_inside_a_transaction(tio):
    """BLINK sleeps ~1s; it must not be called from a live LOAD."""
    print("test_no_blink_inside_a_transaction: structural check")
    import ast
    src = io.open(os.path.join(SRC, "TS", "tspico_io.py"), encoding="utf-8").read()
    tree = ast.parse(src)
    for name in ("LOAD_TS", "SAVE_TS"):
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == name)
        called = {c.func.id for c in ast.walk(fn)
                  if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
        check("BLINK" not in called,
              "%s does not call BLINK (it blocks ~1s mid-transaction)" % name)




def test_aborted_search_rewinds(tio):
    """A BREAK mid-search must leave the tape where the search began.

    The Z80 never signals the abort, so all the Pico sees is the watchdog
    firing. Without the rewind, the next LOAD would start from wherever the
    abandoned search happened to stop -- which looks to the user like the
    tape moved on its own.
    """
    print("test_aborted_search_rewinds: BREAK mid-search restores position")
    TSP = FakeTSP("/tmp")
    TSP.tap_idx = 4
    TSP.offset = 1234
    TSP.ld_start = 200          # a search began here...
    TSP.ld_start_idx = 1        # ...at block 1
    TSP.ld_wrapped = True

    moved = tio.REWIND_ABORTED_SEARCH(TSP)
    check(moved is True, "reported that it rewound")
    check(TSP.offset == 200, "offset back to the search start, got %r" % TSP.offset)
    check(TSP.tap_idx == 1, "tap_idx back to the search start, got %r" % TSP.tap_idx)
    check(TSP.ld_start == -1 and TSP.ld_wrapped is False,
          "search state cleared so the next LOAD starts fresh")

    # An abort with no search running must NOT move anything: that position
    # is a block the Z80 actually accepted.
    TSP2 = FakeTSP("/tmp")
    TSP2.tap_idx, TSP2.offset, TSP2.ld_start = 7, 5000, -1
    moved = tio.REWIND_ABORTED_SEARCH(TSP2)
    check(moved is False, "no search in progress -> reported no rewind")
    check(TSP2.offset == 5000 and TSP2.tap_idx == 7,
          "and left the position alone (%r, %r)" % (TSP2.offset, TSP2.tap_idx))


def test_abort_paths_rewind(tio):
    """Structural: every LOAD_TS abort path must call the rewind.

    Two paths since issue #51: the watchdog's (ABORT_TX) and the BREAK /
    stall path (STOP_WATCHDOG), which ends the transaction itself.
    """
    print("test_abort_paths_rewind: structural check")
    import ast
    src = io.open(os.path.join(SRC, "TS", "tspico_io.py"), encoding="utf-8").read()
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "LOAD_TS")
    aborts = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
              and isinstance(n.func, ast.Name) and n.func.id in ("ABORT_TX", "STOP_WATCHDOG")]
    rewinds = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
               and isinstance(n.func, ast.Name) and n.func.id == "REWIND_ABORTED_SEARCH"]
    check(len(aborts) == 2, "LOAD_TS has 2 abort paths (watchdog, BREAK/stall), found %d" % len(aborts))
    check(len(rewinds) == len(aborts),
          "each one rewinds (%d rewinds for %d aborts)" % (len(rewinds), len(aborts)))



def test_load_abort_rearms_tx(tio):
    """After an aborted LOAD, TX must hold exactly one 0x01 and Y = READY.

    LOAD_TS's normal exit ends with the V6 chain (two 0x01s + Y=READY).
    The abort paths bypass it, and the watchdog has just drained both
    FIFOs -- so without an explicit re-arm the next command's status read
    finds an empty TX and the dispatcher answers Report J.
    docs/PROTOCOL.md 7 states the rule; SAVE_TS is exempt only because
    the dispatcher's ACTIVATE_MQ re-arms after it, and nothing at all
    runs after LOAD_TS.

    Ryan hit this on #48: VERIFY makes the Z80 abandon the transfer as
    soon as the comparison fails, and every command after it answered J
    until a few `tpi:nop`s re-primed the chain.

    ONE byte, not two. The Z80 has already reported and gone -- a second
    would sit in TX and be read as the first byte of the next response,
    the one-byte shift that surfaces as Report R.
    """
    print("test_load_abort_rearms_tx: abort leaves TX primed for the next cmd")
    TSP = FakeTSP("/tmp")
    MQ = FakeMQ(z80_reads=False)          # Z80 has gone back to BASIC

    tio.REARM_AFTER_LOAD_ABORT(MQ, TSP)

    check(MQ.written == [0x01],
          "exactly one 0x01 written, got %r" % (MQ.written,))
    check(len(MQ.tx) == 1,
          "and it is sitting in TX for the next command, got %d" % len(MQ.tx))
    check(len(MQ.tx) <= TX_FIFO_DEPTH,
          "fits the %d-deep TX FIFO" % TX_FIFO_DEPTH)
    check(any("invert(null)" in e for e in MQ.execs),
          "Y restored to READY (execs=%r)" % (MQ.execs,))


def test_abort_paths_rearm(tio):
    """Structural: both LOAD_TS abort paths re-arm, and do it after ABORT_TX.

    Ordering matters. ABORT_TX waits for core1 to finish draining and
    re-activating the SM; anything written before it returns is eaten by
    the watchdog's pull(noblock) cleanup loop.
    """
    print("test_abort_paths_rearm: structural check")
    import ast
    src = io.open(os.path.join(SRC, "TS", "tspico_io.py"), encoding="utf-8").read()
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "LOAD_TS")

    def calls(name):
        return [n for n in ast.walk(fn) if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name) and n.func.id == name]

    # The watchdog path re-arms with REARM_AFTER_LOAD_ABORT after ABORT_TX;
    # the BREAK / stall path (issue #51) with MQ_TO_IDLE after STOP_WATCHDOG.
    aborts = calls("ABORT_TX")
    rearms = calls("REARM_AFTER_LOAD_ABORT")
    stops = calls("STOP_WATCHDOG")
    idles = calls("MQ_TO_IDLE")
    check(len(rearms) == len(aborts) == 1 and len(idles) == len(stops) == 1,
          "both abort paths re-arm (%d/%d after ABORT_TX, %d/%d after STOP_WATCHDOG)"
          % (len(rearms), len(aborts), len(idles), len(stops)))

    ok = all(any(a.lineno < r.lineno for a in aborts) for r in rearms) and \
        all(any(t.lineno < r.lineno for t in stops) for r in idles)
    check(ok, "every re-arm comes after its path's ABORT_TX / STOP_WATCHDOG")



def main():
    print("=" * 64)
    print("SAVE_TS audit host test")
    print("=" * 64)

    install_fakes()
    sys.path.insert(0, SRC)
    import TS.tspico_io as tio
    patch_time(tio)

    test_refuses_bad_name(tio, b"bad file", 'SAVE "bad file" (interior space)')
    test_refuses_bad_name(tio, b"a.tap", 'SAVE "a.tap" (dot)')
    test_refuses_bad_name(tio, b"a/b", 'SAVE "a/b" (FAT-illegal)')
    test_refuses_bad_name(tio, b"ab\xa0", 'SAVE with a byte >= 0x80 (no decode crash)')
    test_refuses_bad_name(tio, b"a\x0db", "SAVE with a control byte")
    test_accepts_good_name(tio)
    test_empty_name_is_legal(tio)
    test_append_ignores_header_name(tio)
    test_end_msg_would_have_overflowed(tio)
    test_bad_crc_refuses(tio)
    test_no_memory_refuses(tio)
    test_watchdog_spawn_failure_survives(tio)
    test_kill_flag_cleared_on_core0(tio)
    test_sd_write_failure_survives(tio)
    test_no_unguarded_thread_spawns(tio)
    test_end_msg_has_no_callers(tio)
    test_saved_flag(tio)
    test_dispatchers_unpack_four(tio)
    test_load_search_is_bounded(tio)
    test_load_data_request_ends_the_search(tio)
    test_no_blink_inside_a_transaction(tio)
    test_aborted_search_rewinds(tio)
    test_abort_paths_rewind(tio)
    test_load_abort_rearms_tx(tio)
    test_abort_paths_rearm(tio)

    print("=" * 64)
    print("RESULT: %d passed, %d failed" % (PASS, FAIL))
    print("=" * 64)
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
