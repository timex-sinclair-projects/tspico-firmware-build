"""Assemble the examples and put them on one TAP as CODE blocks at 60000.

Run:  python3 make_tap.py        (needs sjasmplus on the PATH)
"""
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
NAMES = ["picocmd", "loadfile", "logline", "countdir", "fact", "bios"]


def block(data):
    x = 0
    for b in data:
        x ^= b
    data = data + bytes([x])
    return len(data).to_bytes(2, "little") + data


tap = bytearray()
for n in NAMES:
    subprocess.run(["sjasmplus", "--nologo", "--msg=war", "--raw=%s.bin" % n, "%s.asm" % n],
                   cwd=HERE, check=True)
    code = open(os.path.join(HERE, n + ".bin"), "rb").read()
    hdr = bytes([0, 3]) + n.ljust(10).encode() + len(code).to_bytes(2, "little") \
        + (60000).to_bytes(2, "little") + (32768).to_bytes(2, "little")
    tap += block(hdr) + block(b"\xff" + code)
open(os.path.join(HERE, "picoex.tap"), "wb").write(tap)
print("picoex.tap: %d bytes, %s" % (len(tap), ", ".join(NAMES)))
