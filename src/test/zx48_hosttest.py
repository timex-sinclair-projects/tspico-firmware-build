"""Host-side test for the ZX48-mode handlers — runs on CPython, no Pico.

Unlike save_harness_hosttest.py (which exercises a clean-room harness),
this imports the PRODUCTION module TS/tspico_io.py with the device-only
modules faked, and drives LOAD_ZX / SAVE_ZX with the exact byte sequences
the customised ZX Spectrum ROM puts on the wire.

The wire protocol under test, from the ROM's LD-BYTES/SA-BYTES
(disassembled from flash slot 0 of Pico-v15w.rom):

    LOAD    Z80 -> 'L' (76)                  [consumed by ZX48_IO]
            Pico -> flag, content..., CRC     exactly `totbytes` bytes

    SAVE    Z80 -> 'S' (83)                  [consumed by ZX48_IO]
            Z80 -> len_lo, len_hi, flag, content..., CRC
            Z80 -> 'S' again, then the data block the same way

Regression coverage:
  * LOAD_ZX used to stream one byte too many (flag + totbytes). The
    surplus byte stayed in TX and the next 'L' read it as a flag —
    the "TX FIFO not empty after ZX mode" cleanup in ZX48_IO existed
    to mop that up.
  * SAVE_ZX used to end with ENA_MQ(), rebuilding the single-port
    TS_IO state machine at 15 MHz mid-session.
  * SAVE_ZX read RX unmasked; a 9-bit word (bit 8 = A0) assigned into
    a bytearray raises and drops the Pico to the REPL.

Run:  python3 src/test/zx48_hosttest.py
"""

import builtins
import os
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)


# ---------------------------------------------------------------------------
# Fakes for the device-only modules, so `import TS.tspico_io` works here.
# ---------------------------------------------------------------------------

SM_CALLS = []          # every StateMachine(...) construction, in order


def install_fakes():
    builtins.const = lambda x: x                      # MicroPython builtin

    machine = types.ModuleType("machine")

    class _Pin:
        OUT = 0
        IN = 1
        PULL_UP = 2

        def __init__(self, *a, **k):
            pass

        def value(self, *a):
            return 0

        def toggle(self):
            pass

    machine.Pin = _Pin
    machine.SPI = lambda *a, **k: None
    machine.freq = lambda *a, **k: None
    sys.modules["machine"] = machine

    rp2 = types.ModuleType("rp2")

    def _sm(*a, **k):
        # StateMachine(id, prog, freq=..., ...) — prog is the 2nd positional.
        SM_CALLS.append({"args": a, "freq": k.get("freq")})
        return FakeMQ()

    rp2.StateMachine = _sm
    rp2.asm_pio = lambda *a, **k: (lambda f: f)       # body never executes
    rp2.PIO = types.SimpleNamespace(
        OUT_HIGH=0, OUT_LOW=1, SHIFT_RIGHT=2, SHIFT_LEFT=3, IN_HIGH=4)
    sys.modules["rp2"] = rp2

    utime = types.ModuleType("utime")
    utime.sleep = lambda *a: None
    utime.sleep_ms = lambda *a: None
    sys.modules["utime"] = utime

    thread = types.ModuleType("_thread")
    thread.start_new_thread = lambda fn, args: None   # no watchdog on host
    sys.modules["_thread"] = thread

    ts = types.ModuleType("TS")
    ts.__path__ = [os.path.join(SRC, "TS")]
    sys.modules["TS"] = ts
    sdc = types.ModuleType("TS.sdcard")
    sdc.SDCard = lambda *a, **k: None
    sys.modules["TS.sdcard"] = sdc


class FakeMQ:
    """Stand-in for the TS_IO_DUAL StateMachine.

    put()  -> appends to .tx (what the Z80 would read from $0E)
    get()  -> pops .rx    (what the Z80 wrote to $0E)
    exec() -> recorded in .execs, so Y=READY can be asserted
    """

    def __init__(self):
        self.tx = []
        self.rx = []
        self.execs = []
        self.log = []             # ordered ("put"/"get"/"exec", value)
        self.pending = 0          # what tx_fifo() reports

    def put(self, v):
        v = v if isinstance(v, int) else v[0]
        self.tx.append(v)
        self.log.append(("put", v))

    def get(self):
        if not self.rx:
            raise AssertionError("Z80 stalled: handler read past the wire data")
        v = self.rx.pop(0)
        self.log.append(("get", v))
        return v

    def exec(self, s):
        self.execs.append(s)
        self.log.append(("exec", "READY" if "invert(null)" in s else s))

    def tx_fifo(self):
        return self.pending

    def rx_fifo(self):
        return len(self.rx)

    def active(self, *a):
        pass

    def ready(self):
        return any("invert(null)" in e for e in self.execs)

    def ready_positions(self):
        """Indices in .log where READY was raised."""
        return [i for i, (kind, v) in enumerate(self.log)
                if kind == "exec" and v == "READY"]


class FakeTSP:
    def __init__(self, tmpdir, tapfile=None, totlen=0):
        self.f_name = tapfile
        self.totlen = totlen
        self.offset = 0
        self.tap_idx = 0
        self.LOG_LEVEL = 3
        self.cur_path = tmpdir
        self.zx48 = True
        self.ZX_TAPE_COMPAT = False


# ---------------------------------------------------------------------------
# TAP helpers — standard [len_lo][len_hi][flag][content][xor CRC] blocks.
# ---------------------------------------------------------------------------

def tap_block(flag, content):
    body = bytes([flag]) + bytes(content)
    crc = 0
    for b in body:
        crc ^= b
    body += bytes([crc])
    return bytes([len(body) & 0xFF, len(body) >> 8]) + body


def make_tap(name=b"test      ", data=b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a"):
    header = bytes([0]) + name + bytes([
        len(data) & 0xFF, len(data) >> 8,     # data length
        0x0A, 0x00,                           # param 1 (autostart line)
        0x00, 0x80,                           # param 2
    ])
    return tap_block(0x00, header) + tap_block(0xFF, data), header, data


def check(cond, msg):
    print(("  PASS  " if cond else "  FAIL  ") + msg)
    return bool(cond)


# ---------------------------------------------------------------------------
# LOAD_ZX
# ---------------------------------------------------------------------------

def test_load_zx_streams_exactly_one_block(tio, tmpdir):
    print("LOAD_ZX streams exactly one block, no orphan byte")
    tap, header, data = make_tap()
    path = os.path.join(tmpdir, "temp.tap")
    os.makedirs(os.path.join(tmpdir, "TMP"), exist_ok=True)
    with open(os.path.join(tmpdir, "TMP", "temp.tap"), "wb") as f:
        f.write(tap)

    MQ = FakeMQ()
    TSP = FakeTSP(tmpdir, tapfile="x.tap", totlen=len(tap))
    tio.LOAD_ZX(MQ, TSP)

    hdr_len = tap[0] + 256 * tap[1]                    # 19
    expected = list(tap[2:2 + hdr_len])                # flag + content + CRC
    ok = check(MQ.tx == expected,
               "header block: %d bytes streamed, expected %d" % (len(MQ.tx), hdr_len))
    # What the ROM actually reads: flag + DE (from the header) + CRC.
    rom_reads = 1 + 17 + 1
    ok &= check(len(MQ.tx) == rom_reads,
                "matches the ROM's read count (%d)" % rom_reads)
    ok &= check(TSP.offset == hdr_len + 2,
                "offset advanced past the block (%d)" % TSP.offset)
    ok &= check(MQ.ready(), "left Y = READY")
    # The patched ROM polls $0F after its 'L' and reads $0E the instant the
    # poll succeeds, so the flag byte must be staged BEFORE Y goes high.
    rdy = MQ.ready_positions()
    ok &= check(bool(rdy) and MQ.log[0][0] == "put",
                "staged the flag byte before raising READY")
    return ok


def test_load_zx_second_block_is_clean(tio, tmpdir):
    print("LOAD_ZX second call starts at the data block's own flag")
    tap, header, data = make_tap()
    with open(os.path.join(tmpdir, "TMP", "temp.tap"), "wb") as f:
        f.write(tap)

    TSP = FakeTSP(tmpdir, tapfile="x.tap", totlen=len(tap))
    MQ1 = FakeMQ()
    tio.LOAD_ZX(MQ1, TSP)
    MQ2 = FakeMQ()
    tio.LOAD_ZX(MQ2, TSP)

    data_off = (tap[0] + 256 * tap[1]) + 2
    data_len = tap[data_off] + 256 * tap[data_off + 1]
    expected = list(tap[data_off + 2:data_off + 2 + data_len])

    ok = check(MQ2.tx[:1] == [0xFF], "first byte is the data flag 0xFF")
    ok &= check(MQ2.tx == expected,
                "data block: %d bytes streamed, expected %d" % (len(MQ2.tx), data_len))
    ok &= check(MQ1.tx[-1] == tap[2 + (tap[0] + 256 * tap[1]) - 1],
                "first block ended on its CRC byte, not the next length byte")
    return ok


# ---------------------------------------------------------------------------
# SAVE_ZX
# ---------------------------------------------------------------------------

def sa_bytes_wire(flag, content):
    """What the Spectrum ROM's SA-BYTES puts on $0E for one block.

    'S' is not included — ZX48_IO consumes the header block's 'S' when it
    dispatches, and SAVE_ZX itself consumes the data block's.
    """
    crc = flag
    for b in content:
        crc ^= b
    return [len(content) & 0xFF, len(content) >> 8, flag] + list(content) + [crc]


def test_save_zx_roundtrip(tio, tmpdir):
    print("SAVE_ZX reconstructs a byte-exact TAP and restores the dual-port SM")
    tap, header, data = make_tap()

    MQ = FakeMQ()
    MQ.rx = (sa_bytes_wire(0x00, header)            # header block
             + [83]                                  # the data block's 'S'
             + sa_bytes_wire(0xFF, data))            # data block
    TSP = FakeTSP(tmpdir)

    before = len(SM_CALLS)
    tio.SAVE_ZX(MQ, TSP)

    out = os.path.join(tmpdir, "test.tap")
    ok = check(os.path.exists(out), "wrote %s" % os.path.basename(out))
    if ok:
        with open(out, "rb") as f:
            got = f.read()
        ok &= check(got == tap,
                    "TAP is byte-identical to the reference (%d bytes)" % len(got))
    ok &= check(not MQ.rx, "consumed the whole wire sequence")
    # A ROM patched to poll $0F after 'S' needs READY raised on entry (the
    # 'S' dropped it via PIO auto-busy) and again after the data block's 'S'.
    rdy = MQ.ready_positions()
    gets = [i for i, (kind, _) in enumerate(MQ.log) if kind == "get"]
    ok &= check(bool(rdy) and rdy[0] < gets[0],
                "raised READY on entry, before reading the header block")
    ok &= check(len(rdy) >= 2 and gets[20] < rdy[1] < gets[22],
                "raised READY again between the data block's 'S' and its bytes")
    new_sms = SM_CALLS[before:]
    ok &= check(len(new_sms) == 1, "rebuilt the bus SM once")
    if new_sms:
        ok &= check(tio.TS_IO_DUAL in new_sms[0]["args"],
                    "rebuilt it with TS_IO_DUAL (not the single-port TS_IO)")
        ok &= check(tio.TS_IO not in new_sms[0]["args"],
                    "did not fall back to the single-port TS_IO program")
        ok &= check(new_sms[0]["freq"] == 30_000_000,
                    "at 30 MHz (not the single-port 15 MHz)")
    return ok


def test_save_zx_masks_9bit_rx(tio, tmpdir):
    print("SAVE_ZX masks the 9-bit RX word instead of raising")
    tap, header, data = make_tap(name=b"masked    ")

    MQ = FakeMQ()
    wire = (sa_bytes_wire(0x00, header) + [83] + sa_bytes_wire(0xFF, data))
    wire[5] |= 0x100                                  # bit 8 = A0 ($0F write)
    MQ.rx = wire
    TSP = FakeTSP(tmpdir)

    try:
        tio.SAVE_ZX(MQ, TSP)
        ok = check(True, "no exception on a 9-bit RX word")
    except Exception as e:                            # noqa: BLE001 - that's the point
        return check(False, "raised %s: %s" % (type(e).__name__, e))

    with open(os.path.join(tmpdir, "masked.tap"), "rb") as f:
        got = f.read()
    ok &= check(got == tap, "byte 5 landed masked to 8 bits")
    return ok


# ---------------------------------------------------------------------------

def main():
    install_fakes()
    sys.path.insert(0, SRC)
    import TS.tspico_io as tio

    tio.ENA_SD = lambda: None                         # no SD hardware here
    os.umount = lambda p: None                        # ditto

    tmp = tempfile.mkdtemp(prefix="zx48-")
    os.makedirs(os.path.join(tmp, "TMP"), exist_ok=True)

    # The handlers open the Pico's absolute flash paths ("/TMP/temp.tap",
    # "/assets/nofile.tap"). Rewrite just those into the sandbox; the SD
    # path SAVE_ZX builds from TSP.cur_path is already under tmp and must
    # pass through untouched.
    _real_open = builtins.open

    def _open(path, *a, **k):
        if isinstance(path, str) and (path.startswith("/TMP/")
                                      or path.startswith("/assets/")):
            path = os.path.join(tmp, path.lstrip("/"))
        return _real_open(path, *a, **k)

    tio.open = _open

    ok = True
    ok &= test_load_zx_streams_exactly_one_block(tio, tmp)
    ok &= test_load_zx_second_block_is_clean(tio, tmp)
    ok &= test_save_zx_roundtrip(tio, tmp)
    ok &= test_save_zx_masks_9bit_rx(tio, tmp)

    print("\n%s" % ("ALL PASS" if ok else "FAILURES"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
