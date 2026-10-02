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
  7. tspico_io.ENA_SD's mount-failure path logged through TSP.LOG_LEVEL, but
     tspico_io has no TSP: it raised NameError instead of logging the mount
     error and returning -99.
 21. (§2 #21) SAVE_TS and SAVE_ZX mounted with ENA_SD's single bare
     os.mount, after the 2068 already had "0 OK": a card that came up on a
     second attempt lost the file, and a returned or swapped card skipped
     SD_NOTE_CARD. Their mount now goes through ACTIVATE_SD (SD_MOUNT hook).

Batch A (2026-10-01; the SD-card-ID fix is pinned in sd_state_hosttest.py):

  8. MOUNT_FILE decoded the first 7 raw TAP bytes as UTF-8 to look for
     "ZXTape!", so a TAP starting with a headerless block raised.
  9. LOAD "tpi:-1" mounted the last file (negative index).
 10. tpi:info raised IndexError (Report J) on a TAP that ends with a header.
 11. LOAD_CONFIG let through ROM_SM values tpi:boot/tpi:dock never set, and a
     non-number crashed the boot.
 12. SEND_MSG sent a non-ASCII character as several UTF-8 bytes >= 80h.

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
import re
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
    t.SEND_MSG2 = lambda msg, st, exp=True, colour=False: shown.append(msg)
    t.GETLOG(bytearray(10), "D..tpi:log")
    check(sent == [("Log file too large", t._4_Q_Parameter)] and not shown,
          "a log too big for memory still says so, with Q (%r)" % (sent,))


# ---------------------------------------------------------------------------
# 7. ENA_SD's mount-failure path
# ---------------------------------------------------------------------------

def test_ena_sd():
    print("7. tspico_io.ENA_SD: a failed mount is logged and returns -99")
    import TS.tspico_io as io
    real = io.SDCard, io.os, io.log_entries, io.time, io.SD_MOUNT
    io.SD_MOUNT = None                                          # the bare mount: tspico_io on its own
    io.time = P.FakeTime()                                      # LOG_ADD timestamps with ticks_us

    def no_card(spi, cs):
        raise OSError(19, "ENODEV")                             # init_card: no card
    io.SDCard = no_card
    io.log_entries = ""                                         # tspico_io's log is one string
    try:
        r = io.ENA_SD(2)
        ok = r == -99 and "Mounting SD Card failed" in io.log_entries \
            and "ENODEV" in io.log_entries
        got = (r, io.log_entries)
    except Exception as e:                                      # noqa: BLE001
        ok, got = False, e
    check(ok, "no card: logs the real error and returns -99 (%r)" % (got,))

    # /sd already mounted: os.mount raises EPERM, and the write still has to
    # be able to go ahead on the existing mount -- so ENA_SD must not raise.
    io.SDCard = lambda spi, cs: object()

    def eperm(dev, path):
        raise OSError(1, "EPERM")
    io.os = types.SimpleNamespace(mount=eperm)
    io.log_entries = ""
    try:
        r = io.ENA_SD(2)
        got = r
    except Exception as e:                                      # noqa: BLE001
        got = e
    check(got == -99, "mount refused (already mounted): returns -99, doesn't raise (%r)" % (got,))

    def ctrl_c(spi, cs):
        raise KeyboardInterrupt
    io.SDCard = ctrl_c
    try:
        io.ENA_SD(2)
        got = "swallowed"
    except KeyboardInterrupt:
        got = True
    check(got is True, "Ctrl-C from the host is not swallowed (%r)" % (got,))
    io.SDCard, io.os, io.log_entries, io.time, io.SD_MOUNT = real


# ---------------------------------------------------------------------------
# §2 #21. The SAVE writes mount through ACTIVATE_SD
# ---------------------------------------------------------------------------

def test_save_mount(t):
    print("21. SAVE_TS / SAVE_ZX: the write's mount goes through ACTIVATE_SD")
    import TS.tspico_io as io
    names = ("SDCard", "SPI", "StateMachine", "os", "time", "SAVE_LOG", "SD_REVALIDATE", "TSP", "LOG",
             "ACTIVATE_SD")
    real = {n: getattr(t, n) for n in names}
    t.ACTIVATE_SD = REAL["ACTIVATE_SD"]                         # earlier tests stub it
    check(io.SD_MOUNT is t.SAVE_MOUNT, "tspico sets tspico_io.SD_MOUNT to SAVE_MOUNT")

    state = {"fail": 0, "tries": 0, "cid": 7}
    calls = []

    def sdcard(spi, cs):
        state["tries"] += 1
        if state["fail"]:
            state["fail"] -= 1
            raise OSError(19, "card not ready")
        return types.SimpleNamespace(CID=state["cid"])

    def umount(p):
        calls.append("umount")
        if "mounted" not in calls:
            raise OSError(22, "EINVAL")                     # MicroPython: nothing mounted there

    def mount(sd, p):
        calls.append("mount")
        calls.append("mounted")

    t.SDCard = sdcard
    t.SPI = lambda *a, **k: object()
    t.StateMachine = lambda *a, **k: types.SimpleNamespace(active=lambda *x: None)
    t.os = types.SimpleNamespace(mount=mount, umount=umount)
    t.time = P.FakeTime()
    t.SAVE_LOG = lambda: None
    t.LOG = lambda *a: None
    revalidated = []
    t.SD_REVALIDATE = lambda changed: revalidated.append(changed)
    t.TSP = types.SimpleNamespace(sd_present=True, sd_cid=7, LOG_LEVEL=2)
    try:
        state["fail"] = 1
        try:
            io.ENA_SD(2)
            got = "mounted"
        except Exception as e:                                  # noqa: BLE001
            got = e
        check(got == "mounted" and state["tries"] == 2 and t.TSP.sd_present,
              "a card that is only ready on the second attempt: mounted, no error (%r, %d tries)"
              % (got, state["tries"]))
        check(calls[:2] == ["umount", "mount"],
              "SAVE_MOUNT unmounts first (a stale /sd would be EPERM to ACTIVATE_SD) (%r)" % calls)

        del calls[:]
        calls.append("mounted")                             # /sd left mounted
        state["tries"] = 0
        io.ENA_SD(2)
        check(calls == ["mounted", "umount", "mount", "mounted"] and state["tries"] == 1,
              "a /sd left mounted is unmounted, then mounted again on the first try (%r)" % calls)

        state["tries"], state["fail"] = 0, 99
        try:
            io.ENA_SD(2)
            got = None
        except OSError as e:
            got = e.args[0]
        check(got == 19 and state["tries"] == 5 and t.TSP.sd_present is False,
              "no card: 5 tries, then OSError(19) for the SAVE to catch, sd_present False (%r, %d)"
              % (got, state["tries"]))

        state["fail"], state["cid"] = 0, 8
        t.TSP.sd_present = True
        del revalidated[:]
        io.ENA_SD(2)
        check(revalidated == [True] and t.TSP.sd_cid == 8,
              "a different card: SD_NOTE_CARD sets it up as new (append off, channels closed) (%r)"
              % revalidated)
    finally:
        for n, v in real.items():
            setattr(t, n, v)


# ---------------------------------------------------------------------------
# Batch A (2026-10-01)
# ---------------------------------------------------------------------------

def card_with_tmp(t, root):
    """disk_cmds_hosttest's card, with /TMP (the Pico's flash) in a temp dir."""
    tmp = tempfile.mkdtemp(prefix="audit_tmp.")

    class CardTmp(D.CardOS):
        def real(self, p):
            if p.startswith("/TMP/"):
                return os.path.join(tmp, p[5:])
            return D.CardOS.real(self, p)
    cos = CardTmp(root)
    t.os = cos
    t.open = lambda p, mode="r": open(cos.real(p), mode)
    return cos


def test_mount_bytes(t, root):
    print("8. MOUNT_FILE: TAP signature compared as bytes")
    D.build_card(root)
    D.setup(t, root)
    card_with_tmp(t, root)
    t.MOUNT_FILE, t.COPY_FILE = REAL["MOUNT_FILE"], REAL["COPY_FILE"]
    t.time = P.FakeTime()
    t.busy = False
    t.TSP.offset, t.TSP.tap_idx, t.TSP.append = 0, 0, False
    t.BLINK_ERROR = lambda *a: None
    logs = []
    t.LOG = lambda m, l: logs.append((l, m))
    for name, data, want, what in (
            ("HDRLESS.TAP", bytes([5, 0, 0xFF, 1, 2, 3, 0xFD]), True,
             "first block headerless (FFh at byte 2): mounts"),
            ("NAME80.TAP", bytes([19, 0, 0, 0]) + b"caf\xe9      " + bytes(7), True,
             "header name byte >= 80h: mounts"),
            ("GAMETZX.TAP", b"ZXTape!\x1a\x01\x14\x30\x00", False,
             "a TZX: refused, and the message says TZX")):
        open(os.path.join(root, name), "wb").write(data)
        del logs[:]
        try:
            r = t.MOUNT_FILE("/sd/TAP/" + name)
        except Exception as e:                                  # noqa: BLE001
            r = e
        ok = r is want
        if not want:
            ok = ok and any("TZX" in m for _, m in logs)
        check(ok, "%s (%r)" % (what, r))
    t.LOG = lambda *a: None


def test_index(t):
    print("9. LOAD \"tpi:nnn\": only 0..n-1 is an index")
    t.files = ["A.TAP", "B.TAP"]
    check(t.ResolveIndexName("1") == ("B.TAP", 1), "1 -> the second file")
    check(t.ResolveIndexName("-1") == ("-1", -1), "-1 is not an index (%r)" % (t.ResolveIndexName("-1"),))
    check(t.ResolveIndexName("2") == ("2", -1), "past the end: not an index")
    check(t.ResolveIndexName("game") == ("game", -1), "a name stays a name")


def test_getinfo(t, root):
    print("10. tpi:info on a TAP that ends with a header")
    D.setup(t, root)
    shown = []
    t.SEND_MSG2 = lambda msg, st, exp=True, colour=False: shown.append(msg)
    t.SD_PROBE = lambda *a: True
    t.os = types.SimpleNamespace(statvfs=lambda p: (4096, 4096, 352, 300))
    t.gc = types.SimpleNamespace(mem_free=lambda: 100000, collect=lambda: None)
    t.lista = " " * 64
    t.TSP = types.SimpleNamespace(
        FW_VERSION="2.1", ROM_VERSION="2.1", LOG_LEVEL=2, sd_present=True, ROM_SM=10, bank_sm=1,
        append=False, VERBOSE=False, f_name="/sd/TAP/CUT.TAP", cur_path="/sd/TAP",
        offset_tbl=[[0, 21, " Y", "Program: first"], [21, 10, " N", "10"],
                    [31, 21, " Y", "Program: cut"]],
        tap_idx=2)
    try:
        t.GETINFO(bytearray(10), "D..tpi:info")
        ok = bool(shown) and "Program: cut:no data" in shown[-1]
        got = re.sub("[\x10\x11].", "", shown[-1]).split("Block")[1].split("\r")[0] if shown else shown
    except Exception as e:                                      # noqa: BLE001
        ok, got = False, e
    check(ok, "the last block is a header: shown with 'no data', no IndexError (%r)" % (got,))


def test_rom_sm(t, root):
    print("11. LOAD_CONFIG: ROM_SM is 5, 6, 9 or 10")
    t.time = P.FakeTime()
    t.log_entries = []
    t.LOG = REAL["LOG"]
    t.SAVE_LOG = lambda: None
    cfg = os.path.join(root, "config.ini")
    t.open = lambda p, mode="r": open(cfg if p == "config.ini" else p, mode)
    import json
    for value, want in ((10, 10), (9, 9), (6, 6), (5, 5), (7, 10), (11, 10), (15, 10),
                        (99, 10), ("10", 10), (None, 10)):
        with open(cfg, "w") as f:
            json.dump({"ROM_SM": value}, f)
        try:
            got = t.LOAD_CONFIG()["ROM_SM"]
        except Exception as e:                                  # noqa: BLE001
            got = e
        check(got == want, "ROM_SM %r -> %r (%r)" % (value, want, got))
    t.open = builtins.open
    t.LOG = lambda *a: None


def test_send_msg_bytes(t):
    print("12. SEND_MSG: one byte per character, '?' for anything not printable ASCII")
    sent = []
    t.CMD_PUT = lambda b: sent.append(b)
    t.MQ_READY = lambda: None
    t.CMD_DRAIN = lambda: None
    t.TSP = types.SimpleNamespace(VERBOSE=True)
    REAL["SEND_MSG"]("Copied caf\u00e9~", "x\x00y", t._1_OK)
    body = sent[3:]
    check(all(isinstance(b, int) and 0 <= b < 256 for b in sent),
          "every write is one byte (an int), never a str (%r)" % sent[:6])
    check(body == list(b"Copied caf?~") + [0x0D] + list(b"x?y") + [0x00],
          "\u00e9 -> '?', ~ kept (prints as FREE), 00h in the text -> '?' (%r)" % bytes(body))
    del sent[:]
    REAL["SEND_MSG"]("\rOne\rtwo" + chr(13) + "three\t", "", t._1_OK)
    body = sent[3:]
    check(body == list(b"\rOne\rtwo\rthree?") + [0x00],
          "CR (0Dh) kept as the ROM's new line; other control codes -> '?' (%r)" % bytes(body))


REAL = {}


def main():
    P.install_fakes()
    ext = types.ModuleType("dev_extcmd")
    ext.EXT_SA_FUNCT = {}
    sys.modules["dev_extcmd"] = ext
    import TS.tspico as t
    t.TLM_ENABLED = False
    REAL["LOG"], REAL["SAVE_LOG"] = t.LOG, t.SAVE_LOG
    REAL["MOUNT_FILE"], REAL["COPY_FILE"], REAL["SEND_MSG"] = t.MOUNT_FILE, t.COPY_FILE, t.SEND_MSG
    REAL["ACTIVATE_SD"] = t.ACTIVATE_SD
    root = tempfile.mkdtemp(prefix="audit_hosttest.")
    try:
        test_busy(t, root)
        test_log_before_tsp(t, root)
        test_ch_close(t, root)
        test_cd(t, root)
        test_getlog(t, root)
        test_ena_sd()
        test_save_mount(t)
        test_mount_bytes(t, root)
        test_index(t)
        test_getinfo(t, root)
        test_rom_sm(t, root)
        test_send_msg_bytes(t)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
