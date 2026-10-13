#!/usr/bin/env python3
"""The v3 card's SP0256-AL2 (src/tsbus/sp0256.c), on the host.

Compiles sp0256.c (MAME's core, ported by tools/sp0256-port.py, and the AL2
ROM) with sp0256_shim.c into a shared library and drives it through ctypes.
The references were made with MAME's own C++ (sp0256.cpp, unchanged, around
a stand-in device class; 2026-10-12): the port must give the same samples,
bit for bit, for every allophone and for two sentences.

Needs a C compiler (cc). Run:  python3 src/test/sp0256_hosttest.py
"""

import ctypes
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TSBUS = os.path.normpath(os.path.join(HERE, "..", "tsbus"))

# MAME's samples: each allophone 0-63 spoken alone, one after another.
ALL64_SHA256 = "6a8e59129313bd2d894f64910e32dd8ec5b922eee1309a51c34aaede08d03c9c"
ALL64_LENS = [131, 326, 521, 1041, 2081, 3046, 1850, 645, 839, 1552, 1087, 1843, 553, 1033, 1386, 645,
              1936, 841, 1474, 1846, 2124, 554, 739, 829, 739, 1386, 921, 963, 462, 1345, 829, 1843,
              2673, 823, 1211, 1383, 823, 2052, 1414, 923, 1153, 1429, 1227, 1591, 2120, 923, 1567, 2589,
              1552, 1016, 1544, 1205, 2218, 1846, 1934, 705, 1478, 1358, 2493, 2125, 2584, 795, 1475, 603]
# ... and two sentences, as the text rules give them (allophone numbers).
SENTENCES = [
    ("Hello. I am your Timex Sinclair two thousand and sixty eight.",
     [27, 7, 45, 53, 4, 6, 1, 26, 16, 1, 25, 58, 1, 13, 6, 16, 7, 41, 55, 1, 55, 12, 44, 41, 45, 47, 1, 13,
      31, 1, 29, 32, 43, 15, 11, 21, 1, 26, 11, 21, 1, 55, 12, 41, 55, 17, 19, 1, 20, 17, 4],
     55899, "d77d999879678cd05644989e568bf44ec384c21fdf432c681220eee2fab1edbf"),
    ("Press any key to continue.",
     [9, 39, 7, 55, 1, 7, 11, 19, 1, 42, 19, 1, 13, 31, 1, 8, 24, 11, 13, 12, 11, 49, 22, 4],
     24258, "d543275f17a474ccae5edfd2b9477e39b9141fec1987e514783ba43bdd3e744c"),
]

FAILS = []


def check(ok, what):
    print(("  ok   " if ok else "  FAIL ") + what)
    if not ok:
        FAILS.append(what)


def build():
    d = tempfile.mkdtemp(prefix="sp0256.")
    lib = os.path.join(d, "sp0256.so")
    subprocess.run(["cc", "-shared", "-fPIC", "-O1", "-Wall", "-Werror", "-Wno-unused-function", "-I", TSBUS,
                    os.path.join(TSBUS, "sp0256.c"), os.path.join(HERE, "sp0256_shim.c"),
                    "-o", lib], check=True)
    return d, ctypes.CDLL(lib)


def main():
    d, c = build()
    try:
        c.shim_say.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.c_int, ctypes.POINTER(ctypes.c_int16), ctypes.c_int]
        c.shim_rom.restype = ctypes.POINTER(ctypes.c_uint8)
        buf = (ctypes.c_int16 * 400000)()

        def say(al):
            arr = (ctypes.c_int * len(al))(*al)
            n = c.shim_say(arr, len(al), buf, len(buf))
            return bytes(memoryview(buf).cast("B")[:n * 2])

        print("the ROM")
        rom = bytes(c.shim_rom()[i] for i in range(2048))
        check(hashlib.sha1(rom).hexdigest() == "e60fcb5fa16ff3f3b69d36c7a6e955744d3feafc",
              "sp0256_al2 is the AL2 ROM in MAME's bit order (SHA-1 e60fcb5f...)")

        print("every allophone, against MAME's samples")
        h = hashlib.sha256()
        lens = []
        for i in range(64):
            b = say([i])
            h.update(b)
            lens.append(len(b) // 2)
        check(lens == ALL64_LENS, "the 64 lengths match (%d samples, %.1f s)" % (sum(lens), sum(lens) / 10000))
        check(h.hexdigest() == ALL64_SHA256, "the 64 allophones' samples match, bit for bit")

        print("sentences")
        for text, al, n, sha in SENTENCES:
            b = say(al)
            check(len(b) // 2 == n and hashlib.sha256(b).hexdigest() == sha,
                  "%r: %d samples, bit for bit" % (text, n))

        print("the chip's interface")
        c.shim_init()
        check(c.shim_lrq() == 1 and c.shim_idle() == 1, "at reset: LRQ ready, idle")
        check(c.shim_sample() == 0, "idle: silence")
        check(c.shim_ald(27) == 1 and c.shim_lrq() == 0 and c.shim_idle() == 0, "ALD takes an allophone; LRQ busy")
        check(c.shim_ald(7) == 0, "a second ALD before LRQ comes back is dropped, as on the chip")
        k = 0
        while not c.shim_lrq() and k < 100:
            c.shim_sample()
            k += 1
        check(c.shim_lrq() == 1 and k < 5, "the chip takes the allophone at once and LRQ comes back (%d samples)" % k)
        # Idle is watched every sample, as shim_say does: once halted, MAME's
        # microsequencer sets a repeat of 1 on each call, so it reads idle
        # on alternate samples.
        peak = 0
        spoken = 0
        while not c.shim_idle() and spoken < 3000:
            peak = max(peak, abs(c.shim_sample()))
            spoken += 1
        check(0 < peak <= 8191 and c.shim_idle() == 1 and abs(spoken + k - ALL64_LENS[27]) <= 2,
              "HH1 spoken (peak %d, in 14 bits; %d samples, as alone), then idle" % (peak, spoken + k))
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
