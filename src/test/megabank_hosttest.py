#!/usr/bin/env python3
"""The v3 card's shadow of the TS-2068 Megabank's owner table
(src/tsbus/megabank.c), on the host.

Compiles megabank.c and drives mb_out/mb_clear through ctypes as core 1's
I/O snoop does: OUT (FDh) selects a register, OUT (FCh) writes it, and a
chunk whose owner (OWN0-OWN7, registers 00h-07h) is a bank 1-253 is in
`owned`, which tsbus.c's chunk table yields. Checks the decode, the owner
range, that only owner changes rewrite the table, and mb_clear.

Needs a C compiler (cc). Run:  python3 src/test/megabank_hosttest.py
"""

import ctypes
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TSBUS = os.path.normpath(os.path.join(HERE, "..", "tsbus"))

FAILS = []


def check(ok, what):
    print(("  ok   " if ok else "  FAIL ") + what)
    if not ok:
        FAILS.append(what)


class Shadow(ctypes.Structure):
    _fields_ = [("select", ctypes.c_uint8), ("own", ctypes.c_uint8 * 8), ("owned", ctypes.c_uint8)]


def build():
    d = tempfile.mkdtemp(prefix="megabank.")
    lib = os.path.join(d, "megabank.so")
    subprocess.run(["cc", "-shared", "-fPIC", "-O1", "-Wall", "-Werror", "-I", TSBUS,
                    os.path.join(TSBUS, "megabank.c"), "-o", lib], check=True)
    so = ctypes.CDLL(lib)
    so.mb_out.argtypes = [ctypes.POINTER(Shadow), ctypes.c_uint, ctypes.c_uint]
    so.mb_out.restype = ctypes.c_int
    so.mb_clear.argtypes = [ctypes.POINTER(Shadow)]
    return d, so


def main():
    d, so = build()
    try:
        s = Shadow()
        so.mb_clear(ctypes.byref(s))

        def out(port, data):
            return so.mb_out(ctypes.byref(s), port, data)

        def own(reg, bank):            # select, then write: returns the second OUT's result
            out(0xFD, reg)
            return out(0xFC, bank)

        check(s.owned == 0 and list(s.own) == [0] * 8, "mb_clear: nothing owned")

        check(out(0xFD, 0x04) == 0 and s.select == 4, "OUT (FDh) selects, changes nothing")
        check(out(0xFC, 5) == 1 and s.owned == 0x10 and s.own[4] == 5,
              "OWN4 = 5: chunk 4 owned, the table needs rewriting")
        check(out(0xFC, 6) == 0 and s.owned == 0x10 and s.own[4] == 6,
              "OWN4 = 6: still owned, no rewrite (no auto-increment: OWN4 again)")
        check(out(0xFC, 0) == 1 and s.owned == 0, "OWN4 = 0: given back, rewrite")

        for bank, owned in [(1, True), (64, True), (193, True), (253, True),
                            (0, False), (254, False), (255, False)]:
            own(4, 0)
            own(4, bank)
            check(bool(s.owned & 0x10) == owned,
                  "owner %d (%02Xh): %s" % (bank, bank, "owned" if owned else "none"))
        own(4, 0)

        own(0, 9)
        own(7, 9)
        check(s.owned == 0x81, "OWN0 and OWN7: chunks 0 and 7 (the bits follow the chunks)")
        own(0, 0)
        own(7, 0)

        for reg in (0x08, 0x0C, 0x0F, 0x10, 0x12, 0x14, 0x77, 0xFF):
            check(own(reg, 5) == 0 and s.owned == 0 and list(s.own) == [0] * 8,
                  "register %02Xh is not an owner: ignored" % reg)

        out(0xFD, 0x02)
        for port in (0xF4, 0xFF, 0xFE, 0x0E, 0x0F, 0x73, 0x7C, 0xFB):
            check(out(port, 5) == 0 and s.owned == 0 and s.select == 2,
                  "OUT (%02Xh) is not the board's" % port)

        own(2, 5)
        own(5, 70)
        so.mb_clear(ctypes.byref(s))
        check(s.owned == 0 and list(s.own) == [0] * 8 and s.select == 0,
              "mb_clear after owners: nothing owned (reset, power-up)")
    finally:
        shutil.rmtree(d)

    print()
    if FAILS:
        print("%d FAILED" % len(FAILS))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
