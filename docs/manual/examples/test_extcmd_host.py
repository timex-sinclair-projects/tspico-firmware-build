"""dev_extcmd.py's handlers through the firmware's real PROCESS_CMD (CPython).

Uses the mocks from the repo's src/test/process_cmd_hosttest.py: a FakeMQ
whose TX drains at once, so this checks the bytes each handler answers and
that exactly one pre-load follows, not timing.

Run:  python3 docs/manual/examples/test_extcmd_host.py
"""

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = sys.argv[1] if len(sys.argv) > 1 else os.path.normpath(
    os.path.join(HERE, "..", "..", ".."))           # docs/manual/examples -> the repo
sys.path.insert(0, os.path.join(REPO, "src", "test"))
import process_cmd_hosttest as h                                  # noqa: E402

h.install_fakes()
import TS.tspico as t                                             # noqa: E402
from TS import catalog                                            # noqa: E402

t.TLM_ENABLED = False
ft = h.FakeTime()
t.time = ft
import TS.tspico_io as tio                                        # noqa: E402
tio.time = ft
t.utime = ft
t.ACTIVATE_SD = t.DEACTIVATE_SD = t.ACTIVATE_MQ = lambda *a: None   # no SD bus here

import re, types                    # extcmd's `tp`: the firmware module as the Pico has it,
tp_ = types.ModuleType("dev_tspico")    # without the underscore const()s, which
tp_.__dict__.update({k: v for k, v in vars(t).items() if not re.match(r"_[0-9]+_", k)})
sys.modules["dev_tspico"] = tp_     # MicroPython inlines and never stores
sys.path.insert(0, HERE)
import dev_extcmd                                                 # noqa: E402
EXT = dev_extcmd.EXT_SA_FUNCT


def send(text, p1=0, p2=0, verbose=False):
    text = text.encode()
    mq = h.FakeMQ(h.make_body(text))
    h.fresh(t, mq)
    t.TSP.VERBOSE = verbose
    t.TSP.cur_path = catalog.ROOT
    pre = h.make_pre(text)
    pre[3], pre[4], pre[5], pre[6] = p1 & 0xFF, p1 >> 8, p2 & 0xFF, p2 >> 8
    t.PROCESS_CMD(pre, {}, EXT)
    return mq.tx_log


def msg(log):
    return bytes(b if isinstance(b, int) else ord(b) for b in log)


print("tpi:.hello")
log = send("tpi:.hello")
h.check(msg(log) == b"\x81\x01\rHello from the TS-Pico!\x00\x01", "81h message, then one pre-load (%r)" % msg(log))

print("tpi:.fact")
log = send("tpi:.fact", 20)
d = b"2432902008176640000"
x = 0
for b in d:
    x ^= b
h.check(log == [1, len(d)] + list(d) + [x, 1], "1, n, digits, XOR, then one pre-load")
log = send("tpi:.fact", 33)
h.check(log == [6, 1], "33: status 6, then one pre-load (%r)" % log)

print("tpi:.lines")
tmp = tempfile.mkdtemp()
catalog.ROOT = tmp
with open(os.path.join(tmp, "poem.txt"), "w") as f:
    f.write("one\ntwo\nthree\n")
log = send("tpi:.lines poem.txt")
h.check(msg(log) == b"\x81\x01\rpoem.txt: 3 lines\x00\x01", "counts 3 lines (%r)" % msg(log))
log = send("tpi:.lines nothere.txt")
h.check(log == [3, 1], "missing file: status 3 (F), one pre-load (%r)" % log)
log = send("tpi:.lines nothere.txt", verbose=True)
h.check(msg(log).startswith(b"\x81\x03\rCan't read nothere.txt"), "VERBOSE on: says why (%r)" % msg(log))
log = send("tpi:.lines")
h.check(log == [3, 1], "no name: F (%r)" % log)

print()
print("%d FAILED" % len(h.FAILURES) if h.FAILURES else "all passed")
sys.exit(1 if h.FAILURES else 0)
