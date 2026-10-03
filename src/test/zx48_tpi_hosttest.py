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
import types

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
    """The v3 ROM after its 'T' (ZX48_IO has taken it). op with bit 7 set
    is the v4 ROM, which reads the reply in pieces (length, bytes ... 0)."""
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
    while True:
        for _ in range(n):
            msg.append((yield ("in",)))
        if not op & 0x80 or not n:
            break
        n = yield ("in",)                   # v4: the next piece's length, 0 = the end
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

    def run(name, stale=False, **kw):
        P.fresh(t, pio)
        t.files = ["Manic.tap", "Jetpac.TAP", "zx.rom"]
        t.files_upper = [f.upper() for f in t.files]
        t.TSP.listing_stale = stale
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

        print("the reply loop calls ZX_ROOM only when TX is full")
        # On MicroPython v1.29 a ZX_ROOM call for every byte cost ~49 us, more
        # than the ROM's ~45 us a byte, and the message came out garbled.
        # (The fake Z80 reads a byte on every FIFO query, so asking the FIFO
        # again from in here would change what we measure: count calls.)
        calls = []
        real_room = t.ZX_ROOM

        def counting_room(mq, ms):
            calls.append(1)
            return real_room(mq, ms)
        t.ZX_ROOM = counting_room
        try:
            r, nxt = run("MANIC.TAP")
        finally:
            t.ZX_ROOM = real_room
        n = 2 + len(r[1])
        check(r[0] == 0xFF and len(calls) * 4 < n,
              "ZX_ROOM only when TX is full, not per byte (%d calls for a %d-byte reply)" % (len(calls), n))

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
        check(r[0] == 0x19 and r[1] == b'SAVE "tpi:dir" needs ZX ROM v4' and not mounted,
              'SAVE "tpi:dir" from a v3 ROM: Q, and why (%r)' % (r,))
        r, _ = run("x", op=2)
        check(r[0] == 0x19 and r[1].startswith(b"Only LOAD"), "VERIFY: Q (%r)" % (r,))
        r, _ = run("MANIC.TAP", op=0x81)
        check(r == (0xFF, b"File mounted OK MANIC.TAP") and mounted == ["/sd/TAP/Manic.tap"],
              "a v4 LOAD (op 81h): the same mount, its message as one piece (%r)" % (r,))

        print('SAVE "tpi:dir" from the v4 ROM: the listing in pieces')
        real = {n: getattr(t, n) for n in ("ACTIVATE_SD", "DEACTIVATE_SD", "ACTIVATE_MQ", "CATALOG_TEXT")}
        steps = []
        big = t.DIR_HEADER("40 files, 0 dirs", "/TAP") + "".join(
            "%03d %-18s%10s" % (i, "GAME%02d.TAP" % i, "47 kB") for i in range(40))
        t.ACTIVATE_SD = lambda *a: steps.append("ACTIVATE_SD")
        t.DEACTIVATE_SD = lambda: steps.append("DEACTIVATE_SD")
        t.ACTIVATE_MQ = lambda *a: (steps.append("ACTIVATE_MQ"), setattr(t, "MQ", pio))
        t.CATALOG_TEXT = lambda arg: (steps.append("CATALOG %r" % arg), (big, t._1_OK))[1]
        try:
            r, nxt = run("dir", op=0x80)
            want = t.CAT_COLOUR(big).encode()
            check(r[0] == 0xFF and r[1] == want and len(want) > 1300 and nxt == -1,
                  "0 OK and all %d bytes of CAT's coloured listing, over the 255 one piece holds" % len(want))
            check(steps == ["ACTIVATE_SD", "CATALOG ''", "DEACTIVATE_SD", "ACTIVATE_MQ"],
                  "the card is read and the bus handed back (%s)" % steps)
            check(not pio.tx and pio.dropped == 0, "TX empty afterwards, nothing dropped")
            del steps[:]
            run("DIR games", op=0x80)
            check(steps[1] == "CATALOG 'games'", "SAVE \"tpi:dir games\": the argument goes to CATALOG (%s)" % steps)
            t.CATALOG_TEXT = lambda arg: ("Not found: x", t._3_F_Invalid_file)
            r, _ = run("dir x", op=0x80)
            check(r == (0x0E, b"Not found: x"), "a CATALOG error: its report and message (%r)" % (r,))
        finally:
            for n, v in real.items():
                setattr(t, n, v)
        ok_mount[0] = False
        r, _ = run("manic.tap")
        ok_mount[0] = True
        check(r == (0x19, b"Error mounting file: manic.tap"), "a failed mount: Q (%r)" % (r,))

        print("a file a ZX SAVE has just written (the listing is stale)")
        # SAVE_ZX sets TSP.listing_stale instead of re-reading the folder
        # while the Spectrum may already be sending; ZX_TPI re-reads it
        # before matching the name. Found on hardware 2026-10-02.
        real = {n: getattr(t, n) for n in ("ACTIVATE_SD", "DEACTIVATE_SD", "ACTIVATE_MQ", "DIR_FILES", "os")}
        steps = []

        def dir_files():
            steps.append("DIR_FILES")
            t.files = ["Manic.tap", "Jetpac.TAP", "zx.rom", "q.tap"]
            t.files_upper = [f.upper() for f in t.files]
            return True
        t.ACTIVATE_SD = lambda *a: steps.append("ACTIVATE_SD")
        t.DEACTIVATE_SD = lambda: steps.append("DEACTIVATE_SD")
        t.ACTIVATE_MQ = lambda *a: (steps.append("ACTIVATE_MQ"), setattr(t, "MQ", pio))
        t.DIR_FILES = dir_files
        t.os = types.SimpleNamespace(chdir=lambda p: steps.append("chdir " + p))
        try:
            r, nxt = run("q.tap", stale=True)
            check(r[0] == 0xFF and mounted == ["/sd/TAP/q.tap"],
                  "the just-saved file is found and mounted (%r, %s)" % (r, mounted))
            check(steps == ["ACTIVATE_SD", "chdir /sd/TAP", "DIR_FILES", "DEACTIVATE_SD", "ACTIVATE_MQ"]
                  and not t.TSP.listing_stale,
                  "re-read once, bus handed back, flag cleared (%s)" % steps)
            del steps[:]
            r, nxt = run("q.tap")
            check(not steps and r[0] == 0x0E, "not stale: no re-read (and q.tap isn't listed) (%r)" % (r,))

            def no_card(*a):
                raise OSError(19, "no SD card")
            t.ACTIVATE_SD = no_card
            del steps[:]
            r, nxt = run("manic.tap", stale=True)
            check(r[0] == 0xFF and steps == ["DEACTIVATE_SD", "ACTIVATE_MQ"],
                  "no card for the re-read: carries on with the old listing, bus handed back (%s)" % steps)
        finally:
            for n, v in real.items():
                setattr(t, n, v)

        print("the next 2068 command re-reads a stale listing first")
        seen = []
        real = {n: getattr(t, n) for n in ("REFRESH_LISTING",)}
        t.REFRESH_LISTING = lambda: (seen.append("refresh"), setattr(t.TSP, "listing_stale", False))
        try:
            for stale in (True, False):
                del seen[:]
                text = b"tpi:dir"
                mq = P.FakeMQ(P.make_body(text))
                P.fresh(t, mq)
                t.TSP.listing_stale = stale
                t.PROCESS_CMD(P.make_pre(text), {"TPI:DIR": lambda pre, cmd: seen.append("DIR")}, {})
                want = ["refresh", "DIR"] if stale else ["DIR"]
                check(seen == want, "stale=%s: %s (%s)" % (stale, " then ".join(want), seen))
        finally:
            for n, v in real.items():
                setattr(t, n, v)

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
