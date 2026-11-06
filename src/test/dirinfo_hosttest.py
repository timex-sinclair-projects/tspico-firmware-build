"""Host-side test for dirinfo.tap made on demand (#384) -- CPython, no Pico.

dirinfo.tap is the folder listing as a TAP with one character array, a$,
that the flash menu program (nofile.bas) LOADs. LIST_DIR_FILES used to build
it on every listing as one bytes object (NEW_TAPBLK: ~9.7K in one piece for
300 files, where a big folder ran out of heap) and write it to the card on
every MOVE TO. Now LOAD "tpi:dirinfo.tap" makes it (DIRINFO_WRITE), a row at
a time. This checks, with the real TS.tspico functions on a fake card:

  * a listing (DIR_FILES) no longer writes dirinfo.tap;
  * LOAD "tpi:dirinfo.tap" writes it and mounts it;
  * its bytes are exactly what the old builder made (OLD_DIRINFO below is
    LIST_DIR_FILES' dirinfo rows + NEW_TAPBLK, as they were), checksums and
    lengths included;
  * a folder changed since the last listing is listed again first, so the
    numbers in a$ are the ones LOAD "tpi:n" uses.

Run:  python3 src/test/dirinfo_hosttest.py
"""

import os
import shutil
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import process_cmd_hosttest as P                                # noqa: E402
import disk_cmds_hosttest as D                                  # noqa: E402

results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg)


def OLD_DIRINFO(t, listing):
    """dirinfo.tap as LIST_DIR_FILES and NEW_TAPBLK built it before #384."""
    rows = []
    for a in listing:
        if a[1] == 16384:
            rows.append("%-32s" % t.shorten_filename(t.catalog.screen_name(a[0]), 20))
    nd, i = len(rows), 0
    for a in listing:
        if a[1] == 32768:
            if a[0][-3:].upper() not in t.catalog.DIR_EXT or a[0][0] == "." or a[0] == "dirinfo.tap":
                continue
            rows.append("%03d %-18s%10s" % (i, t.shorten_filename(t.catalog.screen_name(a[0]), 18),
                                            t.catalog.size_text(int(a[3]))))
            i += 1
    rows.insert(0, "%-32s" % nd)
    rows.insert(1, "%-32s" % i)
    n = len(rows)
    blk = bytearray([0xFF, 2, n & 0xFF, n >> 8, 32, 0])
    for r in rows:
        blk += r.encode()
    c = 0
    for b in blk:
        c ^= b
    blk.append(c)
    blk = bytes([len(blk) & 0xFF, len(blk) >> 8]) + blk
    return bytes(t.NEW_HDR(2, "dirinfo", len(blk) - 4)) + blk


def blocks(data):
    out, i = [], 0
    while i < len(data):
        n = data[i] | data[i + 1] << 8
        out.append(data[i + 2:i + 2 + n])
        i += 2 + n
    return out


def main():
    P.install_fakes()
    ext = types.ModuleType("dev_extcmd")
    ext.EXT_SA_FUNCT = {}
    sys.modules["dev_extcmd"] = ext
    import TS.tspico as t
    t.TLM_ENABLED = False
    t.time = P.FakeTime()
    root = tempfile.mkdtemp(prefix="dirinfo_hosttest.")
    D.build_card(root)
    for name, size in (("{game}.tap", 33), ("Zork.DCK", 65536), (".hidden.tap", 5)):
        with open(os.path.join(root, name), "wb") as f:
            f.write(b"z" * size)
    with open(os.path.join(root, "dirinfo.tap"), "wb") as f:
        f.write(b"OLD")                                         # an old firmware's, stale
    dir_files = t.DIR_FILES                                     # D.setup stubs it; the real one is under test
    D.setup(t, root)
    t.DIR_FILES = dir_files
    t.os.statvfs = lambda p: (512, 512, 1000, 500, 500, 0, 0, 0, 0, 255)
    t.TSP.sd_label = ""
    t.TSP.listing_sig = None
    logs = []
    t.LOG = lambda m, lvl: logs.append((lvl, m))
    path = os.path.join(root, "dirinfo.tap")

    print("a listing")
    t.os.chdir("/sd/TAP")
    check(t.DIR_FILES() is True and "ADVENT.TAP" in t.files, "DIR_FILES lists the folder")
    check(open(path, "rb").read() == b"OLD", "and no longer writes dirinfo.tap")
    check(not hasattr(t, "NEW_TAPBLK"), "NEW_TAPBLK is gone")

    print('LOAD "tpi:dirinfo.tap"')
    calls = []
    real_df = t.DIR_FILES
    t.DIR_FILES = lambda: calls.append(1) or real_df()
    msg, name, st = t.LOAD_TPI("dirinfo.tap")
    got = open(path, "rb").read()
    listing = sorted(t.os.ilistdir(), key=lambda e: e[0].lower())
    want = OLD_DIRINFO(t, listing)
    check(st == t._1_OK and t.mounted[-1] == "/sd/TAP/dirinfo.tap", "written and mounted (%r)" % (msg,))
    check(got == want, "the same bytes the old builder made (%d bytes)" % len(got))
    b = blocks(got)
    ok = len(b) == 2 and len(b[0]) == 19
    for blk in b:
        x = 0
        for c in blk:
            x ^= c
        ok = ok and x == 0
    check(ok, "two blocks, a 19-byte header, both checksums right")
    rows = [b[1][6 + 32 * k:6 + 32 * (k + 1)].decode() for k in range((len(b[1]) - 7) // 32)]
    check(int(rows[0]) == len(t.dirs) and int(rows[1]) == len(t.files), "rows 1 and 2: the folder and file counts")
    nums = [r for r in rows[2:] if r[:3].isdigit()]
    check([r[4:22].rstrip() for r in nums] == [t.shorten_filename(t.catalog.screen_name(f), 18) for f in t.files],
          "the numbered rows are files[] in order: LOAD \"tpi:n\"'s numbers")
    check(not calls, "the folder had not changed: no second listing")

    print("a folder changed since the last listing")
    with open(os.path.join(root, "AAA.TAP"), "wb") as f:
        f.write(b"a")
    msg, name, st = t.LOAD_TPI("dirinfo.tap")
    got = open(path, "rb").read()
    listing = sorted(t.os.ilistdir(), key=lambda e: e[0].lower())
    check(calls and t.files[0] == "AAA.TAP", "listed again first: files[] has the new file")
    check(got == OLD_DIRINFO(t, listing) and b"000 AAA.TAP" in got, "and dirinfo.tap numbers it the same way")

    print("a card error")
    real_open = t.open

    def bad_open(p, mode="r"):
        if p.endswith("dirinfo.tap") and "w" in mode:
            raise OSError(5, "EIO")
        return real_open(p, mode)
    t.open = bad_open
    n = len(t.mounted)
    msg, name, st = t.LOAD_TPI("dirinfo.tap")
    t.open = real_open
    check(st == t._4_Q_Parameter and len(t.mounted) == n, "Report Q, nothing mounted (%r)" % (msg,))
    check(any(lvl == 2 and "dirinfo.tap" in m for lvl, m in logs), "ERROR logged")

    shutil.rmtree(root, ignore_errors=True)
    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
