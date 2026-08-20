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

        try:
            tio.SAVE_TS(MQ, TSP)
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

    print("=" * 64)
    print("RESULT: %d passed, %d failed" % (PASS, FAIL))
    print("=" * 64)
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
