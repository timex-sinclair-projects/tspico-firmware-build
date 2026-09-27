"""Host-side test for TS/printer.py -- CPython, no Pico.

Pins the virtual printer's conversions:
  * LPRINT / LLIST text in zmakebas form: ENTER, block graphics, UDGs,
    copyright, backslash, colour controls, AT / TAB / comma, raw bytes;
    PRNSZ wrapping, AUTOLF (CR LF) and AUTOPG (form feed);
  * the exact stream captured on hardware (HELLO, CHR$ 144, "A";, LLIST);
  * numbered file names (PRN0001.TXT, next free number, folder created);
  * COPY -> 16-colour BMP: header, palette, size, bottom-up rows, pixel
    doubling, and the four screen modes (standard, second screen,
    hi-colour, hi-res) -- decoded back and compared pixel by pixel. The
    blank screen captured on hardware is one of the fixtures.

Run:  python3 src/test/printer_hosttest.py
"""

import io
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(SRC, "TS"))
import printer as P                                             # noqa: E402

results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg)


def text(stream, **kw):
    t = P.TextCapture()
    for k, v in kw.items():
        setattr(t, k, v)
    for c in stream:
        t.feed(c)
    return t.buf.decode()


def read_bmp(data):
    """(w, h, pixel(x, y) -> colour index) for a 4-bit BMP."""
    le = lambda o, n: int.from_bytes(data[o:o + n], "little")
    off, w, h = le(10, 4), le(18, 4), le(22, 4)
    stride = ((w * 4 + 31) // 32) * 4

    def pix(x, y):
        row = off + (h - 1 - y) * stride
        b = data[row + x // 2]
        return (b >> 4) if x % 2 == 0 else (b & 0x0F)
    return w, h, pix


def scr_set(scr, base, x, y):
    a = base + P._pix_addr(y) + x // 8
    scr[a] |= 0x80 >> (x % 8)


def main():
    print("text: zmakebas form")
    check(text(b"HELLO\r") == "HELLO\n", "ENTER -> LF")
    check(text(b"HELLO\r", autolf=True) == "HELLO\r\n", "AUTOLF: ENTER -> CR LF")
    # 80h + bits: 1 = top-right, 2 = top-left, 4 = bottom-right, 8 = bottom-left
    check(text(bytes([0x80, 0x8F, 0x85, 0x8A, 0x83])) == "\\  \\::\\ :\\: \\''",
          "block graphics -> zmakebas quadrant pairs (empty, full, right, left, top)")
    check(text(bytes([0x90, 0xA4])) == "\\A\\U", "UDGs -> \\A .. \\U")
    check(text(bytes([0x7F, 0x5C, 0x60])) == "\\*\\\\`",
          "copyright -> \\*, backslash -> \\\\, pound stays `")
    check(text(bytes([0x10, 4, ord("x"), 0x13, 1])) == "\\{INK 4}x\\{BRIGHT 1}",
          "colour controls -> \\{INK n} .. with their parameter")
    check(text(bytes([0x16, 5, 7, 0x17, 12, 0x06])) == "\\{AT 5,7}\\{TAB 12}\\{COMMA}",
          "AT row,col / TAB n / comma")
    check(text(bytes([0x01, 0xC5])) == "\\{0x01}\\{0xC5}", "anything else -> \\{0xNN}")

    print("text: PRNSZ / AUTOPG")
    check(text(b"ABCDEFG", cols=3) == "ABC\nDEF\nG", "wraps at PRNSZ columns")
    check(text(b"a\rb\rc\r", autopg=True, lines=2) == "a\nb\n\fc\n",
          "AUTOPG: form feed every PRNSZ lines")
    check(text(b"x" * 100, cols=0) == "x" * 100, "cols=0: never wraps")

    print("text: the stream captured on hardware")
    cap = b"HELLO\r\x90\rA" + b'  10 PRINT "foo"\r'
    check(text(cap) == 'HELLO\n\\A\nA  10 PRINT "foo"\n',
          "LPRINT HELLO / CHR$ 144 / \"A\"; / LLIST (%r)" % text(cap))

    print("file names")
    d = tempfile.mkdtemp()
    sub = os.path.join(d, "VLPRINT")
    n1 = P.next_name(sub, "PRN", "TXT")
    check(n1 == sub + "/PRN0001.TXT" and os.path.isdir(sub),
          "empty / missing folder -> PRN0001.TXT, folder created")
    for n in ("PRN0001.TXT", "prn0007.txt", "PRN00X2.TXT", "OTHER.TXT"):
        open(os.path.join(sub, n), "w").close()
    check(P.next_name(sub, "PRN", "TXT") == sub + "/PRN0008.TXT",
          "next after the highest number, ignoring junk")

    print("COPY -> BMP")
    blank = open(os.path.join(HERE, "fixtures", "copy_screen_mode0.bin"), "rb").read()
    f = io.BytesIO()
    w, h = P.write_bmp(f, blank, 0, 0, 2, 2)
    data = f.getvalue()
    bw, bh, pix = read_bmp(data)
    check(data[:2] == b"BM" and (bw, bh) == (512, 384) == (w, h)
          and len(data) == 14 + 40 + 64 + 256 * 384
          and int.from_bytes(data[2:6], "little") == len(data),
          "512x384 4-bit BMP, header sizes consistent (%d bytes)" % len(data))
    check(data[28] == 4 and data[46] == 16 and data[54 + 7 * 4:54 + 8 * 4] == bytes((0xD7, 0xD7, 0xD7, 0)),
          "4 bpp, 16-colour palette, colour 7 = white")
    check(all(pix(x, y) == 7 for x in (0, 255, 511) for y in (0, 191, 383)),
          "hardware capture (blank, attr 38h): all paper white")

    scr = bytearray(6912)
    for i in range(768):
        scr[0x1800 + i] = 0x38                  # paper 7, ink 0
    scr[0x1800] = 0x42                          # cell (0,0): bright, ink 2
    scr_set(scr, 0, 0, 0)                       # top-left pixel
    scr_set(scr, 0, 255, 191)                   # bottom-right pixel
    scr_set(scr, 0, 100, 70)
    f = io.BytesIO()
    P.write_bmp(f, scr, 0, 0, 2, 2)
    _, _, pix = read_bmp(f.getvalue())
    check(pix(0, 0) == 10 and pix(1, 1) == 10 and pix(2, 0) == 8,
          "top-left pixel: bright red ink, doubled to 2x2; its paper bright black")
    check(pix(510, 382) == 0 and pix(511, 383) == 0 and pix(509, 383) == 7,
          "bottom-right pixel in the right place (rows run bottom-up)")
    check(pix(200, 140) == 0 and pix(202, 140) == 7, "a pixel mid-screen lands at (2x, 2y)")
    f = io.BytesIO()
    w, h = P.write_bmp(f, scr, 0, 0, 1, 1)
    _, _, pix1 = read_bmp(f.getvalue())
    check((w, h) == (256, 192) and pix1(0, 0) == 10 and pix1(100, 70) == 0 and pix1(101, 70) == 7,
          "1x scale: 256x192, same pixels")

    big = bytearray(15104)
    for i in range(768):
        big[0x3800 + i] = 0x0E                  # screen 1: paper 1, ink 6
    scr_set(big, 0x2000, 10, 20)
    f = io.BytesIO()
    P.write_bmp(f, big, 1, 0, 1, 1)
    _, _, p = read_bmp(f.getvalue())
    check(p(10, 20) == 6 and p(11, 20) == 1, "mode 1: second screen at 6000h, attributes 7800h")

    hc = bytearray(15104)
    scr_set(hc, 0, 3, 9)
    hc[0x2000 + P._pix_addr(9)] = 0x04 | (0x02 << 3)   # row 9, col 0: ink 4, paper 2
    f = io.BytesIO()
    P.write_bmp(f, hc, 2, 0, 1, 1)
    _, _, p = read_bmp(f.getvalue())
    check(p(3, 9) == 4 and p(4, 9) == 2 and p(3, 8) == 0,
          "mode 2 hi-colour: one attribute per pixel row")

    hr = bytearray(15104)
    scr_set(hr, 0, 0, 0)                        # byte column 0 -> x 0-7
    scr_set(hr, 0x2000, 0, 0)                   # byte column 0 of 6000h -> x 8-15
    f = io.BytesIO()
    w, h = P.write_bmp(f, hr, 3, (1 << 3) | 7, 1, 1)
    _, _, p = read_bmp(f.getvalue())
    check((w, h) == (512, 192) and p(0, 0) == 7 and p(1, 0) == 1 and p(8, 0) == 7 and p(9, 0) == 1,
          "mode 3 hi-res: 512 wide, columns alternate 4000h / 6000h, colours from the pre-header")

    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
