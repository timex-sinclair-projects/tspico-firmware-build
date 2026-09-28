"""Host-side test for TS/native.py -- native SD files (SAVE / LOAD "f:name").

The +3DOS header (layout, checksum, round trip), SCREEN$ stored raw, reading
back what a file holds, and the TAP blocks a native file becomes for the
stock LOAD code. CPython, no Pico.

Run:  python3 src/test/native_hosttest.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from TS import native as N                                      # noqa: E402

results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg)


def xor(bs):
    x = 0
    for b in bs:
        x ^= b
    return x


def main():
    print("+3DOS header")
    h = N.plus3_header(N.T_PROGRAM, 1823, 10, 1500)
    check(len(h) == 128 and h[:8] == b"PLUS3DOS" and h[8] == 0x1A, "signature + soft EOF")
    check(h[9] == 1 and h[10] == 0, "issue 1, version 0")
    check(int.from_bytes(bytes(h[11:15]), "little") == 128 + 1823, "file length includes the header")
    check(h[15] == 0 and h[16:22] == bytes([0x1F, 0x07, 10, 0, 0xDC, 0x05]),
          "type, length, param1 (LINE), param2 (vars offset)")
    check(all(b == 0 for b in h[22:127]), "spare and reserved bytes zero")
    check(h[127] == sum(h[:127]) & 0xFF, "checksum of bytes 0-126")
    check(N.parse_plus3(h) == (0, 1823, 10, 1500), "parse round trip")
    bad = bytearray(h)
    bad[20] ^= 1
    check(N.parse_plus3(bad) is None, "bad checksum -> None")
    check(N.parse_plus3(b"NOTPLUS3" + bytes(120)) is None, "no signature -> None")
    check(N.parse_plus3(h[:100]) is None, "short -> None")

    print("SAVE -> file")
    data = bytes(range(256)) * 4
    out, kind = N.to_file(N.T_CODE, len(data), 32768, 32768, data)
    check(kind == "plus3" and len(out) == 128 + 1024 and out[128:] == data, "CODE: header + data")
    scr = bytes(6912)
    out, kind = N.to_file(N.T_CODE, 6912, 16384, 32768, scr)
    check(kind == "screen" and out == scr, "SCREEN$ (CODE 16384,6912): raw, no header")
    out, kind = N.to_file(N.T_CODE, 6912, 32768, 32768, scr)
    check(kind == "plus3", "6912 bytes elsewhere: still a +3DOS file")

    print("file -> what it holds")
    f = bytes(N.plus3_header(N.T_CHARARR, 20, 0xC100, 32768)) + bytes(20)
    check(N.describe(f[:128], len(f)) == (2, 20, 0xC100, 32768, 128), "+3DOS array")
    check(N.describe(f[:128], len(f) - 1) is None, "truncated +3DOS file -> None")
    check(N.describe(bytes(128), 6912) == (3, 6912, 16384, 32768, 0), "raw 6912 bytes: a screen")
    check(N.describe(bytes(128), 5000) is None, "raw, not a screen: None (caller decides)")
    check(N.headerless_code(5000, 40000) == (3, 5000, 40000, 32768, 0), "headerless CODE at an address")

    print("file -> TAP blocks")
    tap = N.as_tap(N.T_PROGRAM, 3, 10, 3, b"\x00\x0a\x0d", "games/advent.bas")
    check(tap[0] | tap[1] << 8 == 19 and tap[2] == 0x00, "header block: 19 bytes, flag 00")
    hdr = tap[3:20]
    check(hdr[0] == 0 and hdr[1:11] == b"games/advent.bas"[:10], "header type and the name as given")
    check(N.fields_from_tape_header(hdr) == (0, 3, 10, 3), "header fields")
    check(tap[20] == xor(tap[2:20]), "header checksum")
    d = tap[21:]
    check(d[0] | d[1] << 8 == 5 and d[2] == 0xFF and d[3:6] == b"\x00\x0a\x0d" and d[6] == xor(d[2:6]),
          "data block: flag FF, payload, checksum")
    check(N.tape_name("/sd/TAP/games/advent.bas") == "advent", "tape name: base name, no extension")
    check(N.tape_name("verylongprogramname.bas") == "verylongpr", "tape name: cut to 10")
    th = N.tape_header(0, N.tape_name("x/advent.bas"), 1, 2, 3)
    check(th[1:11] == b"advent    ", "tape header name space-padded")

    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
