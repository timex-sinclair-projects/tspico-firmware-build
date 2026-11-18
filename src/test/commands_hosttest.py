"""Host-side test for tpi:format (.tap), tpi:list, tpi:label, tpi:rm and tpi:boot -- CPython, no Pico.

Runs the REAL TS.tspico handlers against a temporary directory standing in for
the SD card (the CardOS of disk_cmds_hosttest.py, case-insensitive like FAT),
and a temporary config.ini:

  * LIST shows a file as text or hex, and tpi:label (and FORMAT ":name")
    reads, sets and takes off the card's label in a FAT image;
  * FORMAT makes and mounts a new .tap, and refuses a name that exists (any
    case) instead of emptying it (what tpi:newtap did before FORMAT took over);
  * RM removes any file (not only the indexed types), by name, path or listing
    number, and empty folders; it refuses the mounted file, a missing name, a
    non-empty folder and the current folder -- before its Y/N prompt;
  * BOOT saves the memory type with the slot, LOAD_CONFIG uses both once and
    puts back flash slot 1, and MEM 3 is refused;
  * DIR CODE 1,n / 2,n past the last file gives the real range, 0 to n-1;
  * FWD CODE 2,n (by file) on the last header says it can't, not "Moved";
  * MD takes its name as the other commands do and refuses paths and the
    characters FAT won't take;
  * shorten_filename never returns more than it was asked for.

Run:  python3 src/test/commands_hosttest.py
"""

import json
import os
import shutil
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import process_cmd_hosttest as P                                # noqa: E402
import disk_cmds_hosttest as D                                  # noqa: E402


def _hw():
    """The v2 board module. tspico reaches the hardware through TS/board.py
    (phase 4 of the v3 port plan), so its constructors are patched there."""
    return sys.modules["TS.board_v2"]

results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg)


def pre(a=0, b=0):
    p = bytearray(10)
    p[3], p[4], p[5], p[6] = a & 0xFF, a >> 8, b & 0xFF, b >> 8
    return p


def run(t, handler, text, a=0, b=0):
    handler(pre(a, b), "D.." + text)


def test_format_tap(t, root, sent):
    print("tpi:format (a .tap)")
    del sent[:]
    run(t, t.DISK_FORMAT, "tpi:format fresh")
    check(D.on_card(root, "fresh.tap"), "makes fresh.tap")
    check(t.mounted[-1].lower().endswith("/fresh.tap") and t.TSP.append,
          "mounts it with append on")
    check(sent[-1][3] == t._1_OK, "answers OK")

    del sent[:]
    n = len(t.mounted)
    run(t, t.DISK_FORMAT, "tpi:format chess")
    check(sent[-1][3] == t._3_F_Invalid_file, "an existing name (other case) is F (%r)" % (sent[-1],))
    check(os.path.getsize(os.path.join(root, "CHESS.TAP")) == 1500, "and the file is untouched")
    check(len(t.mounted) == n, "and nothing is mounted")

    del sent[:]
    run(t, t.DISK_FORMAT, "tpi:format chess.tap")
    check(sent[-1][3] == t._3_F_Invalid_file, "the same with .tap given")

    del sent[:]
    run(t, t.DISK_FORMAT, "tpi:format a.b.tap")
    check(D.on_card(root, "a.b.tap") and not D.on_card(root, "a.b.tap.tap") and sent[-1][3] == t._1_OK,
          "a.b.tap makes a.b.tap, not a.b.tap.tap (#169) (%r)" % (sent[-1],))
    del sent[:]
    n = len(t.mounted)
    run(t, t.DISK_FORMAT, "tpi:format .tap")
    check(sent[-1][3] == t._3_F_Invalid_file and not D.on_card(root, ".tap") and len(t.mounted) == n,
          ".tap alone is no name: F, nothing made (%r)" % (sent[-1],))
    check(not hasattr(t, "NEW_TAP"), "tpi:newtap is gone (FORMAT does its job)")


def test_list(t, root, sent):
    print("tpi:list (LIST \"name\")")
    D.build_card(root)
    t.TSP.cur_path = "/sd/TAP"
    with open(os.path.join(root, "README.TXT"), "wb") as f:
        f.write(b"Hello\r\nworld\r\n")
    del sent[:]
    run(t, t.DISK_LIST, "tpi:list readme.txt")
    check(sent[-1] == ("MSG2", "Hello\r\nworld\r\n", t._1_OK), "a text file, as itself (%r)" % (sent[-1],))
    with open(os.path.join(root, "GAME.BIN"), "wb") as f:
        f.write(bytes([0, 1, 0x41, 0x42] * 4))
    del sent[:]
    run(t, t.DISK_LIST, "tpi:list game.bin")
    check(sent[-1] == ("MSG2", "0000 0001414200014142 ..AB..AB\r0008 0001414200014142 ..AB..AB\r", t._1_OK),
          "anything else as hex, all of a small file (%r)" % (sent[-1],))
    with open(os.path.join(root, "BIG.BIN"), "wb") as f:
        f.write(bytes(5000))
    del sent[:]
    run(t, t.DISK_LIST, "tpi:list big.bin")
    check(sent[-1][1].endswith("(the first 2048 of 5000 bytes)"), "a big binary: the first 2048 bytes")
    with open(os.path.join(root, "BIG.TXT"), "wb") as f:
        f.write(b"x" * 3000 + b"\x00" + b"y" * 9000)
    del sent[:]
    run(t, t.DISK_LIST, "tpi:list big.txt")
    m = sent[-1][1]
    check(m.startswith("xxx") and "?" in m and m.endswith("(the first 8192 of 12001 bytes)"),
          "text if its start is: the first 8192 bytes, a later NUL as ?")
    for arg, st, what in (("games", t._4_Q_Parameter, "a folder is Q"),
                          ("nothere.txt", t._3_F_Invalid_file, "a missing file is F"),
                          ("*.tap", t._4_Q_Parameter, "a wildcard is Q"),
                          ("", t._4_Q_Parameter, "no name is Q")):
        del sent[:]
        run(t, t.DISK_LIST, ("tpi:list " + arg).rstrip())
        check(sent[-1][0] == "MSG" and sent[-1][-1] == st, "%s (%r)" % (what, sent[-1]))
    check("TPI:LIST" not in t.SD_FREE, "tpi:list needs the card")


def test_label(t, root, sent):
    import fat_image as F
    print("tpi:label / FORMAT \":name\"")
    D.build_card(root)
    dev, rootsec = F.fat16()
    t.SD_DEV = dev
    t.TSP.sd_label = ""
    mounts = []
    t.os.umount = lambda p: mounts.append(("umount", p))
    t.os.mount = lambda d, p: mounts.append(("mount", p))
    calls = t.dir_files_calls

    del sent[:]
    run(t, t.DISK_LABEL, "tpi:label")
    check(sent[-1] == ("MSG", "No label", "", t._1_OK), "bare: No label (%r)" % (sent[-1],))
    del sent[:]
    run(t, t.DISK_LABEL, "tpi:label games 2")
    check(t.catalog.read_label(dev) == "GAMES 2" and t.TSP.sd_label == "GAMES 2"
          and sent[-1] == ("MSG", "Label: GAMES 2", "", t._1_OK), "sets it, upper case (%r)" % (sent[-1],))
    check(mounts == [("umount", "/sd"), ("mount", "/sd")], "with the card unmounted, then mounted again")
    check(t.dir_files_calls > calls, "and CAT's listing rebuilt")
    del sent[:]
    run(t, t.DISK_LABEL, "tpi:label")
    check(sent[-1] == ("MSG", "Label: ", "GAMES 2", t._1_OK), "bare: shows it (%r)" % (sent[-1],))
    del sent[:]
    run(t, t.DISK_FORMAT, "tpi:format :tspico")
    check(t.catalog.read_label(dev) == "TSPICO" and sent[-1][-1] == t._1_OK, 'FORMAT ":tspico" labels it')
    del sent[:]
    run(t, t.DISK_LABEL, "tpi:label -")
    check(t.catalog.read_label(dev) == "" and t.TSP.sd_label == "" and sent[-1][1] == "Label taken off",
          "- takes it off (%r)" % (sent[-1],))
    run(t, t.DISK_LABEL, "tpi:label X")
    del sent[:]
    run(t, t.DISK_FORMAT, "tpi:format :")
    check(t.catalog.read_label(dev) == "" and sent[-1][1] == "Label taken off", 'FORMAT ":" takes it off')
    for arg, what in (("a.b", "a '.'"), ("TWELVE CHARS", "12 characters")):
        del sent[:]
        run(t, t.DISK_LABEL, "tpi:label " + arg)
        check(sent[-1][-1] == t._4_Q_Parameter and t.catalog.read_label(dev) == "",
              "%s is Q, nothing written (%r)" % (what, sent[-1]))
    t.SD_DEV = object()
    del sent[:]
    run(t, t.DISK_LABEL, "tpi:label X")
    check(sent[-1][-1] == t._4_Q_Parameter, "a card driver with no raw blocks: Q")
    del t.os.umount, t.os.mount


def test_rm(t, root, sent):
    print("tpi:rm")
    D.build_card(root)
    t.TSP.cur_path, t.TSP.f_name = "/sd/TAP", ""
    asked = []

    def prompt(text, *a, **k):
        asked.append(text)
        return answer[0]
    t.SEND_MSG_PROMPT_YN = prompt
    answer = [89]

    del sent[:]
    run(t, t.RM, "tpi:rm notes.bak", 255)
    check(not D.on_card(root, "NOTES.BAK"), "removes a file that isn't an indexed type")
    check(sent[-1][3] == t._1_OK and not asked, "CODE 255,0: no prompt, OK")

    del sent[:]
    run(t, t.RM, "tpi:rm GAMES/manic.tap", 255)
    check(not D.on_card(root, "GAMES", "MANIC.TAP"), "removes by path")

    t.TSP.f_name = "/sd/TAP/CHESS.TAP"
    del sent[:]
    run(t, t.RM, "tpi:rm chess.tap")
    check(D.on_card(root, "CHESS.TAP"), "keeps the mounted file")
    check(sent[-1][3] == t._4_Q_Parameter and not asked,
          "the mounted file is Q, before any prompt (%r)" % (sent[-1],))
    run(t, t.RM, "tpi:rm CHESS.TAP", 255)
    check(D.on_card(root, "CHESS.TAP"), "and with CODE 255,0")
    t.TSP.f_name = ""

    del sent[:]
    run(t, t.RM, "tpi:rm nothere.tap", 255)
    check(sent[-1][3] == t._3_F_Invalid_file, "a missing file is F")

    del sent[:]
    run(t, t.RM, "tpi:rm full", 255)
    check(D.on_card(root, "FULL") and sent[-1][3] == t._4_Q_Parameter, "a folder with files in it is Q")
    del sent[:], asked[:]
    run(t, t.RM, "tpi:rm full")
    check(D.on_card(root, "FULL") and not asked and sent and sent[-1][1] == "RM: Directory not empty"
          and sent[-1][3] == t._4_Q_Parameter,
          "and without CODE: Q, \"Directory not empty\", before any prompt (%r)" % (sent[-1:],))

    with open(os.path.join(root, "EMPTY", "DIRINFO.TAP"), "wb") as f:
        f.write(b"d")
    del sent[:], asked[:]
    run(t, t.RM, "tpi:rm empty")
    check(asked and not D.on_card(root, "EMPTY") and not sent,
          "a folder holding only its dirinfo.tap counts as empty: asked, Y removes it")
    os.makedirs(os.path.join(root, "EMPTY"))

    del sent[:]
    run(t, t.RM, "tpi:rm empty", 255)
    check(not D.on_card(root, "EMPTY") and sent[-1][3] == t._1_OK, "an empty folder goes")

    t.TSP.cur_path = "/sd/TAP/GAMES"
    del sent[:]
    run(t, t.RM, "tpi:rm /games", 255)
    check(D.on_card(root, "GAMES") and sent[-1][3] == t._4_Q_Parameter, "the current folder is Q")
    t.TSP.cur_path = "/sd/TAP"

    del sent[:]
    run(t, t.RM, "tpi:rm old.bak", 1)
    check(D.on_card(root, "OLD.BAK") and sent[-1][3] == t._8_A_Invalid_arg, "a bad CODE is A")

    del sent[:], asked[:]
    answer[0] = 78
    run(t, t.RM, "tpi:rm old.bak")
    check(asked and D.on_card(root, "OLD.BAK") and not sent, "N at the prompt keeps it, nothing more sent")
    answer[0] = 89
    del asked[:]
    run(t, t.RM, "tpi:rm old.bak")
    check(asked and not D.on_card(root, "OLD.BAK") and not sent, "Y removes it, nothing more sent")

    del sent[:]
    run(t, t.RM, "tpi:rm", 255)
    check(sent[-1][3] == t._8_A_Invalid_arg, "no name is A")


def test_dir_range(t, sent):
    print("tpi:dir CODE 1,n / 2,n past the last file (#160)")
    real = t.files
    t.files = ["F%02d.TAP" % i for i in range(12)]
    for a in (1, 2):
        del sent[:]
        run(t, t.DIR, "tpi:dir", a, 12)
        check(sent and sent[-1][1] == "File index 12 out of range 0-11" and sent[-1][3] == t._6_6_Num2Big,
              "CODE %d,12 with twelve files: \"0-11\", Report 6 (%r)" % (a, sent[-1:]))
    del sent[:]
    run(t, t.DIR, "tpi:dir", 1, 11)
    check(sent and sent[-1][3] == t._1_OK and "F11.TAP" in sent[-1][2],
          "CODE 1,11, the last one, is in range (%r)" % (sent[-1:],))
    t.files = []
    del sent[:]
    run(t, t.DIR, "tpi:dir", 1, 0)
    check(sent and sent[-1][1] == "No files in this folder" and sent[-1][3] == t._6_6_Num2Big,
          "no files at all: says so, not \"0--1\" (%r)" % (sent[-1:],))
    t.files = real


def test_ffw_by_file(t, sent):
    print("tpi:ffw CODE 2,n by file (#170)")
    real = t.TSP.f_name, getattr(t.TSP, "offset_tbl", []), getattr(t.TSP, "tap_idx", 0), getattr(t.TSP, "offset", 0)
    t.TSP.f_name = "/sd/TAP/GAMES.TAP"
    # two programs: header 0 + data 1, header 2 + data 3
    t.TSP.offset_tbl = [[0, 19, " Y", "a"], [21, 100, " N", ""], [123, 19, " Y", "b"], [144, 50, " N", ""]]
    t.TSP.tap_idx = 0
    del sent[:]
    run(t, t.FWD, "tpi:ffw", 2, 1)
    check(t.TSP.tap_idx == 2 and sent[-1][1] == "Moved ahead to block # 2" and t.TSP.offset == 123,
          "from the first header: to the second (%r, idx %d)" % (sent[-1], t.TSP.tap_idx))
    del sent[:]
    run(t, t.FWD, "tpi:ffw", 2, 1)
    check(t.TSP.tap_idx == 2 and t.TSP.offset == 123 and sent[-1][1] == "Can't FWD. No later file."
          and sent[-1][3] == t._1_OK,
          "on the last header: stays, and says so -- not \"Moved ahead\" (%r)" % (sent[-1],))
    t.TSP.tap_idx = 1
    del sent[:]
    run(t, t.FWD, "tpi:ffw", 2, 5)
    check(t.TSP.tap_idx == 2, "from a data block, CODE 2,5 stops at the last header there is (%d)" % t.TSP.tap_idx)
    t.TSP.f_name, t.TSP.offset_tbl, t.TSP.tap_idx, t.TSP.offset = real


def test_md(t, root, sent):
    print("tpi:md (#174)")
    D.build_card(root)
    t.TSP.cur_path = "/sd/TAP"
    del sent[:]
    run(t, t.MDIR, "tpi:md  spaced")
    check(D.on_card(root, "SPACED") and not D.on_card(root, " SPACED") and sent[-1][3] == t._1_OK,
          "a second space is not part of the name (%r)" % (sent[-1],))
    before = sorted(os.listdir(root))
    for bad in ("a/b", "/x", "bad*name", "..", "q?"):
        del sent[:]
        run(t, t.MDIR, "tpi:md " + bad)
        check(sent[-1][1] == "MD: name not allowed: " and sent[-1][2] == bad and sent[-1][3] == t._3_F_Invalid_file,
              "%r: not allowed, F (%r)" % (bad, sent[-1]))
    check(sorted(os.listdir(root)) == before, "  and nothing is made")
    del sent[:]
    run(t, t.MDIR, "tpi:md tools")
    check(D.on_card(root, "TOOLS") and sent[-1][1] == "Created dir: " and sent[-1][2] == "tools",
          "a plain name is made (%r)" % (sent[-1],))
    del sent[:]
    run(t, t.MDIR, "tpi:md tools")
    check(sent[-1][3] == t._7_8_EOF, "made again: exists, 8 (%r)" % (sent[-1],))
    del sent[:]
    run(t, t.MDIR, "tpi:md  deeper", 1, 0)
    check(t.TSP.cur_path.upper().endswith("/DEEPER"),
          "CODE 1,0 goes into it, by the clean name (%s)" % t.TSP.cur_path)
    t.TSP.cur_path = "/sd/TAP"


def test_shorten(t):
    print("shorten_filename (#168)")
    f = t.shorten_filename
    check(f("SHORT.TAP", 18) == "SHORT.TAP", "a name that fits is unchanged")
    check(f("AVERYLONGGAMENAME2.TAP", 18) == "AVERYLO>ENAME2.TAP", "a long name keeps its extension, as before (%r)" % f("AVERYLONGGAMENAME2.TAP", 18))
    p = "/TAP/GAMES/A.VERYLONGFOLDERNAMEWITHADOTXXXXXXX"         # 46: the old code gave 73
    check(len(f(p, 27)) == 27 and f(p, 27).startswith("/TAP/GA"),
          "a path whose last dot is in a long folder name: 27 characters, not 73 (%r)" % f(p, 27))
    names = ["X" * 40, "NAME." + "E" * 30, "A.B", "LONGNAME.TAPE", ".HIDDENFILENAME", "A" * 10 + "." + "B" * 10]
    bad = [(n, l, f(n, l)) for n in names for l in range(0, 34) if len(f(n, l)) > max(l, 0)]
    check(not bad, "never longer than asked, for l 0-33 (%r)" % (bad[:3],))
    ok = [(n, l) for n in names for l in range(2, 34) if len(n) > l and len(f(n, l)) != l]
    check(not ok, "a name too long comes out exactly l long (%r)" % (ok[:3],))


def test_boot(t, cfg):
    print("tpi:boot and LOAD_CONFIG")
    with open(cfg, "w") as f:
        json.dump({"ROM_SLOT": 1, "ROM_SM": 10, "DCK_SLOT": 0}, f)
    t.TSP.ROM_SM, t.TSP.bank_sm = 10, 1

    def load():
        with open(cfg) as f:
            return json.load(f)

    run(t, t.MEMBOOT, "tpi:boot", 1, 5)
    c = load()
    check((c["ROM_SLOT"], c["ROM_SM"]) == (5, 9), "BOOT CODE 1,5 saves SRAM slot 5 (%r)" % c)
    check(t.getBoot() == (1, 5), "and switches now")

    iv = t.LOAD_CONFIG()
    check((iv["ROM_SLOT"], iv["ROM_SM"] & 3) == (5, 1), "the next start boots SRAM slot 5 (%r)" % iv)
    c = load()
    check((c["ROM_SLOT"], c["ROM_SM"]) == (1, 10), "config.ini goes back to flash slot 1 (%r)" % c)
    iv = t.LOAD_CONFIG()
    check((iv["ROM_SLOT"], iv["ROM_SM"] & 3) == (1, 2), "the start after that is flash slot 1")

    with open(cfg, "w") as f:
        json.dump({"ROM_SLOT": 1, "ROM_SM": 6, "DCK_SLOT": 0}, f)          # DOCK SRAM, boot flash
    run(t, t.MEMBOOT, "tpi:boot", 2, 4)
    c = load()
    check((c["ROM_SLOT"], c["ROM_SM"]) == (4, 6), "BOOT CODE 2,4 keeps the DOCK bits (%r)" % c)
    t.LOAD_CONFIG()
    c = load()
    check((c["ROM_SLOT"], c["ROM_SM"]) == (1, 6), "one-shot keeps the DOCK bits too (%r)" % c)

    before = load()
    t.TSP.ROM_SM, t.TSP.bank_sm = 10, 1
    run(t, t.MEMBOOT, "tpi:boot", 3, 1)
    check(load() == before and t.getBoot() == (2, 1), "MEM 3 is refused")


def main():
    P.install_fakes()
    ext = types.ModuleType("dev_extcmd")
    ext.EXT_SA_FUNCT = {}
    sys.modules["dev_extcmd"] = ext
    import TS.tspico as t
    t.TLM_ENABLED = False
    root = tempfile.mkdtemp(prefix="cmds_hosttest.")
    cfgdir = tempfile.mkdtemp(prefix="cmds_cfg.")
    cfg = os.path.join(cfgdir, "config.ini")
    try:
        D.build_card(root)
        sent = D.setup(t, root)
        card_open = t.open
        t.open = lambda p, mode="r": open(cfg, mode) if p.lstrip("/") == "config.ini" else card_open(p, mode)
        t.SAVE_LOG = lambda: None
        t.utime = types.SimpleNamespace(sleep=lambda s: None)
        _hw()._rom = types.SimpleNamespace(put=lambda v: None)
        _hw()._bank = types.SimpleNamespace(put=lambda v: None)
        test_format_tap(t, root, sent)
        test_list(t, root, sent)
        test_label(t, root, sent)
        test_rm(t, root, sent)
        test_dir_range(t, sent)
        test_ffw_by_file(t, sent)
        test_md(t, root, sent)
        test_shorten(t)
        test_boot(t, cfg)
    finally:
        shutil.rmtree(root, ignore_errors=True)
        shutil.rmtree(cfgdir, ignore_errors=True)
    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
