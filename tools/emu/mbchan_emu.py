#!/usr/bin/env python3
"""mbchan.bas (and mbchpg.bas, which it loads) in ZEsarUX's Megabank model.

basic/SD/TAP/test/mbchan.bas is the Megabank's r: channel test for the
hardware (tools/hwcheck.py --megabank-channels runs it on the board). This
runs the same two programs in ZEsarUX with the real firmware, checks their
results against hwcheck's MB_CHAN_EXPECT, and then does the Channels step 5
check by hand-typed lines: NEW with a stream open keeps the file to its last
CR. ZEsarUX's model ignores the HSR, so tests 20-23 (a program's page in
chunks 4-7) show the window putting OWNc and SUBc back, not the HSR bit.

    ZESARUX=/path/to/zesarux-with-megabank python3 tools/emu/mbchan_emu.py

Builds build/TSPICO-25.ROM unless TSPICO_ROM names one, and the vendored
tools/zmakebas.
"""

import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

if "TSPICO_ROM" not in os.environ:
    subprocess.run([sys.executable, os.path.join(REPO, "tools", "build-rom.py"), "--megabank"],
                   check=True, stdout=subprocess.DEVNULL)
    os.environ["TSPICO_ROM"] = os.path.join(REPO, "build", "TSPICO-25.ROM")
os.environ.setdefault("MEGABANK", "1")
os.environ["TSPICO_HOST"] = os.path.join(HERE, "megabank_host.py")
os.environ.setdefault("MEGABANK_HOST_LOG", "/tmp/megabank_host.jsonl")

sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import session as S                                    # noqa: E402
from hwcheck import MB_CHAN_EXPECT, REPORTS            # noqa: E402

LOAD, OPENH, PRINT, NEW, ERASE, CAT, CLOSEH = 0xEF, 0xD3, 0xF5, 0xE6, 0xD2, 0xCF, 0xD4
TAP = "/tmp/tspico-root/sd/TAP/"
results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg, flush=True)


def tap_code(path):
    """The data of a tape file's second block (the CODE bytes)."""
    raw = open(path, "rb").read()
    n = raw[0] | raw[1] << 8
    raw = raw[2 + n:]
    n = raw[0] | raw[1] << 8
    return raw[3:2 + n - 1]


def main():
    src = os.path.join(REPO, "basic", "SD", "TAP", "test")
    zmk_dir = os.path.join(REPO, "tools", "zmakebas")      # the vendored one: CLOSE #d needs its fix
    zmk = os.path.join(zmk_dir, "zmakebas")
    if not os.access(zmk, os.X_OK) or os.path.getmtime(zmk) < os.path.getmtime(zmk + ".c"):
        subprocess.run(["make", "-C", zmk_dir, "zmakebas"], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with S.Session() as s:
        for name in ("mbchan", "mbchpg"):
            subprocess.run([zmk, "-a", "10", "-n", name, "-o", TAP + name + ".tap",
                            os.path.join(src, name + ".bas")], check=True)
        for f in ("mbchres.tap", "mbchpres.tap"):
            if os.path.exists(TAP + f):
                os.remove(TAP + f)
        t = s.run(LOAD, '"tpi:mbchan.tap"')
        assert "0 OK" in t, t
        s.run(LOAD, '""', until="Press Y")
        s.cmd("send-keys-ascii 150 121")              # y
        t0 = time.time()
        while time.time() - t0 < 1800:
            time.sleep(2)
            t = s.text()
            if "MBCHAN DONE" in t:
                break
            if "press any key" in t.lower() or "start tape" in t.lower():
                s.key(129)
        check("MBCHAN DONE" in t, "mbchan and mbchpg ran to the end (%.0f s)" % (time.time() - t0))
        data = b""
        for f in ("mbchres.tap", "mbchpres.tap"):
            if os.path.exists(TAP + f):
                data += tap_code(TAP + f)
        recs = {data[i]: (data[i + 1], data[i + 2] + 256 * data[i + 3]) for i in range(0, len(data) - 3, 4)}
        for n, (name, rep, val) in sorted(MB_CHAN_EXPECT.items()):
            if n not in recs:
                check(False, "%2d %s: not recorded" % (n, name))
                continue
            got_rep, got_val = recs[n]
            ok = got_rep == rep and (val is None or got_val == val)
            check(ok, "%2d %s (report %s, %d)" % (n, name, REPORTS[got_rep] if got_rep < 28 else got_rep,
                                                  got_val))
        if 33 in recs and 34 in recs:
            print("  (frames: 2000 characters %d, the loop alone %d)" % (recs[33][1], recs[34][1]))

        # Channels step 5: NEW with a stream open keeps the file to its last CR.
        t = s.run(OPENH, '4,"r:nw","w": ', PRINT, ' #4;"kept": ', PRINT, ' #4;"lost";')
        check("0 OK" in t, "OPEN #4, PRINT #4 \"kept\" then \"lost\" with no CR")
        s.run(NEW)
        t = s.run(CAT, '"r:"')
        line = [l for l in t.splitlines() if "nw" in l]
        check(line and " 5" in line[0], "NEW with the stream open: CAT shows nw at 5 bytes (%s)"
              % (line[0].strip() if line else "no nw:\n" + t))
        t = s.run(ERASE, '"r:nw"')
        check("0 OK" in t, 'then ERASE "r:nw": 0 OK')
    print("%d/%d passed" % (sum(results), len(results)))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
