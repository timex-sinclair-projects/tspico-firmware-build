"""Host-side test for the shared block buffer (#384) -- CPython, no Pico.

On the v3 card a 35000-byte LOAD or SAVE found no free block of its size
once a 300-file folder had been listed: LOAD streamed from the file and ran
dry (Report R), SAVE gave Report 6. board_v3 now makes one 48K buffer at
import, BLOCK_BUF; the slots use its first 32K, and tspico_io.BLOCK lends
its front to LOAD_TS, LOAD_ZX, SAVE_TS and SAVE_ZX. v2 has none.

What it pins:
  * BLOCK(n) with no buffer is a new bytearray(n); with one, a memoryview
    of its first n bytes (no copy); a block bigger than the buffer is a
    bytearray again;
  * board_v3's BLOCK_BUF holds 48K plus SAVE's 4 bytes and LOAD's parity,
    and its _buf (the slots' 32K) is the front of that same buffer;
  * board_v2's BLOCK_BUF is None; tspico.py hands board.BLOCK_BUF on;
  * the LOAD_TS, SAVE_TS and ZX48 host tests pass again with the buffer set
    (TSPICO_BLOCK_BUF): a memoryview block saves and loads byte for byte
    what a bytearray did, the native (+3DOS) SAVE included.

Run:  python3 src/test/block_buf_hosttest.py
"""

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, SRC)

results = []


def check(cond, msg):
    results.append(bool(cond))
    print("%s  %s" % ("PASS" if cond else "FAIL", msg))


def main():
    from sync_io_hosttest import install_fakes
    install_fakes()
    import TS.tspico_io as io

    io.BLOCK_BUF = None
    b = io.BLOCK(100)
    check(type(b) is bytearray and len(b) == 100, "no buffer: BLOCK(100) is a new bytearray(100)")

    buf = bytearray(1000)
    io.BLOCK_BUF = buf
    m = io.BLOCK(300)
    check(isinstance(m, memoryview) and len(m) == 300, "with a buffer: a 300-byte memoryview")
    m[0] = 0x5A
    m[299] = 0xA5
    check(buf[0] == 0x5A and buf[299] == 0xA5, "... of the buffer itself, no copy")
    check(isinstance(io.BLOCK(1000), memoryview), "a block exactly the buffer's size fits")
    big = io.BLOCK(1001)
    check(type(big) is bytearray and len(big) == 1001, "a bigger block: a new bytearray again")
    io.BLOCK_BUF = None

    v3 = open(os.path.join(SRC, "TS", "board_v3.py")).read()
    size = re.search(r"^BLOCK_SIZE = (.+)$", v3, re.M)
    n = eval(size.group(1)) if size else 0
    check(n >= 49152 + 4, "board_v3 BLOCK_SIZE %d holds a 48K SAVE (blen + 4)" % n)
    check(n >= 49152 + 1, "... and a 48K LOAD (content + parity)")
    check(re.search(r"^BLOCK_BUF = bytearray\(BLOCK_SIZE\)", v3, re.M),
          "board_v3 makes BLOCK_BUF at import")
    check(re.search(r"^_buf = memoryview\(BLOCK_BUF\)\[:SLOT_SIZE\]", v3, re.M),
          "board_v3's slot buffer _buf is BLOCK_BUF's first 32K")
    check(not re.search(r"^_buf = bytearray", v3, re.M), "no second 32K buffer")
    v2 = open(os.path.join(SRC, "TS", "board_v2.py")).read()
    check(re.search(r"^BLOCK_BUF = None", v2, re.M), "board_v2: BLOCK_BUF is None")
    ts = open(os.path.join(SRC, "TS", "tspico.py")).read()
    check("tspico_io.BLOCK_BUF = board.BLOCK_BUF" in ts, "tspico.py hands board.BLOCK_BUF to tspico_io")

    tio = open(os.path.join(SRC, "TS", "tspico_io.py")).read()
    for alloc in ("hdr = bytearray(totbytes - 1)\n            arch.readinto(hdr)",
                  "whole = bytearray(totbytes - 1)", "blk = bytearray(long)", "blk = bytearray(n + 4)"):
        check(alloc not in tio.replace("\r\n", "\n"), "no data block allocated outright: %s" % alloc.split("\n")[0])

    env = dict(os.environ, TSPICO_BLOCK_BUF=str(n or 49160))
    for t in ("load_ts_hosttest.py", "save_ts_hosttest.py", "zx48_io_hosttest.py"):
        p = subprocess.run([sys.executable, os.path.join(HERE, t)], env=env,
                           capture_output=True, text=True)
        tail = (p.stdout.strip().splitlines() or [""])[-1]
        check(p.returncode == 0 and "ALL PASS" in tail,
              "%s with the shared buffer: %s" % (t, tail))
        if p.returncode:
            print(p.stdout[-2000:] + p.stderr[-2000:])

    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
