#!/usr/bin/env python3
"""The Z80-model host tests again, on the v3 card's queues (step 4.5 of the
v3 port plan, docs/v3-board-layer-proposal.md).

On v3, MQ is tsbus.MQ(): two 1,024-entry queues that core 1 serves, not
TS_IO_DUAL's 4-entry PIO FIFOs. This runs load_ts, cmd_io, save_ts and
zx48_io unchanged, each in its own process, with:

  * load_ts_hosttest.FakePIO.DEPTH = 1024: the queues' size, tx_fifo() and
    rx_fifo() reporting the real levels, and put_block() as tsbus.c has it;
  * a tsbus module present, so TS.tspico_io takes its v3 paths at import:
    no DMA, no PIO register writes, blocks through STREAM_QUEUE (put_block).

Every scenario must pass as it does on v2: the same bytes, the same final
status and one pre-load, BREAK and stalls handled, and no put() into a full
queue. A deep queue can only hold more of what the firmware queued, so what
this looks for is a byte left in TX that a 4-deep FIFO would have refused
(a pre-load staged twice, an echo nobody read) and a wait that counted on
the FIFO filling up.

Run:  python3 src/test/deep_queue_hosttest.py
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS = ("load_ts_hosttest", "cmd_io_hosttest", "save_ts_hosttest", "zx48_io_hosttest")

SHIM = r"""
import sys, types
sys.path.insert(0, %(here)r)
import load_ts_hosttest as L
import sync_io_hosttest as S
L.FakePIO.DEPTH = 1024
_init = L.FakePIO.__init__
def _track(self, *a, **k):
    _init(self, *a, **k)
    L.FakePIO.current = self                    # tsbus.MQ() is one object
L.FakePIO.__init__ = _track
# Core 1 serves the Z80 whatever Python is doing: every model millisecond
# (one clock read, FakeTime) the Z80 gets Z80_PER_MS steps, a byte about
# every 33 us. A ready-wait that isn't satisfied doesn't count down faster.
Z80_PER_MS = 30
def _z80_runs(pio):
    for _ in range(Z80_PER_MS):
        op = pio.pending
        if pio.script is None or op is None or op == ("stop",):
            return
        if op[0] == "wait" and (pio.status() & op[1]) != op[1]:
            return
        if op[0] == "in" and not pio.tx:
            return
        pio.pump()
_ticks = S.FakeTime.ticks_ms
def _ticks_ms(self):
    pio = getattr(L.FakePIO, "current", None)
    if pio is not None:
        _z80_runs(pio)
    return _ticks(self)
S.FakeTime.ticks_ms = _ticks_ms
tsbus = types.ModuleType("tsbus")
tsbus.MQ = lambda: L.FakePIO.current
for name in ("start", "hold", "serve", "exrom", "dock", "load"):
    setattr(tsbus, name, lambda *a: None)
tsbus.HOME, tsbus.EXROM, tsbus.DOCK = 0, 1, 2
sys.modules["tsbus"] = tsbus
def _v3_fakes(fakes):
    def install_fakes(*a, **k):                 # board_v3 needs these too
        r = fakes(*a, **k)
        _board_v3_fakes()
        return r
    return install_fakes
def _board_v3_fakes():
    m = sys.modules["machine"]
    m.I2C = lambda *a, **k: types.SimpleNamespace(writeto_mem=lambda *a: None)
    m.Timer = type("Timer", (), {"PERIODIC": 1, "ONE_SHOT": 0,
                                 "__init__": lambda self, **k: None,
                                 "init": lambda self, **k: None,
                                 "deinit": lambda self: None})
    sys.modules["tsbus"] = tsbus
S.install_fakes = _v3_fakes(S.install_fakes)
import process_cmd_hosttest as P                # cmd_io's fakes come from here
P.install_fakes = _v3_fakes(P.install_fakes)
import importlib
t = importlib.import_module(%(test)r)
r = t.main()
import TS.tspico_io as io
if io._tsbus_mq is None or io._DMA is not None:
    print("FAIL  tspico_io did not take the v3 paths (%%r, %%r)" %% (io._tsbus_mq, io._DMA))
    r = 1
sys.exit(r or 0)
"""


def main():
    fails = []
    for test in TESTS:
        p = subprocess.run([sys.executable, "-c", SHIM % {"here": HERE, "test": test}],
                           capture_output=True, text=True, cwd=HERE)
        lines = (p.stdout + p.stderr).strip().splitlines()
        bad = [l for l in lines if l.lstrip().startswith(("FAIL", "[FAIL]", "Traceback"))]
        last = lines[-1] if lines else "(no output)"
        ok = p.returncode == 0 and not bad
        print("%s  %-18s %s" % ("PASS" if ok else "FAIL", test, last))
        if not ok:
            fails.append(test)
            for l in bad[:20]:
                print("        " + l)
    print()
    if fails:
        print("%d FAILED" % len(fails))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
