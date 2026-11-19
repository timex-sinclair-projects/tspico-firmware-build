#!/usr/bin/env python3
"""The TS-Pico hardware check: the v2 command list on whichever board is
connected (the TS-Pico 2.x or the v3 card), mostly unattended.

    python3 tools/hwcheck.py              # everything
    python3 tools/hwcheck.py --auto-only  # just the part the 2068 runs itself
    python3 tools/hwcheck.py --manual-only  # just the part that needs hands
    python3 tools/hwcheck.py --megabank     # everything, then the Megabank
    python3 tools/hwcheck.py --megabank-only  # just the Megabank

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

The Megabank section (the TS-2068 Megabank spec, Testing, "On hardware"
steps 2, 4 and 5) needs the board, ROM 2.5 and firmware with the RAM disk.
It runs the board's memory test (tools/megabank/mbmem.tap, built in the
Megabank repo) and basic/SD/TAP/test/mbdisk.bas, which SAVEs, LOADs, MOVEs,
COPYs, ERASEs, fills, backs up and restores the RAM disk, then checks the
write-protect switch and, if you want, a power cut during a SAVE. It erases
the board and the RAM disk; it asks before it starts.
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
MBMEM = os.path.join(HERE, "megabank", "mbmem.tap")
MBDISK = os.path.join(ROOT, "SD card", "TAP", "test", "mbdisk.tap")
MBCHAN = os.path.join(ROOT, "SD card", "TAP", "test", "mbchan.tap")
MBCHPG = os.path.join(ROOT, "SD card", "TAP", "test", "mbchpg.tap")
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
            '      SAVE "tpi:zx48"\n      OUT 244,3\n'
            '      LOAD "tpi:v3t.tap"              (mounted from ZX48 mode: issue #254)\n'
            '      LOAD ""                         (the stripes, then the 16K block)\n'
            '      SAVE "zxs" CODE 32768,16384\n      SAVE "tpi:dir"\n      OUT 244,0\n      OUT 14,14')
        m = tr.mark()
        pause("When you're back at the 2068's prompt,")
        lines = tr.since(m)
        loads = sum(1 for l in lines if "dispatching LOAD" in l)
        result("ZX48: entered and left", any("ZX48_IO enter" in l for l in lines) and any("exiting ZX48" in l for l in lines))
        result("ZX48: LOAD served the blocks", loads >= 6, "%d LOAD blocks" % loads)
        result("ZX48: LOAD \"tpi:v3t.tap\" mounted from ZX48 mode",
               any("ZX_TPI" in l and "op=1" in l and "v3t.tap" in l for l in lines))
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

    say('The boot setting. On the 2068: SAVE "tpi:boot"\n  It should show "BOOT is MEM=2, PAGE=1" (flash slot 1) and 0 OK.')
    tr = Trace()
    try:
        pause("When it has shown it,")
        result('SAVE "tpi:boot" shows the boot setting', any("BOOT is MEM=2, PAGE=1" in l for l in tr.since(0)))
    finally:
        tr.stop()

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


# ---------------------------------------------------------------------------
# 5. The Megabank
# ---------------------------------------------------------------------------

# mbdisk.bas: test -> (name, expected report, expected value or None)
MB_DISK_EXPECT = {
    1: ('FORMAT "r:"', 0, None),
    2: ('FORMAT "r:" again (it asks first over files)', 0, None),
    3: ('SAVE "tpi:ram"', 0, None),
    4: ('SAVE "r:mbdk" CODE 40000,3000', 0, None),
    5: ('VERIFY "r:mbdk" CODE', 0, None),
    6: ('LOAD "r:mbdk" CODE: the bytes came back', 0, 5),
    7: ('VERIFY after a change: Report R', 27, None),
    8: ('SAVE "r:prog" (a program)', 0, None),
    9: ('CAT "r:"', 0, None),
    10: ('MOVE "r:mbdk" TO "r:mbdk2"', 0, None),
    11: ('LOAD the old name: Report F', 15, None),
    12: ('COPY "r:mbdk2" TO "mbdkcopy" (to the card)', 0, None),
    13: ('COPY "mbdkcopy" TO "r:back" (from the card)', 0, None),
    14: ('LOAD "r:back" CODE 50000', 0, 5),
    15: ('COPY "r:back" TO "r:back2" (on the board)', 0, None),
    16: ('ERASE "r:back2"', 0, None),
    17: ('FORMAT "r:64" over files: asks to be repeated', 0, None),
    18: ('FORMAT "r:64" again: done', 0, None),
    19: ('SAVE 48K onto the 64K disk', 0, None),
    20: ('SAVE 48K more: Report Q (full)', 26, None),
    21: ('SAVE 3000 bytes into what is left', 0, None),
    22: ('SAVE "tpi:ram backup mbdkimg"', 0, None),
    23: ('ERASE "r:small"', 0, None),
    24: ('tpi:ram restore over files: asks to be repeated', 0, None),
    25: ('tpi:ram restore again: done', 0, None),
    26: ('the erased file is back', 0, 5),
    27: ('FORMAT "r:" over files: asks', 0, None),
    28: ('FORMAT "r:" again: a default disk', 0, None),
}


def mb_fetch(name):
    """/TAP/<name>.tap's CODE bytes, or None."""
    local = os.path.join(WORK, name + ".tap")
    stop_firmware()
    ps("get", "--sd", "/TAP/%s.tap" % name, local)
    start_firmware()
    try:
        data, _ck = RT.payload(local)
        return data
    except (OSError, IndexError):
        return None


def mb_setup():
    if not os.path.exists(MBMEM):
        sys.exit("No %s (the Megabank repo's firmware/controller/memtest/build.py makes it)." % MBMEM)
    src = os.path.join(ROOT, "basic", "SD", "TAP", "test", "mbdisk.bas")
    if not os.path.exists(MBDISK) or os.path.getmtime(MBDISK) < os.path.getmtime(src):
        print("  Building the BASIC programs (tools/build-basic.sh)...")
        subprocess.run([os.path.join(HERE, "build-basic.sh")], capture_output=True, check=True)
    stop_firmware()
    repl("""import os
for f in ('mbmemres.tap', 'mbdkres.tap', 'mbdkcopy.tap', 'mbdkimg.rdi'):
 try:
  os.remove('/sd/TAP/' + f)
 except OSError:
  pass
""", sd=True)
    for local, remote in ((MBMEM, "/TAP/mbmem.tap"), (MBDISK, "/TAP/mbdisk.tap")):
        out = ps("put", "--sd", local, remote)
        if "bytes" not in out or "MISMATCH" in out:
            sys.exit("Couldn't copy %s to the card:\n%s" % (local, out))
    start_firmware()
    time.sleep(4)
    print("  mbmem.tap and mbdisk.tap are in the card's /TAP.")


def megabank():
    say("The Megabank. It needs ROM 2.5 (PEEK 101 gives 37) and the board fitted.\n"
        "  It ERASES the board, the RAM disk included.")
    if not ask("Go on?"):
        result("Megabank tests", None, "skipped")
        return
    mb_setup()

    say('The memory test. On the 2068, type:\n\n      LOAD "tpi:mbmem.tap"\n      LOAD ""\n\n'
        "  Press Y when it asks. It runs for about 3 minutes with the border\n"
        "  changing; press a key when it asks to save the results.")
    tr = Trace()
    line = tr.wait_for(r"write done: .*mbmemres\.tap", 900)
    tr.stop()
    if not line:
        result("mbmem ran to the end", False, "no mbmemres.tap within 15 minutes")
    else:
        time.sleep(2)
        r = mb_fetch("mbmemres")
        if not r or len(r) < 13:
            result("read mbmemres.tap", False, "couldn't fetch or read it")
        else:
            state, errs, pages = r[0], r[1] + 256 * r[2], r[11] + 256 * r[12]
            result("mbmem: the board answered", state != 1)
            result("mbmem: the write-protect switch was off", state != 2)
            first = ""
            if errs:
                first = "first: pass %d, bank %d, 8K %d via chunk %d, offset %d: wanted %d, read %d" % (
                    r[3], r[4], r[5], r[6], r[7] + 256 * r[8], r[9], r[10])
            result("mbmem: every page read back (%d pages)" % pages, state == 0 and errs == 0 and pages > 0,
                   ("%d bad pages; " % errs + first) if errs else "")
    say("Reset the 2068 now (the memory test overwrote its RAM from 32768 up).")
    pause("When it's back at the prompt,")

    say('The RAM disk. On the 2068, type:\n\n      LOAD "tpi:mbdisk.tap"\n      LOAD ""\n\n'
        "  Press Y when it asks, then a key whenever it says to (each SAVE asks).\n"
        "  It ends with MBDISK DONE.")
    tr = Trace()
    line = tr.wait_for(r"write done: .*mbdkres\.tap", 900)
    trace = list(tr.lines)
    tr.stop()
    if not line:
        result("mbdisk ran to the end", False, "no mbdkres.tap within 15 minutes")
    else:
        time.sleep(2)
        result("mbdisk: no firmware errors in the telemetry",
               not [l for l in trace if "Traceback" in l or "ERROR" in l])
        data = mb_fetch("mbdkres")
        if data is None:
            result("read mbdkres.tap", False, "couldn't fetch or read it")
        else:
            recs = {data[i]: (data[i + 1], data[i + 2]) for i in range(0, len(data) - 2, 3)}
            for t, (name, rep, val) in sorted(MB_DISK_EXPECT.items()):
                if t not in recs:
                    result("%2d %s" % (t, name), False, "not recorded")
                    continue
                got_rep, got_val = recs[t]
                bad = []
                if got_rep != rep:
                    bad.append("report %s, expected %s" % (REPORTS[got_rep] if got_rep < 28 else got_rep,
                                                           REPORTS[rep]))
                if val is not None and got_val != val:
                    bad.append("read %d, expected %d" % (got_val, val))
                result("%2d %s" % (t, name), not bad, "; ".join(bad))
            stop_firmware()
            out = repl("import os\nfor f in ('mbdkcopy.tap', 'mbdkimg.rdi'):\n try:\n  print('SZ', f, os.stat('/sd/TAP/' + f)[6])\n"
                       " except OSError:\n  print('SZ', f, -1)\n", sd=True)
            start_firmware()
            sizes = dict(re.findall(r"SZ (\S+) (-?\d+)", out))
            result("mbdkimg.rdi on the card is 64K", sizes.get("mbdkimg.rdi") == "65536",
                   "%s bytes" % sizes.get("mbdkimg.rdi"))
            result("mbdkcopy.tap on the card", int(sizes.get("mbdkcopy.tap", "-1")) > 3000)

    say('The write-protect switch. Turn it ON, then on the 2068 type:\n\n'
        '      SAVE "r:wp" CODE 0,10\n\n  It should stop with J Invalid I/O device. Then turn the switch OFF.')
    pause("When you've tried it and turned the switch off,")
    result("write-protect on: SAVE \"r:\" gives J", ask("Did it give J Invalid I/O device?"))

    say("A power cut during a SAVE (optional). It needs the 2068 switched off\n  in the middle of a long SAVE.")
    if ask("Do it now?"):
        say('On the 2068:\n      SAVE "r:keep" CODE 0,100\n      SAVE "r:long" CODE 16384,49152\n\n'
            "  and switch the 2068 off while the second SAVE runs (after its key).\n"
            '  Switch it on, then:  CAT "r:"   and   LOAD "r:keep" CODE 30000')
        pause("When you've done that,")
        result('power cut: the other file survived (CAT lists keep, it LOADs)', ask("Did it?"))
    else:
        result("power cut during a SAVE", None, "skipped")


# mbchan.bas: test -> (name, expected report, expected value or None)
MB_CHAN_EXPECT = {
    1: ('FORMAT "r:"', 0, None),
    2: ('FORMAT "r:" again', 0, None),
    3: ('OPEN #4,"r:t","w", PRINT # with TAB, CLOSE #', 0, None),
    4: ('INPUT # reads both lines back', 0, 3),
    5: ('INPUT # past the end: 8 End of file', 8, None),
    6: ('mode a appends ("more" at byte 20)', 0, 109),
    7: ('a record file (8): TAB 3, TAB 1', 0, None),
    8: ('INPUT # TAB 3 gives record 3; TAB 0 the count (3)', 0, 3),
    9: ('a record that overflows: Q', 26, None),
    10: ('TAB 0 then data: Q', 26, None),
    11: ('INPUT # on a w stream: Q', 26, None),
    12: ('binary keeps CHR$ 16 (INKEY$ #)', 0, 16),
    13: ('text drops CHR$ 16 and its parameter', 0, 65),
    14: ('OPEN #6,"r:": TAB 0 gives 5 names', 0, 5),
    15: ('OPEN #6,"r:b*": the pattern gives bin', 0, 1),
    16: ('ERASE of a file open on #4: F', 15, None),
    17: ('20000 bytes to r:g, which must move to grow', 0, None),
    18: ('LOAD "r:g" CODE: the bytes are right', 0, 7),
    19: ('r:after, the file it moved past, intact', 0, 1),
    20: ('a board page in chunk 4 survives 3000 characters', 0, 0),
    21: ('a board page in chunk 5 survives 3000 characters', 0, 0),
    22: ('a board page in chunk 6 survives 3000 characters', 0, 0),
    23: ('a board page in chunk 7 survives 3000 characters', 0, 0),
    24: ('32 errors in a row in the channel, then it still reads', 0, 132),
    25: ('f: and r: together, closed 4 5 6', 0, 7),
    26: ('f: and r: together, closed 4 6 5', 0, 7),
    27: ('f: and r: together, closed 5 4 6', 0, 7),
    28: ('f: and r: together, closed 5 6 4', 0, 7),
    29: ('f: and r: together, closed 6 4 5', 0, 7),
    30: ('f: and r: together, closed 6 5 4', 0, 7),
    31: ('LLIST into OPEN #3,"r:list"; CLOSE #3 gives P back', 0, 16),
    32: ('the listing is in r:list', 0, 49),
    33: ('2000 characters through PRINT # (frames)', 0, None),
    34: ('the same loop without PRINT # (frames)', 0, None),
}


def mb_spans(lines):
    """{name: microseconds from its stream's tpi:rchopen to the next
    tpi:rchclose}, from the telemetry's PROCESS_CMD lines, for mbchan's
    timing streams r:speed and r:speed2 (their names are in the hex payload
    after the mode: "w speed" is 77 20 73 70 65 65 64)."""
    spans, cur = {}, None
    for l in lines:
        m = re.search(r"\[TLM (\d+) ", l)          # pico-serial watch puts the time first
        if not m or "PROCESS_CMD enter" not in l:
            continue
        low = l.lower()
        if "tpi:rchopen" in low:
            cur = None
            if "7720737065656432" in low:
                cur = ("speed2", int(m.group(1)))
            elif "77207370656564" in low:
                cur = ("speed", int(m.group(1)))
        elif "tpi:rchclose" in low and cur:
            spans[cur[0]] = (int(m.group(1)) - cur[1]) % (1 << 30)   # ticks_us wraps at 2**30
            cur = None
    return spans


def mb_channels():
    """The r: channel tests (the Megabank spec, Testing, "Channels (phase
    9)"): mbchan.bas for steps 1, 3, 4, 7 and 8, mbchpg.bas (which mbchan
    loads) for step 2, then the hands-on 5 and 6."""
    say("The Megabank's r: channels. They need ROM 2.5 with phase 9 and the\n"
        "  phase 9 firmware. They FORMAT the RAM disk.")
    if not ask("Go on?"):
        result("r: channel tests", None, "skipped")
        return
    src = os.path.join(ROOT, "basic", "SD", "TAP", "test", "mbchan.bas")
    if not os.path.exists(MBCHAN) or os.path.getmtime(MBCHAN) < os.path.getmtime(src):
        print("  Building the BASIC programs (tools/build-basic.sh)...")
        subprocess.run([os.path.join(HERE, "build-basic.sh")], capture_output=True, check=True)
    stop_firmware()
    out = repl("import json\nc = json.load(open('/config.ini'))\nprint('TEL', c.get('TELEMETRY'))\n")
    if "TEL True" not in out:
        repl("import json\nc = json.load(open('/config.ini'))\nc['TELEMETRY'] = True\n"
             "with open('/config.ini', 'w') as f:\n json.dump(c, f)\n")
        print("  Turned telemetry on in config.ini (the cost is timed from it).")
    repl("""import os
for f in ('mbchres.tap', 'mbchpres.tap', 'mbchf.txt'):
 try:
  os.remove('/sd/TAP/' + f)
 except OSError:
  pass
 try:
  os.remove('/sd/' + f)
 except OSError:
  pass
""", sd=True)
    for local, remote in ((MBCHAN, "/TAP/mbchan.tap"), (MBCHPG, "/TAP/mbchpg.tap")):
        out = ps("put", "--sd", local, remote)
        if "bytes" not in out or "MISMATCH" in out:
            sys.exit("Couldn't copy %s to the card:\n%s" % (local, out))
    start_firmware()
    time.sleep(4)

    say('On the 2068, type:\n\n      LOAD "tpi:mbchan.tap"\n      LOAD ""\n\n'
        "  Press Y when it asks, and a key when each of its two SAVEs asks\n"
        "  (it loads mbchpg in between). It ends with MBCHAN DONE.")
    tr = Trace()
    line = tr.wait_for(r"write done: .*mbchpres\.tap", 1200)
    trace = list(tr.lines)
    tr.stop()
    if not line:
        result("mbchan and mbchpg ran to the end", False, "no mbchpres.tap within 20 minutes")
    else:
        time.sleep(2)
        result("mbchan: no firmware errors in the telemetry",
               not [l for l in trace if "Traceback" in l or "ERROR" in l])
        data, pg = mb_fetch("mbchres"), mb_fetch("mbchpres")
        if data is None or pg is None:
            result("read mbchres.tap and mbchpres.tap", False, "couldn't fetch or read them")
        else:
            data += pg
            recs = {data[i]: (data[i + 1], data[i + 2] + 256 * data[i + 3]) for i in range(0, len(data) - 3, 4)}
            for t, (name, rep, val) in sorted(MB_CHAN_EXPECT.items()):
                if t not in recs:
                    result("%2d %s" % (t, name), False, "not recorded")
                    continue
                got_rep, got_val = recs[t]
                bad = []
                if got_rep != rep:
                    bad.append("report %s, expected %s" % (REPORTS[got_rep] if got_rep < 28 else got_rep,
                                                           REPORTS[rep]))
                if val is not None and got_val != val:
                    bad.append("read %d, expected %d" % (got_val, val))
                result("%2d %s" % (t, name), not bad, "; ".join(bad) or ("%d" % got_val if val is None else ""))
            span = mb_spans(trace)
            if "speed" in span and "speed2" in span:
                us = (span["speed"] - span["speed2"]) / 2000
                result("the cost of a character through PRINT # (step 8)", None,
                       "%.0f us (2000 characters in %.2f s, the loop alone %.2f s)"
                       % (us, span["speed"] / 1e6, span["speed2"] / 1e6))
            else:
                result("the cost of a character through PRINT # (step 8)", None,
                       "not timed: no rchopen/rchclose for r:speed in the telemetry")

    say('NEW with a stream open (step 5). On the 2068, type:\n\n'
        '      OPEN #4,"r:nw","w": PRINT #4;"kept": PRINT #4;"lost";\n'
        '      NEW\n      CAT "r:"\n\n'
        "  nw should be 5 bytes (\"kept\" and its CR). Then:  ERASE \"r:nw\"  should give 0 OK.")
    pause("When you've done that,")
    result("NEW with a stream open: the file kept to its last CR, ERASE works", ask("Was nw 5 bytes, and did ERASE work?"))
    say('A reset with a stream open. On the 2068:\n\n'
        '      OPEN #4,"r:rs","w": PRINT #4;"kept"\n\n'
        '  then press the reset button, and:  CAT "r:"  (rs: 5 bytes), then  ERASE "r:rs"')
    pause("When you've done that,")
    result("reset with a stream open: kept to the CR, ERASE works", ask("Was rs 5 bytes, and did ERASE work?"))
    say('Power-off with a stream open. On the 2068:\n\n'
        '      OPEN #4,"r:po","w": PRINT #4;"kept"\n\n'
        '  then switch the 2068 off and on, and:  CAT "r:"  (po: 5 bytes), then  ERASE "r:po"')
    if ask("Do it now?"):
        pause("When you've done that,")
        result("power-off with a stream open: kept to the CR, ERASE works", ask("Was po 5 bytes, and did ERASE work?"))
    else:
        result("power-off with a stream open", None, "skipped")
    say('The write-protect switch mid-stream (step 6). On the 2068:\n\n'
        '      OPEN #4,"r:wp","w": PRINT #4;"one"\n\n'
        '  Turn the switch ON, then:  PRINT #4;"two"\n'
        '  It should stop with J Invalid I/O device. Turn the switch OFF, then\n'
        '  CLOSE #4  and  CAT "r:".')
    pause("When you've done that,")
    result("write-protect mid-stream: J at the write-back", ask("Did PRINT #4 give J?"))
    result("then CLOSE #4 with the switch off works", ask("Did CLOSE #4 give 0 OK?"))
    n = input("  What length did CAT show for wp? ").strip()
    result("wp's length after the switch (4: the bytes the board dropped aren't counted)", None, n + " bytes")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--auto-only", action="store_true", help="just the tests the 2068 runs by itself")
    g.add_argument("--manual-only", action="store_true", help="just the tests that need hands")
    g.add_argument("--megabank-only", action="store_true", help="just the TS-2068 Megabank's tests")
    g.add_argument("--megabank-channels", action="store_true",
                   help="just the Megabank's r: channel tests (phase 9)")
    ap.add_argument("--megabank", action="store_true", help="the TS-2068 Megabank's tests as well")
    ap.add_argument("--port", help="the TS-Pico's serial device (default: pico-serial.py's first usbmodem; "
                    "give it when the Megabank's controller is plugged in too)")
    a = ap.parse_args()
    if a.port:
        PS[2:2] = ["--port", a.port]
    print("Telemetry is saved to %s" % TRACE_LOG)
    if a.megabank_channels:
        board = "v3"
        mb_channels()
    else:
        board, prn_before = setup()
        if not a.manual_only and not a.megabank_only:
            automatic(board, prn_before)
        if not a.auto_only and not a.megabank_only:
            manual(board)
        if a.megabank or a.megabank_only:
            megabank()
            mb_channels()
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
