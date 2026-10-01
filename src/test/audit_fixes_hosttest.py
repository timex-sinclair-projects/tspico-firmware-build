"""Host-side test for five hang/crash fixes from the 2026-09-30 assumption audit.

Each fix removes an assumption that was true when the code was written and
stopped being true later. Every case below FAILS on the code before the fix
(checked on 2d134dd) and passes after it:

  1. SAVE_LOG left `busy` stuck at True when its flash write raised, and every
     `while busy: pass` then spun for ever (COPY_FILE -- every LOAD "tpi:file"
     mount -- and the main loop's SAVE / LOAD branches).
  2. LOG read TSP.LOG_LEVEL before TSP existed, so the boot-time LOG calls in
     LOAD_CONFIG (no config.ini, a bad one, a bad ROM_SM) crashed the boot.
  3. CH_CLOSE wrote to the card -- padding a part-written record -- without
     activating it (the card is unmounted between commands).
  4. tpi:cd .. from a subfolder went through Ryan's hand-made ".." branch, which
     built a *relative* path ("sd/TAP"); it only worked when MicroPython's
     current directory happened to be the VFS root.
  5. tpi:cd fell back to cur_path + "/" + arg when catalog.resolve() refused a
     path -- which it does only for paths that climb above /sd/TAP -- so
     tpi:cd ../.. could leave the card root.
  6. GETLOG's bare `except:` swallowed CmdAbort (BREAK at the Scroll? prompt).

NOTE ON SCOPE: control flow only, on CPython with the usual fakes. None of
this observes the Z80 bus; see src/CLAUDE.md.

Run:  python3 src/test/audit_fixes_hosttest.py
"""

import builtins
import os
import shutil
import sys
import tempfile
import threading
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import process_cmd_hosttest as P                                # noqa: E402
import disk_cmds_hosttest as D                                  # noqa: E402

results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg)


def finishes(fn, seconds=3):
    """Run fn in a daemon thread: (finished, result or exception)."""

    box = {}

    def run():
        try:
            box["r"] = fn()
        except BaseException as e:                              # noqa: B036
            box["r"] = e
    th = threading.Thread(target=run, daemon=True)
    th.start()
    th.join(seconds)
    return not th.is_alive(), box.get("r")


# ---------------------------------------------------------------------------
# 1. SAVE_LOG / busy
# ---------------------------------------------------------------------------

def test_busy(t, root):
    print("1. SAVE_LOG must not leave `busy` stuck; nothing waits on it for ever")
    t.time = P.FakeTime()                                       # bounded waits trip fast
    t.LOG = lambda *a: None
    t.led = types.SimpleNamespace(value=lambda *a: None, toggle=lambda: None)

    def full_flash(p, mode="r"):
        raise OSError(28, "ENOSPC")                             # flash full
    t.open = full_flash
    t.log_entries = ["[1]ERROR:something\n"]
    t.busy = False
    try:
        t.SAVE_LOG()
    except OSError:
        pass                                                    # on core1 the thread just dies
    check(t.busy is False, "SAVE_LOG whose write fails still clears busy (%r)" % t.busy)
    check(t.log_entries == [], "... and drops the entries it couldn't write (no unbounded growth)")

    # COPY_FILE (every LOAD "tpi:file" mount) with core1 stuck busy.
    src = os.path.join(root, "src.tap")
    dst = os.path.join(root, "dst.tap")
    with open(src, "wb") as f:
        f.write(b"x" * 2000)
    t.open = builtins.open
    t.busy = True                                               # a SAVE_LOG thread died holding it
    done, r = finishes(lambda: t.COPY_FILE(src, dst))
    check(done and r is True, "COPY_FILE returns with busy stuck at True (%s, %r)"
          % ("returned" if done else "still spinning", r))
    check(done and os.path.exists(dst) and open(dst, "rb").read() == b"x" * 2000,
          "... and the copy is complete")

    # The bounded wait the main loop's SAVE / LOAD branches now use.
    t.busy = True
    done, r = finishes(lambda: t.WAIT_CORE1(3000, "test"))
    check(done and r is False, "WAIT_CORE1 gives up when busy never clears (%r)" % (r,))
    t.busy = False
    done, r = finishes(lambda: t.WAIT_CORE1(3000, "test"))
    check(done and r is True, "WAIT_CORE1 returns True at once when core1 is idle")
    t.busy = False


# ---------------------------------------------------------------------------
# 2. LOG before TSP exists
# ---------------------------------------------------------------------------

def test_log_before_tsp(t, root):
    print("2. LOG / LOAD_CONFIG at boot, before TSP exists")
    t.time = P.FakeTime()
    if "TSP" in t.__dict__:
        del t.TSP                                               # the state at boot
    t.log_to_serial = False
    t.log_entries = []
    t.busy = False
    t.LOG = REAL["LOG"]
    t.SAVE_LOG = REAL["SAVE_LOG"]
    try:
        t.LOG("before TSP", 1)
        ok = True
    except NameError as e:
        ok = e
    check(ok is True, "LOG before TSP exists doesn't raise (%r)" % (ok,))

    cfg = os.path.join(root, "config.ini")
    logf = os.path.join(root, "activity.log")

    def fopen(p, mode="r"):
        return open(cfg if p == "config.ini" else logf if p == "/activity.log" else p, mode)
    t.open = fopen
    for name, content in (("no config.ini", None), ("a truncated config.ini", '{"ROM_SL'),
                          ("ROM_SM 4 (selects nothing)", '{"ROM_SM": 4}')):
        if os.path.exists(cfg):
            os.remove(cfg)
        if content is not None:
            with open(cfg, "w") as f:
                f.write(content)
        try:
            v = t.LOAD_CONFIG()
            ok = v["ROM_SLOT"] == 1 and v["ROM_SM"] == 10
        except Exception as e:                                  # noqa: BLE001
            ok = e
        check(ok is True, "LOAD_CONFIG with %s boots on the defaults (%r)" % (name, ok))
    t.open = builtins.open


# ---------------------------------------------------------------------------
# 3. CH_CLOSE and the card
# ---------------------------------------------------------------------------

def test_ch_close(t, root):
    print("3. CLOSE # pads an open record with the card ACTIVE")
    D.build_card(root)
    sent = D.setup(t, root)
    t.TSP.sd_present = True
    state = {"active": False, "card": True, "inactive_io": []}
    card_open = t.open

    def activate(*a, **k):
        if not state["card"]:
            t.TSP.sd_present = False
            raise OSError(19, "ENODEV")
        state["active"] = True

    def deactivate(*a, **k):
        state["active"] = False

    def fopen(p, mode="r"):
        if not state["active"]:
            state["inactive_io"].append((p, mode))
        return card_open(p, mode)
    t.ACTIVATE_SD, t.DEACTIVATE_SD, t.open = activate, deactivate, fopen
    real_stat = t.os.stat

    def stat(p):
        if not state["active"]:
            state["inactive_io"].append((p, "stat"))
        return real_stat(p)
    t.os.stat = stat
    tx = []
    t.CMD_PUT = lambda b: tx.append(b)
    t.CH_READY = lambda: tx.append("READY")
    t.CHANNELS.close_all()

    def cmd(handler, text, stream, par2=0):
        pre = bytearray(10)
        pre[3], pre[5], pre[6] = stream, par2 & 0xFF, par2 >> 8
        del tx[:]
        del sent[:]
        handler(pre, "xxx" + text)
        return tx[0] if tx else None

    check(cmd(t.CH_OPEN, "tpi:chopen u recs.dat", 4, 6) == t._1_OK, "chopen u, record length 6")
    cmd(t.CH_WRITE, "tpi:chwr " + (bytes([23, 2, 0]) + b"ab").hex(), 4)   # TAB 2;"ab"; (no CR)
    del state["inactive_io"][:]
    st = cmd(t.CH_CLOSE, "tpi:chclose", 4)
    check(st == t._1_OK, "chclose: OK (%r)" % (st,))
    check(not state["inactive_io"], "no card access while the card was inactive (%r)"
          % (state["inactive_io"],))
    data = open(os.path.join(root, "recs.dat"), "rb").read()
    check(data == b"      ab    ", "the open record was padded to its length (%r)" % (data,))
    check(4 not in t.CHANNELS.table, "the stream is closed")

    # A read stream (nothing to write): no card needed, so none is touched --
    # CLOSE # works with the card gone, which is why TPI:CHCLOSE stays SD_FREE.
    check(cmd(t.CH_OPEN, "tpi:chopen r recs.dat", 5) == t._1_OK, "chopen r")
    state["card"] = False
    st = cmd(t.CH_CLOSE, "tpi:chclose", 5)
    check(st == t._1_OK and 5 not in t.CHANNELS.table,
          "closing a read stream with no card: OK, without the card (%r)" % (st,))

    # An open record and no card: the padding can't be written. Say so (J,
    # like any other no-card channel op) and KEEP the stream open: the fdd
    # ROM's CLOSE # stops at the error before freeing its side of the
    # channel, so BASIC still has it open too. Once the card is back, the
    # same CLOSE # works and writes the padding.
    state["card"] = True
    t.TSP.sd_present = True
    cmd(t.CH_OPEN, "tpi:chopen u recs2.dat", 6, 6)
    cmd(t.CH_WRITE, "tpi:chwr " + (bytes([23, 1, 0]) + b"z").hex(), 6)
    state["card"] = False
    st = cmd(t.CH_CLOSE, "tpi:chclose", 6)
    check(st == t._10_J_Invalid_IO and 6 in t.CHANNELS.table,
          "open record, no card: J, and the stream stays open (%r)" % (st,))
    state["card"] = True
    t.TSP.sd_present = True
    st = cmd(t.CH_CLOSE, "tpi:chclose", 6)
    data = open(os.path.join(root, "recs2.dat"), "rb").read()
    check(st == t._1_OK and 6 not in t.CHANNELS.table and data == b"z     ",
          "card back, CLOSE # again: OK, closed, padded (%r, %r)" % (st, data))
    t.CHANNELS.close_all()


# ---------------------------------------------------------------------------
# 4/5. tpi:cd
# ---------------------------------------------------------------------------

def test_cd(t, root):
    print("4/5. tpi:cd .. and tpi:cd ../.. go through catalog.resolve")
    D.build_card(root)
    D.setup(t, root)
    st, _ = t.ChangeDir("games/arcade")
    check(st == t._1_OK and t.TSP.cur_path == "/sd/TAP/games/arcade", "cd games/arcade")
    st, _ = t.ChangeDir("..")
    check(st == t._1_OK and t.TSP.cur_path == "/sd/TAP/games",
          "cd .. from two levels down: the parent, as an absolute path (%r, %s)"
          % (st, t.TSP.cur_path))
    st, _ = t.ChangeDir("..")
    check(st == t._1_OK and t.TSP.cur_path == "/sd/TAP", "cd .. again: the root (%r, %s)"
          % (st, t.TSP.cur_path))
    st, _ = t.ChangeDir("..")
    check(st == t._1_OK and t.TSP.cur_path == "/sd/TAP", "cd .. at the root: stays there")
    t.ChangeDir("games")
    st, _ = t.ChangeDir("../..")
    check(st == t._3_F_Invalid_file and t.TSP.cur_path == "/sd/TAP/games",
          "cd ../.. from one level down: F, unchanged -- never above /sd/TAP (%r, %s)"
          % (st, t.TSP.cur_path))


# ---------------------------------------------------------------------------
# 6. GETLOG and BREAK
# ---------------------------------------------------------------------------

def test_getlog(t, root):
    print("6. tpi:log: BREAK at the Scroll? prompt is not swallowed")
    D.setup(t, root)
    logf = os.path.join(root, "activity.log")
    with open(logf, "w") as f:
        f.write("[1]ERROR:x\n" * 10)
    t.os = types.SimpleNamespace(stat=lambda p: (0,) * 6 + (os.path.getsize(logf),))
    t.open = lambda p, mode="r": open(logf, "rb")
    sent = []
    t.SEND_MSG = lambda msg, msg1, st, force=False: sent.append((msg, st))

    def break_at_prompt(msg, st, exp=True):
        raise t.CmdAbort(1)
    t.SEND_MSG2 = break_at_prompt
    try:
        t.GETLOG(bytearray(10), "D..tpi:log")
        got = "returned (CmdAbort swallowed), sent %r" % (sent,)
    except t.CmdAbort:
        got = True
    check(got is True, "CmdAbort from SEND_MSG2 propagates out of GETLOG (%s)" % (got,))
    check(not sent, "... and no error message is sent to the aborting Z80")

    class NoRoom:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def seek(self, *a):
            pass

        def readinto(self, buf):
            raise MemoryError
    t.open = lambda p, mode="r": NoRoom()
    del sent[:]
    shown = []
    t.SEND_MSG2 = lambda msg, st, exp=True: shown.append(msg)
    t.GETLOG(bytearray(10), "D..tpi:log")
    check(sent == [("Log file too large", t._4_Q_Parameter)] and not shown,
          "a log too big for memory still says so, with Q (%r)" % (sent,))


REAL = {}


def main():
    P.install_fakes()
    ext = types.ModuleType("dev_extcmd")
    ext.EXT_SA_FUNCT = {}
    sys.modules["dev_extcmd"] = ext
    import TS.tspico as t
    t.TLM_ENABLED = False
    REAL["LOG"], REAL["SAVE_LOG"] = t.LOG, t.SAVE_LOG
    root = tempfile.mkdtemp(prefix="audit_hosttest.")
    try:
        test_busy(t, root)
        test_log_before_tsp(t, root)
        test_ch_close(t, root)
        test_cd(t, root)
        test_getlog(t, root)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
