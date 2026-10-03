"""TS-Pico virtual printer: LPRINT / LLIST to text, COPY to BMP.

Gustavo's manual v16, sections 2.26-2.27: printer output goes to a .TXT file
in /VLPRINT, COPY writes the screen to a .BMP in /VSCREEN. The 2068 sends
them to the Pico only while TPMODE (5DDBh) bit 0 is set -- SAVE "tpi:picopt"
(the ROM parses that command itself); SAVE "tpi:ts2040" sends them to a
TS 2040 printer instead.

Wire format (captured on hardware, 1.8b ROM, 2026-09-27):
  LPRINT / LLIST: one transaction per character, 10-byte pre-header
      42 05 FF <char> 01|02 <flags> <ATTR_P> LL HH <xor>
  with an 8-byte body (the character's pattern) for chars >= 80h.
  LLIST arrives already detokenised; ENTER is 0Dh.
  COPY: 42 04 FF <hires colour> <mode> 20 18|40 18 LL HH <xor>, then a body
  of the display memory from 4000h: 6912 bytes (mode 0) or 15104 (4000h-
  7AFFh, both screens) for the other modes.

This module is pure: text conversion, file naming, BMP encoding. The bus
side (capturing, statuses, when SD may be touched) is in TS/tspico.py.
"""

import os

VLPRINT = "/sd/VLPRINT"
VSCREEN = "/sd/VSCREEN"

# zmakebas / zmakebas-plus escapes, so a capture reads like a zmakebas
# source listing (github.com/timex-sinclair-projects/zmakebas-plus).
BLOCKS = ("  ", " '", "' ", "''", " .", " :", "'.", "':",
          ". ", ".'", ": ", ":'", "..", ".:", ":.", "::")
CONTROLS = {0x10: "INK", 0x11: "PAPER", 0x12: "FLASH", 0x13: "BRIGHT",
            0x14: "INVERSE", 0x15: "OVER"}


def char_text(c):
    """zmakebas text for one printable byte (not ENTER, not a control)."""
    if c == 0x5C:
        return "\\\\"
    if c == 0x7F:
        return "\\*"                                # copyright
    if 0x20 <= c < 0x7F:
        return chr(c)                               # 60h (pound) stays `
    if 0x80 <= c <= 0x8F:
        return "\\" + BLOCKS[c - 0x80]              # block graphics
    if 0x90 <= c <= 0xA4:
        return "\\" + chr(0x41 + c - 0x90)          # UDGs A-U
    return "\\{0x%02X}" % c                         # anything else, raw


class TextCapture:
    """Turns the 2068's printer stream into zmakebas text in `buf` (bytes,
    UTF-8), tracking column / line for PRNSZ wrapping and AUTOPG."""

    def __init__(self):
        self.cols = 80          # PRNSZ: wrap at this column (0 = never)
        self.lines = 72         # PRNSZ: lines per page for AUTOPG
        self.autolf = False     # AUTOLF: ENTER -> CR LF (else LF)
        self.autopg = False     # AUTOPG: form feed every `lines` lines
        self.reset()

    def reset(self):
        self.buf = bytearray()
        self.col = 0
        self.line = 0
        self._ctl = None        # control byte waiting for its parameter(s)
        self._arg = []

    def _newline(self):
        self.buf.extend(b"\r\n" if self.autolf else b"\n")
        self.col = 0
        self.line += 1
        if self.autopg and self.lines and self.line >= self.lines:
            self.buf.extend(b"\f")
            self.line = 0

    def feed(self, c):
        """One byte from the 2068."""
        if self._ctl is not None:                   # parameter of a control
            self._arg.append(c)
            ctl = self._ctl
            need = 2 if ctl == 0x16 else 1          # AT row,col; the rest one
            if len(self._arg) < need:
                return
            self._ctl = None
            if ctl == 0x16:
                t = "\\{AT %d,%d}" % (self._arg[0], self._arg[1])
            elif ctl == 0x17:
                t = "\\{TAB %d}" % self._arg[0]
            else:
                t = "\\{%s %d}" % (CONTROLS[ctl], self._arg[0])
            self.buf.extend(t.encode())
            return
        if c == 0x0D:
            self._newline()
            return
        if 0x10 <= c <= 0x17:
            self._ctl = c
            self._arg = []
            return
        if c == 0x06:
            self.buf.extend(b"\\{COMMA}")
            return
        if c < 0x20:
            self.buf.extend(("\\{0x%02X}" % c).encode())
            return
        if self.cols and self.col >= self.cols:
            self._newline()
        self.buf.extend(char_text(c).encode())
        self.col += 1


def next_name(folder, prefix, ext):
    """Next free <prefix>NNNN.<ext> in folder (created if missing)."""
    try:
        names = os.listdir(folder)
    except OSError:
        os.mkdir(folder)
        names = []
    top = 0
    p, e = prefix.upper(), "." + ext.upper()
    for n in names:
        u = n.upper()
        if u.startswith(p) and u.endswith(e):
            try:
                top = max(top, int(u[len(p):-len(e)]))
            except ValueError:
                pass
    return "%s/%s%04d.%s" % (folder, prefix, top + 1, ext)


# ---- COPY -> BMP --------------------------------------------------------

# 2068 / Spectrum palette, 0-7 normal and 8-15 bright, as BMP (B, G, R, 0)
_PALETTE = bytearray()
for _i in range(16):
    _v = 0xFF if _i >= 8 else 0xD7
    _c = _i & 7
    _PALETTE.extend(bytes((_v if _c & 1 else 0, _v if _c & 4 else 0,
                           _v if _c & 2 else 0, 0)))


def _pix_addr(y):
    """Offset of pixel row y (0-191) in a display file."""
    return ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2)


def screen_size(mode):
    """(width, height) of the picture for COPY's mode byte."""
    return (512, 192) if mode == 3 else (256, 192)


# The 2.1 ROM's COPY (EXROM 16F3h) reads port FFh and, in 64-column mode,
# sends the colour choice k (bits 3-5) not as k but as table[k], from
# EXROM 16EBh. On the screen, choice k is ink k on paper 7-k (the 2068
# makes the paper the complement): black on white, blue on yellow, red on
# cyan, ... white on black (hardware, 2026-10-03, the eight COPYs of
# basic/SD/TAP/test/hirescopy.bas against the TV). Its bytes hold two
# colours a nibble each, but with red and green swapped in the middle four,
# so they can't be read as colour numbers: look k up instead.
HIRES_K = {0x07: 0, 0x16: 1, 0x43: 2, 0x52: 3, 0x25: 4, 0x34: 5, 0x61: 6, 0x70: 7}


def hires_ink_paper(c):
    """(ink, paper) of a 64-column COPY from its pre-header colour byte."""
    k = HIRES_K.get(c)
    if k is None:                       # not the 2.1 ROM's table: a nibble each
        return (c >> 4) & 7, c & 7
    return k, 7 - k


def row_colours(scr, mode, y, hires_colour, out):
    """Colour indices (0-15) for pixel row y into out (a bytearray of the
    picture width). scr is the COPY body.
      mode 0  standard screen at 4000h, attributes 5800h
      mode 1  second screen at 6000h, attributes 7800h
      mode 2  hi-colour: bitmap 4000h, one attribute per pixel row at 6000h
      mode 3  hi-res 512x192: byte columns alternate 4000h / 6000h, two
              colours from the COPY pre-header's colour byte (hires_ink_paper)
    """
    pa = _pix_addr(y)
    if mode == 3:
        ink, paper = hires_ink_paper(hires_colour)
        x = 0
        for col in range(32):
            for base in (0, 0x2000):
                b = scr[base + pa + col]
                for bit in range(7, -1, -1):
                    out[x] = ink if (b >> bit) & 1 else paper
                    x += 1
        return
    if mode == 1:
        bmp, att = 0x2000 + pa, 0x3800 + (y >> 3) * 32
    elif mode == 2:
        bmp, att = pa, 0x2000 + pa
    else:
        bmp, att = pa, 0x1800 + (y >> 3) * 32
    x = 0
    for col in range(32):
        a = scr[att + col]
        bright = 8 if a & 0x40 else 0
        ink = (a & 7) | bright
        paper = ((a >> 3) & 7) | bright
        b = scr[bmp + col]
        for bit in range(7, -1, -1):
            out[x] = ink if (b >> bit) & 1 else paper
            x += 1


def write_bmp(f, scr, mode, hires_colour, sx, sy):
    """Write the COPY body as a 4-bit (16-colour) BMP, each screen pixel
    sx wide and sy tall, streaming one row at a time (no whole-picture
    buffer: 2048x1536 would not fit)."""
    w0, h0 = screen_size(mode)
    w, h = w0 * sx, h0 * sy
    stride = ((w * 4 + 31) // 32) * 4
    off = 14 + 40 + 64
    size = off + stride * h
    hdr = bytearray(off)
    hdr[0:2] = b"BM"
    for pos, val, n in ((2, size, 4), (10, off, 4), (14, 40, 4),
                        (18, w, 4), (22, h, 4), (26, 1, 2),
                        (28, 4, 2), (34, stride * h, 4),
                        (38, 2835, 4), (42, 2835, 4), (46, 16, 4)):
        for k in range(n):
            hdr[pos + k] = (val >> (8 * k)) & 0xFF
    hdr[54:54 + 64] = _PALETTE
    f.write(hdr)
    cols = bytearray(w0)
    row = bytearray(stride)
    for y in range(h0 - 1, -1, -1):             # BMP rows run bottom-up
        row_colours(scr, mode, y, hires_colour, cols)
        x = 0
        for c in cols:
            for _ in range(sx):
                i = x >> 1
                if x & 1:
                    row[i] = (row[i] & 0xF0) | c
                else:
                    row[i] = (c << 4) | (row[i] & 0x0F)
                x += 1
        for _ in range(sy):
            f.write(row)
    return w, h
