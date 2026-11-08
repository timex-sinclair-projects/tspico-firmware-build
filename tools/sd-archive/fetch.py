#!/usr/bin/env python3
"""Step 1: read the software list page, each program's page, and download the
archive.org zip each one links.

    python3 tools/sd-archive/fetch.py PAGE_URL [--jobs 4]

e.g. http://localhost/downloadable-software/downloadable-software-for-the-ts-2068/
Writes items.json, urlmap.json, detail/ (the program pages) and zips/ in the
work folder. Fetched pages are reused, so it can be run again to pick up new
programs. A zip already in zips/ is reused only while its MD5 matches the
archive.org item's file list: when archive.org replaces a zip (a privacy fix,
a better dump), the next run downloads it again. A zip that can't be checked
(a file served from inside another zip has no MD5 of its own) is reused as
it is, and the run says how many there were.
"""

import argparse
import collections
import concurrent.futures as cf
import hashlib
import html
import os
import re
import time
import urllib.parse

import common as C

get = C.get


def tag(rest, cls):
    m = re.search(r'class="%s">(.*?)</span>' % cls, rest)
    return html.unescape(m.group(1)) if m else ""


def program_page(origin, it):
    fn = C.work("detail", it["href"].strip("/").split("/")[-1] + ".html")
    if not os.path.exists(fn):
        with open(fn, "wb") as f:
            f.write(get(origin + it["href"], 60))
    d = open(fn, encoding="utf8", errors="replace").read()
    # Programs that are part of a collection have no link of their own: the
    # collection's zip brings them.
    it["downloads"] = sorted(set(html.unescape(x) for x in
                                 re.findall(r'href="(https?://archive\.org/download/[^"]+)"', d)))
    return it


def zip_file(u):
    name = urllib.parse.unquote(u.rsplit("/", 1)[1])[-80:].replace("/", "_")
    return C.work("zips", hashlib.md5(u.encode()).hexdigest()[:10] + "_" + name)


def expected(urls):
    """{url: archive.org's file entry (md5, size)} for every url it lists. One
    metadata read per item, so a zip replaced on archive.org shows up."""
    want, items = {}, {}
    for u in urls:
        p = C.archive_path(u)
        if p:
            items.setdefault(p[0], []).append((u, p[1]))
    for item, us in sorted(items.items()):
        try:
            files = C.archive_files(item)
        except Exception as e:                  # noqa: BLE001 -- reported; those zips go unchecked
            print("  can't read the file list of %s (%s): its zips are not checked" % (item, e))
            continue
        for u, name in us:
            if name in files and files[name].get("md5"):
                want[u] = files[name]
    return want


def matches(f, w):
    if w.get("size") and os.path.getsize(f) != int(w["size"]):
        return False                            # no need to read it
    return C.md5_file(f) == w["md5"]


def download(u, w=None):
    """(url, error, what happened): 'kept', 'unchecked', 'new' or 'replaced'."""
    f = zip_file(u)
    had = os.path.exists(f) and os.path.getsize(f) > 0
    if had and not w:
        return u, None, "unchecked"
    if had and matches(f, w):
        return u, None, "kept"
    err = None
    for _ in range(3):
        try:
            data = get(u)
            if w and hashlib.md5(data).hexdigest() != w["md5"]:
                raise ValueError("downloaded copy's MD5 is not archive.org's %s" % w["md5"])
            with open(f + ".part", "wb") as o:
                o.write(data)
            os.replace(f + ".part", f)
            return u, None, "replaced" if had else "new"
        except Exception as e:                  # noqa: BLE001 -- retried, then reported
            err = str(e)
            time.sleep(3)
    if had:
        # The copy here is not archive.org's any more (it may be the one a
        # privacy fix replaced): never build a card from it.
        os.remove(f)
        err += "; the old copy is deleted"
    return u, err, "failed"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("page")
    ap.add_argument("--jobs", type=int, default=4, help="parallel downloads (default 4)")
    a = ap.parse_args()
    for d in ("detail", "zips"):
        os.makedirs(C.work(d), exist_ok=True)
    origin = "{0.scheme}://{0.netloc}".format(urllib.parse.urlparse(a.page))

    page = get(a.page).decode("utf8", "replace")
    cards = re.findall(r'<div class="card"><a href="(/computer_media/[^"]+)".*?<h4>(.*?)</h4>'
                       r'.*?<span class="computertag">(.*?)</span>(.*?)</article>', page, re.S)
    items = {}
    for href, title, ctag, rest in cards:
        items.setdefault(href, dict(href=href, title=html.unescape(title), ctag=ctag,
                                    tags=tag(rest, "item-tags"), kind=tag(rest, "item-media-kind")))
    with cf.ThreadPoolExecutor(8) as ex:
        items = list(ex.map(lambda it: program_page(origin, it), items.values()))
    for it in items:
        it["page"] = origin + it["href"]
    C.save("items.json", items)
    print("%d programs, %d with a download" % (len(items), sum(1 for i in items if i["downloads"])))

    urls = sorted({C.zip_url(d) for i in items for d in i["downloads"]} - {C.ARCHIVE.rstrip("/")})
    want = expected(urls)
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        res = list(ex.map(lambda u: download(u, want.get(u)), urls))
    C.save("urlmap.json", {u: zip_file(u) for u in urls})
    n = collections.Counter(r[2] for r in res)
    print("%d zips: %d kept, %d new, %d replaced (changed on archive.org), %d not checkable, %d failed"
          % (len(res), n["kept"], n["new"], n["replaced"], n["unchecked"], n["failed"]))
    for u, e, k in res:
        if k == "replaced":
            print("  replaced: %s" % urllib.parse.unquote(u))
    for u, e, k in res:
        if e:
            print("  failed: %s: %s" % (u, e))
    if n["replaced"]:
        print("Run plan.py and the later steps again: the replaced zips' tapes are new to them.")


if __name__ == "__main__":
    main()
