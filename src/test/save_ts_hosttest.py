"""Host-side test for SAVE_TS (issue #51 stage 3) -- CPython, no Pico.

Runs the PRODUCTION TS/tspico_io.SAVE_TS against a Z80 that follows the
EXROM's SAVE sequence (1.8b: 18D2 ready-wait, header block, 190B ready-wait
+ status, data block with no ready-wait, final ready-wait + status, BREAK
checked every 256 bytes). The simulated PIO is load_ts_hosttest's: 4-deep
FIFOs, A0 in bit 8 of every Z80 write, auto-busy, RX overflow counted, and a
test FAILURE on any put() into a full TX FIFO. Z80 and SAVE_TS interleave:
every FIFO call SAVE_TS makes advances the Z80 one step. After SAVE_TS
returns, the test does what the dispatcher does (fresh SM, 0x01 pre-load,
idle or RECOVERED) and lets the Z80 finish.

What it pins:
  * a normal SAVE still writes the right .tap, statuses 01 / 01 01;
  * READY is raised by SAVE_TS right before the header capture, and the
    dispatcher no longer says it after a SAVE pre-header;
  * BREAK in the header block and mid data block (the 1.8b ROM's 0Fh
    write): the SAVE ends at once, nothing is written, the Z80 gets
    READY + IDLE and raises Report D;
  * the Z80 going silent mid-block: RECOVERED, nothing written, no hang;
  * a corrupted data block: final status 02 (Report R), nothing written;
  * a header whose session doesn't match the pre-header: refused (R);
  * no RX overflow anywhere, and the data-capture loop allocates nothing.

Run:  python3 src/test/save_ts_hosttest.py
"""

import ast
import os
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from sync_io_hosttest import install_fakes, FakeTime          # noqa: E402
import load_ts_hosttest as L                                    # noqa: E402
from save_name_hosttest import build_header, build_data         # noqa: E402

READY, IDLE, RECOVERED = L.READY, L.IDLE, L.RECOVERED
REPORT = {0x02: "R", 0x03: "F", 0x06: "6", 0x08: "A", 0x0A: "J",
          0x0B: "D"}   # 11 and up: $1BF3's chain falls through to $00F8, RST 8 0Ch -- Report D
SESSION = 0x1234


def status_report(st):
    return "ok" if st == 0x01 else REPORT.get(st, "st%02X" % (st if st is not None else 0))


def z80_save(hdr, dat, header_break=None, break_at=None, stop_at=None, corrupt_at=None):
    """The EXROM after the dispatcher has taken the SAVE pre-header."""
    st = yield ("in",)                          # 18C4: pre-load status, no wait
    if st != 0x01:
        return "st%02X" % (st or 0)
    r = yield from L.ready_wait()               # 18D2
    if r:
        return r
    for i, b in enumerate(hdr):
        if header_break is not None and i == header_break:
            yield L.out(0x0F, 0x03)             # BRK_ABORT
            yield ("wait", READY | IDLE, 3000)
            return "D"
        yield L.out(0x0E, b)
    r = yield from L.ready_wait()               # 190B
    if r:
        return r
    st = yield ("in",)
    if st != 0x01:
        return status_report(st)
    n = len(dat)
    for i, b in enumerate(dat):                 # no ready-wait before the data
        if stop_at is not None and i == stop_at:
            yield ("stop",)
        if break_at is not None and i >= break_at and ((n - 1 - i) & 0xFF) == 0xFF:
            yield L.out(0x0F, 0x03)             # STEP -> BRK_ABORT
            yield ("wait", READY | IDLE, 3000)
            return "D"
        if corrupt_at is not None and i == corrupt_at:
            b ^= 0x55                           # a bit error on the wire
        yield L.out(0x0E, b)
    r = yield from L.ready_wait()
    if r:
        return r
    st = yield ("in",)
    return status_report(st)


results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg)


def main():
    install_fakes()
    tspico = types.ModuleType("TS.tspico")
    tspico.TLM = lambda *a, **k: None
    sys.modules["TS.tspico"] = tspico
    sys.path.insert(0, SRC)
    import TS.tspico_io as io
    io.time = FakeTime()
    io.ENA_SD = lambda *a: None

    d = tempfile.mkdtemp()
    real_chdir = os.chdir
    io.os = types.SimpleNamespace(**{k: getattr(os, k) for k in dir(os) if not k.startswith("__")})
    io.os.chdir = lambda p: None

    payload = bytes((i * 13 + 7) & 0xFF for i in range(3000))
    hdr = bytes(build_header(b"savetest", len(payload), session=SESSION))
    dat = bytes(build_data(payload, session=SESSION))
    pre = bytearray([0, 0, 0xFF, SESSION & 0xFF, SESSION >> 8, 0, 0, 0, 0, 0])

    def save(native=None, f_name="", hdr=hdr, dat=dat, no_card=False, append=False, **kw):
        """Dispatcher side: pre-load staged, Y busy (the pre-header OUTs
        dropped it, and it no longer says READY for a SAVE), then SAVE_TS,
        then the dispatcher's re-arm, then let the Z80 finish."""
        for f in os.listdir(d):
            os.remove(os.path.join(d, f))
        pio = L.FakePIO()
        pio.tx = [0x01]
        pio.y = 0
        io.log_entries = ""
        io.kill = False
        io.dead = True
        io.busy = False
        tsp = types.SimpleNamespace(f_name=f_name, append=append, cur_path=d,
                                    LOG_LEVEL=0, VERBOSE=False, native=native,
                                    save_no_card=no_card)
        pio.run(z80_save(hdr, dat, **kw))
        out = io.SAVE_TS(pio, tsp, pre)
        saved = out[3]
        log = io.log_entries
        # the dispatcher: ACTIVATE_MQ (fresh FIFOs) + 0x01 + idle/RECOVERED
        pio.tx, pio.rx = [0x01], []
        io.MQ_STATUS(pio, "recovered" if getattr(tsp, "save_recovered", False) else "idle")
        pio.finish()
        return pio, pio.result, saved, log, tsp, os.listdir(d)

    try:
        print("normal SAVE")
        pio, r, saved, log, tsp, files = save()
        check(r == "ok" and saved and files == ["savetest.tap"],
              "saved: Z80 gets 0 OK, SAVE_TS reports saved, file written (%s, %s, %s)"
              % (r, saved, files))
        blob = open(os.path.join(d, files[0]), "rb").read() if files else b""
        check(len(blob) == 21 + len(payload) + 4 and blob[21 + 3:21 + 3 + len(payload)] == payload,
              "the .tap holds the header and the payload intact (%d bytes)" % len(blob))
        check(pio.dropped == 0, "no RX overflow (%d dropped)" % pio.dropped)
        check(not tsp.save_recovered, "save_recovered stays False")

        print("READY: SAVE_TS raises it, right before the header capture")
        body = open(os.path.join(SRC, "TS", "tspico_io.py"), encoding="utf-8").read().replace("\r", "")
        sv = body[body.index("def SAVE_TS("):body.index("def SAVE_ZX(")]
        a = sv.index('MQ_STATUS(MQ, "mid")')
        check(sv[a:sv.index("\n", sv.index("\n", a) + 1)].strip().endswith("got = RX_CAPTURE(MQ, raw, 21, 1000)"),
              "MQ_STATUS(mid) is immediately followed by the header capture")
        for name in ("TS/tspico.py", "dev_tspico.py"):
            src = open(os.path.join(SRC, name), encoding="utf-8").read().replace("\r", "")
            i = src.index("if pre[0] not in (0, 255, 66):")
            cond = src[i:src.index("MQ_READY()", i)]
            check("and not (pre[0] == 0 and pre[1] == 0)" not in cond      # SAVE no longer excepted
                  and "SAVE_TS(MQ, TSP, pre)" in src,
                  "%s: no READY after a SAVE pre-header; SAVE_TS gets pre" % name)

        print("BREAK in the header block (1.8b ROM)")
        pio, r, saved, log, tsp, files = save(header_break=8)
        check(r == "D" and not saved and not files,
              "Report D, nothing written (%s, %s)" % (r, files))
        check("stopped by BREAK in the header block" in log, "logged: %r" % log.strip()[:80])

        print("BREAK mid data block (1.8b ROM)")
        pio, r, saved, log, tsp, files = save(break_at=1000)
        check(r == "D" and not saved and not files,
              "Report D, partial SAVE discarded -- nothing written (%s, %s)" % (r, files))
        check("stopped by BREAK after the Z80 sent" in log and "nothing written" in log,
              "logged: %r" % log.strip().splitlines()[-1:])
        check(pio.dropped == 0, "no RX overflow (%d dropped)" % pio.dropped)

        print("the Z80 goes silent mid data block")
        pio, r, saved, log, tsp, files = save(stop_at=1500)
        check(not saved and not files and tsp.save_recovered and pio.status() == 0xFB,
              "nothing written, RECOVERED (FB) for the dispatcher to show (%s, %02X)"
              % (files, pio.status()))
        check("stalled after 1500 of" in log, "logged: %r" % log.strip().splitlines()[-1:])

        print("a corrupted data block")
        pio, r, saved, log, tsp, files = save(corrupt_at=500)
        check(r == "R" and not saved and not files,
              "final status 02 -> Report R, nothing written (%s, %s)" % (r, files))
        check("parity" in log, "logged: %r" % log.strip().splitlines()[-1:])

        print("no SD card (the dispatcher's card check failed)")
        pio, r, saved, log, tsp, files = save(no_card=True)
        check(r == "J" and not saved and not files,
              "refused with Report J at the header, nothing written (%s, %s)" % (r, files))
        check("no SD card" in log and "drained 0" in log,
              "logged, and the Z80 sent no data block: %r" % log.strip().splitlines()[-1:])

        print("the write's mount fails (no card after the transfer; §2 #21)")
        # The 2068 already has "0 OK" (the final status goes out before the
        # SD grabs GPIO 2-4, #40), so this can only be logged and retracted.
        def no_mount(*a):
            raise OSError(19, "SD card mount failed after 5 attempts")
        io.ENA_SD = no_mount
        pio, r, saved, log, tsp, files = save()
        check(r == "ok" and not saved and not files and tsp.f_name == "",
              "logged as a failed write; the name isn't left for the dispatcher to mount (%s, %r)"
              % (saved, tsp.f_name))
        check("SAVE write FAILED" in log and "after 5 attempts" in log,
              "the log says why: %r" % log.strip().splitlines()[-1:])

        print("append mode, and the mount finds a different card (§2 #21)")
        other = tempfile.mkdtemp()
        old = os.path.join(other, "OLD.TAP")
        with open(old, "wb") as f:
            f.write(b"old card")

        def swapped(*a):
            swapped.tsp.append = False                  # what SD_NOTE_CARD -> SD_REVALIDATE does
        io.ENA_SD = swapped
        real_ns = types.SimpleNamespace

        def capture(**k):
            ns = real_ns(**k)
            if "save_no_card" in k:
                swapped.tsp = ns
            return ns
        types.SimpleNamespace = capture
        try:
            pio, r, saved, log, tsp, files = save(f_name=old, append=True)
        finally:
            types.SimpleNamespace = real_ns
        check(not saved and open(old, "rb").read() == b"old card" and not files,
              "nothing appended to the other card's file (%s, %r)" % (saved, open(old, "rb").read()[:12]))
        check("different SD card" in log, "logged: %r" % log.strip().splitlines()[-1:])

        io.ENA_SD = lambda *a: None                     # the same card: append works as before
        pio, r, saved, log, tsp, files = save(f_name=old, append=True)
        check(saved and open(old, "rb").read().startswith(b"old card")
              and len(open(old, "rb").read()) == 8 + 21 + len(payload) + 4,
              "same card: the SAVE is appended (%d bytes)" % len(open(old, "rb").read()))
        os.remove(old)
        os.rmdir(other)

        print("session mismatch between pre-header and header block")
        pre[3] ^= 0xFF
        pio, r, saved, log, tsp, files = save()
        pre[3] ^= 0xFF
        check(r == "R" and not saved and not files and "session" in log,
              "refused with Report R before the data block (%s)" % r)

        print("native SAVE \"f:...\" (armed by tpi:fopen)")
        from TS import native as N
        target = os.path.join(d, "prog.bas")
        arm = lambda **k: dict(dict(op=0, path=target, session=SESSION, refuse=False), **k)
        phdr = bytes(build_header(b"prog.bas", len(payload), hdtype=0, addr=10,
                                  hdvars=len(payload), session=SESSION))
        pio, r, saved, log, tsp, files = save(native=arm(), f_name="/sd/TAP/MOUNTED.TAP", hdr=phdr)
        blob = open(target, "rb").read() if files else b""
        check(r == "ok" and saved and files == ["prog.bas"],
              "written to the armed path, not <name>.tap (%s, %s)" % (r, files))
        check(N.parse_plus3(blob[:128]) == (0, len(payload), 10, len(payload)) and blob[128:] == payload,
              "a +3DOS file: header (program, LINE 10, vars offset) + the payload")
        check(tsp.f_name == "/sd/TAP/MOUNTED.TAP" and tsp.native is None and tsp.native_saved,
              "the mount is untouched, the arm used up, the dispatcher told (native_saved)")
        scr = bytes((i * 3) & 0xFF for i in range(6912))
        shdr = bytes(build_header(b"pic", 6912, hdtype=3, addr=16384, session=SESSION))
        sdat = bytes(build_data(scr, session=SESSION))
        target = os.path.join(d, "pic.scr")
        pio, r, saved, log, tsp, files = save(native=arm(path=target), hdr=shdr, dat=sdat)
        blob = open(target, "rb").read() if files else b""
        check(r == "ok" and blob == scr, "SCREEN$: the raw 6912 bytes, no header (%s, %d)" % (r, len(blob)))
        target = os.path.join(d, "prog.bas")
        pio, r, saved, log, tsp, files = save(native=arm(path=target, refuse=True), hdr=phdr)
        check(r == "D" and not saved and not files and tsp.native is None,
              "'Replace (Y/N)?' answered N: Report D before the data block, nothing written (%s)" % r)
        pio, r, saved, log, tsp, files = save(native=arm(session=0x4321))
        check(r == "ok" and files == ["savetest.tap"] and tsp.native is None,
              "an arm for another session is stale: a normal .tap, the arm dropped (%s, %s)" % (r, files))
        pio, r, saved, log, tsp, files = save(native=dict(op=1, session=SESSION, tap="x", totlen=1))
        check(r == "ok" and files == ["savetest.tap"],
              "a LOAD arm makes a SAVE neither native nor refused (%s)" % (files,))

        print("the data capture allocates nothing per byte")
        tree = ast.parse(body)
        fn = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "RX_BLOCK"][0]
        loop = [n for n in ast.walk(fn) if isinstance(n, ast.While)][0]
        per_byte = loop.body[0].body            # the `if rx():` branch
        bad = []
        for stmt in per_byte:
            for n in ast.walk(stmt):
                if isinstance(n, ast.Assign) and isinstance(n.value, ast.Attribute):
                    bad.append((n.lineno, "bound method"))
                elif isinstance(n, (ast.List, ast.Dict, ast.Tuple, ast.JoinedStr, ast.ListComp)):
                    bad.append((n.lineno, type(n).__name__))
                elif isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Load):
                    bad.append((n.lineno, "attribute lookup"))
        check(not bad, "RX_BLOCK's per-byte branch: no attribute lookups, bound methods or containers (%s)" % bad)

        print("  PASS  no put() into a full TX FIFO (FakePIO raises if one happens)")
    except L.PutWouldBlock as e:
        check(False, str(e))
    finally:
        for f in os.listdir(d):
            os.remove(os.path.join(d, f))
        os.rmdir(d)

    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
