"""Host-side test: an SD card that wedges MID-SESSION must not brick the Pico.

Field log, 2026-09-26: a card failed a write (EIO), and from then on
ACTIVATE_SD could not mount it ("[Errno 19] ENODEV" x5) until power-cycle.
ACTIVATE_SD used to drop into BLINK_ERROR forever at that point -- from
inside any command that touches the card (CD, MD, RM, NEWTAP, HELP, every
MOUNT_FILE). It now raises OSError instead, and:

  * PROCESS_CMD's handler catches it; FAIL_CMD sees sd_active, hands the
    bus back (DEACTIVATE_SD -> ACTIVATE_MQ) and gives the Z80 a Report J
    status on the LIVE bus state machine, then the V6 pre-load. Without the
    hand-back those bytes went into the parked NULL_SM and the TS-Pico was
    deaf for the rest of the session -- the same thing happens when a
    handler dies of EIO after a mount that DID succeed, so that's covered
    too;
  * the dispatcher's post-SAVE remount (not under PROCESS_CMD) logs and
    re-arms instead of ending TS2068_IO, and doesn't spend another five
    attempts on the directory refresh;
  * boot, with no card at all, carries on into the dispatcher without one
    (it used to end in the blink loop): TSP.sd_present stays False and the
    commands that need a card are refused (sd_state_hosttest.py).

Runs the REAL TS.tspico ACTIVATE_SD / DEACTIVATE_SD / ACTIVATE_MQ /
MQ_READY / FAIL_CMD / PROCESS_CMD / MDIR / MOUNT_FILE / TS2068_IO; only
the hardware (StateMachine, SPI, SDCard, os) is faked.

Run:  python3 src/test/sd_wedged_hosttest.py
"""

import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import process_cmd_hosttest as P                                # noqa: E402

READY = "mov(y, invert(null))"


class Bricked(BaseException):
    """Something reached BLINK_ERROR."""


class LoopDone(BaseException):
    """The dispatcher came back round to poll a bus SM we've finished with."""


class ReachedDispatcher(BaseException):
    pass


class SM(P.FakeMQ):
    """A PIO state machine. `prog` tells the bus SM from the parked one."""

    def __init__(self, prog, stop_when_empty=False):
        P.FakeMQ.__init__(self)
        self.prog = prog
        self.stop_when_empty = stop_when_empty

    def rx_fifo(self):
        if not self.rx and self.stop_when_empty:
            raise LoopDone()
        return len(self.rx)


class Card:
    """SDCard + os, with a switch for 'wedged': mount fails ENODEV."""

    def __init__(self):
        self.wedged = False
        self.fail_on = None           # an os call that raises EIO once mounted
        self.attempts = 0
        self.mounted = False

    def sdcard(self, spi, cs):
        self.attempts += 1
        if self.wedged:
            raise OSError(19, "ENODEV")
        return object()

    def _maybe_fail(self, op):
        if op == self.fail_on:
            raise OSError(5, "EIO")

    def os(self):
        card = self

        def mount(sd, p):
            card.mounted = True

        def umount(p):
            if not card.mounted:
                raise OSError(22, "EINVAL")
            card.mounted = False

        def chdir(p):
            card._maybe_fail("chdir")

        def stat(p):
            raise OSError(2, "ENOENT")

        return types.SimpleNamespace(
            mount=mount, umount=umount, chdir=chdir, stat=stat,
            mkdir=lambda p: card._maybe_fail("mkdir"),
            remove=lambda p: None,
            ilistdir=lambda *a: iter([]),
            statvfs=lambda p: (512, 512, 1000, 500, 500, 0, 0, 0, 0, 255))


results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg)


def install(t):
    """Fresh card, SM factory and log for one scenario."""
    env = types.SimpleNamespace(card=Card(), sms=[], logs=[], blinks=0,
                                stop_new_bus=False)

    def state_machine(n, prog, **k):
        sm = SM(getattr(prog, "__name__", str(prog)),
                stop_when_empty=env.stop_new_bus)
        env.sms.append(sm)
        return sm

    def blink():
        env.blinks += 1
        raise Bricked()

    t.StateMachine = state_machine
    t.SPI = lambda *a, **k: object()
    t.SDCard = env.card.sdcard
    t.os = env.card.os()
    t.BLINK_ERROR = blink
    t.LOG = lambda msg, level: env.logs.append((level, msg))
    t.sd_active = False
    return env


def bus_sms(env):
    return [sm for sm in env.sms if sm.prog != "NULL_SM"]


def test_activate_sd(t):
    print("ACTIVATE_SD, card wedged")
    env = install(t)
    env.card.wedged = True
    t.TSP = types.SimpleNamespace(LOG_LEVEL=0, sd_present=True, sd_cid=0, sd_listing_ok=True, save_no_card=False)           # a card was in
    try:
        t.ACTIVATE_SD()
        outcome = "returned"
    except OSError as e:
        outcome = "OSError %s" % e.args[0]
    except Bricked:
        outcome = "bricked"
    check(outcome == "OSError 19",
          "raises OSError(ENODEV) instead of looping in BLINK_ERROR (%s)" % outcome)
    check(env.card.attempts == 5 and env.blinks == 0,
          "still 5 attempts, BLINK_ERROR never called")
    check(t.sd_active is True, "sd_active left True (bus is still parked)")
    check(any(lvl == 2 and "after 5 attempts" in m for lvl, m in env.logs),
          "the failure is logged as an ERROR")


def run_cmd(t, env, text, load_cmd=0):
    """PROCESS_CMD one 'B' command arriving on a live bus SM."""
    t.ACTIVATE_MQ()                            # the session's bus SM
    bus = t.MQ
    bus.rx = list(P.make_body(text))
    t.TSP = types.SimpleNamespace(
        zx48=False, f_name="", append=False, cur_path="/sd/TAP",
        VERBOSE=False, LOG_LEVEL=0, offset=0, offset_tbl=[], tap_idx=0,
        sd_present=True, sd_cid=0, sd_listing_ok=True, save_no_card=False)
    t.files = ["GAME.TAP"]
    t.files_upper = ["GAME.TAP"]
    t.alldirs = []
    try:
        t.PROCESS_CMD(P.make_pre(text, load_cmd), {"TPI:MD": t.MDIR}, {})
        return bus, None
    except BaseException as e:                 # noqa: BLE001
        return bus, e


def test_process_cmd(t):
    for label, text, load_cmd, setup in (
            ("MD, card wedged (ACTIVATE_SD gives up)",
             b"tpi:md NEWDIR", 0, lambda c: setattr(c, "wedged", True)),
            ("LOAD \"tpi:GAME.TAP\", card wedged (via MOUNT_FILE)",
             b"tpi:GAME.TAP", 1, lambda c: setattr(c, "wedged", True)),
            ("MD, card mounts then EIO (handler dies with SD active)",
             b"tpi:md NEWDIR", 0, lambda c: setattr(c, "fail_on", "chdir"))):
        print("PROCESS_CMD: " + label)
        env = install(t)
        setup(env.card)
        bus, raised = run_cmd(t, env, text, load_cmd)
        live = t.MQ
        check(raised is None and env.blinks == 0,
              "command fails without raising or bricking (%r)" % raised)
        check(live is not bus and live.prog != "NULL_SM" and live is bus_sms(env)[-1],
              "bus SM rebuilt: MQ is a fresh live SM, not the parked NULL_SM")
        check(live.tx_log == [10, 0x01],
              "Z80 gets Report J then the V6 pre-load on the live SM: %r" % live.tx_log)
        check(live.execs.count(READY) >= 1 and live.execs[-1] == READY,
              "Y set READY after the bytes are staged")
        parked = [sm for sm in env.sms if sm.prog == "NULL_SM"]
        check(parked and all(not sm.tx_log for sm in parked),
              "nothing was put() into the parked SM")
        check(t.sd_active is False and not env.card.mounted,
              "sd_active cleared, /sd unmounted")


def boot_fakes(t, env, inject_pre):
    """Enough of TS2068_IO's boot for it to reach the dispatcher."""
    real_log = t.LOG

    def log(msg, level):
        real_log(msg, level)
        if msg.startswith("TS Pico initialized OK"):
            inject_pre()

    t.LOG = log
    t.LOAD_CONFIG = lambda: {}
    t.PICO_STATUS = lambda _v: types.SimpleNamespace(
        cur_path="/sd/TAP", LOG_LEVEL=0, ROM_SM=0, bank_sm=0, f_name="",
        append=False, tap_idx=0, offset=0, offset_tbl=[], zx48=False,
        VERBOSE=False, sd_present=False, sd_cid=None, sd_listing_ok=False,
        save_no_card=False)
    t._thread = types.SimpleNamespace(start_new_thread=lambda *a: None)
    t.gc = types.SimpleNamespace(mem_free=lambda: 0, collect=lambda: None)
    t.REMOVE_DIR = lambda d: None
    t.GET_DIRS = lambda *a, **k: ["/TAP"]
    t.OPEN_NOFILE_TAP = lambda: True
    t.DIR_FILES = lambda: True
    t.busy = False


class Booted(BaseException):
    """TS2068_IO finished its boot and logged 'TS Pico initialized OK'."""


def test_boot_no_card(t):
    print("TS2068_IO boot, no card at all")
    env = install(t)
    env.card.wedged = True

    def booted():
        raise Booted()
    boot_fakes(t, env, booted)
    try:
        t.TS2068_IO()
        outcome = "returned"
    except Booted:
        outcome = "reached the dispatcher"
    except Bricked:
        outcome = "bricked"
    except BaseException as e:                 # noqa: BLE001
        outcome = "raised %r" % e
    check(outcome == "reached the dispatcher" and env.blinks == 0,
          "boot carries on without a card, no blink loop (%s)" % outcome)
    check(t.TSP.sd_present is False, "TSP.sd_present is False")
    check(env.card.attempts == 5, "boot gave a cold card 5 tries (%d)" % env.card.attempts)


def test_save_remount(t):
    print("Dispatcher: SAVE succeeds, then the card wedges before the re-mount")
    env = install(t)

    def inject_pre():
        t.MQ.rx = [0] * 10                     # pre[0]=0, pre[1]=0: SAVE
        env.stop_new_bus = True                # next bus SM ends the test

    def save_ts(mq, tsp, pre=None):
        tsp.f_name = "/sd/TAP/NEW.tap"         # a new file, none mounted before
        env.card.wedged = True
        env.card.attempts = 0
        return mq, tsp, "", True

    boot_fakes(t, env, inject_pre)
    t.SAVE_TS = save_ts
    try:
        t.TS2068_IO()
        outcome = "returned"
    except LoopDone:
        outcome = "back at the top of the loop"
    except Bricked:
        outcome = "bricked"
    except BaseException as e:                 # noqa: BLE001
        outcome = "raised %r" % e
    check(outcome == "back at the top of the loop",
          "TS2068_IO survives and polls for the next command (%s)" % outcome)
    check(any("Re-mount after save failed" in m for _, m in env.logs),
          "the failed re-mount is logged")
    check(env.card.attempts == 5 and not any("SD refresh failed" in m for _, m in env.logs),
          "directory refresh skipped: only one round of 5 attempts (%d)" % env.card.attempts)
    live = bus_sms(env)[-1]
    check(t.MQ is live and live.tx_log == [0x01] and live.execs[-1:] == [READY],
          "re-armed once: fresh bus SM, one 0x01 pre-load, then READY")
    check(t.sd_active is False, "sd_active cleared")


def test_service_restart(t):
    print("An unexpected error restarts the service loop, not the ROM lines (audit §4)")
    env = install(t)

    def inject_pre():
        t.MQ.rx = [0] * 10                     # a SAVE pre-header

    calls = []

    def save_ts(mq, tsp, pre=None):
        calls.append(1)
        env.stop_new_bus = True                # the rebuilt bus ends the test once idle
        raise RuntimeError("boom")

    boot_fakes(t, env, inject_pre)
    t.SAVE_TS = save_ts
    idled = []
    real_idle = t.MQ_TO_IDLE

    def record_idle(mq, **k):
        idled.append((mq, k))
        return real_idle(mq, **k)
    t.MQ_TO_IDLE = record_idle
    try:
        t.TS2068_IO()
        outcome = "returned"
    except LoopDone:
        outcome = "back at the top of the loop"
    except BaseException as e:                 # noqa: BLE001
        outcome = "raised %r" % e
    finally:
        t.MQ_TO_IDLE = real_idle
    progs = [sm.prog for sm in env.sms]
    check(outcome == "back at the top of the loop" and len(calls) == 1,
          "one failure: the loop restarts and waits for the next command (%s)" % outcome)
    check(progs.count("set_ctrl") == 1 and progs.count("sel_bank") == 1,
          "the ROM and bank state machines were built once, at boot, never again (%r)" % progs)
    live = bus_sms(env)[-1]
    check(t.MQ is live and idled and idled[-1][0] is live and idled[-1][1] == {"recovered": True},
          "a new bus SM, put back to idle with RECOVERED (MQ_TO_IDLE stages the one 0x01) (%r)"
          % [k for _, k in idled])
    check(any("restarting the service loop (1 in the last minute)" in m and lvl == 2 for lvl, m in env.logs),
          "logged as an error")

    print("Three failures within a minute: give up, as before")
    env = install(t)
    calls = []
    real_idle = t.MQ_TO_IDLE

    def idle_then_save(mq, **k):               # the restart empties the FIFOs: then the
        real_idle(mq, **k)                     # 2068's next command, another SAVE, arrives
        mq.rx = [0] * 10

    def save_ts_always(mq, tsp, pre=None):
        calls.append(1)
        raise RuntimeError("boom %d" % len(calls))

    boot_fakes(t, env, inject_pre)
    t.SAVE_TS = save_ts_always
    t.MQ_TO_IDLE = idle_then_save
    try:
        t.TS2068_IO()
        outcome = "returned"
    except RuntimeError as e:
        outcome = "raised %s" % e
    except BaseException as e:                 # noqa: BLE001
        outcome = "raised %r" % e
    finally:
        t.MQ_TO_IDLE = real_idle
    check(outcome == "raised boom 3" and len(calls) == 3,
          "the third failure goes out to main.py (%s, %d calls)" % (outcome, len(calls)))


def main():
    P.install_fakes()
    # TS2068_IO's boot imports the extension commands. The real dev_extcmd
    # imports TS.tspico back (and the tests here need none of its
    # commands), so a stub with an empty EXT_SA_FUNCT stands in for it.
    # The commands themselves are tested in extcmd_hosttest.py.
    ext = types.ModuleType("dev_extcmd")
    ext.EXT_SA_FUNCT = {}
    sys.modules["dev_extcmd"] = ext
    import TS.tspico as t

    t.TLM_ENABLED = False
    t.time = P.FakeTime()
    t.SAVE_LOG = lambda: None

    test_activate_sd(t)
    test_process_cmd(t)
    test_boot_no_card(t)
    test_save_remount(t)
    test_service_restart(t)

    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
