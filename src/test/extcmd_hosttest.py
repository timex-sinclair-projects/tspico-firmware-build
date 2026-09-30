"""The example external commands (src/TS/extcmd.py) through the real
PROCESS_CMD -- CPython, no Pico.

Each must give exactly ONE answer and leave exactly one 01h pre-load after
it (the tail's). The shipped examples used to break that: .rndw answered 01h
and then sent the word as extra bytes, .fact sent a message and then more
bytes -- orphans that corrupted the next command.

Run:  python3 src/test/extcmd_hosttest.py
"""

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import process_cmd_hosttest as h                                  # noqa: E402


def send(t, ext, text, p1=0):
    raw = text.encode()
    mq = h.FakeMQ(h.make_body(raw))
    h.fresh(t, mq)
    pre = h.make_pre(raw)
    pre[3], pre[4] = p1 & 0xFF, p1 >> 8
    t.PROCESS_CMD(pre, {}, ext)
    return [b if isinstance(b, int) else ord(b) for b in mq.tx_log]


def main():
    h.install_fakes()
    sys.modules["dev_tspico"] = None          # src/dev_tspico.py is on the path here:
    import TS.tspico as t                     # make extcmd use the module under test
    import TS.extcmd as x
    t.TLM_ENABLED = False
    ft = h.FakeTime()
    t.time = ft
    import TS.tspico_io as tio
    tio.time = ft
    t.utime = ft
    ext = x.EXT_SA_FUNCT

    print("tpi:.fact")
    for n in (0, 5, 20, 32):
        log = send(t, ext, "tpi:.fact", n)
        d = str(math.factorial(n)).encode()
        xo = 0
        for b in d:
            xo ^= b
        h.check(log == [1, len(d)] + list(d) + [xo, 1],
                "%d! : 1, count, digits, XOR, then one pre-load" % n)
    log = send(t, ext, "tpi:.fact", 33)
    h.check(log == [t._6_6_Num2Big, 1], "33: status 6 (Report 6), then one pre-load (%r)" % log)

    print("tpi:.rndw")
    x.WORDS = os.path.join(os.path.dirname(HERE), "words.txt")
    words = set(open(x.WORDS).read().split())
    for _ in range(20):
        log = send(t, ext, "tpi:.rndw")
        ok = log[:3] == [0x81, 1, 0x0D] and log[-2:] == [0, 1] and 0 not in log[3:-2]
        word = bytes(log[3:-2]).decode()
        h.check(ok and word in words, "81h message with a real word (%r), then one pre-load" % word)
    x.WORDS = "/nonexistent/words.txt"
    log = send(t, ext, "tpi:.rndw")
    h.check(log == [t._3_F_Invalid_file, 1], "no words.txt: status 3 (F), then one pre-load (%r)" % log)

    print()
    print("%d FAILED" % len(h.FAILURES) if h.FAILURES else "ALL PASS")
    return 1 if h.FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
