"""Host-side test for the virtual printer's bus side -- CPython, no Pico.

Runs the PRODUCTION TS.tspico.PRINT_IO and the printer commands against a
Z80 that follows the EXROM's printer sequences (captured on hardware with
the 1.8b ROM): an LPRINT character (pre-load status, READY), a character
>= 80h and COPY (pre-load, READY, 'D' + len + data + XOR, READY, final
status). The PIO is load_ts_hosttest's (4-deep FIFOs, auto-busy, puts into
a full TX recorded); the SD card is a temp folder.

What it pins:
  * every character is its own transaction: TX = [01], status FF after
    each, so the next SYNC / pre-header finds the pre-load;
  * the text lands in /VLPRINT/PRN0001.TXT in zmakebas form, flushed
    mid-printout once the buffer passes PRINT_FLUSH_AT, and on CLPRINT;
    OPPRINT starts the next numbered file;
  * a UDG's 8-byte body is taken and the Z80 gets final status 01;
  * COPY writes /VSCREEN/SCR0001.BMP at the default 512x384, status 01;
    tpi:bmp changes the size;
  * BREAK in the middle of a COPY body: back to idle, no file;
  * the dispatcher flushes printer text before any other command.

Run:  python3 src/test/printer_io_hosttest.py
"""

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import process_cmd_hosttest as P                                # noqa: E402
import load_ts_hosttest as L                                    # noqa: E402

READY, IDLE = L.READY, L.IDLE
results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg)


class PIO(L.FakePIO):
    blocked = False

    def put(self, b):
        if len(self.tx) >= 4:
            self.blocked = True
        return L.FakePIO.put(self, b)


def z80_char():
    """LPRINT of an ordinary character (EXROM 1828h)."""
    st = yield ("in",)
    r = yield from L.ready_wait()
    return r or ("ok" if st == 0x01 else "st%02X" % (st or 0))


def z80_body(data, break_at=None):
    """A character >= 80h or COPY: EXROM 223Eh."""
    st = yield ("in",)
    if st != 0x01:
        return "st%02X" % (st or 0)
    r = yield from L.ready_wait()
    if r:
        return r
    n = len(data)
    body = bytes([0x44, n & 0xFF, n >> 8]) + bytes(data)
    x = 0
    for b in body:
        x ^= b
    for i, b in enumerate(body + bytes([x])):
        if break_at is not None and i == break_at:
            yield L.out(0x0F, 0x03)
            yield ("wait", READY | IDLE, 3000)
            return "D"
        yield L.out(0x0E, b)
    r = yield from L.ready_wait()
    if r:
        return r
    st = yield ("in",)
    return "ok" if st == 0x01 else "st%02X" % (st or 0)


def char_pre(c, n=0):
    pre = bytearray([0x42, 0x05, 0xFF, c, 0x02 if c >= 0x80 else 0x01, 0x01, 0x38, n & 0xFF, n >> 8, 0])
    x = 0
    for b in pre[:9]:
        x ^= b
    pre[9] = x
    return pre


def copy_pre(n, mode=0):
    pre = bytearray([0x42, 0x04, 0xFF, 0xFF, mode, 0x20, 0x18, n & 0xFF, n >> 8, 0])
    x = 0
    for b in pre[:9]:
        x ^= b
    pre[9] = x
    return pre


def main():
    P.install_fakes()
    import TS.tspico as t
    import TS.tspico_io as tio
    t.TLM_ENABLED = False
    ft = L.FakeTime()
    t.time = ft
    tio.time = ft

    root = tempfile.mkdtemp()
    t.VLPRINT = os.path.join(root, "VLPRINT")
    t.VSCREEN = os.path.join(root, "VSCREEN")
    pio = PIO()
    t.ACTIVATE_SD = lambda: None
    t.DEACTIVATE_SD = lambda: None

    def activate_mq():                          # a fresh SM: FIFOs empty, Y busy
        pio.tx, pio.rx, pio.y = [], [], 0
    t.ACTIVATE_MQ = activate_mq
    msgs = []
    t.SEND_MSG = lambda msg, msg1, st, *a: msgs.append((msg, st))

    def run(script, pre):
        P.fresh(t, pio)
        pio.tx, pio.rx, pio.y = [0x01], [], 0   # previous pre-load; pre-header OUTs dropped Y
        tio.kill = False
        pio.run(script)
        t.PRINT_IO(pre)
        pio.finish()
        return pio.result

    def idle():
        return pio.tx == [0x01] and not pio.rx and pio.status() == 0xFF and not pio.blocked

    def prn(name="PRN0001.TXT"):
        p = os.path.join(t.VLPRINT, name)
        return open(p, "rb").read().decode() if os.path.exists(p) else None

    print("LPRINT characters")
    t.PRT = t.TextCapture()
    t.prn_path = None
    t.PRINT_FLUSH_AT = 4096
    rs = [run(z80_char(), char_pre(c)) for c in b"HI\r"]
    check(rs == ["ok"] * 3 and idle(), "each character: status read, READY, TX = [01], FF (%s)" % rs)
    check(prn() is None and t.PRT.buf == b"HI\n", "buffered, nothing on SD yet")

    print("a UDG character (8-byte body)")
    r = run(z80_body([0, 0x3C, 0x42, 0x42, 0x7E, 0x42, 0x42, 0]), char_pre(0x90, 8))
    check(r == "ok" and idle() and t.PRT.buf.endswith(b"\\A"),
          "body taken, final status 01, \\A in the text (%s)" % r)

    print("flush mid-printout")
    t.PRINT_FLUSH_AT = 8
    for c in b"XYZ\r":
        run(z80_char(), char_pre(c))
    check(prn() == "HI\n\\AXYZ" and t.PRT.buf == b"\n" and idle(),
          "reaching PRINT_FLUSH_AT writes PRN0001.TXT; the rest stays buffered (%r)" % prn())
    t.PRINT_FLUSH_AT = 4096

    print("CLPRINT / OPPRINT")
    run(z80_char(), char_pre(ord("Q")))
    t.PRN_CLOSE(None, "   tpi:clprint")
    check(prn() == "HI\n\\AXYZ\nQ" and t.prn_path is None and "closed" in msgs[-1][0],
          "CLPRINT writes the rest and closes (%r)" % msgs[-1][0])
    t.PRN_OPEN(None, "   tpi:opprint")
    run(z80_char(), char_pre(ord("Z")))
    t.PRINT_FLUSH()
    check(prn("PRN0002.TXT") == "Z" and "PRN0002" in msgs[-1][0],
          "OPPRINT starts PRN0002.TXT (%r)" % msgs[-1][0])

    print("PRNSZ / AUTOLF / BMP")
    t.PRN_SIZE(bytearray([0, 0, 0, 40, 0, 20, 0, 0, 0, 0]), "   tpi:prnsz")
    check((t.PRT.cols, t.PRT.lines) == (40, 20), "CODE 40,20 -> 40 columns, 20 lines")
    t.PRN_SIZE(bytearray(10), "   tpi:prnsz 80 72")
    check((t.PRT.cols, t.PRT.lines) == (80, 72), "text arguments work too")
    t.PRN_FLAG(None, "   tpi:autolf")
    on = t.PRT.autolf
    t.PRN_FLAG(None, "   tpi:noautolf")
    check(on and not t.PRT.autolf, "AUTOLF on, NOAUTOLF off")
    t.PRN_BMP(bytearray([0, 0, 0, 0, 1, 192, 0, 0, 0, 0]), "   tpi:bmp")
    check(t.bmp_size == (256, 192), "BMP CODE 256,192")
    t.PRN_BMP(bytearray([0, 0, 0, 100, 0, 50, 0, 0, 0, 0]), "   tpi:bmp")
    check(t.bmp_size == (256, 192) and msgs[-1][1] == t._4_Q_Parameter, "bad size refused (Q)")
    t.bmp_size = (512, 384)

    print("COPY")
    scr = open(os.path.join(HERE, "fixtures", "copy_screen_mode0.bin"), "rb").read()
    r = run(z80_body(scr), copy_pre(len(scr)))
    bmp = os.path.join(t.VSCREEN, "SCR0001.BMP")
    check(r == "ok" and idle() and os.path.exists(bmp) and os.path.getsize(bmp) == 98422,
          "SCR0001.BMP, 512x384 (%d bytes), final status 01 (%s)"
          % (os.path.getsize(bmp) if os.path.exists(bmp) else -1, r))
    r = run(z80_body(scr, break_at=2000), copy_pre(len(scr)))
    check(r == "D" and idle() and not os.path.exists(os.path.join(t.VSCREEN, "SCR0002.BMP")),
          "BREAK mid-body: Report D, back to idle, no file (%s)" % r)

    print("the dispatcher flushes before any other command")
    for name in ("TS/tspico.py", "dev_tspico.py"):
        src = open(os.path.join(SRC, name), encoding="utf-8").read().replace("\r", "")
        i = src.index("if PRT.buf and not (pre[0] == 66 and pre[1] in (4, 5, 6)):")
        j = src.index("if pre[0] not in (0, 255, 66):", i)
        check("PRINT_FLUSH()" in src[i:j] and "elif pre[0] == 66 and pre[1] in (4, 5, 6):" in src,
              "%s: flush before the handler, printer pre-headers go to PRINT_IO" % name)

    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
