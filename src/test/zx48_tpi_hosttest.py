"""Host-side test for LOAD "tpi:name" in ZX48 mode -- CPython, no Pico.

Runs the PRODUCTION TS.tspico.ZX_TPI (and LOAD_TPI, which it shares with
TS-2068 mode) against a Z80 that follows the ZX v3 ROM
(src/rom/patches/tspico-zx48-v3.asm; its Z80 code is checked in
rom_zx48_hosttest.py): after 'T' it waits for READY, sends op, length and
the name, waits for READY again, and reads status, length and message.
The PIO is load_ts_hosttest's (4-deep FIFOs, auto-busy, put() into a full
TX fails the test). MOUNT_FILE is stubbed; the folder listing is faked.

What it pins:
  * a name, any case, or a listing number mounts the file: status FFh
    (0 OK) and the message;
  * the reply's first bytes are in TX before READY (the ROM reads the
    instant it sees it), and the rest follows without an empty read;
  * a missing file -> F (0Eh), a .ROM -> Q (19h), SAVE "tpi:..." -> Q, a
    failed mount -> Q, each with its message;
  * a name that stops half-way: no reply, nothing mounted, no hang;
  * ZX48_IO dispatches 'T' to ZX_TPI in both copies of the firmware.

Run:  python3 src/test/zx48_tpi_hosttest.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import process_cmd_hosttest as P                                # noqa: E402
import load_ts_hosttest as L                                    # noqa: E402

READY = L.READY
results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg)


def z80_tpi(name, op=1, stop_at=None):
    """The v3 ROM after its 'T' (ZX48_IO has taken it)."""
    st = yield ("wait", READY, 20000)
    if st is None:
        return ("J", None)
    wire = [op, len(name)] + list(name.encode())
    for i, b in enumerate(wire):
        if stop_at is not None and i == stop_at:
            yield ("stop",)
        yield L.out(0x0E, b)
    st = yield ("wait", READY, 200000)
    if st is None:
        return ("J", None)
    status = yield ("in",)
    n = yield ("in",)
    msg = bytearray()
    for _ in range(n):
        msg.append((yield ("in",)))
    return (status, bytes(msg))


def main():
    P.install_fakes()
    import TS.tspico as t
    import TS.tspico_io as tio
    t.TLM_ENABLED = False
    ft = L.FakeTime()
    t.time = ft
    tio.time = ft

    pio = L.FakePIO()
    mounted = []
    ok_mount = [True]

    def mount(path, remounting=False):
        mounted.append(path)
        return ok_mount[0]
    t.MOUNT_FILE = mount

    def run(name, **kw):
        P.fresh(t, pio)
        t.files = ["Manic.tap", "Jetpac.TAP", "zx.rom"]
        t.files_upper = [f.upper() for f in t.files]
        pio.tx, pio.rx, pio.y = [], [], 0            # the 'T' dropped READY
        pio.tx_at_ready = []
        del mounted[:]
        pio.run(z80_tpi(name, **kw))
        nxt = t.ZX_TPI()
        pio.finish()
        return pio.result, nxt

    try:
        print('LOAD "tpi:MANIC.TAP"')
        r, nxt = run("MANIC.TAP")
        check(r == (0xFF, b"File mounted OK MANIC.TAP") and nxt == -1,
              "0 OK and the message (%r)" % (r,))
        check(mounted == ["/sd/TAP/Manic.tap"], "mounted the file as listed (%s)" % mounted)
        at = pio.tx_at_ready[-1] if pio.tx_at_ready else []
        check(len(at) == 4 and at[:2] == [0xFF, 25],
              "status, length and the first message bytes were in TX before READY (%s)" % at)
        check(not pio.tx and pio.dropped == 0, "TX empty afterwards, nothing dropped")

        print('LOAD "tpi:1" -- a number from the listing')
        r, _ = run("1")
        check(r[0] == 0xFF and mounted == ["/sd/TAP/Jetpac.TAP"], "mounted Jetpac.TAP (%r)" % (r,))

        print("errors")
        r, _ = run("nothere.tap")
        check(r == (0x0E, b"File does not exist: nothere.tap") and not mounted, "missing: F (%r)" % (r,))
        r, _ = run("zx.rom")
        check(r == (0x19, b"Only .tap files in ZX48 mode: zx.rom") and not mounted,
              "a .ROM: Q, not mounted (%r)" % (r,))
        r, _ = run("dir", op=0)
        check(r[0] == 0x19 and r[1].startswith(b"Only LOAD") and not mounted,
              'SAVE "tpi:dir": Q (%r)' % (r,))
        ok_mount[0] = False
        r, _ = run("manic.tap")
        ok_mount[0] = True
        check(r == (0x19, b"Error mounting file: manic.tap"), "a failed mount: Q (%r)" % (r,))

        print("the name stops half-way")
        r, nxt = run("manic.tap", stop_at=5)
        check(not mounted and nxt == -1 and not pio.tx, "no reply, nothing mounted, no hang")

        print("  PASS  no put() into a full TX FIFO (FakePIO raises if one happens)")
    except L.PutWouldBlock as e:
        check(False, str(e))

    print("ZX48_IO dispatches 'T'")
    for name in ("TS/tspico.py", "dev_tspico.py"):
        src = open(os.path.join(SRC, name), encoding="utf-8").read().replace("\r", "")
        body = src[src.index("def ZX48_IO("):]
        check("elif a == 84:" in body and "nxt = ZX_TPI()" in body, "%s: 'T' -> ZX_TPI" % name)

    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
