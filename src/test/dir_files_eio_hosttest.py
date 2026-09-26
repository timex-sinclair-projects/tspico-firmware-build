"""Host-side test for DIR_FILES on a failing SD card -- CPython, no Pico.

A TS-Pico's card mounted at boot and then failed its first write:

    File "TS/tspico.py", line 4437, in TS2068_IO
    File "TS/tspico.py", line 1087, in DIR_FILES     <- os.ilistdir()
    File "TS/sdcard.py", line 414, in writeblocks
    OSError: [Errno 5] EIO: write fail

FatFs was flushing the sector os.remove("dirinfo.tap") had dirtied, so the
write surfaced from a directory READ. That OSError went straight out of
TS2068_IO as a FATAL and the 2068 got no TS-Pico at all.

DIR_FILES now logs an ERROR and returns False on OSError, and TS2068_IO's
boot carries on into the dispatcher. This runs the REAL TS.tspico functions
(device modules faked as in process_cmd_hosttest.py) against a fake
filesystem whose card fails the way that one did.

Run:  python3 src/test/dir_files_eio_hosttest.py
"""

import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import process_cmd_hosttest as P                                # noqa: E402


EIO = OSError(5, "EIO: write fail")


class ReachedDispatcher(Exception):
    """TS2068_IO logged that it is about to enter its main loop."""


class Bricked(Exception):
    """TS2068_IO reached a BLINK_ERROR loop."""


class FakeOS:
    """Just enough of MicroPython's os for DIR_FILES and TS2068_IO's boot.

    fail_on names the call that raises EIO ("ilistdir", "write", ...).
    """

    def __init__(self, fail_on=None):
        self.fail_on = fail_on
        self.files = {"GAME.TAP": 1234, "dirinfo.tap": 64}
        self.written = {}

    def _maybe_fail(self, op):
        if op == self.fail_on:
            raise EIO

    def remove(self, name):
        self._maybe_fail("remove")
        if name not in self.files:
            raise OSError(2, "ENOENT")
        del self.files[name]

    def ilistdir(self, *_a):
        self._maybe_fail("ilistdir")
        return iter([("SUB", 16384, 0, 0)] +
                    [(n, 32768, 0, s) for n, s in self.files.items()])

    def statvfs(self, _p):
        self._maybe_fail("statvfs")
        return (512, 512, 1000, 500, 500, 0, 0, 0, 0, 255)

    def stat(self, _p):
        return (0, 0, 0, 0, 0, 0, 100, 0, 0, 0)

    def chdir(self, _p):
        pass

    def mkdir(self, _p):
        pass

    def umount(self, _p):
        pass

    def open(self, name, mode="r"):
        fs = self

        class F:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def write(self, data):
                # A real half-written file stays behind; model that.
                fs.files[name] = fs.files.get(name, 0) + len(data)
                fs._maybe_fail("write")

        self._maybe_fail("open")
        self.files[name] = 0
        return F()


results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg)


def setup(t, fail_on):
    fos = FakeOS(fail_on)
    t.os = fos
    t.open = fos.open
    t.TSP = types.SimpleNamespace(cur_path="/sd/TAP", LOG_LEVEL=0)
    return fos


def test_dir_files(t, logs):
    print("DIR_FILES")

    fos = setup(t, None)
    del logs[:]
    ok = t.DIR_FILES()
    check(ok is True and t.files == ["GAME.TAP"] and "GAME.TAP" in t.lista,
          "healthy card: returns True, lists GAME.TAP")
    check("dirinfo.tap" in fos.files and fos.files["dirinfo.tap"] > 0,
          "healthy card: dirinfo.tap written")
    check(not any(lvl >= 2 for lvl, _ in logs), "healthy card: no ERROR logged")

    for fail_on, what in (("ilistdir", "os.ilistdir (the field failure)"),
                          ("statvfs", "os.statvfs"),
                          ("write", "the dirinfo.tap write")):
        fos = setup(t, fail_on)
        t.files = ["STALE.TAP"]
        del logs[:]
        try:
            ok = t.DIR_FILES()
            raised = None
        except Exception as e:                                  # noqa: BLE001
            ok, raised = None, e
        check(raised is None and ok is False,
              "EIO from %s: returns False, does not raise (%r)" % (what, raised))
        check(t.files == [] and t.files_upper == [],
              "EIO from %s: files[] emptied, no stale entries" % what)
        check(t.lista[32:64].startswith("SD: card error") and "power cycle" in t.lista,
              "EIO from %s: lista keeps its layout and says the card failed" % what)
        check(any(lvl == 2 and "EIO" in m for lvl, m in logs),
              "EIO from %s: ERROR logged with the reason" % what)
        check("dirinfo.tap" not in fos.files,
              "EIO from %s: no (half-written) dirinfo.tap left behind" % what)


def test_boot(t, logs):
    print("TS2068_IO boot")

    mq = P.FakeMQ()

    def log(msg, level):
        logs.append((level, msg))
        if msg.startswith("TS Pico initialized OK"):
            raise ReachedDispatcher()

    def bricked():
        raise Bricked()

    def activate_mq(ready=True):
        t.MQ = mq

    t.LOG = log
    t.BLINK_ERROR = bricked
    t.LOAD_CONFIG = lambda: {}
    t.PICO_STATUS = lambda _v: types.SimpleNamespace(
        cur_path="/sd/TAP", LOG_LEVEL=0, ROM_SM=0, bank_sm=0)
    t.StateMachine = lambda *a, **k: types.SimpleNamespace(
        active=lambda *x: None, put=lambda *x: None)
    t._thread = types.SimpleNamespace(start_new_thread=lambda *a: None)
    t.gc = types.SimpleNamespace(mem_free=lambda: 0, collect=lambda: None)
    t.REMOVE_DIR = lambda d: None
    t.ACTIVATE_SD = lambda *a, **k: None
    t.GET_DIRS = lambda *a, **k: ["/TAP"]
    t.ACTIVATE_MQ = activate_mq
    t.MQ_READY = lambda: None
    t.OPEN_NOFILE_TAP = lambda: True

    for fail_on, label in ((None, "healthy card"),
                           ("ilistdir", "EIO from os.ilistdir"),
                           ("write", "EIO from the dirinfo.tap write")):
        setup(t, fail_on)
        del logs[:]
        del mq.tx_log[:]
        try:
            t.TS2068_IO()
            outcome = "returned"
        except ReachedDispatcher:
            outcome = "dispatcher"
        except Bricked:
            outcome = "bricked"
        except Exception as e:                                  # noqa: BLE001
            outcome = "raised %r" % e
        check(outcome == "dispatcher",
              "%s: boot reaches the dispatcher (%s)" % (label, outcome))
        check(mq.tx_log == [0x01],
              "%s: boot status pre-load staged exactly once" % label)
        if fail_on:
            check(any(lvl == 2 and "EIO" in m for lvl, m in logs),
                  "%s: ERROR logged with the reason" % label)
            check(not any("mounted OK" in m for _, m in logs),
                  "%s: does not claim the card is OK" % label)
        else:
            check(any("mounted OK" in m for _, m in logs),
                  "%s: logs the card OK" % label)


def main():
    P.install_fakes()
    import TS.tspico as t

    t.TLM_ENABLED = False
    t.time = P.FakeTime()
    t.SAVE_LOG = lambda: None
    # NEW_TAPBLK does bytearray += str, which only MicroPython allows; the
    # TAP encoding isn't under test, only that bytes reach the file.
    t.NEW_TAPBLK = lambda items, size: bytearray(4 + size * len(items))
    t.NEW_HDR = lambda typ, name, n: bytearray(21)
    logs = []
    t.LOG = lambda msg, level: logs.append((level, msg))

    test_dir_files(t, logs)
    test_boot(t, logs)

    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
