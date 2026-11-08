#!/usr/bin/env python3
"""Step 7: the card's tapes as plain files on archive.org, for the v3 WiFi
download (#401).

    python3 tools/sd-archive/tap_folder.py CARD OUTDIR [--max-tap BYTES]
    python3 tools/sd-archive/tap_folder.py CARD OUTDIR --publish [--dry-run]

CARD is the folder build_card.py made. OUTDIR gets:

  OUTDIR/TAP/<CATEGORY>[/<COLLECTION>]/<name>.tap   every archive tape on the
                                                     card, at its card path
  OUTDIR/TAP/.../index.txt, index2.txt...            each folder's index, for
                                                     browsing (8 KB parts)
  OUTDIR/tspico-taps.txt, tspico-taps.txt.gz         every tape in one index,
                                                     for search

Only the card's tapes go in: the ones that load and start (load-tested), with
the pipeline's repairs and conversions, from zips checked against archive.org
(fetch.py) and screened for personal data. The tour and its demo tapes stay
on the card only. A tape over --max-tap (default 65536) is left out and
listed, so the card never asks for more than it can hold.

A plain file in an item comes back with a Content-Length, which Zimodem's
AT&G needs; a tape inside a zip can't be fetched that way (see
docs/v3-wifi-archive-proposal.md). The URL is the item, then the path:

  AT&G"https://archive.org/download/ITEM/TAP/GAMES/name.tap"

Browsing starts at TAP/index.txt. Every folder has an index.txt: its
subfolders, then its tapes, tab-separated UTF-8 after a '#' header. A folder's
index is split into parts of at most 8192 bytes (MAX_PART), so each part fits
the card's 32 KB download buffer with room to spare: index.txt, index2.txt...
The header says which part it is and how many there are:

  #tspico-dir  1  DATE  TAP/HOME  Home and business  part 1 of 2  tapes 428

  name/  D  title  tapes                  a subfolder: its title (the program's
                                          title on the site, for a collection)
                                          and how many tapes are under it
  name.tap  status  title  year  publisher  size  post
                                          a tape, with the fields below; in a
                                          collection, the title drops the
                                          collection's name

The full index, tspico-taps.txt.gz, is one line per tape, after a '#' header
(gzipped with a 4 KB window, GZ_WBITS, so the card can unpack it):

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
the item's copy, then the indexes that changed. Uploads go CHUNK files at a
time, and wait while the item has more than QUEUE archive.org tasks queued,
since archive.org refuses uploads past a few hundred. Every upload sends
x-archive-keep-old-version: 0 (ia upload --no-backup), so a replaced tape
leaves no copy under history/files/; a tape changed to take personal data
out must not stay public there. A tape in the item that is no longer on the
card is listed, not deleted: delete it with `ia delete ITEM --no-backup PATH`.
--dry-run says what it would upload and changes nothing.
"""

import argparse
import collections
import csv
import zlib
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
CHUNK = 50                          # files per upload call
QUEUE = 100                         # archive.org refuses uploads ("bucket_tasks_queued exceeds rationed
                                    # amount") once an item has a few hundred tasks queued; each file is one task
DIR_INDEX = "index"                 # index.txt, then index2.txt, index3.txt... in every folder
MAX_PART = 8192                     # bytes per index part, header included
GZ_WBITS = 12                       # the .gz's window: 4 KB, what the card's inflate allocates
MAX_GZ = 49160                      # the .gz must fit the card's download buffer (board_v3 BLOCK_BUF)
GROUPS = {"ARCADE": "Arcade games", "GAMES": "Games", "EDUCATE": "Education", "MUSIC": "Music, sound and speech",
          "HOME": "Home and business", "GRAPHICS": "Graphics", "UTILITY": "Utilities", "DEMOS": "Demos",
          "COLLECT": "Collections and magazines", "MISC": "Other programs"}
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



def gz_index(text):
    """The full index gzipped with a GZ_WBITS window, not gzip's 32K: the card
    unpacks it with deflate.DeflateIO(f, GZIP, GZ_WBITS), which allocates the
    window, and once its firmware has run the heap has no 32K block (the
    first tpi:net find gave MemoryError, 2026-11-08). Any gunzip reads it."""
    c = zlib.compressobj(9, zlib.DEFLATED, 16 + GZ_WBITS)
    gz = c.compress(text) + c.flush()
    assert len(gz) <= MAX_GZ, "the .gz is %d bytes, over the card's %d: split the index" % (len(gz), MAX_GZ)
    return gz

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


def part_name(k):
    return "%s%s.txt" % (DIR_INDEX, "" if k == 1 else k)


def write_dirs(out, lines, posts):
    """An index in every folder: its subfolders, then its tapes, in parts of at most MAX_PART bytes.
    posts: {tape path: its program's title on the site}, which names a collection's folder.
    Returns the index paths, relative to out."""
    tapes = collections.defaultdict(list)                   # folder -> tape lines
    subs = collections.defaultdict(set)                     # folder -> subfolders
    for f in lines:
        d = os.path.dirname(f[0])
        tapes[d].append(f)
        while "/" in d:
            subs[os.path.dirname(d)].add(d)
            d = os.path.dirname(d)
    count = collections.Counter()
    for d, ts in tapes.items():
        x = d
        while True:
            count[x] += len(ts)
            if "/" not in x:
                break
            x = os.path.dirname(x)

    def title(d):
        name = os.path.basename(d)
        if d.count("/") == 1:
            return GROUPS.get(name, name.title())
        ts = [posts[t[0]] for t in tapes[d]] or [title(x) for x in subs[d]]
        return collections.Counter(ts).most_common(1)[0][0]

    written, today = [], time.strftime("%Y-%m-%d")
    for d in sorted(set(tapes) | set(subs)):
        t = title(d) if "/" in d else "TS-2068 programs"
        rows = [[os.path.basename(x) + "/", "D", title(x), str(count[x])]
                for x in sorted(subs[d], key=lambda x: title(x).lower())]
        for f in tapes[d]:
            tt = f[2][len(t) + 2:] if f[2].startswith(t + ": ") else f[2]
            rows.append([os.path.basename(f[0]), f[1], tt] + f[3:])
        parts, cur, size = [], [], 0
        for r in rows:
            b = len(("\t".join(r) + "\n").encode("utf-8"))
            if cur and size + b > MAX_PART - 120:           # room for the header
                parts.append(cur)
                cur, size = [], 0
            cur.append(r)
            size += b
        parts.append(cur)
        for k, rs in enumerate(parts, 1):
            head = "#tspico-dir\t%d\t%s\t%s\t%s\tpart %d of %d\ttapes %d\n" % (
                FORMAT, today, d, t, k, len(parts), count[d])
            text = (head + "".join("\t".join(r) + "\n" for r in rs)).encode("utf-8")
            assert len(text) <= MAX_PART, (d, k, len(text))
            rel = os.path.join(d, part_name(k))
            with open(os.path.join(out, rel), "wb") as fh:
                fh.write(text)
            written.append(rel)
    return written


def build(card, out, max_tap):
    rows = [r for r in csv.DictReader(open(os.path.join(card, "catalog.csv")))
            if r["on_card"] == "yes" and r["page"]]          # archive tapes; not the tour
    desc = {C.public(k): v for k, v in C.load("descriptions.json", {}).items()}
    per_page = collections.Counter(r["page"] for r in rows)
    lines, big, nopost, posts = [], [], 0, {}
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
        posts[path] = clean(r["title"])
    head = "#tspico-taps\t%d\t%s\ttapes %d\tmax-tap %d\n" % (FORMAT, time.strftime("%Y-%m-%d"), len(lines), max_tap)
    text = (head + "".join("\t".join(f) + "\n" for f in lines)).encode("utf-8")
    with open(os.path.join(out, INDEX), "wb") as f:
        f.write(text)
    with open(os.path.join(out, INDEX + ".gz"), "wb") as f:
        f.write(gz_index(text))
    print("%d tapes -> %s; status %s" % (len(lines), out, dict(sorted(collections.Counter(l[1] for l in lines).items()))))
    print("index %d bytes, .gz %d bytes; %d tapes without a post ID%s" % (
        len(text), os.path.getsize(os.path.join(out, INDEX + ".gz")), nopost,
        " (run describe.py)" if nopost else ""))
    dirs = write_dirs(out, lines, posts)
    sizes = [os.path.getsize(os.path.join(out, p)) for p in dirs]
    print("%d folder indexes in %d folders; largest part %d bytes" % (
        len(dirs), len({os.path.dirname(p) for p in dirs}), max(sizes)))
    if big:
        print("left out, over --max-tap %d: %d tapes" % (max_tap, len(big)))
        for s, p in sorted(big, reverse=True):
            print("  %7d  %s" % (s, p))
    return [l[0] for l in lines], dirs


def publish(out, paths, dirs, dry):
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
    idx = [n for n in dirs + [INDEX, INDEX + ".gz"]
           if n not in have or have[n].get("md5") != C.md5_file(os.path.join(out, n))]
    files.update({n: os.path.join(out, n) for n in idx})
    stale = sorted(n for n in have if re.fullmatch(r"TAP/.*%s\d*\.txt" % DIR_INDEX, n) and n not in set(dirs))
    for n in stale:
        print("  index part no longer made (not deleted): %s" % n)
    print("%d of %d indexes to upload" % (len(idx), len(dirs) + 2))
    if dry:
        print("would upload %d files with %s%s" % (len(files), NO_BACKUP, ", creating the item" if new else ""))
        return
    import internetarchive as ia
    def order(n):                       # tapes, then the folder indexes, then the full index
        return (n.startswith(INDEX), os.path.basename(n).startswith(DIR_INDEX), n)
    names = sorted(files, key=order)
    for i in range(0, len(names), CHUNK):
        if not wait_for_queue(ia):
            raise SystemExit("archive.org still has over %d tasks queued for %s after 6 hours" % (QUEUE, ITEM))
        chunk = {n: files[n] for n in names[i:i + CHUNK]}
        kw = dict(metadata=METADATA) if new and i == 0 else {}
        for attempt in range(10):
            try:
                for r in ia.upload(ITEM, files=chunk, headers=NO_BACKUP, checksum=True,
                                   retries=5, retries_sleep=30, **kw):
                    r.raise_for_status()
                break
            except Exception as e:              # noqa: BLE001 -- archive.org's rate limit comes back as an HTTP error
                if "reduce your request rate" not in str(e) or attempt == 9:
                    raise
                print("  archive.org asks to slow down; waiting for its queue")
                wait_for_queue(ia, 0, 60)
        print("  uploaded %d of %d" % (min(i + CHUNK, len(names)), len(names)))
    if not wait_for_queue(ia, 0, 30):        # one task can sit queued for hours; check what's there now
        print("archive.org still has tasks queued for the item after 30 minutes; check later with:")
        print("  ia list %s | grep history/" % ITEM)
    print("https://archive.org/download/%s/%s.gz" % (ITEM, INDEX))
    left = [n for n in C.archive_files(ITEM) if n.startswith("history/")]
    if left:
        raise SystemExit("archive.org kept %d old copies under history/: %s" % (len(left), left[:5]))


def wait_for_queue(ia, most=QUEUE, minutes=360):
    """Wait until the item has at most `most` archive.org tasks queued or running.
    Returns False if it still has more after `minutes`."""
    s = ia.get_session()
    for _ in range(minutes * 2):
        t = s.get_tasks_summary(ITEM)
        if t.get("queued", 0) + t.get("running", 0) <= most:
            return True
        time.sleep(30)
    return False


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
    paths, dirs = build(card, out, a.max_tap)
    if a.publish:
        publish(out, paths, dirs, a.dry_run)


if __name__ == "__main__":
    sys.exit(main())
