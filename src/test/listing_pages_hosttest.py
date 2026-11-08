"""Host-side test for the listing made as it is read (#384) -- CPython, no Pico.

lista was a str: every row of the folder, 32 characters each (9.7K for 300
files), kept until the next listing; CAT's colored copy of it, made by
CAT_COLOUR for every CAT, was a second block the size of it (12.1K), and a
300-file folder on the v3 card could not find one. Now lista is a DirText:
DIR_HEADER and INDEX, with each row made when it is read, and CAT_COLOUR of
it is a DirColour, colored the same way, also a row at a time.

What it pins:
  * DirColour reads, character for character, as CAT_COLOUR of the plain
    text: the header, folder rows, numbered rows, other rows, the "and n
    more" row and NORMAL_; its length and its count of line ends (none);
  * SEND_MSG2 sends the 2068 exactly the same bytes for a DirColour as for
    CAT_COLOUR's str: every page, the Scroll? prompts and their
    percentages, the erase sequences, the end of the loop; for a page
    count of 1, 2 and 15, with the keys Y, a digit and N at the prompts;
  * DirText's row cache: reading a page reads each row once.

Run:  python3 src/test/listing_pages_hosttest.py
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


def folder(rng, nd, nf, no):
    out, seen = [], set()
    while len(out) < nd + nf + no:
        k = len(out)
        if k < nd:
            e = ("Dir%d_%s" % (rng.randint(0, 999), "x" * rng.randint(0, 25)), 16384, 0, 0)
        elif k < nd + nf:
            e = ("g%d%s.%s" % (rng.randint(0, 99999), "y" * rng.randint(0, 20), rng.choice(["tap", "TZX", "dck"])),
                 32768, 0, rng.randint(0, 3000000))
        else:
            e = ("note%d.txt" % rng.randint(0, 9999), 32768, 0, rng.randint(0, 99999))
        if e[0].lower() not in seen:
            seen.add(e[0].lower())
            out.append(e)
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
    t.TSP = types.SimpleNamespace(cur_path="/sd/TAP", LOG_LEVEL=0, sd_label="", ROM_VERSION="2.3")
    rng = random.Random(384)

    def listed(items, index=None):
        if index is not None:
            t.INDEX = index
        t.os = FakeOS(items)
        t.LIST_DIR_FILES()
        return t.lista

    saved = t.INDEX
    shapes = [("300 files, 14 folders, 5 others", folder(rng, 14, 300, 5), None),
              ("folders only", folder(rng, 6, 0, 0), None),
              ("one file", folder(rng, 0, 1, 0), None),
              ("others only", folder(rng, 0, 0, 4), None),
              ("too many: 40 of 60 and a row that says so", folder(rng, 5, 50, 5), C.Index(40, 8192))]
    for label, items, index in shapes:
        dt = listed(items, index)
        plain = dt.text()
        want = t.CAT_COLOUR(plain)                                   # the str path, as it always was
        dc = t.CAT_COLOUR(dt)
        check(isinstance(dt, t.DirText) and isinstance(dc, t.DirColour) and isinstance(want, str),
              "%s: lista is a DirText, CAT_COLOUR of it a DirColour" % label)
        check(len(dc) == len(want) and all(dc[i] == want[i] for i in range(len(want))),
              "  ... which reads as CAT_COLOUR of the plain text, all %d characters" % len(want))
        check(dc.count("\r", 5) == want.count("\r", 5) == 0 and dc.count("\n") == 0 and dc.count("\r\n") == 0,
              "  ... and holds no line end, as SEND_MSG2's prompt test asks")
        t.INDEX = saved

    # SEND_MSG2: the same bytes to the 2068
    sent = []
    keys = []
    t.CMD_SEND = lambda buf, ready: sent.append(bytes(buf))
    t.CMD_KEY = lambda: keys.pop(0)
    t.CMD_RX_FLUSH = lambda: None
    t.CMD_DRAIN = lambda: None
    t.TLM = lambda *a, **k: None
    t.MQ = types.SimpleNamespace(rx_fifo=lambda: 0, get=lambda: 0)

    def out(msg, ks):
        del sent[:]
        keys[:] = list(ks)
        t.SEND_MSG2(msg, t._1_OK, False, True)
        return list(sent)

    for label, items, ks in (("one page (6 rows)", folder(rng, 1, 4, 1), []),
                             ("two pages", folder(rng, 2, 30, 0), [ord("y")]),
                             ("300 files, Y at every prompt", folder(rng, 14, 300, 5), [ord("y")] * 20),
                             ("300 files, 5 then Y", folder(rng, 3, 300, 0), [ord("5")] + [ord("y")] * 70),
                             ("300 files, N at the second prompt", folder(rng, 3, 300, 0), [ord("y"), ord("n")])):
        dt = listed(items)
        a = out(t.CAT_COLOUR(dt.text()), ks)
        b = out(t.CAT_COLOUR(dt), ks)
        check(a == b and len(a) >= 1, "SEND_MSG2, %s: the same %d page(s), byte for byte" % (label, len(a)))

    # A page reads each row once
    dt = listed(folder(rng, 0, 40, 0))
    made = []
    real = t.DirText.row
    t.DirText.row = lambda self, r: made.append(r) or real(self, r)
    try:
        dc = t.CAT_COLOUR(dt)
        for i in range(len(dc)):
            dc[i]
    finally:
        t.DirText.row = real
    check(made == list(range(40)), "reading the whole listing in order makes each of its 40 rows once")

    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
