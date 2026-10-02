"""Host-side test for ZX48 mode without the core1 watchdog (issue #51) --
CPython, no Pico.

Runs the PRODUCTION TS/tspico_io.LOAD_ZX / LOAD_ZX_C / SAVE_ZX against a Z80
that follows the ZX v2 Spectrum ROM (ROMs/TSPICO-ZX48-V2.BIN): LD-BYTES and
SA-BYTES send 'L' / 'S' on $0E, poll $0F for READY (~3.8 s, then Report R),
then move the block with no handshake. LD-BYTES reads flag + the length IT
expects + CRC, whatever the block's own length -- which is how LOAD "name"
skips the blocks before its file. The PIO is load_ts_hosttest's: 4-deep
FIFOs, auto-busy, and a test FAILURE on any put() into a full TX FIFO
(which blocks forever on a Pico). The test's dispatcher does what ZX48_IO
does, including dispatching a command byte a handler took mid-block.

What it pins:
  * LOAD "" still loads header + data, the tape position moves on;
  * LOAD "name" skips a program in front of it: each skipped block ends
    as soon as the Z80 sends its next 'L' (no 3 s wait), the tape moves on
    (it used to send the same block again), and the unread tail is
    flushed so the next flag is clean;
  * a Z80 that stops reading mid-block (BREAK between blocks, a reset):
    the LOAD gives up after ZX_STALL_MS, TX is flushed, the next LOAD works;
  * compatible mode (LOAD_ZX_C): READY for every 'L', a bounded tail;
  * SAVE writes the right .tap; a SAVE that stops, fails its parity or has
    an unusable name writes nothing, and a refused header's data block
    never gets READY (the ROM gives Report R);
  * no put() into a full TX FIFO anywhere, no watchdog.

Run:  python3 src/test/zx48_io_hosttest.py
"""

import os
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from sync_io_hosttest import install_fakes, FakeTime          # noqa: E402
import load_ts_hosttest as L                                    # noqa: E402

READY = L.READY
out = L.out
results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg)


def tap_block(flag, content):
    return L.tap_block(flag, content)


def header(name, n, typ=3):
    return bytes([typ]) + name.ljust(10).encode() + bytes([n & 0xFF, n >> 8, 0, 0x80, 0, 0])


# ---- the Z80: the ZX v2 ROM ------------------------------------------------

def ld_bytes(n):
    """LD-BYTES: 'L', READY, then flag + n + CRC. None = it failed: no READY
    in ~3.8 s, or a parity miss (the ROM then falls into the old tape-edge
    code, which finds no tape and returns carry clear too)."""
    yield out(0x0E, 76)
    st = yield ("wait", READY, 20000)
    if st is None:
        return None
    flag = yield ("in",)
    h, data = flag, bytearray()
    for _ in range(n):
        b = yield ("in",)
        h ^= b
        data.append(b)
    crc = yield ("in",)
    return (flag, bytes(data)) if crc == h else None


def z80_load(name=None, stop_after_blocks=None):
    """LOAD "name" (None = LOAD ""): LD-LOOK-H ($0767), then LD-BLOCK.
    LD-LOOK-H tries again after ANY failed LD-BYTES (JR NC at $0773) -- a
    parity miss, a READY timeout, a block that isn't a header -- until
    BREAK. Only the data block's LD-BYTES failing gives Report R."""
    blocks = 0
    while True:
        if stop_after_blocks is not None and blocks == stop_after_blocks:
            yield ("stop",)                 # BREAK between blocks: the Z80 is gone
        if blocks > 12:
            return ("looping", None)        # a real ROM would go on until BREAK
        r = yield from ld_bytes(17)
        blocks += 1
        if r is None:
            continue
        flag, hd = r
        if flag != 0 or hd[0] != 3:
            continue                        # not a CODE header: look again
        if name is not None and hd[1:11].decode().rstrip() != name:
            continue                        # "Bytes: other" -- look again
        r = yield from ld_bytes(hd[11] | (hd[12] << 8))
        return ("R", None) if r is None else ("ok", r[1])


def sa_bytes(flag, content, corrupt=None, stop_at=None):
    """SA-BYTES: 'S', READY, then len_lo, len_hi, flag, content, CRC."""
    yield out(0x0E, 83)
    st = yield ("wait", READY, 20000)
    if st is None:
        return "R"
    h = flag
    for b in content:
        h ^= b
    wire = [len(content) & 0xFF, len(content) >> 8, flag] + list(content) + [h]
    for i, b in enumerate(wire):
        if stop_at is not None and i == stop_at:
            yield ("stop",)
        if corrupt is not None and i == corrupt:
            b ^= 0x55
        yield out(0x0E, b)
    return "ok"


def z80_save(name, data, **kw):
    hdr_kw = {k[4:]: v for k, v in kw.items() if k.startswith("hdr_")}
    dat_kw = {k[4:]: v for k, v in kw.items() if k.startswith("dat_")}
    r = yield from sa_bytes(0x00, header(name, len(data)), **hdr_kw)
    if r != "ok":
        return r
    return (yield from sa_bytes(0xFF, data, **dat_kw))


# ---- the test ---------------------------------------------------------------

def main():
    install_fakes()
    sys.path.insert(0, SRC)
    import TS.tspico_io as io
    io.time = FakeTime()
    io.ENA_SD = lambda *a: None
    io.ENA_MQ_DUAL = lambda MQ: MQ          # the SM survives the SD write here

    d = tempfile.mkdtemp()
    tap_path = os.path.join(d, "temp.tap")
    real_open = open
    io.open = lambda path, mode="r": real_open(tap_path if path == "/TMP/temp.tap" else path, mode)

    data_a = bytes((i * 5 + 1) & 0xFF for i in range(300))
    data_b = bytes((i * 11 + 7) & 0xFF for i in range(2000))
    tap = (tap_block(0x00, header("alpha", len(data_a))) + tap_block(0xFF, data_a)
           + tap_block(0x00, header("beta", len(data_b))) + tap_block(0xFF, data_b))
    with real_open(tap_path, "wb") as f:
        f.write(tap)
    tsp = types.SimpleNamespace(f_name="t.tap", totlen=len(tap), offset=0, tap_idx=0,
                                LOG_LEVEL=0, cur_path=d)
    pio = L.FakePIO()
    calls = []

    def session(script, compat=False):
        """ZX48_IO: take a command byte (or the one a handler handed back)
        and dispatch it, until the Z80 is done."""
        pio.tx, pio.rx, pio.y = [], [], 0xFFFFFFFF
        pio.run(script)
        logs, nxt = "", -1
        while True:
            if nxt < 0:
                if not pio.rx:
                    if pio.script is None or pio.pending == ("stop",):
                        break
                    pio.pump()
                    continue
                a = pio.get()
            else:
                a, nxt = nxt, -1
            calls.append(a)
            if a == 76:
                if compat:
                    _, _, log, nxt = io.LOAD_ZX_C(pio, tsp, 52100)
                else:
                    _, _, log, nxt = io.LOAD_ZX(pio, tsp)
            elif a == 83:
                _, _, log, nxt = io.SAVE_ZX(pio, tsp)
            else:
                raise AssertionError("unexpected command byte 0x%02X" % a)
            logs += log
        pio.finish()
        return pio.result, logs

    off_b = len(tap_block(0x00, header("alpha", len(data_a))) + tap_block(0xFF, data_a))

    try:
        print('LOAD ""')
        r, log = session(z80_load())
        check(r == ("ok", data_a), "header + data loaded (%s)" % (r[0],))
        check(tsp.offset == off_b and not pio.tx and pio.dropped == 0,
              "tape moved on past both blocks, TX empty, nothing dropped (offset %d)" % tsp.offset)

        print('LOAD "beta" skips the program in front of it')
        tsp.offset = tsp.tap_idx = 0
        del calls[:]
        t0 = io.time.ms
        r, log = session(z80_load("beta"))
        check(r == ("ok", data_b), "beta loaded after alpha's two blocks (%s)" % (r[0],))
        check(calls == [76] * 4, "four LD-BYTES calls: alpha's header, alpha's data, beta's header, beta's data")
        check("read 19 of 302 bytes, then sent 0x4C" in log,
              "alpha's data block ended when the Z80 sent its next 'L' (%r)" % log.strip().splitlines()[:2])
        check(io.time.ms - t0 < io.ZX_STALL_MS,
              "no stall wait for the skipped block (%d ms)" % (io.time.ms - t0))
        check(tsp.offset == 0 and not pio.tx, "tape at the end (rewound), TX empty")

        print("the Z80 stops reading mid-block (BREAK between blocks)")
        tsp.offset = tsp.tap_idx = 0
        r, log = session(z80_load("beta", stop_after_blocks=2))
        # alpha's header read whole; alpha's data read 19 bytes, then the Z80 stops
        check("then stopped" in log and not pio.tx,
              "gave up after ZX_STALL_MS, TX flushed (%r)" % log.strip().splitlines()[-1:])
        check(tsp.offset == off_b, "the tape moved on past the half-read block (%d)" % tsp.offset)
        r, log = session(z80_load())
        check(r == ("ok", data_b), "the next LOAD works first time (%s)" % (r[0],))

        print("an unread tail shorter than the FIFO is flushed at the next 'L'")
        short = bytes(range(20))                # 22 bytes on the wire; the ROM reads 19
        tap2 = tap_block(0xFF, short) + tap_block(0x00, header("beta", len(data_b))) + tap_block(0xFF, data_b)
        with real_open(tap_path, "wb") as f:
            f.write(tap2)
        tsp.totlen, tsp.offset, tsp.tap_idx = len(tap2), 0, 0
        r, log = session(z80_load("beta"))
        check(r == ("ok", data_b), "beta loaded; the 3 unread bytes never became a flag (%s)" % (r[0],))
        with real_open(tap_path, "wb") as f:
            f.write(tap)
        tsp.totlen = len(tap)

        print("compatible mode (LOAD_ZX_C)")
        tsp.offset = tsp.tap_idx = 0
        del calls[:]
        r, log = session(z80_load(), compat=True)
        check(r == ("ok", data_a) and calls == [76],
              "one LOAD_ZX_C streams the tape; READY for the ROM's second 'L' (%s, %s)" % (r[0], calls))
        check("stream ended with" in log and not pio.tx,
              "the unread tail (beta) is dropped after the stall, TX empty")

        print("SAVE")
        payload = bytes((i * 3) & 0xFF for i in range(1500))
        r, log = session(z80_save("saved", payload))
        f = os.path.join(d, "saved.tap")
        want = tap_block(0x00, header("saved", len(payload))) + tap_block(0xFF, payload)
        check(r == "ok" and os.path.exists(f) and real_open(f, "rb").read() == want,
              "saved.tap is the right TAP (%s)" % r)
        check(getattr(tsp, "listing_stale", False),
              "the folder's listing is marked stale, for the next command to re-read")
        tsp.listing_stale = False

        for what, kw, z80 in (
                ("the header block stops", dict(hdr_stop_at=9), None),
                ("the data block stops", dict(dat_stop_at=700), None),
                ("the data block fails its parity", dict(dat_corrupt=400), "ok"),
                ("a refused header: its data block never gets READY", dict(hdr_corrupt=6), "R")):
            if os.path.exists(f):
                os.remove(f)
            r, log = session(z80_save("saved", payload, **kw))
            check(not os.path.exists(f) and "nothing saved" in log and (z80 is None or r == z80)
                  and not getattr(tsp, "listing_stale", False),
                  "%s: nothing written, listing not marked (Z80: %s; %r)" % (what, r, log.strip().splitlines()[-1:]))

        print("SAVE: the folder is decided after the mount (§2 #21)")
        # ZX48 mode has no card check before a SAVE, so the write's mount is
        # where a returned or different card is set up -- and SD_REVALIDATE
        # moves cur_path to the top folder when this card lacks the old one.
        top = tempfile.mkdtemp()
        tsp.cur_path = os.path.join(d, "GONE")

        def card_back(*a):
            tsp.cur_path = top
        io.ENA_SD = card_back
        r, log = session(z80_save("moved", payload))
        check(os.path.exists(os.path.join(top, "moved.tap")) and "wrote" in log,
              "written into the folder the mount left (%r)" % log.strip().splitlines()[-1:])
        os.remove(os.path.join(top, "moved.tap"))
        os.rmdir(top)
        io.ENA_SD = lambda *a: None
        tsp.cur_path = d

        r, log = session(z80_save("a/b", payload))
        check(not os.path.exists(os.path.join(d, "a")) and not os.path.exists(os.path.join(d, "b.tap"))
              and "file name" in log,
              "an unusable name ('a/b'): nothing written (%r)" % log.strip())

        print("  PASS  no put() into a full TX FIFO (FakePIO raises if one happens)")
        for name in ("START_WATCHDOG", "WATCHDOG", "ABORT_TX", "CORE1_BUSY"):
            check(not hasattr(io, name), "no %s in tspico_io" % name)
    except L.PutWouldBlock as e:
        check(False, str(e))

    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
