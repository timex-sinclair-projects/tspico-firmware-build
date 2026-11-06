#!/usr/bin/env python3
"""The heap measurement for #384: how the Pico's free memory and its largest
free block change as the TS-Pico is used.

    python3 tools/memcheck.py                 # on the connected TS-Pico (v2 or v3)
    python3 tools/memcheck.py --rounds 5      # more rounds (default 3)
    python3 tools/memcheck.py --emu           # a dry run in ZEsarUX (tools/emu)
    python3 tools/memcheck.py --parse LOG     # just the report, from a saved console log

The 2068 runs basic/SD/TAP/test/memtest.bas (built by tools/build-basic.sh).
After each step it sends SAVE "tpi:meminfo <tag>". The firmware's MEMINFO
collects garbage, measures, and prints one line on the USB console:

    MEM tag=r1_mount free=… alloc=… largest=… files=… dirs=… lista=… blocks=… ms=…

"largest" is the biggest buffer the heap can give at that moment
(LARGEST_BLOCK). It is the number that decides whether a 32K or 64K buffer
fits, which total free memory does not. Tags with "map" add the heap map
(micropython.mem_info(1)): one letter per 16-byte block, showing what kind
of object sits where.

Each round goes into a folder of 300 small tapes (MEMDIR, made here), into
the card's biggest folder, back to /TAP, mounts a tape with 61 blocks, loads
a 35000-byte block, SAVEs it back (press ENTER at "Start tape"), mounts an
8K .DCK (no flash write: the image is only built), closes, and on the v3 card
speaks a line.

This script:
  1. stops the firmware, sees which board it is and checks the firmware has
     tpi:meminfo (flash this branch first if not), finds the card's biggest
     folder, and puts MEMDIR, memtest.tap, memcfg.tap, memtape.tap and
     memdock.dck on the card;
  2. restarts the firmware and asks you to type, on the 2068:
         MOVE TO "/"     then     LOAD "tpi:memtest.tap"     then     LOAD ""
     then watches the console until the program's last measurement;
  3. prints a table (and the heap maps' summaries) and saves everything in
     an output folder: report.md, mem.csv, console.log, the maps.

The numbers are the hardware's. In the emulator (--emu) the firmware runs on
CPython: the program's flow and the MEM lines are real, the numbers are not.

The 2068 should be on and at the BASIC prompt with the SD card in, and
nothing else using the Pico's port (Thonny, a watch).
"""

import argparse
import csv
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src", "test"))
import sd_roundtrip as RT                                       # noqa: E402

PS = [sys.executable, os.path.join(HERE, "pico-serial.py")]
MEMTEST_SRC = os.path.join(ROOT, "basic", "SD", "TAP", "test", "memtest.bas")
MEMTEST = os.path.join(ROOT, "SD card", "TAP", "test", "memtest.tap")

MEMDIR_FILES = 300                      # tapes in the test folder
BIG_LEN = 35000                         # memtest.bas: LOAD ""CODE 30000, SAVE …CODE 30000,35000
SMALL_BLOCKS = 30                       # header + data pairs after the big block
MEM_FIELDS = ("free", "alloc", "largest", "files", "dirs", "lista", "blocks", "ms")


# ---------------------------------------------------------------------------
# The files the program needs
# ---------------------------------------------------------------------------

def cfg_tap(board_v3, rounds, bigdir):
    """memcfg.tap: CODE at 60000 -- board (1: v3), rounds, the length of the
    big folder's path, then the path. memtest.bas line 20 reads it."""
    path = bigdir.encode("ascii")
    data = bytes([1 if board_v3 else 0, rounds, len(path)]) + path
    return RT.hdr(3, "memcfg", len(data), 60000, 32768) + RT.blk(0xFF, data)


def tape():
    """memtape.tap: the 35000-byte CODE block LOAD ""CODE 30000 takes, then
    SMALL_BLOCKS small ones: a block table of 2 + 2 * SMALL_BLOCKS entries."""
    big = bytes((i * 7) & 0xFF for i in range(BIG_LEN))
    out = RT.hdr(3, "big", BIG_LEN, 30000, 32768) + RT.blk(0xFF, big)
    for i in range(SMALL_BLOCKS):
        out += RT.hdr(3, "small%02d" % i, 64, 40000, 32768) + RT.blk(0xFF, bytes([i]) * 64)
    return out


def dock():
    """memdock.dck: a DOCK image (bank 0) with one 8K chunk, the rest absent."""
    return bytes([0, 2, 0, 0, 0, 0, 0, 0, 0]) + bytes((i * 3) & 0xFF for i in range(8192))


def little_tap(i):
    """One of MEMDIR's tapes: a small CODE block."""
    return RT.hdr(3, "m%03d" % i, 16, 40000, 32768) + RT.blk(0xFF, bytes([i & 0xFF]) * 16)


def build_memtest():
    if not os.path.exists(MEMTEST) or os.path.getmtime(MEMTEST) < os.path.getmtime(MEMTEST_SRC):
        print("  Building the BASIC programs (tools/build-basic.sh)...")
        subprocess.run([os.path.join(HERE, "build-basic.sh")], capture_output=True, check=True)


def write_files(folder, board_v3, rounds, bigdir):
    """The four files in `folder` (a local folder): what goes in the card's /TAP."""
    build_memtest()
    shutil.copy(MEMTEST, os.path.join(folder, "memtest.tap"))
    for name, data in (("memcfg.tap", cfg_tap(board_v3, rounds, bigdir)),
                       ("memtape.tap", tape()), ("memdock.dck", dock())):
        with open(os.path.join(folder, name), "wb") as f:
            f.write(data)
    return ("memtest.tap", "memcfg.tap", "memtape.tap", "memdock.dck")


# ---------------------------------------------------------------------------
# Reading the console
# ---------------------------------------------------------------------------

MEM_RX = re.compile(r"MEM tag=(\S+)((?: \w+=-?\d+)+)")


def parse_mem(line):
    """A MEM line as a dict (tag and the numbers), or None."""
    m = MEM_RX.search(line)
    if not m:
        return None
    row = {"tag": m.group(1)}
    for k, v in re.findall(r"(\w+)=(-?\d+)", m.group(2)):
        row[k] = int(v)
    return row


# mem_info(1)'s map letters (MicroPython py/gc.c, gc_dump_alloc_table)
MAP_KINDS = {"h": "other", "T": "tuple", "L": "list", "D": "dict", "S": "str/bytes",
             "A": "bytearray", "M": "module", "B": "code", "F": "float", "m": "marked"}


def parse_map(lines):
    """Summarise one micropython.mem_info(1) dump: block counts by kind (a
    head letter and the '=' tail blocks after it), the free runs, and the
    header's own numbers. Lines of "(n lines all free)" count 64 free
    blocks each."""
    head = {}
    for l in lines:
        for key in ("total", "used", "free", "max free sz", "max blk sz", "No. of 1-blocks",
                    "2-blocks"):
            m = re.search(re.escape(key) + r":\s*(\d+)", l)
            if m and key not in head:
                head[key] = int(m.group(1))
    cells = []
    for l in lines:
        m = re.match(r"\s*\((\d+) lines all free\)", l)
        if m:
            cells.append("." * (64 * int(m.group(1))))
            continue
        m = re.match(r"^[0-9a-f]{8}: (\S+)$", l.rstrip())
        if m:
            cells.append(m.group(1))
    cells = "".join(cells)
    blocks, objects = {}, {}
    kind = None
    runs, run = [], 0
    for c in cells:
        if c == ".":
            run += 1
            kind = None
            continue
        if run:
            runs.append(run)
            run = 0
        if c == "=":
            if kind:
                blocks[kind] = blocks.get(kind, 0) + 1
            continue
        kind = MAP_KINDS.get(c, "other")
        blocks[kind] = blocks.get(kind, 0) + 1
        objects[kind] = objects.get(kind, 0) + 1
    if run:
        runs.append(run)
    runs.sort(reverse=True)
    return {"header": head, "blocks": blocks, "objects": objects, "free_runs": runs,
            "cells": len(cells)}


WATCH_TIME = re.compile(r"^\d\d:\d\d:\d\d ")


def collect(lines):
    """The MEM rows and the heap maps ({tag: summary}) in console lines."""
    rows, maps = [], {}
    cur, tag = None, None
    for line in lines:
        line = WATCH_TIME.sub("", line)     # pico-serial.py watch puts the time first
        m = re.search(r"MEM map begin tag=(\S+)", line)
        if m:
            cur, tag = [], m.group(1)
            continue
        if cur is not None:
            if "MEM map end" in line:
                maps[tag] = parse_map(cur)
                cur = None
            else:
                cur.append(line)
            continue
        row = parse_mem(line)
        if row:
            rows.append(row)
    return rows, maps


def k(n):
    return "%.1f" % (n / 1024)


def report(rows, maps, out):
    """The table and the map summaries: printed, and in out/report.md and out/mem.csv."""
    md = ["# Heap measurement (#384)", "",
          "| step | free K | largest K | alloc K | files | dirs | lista | blocks | ms |",
          "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append("| %s | %s | %s | %s | %d | %d | %d | %d | %d |" % (
            r["tag"], k(r.get("free", 0)), k(r.get("largest", 0)), k(r.get("alloc", 0)),
            r.get("files", 0), r.get("dirs", 0), r.get("lista", 0),
            r.get("blocks", 0), r.get("ms", 0)))
    if rows:
        lg = [r.get("largest", 0) for r in rows]
        md += ["", "Largest block: %s K at the start, %s K at the lowest (%s), %s K at the end." % (
            k(lg[0]), k(min(lg)), rows[lg.index(min(lg))]["tag"], k(lg[-1]))]
        per_round = {}
        for r in rows:
            m = re.match(r"r(\d+)_", r["tag"])
            if m:
                per_round.setdefault(int(m.group(1)), []).append(r.get("largest", 0))
        if per_round:
            md.append("Lowest largest block in each round: " + ", ".join(
                "%d: %s K" % (n, k(min(v))) for n, v in sorted(per_round.items())) + ".")
    for tag, s in maps.items():
        h = s["header"]
        md += ["", "## Heap map: %s" % tag, ""]
        if h:
            md.append("mem_info: " + ", ".join("%s %d" % (a, b) for a, b in h.items())
                      + ("  (max free sz is in 16-byte blocks: %s K)" % k(16 * h["max free sz"])
                         if "max free sz" in h else ""))
        runs = s["free_runs"]
        md.append("Free runs: %d; the largest %s K; runs of 1K or more: %d." % (
            len(runs), ", ".join(k(16 * r) for r in runs[:4]) or "none",
            sum(1 for r in runs if r >= 64)))
        md += ["", "| kind | objects | K |", "|---|---|---|"]
        for kind, n in sorted(s["blocks"].items(), key=lambda kv: -kv[1]):
            md.append("| %s | %d | %s |" % (kind, s["objects"].get(kind, 0), k(16 * n)))
    text = "\n".join(md) + "\n"
    print("\n" + text)
    if out:
        with open(os.path.join(out, "report.md"), "w") as f:
            f.write(text)
        with open(os.path.join(out, "mem.csv"), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(("tag",) + MEM_FIELDS)
            for r in rows:
                w.writerow([r["tag"]] + [r.get(x, "") for x in MEM_FIELDS])
    return text


# ---------------------------------------------------------------------------
# On the hardware
# ---------------------------------------------------------------------------

def ps(*args, timeout=180):
    r = subprocess.run(PS + list(args), capture_output=True, text=True, timeout=timeout)
    return r.stdout + r.stderr


def repl(code, work, sd=False, timeout=60):
    path = os.path.join(work, "snippet.py")
    with open(path, "w") as f:
        f.write(code)
    args = ["run", "--file", path, "--timeout", str(timeout)]
    if sd:
        args.insert(1, "--sd")
    return ps(*args, timeout=timeout + 60)


BIGGEST = """import os
best = ('', -1)
def walk(p, rel):
    global best
    n = 0
    for e in os.ilistdir(p):
        if e[1] & 0x4000:
            if e[0].upper() != 'MEMDIR' and not e[0].startswith('.'):
                walk(p + '/' + e[0], rel + '/' + e[0])
        else:
            n += 1
    if rel and n > best[1]:
        best = (rel, n)
walk('/sd/TAP', '')
print('BIG', best[0] or '-', best[1])
"""

MAKE_MEMDIR = """import os
d = '/sd/TAP/MEMDIR'
try:
    os.mkdir(d)
except OSError:
    pass
src = open('/sd/TAP/m000.tap', 'rb').read()
have = set(os.listdir(d))
made = 0
for i in range(%d):
    n = 'm%%03d.tap' %% i
    if n not in have:
        with open(d + '/' + n, 'wb') as f:
            f.write(src)
        made += 1
os.remove('/sd/TAP/m000.tap')
try:
    os.remove('/sd/TAP/memsave.tap')
except OSError:
    pass
print('MEMDIR', len(os.listdir(d)), 'made', made)
"""


def hardware(args, out):
    work = tempfile.mkdtemp(prefix="memcheck.")
    print("Setting up. The firmware stops for a minute; leave the 2068 at the prompt.")
    ps("break", "--timeout", "5")
    o = repl("from TS import board\nimport TS.tspico as T\n"
             "print('HW', board.NAME, T.FW_VERSION, hasattr(T, 'MEMINFO'))\n", work)
    m = re.search(r"HW (\w+) (\S+) (\w+)", o)
    if not m:
        sys.exit("Couldn't read the board from the REPL:\n" + o)
    board_v3 = m.group(1) == "v3"
    print("  Board: %s, firmware %s" % ("the v3 card" if board_v3 else "TS-Pico 2.x", m.group(2)))
    if m.group(3) != "True":
        ps("softreset")
        sys.exit("  This firmware has no tpi:meminfo. Flash this branch first:\n"
                 "    python3 tools/pico-serial.py flash %s--branch <this branch>"
                 % ("--v3 " if board_v3 else ""))

    o = repl(BIGGEST, work, sd=True)
    m = re.search(r"BIG (\S+) (-?\d+)", o)
    bigdir = m.group(1) if m and m.group(1) != "-" else ""
    if len(bigdir) > 64:
        bigdir = ""
    print("  The card's biggest folder: %s" % ("%s (%s files)" % (bigdir, m.group(2)) if bigdir
                                                 else "none (only MEMDIR is used)"))

    with open(os.path.join(work, "m000.tap"), "wb") as f:
        f.write(little_tap(0))
    for name in write_files(work, board_v3, args.rounds, bigdir) + ("m000.tap",):
        o = ps("put", "--sd", os.path.join(work, name), "/TAP/" + name)
        if "bytes" not in o or "MISMATCH" in o:
            sys.exit("Couldn't copy %s to the card:\n%s" % (name, o))
    o = repl(MAKE_MEMDIR % MEMDIR_FILES, work, sd=True, timeout=180)
    print("  " + (re.search(r"MEMDIR.*", o).group(0) if "MEMDIR" in o else o.strip()))
    ps("softreset")
    time.sleep(4)

    log = os.path.join(out, "console.log")
    watch = subprocess.Popen(PS + ["watch", "--seconds", str(args.timeout)], stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True, bufsize=1)
    print('\nOn the 2068 type:   MOVE TO "/"   then   LOAD "tpi:memtest.tap"   then   LOAD ""')
    print("Press ENTER at each \"Start tape\" (%d of them). Waiting for the last measurement..."
          % args.rounds)
    lines = []
    t0 = time.time()
    try:
        with open(log, "w") as f:
            for line in watch.stdout:
                line = line.rstrip("\n")
                lines.append(line)
                f.write(line + "\n")
                f.flush()
                r = parse_mem(line)
                if r:
                    print("  %-16s free %6s K  largest %6s K" % (r["tag"], k(r.get("free", 0)),
                                                                   k(r.get("largest", 0))))
                if "MEM map end tag=end" in line or time.time() - t0 > args.timeout:
                    break
    finally:
        watch.terminate()
    return lines


# ---------------------------------------------------------------------------
# In the emulator
# ---------------------------------------------------------------------------

def emulator(args, out):
    sys.path.insert(0, os.path.join(HERE, "emu"))
    import session as S
    card = os.path.join(tempfile.mkdtemp(prefix="memcheck-card."), "sd")
    tapdir = os.path.join(card, "TAP")
    os.makedirs(os.path.join(tapdir, "MEMDIR"))
    os.makedirs(os.path.join(tapdir, "GAMES"))
    for i in range(MEMDIR_FILES):
        with open(os.path.join(tapdir, "MEMDIR", "m%03d.tap" % i), "wb") as f:
            f.write(little_tap(i))
    for i in range(120):
        with open(os.path.join(tapdir, "GAMES", "g%03d.tap" % i), "wb") as f:
            f.write(little_tap(i))
    write_files(tapdir, False, args.rounds, "/GAMES")
    log = "/tmp/pico_host.out"
    with S.Session(sd=card, log=log) as s:
        s.run(S.MOVE, " ", S.TO, '"/"')
        s.run(S.LOAD, '"tpi:memtest.tap"')
        s.run(S.LOAD, '""', until="memory test", timeout=60)
        t0 = time.time()
        while time.time() - t0 < args.timeout:
            time.sleep(1)
            t = s.text()
            if "press any key" in t.lower():
                s.key(129)
            if "MEMTEST DONE" in t:
                break
            if re.search(r"\n\S.*, \d+:\d+\s*$", t) and "MEMTEST" not in t:
                print("  The program stopped:\n" + t)
                break
        s.screenshot(os.path.join(out, "end.bmp"))
        print(s.text())
    with open(log) as f:
        lines = f.read().splitlines()
    shutil.copy(log, os.path.join(out, "console.log"))
    return lines


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--emu", action="store_true", help="a dry run in ZEsarUX (tools/emu)")
    ap.add_argument("--parse", metavar="LOG", help="report on a saved console log, no board")
    ap.add_argument("--out", help="the output folder (default: a new temporary one)")
    ap.add_argument("--timeout", type=int, default=2400, help="seconds to wait for the program")
    args = ap.parse_args()
    if not 1 <= args.rounds <= 20:
        sys.exit("--rounds: 1 to 20")
    out = args.out or tempfile.mkdtemp(prefix="memcheck-out.")
    os.makedirs(out, exist_ok=True)
    if args.parse:
        with open(args.parse) as f:
            lines = f.read().splitlines()
    elif args.emu:
        lines = emulator(args, out)
    else:
        lines = hardware(args, out)
    rows, maps = collect(lines)
    if not rows:
        sys.exit("No MEM lines. The console log is in " + out)
    report(rows, maps, out)
    print("Saved in " + out)


if __name__ == "__main__":
    main()
