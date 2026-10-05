#!/usr/bin/env python3
"""Rebuild the damaged-TAP test set in this folder (see README.md).

    python3 src/test/fixtures/damaged-taps/make_damaged_taps.py
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))


def tap_block(flag, body, bad_crc=False):
    """One TAP block: length, flag, body, XOR checksum (spoiled if bad_crc)."""
    data = bytes([flag]) + bytes(body)
    x = 0
    for b in data:
        x ^= b
    data += bytes([x ^ 0x55 if bad_crc else x])
    return bytes([len(data) & 0xFF, len(data) >> 8]) + data


def header(htype, name, length, param2=None):
    """A 17-byte tape header: param 1 = 8000h (no autorun), param 2 the length
    unless given."""
    p2 = length if param2 is None else param2
    return bytes([htype]) + name.encode().ljust(10)[:10] + bytes(
        [length & 0xFF, length >> 8, 0x00, 0x80, p2 & 0xFF, p2 >> 8])


def basic_tap(name, line):
    """A one-line BASIC program: 10 <line>."""
    prog = bytes([0, 10, (len(line) + 1) & 0xFF, (len(line) + 1) >> 8]) + line + b"\x0d"
    return tap_block(0x00, header(0, name, len(prog))) + tap_block(0xFF, prog)


PROG = basic_tap("prog", b'\xf5"hi"')                  # 10 PRINT "hi"

TAPS = {
    # The only block: header flag, 7625 bytes, bad checksum.
    "big.tap": tap_block(0x00, bytes(range(256)) * 29 + bytes(201), bad_crc=True),
    # Starts 00 00 (a zero-length block), then a good program.
    "zero.tap": b"\x00\x00" + PROG,
    # A good header, then a data block with a bad checksum.
    "bad.tap": tap_block(0x00, header(0, "prog", 4)) + tap_block(0xFF, b"\x01\x02\x03\x04", bad_crc=True),
    # A 17-byte header with a bad checksum, then a good program.
    "hcrc.tap": tap_block(0x00, header(3, "x", 4, 0), bad_crc=True) + PROG,
    # Two damaged header-flag blocks (6 bytes, not 19), then a good program.
    "multi.tap": tap_block(0x00, b"\x01\x02\x03\x04", bad_crc=True)
                 + tap_block(0x00, bytes(4), bad_crc=True) + PROG,
    # A CODE header for 4 bytes; the data block holds 10.
    "dlong.tap": tap_block(0x00, header(3, "c", 4, 0)) + tap_block(0xFF, bytes(10)),
    # A program, two stray data blocks, then the program "two".
    "hdd.tap": PROG + tap_block(0xFF, b"xx") + tap_block(0xFF, b"yy") + basic_tap("two", b'\xf5"two"'),
}

if __name__ == "__main__":
    for name, data in TAPS.items():
        with open(os.path.join(HERE, name), "wb") as f:
            f.write(data)
        print("%-10s %5d bytes" % (name, len(data)))
