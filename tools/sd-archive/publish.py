#!/usr/bin/env python3
"""Step 6: put the card on archive.org, next to the tapes it came from.

    python3 tools/sd-archive/publish.py OUTDIR [--dry-run]

Zips OUTDIR (TAP/, help/, catalog.csv: what goes on the card) and uploads the
zip and the catalog to the timex-sinclair-software-archive item, replacing the
previous copies. The web updater links to the zip there. Needs the
internetarchive library (pip install internetarchive) and an account that can
write the item (`ia configure`, which writes ~/.config/internetarchive/ia.ini).

The upload sends x-archive-keep-old-version: 0 (what `ia upload --no-backup`
does), so archive.org drops the copy it replaces instead of keeping it under
history/files/: an old card can hold tapes since withdrawn for privacy. When
archive.org has finished, it checks that no history/files/ copy of the card is
left, and stops with an error if one is. --dry-run uploads nothing, and makes
the same check of the item as it is now.
"""

import argparse
import os
import time
import zipfile

import common as C

ITEM = "timex-sinclair-software-archive"
NAME = "TS-Pico SD Card - TS-2068 Software Library (2026)(TS2068)(US)(Collection)"
HISTORY = "history/files/TS-Pico SD Card"
NO_BACKUP = {"x-archive-keep-old-version": "0"}    # ia upload --no-backup


def old_copies():
    """The card's replaced copies archive.org kept under history/files/."""
    return sorted(n for n in C.archive_files(ITEM) if n.startswith(HISTORY))


def wait_for_tasks(item, minutes=30):
    """archive.org files an upload, and drops what it replaces, in tasks that
    run after the upload returns. Wait for them, so the check sees the result."""
    for _ in range(minutes * 2):
        if item.no_tasks_pending():
            return True
        time.sleep(30)
    return False


def check_history():
    left = old_copies()
    for n in left:
        print("  old copy kept: %s/%s" % (ITEM, n))
    return left


def make_zip(card, path):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for top in ("TAP", "help"):
            for d, dirs, files in os.walk(os.path.join(card, top)):
                dirs[:] = sorted(x for x in dirs if not C.JUNK.match(x))
                for f in sorted(files):
                    if C.JUNK.match(f):
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
            print("would upload: %s/%s (header %s)" % (ITEM, k, ", ".join("%s: %s" % h for h in NO_BACKUP.items())))
        print("old copies of the card under history/files/ now: %d" % len(check_history()))
        return
    import internetarchive as ia
    for r in ia.upload(ITEM, files=files, headers=NO_BACKUP, verbose=True, retries=5, retries_sleep=30):
        r.raise_for_status()
    for k in files:
        print("https://archive.org/download/%s/%s" % (ITEM, k.replace(" ", "%20")))
    if not wait_for_tasks(ia.get_item(ITEM)):
        print("archive.org still has tasks queued for the item after 30 minutes; check later with:")
        print("  ia list %s | grep history/" % ITEM)
    if check_history():
        raise SystemExit("archive.org kept old copies of the card (above). Delete them with "
                         "`ia delete %s --no-backup 'FILE'` and check again." % ITEM)
    print("no old copies of the card under history/files/")


if __name__ == "__main__":
    main()
