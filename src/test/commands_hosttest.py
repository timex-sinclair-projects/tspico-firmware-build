"""Host-side test for tpi:newtap, tpi:rm and tpi:boot -- CPython, no Pico.

Runs the REAL TS.tspico handlers against a temporary directory standing in for
the SD card (the CardOS of disk_cmds_hosttest.py, case-insensitive like FAT),
and a temporary config.ini:

  * NEWTAP makes and mounts a new .tap, and refuses a name that exists (any
    case) instead of emptying it;
  * RM removes any file (not only the indexed types), by name, path or listing
    number, and empty folders; it refuses the mounted file, a missing name, a
    non-empty folder and the current folder -- before its Y/N prompt;
  * BOOT saves the memory type with the slot, LOAD_CONFIG uses both once and
    puts back flash slot 1, and MEM 3 is refused.

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


def test_newtap(t, root, sent):
    print("tpi:newtap")
    del sent[:]
    run(t, t.NEW_TAP, "tpi:newtap fresh")
    check(D.on_card(root, "fresh.tap"), "makes fresh.tap")
    check(t.mounted[-1].lower().endswith("/fresh.tap") and t.TSP.append,
          "mounts it with append on")
    check(sent[-1][3] == t._1_OK, "answers OK")

    del sent[:]
    n = len(t.mounted)
    run(t, t.NEW_TAP, "tpi:newtap chess")
    check(sent[-1][3] == t._3_F_Invalid_file, "an existing name (other case) is F (%r)" % (sent[-1],))
    check(os.path.getsize(os.path.join(root, "CHESS.TAP")) == 1500, "and the file is untouched")
    check(len(t.mounted) == n, "and nothing is mounted")

    del sent[:]
    run(t, t.NEW_TAP, "tpi:newtap chess.tap")
    check(sent[-1][3] == t._3_F_Invalid_file, "the same with .tap given")


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
        t.ROM = types.SimpleNamespace(put=lambda v: None)
        t.BANK = types.SimpleNamespace(put=lambda v: None)
        test_newtap(t, root, sent)
        test_rm(t, root, sent)
        test_boot(t, cfg)
    finally:
        shutil.rmtree(root, ignore_errors=True)
        shutil.rmtree(cfgdir, ignore_errors=True)
    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
