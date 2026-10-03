#!/usr/bin/env python3
"""Render TS-Pico screens for the manual -- no 2068 needed.

Each picture is made in two steps:

  1. The PRODUCTION firmware (src/TS/tspico.py, under the host-test fakes)
     builds the reply for a command -- CAT, tpi:info, the tpi:cd menu, ... --
     and the bytes it would put on the bus are captured, exactly as the 2068
     would read them (function code, status, text, colour codes, the
     "Scroll?" page break).

  2. Those bytes are drawn the way the ROM prints them: 32 columns, CR, INK
     and PAPER (10h/11h + value, 8 = keep, 9 = contrast), with the 2068's own
     character set from its HOME ROM (3D00h; the Spectrum ROM's is the same).

So the text, layout and colours are the firmware's own, but the picture is a
rendering, not a photograph: the border, and where on the screen the ROM
starts printing, are chosen to look like a fresh screen.

Run:   python3 tools/render_screens.py            (writes docs/manual/images/*.png)
Needs: Pillow.
"""

import os
import sys
import tempfile
import types

from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "docs", "manual", "images")
sys.path.insert(0, os.path.join(REPO, "src", "test"))
sys.path.insert(0, os.path.join(REPO, "src"))

# ---- drawing -----------------------------------------------------------------

FONT = open(os.path.join(REPO, "ROMs", "GENUINE-2068-home.bin"), "rb").read()[0x3D00:0x4000]
# The 2068/Spectrum palette, BRIGHT 0 (what the Pico's text uses).
PALETTE = [(0, 0, 0), (0, 0, 205), (205, 0, 0), (205, 0, 205),
           (0, 205, 0), (0, 205, 205), (205, 205, 0), (205, 205, 205)]
KEYWORDS = {124: " STICK ", 126: " FREE "}       # how the 2068 prints | and ~
PAPER, INK, BORDER = 7, 0, 7                      # the 2068's own colours at power-on
SCALE = 3
EDGE = 24                                         # border, in screen pixels


class Screen:
    """The 2068's display: 24 rows of 32 cells, each with a character, an ink
    and a paper. Rows 0-21 are the upper screen, 22-23 the lower."""

    def __init__(self):
        self.ch = [[32] * 32 for _ in range(24)]
        self.ink = [[INK] * 32 for _ in range(24)]
        self.paper = [[PAPER] * 32 for _ in range(24)]
        self.row = self.col = 0
        self.cur_ink, self.cur_paper = 8, 8       # 8 = whatever is on screen

    def _scroll(self):
        for grid, blank in ((self.ch, 32), (self.ink, INK), (self.paper, PAPER)):
            del grid[0]
            grid.insert(21, [blank] * 32)
        self.row = 21

    def _cell(self, c):
        if self.col == 32:
            self.newline()
        r, k = self.row, self.col
        paper = self.paper[r][k] if self.cur_paper == 8 else self.cur_paper
        if self.cur_paper == 9:
            paper = 7 if self.ink[r][k] < 4 else 0
        ink = self.ink[r][k] if self.cur_ink == 8 else self.cur_ink
        if self.cur_ink == 9:
            ink = 0 if paper >= 4 else 7
        self.ch[r][k], self.ink[r][k], self.paper[r][k] = c, ink, paper
        self.col += 1

    def newline(self):
        self.col = 0
        self.row += 1
        if self.row > 21:
            self._scroll()

    def print_bytes(self, data, expand=True):
        """RST 10h, a byte at a time, as the ROM prints the Pico's text."""
        i = 0
        while i < len(data):
            b = data[i]
            if b in (0x10, 0x11) and i + 1 < len(data):
                v = data[i + 1]
                if b == 0x10:
                    self.cur_ink = v
                else:
                    self.cur_paper = v
                i += 2
                continue
            if b == 0x0D:
                self.newline()
            elif b == 0x08:
                self.col = max(0, self.col - 1)
            elif expand and b in KEYWORDS:
                for c in KEYWORDS[b].encode():
                    self._cell(c)
            elif 32 <= b <= 127:
                self._cell(b)
            i += 1

    def report(self, text):
        """The report on the bottom line, in the lower screen's colours."""
        for k, c in enumerate(text.encode()[:32]):
            self.ch[23][k], self.ink[23][k], self.paper[23][k] = c, INK, PAPER

    def image(self):
        w, h = 256 + 2 * EDGE, 192 + 2 * EDGE
        img = Image.new("RGB", (w, h), PALETTE[BORDER])
        px = img.load()
        for r in range(24):
            for k in range(32):
                g = FONT[(self.ch[r][k] - 32) * 8:(self.ch[r][k] - 32) * 8 + 8]
                fg, bg = PALETTE[self.ink[r][k]], PALETTE[self.paper[r][k]]
                for y in range(8):
                    bits = g[y]
                    for x in range(8):
                        px[EDGE + k * 8 + x, EDGE + r * 8 + y] = fg if bits & (0x80 >> x) else bg
        return img.resize((w * SCALE, h * SCALE), Image.NEAREST)


def save(screen, name):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name + ".png")
    screen.image().save(path, optimize=True)
    print("wrote", os.path.relpath(path, REPO))


# ---- the firmware, under the host-test fakes -----------------------------------

def firmware():
    import process_cmd_hosttest as P
    P.install_fakes()
    ext = types.ModuleType("dev_extcmd")
    ext.EXT_SA_FUNCT = {}
    sys.modules["dev_extcmd"] = ext
    import TS.tspico as t
    t.TLM_ENABLED = False
    t.time = P.FakeTime()
    t.LOG = lambda *a, **k: None
    t.led = types.SimpleNamespace(value=lambda *a: None, toggle=lambda: None)
    return t


class Wire:
    """What the Pico puts on the bus for one reply: CMD_PUT's bytes, with the
    key the 2068 user presses at a prompt."""

    def __init__(self, t, keys=(78,)):
        self.out = []
        self.keys = list(keys)
        t.CMD_PUT = lambda b: self.out.append(b if isinstance(b, int) else ord(b))
        t.MQ_READY = lambda: None
        t.CMD_DRAIN = lambda: None
        t.CMD_KEY = lambda: self.keys.pop(0) if self.keys else 78
        t.MQ = types.SimpleNamespace(rx_fifo=lambda: 0, get=lambda: 0, put=lambda b: None,
                                     tx_fifo=lambda: 0)

    def first_page(self):
        """The text the ROM prints before it waits for a key (00h) or the end
        of the loop (03h): past the function code and status."""
        b = bytes(self.out)
        body = b[2:]
        for end in (0x00, 0x03):
            if end in body:
                body = body[:body.index(end)]
        return body


def folder(t, entries):
    """A pretend card: /sd/TAP with these (name, size or None for a folder)."""
    root = tempfile.mkdtemp()
    for name, size in entries:
        p = os.path.join(root, name)
        if size is None:
            os.mkdir(p)
        else:
            with open(p, "wb") as f:
                f.truncate(size)

    def real(p):
        assert p.startswith("/sd/TAP"), p
        return os.path.join(root, p[len("/sd/TAP"):].strip("/"))

    class HostOS:
        def stat(self, p):
            st = os.stat(real(p))
            mode = 0x4000 if os.path.isdir(real(p)) else 0x8000
            return (mode, 0, 0, 0, 0, 0, st.st_size, 0, 0, 0)

        def ilistdir(self, p="/sd/TAP"):
            for n in os.listdir(real(p)):
                full = os.path.join(real(p), n)
                yield (n, 16384, 0, 0) if os.path.isdir(full) else (n, 32768, 0, os.path.getsize(full))

        def statvfs(self, p):
            return (4096, 4096, 61440, 57000)       # a 240 MB card, ~222 MB free
    t.os = HostOS()
    return root


# ---- the screens ----------------------------------------------------------------

GAMES = [("DEMO", None), ("GAMES", None), ("TEST", None),
         ("3DTanx.tap", 9_216), ("Chess.tap", 21_514), ("{game}.tap", 6_970),
         ("Frogger.tap", 41_377), ("jet~1.tap", 17_830), ("Manic.tap", 37_902),
         ("Pssst.tap", 16_475), ("Zebra-OS64.dck", 65_536)]


def tap_files():
    return sorted([n for n, s in GAMES if s is not None and n[-4:].lower() in (".tap", ".dck")],
                  key=str.lower)


def cat(t):
    folder(t, GAMES)
    t.TSP = types.SimpleNamespace(cur_path="/sd/TAP", f_name="", offset_tbl=[], tap_idx=0,
                                  ROM_VERSION="2.1", VERBOSE=False, LOG_LEVEL=2)
    t.files = tap_files()
    text, st = t.CATALOG_TEXT("")
    w = Wire(t)
    t.SEND_MSG2(t.CAT_COLOUR(text), 1, False, True)
    s = Screen()
    s.print_bytes(w.first_page(), expand=False)
    s.report("0 OK, 0:1")
    save(s, "cat")


def info(t):
    t.SD_PROBE = lambda *a: True
    t.os = types.SimpleNamespace(statvfs=lambda p: (4096, 4096, 352, 182))
    t.gc = types.SimpleNamespace(mem_free=lambda: 108_544, collect=lambda: None)
    t.files = tap_files()
    t.sd_space = (251_658_240, 233_472_000)
    t.public_fname = lambda n=0: "Manic.tap"
    t.public_path = lambda n=0: "/"
    t.isTapMounted = lambda: True
    t.getBoot = lambda: (2, 1)
    t.getDock = lambda: (2, 0)
    t.BUILD_VERSION = "3adf215 (main)"
    t.TSP = types.SimpleNamespace(FW_VERSION="2.1", ROM_VERSION="2.1", LOG_LEVEL=2,
                                  sd_present=True, append=False, VERBOSE=False,
                                  f_name="/sd/TAP/Manic.tap", tap_idx=0,
                                  offset_tbl=[[0, 19, " Y", "manic     "], [21, 1236, " N", "Program"]])
    real_sys = t.sys
    t.sys = types.SimpleNamespace(implementation=types.SimpleNamespace(version=(1, 29, 0)))
    w = Wire(t)
    try:
        t.GETINFO(bytearray(10), "D..tpi:info")
    finally:
        t.sys = real_sys
    s = Screen()
    s.print_bytes(w.first_page(), expand=True)
    s.report("0 OK, 0:1")
    save(s, "info")


def cd_menu(t):
    w = Wire(t, keys=[78])
    t.ListMenu(["DEMO", "GAMES", "TEST", "UTILS"], "Path:/", "  Directory Name",
               "  " + "-" * 30, "Change to dir", "Changing dir to: ", True)
    s = Screen()
    s.print_bytes(w.first_page(), expand=False)
    save(s, "cd-menu")


def tapdir(t):
    head = ("File:%-27s" % "/Manic.tap") + "Pointer at block: 02, Append:off"
    blocks = [[0, 19, " Y", "manic     "], [21, 1236, " N", "Program"],
              [1259, 19, " Y", "manicscr  "], [1280, 6914, " N", "Code block"],
              [8196, 19, " Y", "maniccode "], [8217, 29_683, " N", "Code block"]]
    rows = [(">" if i == 2 else " ") + "%02d %6s  %5s %s  %-10s" % (i, e[0], e[1], e[2], e[3])
            for i, e in enumerate(blocks)]
    text = head + "Blk  Start   Len  Hdr?  Desc.   " + "-" * 32 + "".join(rows)
    w = Wire(t)
    t.SEND_MSG2(t.TAPDIR_COLOUR(text, False), 1, True, True)
    s = Screen()
    s.print_bytes(w.first_page(), expand=True)
    s.report("0 OK, 0:1")
    save(s, "tapdir")


def several_match(t):
    t.TSP = types.SimpleNamespace(VERBOSE=False, ROM_VERSION="2.1")
    w = Wire(t)
    t.SEND_MSG("6 files match: ", '*.tap\rUse LOAD "tpi:" with its number.', t._3_F_Invalid_file, True)
    s = Screen()
    s.print_bytes(w.first_page(), expand=False)
    s.report("F Invalid file name, 0:1")
    save(s, "load-several-match")


def zx48_switch(t):
    t.TSP = types.SimpleNamespace(VERBOSE=False, ROM_VERSION="2.1", ZX_TAPE_COMPAT=False, zx48=False)
    w = Wire(t)
    t.ZX48(bytearray(10), "D..tpi:zx48")
    s = Screen()
    s.print_bytes(w.first_page(), expand=False)
    s.report("0 OK, 0:1")
    save(s, "zx48-switch")


def zx48_dir(t):
    """SAVE "tpi:dir" on the Spectrum (ZX v4 ROM): the same listing, in
    pieces, printed with PR-STRING, then ENTER and the report."""
    folder(t, GAMES)
    t.TSP = types.SimpleNamespace(cur_path="/sd/TAP", f_name="", offset_tbl=[], tap_idx=0,
                                  ROM_VERSION="2.1", VERBOSE=False, LOG_LEVEL=2)
    t.files = tap_files()
    text, st = t.CATALOG_TEXT("")
    s = Screen()
    s.print_bytes(t.CAT_COLOUR(text).encode() + b"\r", expand=False)
    s.report("0 OK, 0:1")
    save(s, "zx48-dir")


def main():
    t = firmware()
    for fn in (cat, info, cd_menu, tapdir, several_match, zx48_switch, zx48_dir):
        fn(t)


if __name__ == "__main__":
    main()
