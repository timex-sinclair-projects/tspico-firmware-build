"""Host-side test for save_harness.py — runs on CPython, no Pico required.

It mocks the machine/rp2/TS.* modules and the MQ state machine, feeds
save_harness the EXACT byte sequence the TS-2068 ROM puts on the wire during
SAVE (derived from the l1879h disassembly), and asserts that the harness:
  * decodes the header, verifies the header CRC,
  * reconstructs both .tap blocks byte-identically to a known-good reference
    (the same layout make_test_tap.py produces),
  * implements create-new vs. append correctly,
  * stages the right status bytes, and
  * reports a partial-byte stall as evidence rather than hanging.

This exercises the harness's real code paths (drain_phase, frame_*_inplace,
choose_target, write_tap, handle_save) — only the PIO/transport is mocked.

Run:  python3 src/test/save_harness_hosttest.py
"""

import os
import sys
import types
import struct
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# Mock the device-only modules so `import save_harness` works on CPython.
# ---------------------------------------------------------------------------

def install_fakes():
    machine = types.ModuleType("machine")
    machine.Pin = lambda *a, **k: types.SimpleNamespace(
        value=lambda *x: None, init=lambda *x, **y: None,
        OUT=0, IN=1, PULL_UP=2, PULL_DOWN=3)
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
        OUT_HIGH=0, OUT_LOW=1, SHIFT_RIGHT=2, SHIFT_LEFT=3, IN_HIGH=4)
    sys.modules["rp2"] = rp2

    ts = types.ModuleType("TS")
    ts.__path__ = []
    sys.modules["TS"] = ts
    tio = types.ModuleType("TS.tspico_io")
    tio.TS_IO_DUAL = object()
    tio.set_ctrl = object()
    tio.sel_bank = object()
    sys.modules["TS.tspico_io"] = tio
    sdc = types.ModuleType("TS.sdcard")
    sdc.SDCard = lambda *a, **k: None
    sys.modules["TS.sdcard"] = sdc


def fake_time():
    import time as _rt
    m = types.ModuleType("time")
    m.ticks_ms = lambda: int(_rt.monotonic() * 1000)
    m.ticks_us = lambda: int(_rt.monotonic() * 1_000_000)
    m.ticks_diff = lambda a, b: a - b
    return m


class FakeMQ:
    """Just enough of rp2.StateMachine for drain_phase / handle_save."""
    def __init__(self, rx_bytes=b""):
        self.rx = list(rx_bytes)
        self.tx = []
    def rx_fifo(self):
        return len(self.rx)
    def tx_fifo(self):
        return 0                      # pretend the Z80 reads instantly
    def get(self):
        return self.rx.pop(0)
    def put(self, b):
        self.tx.append(b)
    def exec(self, _s):
        pass
    def active(self, *_a):
        pass
    def feed(self, data):
        self.rx.extend(data)


# ---------------------------------------------------------------------------
# Known-good reference (make_test_tap.py's program + TAP) and the wire
# simulation (what l1879h emits). Kept self-contained so this file also serves
# as executable documentation of the protocol.
# ---------------------------------------------------------------------------

def build_reference():
    prog = bytearray()
    line_10 = bytes([0xF5, 0x22, 0x74, 0x65, 0x73, 0x74, 0x22, 0x0D])
    prog += bytes([0x00, 0x0A]) + struct.pack("<H", len(line_10)) + line_10
    line_20 = bytes([0xEC, 0x31, 0x30, 0x0E, 0x00, 0x00, 0x0A, 0x00, 0x00, 0x0D])
    prog += bytes([0x00, 0x14]) + struct.pack("<H", len(line_20)) + line_20
    BLEN = len(prog)

    # header block = [flag 0x00][HDTYPE 0x00][name×10][BLEN][autorun][vars][crc]
    hdr_block = bytearray([0x00, 0x00]) + b"test      "
    hdr_block += struct.pack("<H", BLEN) + struct.pack("<H", 0x8000) + struct.pack("<H", BLEN)
    crc = 0
    for b in hdr_block:
        crc ^= b
    hdr_block.append(crc)

    data_block = bytearray([0xFF]) + prog
    crc = 0
    for b in data_block:
        crc ^= b
    data_block.append(crc)

    tap = struct.pack("<H", len(hdr_block)) + bytes(hdr_block)
    tap += struct.pack("<H", len(data_block)) + bytes(data_block)
    return prog, bytes(tap)


def simulate_wire(prog, name=b"test      ", session=0x1234, bank=0xFF):
    sLo, sHi = session & 0xFF, (session >> 8) & 0xFF
    BLEN = len(prog)

    pre = bytearray([0x00, 0x00, bank, sLo, sHi])
    pre += struct.pack("<H", 0x5CCB)          # header RAM addr (don't-care)
    pre += struct.pack("<H", 17)              # header content length
    c = 0
    for b in pre:
        c ^= b
    pre.append(c)

    hc = bytearray([0x00]) + name + struct.pack("<H", BLEN)
    hc += struct.pack("<H", 0x8000) + struct.pack("<H", BLEN)   # 17 content bytes
    hdr = bytearray([0x00, sLo, sHi]) + hc
    par = 0x00
    for b in hc:
        par ^= b
    hdr.append(par)

    data = bytearray([0xFF, sLo, sHi]) + prog
    par = 0xFF
    for b in prog:
        par ^= b
    data.append(par)
    return bytes(pre), bytes(hdr), bytes(data)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def load_harness(tmpdir, write_target="flash", mounted=None, append=False):
    install_fakes()
    if "save_harness" in sys.modules:
        del sys.modules["save_harness"]
    sys.path.insert(0, HERE)
    import save_harness as sh
    sh.time = fake_time()
    sh.WRITE_TARGET = write_target
    sh.FLASH_DIR = tmpdir
    sh.SD_DIR = tmpdir
    sh.MOUNTED_TAP = mounted
    sh._current_tap = mounted
    sh.APPEND = append
    sh.STALL_MS = 200                 # fail fast if a phase is under-fed
    sh.VERBOSE = False
    return sh


def walk_tap(tap):
    i, blocks = 0, []
    while i < len(tap):
        ln = tap[i] | (tap[i + 1] << 8)
        blocks.append(tap[i + 2:i + 2 + ln])
        i += 2 + ln
    return blocks


PASS = 0
FAIL = 0

def check(cond, msg):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  [PASS] " + msg)
    else:
        FAIL += 1
        print("  [FAIL] " + msg)


def test_create_new():
    print("test_create_new: SAVE with nothing mounted -> creates <name>.tap")
    prog, ref_tap = build_reference()
    pre, hdr, data = simulate_wire(prog)

    with tempfile.TemporaryDirectory() as tmp:
        sh = load_harness(tmp, "flash", mounted=None, append=False)
        sh.MQ = FakeMQ(hdr + data)                 # header then data on the wire
        ev = sh.handle_save(bytearray(pre), 0)

        check(ev.get("ok"), "handle_save reported ok")
        check(ev.get("hdr_crc_ok") is True, "header CRC verified ok")
        check(ev.get("data_crc_ok") is True, "data CRC verified ok")
        check(ev.get("name") == "test", "save name decoded = 'test'")
        check(ev.get("blen") == len(prog), "BLEN decoded = %d" % len(prog))
        # status bytes: header-status(1) + final(1) + next-preload(1)
        check(sh.MQ.tx == [0x01, 0x01, 0x01],
              "staged status bytes = [01,01,01], got %s" % sh.MQ.tx)

        path = ev["path"]
        check(path == os.path.join(tmp, "test.tap"),
              "created path = %s" % path)
        with open(path, "rb") as f:
            written = f.read()
        check(written == ref_tap,
              "written .tap is BYTE-IDENTICAL to reference (%d bytes)"
              % len(written))
        if written != ref_tap:
            for i, (a, b) in enumerate(zip(ref_tap, written)):
                if a != b:
                    print("      first diff @%d ref=%02X got=%02X" % (i, a, b))
                    break


def test_append():
    print("test_append: mounted tap + APPEND -> appends both blocks at EOF")
    prog, ref_tap = build_reference()
    pre, hdr, data = simulate_wire(prog)

    with tempfile.TemporaryDirectory() as tmp:
        mounted = os.path.join(tmp, "mytape.tap")
        with open(mounted, "wb") as f:      # pre-existing one-program tap
            f.write(ref_tap)

        sh = load_harness(tmp, "flash", mounted=mounted, append=True)
        sh.MQ = FakeMQ(hdr + data)
        ev = sh.handle_save(bytearray(pre), 0)

        check(ev.get("ok"), "handle_save reported ok")
        check(ev.get("path") == mounted, "appended to mounted path")
        check(ev.get("mode") == "ab", "opened in append mode 'ab'")
        with open(mounted, "rb") as f:
            written = f.read()
        blocks = walk_tap(written)
        check(len(blocks) == 4,
              "tap now has 4 blocks (hdr,data,hdr,data), got %d" % len(blocks))
        check(written == ref_tap + ref_tap,
              "appended content = two identical programs back-to-back")


def test_stall_evidence():
    print("test_stall_evidence: only 9 of 21 header bytes -> reported, no hang")
    prog, _ = build_reference()
    pre, hdr, data = simulate_wire(prog)

    with tempfile.TemporaryDirectory() as tmp:
        sh = load_harness(tmp, "flash", mounted=None, append=False)
        sh.MQ = FakeMQ(hdr[:9])                    # the classic 9/21 stall
        ev = sh.handle_save(bytearray(pre), 0)

        check(not ev.get("ok"), "handle_save did NOT report ok")
        check("stall" in ev and "9/21" in ev["stall"],
              "stall reported with count: %r" % ev.get("stall"))
        check(ev.get("hdr_got") == 9, "hdr_got == 9 (evidence captured)")


def test_create_then_append_session():
    print("test_create_then_append_session: None+APPEND -> create then append")
    prog, ref_tap = build_reference()
    pre, hdr, data = simulate_wire(prog)

    with tempfile.TemporaryDirectory() as tmp:
        sh = load_harness(tmp, "flash", mounted=None, append=True)
        # First SAVE: nothing mounted -> create + mount.
        sh.MQ = FakeMQ(hdr + data)
        ev1 = sh.handle_save(bytearray(pre), 0)
        check(ev1.get("ok") and ev1.get("mode") == "wb",
              "1st SAVE created a new file (mode wb)")
        first_path = ev1["path"]
        # Second SAVE: now mounted + APPEND -> append to same file.
        sh.MQ = FakeMQ(hdr + data)
        ev2 = sh.handle_save(bytearray(pre), 0)
        check(ev2.get("ok") and ev2.get("mode") == "ab",
              "2nd SAVE appended (mode ab)")
        check(ev2.get("path") == first_path, "2nd SAVE targeted the same file")
        with open(first_path, "rb") as f:
            written = f.read()
        check(written == ref_tap + ref_tap, "file holds two programs")


def test_prod_drain_modes():
    print("test_prod_drain_modes: prod / prod_nomask still reconstruct correctly")
    # The A/B drain modes change *timing* on hardware, not the output when all
    # bytes are present. Here we confirm the code paths are correct and produce
    # the same byte-identical .tap when fully fed.
    prog, ref_tap = build_reference()
    pre, hdr, data = simulate_wire(prog)
    for mode in ("prod", "prod_nomask"):
        with tempfile.TemporaryDirectory() as tmp:
            sh = load_harness(tmp, "flash", mounted=None, append=False)
            sh.DRAIN_MODE = mode
            sh.MQ = FakeMQ(hdr + data)
            ev = sh.handle_save(bytearray(pre), 0)
            check(ev.get("ok"), "%s: handle_save ok" % mode)
            with open(ev["path"], "rb") as f:
                written = f.read()
            check(written == ref_tap, "%s: .tap byte-identical to reference" % mode)


def test_data_watchdog_wiring():
    print("test_data_watchdog_wiring: watchdog thread machinery keeps output correct")
    # The GIL-contention effect only appears on the RP2040 with real byte
    # timing; here we just confirm spawning/joining the thread around the data
    # drain doesn't break handle_save or the reconstructed .tap.
    prog, ref_tap = build_reference()
    pre, hdr, data = simulate_wire(prog)
    with tempfile.TemporaryDirectory() as tmp:
        sh = load_harness(tmp, "flash", mounted=None, append=False)
        sh.DATA_WATCHDOG = "sleep"        # gentle: yields, exits quickly
        sh.MQ = FakeMQ(hdr + data)
        ev = sh.handle_save(bytearray(pre), 0)
        check(ev.get("ok"), "sleep-watchdog: handle_save ok")
        check(ev.get("data_watchdog") == "sleep", "watchdog mode recorded in event")
        with open(ev["path"], "rb") as f:
            written = f.read()
        check(written == ref_tap, "sleep-watchdog: .tap byte-identical")


def main():
    print("=" * 64)
    print("save_harness host test")
    print("=" * 64)
    test_create_new()
    test_append()
    test_create_then_append_session()
    test_stall_evidence()
    test_prod_drain_modes()
    test_data_watchdog_wiring()
    print("=" * 64)
    print("RESULT: %d passed, %d failed" % (PASS, FAIL))
    print("=" * 64)
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
