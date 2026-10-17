#!/usr/bin/env python3
"""Build the TS-Pico 2.3 tour and its demo card (promo/demo/README.md).

    python3 promo/demo/build.py [--zmakebas PATH]

Writes promo/demo/TOUR.TAP (from tour.bas) and promo/demo/card/TAP/:
tour.tap (the same program), art.tap (a picture and eight graphics, made
here), multi.tap and hello.tap (the repo's demo programs, basic/SD/TAP/demo),
and library/ (26 one-line programs, for a listing longer than the screen).
The help folder is not copied: the README says to copy the repo's
"SD card/help" next to TAP.

Without --zmakebas, the vendored tools/zmakebas is compiled into a temporary
folder (never in the repo).
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
CARD = os.path.join(HERE, "card", "TAP")
ROM = os.path.join(REPO, "src", "rom", "TSPICO-23.ROM")
DEMO_BAS = os.path.join(REPO, "basic", "SD", "TAP", "demo")

NATO = ("alpha bravo charlie delta echo foxtrot golf hotel india juliett kilo lima mike "
        "november oscar papa quebec romeo sierra tango uniform victor whiskey xray yankee zulu").split()


def zmakebas_binary(given):
    if given:
        return given
    tmp = tempfile.mkdtemp(prefix="zmakebas-")
    for f in ("Makefile", "zmakebas.c"):
        shutil.copy(os.path.join(REPO, "tools", "zmakebas", f), tmp)
    subprocess.run(["make", "-C", tmp, "zmakebas"], check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)
    return os.path.join(tmp, "zmakebas")


def zmake(zmk, src):
    """One or more programs from a .bas (a `#! zmakebas` line starts each), as a TAP."""
    segs, cur = [], None
    for line in open(src):
        if line.startswith("#!") and "zmakebas" in line:
            cur = [line]
            segs.append(cur)
        elif cur is not None:
            cur.append(line)
    out = b""
    with tempfile.TemporaryDirectory() as tmp:
        for i, seg in enumerate(segs):
            opts = seg[0].split("zmakebas", 1)[1].split()
            p = os.path.join(tmp, "%d.bas" % i)
            open(p, "w").writelines(seg)
            out += subprocess.run([zmk, *opts, "-o", "-", p], check=True,
                                  stdout=subprocess.PIPE).stdout
    return out


def block(flag, body):
    data = bytes([flag]) + bytes(body)
    x = 0
    for b in data:
        x ^= b
    return len(data + b"x").to_bytes(2, "little") + data + bytes([x])


def header(kind, name, length, p1, p2=0x8000):
    return block(0, bytes([kind]) + name.encode().ljust(10)[:10] + length.to_bytes(2, "little")
                 + p1.to_bytes(2, "little") + p2.to_bytes(2, "little"))


def picture():
    """art.tap's SCREEN$: TS-Pico and 2.3 in big ROM letters, on blue,
    with the four stripes."""
    font = open(ROM, "rb").read()[0x3D00:0x4000]
    px = [[0] * 256 for _ in range(192)]
    attr = [[0x0F] * 32 for _ in range(24)]                   # blue paper, white ink

    def text(s, x, y, k):
        for i, ch in enumerate(s):
            g = font[(ord(ch) - 32) * 8:(ord(ch) - 32) * 8 + 8]
            for r in range(8):
                for c in range(8):
                    if g[r] & (0x80 >> c):
                        for yy in range(k):
                            for xx in range(k):
                                px[y + r * k + yy][x + (i * 8 + c) * k + xx] = 1

    text("TS-Pico", 44, 12, 3)
    text("2.3", 72, 44, 5)
    for r in range(5, 11):
        for c in range(8, 24):
            attr[r][c] = 0x0E                                   # yellow ink on blue
    text("from art.tap", 8, 120, 1)
    text("loaded with", 8, 136, 1)
    text('LOAD "" SCREEN$', 8, 144, 1)
    for i in range(8):                                          # the stripes, bottom right
        for j, color in enumerate((2, 6, 4, 5)):
            for c in (23 - i + 2 * j, 24 - i + 2 * j):
                attr[16 + i][c] = color << 3
    scr = bytearray(6912)
    for y in range(192):
        base = ((y & 0xC0) << 5) | ((y & 0x07) << 8) | ((y & 0x38) << 2)
        for cx in range(32):
            b = 0
            for bit in range(8):
                b = (b << 1) | px[y][cx * 8 + bit]
            scr[base + cx] = b
    for r in range(24):
        for c in range(32):
            scr[6144 + r * 32 + c] = attr[r][c]
    return bytes(scr)


SPRITES = """
..XXXXXXXXXX....  .XXXXXXXXXXXXXX.
.X.X.X.X.X.XX...  X..............X
.X.X.X.X.X.X.X..  X.XXXXXXXXXXXX.X
.X............X.  X.X..........X.X
.X............X.  X.X.XX....XX.X.X
.X..XXXXXXXX..X.  X.X.XX....XX.X.X
.X..X......X..X.  X.X..........X.X
.X..X..SD..X..X.  X.XXXXXXXXXXXX.X
.X..X......X..X.  X..............X
.X..X......X..X.  X..............X
.X..XXXXXXXX..X.  X....XXXXXX....X
.X............X.  X...X......X...X
.X............X.  X..X........X..X
.X............X.  X.X..........X.X
.XXXXXXXXXXXXXX.  XXXXXXXXXXXXXXXX
................  ................
"""


def sprites():
    """64 bytes: UDGs A-D an SD card (2x2), E-H a cassette (2x2)."""
    rows = [l.split() for l in SPRITES.strip("\n").splitlines()]
    out = bytearray()
    for pic in (0, 1):
        for half_r, half_c in ((0, 0), (0, 8), (8, 0), (8, 8)):
            for r in range(8):
                bits = rows[half_r + r][pic][half_c:half_c + 8]
                out.append(int("".join("1" if ch not in "." else "0" for ch in bits), 2))
    return bytes(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--zmakebas", help="a built zmakebas (default: build the vendored one)")
    zmk = zmakebas_binary(ap.parse_args().zmakebas)

    tour = zmake(zmk, os.path.join(HERE, "tour.bas"))
    open(os.path.join(HERE, "TOUR.TAP"), "wb").write(tour)

    if os.path.isdir(CARD):
        shutil.rmtree(CARD)
    os.makedirs(os.path.join(CARD, "library"))
    open(os.path.join(CARD, "tour.tap"), "wb").write(tour)
    open(os.path.join(CARD, "multi.tap"), "wb").write(zmake(zmk, os.path.join(DEMO_BAS, "multi.bas")))
    open(os.path.join(CARD, "hello.tap"), "wb").write(zmake(zmk, os.path.join(DEMO_BAS, "hello.bas")))
    spr = sprites()
    open(os.path.join(CARD, "art.tap"), "wb").write(
        header(3, "sprites", len(spr), 0xFF58) + block(0xFF, spr)
        + header(3, "picture", 6912, 0x4000) + block(0xFF, picture()))
    for name in NATO:
        with tempfile.NamedTemporaryFile("w", suffix=".bas", delete=False) as f:
            f.write('10 PRINT "%s"\n' % name)
        tap = subprocess.run([zmk, "-n", name, "-o", "-", f.name], check=True,
                             stdout=subprocess.PIPE).stdout
        os.unlink(f.name)
        open(os.path.join(CARD, "library", name + ".tap"), "wb").write(tap)
    print("wrote %s and %s" % (os.path.relpath(os.path.join(HERE, "TOUR.TAP"), REPO),
                               os.path.relpath(CARD, REPO)))


if __name__ == "__main__":
    sys.exit(main())
