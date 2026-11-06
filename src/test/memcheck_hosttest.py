"""Host-side test for tpi:meminfo and tools/memcheck.py (#384) -- CPython, no Pico.

  * LARGEST_BLOCK finds the biggest bytearray a heap will give, to MEM_STEP
    bytes, against a fake heap whose largest block is smaller than its free
    total (the fragmented case it exists for);
  * MEMINFO collects first, prints one MEM line with the numbers and the
    listing sizes, logs it, prints the heap map only when asked ("map"), and
    answers the 2068 with one forced message;
  * memcheck.py reads MEM lines and mem_info(1) maps (the free runs, the
    "(n lines all free)" lines, the object kinds), and builds the files
    memtest.bas reads: memcfg.tap's layout, memtape.tap's blocks, the .DCK.

Run:  python3 src/test/memcheck_hosttest.py
"""

import io
import os
import sys
import tempfile
import types
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import process_cmd_hosttest as P                                # noqa: E402
import disk_cmds_hosttest as D                                  # noqa: E402

results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg)


class FakeHeap:
    """gc and bytearray for a heap with `free` bytes free in all, the
    biggest piece `largest` bytes."""

    def __init__(self, free, largest):
        self.free, self.largest = free, largest
        self.collects = 0
        self.asks = []

    def collect(self):
        self.collects += 1

    def mem_free(self):
        return self.free

    def mem_alloc(self):
        return 200_000 - self.free

    def bytearray(self, n=0):
        self.asks.append(n)
        if n > self.largest:
            raise MemoryError
        return b""


def test_largest(t):
    print("LARGEST_BLOCK")
    real_gc = t.gc
    try:
        for free, largest in ((190_000, 113_000), (190_000, 52_000), (60_000, 60_000), (300, 0)):
            h = FakeHeap(free, largest)
            t.gc, t.bytearray = h, h.bytearray
            got = t.LARGEST_BLOCK()
            check(largest - t.MEM_STEP < got <= largest and got % 16 == 0,
                  "free %d, largest %d: finds %d (within %d)" % (free, largest, got, t.MEM_STEP))
            check(len(h.asks) <= 12, "  in %d tries" % len(h.asks))
    finally:
        t.gc = real_gc
        del t.bytearray


def test_meminfo(t, sent):
    print("tpi:meminfo")
    real_gc = t.gc
    logged = []
    t.LOG = lambda m, lvl: logged.append((m, lvl))
    h = FakeHeap(150_000, 52_000)
    t.gc, t.bytearray = h, h.bytearray
    t.files, t.dirs, t.alldirs, t.lista = ["a"] * 7, ["d"] * 2, ["/TAP"] * 3, "x" * 99
    t.TSP.offset_tbl = [[0, 1, " Y", "n"]] * 5
    maps = []
    mp = types.ModuleType("micropython")
    mp.mem_info = lambda *a: maps.append(a)
    sys.modules["micropython"] = mp
    try:
        del sent[:]
        out = io.StringIO()
        with redirect_stdout(out):
            t.MEMINFO(bytearray(10), "D..tpi:meminfo r1_mount")
        line = out.getvalue().strip()
        check(line.startswith("MEM tag=r1_mount free=150000 alloc=50000 largest=5"),
              "one MEM line: tag, free, alloc, largest (%r)" % line[:70])
        check(" files=7 dirs=2 alldirs=3 lista=99 blocks=5 " in line, "the listing sizes and the block table")
        check(h.collects >= 1, "collects before it measures")
        check(logged and logged[0][0] == line and logged[0][1] == 4, "the same line in the log, at level 4")
        check(not maps, "no heap map unless asked")
        check(sent[-1][0] == "MSG" and sent[-1][1] == "Free 146K, largest %dK" % (t.LARGEST_BLOCK() >> 10)
              and sent[-1][2] == "r1_mount" and sent[-1][3] == t._1_OK, "the 2068 gets free and largest (%r)" % (sent[-1],))

        out = io.StringIO()
        with redirect_stdout(out):
            t.MEMINFO(bytearray(10), "D..tpi:meminfo start MAP")
        text = out.getvalue()
        check("MEM tag=start " in text and maps == [(1,)], "\"map\" (any case) is not the tag, and asks for mem_info(1)")
        check("MEM map begin tag=start" in text and "MEM map end tag=start" in text, "between begin and end lines")

        out = io.StringIO()
        with redirect_stdout(out):
            t.MEMINFO(bytearray(10), "D..tpi:meminfo")
        check("MEM tag=- " in out.getvalue(), "no tag: '-'")
    finally:
        t.gc = real_gc
        del t.bytearray
        sys.modules.pop("micropython", None)
    check("TPI:MEMINFO" in t.SD_FREE, "works without the SD card")


_L1 = "hTh=LD=S==S=" + "." * 5 + "A" + "=" * 7 + "h=h="
_L4 = "." * 6 + "SS" + "." * 46 + "h" + "=" * 9
SAMPLE_MAP = ["stack: 1060 out of 7936",
              "GC: total: 4096, used: 640, free: 3456, max new split: 0",
              " No. of 1-blocks: 6, 2-blocks: 2, max blk sz: 10, max free sz: 169",
              "GC memory layout; from 20012340:",
              "00000000: " + _L1 + "." * (64 - len(_L1)),
              "00000400: " + "." * 64,
              "       (1 lines all free)",
              "00000c00: " + _L4]


def test_parse():
    import memcheck as M
    print("memcheck.py: reading the console")
    r = M.parse_mem("junk MEM tag=r2_save free=1000 alloc=2 largest=512 files=3 dirs=0 alldirs=1 lista=9 blocks=62 ms=7")
    check(r == {"tag": "r2_save", "free": 1000, "alloc": 2, "largest": 512, "files": 3, "dirs": 0,
                "alldirs": 1, "lista": 9, "blocks": 62, "ms": 7}, "a MEM line (%r)" % (r,))
    check(M.parse_mem("MEM map begin tag=x") is None, "not the map's begin line")
    s = M.parse_map(SAMPLE_MAP)
    check(s["header"].get("max free sz") == 169 and s["header"].get("total") == 4096, "the header's numbers")
    check(s["cells"] == 4 * 64, "every line, with an all-free line as 64 blocks (%d)" % s["cells"])
    check(s["free_runs"][:3] == [35 + 64 + 64 + 6, 46, 5], "free runs join across lines (%r)" % s["free_runs"][:3])
    check(s["objects"].get("str/bytes") == 4 and s["blocks"].get("str/bytes") == 7, "strings: 4 objects, 7 blocks")
    check(s["objects"].get("bytearray") == 1 and s["blocks"].get("bytearray") == 8, "a bytearray with its tail")
    check(s["blocks"].get("other") == 3 + 4 + 10 and s["blocks"].get("dict") == 2, "plain heads and a dict with their tails")
    lines = ["MEM tag=start free=10 alloc=1 largest=8 files=0 dirs=0 alldirs=0 lista=0 blocks=0 ms=1",
             "MEM map begin tag=start"] + SAMPLE_MAP + ["MEM map end tag=start",
             "MEM tag=r1_memdir free=9 alloc=2 largest=4 files=300 dirs=0 alldirs=0 lista=0 blocks=0 ms=1"]
    rows, maps = M.collect(lines)
    check([x["tag"] for x in rows] == ["start", "r1_memdir"] and list(maps) == ["start"], "rows and maps apart")
    out = tempfile.mkdtemp(prefix="memcheck_hosttest.")
    with redirect_stdout(io.StringIO()):
        text = M.report(rows, maps, out)
    check("| r1_memdir |" in text and os.path.exists(os.path.join(out, "mem.csv")), "a report and a CSV")


def test_files():
    import memcheck as M
    print("memcheck.py: the files memtest.bas reads")
    cfg = M.cfg_tap(True, 3, "/GAMES")
    data = cfg[2 + 19 + 2 + 1:-1]                               # after the header block, the flag
    check(cfg[2 + 1] == 3 and cfg[2 + 14] | cfg[2 + 15] << 8 == 60000, "memcfg: a CODE header for 60000")
    check(data[:3] == bytes([1, 3, 6]) and data[3:] == b"/GAMES", "board, rounds, length, path (%r)" % data)
    tape = M.tape()
    blocks, i = [], 0
    while i < len(tape):
        n = tape[i] | tape[i + 1] << 8
        blocks.append(tape[i + 2:i + 2 + n])
        i += 2 + n
    check(len(blocks) == 2 + 2 * M.SMALL_BLOCKS, "memtape: %d blocks" % len(blocks))
    check(blocks[0][1] == 3 and blocks[0][12] | blocks[0][13] << 8 == M.BIG_LEN
          and len(blocks[1]) == M.BIG_LEN + 2, "the first is a %d-byte CODE block" % M.BIG_LEN)
    ok = True
    for b in blocks:
        x = 0
        for c in b:
            x ^= c
        ok = ok and x == 0
    check(ok, "every block's checksum is right")
    d = M.dock()
    check(d[0] == 0 and d[1] == 2 and set(d[2:9]) == {0} and len(d) == 9 + 8192, "memdock: bank 0, one 8K chunk")


def main():
    P.install_fakes()
    ext = types.ModuleType("dev_extcmd")
    ext.EXT_SA_FUNCT = {}
    sys.modules["dev_extcmd"] = ext
    import TS.tspico as t
    t.TLM_ENABLED = False
    t.time = P.FakeTime()
    root = tempfile.mkdtemp(prefix="memcheck_hosttest.")
    sent = D.setup(t, root)
    test_largest(t)
    test_meminfo(t, sent)
    test_parse()
    test_files()
    print("\n%d/%d passed" % (sum(results), len(results)))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
