"""Shared by the tools/sd-archive scripts: where things live, TAP parsing,
and what a load test's result means.

Everything downloaded or generated goes in the work folder, $TSPICO_ARCHIVE_WORK
(default ~/tspico-archive-work), never in the repo: the zips alone are ~4.4 GB.
"""

import json
import os
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
EMU_DIR = os.path.join(REPO, "tools", "emu")
WORK = os.path.abspath(os.path.expanduser(os.environ.get("TSPICO_ARCHIVE_WORK", "~/tspico-archive-work")))
ARCHIVE = "https://archive.org/download/timex-sinclair-software-archive/"
# The site the program pages are published on. fetch.py may read a local copy
# (http://localhost/...); the catalog links the public pages.
SITE = os.environ.get("TSPICO_ARCHIVE_SITE", "https://timexsinclair.com")


def public(url):
    """A program page's URL on the public site, whatever host fetch.py read."""
    u = urllib.parse.urlparse(url)
    return SITE + u._replace(scheme="", netloc="").geturl()


def work(*p):
    return os.path.join(WORK, *p)


def load(name, default=None):
    p = work(name)
    if not os.path.exists(p):
        if default is not None:
            return default
        raise SystemExit("%s is missing: run the earlier steps first (see README.md)" % p)
    with open(p) as f:
        return json.load(f)


def save(name, data):
    os.makedirs(WORK, exist_ok=True)
    tmp = work(name + ".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, work(name))


def zip_url(url):
    """A program page's archive.org link as a plain download URL. One page links
    the collection with a text fragment naming the file (#:~:text=...)."""
    if "#:~:text=" in url:
        return ARCHIVE + urllib.parse.quote(urllib.parse.unquote(url.split("text=", 1)[1]))
    return url.split("#")[0]


def tap_path(sha):
    return work("taps", sha[:12] + ".tap")


# ---- TAP files ----

def blocks(d):
    """[(flag, body, problem)] for each block; problem is '', 'checksum',
    'zero length' or 'cut short'."""
    out, i = [], 0
    while i + 2 <= len(d):
        ln = d[i] | d[i + 1] << 8
        if ln == 0:
            out.append((None, b"", "zero length"))
            break
        b = d[i + 2:i + 2 + ln]
        x = 0
        for c in b:
            x ^= c
        prob = "cut short" if i + 2 + ln > len(d) else ("checksum" if x else "")
        out.append((b[0] if b else None, b, prob))
        i += 2 + ln
    return out


def read(path):
    with open(path, "rb") as f:
        return f.read()


def damage(d):
    """How many blocks are damaged, of how many."""
    bl = blocks(d)
    return sum(1 for b in bl if b[2]), len(bl)


def headers(d):
    """[(type, name, length, param1)] of the 2068 headers: 0 program, 3 bytes."""
    return [(b[1], b[2:12].decode("latin-1").rstrip(), b[12] | b[13] << 8, b[14] | b[15] << 8)
            for f, b, p in blocks(d) if f == 0 and len(b) == 19]


def has_program(d):
    return any(h[0] == 0 for h in headers(d))


def autoruns(d):
    """The first program header's LINE: below 32768 it starts by itself."""
    for h in headers(d):
        if h[0] == 0:
            return h[3] < 32768
    return True


# ---- load-test results ----

REPORTS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def report(r):
    """The 2068 report letter ('2', 'R', ...) left in ERR_NR, or None."""
    e = r.get("err")
    if e is None or e == 0xFF:
        return None
    return REPORTS[e + 1] if e + 1 < len(REPORTS) else str(e)


def classify(r):
    """OK: every block served. PARTIAL: running, the rest of the tape not asked
    for yet (a menu, the next part). LOOP: the 2068 kept asking for a file the
    tape doesn't have. *-ERR: stopped with a report."""
    if r.get("status"):
        return r["status"]
    if r.get("traceback"):
        return "FIRMWARE-EXC"
    rep = report(r)
    if rep == "R" or r.get("rtape"):
        return "R-TAPE"
    if rep == "T":
        return "T-RESET"
    if r["served"] == 0:
        return "NOTHING"
    if r["served"] > 2 * max(r["blocks"], 1) + 2:
        return "LOOP"
    if r["served"] < r["blocks"]:
        return "PARTIAL" + ("-ERR" if rep and rep not in "09" else "")
    if rep and rep not in "09":
        return "LOADED-ERR"
    return "OK"


def last_line(screen):
    lines = [x.strip() for x in (screen or "").splitlines() if x.strip()]
    return lines[-1] if lines else ""
