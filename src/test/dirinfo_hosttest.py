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
    numbers in a$ are the ones LOAD "tpi:n" uses;
  * LIST_DIR_FILES makes no rows: lista is a DirText, its rows made from
    INDEX when read (#384), and it reads as the whole listing. It collects
    once, after reading the folder and before it makes anything it keeps
    (the signature, the DirText), so those don't land past the garbage;
  * DEACTIVATE_SD drops the SD card driver (SD_DEV), made new by every
    mount, so it isn't kept between commands either.

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
    deactivate_sd = t.DEACTIVATE_SD                             # and this one, for the SD_DEV check
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

    print('OPEN #4,"x:": dir, path, mount, info (#404)')
    got = open(path, "rb").read()
    di = blocks(got)[1]
    di_rows = [di[6 + 32 * k:6 + 32 * (k + 1)].decode() for k in range((len(di) - 7) // 32)]
    with open(os.path.join(root, "BBB.TAP"), "wb") as f:
        f.write(b"bb")                                          # changed again since dirinfo.tap
    tx = []
    real_put, real_ready, real_sd_call = t.CMD_PUT, t.CH_READY, t.SD_CALL
    t.CMD_PUT = lambda b: tx.append(b)
    t.CH_READY = lambda: tx.append("READY")
    t.tspico_io.CAN_STREAM = lambda: False

    def no_card(fn, *a):
        raise AssertionError("SD_CALL used for an x: stream")
    t.SD_CALL = no_card

    def cmd(handler, text, stream, par2=0):
        pre = bytearray(10)
        pre[3], pre[5] = stream, par2
        del tx[:]
        handler(pre, "xxx" + text)
        return tx

    def say(line):
        return cmd(t.CH_WRITE, "tpi:chwr " + (line + "\r").encode().hex(), 4)

    def answer():
        out = b""
        while True:
            r = cmd(t.CH_READ, "tpi:chrd", 4, 255)
            if r[0] != 1:
                return out, r[0]
            out += bytes(r[3:3 + r[1]])

    sa = {"TPI:CHOPEN": None, "TPI:CHWR": None, "TPI:CHRD": None}
    check(not t.SD_NEEDED(False, "TPI:CHOPEN", "tpi:chopen r x:", sa, 4), "SD_NEEDED: chopen x: needs no card")
    check(cmd(t.CH_OPEN, "tpi:chopen r x:y", 4) == [t._4_Q_Parameter, "READY"], "x:y: Q (only \"x:\")")
    check(cmd(t.CH_OPEN, "tpi:chopen r x:", 4, 10) == [t._4_Q_Parameter, "READY"], "x: with a record length: Q")
    check(cmd(t.CH_OPEN, "tpi:chopen r X:", 4) == [t._1_OK, "READY"] and t.CHANNELS.in_memory(4),
          "X: opens a command stream, no card")
    check(not t.SD_NEEDED(False, "TPI:CHWR", "tpi:chwr 00", sa, 4)
          and not t.SD_NEEDED(False, "TPI:CHRD", "tpi:chrd", sa, 4)
          and t.SD_NEEDED(False, "TPI:CHRD", "tpi:chrd", sa, 5),
          "SD_NEEDED: chwr/chrd on it need no card; another stream still does")
    check(say("dir") == [t._1_OK, "READY"], "PRINT #4;\"dir\": OK")
    data, end = answer()
    lines = data.split(b"\r")[:-1]
    check(end == t._7_8_EOF and data.endswith(b"\r"), "read to the end, then Report 8's status")
    listing = sorted(t.os.ilistdir(), key=lambda e: e[0].lower())
    want = OLD_DIRINFO(t, listing)
    wb = blocks(want)[1]
    want_rows = [wb[6 + 32 * k:6 + 32 * (k + 1)].decode() for k in range((len(wb) - 7) // 32)]
    check(want_rows != di_rows, "  (the folder changed since dirinfo.tap was made)")
    check([l.decode() for l in lines[:2]] == [want_rows[0].strip(), want_rows[1].strip()],
          "lines 1-2: the folder and file counts, fresh (%r)" % lines[:2])
    check([l.decode() for l in lines[2:]] == want_rows[2:],
          "then dirinfo.tap's rows, 32 characters each, for the folder as it is now")
    k = list(t.files).index("BBB.TAP")
    check(all(len(l) == 32 for l in lines[2:]) and (b"%03d BBB.TAP" % k) in data,
          "  BBB.TAP numbered %d, as files[] (LOAD \"tpi:n\") numbers it" % k)
    say("dir")
    cmd(t.CH_READ, "tpi:chrd", 4, 40)
    say("path")
    data, end = answer()
    check(data == b"/TAP\r", "path after a dir read only in part: just the path (%r)" % data)
    t.TSP.f_name = "/sd/TAP/CHESS.TAP"
    say("MOUNT")
    check(answer()[0] == b"/TAP/CHESS.TAP\r", "mount: the mounted file (either case)")
    t.TSP.f_name = ""
    say("mount")
    check(answer()[0] == b"\r", "mount with nothing mounted: an empty line")
    t.TSP.sd_label = "TSPICO"
    t.TSP.FW_VERSION = "9.9.9"
    t.rom_id = 0x23
    say("info")
    check(answer()[0] == b"TSPICO\r256000\r512000\r9.9.9\r2.3\r",
          "info: label, free, total, firmware, ROM")
    t.rom_id = 0xFF
    real_act = t.ACTIVATE_SD

    def no_sd(*a, **k):
        t.TSP.sd_present = False
        raise OSError(19, "no SD card")
    t.ACTIVATE_SD = no_sd
    say("info")
    check(answer()[0] == b"\r0\r0\r9.9.9\r\r", "info with no card: no label or space; no ROM version")
    check(say("dir") == [t._10_J_Invalid_IO, "READY"], "dir with no card: J")
    t.ACTIVATE_SD = real_act
    t.TSP.sd_present = True
    check(say("format") == [t._4_Q_Parameter, "READY"], "an unknown command: Q")
    check(answer() == (b"", t._7_8_EOF), "  and nothing to read")
    check(cmd(t.CH_CLOSE, "tpi:chclose", 4) == [t._1_OK, "READY"] and not t.CHANNELS.in_memory(4),
          "CLOSE #4, no card")
    t.CMD_PUT, t.CH_READY, t.SD_CALL = real_put, real_ready, real_sd_call
    os.remove(os.path.join(root, "BBB.TAP"))

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

    print("a big folder: no rows made, one collection before what it keeps")
    big = os.path.join(root, "BIG")
    os.makedirs(big)
    for k in range(95):
        with open(os.path.join(big, "f%03d.tap" % k), "wb") as f:
            f.write(b"b")
    for k in range(3):
        os.makedirs(os.path.join(big, "dir%d" % k))
    with open(os.path.join(big, "notes.txt"), "wb") as f:
        f.write(b"n")                                           # a row without a number
    t.os.chdir("/sd/TAP/BIG")
    real_gc = t.gc
    counted = []
    t.gc = types.SimpleNamespace(collect=lambda: counted.append((t.TSP.listing_sig, t.lista)))
    made = []
    real_row = t.DirText.row
    t.DirText.row = lambda self, r: made.append(r) or real_row(self, r)
    try:
        t.LIST_DIR_FILES()
        check(not made and isinstance(t.lista, t.DirText),
              "99 entries: lista is a DirText, and no row was made")
        check(counted == [(None, "")] and t.TSP.listing_sig is not None,
              "  one collection, before the signature and the DirText were made")
        check(len(t.lista) == 128 + 32 * 99 and t.lista[128 + 32 * 3:128 + 32 * 3 + 4] == "000 ",
              "  it reads as the listing: 99 rows of 32, the first numbered row after the 3 folders")
    finally:
        t.gc = real_gc
        t.DirText.row = real_row
    check(len(t.files) == 95 and len(t.dirs) == 3 and "notes.txt" in t.lista, "  all 99 rows there")

    print("the SD card driver goes with the mount")
    t.SD_DEV = object()
    t.os.umount = lambda p: None
    t.board = types.SimpleNamespace(sd_release_bus=lambda: None)
    deactivate_sd()
    check(t.SD_DEV is None, "DEACTIVATE_SD drops SD_DEV: nothing of the mount is kept between commands")

    shutil.rmtree(root, ignore_errors=True)
    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
