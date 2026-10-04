#!/usr/bin/env python3
"""Screen captures for the user manual, from the emulator: the real ROM
printing the real firmware's replies (tools/emu, issue #35). Writes
docs/manual/images/<name>.png, 2x, the 2068's whole display with border.

    python3 tools/emu/manual_screens.py

The Spectrum-side picture (zx48-dir.png) still comes from
tools/render_screens.py: the emulator has no ZX v4 ROM in the DOCK bank.
"""

import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import session as S                                           # noqa: E402
from PIL import Image                                         # noqa: E402

OUT = os.path.join(S.REPO, "docs", "manual", "images")
SEED = "/tmp/tspico-manual-seed"
BMP = "/tmp/tspico-shot.bmp"


def card():
    """The pretend card the manual's pictures show."""
    if os.path.isdir(SEED):
        shutil.rmtree(SEED)
    tap = os.path.join(SEED, "TAP")
    for d in ("DEMO", "GAMES", "TEST", "UTILS"):
        os.makedirs(os.path.join(tap, d))
    shutil.copytree(os.path.join(S.REPO, "SD card", "help"), os.path.join(SEED, "help"))
    for name, size in (("3DTanx.tap", 9_216), ("Chess.tap", 21_514), ("{game}.tap", 6_970),
                       ("Frogger.tap", 41_377), ("jet~1.tap", 17_830), ("Pssst.tap", 16_475),
                       ("Zebra-OS64.dck", 65_536)):
        with open(os.path.join(tap, name), "wb") as f:
            f.write(bytes(size))
    # Manic.tap: real blocks, for CAT "" -- a loader, a screen, the code.
    prog = S.basic_tap("manic", [(10, bytes([S.LOAD]) + b'""' + bytes([0xAA])),   # LOAD ""SCREEN$
                                 (20, bytes([S.LOAD]) + b'""' + bytes([S.CODE]))])
    scr = S.tap_block(0x00, bytes([3]) + b"manicscr  " + bytes([0x00, 0x1B, 0x00, 0x40, 0, 0x80])) \
        + S.tap_block(0xFF, bytes(6912))
    code = S.tap_block(0x00, bytes([3]) + b"maniccode " + bytes([0xF3, 0x73, 0x00, 0x80, 0, 0x80])) \
        + S.tap_block(0xFF, bytes(29683))
    with open(os.path.join(tap, "Manic.tap"), "wb") as f:
        f.write(prog + scr + code)


def shot(s, name):
    s.screenshot(BMP)
    time.sleep(0.5)
    im = Image.open(BMP).convert("RGB")
    im = im.resize((im.width * 2, im.height * 2), Image.NEAREST)
    im.save(os.path.join(OUT, name + ".png"), optimize=True)
    print("wrote docs/manual/images/%s.png" % name, flush=True)


def fresh_screen(s):
    """CLS, so each picture starts on a clean screen."""
    s.run(0xFB)                                               # CLS


def main():
    os.environ["TSPICO_BRANCH"] = "main"                      # tpi:info's Build line, as users see it
    card()
    s = S.Session(sd=SEED)
    try:
        fresh_screen(s)
        s.run(S.CAT)
        shot(s, "cat")

        fresh_screen(s)
        s.run(S.SAVE, '"tpi:cd"', until="quit?", timeout=30)
        shot(s, "cd-menu")
        s.cmd("send-keys-ascii 120 78")                        # N: quit the menu
        time.sleep(2)

        fresh_screen(s)
        s.run(S.LOAD, '"tpi:*.tap"')
        shot(s, "load-several-match")

        s.run(S.LOAD, '"tpi:Manic.tap"')
        s.run(S.SAVE, '"tpi:ffw"')
        s.run(S.SAVE, '"tpi:ffw"')                             # the pointer at block 02, as the text says
        fresh_screen(s)
        s.run(S.CAT, '""')
        shot(s, "tapdir")

        fresh_screen(s)
        s.run(S.SAVE, '"tpi:info"')
        shot(s, "info")

        fresh_screen(s)
        s.run(S.SAVE, '"tpi:zx48"')
        shot(s, "zx48-switch")
    finally:
        s.close()


if __name__ == "__main__":
    main()
