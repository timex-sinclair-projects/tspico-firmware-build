"""Host-side test: colour on the CAT listing and the tpi:info screen, and the
SD sizes in units that fit the card (2026-10-02).

  * catalog.space_pair: kB / MB / GB chosen from the total, so the 256 MB
    cards the boards ship with read "240 MB", not "0.2346GB".
  * SEND_MSG2(colour=True) passes INK (10h) and PAPER (11h) with a value
    the ROM can take (1, 2, 4-9), at zero width: a 32-character row with
    codes in it still ends in exactly one CR. Values 0 and 3 would end the
    ROM's string, so those codes are dropped with their value. Without
    colour=True every attribute code is dropped, as before.
  * CAT_COLOUR: blue bar over the path and card line, cyan column titles,
    the dashed line gone, folders in blue as "folder", index numbers on
    cyan chips; any other text goes through unchanged.
  * GETINFO: the cyan badge on a blue strip; the strip and the missing
    values turn red when there's no card or nothing mounted.

Run:  python3 src/test/screen_colour_hosttest.py
"""

import os
import re
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import process_cmd_hosttest as P                                # noqa: E402

results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg)


def plain(m):
    """The text without its colour codes."""
    return re.sub("[\x10\x11].", "", m)


def codes(m):
    """[(code, value), ...] in order."""
    return [(ord(a), ord(b)) for a, b in re.findall("([\x10\x11])(.)", m)]


def screen(m):
    """What the 2068 shows: lines of at most 32 characters (codes take no
    room; a CR ends a line; a 33rd character starts a new one)."""
    lines, cur = [], ""
    for ch in plain(m):
        if ch == "\r":
            lines.append(cur)
            cur = ""
            continue
        if len(cur) == 32:
            lines.append(cur)
            cur = ""
        cur += ch
    if cur:
        lines.append(cur)
    return lines


def test_space(c):
    print("catalog.space_pair: units from the total")
    for total, free, want in ((251_658_240, 247_463_936, ("240 MB", "236 MB")),
                              (15_931_539_456, 13_207_225_344, ("14.8 GB", "12.3 GB")),
                              (1_441_792, 745_472, ("1.4 MB", "0.7 MB")),
                              (512_000, 10_240, ("500 kB", "10 kB"))):
        got = c.space_pair(total, free)
        check(got == want, "%d / %d bytes -> %s" % (total, free, got))
    line = "SD: %s; free: %s" % c.space_pair(15_931_539_456, 13_207_225_344)
    check(len(line) <= 32, "the largest card's CAT line fits the 32 columns (%r)" % line)


def send2(t, msg, colour):
    out = []
    t.CMD_PUT = lambda b: out.append(b)
    t.MQ_READY = lambda: None
    t.CMD_DRAIN = lambda: None
    t.MQ = types.SimpleNamespace(rx_fifo=lambda: 0, get=lambda: 0)
    t.TSP = types.SimpleNamespace(ROM_VERSION="2.1")
    t.SEND_MSG2(msg, 1, False, colour)
    return bytes(out[4:])                                         # past 86h, st, CR, CR


def test_send_msg2(t):
    print("SEND_MSG2: colour codes")
    row = "\x11\x01" + "A" * 32 + "\x11\x08" + "B" * 32
    got = send2(t, row, True)
    check(got == b"\x11\x01" + b"A" * 32 + b"\r\x11\x08" + b"B" * 32 + b"\r\x03",
          "kept, zero width: each 32-character row still ends in one CR (%r)" % got)
    got = send2(t, row, False)
    check(got == b"A" * 32 + b"\r" + b"B" * 32 + b"\r\x03",
          "without colour=True: dropped with their value, as before (%r)" % got)
    got = send2(t, "\x10\x00a\x11\x03b\x10\x09c\x12\x01d", True)
    check(got == b"ab\x10\x09cd\x03",
          "values 0 and 3 (they would end the ROM's string) and FLASH dropped; INK 9 kept (%r)" % got)
    got = send2(t, "abc\x10\x01def\r", True)
    check(got == b"abc\x10\x01def\r\x03", "a short line with a code: one CR, no extra (%r)" % got)


def test_cat_colour(t):
    print("CAT_COLOUR")
    rows = ["<GAMES>               " + "%10s" % "0 B",
            "000 manic.tap         " + "%10s" % "47.00 kB",
            "    readme.txt        " + "%10s" % "3.00 kB"]
    lista = t.DIR_HEADER("SD: 240 MB; free: 236 MB", "/GAMES") + "".join(rows)
    out = t.CAT_COLOUR(lista)
    lines = screen(out)
    check(lines[:3] == ["Path:/GAMES".ljust(32), "SD: 240 MB; free: 236 MB".ljust(32),
                        "File Name                   Size"],
          "the header's three lines; the dashed line gone (%r)" % lines[:4])
    check(lines[3] == "<GAMES>                   folder", "a folder's size reads 'folder' (%r)" % lines[3])
    check(lines[4:] == [rows[1], rows[2]], "file rows unchanged as text (%r)" % lines[4:])
    cs = codes(out)
    check(cs[:4] == [(0x11, 1), (0x10, 7), (0x11, 5), (0x10, 9)],
          "blue bar with white text, then cyan titles with contrast ink (%r)" % cs[:4])
    check(out.index("<GAMES>") > out.index("\x10\x01", 10), "the folder in blue ink")
    i = out.index("000")
    check(out[i - 4:i] == "\x11\x05\x10\x09" and out[i + 3:i + 7] == "\x11\x08\x10\x08",
          "the index on a cyan chip, then back to the screen's colours")
    check(all(v not in (0, 3) for _, v in cs), "no value the ROM can't take (%r)" % cs)
    for text in ("CACHED", "File:/advent.tap" + " " * 16 + "x"):
        check(t.CAT_COLOUR(text) == text, "not a folder listing (%r...): unchanged" % text[:12])
    out = t.CAT_COLOUR(t.DIR_HEADER("x", "/") + "Directory is empty\r")
    check(screen(out)[3] == "Directory is empty", "an empty folder still says so (%r)" % screen(out)[3:4])


def test_info(t):
    print("GETINFO")
    sent = []
    t.SEND_MSG2 = lambda msg, st, exp=True, colour=False: sent.append((msg, colour))
    t.SD_PROBE = lambda *a: True
    t.os = types.SimpleNamespace(statvfs=lambda p: (4096, 4096, 352, 182))
    t.gc = types.SimpleNamespace(mem_free=lambda: 108_544, collect=lambda: None)
    t.files = ["a.tap"] * 9
    t.sd_space = (251_658_240, 247_463_936)
    t.public_fname = lambda n=0: "manic.tap"
    t.public_path = lambda n=0: "/GAMES"
    t.isTapMounted = lambda: False
    t.getBoot = lambda: (2, 1)
    t.getDock = lambda: (2, 4)
    t.BUILD_VERSION = "b7a2e91 (main)"

    def run(sd, mounted):
        t.TSP = types.SimpleNamespace(FW_VERSION="2.1", ROM_VERSION="2.1", LOG_LEVEL=2,
                                      sd_present=sd, append=False, VERBOSE=True,
                                      f_name="/sd/TAP/GAMES/manic.tap" if mounted else "",
                                      tap_idx=0, offset_tbl=[])
        del sent[:]
        t.GETINFO(bytearray(10), "D..tpi:info")
        return sent[-1]

    msg, colour = run(True, True)
    lines = screen(msg)
    check(colour, "sent with colour=True")
    check(lines[0] == " TS-Pico  interface status      ", "the title line (%r)" % lines[0])
    check(codes(msg)[:4] == [(0x11, 5), (0x10, 9), (0x11, 1), (0x10, 7)],
          "cyan badge, then the blue strip (%r)" % codes(msg)[:4])
    want = {"Flash     1.4 MB, 0.7 MB free", "SD card   240 MB, 236 MB free",
            "Mounted   manic.tap", "Path      /GAMES", "Files     9",
            "Append    off   Verbose on", "Boot      2,1   Dock 2,4", "Build     b7a2e91 (main)",
            "Free RAM  106 kB"}
    missing = want - set(lines)
    check(not missing, "the values, in the new units (missing: %r)" % sorted(missing))
    check(all(len(l) <= 32 for l in lines) and len(lines) <= 22,
          "every line fits, %d lines (the 22-line page)" % len(lines))
    check(all(v not in (0, 3) for _, v in codes(msg)), "no value the ROM can't take")
    check(not re.search("\x10\x02", msg), "nothing missing: no red")

    msg, _ = run(False, False)
    lines = screen(msg)
    check(codes(msg)[2] == (0x11, 2), "no card, nothing mounted: the strip is red (%r)" % (codes(msg)[2],))
    check("SD card   none" in lines and "Mounted   none" in lines, "both say none")
    check(msg.count("\x10\x02none") == 2, "each 'none' in red ink")
    msg, _ = run(True, False)
    check(codes(msg)[2] == (0x11, 2) and msg.count("\x10\x02none") == 1,
          "nothing mounted alone: red strip, one red none")


def main():
    P.install_fakes()
    ext = types.ModuleType("dev_extcmd")
    ext.EXT_SA_FUNCT = {}
    sys.modules["dev_extcmd"] = ext
    import TS.tspico as t
    from TS import catalog
    t.TLM_ENABLED = False
    t.time = P.FakeTime()
    test_space(catalog)
    test_send_msg2(t)
    test_cat_colour(t)
    test_info(t)
    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
