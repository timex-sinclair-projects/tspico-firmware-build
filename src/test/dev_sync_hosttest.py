"""The development overrides must match the modules they stand in for.

src/dev_tspico.py is copied to the Pico as /dev_tspico.py (or compiled to
/dev_tspico.mpy) and, when present, main.py runs it INSTEAD of the frozen
TS.tspico. src/dev_extcmd.py does the same for TS.extcmd. A copy that falls
behind silently takes commands away from whoever deploys it: before this
check, dev_tspico.py was 1063 diff lines behind and had no catalog, native or
channel commands at all.

So the copies are kept identical to their sources (line endings aside) and CI
fails when they drift. To bring them back in line:

    cp src/TS/tspico.py src/dev_tspico.py
    cp src/TS/extcmd.py src/dev_extcmd.py

Run:  python3 src/test/dev_sync_hosttest.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)

PAIRS = (("TS/tspico.py", "dev_tspico.py"),
         ("TS/extcmd.py", "dev_extcmd.py"))


def text(rel):
    with open(os.path.join(SRC, rel), "rb") as f:
        return f.read().replace(b"\r\n", b"\n")


def main():
    bad = []
    for src, dev in PAIRS:
        same = text(src) == text(dev)
        print(("  PASS  " if same else "  FAIL  ") + "src/%s matches src/%s" % (dev, src))
        if not same:
            bad.append((src, dev))
    if bad:
        print("\nOut of date. Refresh with:")
        for src, dev in bad:
            print("    cp src/%s src/%s" % (src, dev))
        return 1
    print("\nALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
