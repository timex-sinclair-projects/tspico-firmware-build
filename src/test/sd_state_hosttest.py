"""Host-side test: the TS-Pico without an SD card, and with a card swapped.

The SD card is a state now, not a condition for running (issue #43):

  * ACTIVATE_SD records whether a card is in (TSP.sd_present) and which one
    (TSP.sd_cid, the card's CID register). Once the card is known to be
    missing it tries once, not five times: with no card each attempt costs
    ~0.5 s and every command would stall ~5 s.
  * A card that comes back, or a different card, is set up again
    (SD_REVALIDATE): a blank card gets its TAP folder; the current folder
    and the mounted file are kept if the card has them; a different card
    turns append off and drops open channels.
  * A command that needs the card, with none in, looks once more and then
    answers "No SD card. Insert one and / try again." (always shown) with
    Report J; channel commands get a bare J. Commands that don't need the
    card run as before.
  * SD_CALL answers J and that message when the card is missing.

(SAVE's card check is in save_ts_hosttest.py; boot without a card in
sd_wedged_hosttest.py.)

Run:  python3 src/test/sd_state_hosttest.py
"""

import os
import re
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


def tsp(**kw):
    base = dict(zx48=False, f_name="", append=False, cur_path="/sd/TAP", VERBOSE=False,
                LOG_LEVEL=2, offset=0, offset_tbl=[], tap_idx=0, sd_present=True, sd_cid=5,
                sd_listing_ok=True, save_no_card=False)
    base.update(kw)
    return types.SimpleNamespace(**base)


def test_attempts(t):
    print("ACTIVATE_SD: how many tries")
    state = {"n": 0, "card": False, "cid": 7}

    def sdcard(spi, cs):
        state["n"] += 1
        if not state["card"]:
            raise OSError(19, "no SD card")
        return types.SimpleNamespace(CID=state["cid"])
    t.SDCard = sdcard
    _hw().SPI = lambda *a, **k: object()
    _hw().StateMachine = lambda *a, **k: types.SimpleNamespace(active=lambda *x: None)
    t.os = types.SimpleNamespace(mount=lambda sd, p: None)
    t.SAVE_LOG = lambda: None
    seen = []
    t.SD_REVALIDATE = lambda changed: seen.append(changed)

    t.TSP = tsp(sd_present=True, sd_cid=7)
    try:
        t.ACTIVATE_SD()
    except OSError:
        pass
    check(state["n"] == 5 and t.TSP.sd_present is False,
          "card believed in, now gone: 5 tries, then sd_present False (%d)" % state["n"])

    state["n"] = 0
    try:
        t.ACTIVATE_SD()
        raised = False
    except OSError as e:
        raised = e.args[0] == 19
    check(state["n"] == 1 and raised, "card known missing: 1 try, OSError(19) (%d)" % state["n"])

    state["n"], state["card"] = 0, True
    t.ACTIVATE_SD()
    check(t.TSP.sd_present and seen == [False],
          "the same card back: set up again, not as a different card (%r)" % seen)

    del seen[:]
    t.ACTIVATE_SD()
    check(seen == [], "card still in: nothing to set up")

    state["cid"] = 8
    t.ACTIVATE_SD()
    check(seen == [True] and t.TSP.sd_cid == 8, "a different card (CID changed): set up as new (%r)" % seen)

    # The driver gives CID 0 when it can't read the CID (CMD10 failed).
    del seen[:]
    state["cid"] = 0
    t.ACTIVATE_SD()
    check(seen == [] and t.TSP.sd_cid == 8,
          "CID unreadable (0) on the same card: not a swap, known CID kept (%r, %r)"
          % (seen, t.TSP.sd_cid))
    state["cid"] = 8
    t.ACTIVATE_SD()
    check(seen == [], "CID readable again, same card: still nothing to do (%r)" % seen)
    state["cid"] = 9
    t.ACTIVATE_SD()
    check(seen == [True] and t.TSP.sd_cid == 9, "then a real change is still seen (%r)" % seen)

    # SD_TRY_MS: a card that is in but not answering takes ~4 s an attempt
    # (the driver's _recover waits out three 1 s busy timeouts, then CMD0's
    # 500 ms). Five of those ran past the 2068's ~19.9 s READY wait.
    print("ACTIVATE_SD: no new attempt once SD_TRY_MS has gone")

    class Clock:
        ms = 0
        def ticks_ms(self):
            return self.ms
        ticks_us = ticks_ms
        ticks_diff = staticmethod(lambda a, b: a - b)
        def sleep_ms(self, n):
            self.ms += n
        def sleep(self, s):
            self.ms += int(s * 1000)
    real_time = t.time
    t.time = clock = Clock()
    try:
        for per, want, what in ((4000, 2, "not answering (~4 s an attempt): 2 attempts"),
                                (500, 5, "empty slot or cold card (~0.5 s an attempt): all 5")):
            state["n"], state["card"] = 0, False
            t.TSP = tsp(sd_present=True, sd_cid=9)

            def slow(spi, cs, per=per):
                state["n"] += 1
                clock.ms += per
                raise OSError(19, "no SD card")
            t.SDCard = slow
            clock.ms = 0
            try:
                t.ACTIVATE_SD()
                msg = "mounted?"
            except OSError as e:
                msg = str(e)
            check(state["n"] == want and "after %d attempts" % want in msg
                  and clock.ms < 10000,
                  "%s, %d ms, under the 2068's ~19.9 s (%d, %r)" % (what, clock.ms, state["n"], msg))

        state["n"] = 0
        t.TSP = tsp(sd_present=True, sd_cid=9)
        calls = []

        def late(spi, cs):
            state["n"] += 1
            clock.ms += 4000 if state["n"] == 1 else 500
            if state["n"] < 2:
                raise OSError(19, "not ready")
            return types.SimpleNamespace(CID=9)
        t.SDCard = late
        clock.ms = 0
        t.ACTIVATE_SD()
        check(state["n"] == 2 and t.TSP.sd_present,
              "a slow first attempt, then the card answers: mounted on attempt 2")
    finally:
        t.time = real_time


class Card(D.CardOS):
    """CardOS plus the Pico's own flash for /TMP (FORGET_MOUNT's copies)."""

    def remove(self, p):
        if p.startswith("/TMP/"):
            self.flash_removed.append(p)
            return
        D.CardOS.remove(self, p)


def revalidate_env(t, root):
    D.build_card(root)
    sent = D.setup(t, root)
    card = Card(root)
    card.flash_removed = []
    t.os = card
    t.TSP = tsp(cur_path="/sd/TAP/GAMES", f_name="/sd/TAP/CHESS.TAP", append=True,
                offset_tbl=[1, 2], tap_idx=1)
    t.CHANNELS = types.SimpleNamespace(closed=[], close_all=lambda: t.CHANNELS.closed.append(1))
    t.prev_path = "/sd/TAP/FULL"
    t.prn_path = "/sd/VLPRINT/PRN0001.TXT"
    return card, sent


def test_revalidate(t, root):
    print("SD_REVALIDATE: the same card back")
    card, _ = revalidate_env(t, root)
    t.SD_REVALIDATE(False)
    check(t.TSP.cur_path == "/sd/TAP/GAMES" and t.TSP.f_name == "/sd/TAP/CHESS.TAP" and t.TSP.append,
          "folder, mounted file and append kept")
    check(t.CHANNELS.closed == [] and t.prn_path, "channels and printer capture kept")
    check(card.cwd == "/sd/TAP/GAMES" and t.dir_files_calls == 1 and t.alldirs == ["/TAP"],
          "in the folder, listing and directory list rebuilt")

    print("SD_REVALIDATE: a different card that has the same folder and file")
    card, _ = revalidate_env(t, root)
    t.SD_REVALIDATE(True)
    check(t.TSP.cur_path == "/sd/TAP/GAMES" and t.TSP.f_name == "/sd/TAP/CHESS.TAP",
          "folder and mounted file kept")
    check(not t.TSP.append, "append switched off: saves must not land in the other card's file")
    check(t.CHANNELS.closed == [1] and t.prn_path is None, "open channels and printer capture dropped")

    print("SD_REVALIDATE: a different card without them")
    card, _ = revalidate_env(t, root)
    shutil.rmtree(os.path.join(root, "GAMES"))
    shutil.rmtree(os.path.join(root, "FULL"))
    os.remove(os.path.join(root, "CHESS.TAP"))
    t.SD_REVALIDATE(True)
    check(t.TSP.cur_path == "/sd/TAP" and t.prev_path is None,
          "folder gone: back to the top; MOVE TO \"\" target gone too")
    check(t.TSP.f_name == "" and t.TSP.offset_tbl == [] and not t.TSP.append,
          "mounted file gone: unmounted")
    check(sorted(card.flash_removed) == ["/TMP/temp.bin", "/TMP/temp.tap"],
          "its flash copies removed, each on its own (%r)" % card.flash_removed)

    print("SD_REVALIDATE: a blank card (no TAP folder)")
    card, _ = revalidate_env(t, root)
    shutil.rmtree(root)
    t.TSP.cur_path, t.TSP.f_name = "/sd/TAP", ""
    t.SD_REVALIDATE(True)
    check(os.path.isdir(root) and t.TSP.cur_path == "/sd/TAP", "TAP folder made; at the top")


def run(t, text, sa, ext=None, load_cmd=0, card=False, back=False):
    raw = text.encode()
    mq = P.FakeMQ(P.make_body(raw))
    P.fresh(t, mq)
    t.TSP = tsp(sd_present=card)
    probes = []

    def probe(*a):
        probes.append(1)
        if back:
            t.TSP.sd_present = True
        return back
    t.SD_PROBE = probe
    t.PROCESS_CMD(P.make_pre(raw, load_cmd), sa, ext or {})
    # SEND_MSG queues message text as 1-character strings (StateMachine.put
    # takes either); compare as byte values
    return [b if isinstance(b, int) else ord(b) for b in mq.tx_log], probes


def test_gate(t):
    print("PROCESS_CMD with no card")
    ran = []

    def handler(name):
        def h(pre, cmd):
            ran.append(name)
            t.MQ.put(0x01)
            t.MQ_READY()
        return h
    sa = {k: handler(k) for k in ("TPI:DIR", "TPI:INFO", "TPI:HELP", "TPI:CHRD", "TPI:VERBOSE")}
    msg = list(t.NO_CARD_MSG.encode())

    del ran[:]
    tx, probes = run(t, "tpi:dir", sa)
    check(ran == [] and probes == [1], "tpi:dir: looks for the card once, handler not run")
    check(tx == [0x81, 10, 0x0D] + msg + [0, 0x01],
          "the message is shown even with VERBOSE off, then Report J, then one pre-load")

    del ran[:]
    tx, probes = run(t, "tpi:chrd", sa)
    check(ran == [] and tx == [10, 0x01], "tpi:chrd (mid-statement): a bare J, nothing printed (%r)" % tx)

    del ran[:]
    tx, probes = run(t, "tpi:frogger.tap", sa, load_cmd=1)
    check(tx[:2] == [0x81, 10], "LOAD \"tpi:name\": refused the same way")

    del ran[:]
    run(t, "tpi:info", sa)
    run(t, "tpi:verbose on", sa)
    run(t, "tpi:help", sa)
    check(ran == ["TPI:INFO", "TPI:VERBOSE", "TPI:HELP"], "info, verbose, help without a topic: run as usual")

    del ran[:]
    tx, _ = run(t, "tpi:help rm", sa)
    check(ran == [] and tx[:2] == [0x81, 10], "help with a topic (a file on the card): refused")

    del ran[:]
    run(t, "tpi:.mine", sa, ext={"TPI:.MINE": lambda mq, tsp, pre, cmd: ran.append("ext") or t.MQ.put(1)})
    check(ran == ["ext"], "external commands decide for themselves")

    del ran[:]
    tx, probes = run(t, "tpi:dir", sa, back=True)
    check(ran == ["TPI:DIR"] and probes == [1], "card put back: the next command finds it and runs")

    del ran[:]
    tx, probes = run(t, "tpi:dir", sa, card=True)
    check(ran == ["TPI:DIR"] and probes == [], "card in: no extra look, runs as before")


def test_sd_call(t):
    print("SD_CALL")
    t.DEACTIVATE_SD = lambda: None
    t.ACTIVATE_MQ = lambda *a, **k: None
    t.LOG = lambda *a: None

    def gone(*a, **k):
        t.TSP.sd_present = False
        raise OSError(19, "no SD card")
    t.TSP = tsp(sd_present=False)
    t.ACTIVATE_SD = gone
    check(t.SD_CALL(lambda: "done") == (t.NO_CARD_MSG, t._10_J_Invalid_IO),
          "no card: the no-card message and J")

    def ok(*a, **k):
        return None
    t.TSP = tsp(sd_present=True)
    t.ACTIVATE_SD = ok

    def fails():
        raise OSError(5, "EIO")
    check(t.SD_CALL(fails) == ("SD card error", t._3_F_Invalid_file),
          "card in but failing: SD card error, F (as before)")


def test_info(t):
    print("tpi:info looks at the card")
    sent = []
    t.SEND_MSG2 = lambda msg, st, *a: sent.append(msg)
    t.os = types.SimpleNamespace(statvfs=lambda p: (4096, 4096, 256, 128, 128, 0, 0, 0, 0, 255))
    t.gc = types.SimpleNamespace(mem_free=lambda: 100000, collect=lambda: None)
    t.sd_space = (8_000_000_000, 7_750_000_000)                 # what the last listing read
    plain = lambda m: re.sub("[\x10\x11].", "", m)                # without the colour codes
    t.files = []

    def probe(*a):                       # the card was taken out after the last command
        t.TSP.sd_present = False
        return False
    t.SD_PROBE = probe
    t.TSP = tsp(sd_present=True, FW_VERSION="2.1", ROM_VERSION="2.1", ROM_SM=10, bank_sm=1,
                LOG_LEVEL=2)
    t.GETINFO(bytearray(10), "D..tpi:info")
    check(sent and re.search(r"SD card +none", plain(sent[-1])) and "7.5 GB" not in plain(sent[-1]),
          "card pulled since the last command: info says none, not the old card")

    t.SD_PROBE = lambda *a: True
    t.TSP.sd_present = True
    t.GETINFO(bytearray(10), "D..tpi:info")
    check(re.search(r"SD card +7\.5 GB, 7\.2 GB free", plain(sent[-1])), "card in: its space shown")


def main():
    P.install_fakes()
    ext = types.ModuleType("dev_extcmd")
    ext.EXT_SA_FUNCT = {}
    sys.modules["dev_extcmd"] = ext
    import TS.tspico as t
    t.TLM_ENABLED = False
    ft = P.FakeTime()
    t.time = ft
    import TS.tspico_io as tio
    tio.time = ft
    t.utime = ft
    # Everything the tests below (and disk_cmds_hosttest.setup) replace, put
    # back between tests so each one runs the real code it is about.
    real = {n: getattr(t, n) for n in ("ACTIVATE_SD", "SD_REVALIDATE", "SD_CALL", "SD_PROBE",
                                       "DEACTIVATE_SD", "ACTIVATE_MQ", "LOG", "os",
                                       "SEND_MSG", "SEND_MSG2", "DIR_FILES", "GET_DIRS",
                                       "MOUNT_FILE", "SDCard")}
    real_hw = {n: getattr(_hw(), n) for n in ("SPI", "StateMachine")}
    logs = []
    t.LOG = lambda msg, level: logs.append((level, msg))

    root = tempfile.mkdtemp(prefix="sd_state.")
    try:
        test_attempts(t)
        t.SD_REVALIDATE = real["SD_REVALIDATE"]
        test_revalidate(t, root)
        for n, v in real.items():
            setattr(t, n, v)
        for n, v in real_hw.items():
            setattr(_hw(), n, v)
        t.LOG = lambda msg, level: logs.append((level, msg))
        test_gate(t)
        test_sd_call(t)
        test_info(t)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
