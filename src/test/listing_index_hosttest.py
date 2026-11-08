"""Host-side test for the folder index (#384) -- CPython, no Pico.

LIST_DIR_FILES used to keep the folder as one str per name in files[] and
dirs[], made in the same pass as the listing's garbage and spread over the
heap with it. It now fills INDEX (catalog.Index): buffers made once, at
import, holding the names packed as UTF-8, their sizes, and where each kind
starts. files and dirs are Views of it.

What it pins:
  * the listing (files, dirs, lista) is exactly what the old code gave, on
    generated folders: mixed case, non-ASCII names, dot files, dirinfo.tap,
    folders only, files only, empty, already in order and not;
  * the Views act as the lists did: len, [i], [-1], iteration, enumerate,
    ==, `in`, and an IndexError past the end;
  * a folder that doesn't fit lists what fits, in order and with no gap in
    the numbers, and says how many more there are;
  * INDEX is made once: a listing makes no new buffers.

The old code is kept here as it was on main cec98f4.

Run:  python3 src/test/listing_index_hosttest.py
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


class FakeOS:
    def __init__(self, items):
        self.items = items

    def ilistdir(self, *a):
        return iter(list(self.items))

    def statvfs(self, p):
        return (4096, 4096, 500000, 300000, 300000, 0, 0, 0, 0, 255)

    def chdir(self, p):
        pass


def old_listing(t, catalog, items):
    """main cec98f4's LIST_DIR_FILES, its rows and lists, from the items."""
    files, dirs, L = [], [], []
    ext = catalog.DIR_EXT
    listing = catalog.sort_items(iter(items))
    for a in listing:
        if a[1] == 16384:
            dirs.append(a[0])
            L.append("<%-21s       0 B" % (t.shorten_filename(catalog.screen_name(a[0]), 20) + ">"))
    i = 0
    for a in listing:
        if a[1] == 32768:
            if (a[0][-3:].upper() not in ext) or (a[0][0] in ".") or a[0] == "dirinfo.tap":
                continue
            files.append(a[0])
            L.append("%03d %-18s%10s" % (i, t.shorten_filename(catalog.screen_name(a[0]), 18),
                                         catalog.size_text(int(a[3]))))
            i += 1
    for a in listing:
        if a[1] == 32768 and a[0][-3:].upper() not in ext and a[0][0] != "." and a[0] != "dirinfo.tap":
            L.append("    %-18s%10s" % (t.shorten_filename(catalog.screen_name(a[0]), 18),
                                        catalog.size_text(int(a[3]))))
    return files, dirs, "".join(L) if L else "Directory is empty\r"


def folder(rng, nd, nf, no, extra=()):
    names = set()
    out = []
    while len(out) < nd:
        n = rng.choice(["Games", "util", "Zeta", "a", "Sub"]) + str(rng.randint(0, 999))
        if n.lower() not in names:
            names.add(n.lower())
            out.append((n, 16384, 0, 0))
    while len(out) < nd + nf:
        n = "%s%d.%s" % (rng.choice(["game", "Jet", "caf\xe9", "x{y}", "LONG_NAME_OF_A_GAME"]),
                         rng.randint(0, 9999), rng.choice(["tap", "TAP", "tzx", "dck", "Rom", "bin"]))
        if n.lower() not in names:
            names.add(n.lower())
            out.append((n, 32768, 0, rng.randint(0, 3000000)))
    while len(out) < nd + nf + no:
        n = "note%d.%s" % (rng.randint(0, 9999), rng.choice(["txt", "md", "bas", "z80"]))
        if n.lower() not in names:
            names.add(n.lower())
            out.append((n, 32768, 0, rng.randint(0, 99999)))
    out += list(extra)
    rng.shuffle(out)
    return out


def main():
    import process_cmd_hosttest as P
    P.install_fakes()
    ext = types.ModuleType("dev_extcmd")
    ext.EXT_SA_FUNCT = {}
    sys.modules["dev_extcmd"] = ext
    import TS.tspico as t
    from TS import catalog as C
    t.TSP = types.SimpleNamespace(cur_path="/sd/TAP", LOG_LEVEL=0, sd_label="")
    rng = random.Random(384)

    junk = [(".hidden.tap", 32768, 0, 5), ("dirinfo.tap", 32768, 0, 700), ("._game.tap", 32768, 0, 4096),
            (".Spotlight-V100", 16384, 0, 0)]
    cases = {
        "300 files, 14 folders, 5 others": folder(rng, 14, 300, 5),
        "a mixed folder with dot files and dirinfo.tap": folder(rng, 3, 40, 6, junk),
        "folders only": folder(rng, 9, 0, 0),
        "files only": folder(rng, 0, 25, 0),
        "others only": folder(rng, 0, 0, 7),
        "empty": [],
        "only things left out": [(".x.tap", 32768, 0, 1), ("dirinfo.tap", 32768, 0, 1)],
        "already in order": sorted(folder(rng, 2, 60, 2), key=lambda e: (e[1] != 16384, e[0].lower())),
    }
    buffers = (id(t.INDEX.names), id(t.INDEX.off), id(t.INDEX.size))
    for label, items in cases.items():
        t.os = FakeOS(items)
        t.LIST_DIR_FILES()
        want_files, want_dirs, want_rows = old_listing(t, C, items)
        check(list(t.files) == want_files and list(t.dirs) == want_dirs and t.lista[128:] == want_rows,
              "%s: files, dirs and lista as before" % label)
    check((id(t.INDEX.names), id(t.INDEX.off), id(t.INDEX.size)) == buffers,
          "every listing used the same buffers, made at import")

    # The Views act as the lists did
    items = folder(rng, 4, 30, 2)
    t.os = FakeOS(items)
    t.LIST_DIR_FILES()
    want, wdirs, _ = old_listing(t, C, items)
    f = t.files
    check(len(f) == 30 and f[0] == want[0] and f[29] == want[29] and f[-1] == want[-1],
          "files: len, [0], [29] and [-1]")
    check([n for n in f] == want and list(enumerate(f)) == list(enumerate(want)),
          "files: iteration and enumerate")
    check(f == want and want[3] in f and "nothere.tap" not in f, "files: == a list, and `in`")
    try:
        f[30]
        past = False
    except IndexError:
        past = True
    check(past, "files[30] of 30: IndexError")
    check([f.size(i) for i in range(30)] == [dict((e[0], e[3]) for e in items)[n] for n in want],
          "files.size(i): each file's size")
    check(list(t.dirs) == wdirs and ["..", ] + list(t.dirs) == [".."] + wdirs,
          "dirs: the folders (CDIR's menu takes list(dirs))")

    # A folder that doesn't fit
    saved = t.INDEX
    t.INDEX = C.Index(20, 4096)
    items = folder(rng, 5, 40, 3)
    t.os = FakeOS(items)
    t.LIST_DIR_FILES()
    want, wdirs, _ = old_listing(t, C, items)
    check(list(t.dirs) == wdirs and list(t.files) == want[:15] and t.INDEX.more == 28,
          "20 entries' room, 48 entries: the 5 folders and the first 15 files, 28 more")
    rows = t.lista[128:]
    check(rows.count("\x00") == 0 and "014 " in rows and "015 " not in rows
          and rows.endswith("%-32s" % "    and 28 more not listed"),
          "... numbered 000-014, then a row that says 28 more")
    t.INDEX = C.Index(100, 60)
    t.os = FakeOS([("aa.tap", 32768, 0, 1), ("b" * 55 + ".tap", 32768, 0, 1), ("cc.tap", 32768, 0, 1)])
    t.LIST_DIR_FILES()
    check(list(t.files) == ["aa.tap"] and t.INDEX.more == 2,
          "60 bytes of names: a long name doesn't fit, and nothing after it is listed either")
    t.INDEX = saved

    # catalog.kind_of: LIST_DIR_FILES' rule
    k = C.kind_of
    check([k(("x.TAP", 32768)), k(("x.txt", 32768)), k((".x.tap", 32768)), k(("dirinfo.tap", 32768)),
           k((".git", 16384)), k(("x.tap", 4096))] == [C.FILE, C.OTHER, None, None, C.DIR, None],
          "kind_of: numbered, other, dot file, dirinfo.tap, dot folder, neither file nor folder")

    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
