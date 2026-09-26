"""Host-side test for ACTIVATE_SD's boot-time mount -- CPython, no Pico.

A TS-Pico's SD card failed to mount at boot while the same card mounted
fine by hand seconds later. ACTIVATE_SD now tries the whole mount up to 5
times, 0.5 s apart, prints each failure with its reason, and only then drops
into the BLINK_ERROR loop.

Runs the REAL TS.tspico.ACTIVATE_SD (device modules faked the same way as
process_cmd_hosttest.py) with SDCard / SPI / os.mount replaced by fakes.

Run:  python3 src/test/sd_mount_hosttest.py
"""

import contextlib
import io
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import process_cmd_hosttest as P                                # noqa: E402


class Bricked(Exception):
    """ACTIVATE_SD reached its BLINK_ERROR loop."""


results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg)


def main():
    P.install_fakes()
    import TS.tspico as t

    t.TLM_ENABLED = False
    t.time = P.FakeTime()
    t.StateMachine = lambda *a, **k: types.SimpleNamespace(active=lambda *x: None)
    t.SPI = lambda *a, **k: object()
    t.SAVE_LOG = lambda: None
    logs = []
    t.LOG = lambda msg, level: logs.append((level, msg))

    def blink():
        raise Bricked()
    t.BLINK_ERROR = blink

    def run(fail_times):
        """Mount with a card whose first `fail_times` start-ups fail."""
        state = {"n": 0, "mounted": 0}

        def sdcard(spi, cs):
            state["n"] += 1
            if state["n"] <= fail_times:
                raise OSError(19, "no SD card")
            return object()
        t.SDCard = sdcard
        t.os = types.SimpleNamespace(mount=lambda sd, p: state.__setitem__("mounted", state["mounted"] + 1))
        del logs[:]
        out = io.StringIO()
        bricked = False
        with contextlib.redirect_stdout(out):
            try:
                t.ACTIVATE_SD()
            except Bricked:
                bricked = True
        return state, bricked, out.getvalue()

    print("ACTIVATE_SD")
    state, bricked, out = run(0)
    check(state["n"] == 1 and state["mounted"] == 1 and not bricked and not out,
          "card fine at once: one attempt, mounted, nothing printed")

    state, bricked, out = run(2)
    check(state["n"] == 3 and state["mounted"] == 1 and not bricked,
          "card fails twice then works: mounted on attempt 3 (%d attempts)" % state["n"])
    check(out.count("failed") == 2 and "no SD card" in out,
          "each failed attempt printed with its reason: %r" % out.strip().splitlines()[:1])
    check(any(lvl == 1 and "attempt 3" in m for lvl, m in logs),
          "the recovery is logged (warning)")

    state, bricked, out = run(99)
    check(state["n"] == 5 and bricked and state["mounted"] == 0,
          "card never works: exactly 5 attempts, then the BLINK_ERROR loop")
    check(any(lvl == 2 and "after 5 attempts" in m and "no SD card" in m for lvl, m in logs),
          "the final error, with its reason, is logged")

    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
