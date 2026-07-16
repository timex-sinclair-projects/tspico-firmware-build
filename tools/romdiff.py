#!/usr/bin/env python3
"""Regenerate the TS-PICO ROM analysis resources under docs/rom-analysis/.

Compares the TS-PICO HOME/EXROM images against stock TS2068 ROMs and against
each other, emitting hunk lists as text and JSON.

Usage:
    python3 tools/romdiff.py                 # print report to stdout
    python3 tools/romdiff.py --json OUT.json # also write machine-readable hunks

ROM images are expected in ROMs/ (see docs/rom-analysis/README.md for the
provenance and checksums of each image).
"""

import argparse
import hashlib
import json
import zlib
import pathlib
import sys

ROMDIR = pathlib.Path(__file__).resolve().parent.parent / "ROMs"

IMAGES = {
    "tspico-11-home": "TSPICO-11-home",
    "tspico-15w-home": "TSPICO-15w-home",
    "tspico-11-exrom": "TSPICO-11-exrom",
    "tspico-15w-exrom": "TSPICO-15w-exrom",
    # Genuine TS2068 baseline. See KNOWN_BAD below before substituting anything.
    "genuine-home": "GENUINE-2068-home.bin",
    "genuine-exrom": "GENUINE-2068-exrom.bin",
}

# Expected CRC32s -- checked at run time so a swapped image cannot go unnoticed.
EXPECT_CRC = {
    "genuine-home": 0xbf44ec3f,
    "genuine-exrom": 0xae16233a,
    "tspico-11-home": 0xe8714bed,
    "tspico-15w-home": 0xe8714bed,
    "tspico-11-exrom": 0x268649f6,
    "tspico-15w-exrom": 0xcacf18c5,
}

# Baselines that look stock but are not. `2068Home.BIN` / `2068Exrom.BIN` in the
# TS2068 Ref Library are the obvious images to reach for and the obvious mistake
# to make -- they are a modified, partly bit-rotted personal EPROM dump ("W.J."),
# and diffing against them fabricates ~150 bytes of phantom "TS-PICO changes".
# The images are deliberately not shipped here; this map exists so that dropping
# one in gets named rather than silently believed.
# See docs/rom-analysis/DIFF_HOME_vs_STOCK.md#baseline.
KNOWN_BAD = {
    0x7d411fe9: "the W.J. modified HOME dump (TS2068 Ref Library/2068 ROMS/2068Home.BIN)",
    0x526f5676: "the W.J. modified EXROM dump (TS2068 Ref Library/2068 ROMS/2068Exrom.BIN)",
}

# Pairs to diff: (label, left, right, note)
COMPARISONS = [
    ("HOME: genuine -> TS-PICO", "genuine-home", "tspico-11-home",
     "TSPICO-11-home and TSPICO-15w-home are byte-identical. Expect 242 B / 10 hunks."),
    ("EXROM chunk0: genuine -> TS-PICO v1.1", "genuine-exrom", "tspico-11-exrom",
     "Genuine 8K vs the low 8K only; chunk 1 (0x2000+) is all-new. Expect 2326 B / 36 hunks."),
    ("EXROM: TS-PICO v1.1 -> v1.5w", "tspico-11-exrom", "tspico-15w-exrom",
     "The shipping-vs-next delta. Expect 15 B / 2 hunks."),
]

GAP = 8  # bytes of agreement that close a hunk


def load(name):
    path = ROMDIR / IMAGES[name]
    if not path.exists():
        sys.exit(f"missing ROM image: {path}\nSee docs/rom-analysis/README.md")
    return path.read_bytes()


def hunks(a, b, gap=GAP):
    """Group differing offsets into hunks, merging runs closer than `gap`."""
    n = min(len(a), len(b))
    out = []
    for i in range(n):
        if a[i] == b[i]:
            continue
        if out and i - out[-1][1] <= gap:
            out[-1][1] = i
        else:
            out.append([i, i])
    return [(s, e) for s, e in out]


def report(label, a, b, note, collect):
    hs = hunks(a, b)
    ndiff = sum(1 for i in range(min(len(a), len(b))) if a[i] != b[i])
    print(f"\n=== {label} ===")
    print(f"    {note}")
    print(f"    {len(hs)} hunks, {ndiff} bytes differ "
          f"(compared over {min(len(a), len(b))} bytes)")
    for s, e in hs:
        print(f"  {s:04X}-{e:04X} ({e - s + 1:3d})  "
              f"old: {a[s:e + 1][:12].hex(' ')}\n"
              f"{'':17}new: {b[s:e + 1][:12].hex(' ')}")
        collect.append({
            "comparison": label,
            "start": s, "end": e, "length": e - s + 1,
            "old": a[s:e + 1].hex(), "new": b[s:e + 1].hex(),
        })


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", metavar="FILE", help="write hunks as JSON")
    args = ap.parse_args()

    roms = {k: load(k) for k in IMAGES}

    print("=== image inventory ===")
    bad = []
    for k, fn in IMAGES.items():
        d = roms[k]
        crc = zlib.crc32(d) & 0xffffffff
        flag = ""
        if k in EXPECT_CRC:
            if crc == EXPECT_CRC[k]:
                flag = " OK"
            elif crc in KNOWN_BAD:
                flag = f" !! this is {KNOWN_BAD[crc]}"
                bad.append(k)
            else:
                flag = f" !! expected {EXPECT_CRC[k]:08x}"
                bad.append(k)
        print(f"  {k:16s} {fn:24s} {len(d):6d} B  crc32={crc:08x}"
              f"  md5={hashlib.md5(d).hexdigest()}{flag}")
    if bad:
        print("\n!! WRONG IMAGE(S): " + ", ".join(bad) +
              "\n!! Every hunk count below is meaningless until this is fixed."
              "\n!! See docs/rom-analysis/DIFF_HOME_vs_STOCK.md#baseline")

    if roms["tspico-11-home"] != roms["tspico-15w-home"]:
        print("\n!! TSPICO-11-home and TSPICO-15w-home now DIFFER - "
              "this contradicts the analysis in docs/rom-analysis/. Re-check.")

    collected = []
    for label, left, right, note in COMPARISONS:
        a, b = roms[left], roms[right]
        if "chunk0" in label:
            b = b[:len(a)]
        report(label, a, b, note, collected)

    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(collected, indent=2))
        print(f"\nwrote {args.json} ({len(collected)} hunks)")


if __name__ == "__main__":
    main()
