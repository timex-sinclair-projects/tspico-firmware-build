"""Host-side test for the listing-text rewrites (#384) -- CPython, no Pico.

The listing path made far more short-lived strings than it needed, which
spreads the kept objects across the Pico's non-moving heap:
  * CAT_COLOUR and TAPDIR_COLOUR took a row with `rest = rest[32:]`,
    copying the rest of the listing for every row;
  * every listing sorted with sorted(key=...), and MicroPython calls the
    key on every comparison (45,149 lowered strings for a 300-file folder
    in name order, 1.58 s on the v3 card);
  * screen_name rebuilt every name a character at a time;
  * CATALOG_TEXT made an upper-case copy of files[] and searched it twice
    per row;
  * the ZX48 tpi:dir reply grew a byte at a time and copied every piece.

The rewrites must give exactly what the old code gave. The old code is
kept here, as it was on main 1d08839, and compared on generated listings.

Run:  python3 src/test/listing_text_hosttest.py
"""

import os
import random
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, SRC)

results = []


def check(cond, msg):
    results.append(bool(cond))
    print("%s  %s" % ("PASS" if cond else "FAIL", msg))


# ─── The old code (main 1d08839) ───────────────────────────────────────────
INK_ = "\x10"
PAPER_ = "\x11"
NORMAL_ = PAPER_ + "\x08" + INK_ + "\x08"
BLUE_ = PAPER_ + "\x07" + INK_ + "\x01"
PLAIN_ = PAPER_ + "\x08" + INK_ + "\x09"
UNSHOWABLE = "{|}~\x7f"


def old_screen_name(s):
    return "".join("?" if (c < " " or c > "~" or c in UNSHOWABLE) else c for c in s)


def old_cat_colour(text):
    if not text.startswith("Path:") or len(text) < 128:
        return text
    out = [PAPER_ + "\x01" + INK_ + "\x07" + text[0:64],
           PAPER_ + "\x05" + INK_ + "\x09" + text[64:96]]
    rest = text[128:]
    while len(rest) >= 32:
        row = rest[:32]
        if row[0] == "<":
            out.append(PLAIN_ + row[:22] + "%10s" % "folder")
        elif row[:3].isdigit() and row[3] == " ":
            out.append(PAPER_ + "\x05" + INK_ + "\x09" + row[:3] + PLAIN_ + row[3:])
        elif row[:4] == "    ":
            out.append(PLAIN_ + row)
        else:
            break
        rest = rest[32:]
    out.append((PLAIN_ + rest if rest else "") + NORMAL_)
    return "".join(out)


def old_tapdir_colour(text, headers):
    if not text.startswith("File:") or len(text) < 128:
        return text
    out = [PAPER_ + "\x01" + INK_ + "\x07" + text[0:64],
           PAPER_ + "\x05" + INK_ + "\x09" + text[64:96]]
    rest = text[128:]
    while len(rest) >= 32 and rest[0] in " >" and rest[1:3].isdigit():
        row = rest[:32]
        if row[0] == ">":
            out.append(PAPER_ + "\x06" + INK_ + "\x09" + row)
        else:
            hdr = ("Data block" not in row[4:15]) if headers else row[18:20] == " Y"
            out.append(PLAIN_ + row[0] + PAPER_ + "\x05" + INK_ + "\x09" + row[1:3]
                       + (BLUE_ if hdr else PLAIN_) + row[3:])
        rest = rest[32:]
    out.append((PLAIN_ + rest if rest else "") + NORMAL_)
    return "".join(out)


def old_pieces(text):
    parts = []
    i = 0
    while i < len(text):
        j = i + 255
        if j < len(text):
            k = text.rfind(b"\x11", i + 1, j + 1)
            if k >= 0:
                j = k
        parts.append(text[i:j])
        i = j
    out = bytearray(1 + len(text) + len(parts) + 1)
    j = 1
    for part in parts:
        out[j] = len(part)
        out[j + 1:j + 1 + len(part)] = part
        j += 1 + len(part)
    out[j] = 0
    return out


# ─── Listings to compare on ────────────────────────────────────────────────
def header(first="Path:"):
    return ("%-32s" % (first + "/games")) + ("%-32s" % "SD 1.9 GB, 1.2 GB free") \
        + ("%-32s" % "File Name                   Size") + "-" * 32


def dir_listing(rng, ndirs, nfiles, nother, tail=""):
    rows = ["<%-21s       0 B" % ("dir%d>" % k) for k in range(ndirs)]
    rows += ["%03d %-18s%10s" % (k, "game%d.tap" % k, "%d B" % rng.randint(1, 60000)) for k in range(nfiles)]
    rows += ["    %-18s%10s" % ("note%d.txt" % k, "1 K") for k in range(nother)]
    return header() + "".join(rows) + tail


def tap_listing(rng, nblocks, nxt, tail=""):
    rows = []
    for k in range(nblocks):
        kind = rng.choice(["Program     ", "Code block  ", "Data block  "])
        y = rng.choice([" Y", " N"])
        rows.append(("%s%02d %s %5d %-8s%s" % (">" if k == nxt else " ", k, kind, rng.randint(1, 9999),
                                               "name%d" % k, y))[:32].ljust(32))
    return header("File:") + "".join(rows) + tail


def main():
    import process_cmd_hosttest as P
    P.install_fakes()
    ext = types.ModuleType("dev_extcmd")
    ext.EXT_SA_FUNCT = {}
    sys.modules["dev_extcmd"] = ext
    import TS.tspico as t
    from TS import catalog as C

    rng = random.Random(384)

    # screen_name: the fast path changes nothing
    names = ["game.tap", "{game}.tap", "jet~1.tap", "caf\xe9.tap", "a|b", "x\x7f", "", "  ", "UPPER.TZX"]
    names += ["".join(chr(rng.randint(0x20, 0x7f)) for _ in range(rng.randint(1, 20))) for _ in range(300)]
    check(all(C.screen_name(n) == old_screen_name(n) for n in names),
          "screen_name: the same as before on %d names" % len(names))
    plain = "game.tap"
    check(C.screen_name(plain) is plain, "screen_name: a name with nothing to replace comes back as it is")

    # sort_items: the order sorted(key=lower) gave
    def items(ns):
        return [(n, 32768, 0, 100) for n in ns]
    cases = {
        "in order": items("g%03d.tap" % i for i in range(300)),
        "reversed": items("g%03d.tap" % i for i in range(300, 0, -1)),
        "shuffled": items(rng.sample(["G%03d.TAP" % i for i in range(150)] + ["h%03d.tap" % i for i in range(150)], 300)),
        "mixed case": items(["b.tap", "A.tap", "c.TAP", "B2.tap", "a2.TAP"]),
        "one": items(["x.tap"]),
        "empty": [],
    }
    for label, its in cases.items():
        want = sorted(its, key=lambda it: it[0].lower())
        got = C.sort_items(iter(its))
        check(got == want, "sort_items, %s: the order sorted(key=lower) gives" % label)
    # an ordered folder is not sorted at all: the one sort call is after the order test
    src = open(os.path.join(SRC, "TS", "catalog.py")).read()
    body = src[src.index("def sort_items"):src.index("\n\n\n", src.index("def sort_items"))]
    check(body.count(".sort(") == 1 and "break" in body.split(".sort(")[1][:30],
          "sort_items sorts only when it finds two names out of order")
    ts = open(os.path.join(SRC, "TS", "tspico.py")).read()
    check("key=lambda" not in ts, "tspico.py sorts no listing with sorted(key=...)")
    check("key=lambda" not in src, "catalog.py neither")

    # CAT_COLOUR and TAPDIR_COLOUR
    texts = [dir_listing(rng, d, f, o, tail) for d, f, o, tail in
             ((0, 0, 0, ""), (3, 10, 2, ""), (14, 300, 5, ""), (1, 1, 0, "Directory is empty\r"),
              (0, 5, 0, "xyz"), (2, 0, 1, "trailing text of 40 characters, not a row"))]
    texts += [header() + "Directory is empty\r", "No match for *.zzz", header()[:100], ""]
    check(all(t.CAT_COLOUR(x) == old_cat_colour(x) for x in texts),
          "CAT_COLOUR: the same as before on %d listings" % len(texts))
    taps = [tap_listing(rng, n, nxt, tail) for n, nxt, tail in
            ((0, None, "<empty file>\r"), (3, 1, ""), (40, 0, ""), (99, 50, "tail"))]
    taps += ["File:short", header("File:")]
    check(all(t.TAPDIR_COLOUR(x, h) == old_tapdir_colour(x, h) for x in taps for h in (False, True)),
          "TAPDIR_COLOUR: the same as before on %d listings, both views" % len(taps))
    check("\n        rest = rest[32:]" not in ts.replace("\r\n", "\n"), "no listing copies its rest a row at a time")

    # ZX_PIECES
    blobs = [b"", b"x", b"a" * 254, b"a" * 255, b"a" * 256, b"b" * 1000]
    for _ in range(40):
        n = rng.randint(1, 3000)
        blobs.append(bytes(rng.choice(b"\x11\x10abc 0123") for _ in range(n)))
    listing = t.CAT_COLOUR(dir_listing(rng, 14, 300, 5)).encode()
    blobs.append(listing)
    check(all(t.ZX_PIECES(b) == old_pieces(b) for b in blobs),
          "ZX_PIECES: the same reply as before on %d texts (a 300-file CAT among them)" % len(blobs))

    # CATALOG_TEXT's index numbers: files[] order, exact names, any order of lookups
    t.files = ["g%03d.tap" % i for i in range(300)]
    src_t = ts.replace("\r\n", "\n")
    seg = src_t[src_t.index("    at = [0]\n"):src_t.index("        return None\n", src_t.index("    at = [0]\n"))
                + len("        return None\n")]
    ns = {"files": t.files}
    for here in (True, False):
        code = "def make(files, here):\n" + "".join(l + "\n" for l in seg.split("\n")) \
               + "    return index_of\n"
        exec(code, ns)
        idx = ns["make"](t.files, here)
        order = list(range(300)) + rng.sample(range(300), 300) + [5, 5, 299, 0]
        if here:
            check(all(idx(t.files[k]) == k for k in order),
                  "CATALOG_TEXT index_of: every file's place in files[], in order and out of order")
            check(idx("nothere.tap") is None and idx("G000.TAP") is None,
                  "... None for a name not in files[] (the names match exactly)")
        else:
            check(all(idx(t.files[k]) is None for k in range(10)), "... and None in another folder")

    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
