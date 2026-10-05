#!/usr/bin/env python3
"""Step 6: put the card on archive.org, next to the tapes it came from.

    python3 tools/sd-archive/publish.py OUTDIR [--dry-run]

Zips OUTDIR (TAP/, help/, catalog.csv: what goes on the card) and uploads the
zip and the catalog to the timex-sinclair-software-archive item, replacing the
previous copies. The web updater links to the zip there. Needs the
internetarchive library (pip install internetarchive) and an account that can
write the item (`ia configure`, which writes ~/.config/internetarchive/ia.ini).
"""

import argparse
import os
import zipfile

ITEM = "timex-sinclair-software-archive"
NAME = "TS-Pico SD Card - TS-2068 Software Library (2026)(TS2068)(US)(Collection)"


def make_zip(card, path):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for top in ("TAP", "help"):
            for d, dirs, files in os.walk(os.path.join(card, top)):
                dirs.sort()
                for f in sorted(files):
                    if f.startswith("."):
                        continue
                    p = os.path.join(d, f)
                    z.write(p, os.path.relpath(p, card))
        z.write(os.path.join(card, "catalog.csv"), "catalog.csv")
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("card", help="the OUTDIR build_card.py made")
    ap.add_argument("--dry-run", action="store_true", help="make the zip, upload nothing")
    a = ap.parse_args()
    card = os.path.abspath(a.card)
    for p in ("TAP", "help", "catalog.csv"):
        if not os.path.exists(os.path.join(card, p)):
            raise SystemExit("%s has no %s: run build_card.py first" % (card, p))
    zp = make_zip(card, card.rstrip("/") + ".zip")
    with zipfile.ZipFile(zp) as z:
        n = sum(1 for i in z.infolist() if i.filename.lower().endswith(".tap"))
    print("%s: %d tapes, %.1f MB" % (zp, n, os.path.getsize(zp) / 1e6))
    files = {NAME + ".zip": zp, NAME + ".csv": os.path.join(card, "catalog.csv")}
    if a.dry_run:
        for k in files:
            print("would upload: %s/%s" % (ITEM, k))
        return
    import internetarchive as ia
    for r in ia.upload(ITEM, files=files, verbose=True, retries=5, retries_sleep=30):
        r.raise_for_status()
    for k in files:
        print("https://archive.org/download/%s/%s" % (ITEM, k.replace(" ", "%20")))


if __name__ == "__main__":
    main()
