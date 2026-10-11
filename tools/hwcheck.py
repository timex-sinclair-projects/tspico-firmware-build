#!/usr/bin/env python3
"""The TS-Pico hardware check: the v2 command list on whichever board is
connected (the TS-Pico 2.x or the v3 card), mostly unattended.

    python3 tools/hwcheck.py              # everything
    python3 tools/hwcheck.py --auto-only  # just the part the 2068 runs itself
    python3 tools/hwcheck.py --manual-only  # just the part that needs hands

The automatic part is a BASIC program, basic/SD/TAP/test/hwtest.bas (built by
tools/build-basic.sh), that runs ~18 tests on the 2068 and records each
report code. This script:

  1. stops the firmware, sees which board it is, makes sure telemetry is on,
     clears the last run's files, and puts hwtest.tap, hwcfg.tap (which board)
     and v3t.tap (src/test/sd_roundtrip.py's tape, for the hands-on tests)
     in the card's /TAP;
  2. restarts the firmware and asks you to type LOAD "hwtest" on the 2068,
     then watches the telemetry until the program saves its results;
  3. fetches the results and every file the tests wrote, and checks them:
     report codes and values against what this board should give, and the
     virtual printer's text;
  4. walks you through the tests that need hands (BREAK, pulling the card,
     ZX48 mode, a ROM switch), checking each one in the telemetry;
  5. prints a pass/fail table.

The 2068 should be on and at the BASIC prompt, with the SD card in, and
nothing else using the Pico's port (Thonny, a watch). It uses
tools/pico-serial.py for everything on the Pico's side.
"""

import argparse
import json
import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src", "test"))
import sd_roundtrip as RT                                       # noqa: E402

PS = [sys.executable, os.path.join(HERE, "pico-serial.py")]
HWTEST = os.path.join(ROOT, "SD card", "TAP", "test", "hwtest.tap")
WORK = tempfile.mkdtemp(prefix="hwcheck.")

RESULTS = []                                                    # (name, ok, detail)
TRACE_LOG = os.path.join(WORK, "trace.log")                     # every telemetry line, for afterwards


def result(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    mark = "PASS" if ok is True else ("FAIL" if ok is False else "info")
    print("  %-4s  %s%s" % (mark, name, ("  -- " + detail) if detail else ""))


def say(msg):
    print("\n" + msg)


def ask(msg):
    """A y/n question; True for y."""
    while True:
        a = input("  " + msg + " [y/n] ").strip().lower()
        if a in ("y", "n"):
            return a == "y"


def pause(msg):
    input("  " + msg + "  (press Enter) ")


# ---------------------------------------------------------------------------
# The Pico's side, through pico-serial.py
# ---------------------------------------------------------------------------

def ps(*args, timeout=180):
    r = subprocess.run(PS + list(args), capture_output=True, text=True, timeout=timeout)
    return r.stdout + r.stderr


def repl(code, sd=False, timeout=30):
    """Run code at the REPL (the firmware must be stopped); its output."""
    path = os.path.join(WORK, "snippet.py")
    with open(path, "w") as f:
        f.write(code)
    args = ["run", "--file", path, "--timeout", str(timeout)]
    if sd:
        args.insert(1, "--sd")
    out = ps(*args, timeout=timeout + 60)
    return "\n".join(l for l in out.splitlines() if not l.startswith("[TLM") and not l.startswith("[ACTIVATE"))


def stop_firmware():
    ps("break", "--timeout", "5")


def start_firmware():
    ps("softreset")


class Trace:
    """pico-serial.py watch in the background; its lines in a queue."""

    def __init__(self):
        self.lines = []
        self.q = queue.Queue()
        self.p = subprocess.Popen(PS + ["watch", "--seconds", "7200"], stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, text=True, bufsize=1)
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        with open(TRACE_LOG, "a") as log:
            for line in self.p.stdout:
                line = line.rstrip("\n")
                self.lines.append(line)
                self.q.put(line)
                log.write(line + "\n")
                log.flush()

    def wait_for(self, pattern, seconds):
        """The first line matching pattern, or None after `seconds`."""
        rx = re.compile(pattern)
        end = time.time() + seconds
        while time.time() < end:
            try:
                line = self.q.get(timeout=1)
            except queue.Empty:
                continue
            if rx.search(line):
                return line
        return None

    def mark(self):
        return len(self.lines)

    def since(self, mark):
        return self.lines[mark:]

    def stop(self):
        self.p.terminate()
        try:
            self.p.wait(5)
        except subprocess.TimeoutExpired:
            self.p.kill()
        time.sleep(1)


# ---------------------------------------------------------------------------
# 1. Set up
# ---------------------------------------------------------------------------

def setup():
    say("Setting up. The firmware stops for a minute; leave the 2068 at the prompt.")
    stop_firmware()
    out = repl("from TS import board\nimport TS.tspico as T\nprint('HW', board.NAME, T.FW_VERSION)\n"
               "import json\nc = json.load(open('/config.ini'))\nprint('CFG', json.dumps(c))\n")
    m = re.search(r"HW (\w+) (\S+)", out)
    if not m:
        sys.exit("Couldn't read the board from the REPL:\n" + out)
    board, fw = m.group(1), m.group(2)
    cfg = json.loads(re.search(r"CFG (.*)", out).group(1))
    print("  Board: %s, firmware %s" % ("the v3 card" if board == "v3" else "TS-Pico 2.x", fw))
    if not cfg.get("TELEMETRY") or cfg.get("ROM_SLOT") != 1:
        repl("import json\nc = json.load(open('/config.ini'))\nc['TELEMETRY'] = True\nc['ROM_SLOT'] = 1\n"
             "c['ROM_SM'] = (c.get('ROM_SM', 10) & 12) + 2\nwith open('/config.ini', 'w') as f:\n json.dump(c, f)\n")
        print("  Turned telemetry on (and set the boot slot to 1) in config.ini.")

    # The tapes: the round trip, which board, the program.
    src = os.path.join(ROOT, "basic", "SD", "TAP", "test", "hwtest.bas")
    if not os.path.exists(HWTEST) or os.path.getmtime(HWTEST) < os.path.getmtime(src):
        print("  Building the BASIC programs (tools/build-basic.sh)...")
        subprocess.run([os.path.join(HERE, "build-basic.sh")], capture_output=True, check=True)
    v3t = os.path.join(WORK, "v3t.tap")
    RT.main(["", "make", v3t])
    cfgtap = os.path.join(WORK, "hwcfg.tap")
    with open(cfgtap, "wb") as f:
        f.write(RT.hdr(3, "hwcfg", 1, 60000, 32768) + RT.blk(0xFF, bytes([1 if board == "v3" else 0])))

    # The last run's files out of the way, and the printer's files listed, so
    # the new one can be found.
    out = repl("""import os
def rm(p):
 try:
  if os.stat(p)[0] & 0x4000:
   for n in os.listdir(p):
    rm(p + '/' + n)
   os.rmdir(p)
  else:
   os.remove(p)
 except OSError:
  pass
for f in ('hwres', 'zxs'):
 rm('/sd/TAP/%s.tap' % f)
rm('/sd/TAP/hwdir')
try:
 print('PRN', sorted(os.listdir('/sd/VLPRINT')))
except OSError:
 print('PRN', [])
""", sd=True)
    m = re.search(r"PRN (\[.*\])", out)
    prn_before = eval(m.group(1)) if m else []
    for local, remote in ((HWTEST, "/TAP/hwtest.tap"), (cfgtap, "/TAP/hwcfg.tap"), (v3t, "/TAP/v3t.tap")):
        out = ps("put", "--sd", local, remote)
        if "bytes" not in out or "MISMATCH" in out:
            sys.exit("Couldn't copy %s to the card:\n%s" % (local, out))
    print("  hwtest.tap, hwcfg.tap and v3t.tap are in the card's /TAP.")
    start_firmware()
    time.sleep(4)
    return board, prn_before


# ---------------------------------------------------------------------------
# 2-3. The automatic tests
# ---------------------------------------------------------------------------

# test -> (name, expected report, expected value or None, v3 only)
EXPECT = {
    1: ("read hwcfg.tap (which board)", 0, None, False),
    2: ('SAVE "tpi:info"', 0, None, False),
    3: ('SAVE "tpi:dir"', 0, None, False),
    10: ('SAVE "tpi:md hwdir"', 0, None, False),
    11: ('SAVE "tpi:cd hwdir"', 0, None, False),
    13: ('SAVE "tpi:cd .."', 0, None, False),
    14: ('SAVE "tpi:picopt"', 0, None, False),
    15: ('LPRINT to the virtual printer', 0, None, False),
    16: ('SAVE "tpi:clprint"', 0, None, False),
    17: ('SAVE "tpi:ts2040"', 0, None, False),
    18: ('LOAD "tpi:nosuch.tap": Report F', 15, None, False),
    19: ('tpi:dock CODE 2,10 (Flight Simulator)', 0, 115, False),
    20: ('tpi:dock CODE 2,12 (Crazy Bugs)', 0, 40, False),
    21: ("a flash dock ignores a POKE", 0, 40, True),
    22: ("RAM dock CODE 1,4 takes a POKE", 0, 99, True),
    23: ("the RAM dock keeps it across a switch", 0, 99, True),
    24: ('tpi:dock CODE 2,0 (the default dock)', 0, 17, False),
    25: ('tpi:boot CODE 1,9 (an empty RAM slot): Report F', 15, None, True),
}
REPORTS = "0123456789ABCDEFGHIJKLMNOPQR"


def automatic(board, prn_before):
    say('Automatic tests. On the 2068, type:\n\n      LOAD "hwtest"\n\n'
        "  It runs by itself for a minute or two; press a key when it asks to save\n  the results, and it ends with HWTEST DONE. A few seconds later the 2068\n"
        "  restarts: that's this script stopping the firmware to fetch the results.")
    tr = Trace()
    line = tr.wait_for(r"write done: .*hwres\.tap", 900)
    if not line:
        tr.stop()
        result("hwtest ran to the end", False, "no hwres.tap within 15 minutes")
        return
    time.sleep(2)
    trace = list(tr.lines)
    tr.stop()
    result("hwtest ran to the end", True)
    errors = [l for l in trace if "Traceback" in l or "ERROR" in l]
    result("no firmware errors in the telemetry", not errors, "; ".join(errors[:3]))

    stop_firmware()
    ps("get", "--sd", "/TAP/hwres.tap", os.path.join(WORK, "hwres.tap"))
    out = repl("import os\ntry:\n print('PRN', sorted(os.listdir('/sd/VLPRINT')))\nexcept OSError:\n print('PRN', [])\n", sd=True)
    m = re.search(r"PRN (\[.*\])", out)
    new = [n for n in (eval(m.group(1)) if m else []) if n not in prn_before]
    prn = ""
    if new:
        ps("get", "--sd", "/VLPRINT/" + new[-1], os.path.join(WORK, "prn.txt"))
        try:
            prn = open(os.path.join(WORK, "prn.txt"), errors="replace").read()
        except OSError:
            pass
    start_firmware()

    try:
        data, ck = RT.payload(os.path.join(WORK, "hwres.tap"))
    except (OSError, IndexError):
        result("read hwres.tap", False, "couldn't fetch or read it")
        return
    recs = {data[i]: (data[i + 1], data[i + 2]) for i in range(0, len(data) - 2, 3)}
    for t, (name, rep, val, v3only) in sorted(EXPECT.items()):
        if v3only and board != "v3":
            continue
        if t not in recs:
            result("%2d %s" % (t, name), False, "not recorded")
            continue
        got_rep, got_val = recs[t]
        bad = []
        if got_rep != rep:
            bad.append("report %s, expected %s" % (REPORTS[got_rep] if got_rep < 28 else got_rep, REPORTS[rep]))
        if t == 1 and got_val != (1 if board == "v3" else 0):
            bad.append("it read board %d" % got_val)
        if val is not None and got_val != val:
            if board == "v3":
                bad.append("read %d, expected %d" % (got_val, val))
            else:                               # v2's dock upper half isn't pinned down
                result("%2d %s" % (t, name), "info" if not bad else False, "v2 read %d (v3 reads %d)" % (got_val, val))
                continue
        result("%2d %s" % (t, name), not bad, "; ".join(bad))

    result("the printer file has the LPRINT", "hwtest 1234" in prn, new[-1] if new else "no new file in /VLPRINT")


# ---------------------------------------------------------------------------
# 4. The tests that need hands
# ---------------------------------------------------------------------------

def manual(board):
    tr = Trace()
    try:
        say('BREAK during a LOAD. On the 2068: LOAD "v3t", and press BREAK while the 16K\n'
            '  block loads. Then LOAD "v3t" again and let it finish.')
        pause("When it has finished,")
        ok = ask("Did the first stop with D BREAK, and the second load completely?")
        result("BREAK mid-LOAD, then a full LOAD", ok)

        say("Pulling the SD card (safe: nothing is reading it between commands).\n"
            '  Take the card out, type SAVE "tpi:dir", put the card back, type SAVE "tpi:dir".')
        m = tr.mark()
        pause("When the second listing shows,")
        lines = tr.since(m)
        gone = any("FAILED" in l and "ACTIVATE_SD" in l for l in lines)
        back = any("SD mounted" in l for l in lines)
        reset = any("port gone" in l for l in lines)
        result("card out: no card reported", gone)
        result("card back: mounted again", back)
        result("the board didn't reset", not reset, "the USB port dropped" if reset else "")

        say("ZX48 (Spectrum) mode. On the 2068, one line at a time:\n"
            '      LOAD "tpi:v3t.tap"\n      SAVE "tpi:zx48"\n      OUT 244,3\n'
            '      LOAD ""                         (the stripes, then the 16K block)\n'
            '      SAVE "zxs" CODE 32768,16384\n      SAVE "tpi:dir"\n      OUT 244,0\n      OUT 14,14')
        m = tr.mark()
        pause("When you're back at the 2068's prompt,")
        lines = tr.since(m)
        loads = sum(1 for l in lines if "dispatching LOAD" in l)
        result("ZX48: entered and left", any("ZX48_IO enter" in l for l in lines) and any("exiting ZX48" in l for l in lines))
        result("ZX48: LOAD served the blocks", loads >= 6, "%d LOAD blocks" % loads)
        result("ZX48: SAVE and tpi:dir", any("dispatching SAVE" in l for l in lines) and any("name='dir'" in l for l in lines))
    finally:
        tr.stop()
    stop_firmware()
    ps("get", "--sd", "/TAP/zxs.tap", os.path.join(WORK, "zxs.tap"))
    start_firmware()
    try:
        zxs, ck = RT.payload(os.path.join(WORK, "zxs.tap"))
        result("ZX48: zxs.tap byte for byte", ck and zxs == RT.content()[2])
    except (OSError, IndexError):
        result("ZX48: zxs.tap byte for byte", False, "not fetched")

    if board == "v3":
        say('A restart. On the 2068: SAVE "tpi:boot"\n  The 2068 should reset into the TS-Pico ROM (boot slot 1).')
        pause("When it's back,")
        result('SAVE "tpi:boot" restarts the 2068', ask("Did it restart to the copyright screen?"))

    say('A ROM switch. On the 2068: SAVE "tpi:boot" CODE 2,2' + ("" if board == "v3" else ": NEW") +
        "\n  It should start ZX Diagnostics (flash slot 2).")
    pause("When you've looked,")
    result("tpi:boot to slot 2 starts ZX Diagnostics", ask("Is ZX Diagnostics running?"))
    stop_firmware()
    repl("import json\nc = json.load(open('/config.ini'))\nc['ROM_SLOT'] = 1\nc['ROM_SM'] = (c['ROM_SM'] & 12) + 2\n"
         "with open('/config.ini', 'w') as f:\n json.dump(c, f)\n")
    start_firmware()
    print("  Put the boot slot back to 1." +
          ("" if board == "v3" else " Press the TS Reset button to bring the 2068 back."))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--auto-only", action="store_true", help="just the tests the 2068 runs by itself")
    g.add_argument("--manual-only", action="store_true", help="just the tests that need hands")
    a = ap.parse_args()
    print("Telemetry is saved to %s" % TRACE_LOG)
    board, prn_before = setup()
    if not a.manual_only:
        automatic(board, prn_before)
    if not a.auto_only:
        manual(board)
    passed = sum(1 for r in RESULTS if r[1] is True)
    failed = [r for r in RESULTS if r[1] is False]
    say("Summary: %d passed, %d failed, %d for information (%s)." % (
        passed, len(failed), sum(1 for r in RESULTS if r[1] not in (True, False)),
        "the v3 card" if board == "v3" else "TS-Pico 2.x"))
    for name, _ok, detail in failed:
        print("  FAIL  %s%s" % (name, ("  -- " + detail) if detail else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
