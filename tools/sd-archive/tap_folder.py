#!/usr/bin/env python3
"""Step 7: the card's tapes as plain files on archive.org, for the v3 WiFi
download (#401).

    python3 tools/sd-archive/tap_folder.py CARD OUTDIR [--max-tap BYTES]
    python3 tools/sd-archive/tap_folder.py CARD OUTDIR --publish [--dry-run]

CARD is the folder build_card.py made. OUTDIR gets:

  OUTDIR/TAP/<CATEGORY>[/<COLLECTION>]/<name>.tap   every archive tape on the
                                                     card, at its card path
  OUTDIR/tspico-taps.txt, tspico-taps.txt.gz         the index the card loads

Only the card's tapes go in: the ones that load and start (load-tested), with
the pipeline's repairs and conversions, from zips checked against archive.org
(fetch.py) and screened for personal data. The tour and its demo tapes stay
on the card only. A tape over --max-tap (default 65536) is left out and
listed, so the card never asks for more than it can hold.

A plain file in an item comes back with a Content-Length, which Zimodem's
AT&G needs; a tape inside a zip can't be fetched that way (see
docs/v3-wifi-archive-proposal.md). The URL is the item, then the path:

  AT&G"https://archive.org/download/ITEM/TAP/GAMES/name.tap"

The index is one line per tape, tab-separated, UTF-8, after a '#' header:

  path  status  title  year  publisher  size  post

  path       TAP/<folder>/<name>.tap, as in the item and on the card
  status     L  LOAD ""           R  LOAD "", then RUN
             C  LOAD "" CODE      S  loads another way (ECM pictures:
                                     with ecmvpico.tap)
  title      the program's title on timexsinclair.com; a tape from a
             collection is "Collection: tape"
  year, publisher   from the zip's TOSEC name, when it has them
  size       the tape's size in bytes
  post       the computer_media post ID: https://timexsinclair.com/?p=ID
             (needs describe.py's descriptions.json; empty without it)

--publish uploads to the ITEM below: only the tapes whose MD5 differs from
the item's copy, then the index. Every upload sends
x-archive-keep-old-version: 0 (ia upload --no-backup), so a replaced tape
leaves no copy under history/files/; a tape changed to take personal data
out must not stay public there. A tape in the item that is no longer on the
card is listed, not deleted: delete it with `ia delete ITEM --no-backup PATH`.
--dry-run says what it would upload and changes nothing.
"""

import argparse
import collections
import csv
import gzip
import os
import re
import shutil
import sys
import time
import urllib.parse

import common as C

ITEM = "tspico-2068-tapes"
INDEX = "tspico-taps.txt"           # the card fetches INDEX + ".gz"
FORMAT = 1
MAX_COMMAND = 255                   # Zimodem's MAX_COMMAND_SIZE is 256, with the 0
NO_BACKUP = {"x-archive-keep-old-version": "0"}
STATUS = {'LOAD ""': "L", 'LOAD "", then RUN': "R", 'LOAD "" CODE': "C"}
METADATA = dict(
    mediatype="software", collection="open_source_software",
    title="TS-Pico WiFi tapes: TS-2068 programs as plain TAP files",
    description=("The TS-2068 programs from the TS-Pico SD card, one plain .tap file each, so a TS-Pico v3 "
                 "card can download a single tape over WiFi. Every tape here loads and starts on a TS-2068 "
                 "(tested in an emulator). tspico-taps.txt.gz is the index the card reads. The originals, "
                 "with their documentation, are in the timex-sinclair-software-archive item, and each "
                 "program's page is on timexsinclair.com."),
    subject=["Timex/Sinclair 2068", "TS-Pico", "TAP"], creator="timexsinclair.com",
)


def tosec(zipname):
    """(title, year, publisher) from 'Title (1984)(Publisher)(TS2068)....zip'."""
    stem = re.sub(r"\.zip$", "", zipname, flags=re.I)
    title = stem.split("(")[0].strip() or stem
    groups = re.findall(r"\(([^()]*)\)", stem[len(title):])
    year = groups[0] if groups and re.fullmatch(r"[0-9x]{4}", groups[0]) else ""
    pub = groups[1] if year and len(groups) > 1 and groups[1] not in ("TS2068", "US", "GB", "-") else ""
    return title, year, pub


def tape_title(title, original, n):
    """A program with one tape is its title; with several, each tape says which."""
    if n == 1:
        return title
    stem = re.sub(r"\.(tap|tzx|wav)$", "", os.path.basename(original), flags=re.I)
    stem = re.sub(r"\s*\([^()]*\)", "", stem).strip() or stem
    return stem if stem.lower().startswith(title.lower()) else "%s: %s" % (title, stem)


def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


def build(card, out, max_tap):
    rows = [r for r in csv.DictReader(open(os.path.join(card, "catalog.csv")))
            if r["on_card"] == "yes" and r["page"]]          # archive tapes; not the tour
    desc = {C.public(k): v for k, v in C.load("descriptions.json", {}).items()}
    per_page = collections.Counter(r["page"] for r in rows)
    lines, big, nopost = [], [], 0
    for r in sorted(rows, key=lambda r: (r["folder"], r["file"])):
        path = "%s/%s" % (r["folder"], r["file"])
        src = os.path.join(card, path)
        size = os.path.getsize(src)
        if size > max_tap:
            big.append((size, path))
            continue
        url = "https://archive.org/download/%s/%s" % (ITEM, path)
        assert len('AT&G"%s"' % url) <= MAX_COMMAND, url
        dst = os.path.join(out, path)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
        zipname = urllib.parse.unquote(r["download"].rsplit("/", 1)[-1])
        _, year, pub = tosec(zipname)
        post = str(desc.get(r["page"], {}).get("id", ""))
        nopost += not post
        st = STATUS.get(r["load"], "S")
        fields = [path, st, clean(tape_title(r["title"], r["original_file"], per_page[r["page"]])),
                  year, clean(pub), str(size), post]
        assert all("\t" not in x for x in fields), fields
        lines.append(fields)
    head = "#tspico-taps\t%d\t%s\ttapes %d\tmax-tap %d\n" % (FORMAT, time.strftime("%Y-%m-%d"), len(lines), max_tap)
    text = (head + "".join("\t".join(f) + "\n" for f in lines)).encode("utf-8")
    with open(os.path.join(out, INDEX), "wb") as f:
        f.write(text)
    with open(os.path.join(out, INDEX + ".gz"), "wb") as f:
        f.write(gzip.compress(text, 9, mtime=0))
    print("%d tapes -> %s; status %s" % (len(lines), out, dict(sorted(collections.Counter(l[1] for l in lines).items()))))
    print("index %d bytes, .gz %d bytes; %d tapes without a post ID%s" % (
        len(text), os.path.getsize(os.path.join(out, INDEX + ".gz")), nopost,
        " (run describe.py)" if nopost else ""))
    if big:
        print("left out, over --max-tap %d: %d tapes" % (max_tap, len(big)))
        for s, p in sorted(big, reverse=True):
            print("  %7d  %s" % (s, p))
    return [l[0] for l in lines]


def publish(out, paths, dry):
    have = C.archive_files(ITEM)            # {} while the item doesn't exist
    new = not have
    todo = {p: os.path.join(out, p) for p in paths
            if p not in have or have[p].get("md5") != C.md5_file(os.path.join(out, p))}
    gone = sorted(n for n in have if n.startswith("TAP/") and n.endswith(".tap") and n not in set(paths))
    print("%s: %d tapes to upload (%d new, %d changed), %d unchanged" % (
        ITEM, len(todo), sum(p not in have for p in todo), sum(p in have for p in todo), len(paths) - len(todo)))
    for n in gone:
        print("  no longer on the card (not deleted): %s" % n)
    files = dict(todo)
    files.update({n: os.path.join(out, n) for n in (INDEX, INDEX + ".gz")})
    if dry:
        print("would upload %d files with %s%s" % (len(files), NO_BACKUP, ", creating the item" if new else ""))
        return
    import internetarchive as ia
    names = sorted(files, key=lambda n: (n.startswith(INDEX), n))     # the index last
    for i in range(0, len(names), 100):
        chunk = {n: files[n] for n in names[i:i + 100]}
        kw = dict(metadata=METADATA) if new and i == 0 else {}
        for r in ia.upload(ITEM, files=chunk, headers=NO_BACKUP, retries=5, retries_sleep=30, **kw):
            r.raise_for_status()
        print("  uploaded %d of %d" % (min(i + 100, len(names)), len(names)))
    print("https://archive.org/download/%s/%s.gz" % (ITEM, INDEX))
    left = [n for n in C.archive_files(ITEM) if n.startswith("history/")]
    if left:
        raise SystemExit("archive.org kept %d old copies under history/: %s" % (len(left), left[:5]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("card", help="the OUTDIR build_card.py made")
    ap.add_argument("out", help="where to lay out the folder (must not exist)")
    ap.add_argument("--max-tap", type=int, default=65536)
    ap.add_argument("--publish", action="store_true", help="upload what changed to archive.org")
    ap.add_argument("--dry-run", action="store_true", help="with --publish: upload nothing")
    a = ap.parse_args()
    card, out = os.path.abspath(a.card), os.path.abspath(a.out)
    if not os.path.exists(os.path.join(card, "catalog.csv")):
        raise SystemExit("%s has no catalog.csv: run build_card.py first" % card)
    if os.path.exists(out):
        raise SystemExit("%s exists: move it away first" % out)
    paths = build(card, out, a.max_tap)
    if a.publish:
        publish(out, paths, a.dry_run)


if __name__ == "__main__":
    sys.exit(main())
