#!/usr/bin/env python3
"""The index a v3 card downloads to find tapes in the archive.org item
(docs/v3-wifi-archive-proposal.md).

    python3 tools/sd-archive/net_index.py [--max-zip BYTES] [--offline] [--publish]

Writes net/tspico-net.txt and net/tspico-net.txt.gz in the work folder.
--publish uploads both to the item, as tspico-net.txt(.gz), replacing the
previous copies (needs internetarchive and ia.ini, as publish.py does). The
card downloads the .gz
through Zimodem (AT&G needs a file with a Content-Length, which a plain file
in the item has), gunzips it to the SD card and searches it there.

Every 2068 ZIP in the item is looked at, tested or not (David, 2026-11-07):
those tagged (TS2068), and those the site's 2068 list links (plan.json),
which include some without the tag. Left out, because the card can't use
them:
  - ZIPs over --max-zip: the card holds the whole ZIP in RAM before it
    unzips it (the ESP32's line has no flow control, so it can't write the
    SD card as the bytes arrive). The default, 32768, is board_v3's slot
    buffer, which is allocated while the heap is clean.
  - ZIPs with no .tap inside (WAV or TZX only, disk images): the card
    doesn't convert.
  - A .tap that is really a TZX, or stored with a method other than
    stored/deflate.
  - A ZIP whose AT&G"<url>" line would be over Zimodem's 256-byte command
    buffer (MAX_COMMAND_SIZE).

One line per tape, tab-separated, UTF-8:

  name  status  title  year  publisher  zip  entry  zipsize  tapsize

  name     the 8.3 name to save it as, unique in the index (plan.py's, for a
           tape that is on the SD card image)
  status   L  loads and starts with LOAD ""        (load-tested)
           R  LOAD "", then RUN                     (load-tested)
           C  LOAD "" CODE                          (load-tested)
           S  loads another way: see the SD card catalog
           X  tested and fails, or damaged
           ?  not tested
  zip      the ZIP's name in the item
  entry    the tape's position in the ZIP's central directory (from 0); the
           card reads the directory at the end of the ZIP it holds in RAM
  zipsize, tapsize   in bytes

The first line is a header starting with '#'.
"""

import argparse
import collections
import gzip
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import zipfile

import common as C
import build_card
import plan as P

FILES = "https://archive.org/metadata/timex-sinclair-software-archive/files"
FORMAT = 1
ITEM = "timex-sinclair-software-archive"
INDEX = "tspico-net.txt"   # in the item; the card fetches INDEX + ".gz"
MAX_COMMAND = 255          # Zimodem's MAX_COMMAND_SIZE is 256, with the 0
SAFE = "()!,;'*+&=@$-_.~"  # left unquoted, so the AT&G line stays short


def get(url, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": "tspico-net-index"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def url_for(zipname):
    """The ZIP's download URL as the card sends it: only what HTTP needs
    quoted is quoted (spaces, %, #, ?, non-ASCII)."""
    return C.ARCHIVE + urllib.parse.quote(zipname, safe=SAFE)


def at_line(zipname):
    return 'AT&G"%s"' % url_for(zipname)


def tosec(zipname):
    """(title, year, publisher) from 'Title (1984)(Publisher)(TS2068)....zip'."""
    stem = zipname[:-4] if zipname.lower().endswith(".zip") else zipname
    title = stem.split("(")[0].strip() or stem
    groups = re.findall(r"\(([^()]*)\)", stem[len(title):])
    year = groups[0] if groups and re.fullmatch(r"[0-9x]{4}", groups[0]) else ""
    pub = groups[1] if year and len(groups) > 1 and groups[1] not in ("TS2068", "US", "GB", "-") else ""
    return title, year, pub


def tape_title(ztitle, member, n):
    """A ZIP with one tape is its title; with several, each tape says which."""
    if n == 1:
        return ztitle
    stem = re.sub(r"\.tap$", "", os.path.basename(member), flags=re.I)
    stem = re.sub(r"\s*\([^()]*\)", "", stem).strip() or stem
    return stem if stem.lower().startswith(ztitle.lower()) else "%s: %s" % (ztitle, stem)


def tape_entries(z):
    """[(entry index, ZipInfo)] of the tapes plan.py would take: .tap, not
    dirinfo.tap, lkdos/ fragments only when there's nothing else."""
    infos = [(i, zi) for i, zi in enumerate(z.infolist())
             if "__MACOSX" not in zi.filename and not os.path.basename(zi.filename).startswith("._")
             and not zi.is_dir() and zi.filename.lower().endswith(".tap")
             and os.path.basename(zi.filename).lower() != "dirinfo.tap"]
    if any("/lkdos/" not in zi.filename.lower() for i, zi in infos):
        infos = [(i, zi) for i, zi in infos if "/lkdos/" not in zi.filename.lower()]
    return infos


def local_zips():
    """The ZIPs fetch.py already has, by (name, size). fetch.py keeps the last
    80 characters of the name after a 10-digit hash."""
    out = {}
    for d, cut in ((C.work("zips"), 11), (C.work("net", "zips"), 0)):
        if os.path.isdir(d):
            for f in os.listdir(d):
                p = os.path.join(d, f)
                out[(f[cut:][-80:], os.path.getsize(p))] = p
    return out


def zip_bytes(name, size, have, offline):
    p = have.get((name.replace("/", "_")[-80:], size))
    if p:
        return C.read(p)
    if offline:
        return None
    os.makedirs(C.work("net", "zips"), exist_ok=True)
    data = get(C.ARCHIVE + urllib.parse.quote(name))
    if len(data) != size:
        raise RuntimeError("%s: got %d bytes, the item says %d" % (name, len(data), size))
    with open(C.work("net", "zips", name.replace("/", "_")), "wb") as f:
        f.write(data)
    return data


def tested():
    """{(zip, member): (status, 8.3 name)} for the tapes the SD card pipeline
    load-tested, with build_card's verdict."""
    plan = C.load("plan.json", [])
    res = build_card.results("results.json")
    code, run, stock, ares = (build_card.results(n) for n in ("results_code.json", "results_run.json",
                                                               "results_stock.json", "results_alt.json"))
    alt = C.load("alt.json", {})
    out = {}
    for e in plan:
        if e["src"] != "tap":
            continue            # converted from TZX/WAV on the host: not a .tap in the ZIP
        sid = e["sha1"][:12]
        if sid not in res:
            continue
        a = dict(ares[sid], **alt[sid]) if alt.get(sid) and sid in ares else None
        on, how, note = build_card.verdict(e, res[sid], C.tap_path(e["sha1"]), code.get(sid), a,
                                           run.get(sid), stock.get(sid))
        if not on or note.startswith("the archive's"):
            st = "X"            # fails, or only a converted copy works
        else:
            st = {'LOAD ""': "L", 'LOAD "", then RUN': "R", 'LOAD "" CODE': "C"}.get(how, "S")
        out[(e["zip"], e["member"])] = (st, e["name"])
    return out


def build(files, max_zip, offline, log=print):
    have = local_zips()
    known = tested()
    listed = {e["zip"] for e in C.load("plan.json", [])}
    zips = sorted((f for f in files if f.get("source") == "original" and f["name"].lower().endswith(".zip")
                   and ("(TS2068)" in f["name"] or f["name"] in listed)), key=lambda f: f["name"].lower())
    why = collections.Counter()
    rows, names = [], set()
    for f in zips:
        name, size = f["name"], int(f["size"])
        if size > max_zip:
            why["over --max-zip"] += 1
            continue
        if len(at_line(name)) > MAX_COMMAND:
            why["AT&G line too long"] += 1
            continue
        data = zip_bytes(name, size, have, offline)
        if data is None:
            why["not downloaded (--offline)"] += 1
            continue
        try:
            z = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile:
            why["not a ZIP"] += 1
            continue
        tapes = tape_entries(z)
        if not tapes:
            why["no .tap inside"] += 1
            continue
        ztitle, year, pub = tosec(name)
        for i, zi in tapes:
            if zi.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED) or zi.flag_bits & 1:
                why["tape stored another way"] += 1
                continue
            d = z.read(zi)
            if d.startswith(b"ZXTape!"):
                why["a TZX named .tap"] += 1
                continue
            st, short = known.get((name, zi.filename), (None, None))
            if st is None:
                nbad, nbl = C.damage(d)
                st = "X" if nbad or not nbl else "?"
            title = tape_title(ztitle, zi.filename, len(tapes))
            base = (short or P.short(title) + ".tap")[:-4]
            nm, k = base, 1
            while nm + ".tap" in names:
                k += 1
                nm = base[:8 - len(str(k))] + str(k)
            names.add(nm + ".tap")
            rows.append((nm + ".tap", st, title, year, pub, name, str(i), str(size), str(zi.file_size)))
    for k, v in sorted(why.items()):
        log("left out, %s: %d ZIPs" % (k, v) if "tape" not in k and "TZX" not in k
            else "left out, %s: %d tapes" % (k, v))
    return rows, len(zips)


def write(rows, nzips, max_zip, path):
    for r in rows:
        assert all("\t" not in x and "\n" not in x for x in r), r
    head = "#tspico-net\t%d\t%s\ttapes %d\tmax-zip %d\n" % (FORMAT, time.strftime("%Y-%m-%d"),
                                                            len(rows), max_zip)
    text = (head + "".join("\t".join(r) + "\n" for r in rows)).encode("utf-8")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(text)
    with open(path + ".gz", "wb") as f:
        f.write(gzip.compress(text, 9, mtime=0))
    return len(text), os.path.getsize(path + ".gz")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--max-zip", type=int, default=32768)
    ap.add_argument("--offline", action="store_true",
                    help="use the cached file list and ZIPs only; download nothing")
    ap.add_argument("--publish", action="store_true",
                    help="upload the index to the item (replaces the copy there)")
    a = ap.parse_args()
    if a.offline:
        files = C.load(os.path.join("net", "files.json"))
    else:
        files = json.loads(get(FILES))["result"]
        os.makedirs(C.work("net"), exist_ok=True)
        C.save(os.path.join("net", "files.json"), files)
    rows, nzips = build(files, a.max_zip, a.offline)
    n, gz = write(rows, nzips, a.max_zip, C.work("net", INDEX))
    st = collections.Counter(r[1] for r in rows)
    print("%d 2068 ZIPs -> %d tapes from %d ZIPs; status %s" %
          (nzips, len(rows), len({r[5] for r in rows}), dict(sorted(st.items()))))
    print("%s: %d bytes, .gz %d bytes" % (C.work("net", INDEX), n, gz))
    print("longest AT&G line: %d bytes" % max(len(at_line(r[5])) for r in rows))
    if a.publish:
        import internetarchive as ia
        files = {INDEX: C.work("net", INDEX), INDEX + ".gz": C.work("net", INDEX + ".gz")}
        for r in ia.upload(ITEM, files=files, verbose=True, retries=5, retries_sleep=30):
            r.raise_for_status()
        print(C.ARCHIVE + INDEX + ".gz")


if __name__ == "__main__":
    sys.exit(main())
