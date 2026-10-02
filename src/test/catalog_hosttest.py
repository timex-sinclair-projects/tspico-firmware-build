"""Host-side test for CAT / SAVE "tpi:dir <arg>" -- CPython, no Pico.

Two layers:

  * TS/catalog.py on its own: glob matching, path resolution (never above
    the public root), argument splitting, the TAP block table and the
    header-listing rows TAPDIR and CAT share.
  * The REAL TS.tspico DIR -> CATALOG path, against a temporary directory
    standing in for the SD card (/sd/TAP), with the SD/MQ switching and the
    message senders faked. What reaches SEND_MSG2 / SEND_MSG is checked.

What it pins down: bare DIR is still the cached listing; a pattern lists
every match with the index LOAD "tpi:n" uses (blank for files DIR does not
index); another directory lists without indices; a TAP lists its blocks
(headerless ones too); the mounted TAP uses its live table and position;
misses are Report F; and the SD is always handed back to the MQ.

Run:  python3 src/test/catalog_hosttest.py
"""

import io
import os
import shutil
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import process_cmd_hosttest as P                                # noqa: E402

results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg)


# ---------------------------------------------------------------------------
# TAP construction
# ---------------------------------------------------------------------------

def block(data):
    n = len(data)
    return bytes([n & 0xFF, n >> 8]) + data


def header(typ, name, length, p1=0, p2=0):
    body = bytes([0, typ]) + name.encode().ljust(10)[:10] + bytes(
        [length & 0xFF, length >> 8, p1 & 0xFF, p1 >> 8, p2 & 0xFF, p2 >> 8])
    x = 0
    for b in body:
        x ^= b
    return block(body + bytes([x]))


def data(payload):
    body = bytes([0xFF]) + payload
    x = 0
    for b in body:
        x ^= b
    return block(body + bytes([x]))


TAP = (header(0, "ADVENT", 100, 10, 100) + data(bytes(100)) +
       header(3, "ADVCODE", 300, 32768) + data(bytes(300)) +
       data(bytes(50)))                                     # headerless


# ---------------------------------------------------------------------------
# catalog.py on its own
# ---------------------------------------------------------------------------

def test_catalog(c):
    print("catalog.py")

    m = c.match
    check(m("GAME.TAP", "*.tap") and m("game.tap", "*.TAP"), "match: case-insensitive *")
    check(m("A", "*") and m("", "*") and not m("A", ""), "match: * alone, empty")
    check(m("CHESS.TAP", "?HESS.*") and not m("HESS.TAP", "?HESS.*"), "match: ? is exactly one")
    check(m("MANIC.TZX", "*a*i*") and not m("MANIC.TZX", "*a*z"), "match: several *")
    check(m("A.B.C", "*.c") and not m("ABC", "*.c"), "match: last dot")

    R = "/sd/TAP"
    check(c.resolve(R, "") == R, "resolve: '' is the current dir")
    check(c.resolve(R + "/GAMES", "arcade") == R + "/GAMES/arcade", "resolve: relative")
    check(c.resolve(R + "/GAMES", "..") == R, "resolve: .. up")
    check(c.resolve(R, "..") is None, "resolve: .. above the root is refused")
    check(c.resolve(R + "/GAMES", "/UTILS") == R + "/UTILS", "resolve: leading / is the root")
    check(c.resolve(R + "/GAMES", "/") == R, "resolve: / alone")
    check(c.resolve(R, "a/./b//c") == R + "/a/b/c", "resolve: . and // ignored")
    check(c.resolve("/flash", "x") is None, "resolve: a cwd outside the root is refused")
    check(c.public(R) == "/" and c.public(R + "/G") == "/G", "public path")

    check(c.split_arg("*.tap") == ("", "*.tap"), "split: bare pattern")
    check(c.split_arg("games/b*") == ("games", "b*"), "split: dir + pattern")
    check(c.split_arg("/*.tzx") == ("/", "*.tzx"), "split: root + pattern")
    check(c.split_arg("games") == ("games", None), "split: plain name")
    check(c.split_arg(" games/x.tap ") == ("games/x.tap", None), "split: strips spaces")

    check(c.size_text(900) == "900 B" and c.size_text(48213) == "47.00 kB",
          "size column matches LIST_DIR_FILES")

    tbl = c.tap_table(io.BytesIO(TAP))
    check(len(tbl) == 5, "tap_table: five blocks (%d)" % len(tbl))
    check(tbl[0][2] == " Y" and tbl[0][3] == "ADVENT    " and tbl[1][3] == "Program",
          "tap_table: header name, data block carries its type")
    check(tbl[2][3] == "ADVCODE   " and tbl[3][3] == "Code block" and tbl[3][1] == 302,
          "tap_table: code header and its data length")
    check([e[0] for e in tbl] == [0, 21, 125, 146, 450], "tap_table: offsets %r" % [e[0] for e in tbl])
    check(c.tap_table(io.BytesIO(b"")) == [], "tap_table: empty file")

    rows = "".join(c.tap_header_rows(tbl))
    check("ADVENT" in rows and "ADVCODE" in rows and "Data block" not in rows,
          "header rows: headers only by default (TAPDIR's behaviour)")
    rows = "".join(c.tap_header_rows(tbl, orphans=True))
    check("Data block     52 headerless" in rows, "header rows: orphans=True shows the headerless block, named so")
    rows = c.tap_header_rows(tbl, cur_idx=1)
    check(rows[0] == " " and ">" in rows and "Data block    102" in "".join(rows),
          "header rows: the position is marked, even on a data block")
    check(all(len(r) == 32 for r in
              ["".join(c.tap_header_rows(tbl, orphans=True)[i:i + 4])
               for i in range(0, len(c.tap_header_rows(tbl, orphans=True)), 4)]),
          "header rows: every row is 32 characters")

    dr = c.dir_rows([("SUB", True, 0), ("GAME.TAP", False, 48213), ("NOTES.TXT", False, 12)],
                    lambda n: 7 if n == "GAME.TAP" else None, lambda s, n: s[:n])
    check(dr[0].startswith("<SUB>") and dr[1].startswith("007 GAME.TAP") and
          dr[2].startswith("    NOTES.TXT"), "dir rows: dirs, indexed and unindexed files")
    check(all(len(r) == 32 for r in dr), "dir rows: every row is 32 characters")


# ---------------------------------------------------------------------------
# tspico.DIR -> CATALOG against a temp directory
# ---------------------------------------------------------------------------

class HostOS:
    """os for tspico, with /sd/TAP mapped onto a temp directory."""

    def __init__(self, root):
        self.root = root

    def real(self, p):
        """Resolve case-insensitively, as FAT does (CI's Linux FS does not)."""
        assert p.startswith("/sd/TAP"), p
        cur = self.root
        for part in p[len("/sd/TAP"):].split("/"):
            if not part:
                continue
            hits = [n for n in os.listdir(cur) if n.lower() == part.lower()] \
                if os.path.isdir(cur) else []
            cur = os.path.join(cur, hits[0] if hits else part)
        return cur

    def stat(self, p):
        st = os.stat(self.real(p))
        mode = 0x4000 if os.path.isdir(self.real(p)) else 0x8000
        return (mode, 0, 0, 0, 0, 0, st.st_size, 0, 0, 0)

    def ilistdir(self, p):
        for n in os.listdir(self.real(p)):
            full = os.path.join(self.real(p), n)
            if os.path.isdir(full):
                yield (n, 16384, 0, 0)
            else:
                yield (n, 32768, 0, os.path.getsize(full))


def test_dir(t, root):
    import TS.catalog
    global c_counts
    c_counts = TS.catalog.counts
    print("tspico DIR / CATALOG")

    hos = HostOS(root)
    sent = []
    sd = []

    t.os = hos
    t.open = lambda p, mode="r": open(hos.real(p), mode)
    t.ACTIVATE_SD = lambda *a, **k: sd.append("sd")
    t.DEACTIVATE_SD = lambda *a, **k: sd.append("off")
    t.ACTIVATE_MQ = lambda *a, **k: sd.append("mq")
    t.SEND_MSG2 = lambda msg, st, exp=True, colour=False: sent.append(("MSG2", msg, st))
    t.SEND_MSG = lambda msg, msg1, st, force=False: sent.append(("MSG", msg, st))
    t.CAT_COLOUR = lambda text: text           # the plain listing; its colours: screen_colour_hosttest
    t.led = types.SimpleNamespace(value=lambda *a: None)
    t.LOG = lambda *a: None
    t.TSP = types.SimpleNamespace(cur_path="/sd/TAP", f_name="", offset_tbl=[], tap_idx=0,
                                  VERBOSE=False, LOG_LEVEL=2)
    t.files = ["ADVENT.TAP", "CHESS.TAP", "MANIC.TZX"]          # what DIR_FILES indexed
    t.lista = "CACHED-LISTA"
    pre0 = bytearray(10)

    def run(cmd, pre=pre0):
        del sent[:]
        del sd[:]
        t.DIR(pre, "xxx" + cmd)
        return sent[-1] if sent else None

    r = run("tpi:dir")
    check(r == ("MSG2", "CACHED-LISTA", t._1_OK) and sd == ["sd", "off", "mq"],
          "bare tpi:dir: looks at the card once (a swap or a pulled card shows), "
          "then the cached listing (%r)" % sd)

    def no_card(*a, **k):
        sd.append("sd")
        raise OSError(19, "no SD card")
    t.ACTIVATE_SD = no_card
    r = run("tpi:dir")
    check(r == ("MSG", t.NO_CARD_MSG, t._10_J_Invalid_IO),
          "bare tpi:dir, card taken out: the no-card answer, not the old card's files")
    t.ACTIVATE_SD = lambda *a, **k: sd.append("sd")

    r = run("tpi:dir *.tap")
    check(r[0] == "MSG2" and r[2] == t._1_OK, "tpi:dir *.tap: OK")
    body = r[1]
    check("000 ADVENT.TAP" in body and "001 CHESS.TAP" in body and "MANIC" not in body,
          "tpi:dir *.tap: matches with the LOAD \"tpi:n\" index")
    check("*.tap: 2 files, 0 dirs" in body, "tpi:dir *.tap: count line")
    check("*: 4 files, 2 dirs" in run("tpi:dir *")[1] and c_counts(1, 1) == "1 file, 1 dir", "count line: plurals")
    check(sd == ["sd", "off", "mq"], "SD activated, then handed back to the MQ (%r)" % sd)
    check(len(body) % 32 == 0, "listing is whole 32-character rows (%d)" % len(body))

    body = run("tpi:dir *")[1]
    check("    README.TXT" in body and "<GAMES>" in body and ".hidden" not in body,
          "tpi:dir *: every match, unindexed non-TAP, dirs, no dotfiles")
    check("dirinfo" not in body, "tpi:dir *: dirinfo.tap never listed")

    body = run("tpi:dir games")[1]
    check("Path:/games" in body and "    ARCADE.TAP" in body, "tpi:dir games: another dir, no indices")
    with open(os.path.join(root, "GAMES", "AAA.TXT"), "wb") as f:
        f.write(b"t")
    body = run("tpi:dir games")[1]
    check(body.find("    AAA.TXT") > body.find("    ARCADE.TAP") > 0,
          "tpi:dir games: other files after the DIR types, like bare DIR")
    os.remove(os.path.join(root, "GAMES", "AAA.TXT"))

    body = run("tpi:dir /games/*.t*")[1]
    check("ARCADE.TAP" in body and "Path:/games" in body, "tpi:dir /games/*.t*: absolute path + pattern")

    r = run("tpi:dir advent.tap")
    check(r[0] == "MSG2" and "File:/advent.tap" in r[1] and "5 blocks" in r[1],
          "tpi:dir advent.tap: its block listing")
    check("ADVENT" in r[1] and "ADVCODE" in r[1] and "Data block     52" in r[1] and ">" not in r[1],
          "tpi:dir advent.tap: headers + headerless block, no position mark")

    t.TSP.f_name = "/sd/TAP/ADVENT.TAP"
    t.TSP.offset_tbl = [[0, 19, " Y", "LIVE      "], [21, 5, " N", "Program"]]
    t.TSP.tap_idx = 1
    r = run("tpi:dir ADVENT.TAP")
    check("LIVE" in r[1] and "mounted" in r[1] and ">01" in r[1],
          "the mounted TAP: live table and the position")
    t.TSP.f_name = ""

    r = run("tpi:dir manic.tzx")
    check(r[0] == "MSG2" and "002 MANIC.TZX" in r[1], "one file typed in lower case: stored name, with index")

    for arg, what in (("*.dck", "no match"), ("nothere", "missing name"),
                      ("../..", "above the root"), ("advent.tap/*", "pattern under a file"),
                      ("empty", "an empty directory")):
        r = run("tpi:dir " + arg)
        check(r[0] == "MSG" and r[2] == t._3_F_Invalid_file,
              "%s -> Report F (%r)" % (what, r[1]))
        check(sd == ["sd", "off", "mq"], "%s: SD still handed back" % what)

    t.TSP.cur_path = "/sd/TAP/GAMES"
    body = run("tpi:dir *")[1]
    check("000 ARCADE.TAP" not in body and "    ARCADE.TAP" in body,
          "cwd GAMES: indices only for names in files[] (none here)")
    body = run("tpi:dir ../*.tzx")[1]
    check("002 MANIC.TZX" not in body and "MANIC.TZX" in body,
          "../*.tzx lists the parent, unindexed (files[] is the cwd's)")
    t.TSP.cur_path = "/sd/TAP"

    pre = bytearray(10)
    pre[3] = 2                                                   # CODE 2,0 still the old path
    r = run("tpi:dir", pre)
    check(r[0] == "MSG2" and "ADVENT.TAP" in r[1] and "  #  File Name" in r[1],
          "CODE 2,0 unchanged")


def main():
    P.install_fakes()
    ext = types.ModuleType("dev_extcmd")
    ext.EXT_SA_FUNCT = {}
    sys.modules["dev_extcmd"] = ext
    import TS.catalog as c
    import TS.tspico as t
    t.TLM_ENABLED = False

    test_catalog(c)

    root = tempfile.mkdtemp(prefix="cat_hosttest.")
    try:
        with open(os.path.join(root, "ADVENT.TAP"), "wb") as f:
            f.write(TAP)
        for n, size in (("CHESS.TAP", 16384), ("MANIC.TZX", 40960), ("README.TXT", 12),
                        (".hidden", 1), ("dirinfo.tap", 64)):
            with open(os.path.join(root, n), "wb") as f:
                f.write(bytes(size))
        os.mkdir(os.path.join(root, "GAMES"))
        os.mkdir(os.path.join(root, "EMPTY"))
        with open(os.path.join(root, "GAMES", "ARCADE.TAP"), "wb") as f:
            f.write(bytes(10))
        test_dir(t, root)
    finally:
        shutil.rmtree(root)

    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
