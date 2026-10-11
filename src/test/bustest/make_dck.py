#!/usr/bin/env python3
"""The bus-integrity test cartridge for bustest.asm (issue: Sinistar on v3).

Every byte of the 64K dock is f(addr) = lo ^ hi ^ 5Ah, so the Z80 can check
any read without a copy. Each 8K chunk c has a stub at c*2000h + 1000h:
LD A,D0h+c / RET, so a JP into it right after a bank switch shows which bank
answered (bustest.asm puts LD A,50h+c / RET in RAM at the same places, and
fills RAM with ~f). The dock's first and 8000h bytes are 00h, so it never
looks like an LROS or AROS cartridge.

    python3 make_dck.py OUTDIR [DOCKCODE]
        -> bustest.dck (for the loader, either board), F08.bin and F09.bin
           (the v3 card's flash slot files for slots 8-9). With DOCKCODE
           (bustestd_dock.bin, bustest.asm built with -DDOCKRUN), the test's
           own code goes in at 9100h and the files are bustestd.dck and
           D08.bin / D09.bin.
"""
import os
import sys


DOCK_CODE = 0x9100      # bustest.asm's org with DOCKRUN: chunk 4, past its stub


def image(code=b""):
    d = bytearray((a & 0xFF) ^ (a >> 8) ^ 0x5A for a in range(0x10000))
    for c in range(8):
        s = c * 0x2000 + 0x1000
        d[s:s + 3] = bytes([0x3E, 0xD0 + c, 0xC9])
    d[0x0000] = 0x00
    d[0x8000] = 0x00
    assert DOCK_CODE + len(code) <= 0xA000
    d[DOCK_CODE:DOCK_CODE + len(code)] = code
    return bytes(d)


def main(argv):
    out = argv[1] if len(argv) > 1 else "."
    code = open(argv[2], "rb").read() if len(argv) > 2 else b""
    d = image(code)
    name, slot = ("bustestd", "D") if code else ("bustest", "F")
    with open(os.path.join(out, name + ".dck"), "wb") as f:
        f.write(bytes([0x00] + [0x02] * 8) + d)    # DOCK bank, eight ROM chunks
    with open(os.path.join(out, slot + "08.bin"), "wb") as f:
        f.write(d[:0x8000])
    with open(os.path.join(out, slot + "09.bin"), "wb") as f:
        f.write(d[0x8000:])
    print("%s.dck, %s08.bin, %s09.bin in %s" % (name, slot, slot, out))


if __name__ == "__main__":
    main(sys.argv)
