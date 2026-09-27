"""Host-side test for UPDATE mode (ZX_BOOTSTRAP) -- CPython, no Pico.

Runs the PRODUCTION TS.tspico.ZX_BOOTSTRAP and tspico_io's TAPE_STREAM /
ZX_ARM / ZX_STREAM against a Z80 that follows the ORIGINAL slot-0 Spectrum
ROM (crc32 A8E12A24): LD-BYTES sends 'L' and then just reads -- no READY, no
handshake. The PIO is load_ts_hosttest's (4-deep FIFOs, a test failure on
any put() into a full TX); its Z80 waits for a byte rather than reading 00h
from an empty TX, so "TX was staged before the read" is checked explicitly.

What it pins:
  * the tape is served as one stream: every block arrives whole, in order,
    and each block's flag is already in TX when its 'L' comes;
  * once the whole tape is read it rewinds: LOAD "" again works;
  * a LOAD stopped part-way rewinds after UPDATE_REWIND_MS;
  * an old TS-2068 ROM's command (a 10-byte pre-header) is swallowed and the
    tape rewound -- the next LOAD "" starts at the first block;
  * a SYNC (1.8b ROM) or OUT 14,14 ends UPDATE mode, clears the flag and
    leaves the bus idle (TX = [01], status FF) for the main loop;
  * a missing tape ends UPDATE mode at once;
  * TS2068_IO runs ZX_BOOTSTRAP before its main loop when UPDATE is set.

Run:  python3 src/test/zx_boot_hosttest.py
"""

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import process_cmd_hosttest as P                                # noqa: E402
import load_ts_hosttest as L                                    # noqa: E402

results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg)


def tap_block(flag, content):
    return L.tap_block(flag, content)


def header(typ, name, n):
    return bytes([typ]) + name.ljust(10).encode() + bytes([n & 0xFF, n >> 8, 0, 0x80, 0, 0x80])


class PIO(L.FakePIO):
    def __init__(self):
        L.FakePIO.__init__(self)
        self.staged_at_L = []           # TX contents the moment each 'L' went out

    def pump(self):
        op = self.pending
        if op and op[0] == "out" and op[2] == 0x4C and op[1] == 0x0E:
            self.staged_at_L.append(list(self.tx))
        L.FakePIO.pump(self)


def idle(pumps):
    """The Z80 busy elsewhere (printing, BASIC, the user typing) for a while:
    a wait on a status bit that is never set."""
    yield ("wait", 0x100, pumps)


def ld_bytes(n):
    """The original ROM's LD-BYTES: 'L', a fixed delay, flag + n + CRC. The
    ROM spends ~1 ms between blocks (printing "Bytes: ...", its own
    bookkeeping) before the 'L'."""
    yield from idle(20)
    yield L.out(0x0E, 0x4C)
    flag = yield ("in",)
    h, data = flag, bytearray()
    for _ in range(n):
        b = yield ("in",)
        h ^= b
        data.append(b)
    crc = yield ("in",)
    return flag, bytes(data), crc == h


def z80_load(blocks, stop_after=None, then=None):
    """LOAD "": read the blocks with the lengths the ROM would ask for."""
    got = []
    yield from idle(200)                    # the user types LOAD ""
    for k, n in enumerate(blocks):
        if stop_after is not None and k == stop_after:
            break
        r = yield from ld_bytes(n)
        got.append(r)
    if then is not None:
        yield from then()
    return got


def main():
    P.install_fakes()
    import TS.tspico as t
    import TS.tspico_io as tio
    t.TLM_ENABLED = False
    ft = L.FakeTime()
    t.time = ft
    tio.time = ft
    t.SAVE_LOG = lambda: None
    config = {}
    t.CONFIG_SET = lambda k, v: config.__setitem__(k, v)

    prog = bytes(range(40))
    code = bytes((i * 5 + 3) & 0xFF for i in range(1500))
    tap = (tap_block(0, header(0, "loader", len(prog))) + tap_block(0xFF, prog)
           + tap_block(0, header(3, "code", len(code))) + tap_block(0xFF, code))
    d = tempfile.mkdtemp()
    path = os.path.join(d, "update.tap")
    open(path, "wb").write(tap)
    t.UPDATE_TAPE = path
    lengths = [17, len(prog), 17, len(code)]
    want = [(0, header(0, "loader", len(prog))), (0xFF, prog),
            (0, header(3, "code", len(code))), (0xFF, code)]

    print("TAPE_STREAM")
    stream, starts = tio.TAPE_STREAM(path)
    check(starts == [0, 19, 19 + 42, 19 + 42 + 19] and len(stream) == len(tap) - 8,
          "one stream, 2-byte lengths dropped, block offsets %s" % starts)

    pio = L.FakePIO()

    def boot(script, until=None):
        """TS2068_IO's start: MQ ready with the 01h pre-load, then UPDATE mode."""
        P.fresh(t, pio)
        t.TSP.UPDATE = 1
        pio.__class__ = PIO
        pio.staged_at_L = []
        pio.tx, pio.rx, pio.y = [0x01], [], 0xFFFFFFFF
        config.clear()
        pio.run(script)
        t.ZX_BOOTSTRAP()
        pio.finish()
        return pio.result

    def sync():
        yield L.out(0x0F, 0x03)
        yield ("wait", L.READY | L.IDLE, 3000)

    def out14():
        yield L.out(0x0E, 0x0E)

    def load_twice_then_sync():
        a = yield from z80_load(lengths)
        b = yield from z80_load(lengths)
        yield from sync()
        return a, b

    def ok(got):
        return [(f, dta) for f, dta, good in got] == want and all(g for _, _, g in got)

    try:
        print("LOAD \"\" -- the tape as one stream")
        a, b = boot(load_twice_then_sync())
        check(ok(a), "all four blocks whole, in order, CRCs right")
        check(all(s and s[0] == stream[st] for s, st in zip(pio.staged_at_L[:4], starts)),
              "each block's flag was already in TX when its 'L' went out")
        check(ok(b), "the whole tape read: it rewound, and LOAD \"\" again works")
        check(config == {"UPDATE": None} and t.TSP.UPDATE == 0,
              "SYNC (the 1.8b ROM) ends UPDATE mode and clears the flag")
        check(pio.tx == [0x01] and pio.status() == 0xFF,
              "the bus is left idle for the main loop: TX = [01], status FF (%s, %02X)"
              % (pio.tx, pio.status()))

        print("a LOAD stopped part-way")

        def stopped():
            yield from z80_load(lengths, stop_after=2)      # BREAK after the program
            yield from idle(40000)                          # well over UPDATE_REWIND_MS
            got = yield from z80_load(lengths)
            yield from out14()
            return got

        # the Z80 idles between the two LOADs; FakeTime moves 1 ms per clock read
        got = boot(stopped())
        check(ok(got), "after %d ms without a read the tape rewound: the next LOAD \"\" "
              "starts at the first block" % t.UPDATE_REWIND_MS)
        check(config == {"UPDATE": None}, "OUT 14,14 ends UPDATE mode")

        print("an old TS-2068 ROM's command")

        def old_rom_then_load():
            for b in (0x42, 0x00, 0xFF, 0, 0, 0, 0, 7, 0, 0xBA):   # SAVE "tpi:dir", 1.5w
                yield L.out(0x0E, b)
            yield ("in",)                                         # reads a "status"
            yield from idle(2000)                                 # Report J; the user types again
            got = yield from z80_load(lengths)
            yield from out14()
            return got

        got = boot(old_rom_then_load())
        check(ok(got), "its pre-header swallowed, the tape rewound: LOAD \"\" gets every block")

        print("a missing tape")
        t.UPDATE_TAPE = path + ".missing"
        P.fresh(t, pio)
        t.TSP.UPDATE = 1
        config.clear()
        pio.tx, pio.rx = [0x01], []
        pio.script = None
        t.ZX_BOOTSTRAP()
        check(config == {"UPDATE": None} and pio.tx == [0x01],
              "returns at once, clears the flag, leaves the pre-load alone")
        t.UPDATE_TAPE = path

        print("  PASS  no put() into a full TX FIFO (FakePIO raises if one happens)")
    except L.PutWouldBlock as e:
        check(False, str(e))

    print("TS2068_IO runs it before the main loop")
    for name in ("TS/tspico.py", "dev_tspico.py"):
        src = open(os.path.join(SRC, name), encoding="utf-8").read().replace("\r", "")
        body = src[src.index("def TS2068_IO("):]
        i = body.index("if getattr(TSP, \"UPDATE\", 0):")
        check(body[i:i + 80].split("\n")[1].strip().startswith("ZX_BOOTSTRAP()")
              and i < body.index("while True:                                                                                    # main execution loop"),
              "%s: UPDATE set: ZX_BOOTSTRAP(), before the main loop" % name)

    ok_all = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok_all else "FAILURES", len(results)))
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
