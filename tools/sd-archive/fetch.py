#!/usr/bin/env python3
"""Step 1: read the software list page, each program's page, and download the
archive.org zip each one links.

    python3 tools/sd-archive/fetch.py PAGE_URL [--jobs 4]

e.g. http://localhost/downloadable-software/downloadable-software-for-the-ts-2068/
Writes items.json, urlmap.json, detail/ (the program pages) and zips/ in the
work folder. Already-downloaded zips and fetched pages are reused, so it can
be run again to pick up new programs.
"""

import argparse
import concurrent.futures as cf
import hashlib
import html
import os
import re
import time
import urllib.parse
import urllib.request

import common as C

UA = {"User-Agent": "tspico-sd-archive"}


def get(url, timeout=120):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


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


def download(u):
    f = zip_file(u)
    if os.path.exists(f) and os.path.getsize(f):
        return u, None
    err = None
    for _ in range(3):
        try:
            data = get(u)
            with open(f + ".part", "wb") as o:
                o.write(data)
            os.replace(f + ".part", f)
            return u, None
        except Exception as e:                  # noqa: BLE001 -- retried, then reported
            err = str(e)
            time.sleep(3)
    return u, err


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
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        res = list(ex.map(download, urls))
    C.save("urlmap.json", {u: zip_file(u) for u in urls})
    bad = [r for r in res if r[1]]
    print("%d zips, %d failed" % (len(res), len(bad)))
    for u, e in bad:
        print("  %s: %s" % (u, e))


if __name__ == "__main__":
    main()
