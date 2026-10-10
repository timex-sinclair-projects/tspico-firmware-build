#!/usr/bin/env python3
"""LOAD and SAVE through the SD card, checked byte for byte (v3 port step 4.4).

    python3 src/test/sd_roundtrip.py make v3t.tap      # the test tape
    python3 tools/pico-serial.py break
    python3 tools/pico-serial.py put --sd v3t.tap /TAP/v3t.tap
    python3 tools/pico-serial.py softreset

On the 2068:  LOAD "v3t"   (runs: a striped SCREEN$, then 16K of CODE)
              SAVE "v3b" LINE 10
              SAVE "v3s" SCREEN$
              SAVE "v3c" CODE 32768,16384
              VERIFY "v3c" CODE

Then `break`, `get --sd /TAP/v3b.tap v3b.tap` (and v3s, v3c), `softreset`, and

    python3 src/test/sd_roundtrip.py check v3t.tap v3b.tap v3s.tap v3c.tap

The BASIC and CODE blocks must match exactly. The SCREEN$ is compared at
every scroll of 0-3 character rows: typing the SAVEs scrolls the 2068's
screen, so a good transfer matches the original moved up a row or two.
Works on either board: nothing here is v3-specific.
"""

import random
import sys


def blk(flag, data):
    b = bytes([flag]) + data
    x = 0
    for c in b:
        x ^= c
    b += bytes([x])
    return len(b).to_bytes(2, "little") + b


def hdr(typ, name, length, p1, p2):
    return blk(0, bytes([typ]) + name.ljust(10).encode() + length.to_bytes(2, "little")
               + p1.to_bytes(2, "little") + p2.to_bytes(2, "little"))


def line(n, body):
    body += b"\r"
    return n.to_bytes(2, "big") + len(body).to_bytes(2, "little") + body


def content():
    LOAD, SCREEN, CODE = 0xEF, 0xAA, 0xAF
    prog = line(10, bytes([LOAD]) + b'""' + bytes([SCREEN])) + line(20, bytes([LOAD]) + b'""' + bytes([CODE]))
    scr = bytearray(6912)                   # a pattern on rows 0-21, the lower screen blank
    for y in range(176):
        third, row, ln = y // 64, (y // 8) % 8, y % 8
        for col in range(32):
            scr[third * 2048 + ln * 256 + row * 32 + col] = (y * 7 + col * 13) & 0xFF
    for i in range(768):
        r = i // 32
        scr[6144 + i] = 0x38 if r >= 22 else ((r * 8 + i % 8) & 0x3F)
    rnd = random.Random(2068)
    code = bytes(rnd.getrandbits(8) for _ in range(16384))
    return prog, bytes(scr), code


def blocks(path):
    b = open(path, "rb").read()
    i, out = 0, []
    while i < len(b):
        n = b[i] | b[i + 1] << 8
        out.append(b[i + 2:i + 2 + n])
        i += 2 + n
    return out


def payload(path):
    """The data block of a one-file TAP, its checksum checked."""
    bl = blocks(path)
    d = bl[1]
    x = 0
    for c in d[:-1]:
        x ^= c
    return d[1:-1], x == d[-1]


def char_row(scr, r):
    return b"".join(scr[(r // 8) * 2048 + l * 256 + (r % 8) * 32:][:32] for l in range(8))


def main(argv):
    prog, scr, code = content()
    if len(argv) == 3 and argv[1] == "make":
        out = hdr(0, "v3t", len(prog), 10, len(prog)) + blk(0xFF, prog)
        out += hdr(3, "v3s", 6912, 16384, 32768) + blk(0xFF, scr)
        out += hdr(3, "v3c", 16384, 32768, 32768) + blk(0xFF, code)
        open(argv[2], "wb").write(out)
        print("%s: %d bytes" % (argv[2], len(out)))
        return 0
    if len(argv) == 6 and argv[1] == "check":
        ok = True
        for name, path, want in (("BASIC", argv[3], prog), ("CODE", argv[5], code)):
            got, ck = payload(path)
            good = ck and got == want
            ok &= good
            print("%-7s %s (%d bytes, checksum %s)" % (name, "same" if good else "DIFFERENT", len(got), "ok" if ck else "BAD"))
        got, ck = payload(argv[4])
        scroll = [k for k in range(4) if all(char_row(got, r) == char_row(scr, r + k) for r in range(22 - k))
                  and got[6144:6144 + (22 - k) * 32] == scr[6144 + k * 32:6144 + 22 * 32]]
        good = ck and len(got) == 6912 and bool(scroll)
        ok &= good
        print("SCREEN$ %s" % ("same, scrolled %d row(s)" % scroll[0] if good else "DIFFERENT"))
        print("PASS" if ok else "FAIL")
        return 0 if ok else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
