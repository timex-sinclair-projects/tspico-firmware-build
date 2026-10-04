#!/usr/bin/env python3
"""End-to-end smoke test in Fuse (issue #35): the TS-Pico ROM in a headless
Fuse from timex-sinclair-projects/fuse-tspico, the real firmware behind it
(pico_host.py). About 30 seconds.

    FUSE=/path/to/fuse python3 tools/emu/fuse_smoke.py [--keep]

$FUSE is a Fuse built with --with-null-ui --enable-automation; without it,
the lab build. Fuse has no remote control like ZEsarUX's ZRCP, so:

- **The test is a BASIC program**, served by the firmware as its "nothing
  mounted" file (/assets/nofile.tap), so that LOAD "" fetches it over the
  bridge and it runs itself: CAT, mount a CODE file from the card, LOAD
  it, VERIFY it.
- **Keys** are pressed by Fuse's debugger (--debugger-command): a code in
  LAST_K and FLAGS bit 5 set, as the ROM's keyboard interrupt would, once
  the ROM has taken the previous one. That types LOAD "". (Fuse's own
  auto-load won't run with a custom ROM.) SAVE's "press any key" doesn't
  take a key this way, so SAVE is left to smoke.py.
- **The result**: the debugger prints ERR_NR (FFh = 0 OK) and the loaded
  bytes at the end, and automation saves the screen.
"""

import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import session as S                                           # noqa: E402

FUSE = os.environ.get("FUSE", os.path.expanduser(
    "~/Documents/github/fuse-tspico-lab/build-null/fuse"))
ROOT = "/tmp/fuse-tspico-root"
OUT = "/tmp/fuse-tspico-out"
LOG = "/tmp/fuse_pico_host.out"
VERIFY = 0xD6
results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg, flush=True)


def test_program():
    """10 CAT  20 LOAD "tpi:fusedata.tap"  30 LOAD "" CODE 40000
    40 VERIFY "" CODE 40000  50 PRINT "FUSE OK"  (autorun from 10)"""
    num = lambda n: str(n).encode() + b"\x0e\x00\x00" + bytes([n & 0xFF, n >> 8]) + b"\x00"
    return S.basic_tap("fusetest", [
        (10, bytes([S.CAT])),
        (20, bytes([S.LOAD]) + b'"tpi:fusedata.tap"'),
        (30, bytes([S.LOAD]) + b'""' + bytes([S.CODE]) + num(40000)),
        (40, bytes([VERIFY]) + b'""' + bytes([S.CODE]) + num(40000)),
        (50, bytes([S.PRINT]) + b'"FUSE OK"'),
    ], autorun=10)


DATA = bytes((i * 7 + 3) & 0xFF for i in range(1000))


def code_tap(name, start, data):
    """A TAP holding one CODE block."""
    hdr = bytes([3]) + name.encode().ljust(10)[:10] + bytes(
        [len(data) & 0xFF, len(data) >> 8, start & 0xFF, start >> 8, 0, 0x80])
    return S.tap_block(0x00, hdr) + S.tap_block(0xFF, data)


def keys(presses, end, peeks=()):
    """Debugger commands: each (frames to wait, code) is pressed in turn,
    once the ROM has taken the previous key; `end` frames after the last,
    print ERR_NR and the bytes at `peeks`."""
    c = ["set $t 0", "set $k 0", "break time 100", "commands 1", "set $t $t+1", "continue", "end"]
    for i, (wait, code) in enumerate(presses):
        c += ["break time 200 if $k==%d && $t>=%d && ([23611]&32)==0" % (i, wait),
              "commands %d" % (i + 2), "set 23560 %d" % code, "set 23611 [23611]|32",
              "set $k %d" % (i + 1), "set $t 0", "continue", "end"]
    c += ["break time 300 if $k==%d && $t==%d" % (len(presses), end),
          "commands %d" % (len(presses) + 2), "print [23610]"]
    c += ["print [%d]" % a for a in peeks] + ["continue", "end"]
    return "\n".join(c)


def main():
    keep = "--keep" in sys.argv
    if not os.path.exists(FUSE):
        sys.exit("No Fuse at %s: set $FUSE (built --with-null-ui --enable-automation)" % FUSE)
    for d in (ROOT, OUT):
        shutil.rmtree(d, ignore_errors=True)
    os.makedirs(OUT)
    rom = open(S.ROM, "rb").read()
    open(OUT + "/home.rom", "wb").write(rom[:16384])
    open(OUT + "/exrom.rom", "wb").write(rom[16384:])
    os.makedirs(ROOT)
    shutil.copytree(os.path.join(S.REPO, "src", "assets"), ROOT + "/assets")
    open(ROOT + "/assets/nofile.tap", "wb").write(test_program())
    os.makedirs(ROOT + "/sd/TAP")
    open(ROOT + "/sd/TAP/fusedata.tap", "wb").write(code_tap("fusedata", 40000, DATA))

    subprocess.run(["pkill", "-f", "tools/emu/pico_host.py"], stderr=subprocess.DEVNULL)
    host = subprocess.Popen([sys.executable, "-u", os.path.join(HERE, "pico_host.py"), "--root", ROOT],
                            stdout=open(LOG, "w"), stderr=subprocess.STDOUT)
    try:
        t0 = time.time()
        while "listening" not in open(LOG).read():
            assert time.time() - t0 < 20, "pico_host didn't start: see " + LOG
            time.sleep(0.2)
        time.sleep(1.5)
        # ENTER past the copyright, then LOAD "" ENTER
        presses = [(150, 13), (10, 0xEF), (10, 0x22), (10, 0x22), (10, 13)]
        peeks = (40000, 40001, 40500, 40999)
        print("Fuse: LOAD \"\" runs the test program (CAT, mount, LOAD CODE, VERIFY)")
        r = subprocess.run([FUSE, "--machine", "ts2068", "--rom-ts2068-0", OUT + "/home.rom",
                            "--rom-ts2068-1", OUT + "/exrom.rom", "--no-sound", "--tspico",
                            "--debugger-command", keys(presses, 1200, peeks),
                            "--automation-frames", "2000", "--automation-capture-screen",
                            "--automation-output", OUT], capture_output=True, text=True, timeout=300)
    finally:
        host.terminate()
        host.wait(5)

    log = open(LOG).read()
    res = json.load(open(OUT + "/result.json"))
    check(r.returncode == 0 and res["execution"]["termination"]["type"] == "frames",
          "Fuse ran its 2000 frames")
    check("emulator connected (tcp" in log, "Fuse connected over TCP (HELLO)")
    check("Program: fusetest" in log or "LVM LOAD enter" in log, "LOAD \"\" fetched the test program")
    out = [int(l, 16) for l in r.stdout.splitlines() if l.startswith("0x")]
    check(len(out) == 1 + len(peeks) and out[0] == 0xFF,
          "the program ended 0 OK (ERR_NR %s)" % (hex(out[0]) if out else "?"))
    check(out[1:] == [DATA[a - 40000] for a in peeks], "LOAD CODE put the file's bytes at 40000")
    check("Traceback" not in log, "no firmware exception (%s)" % LOG)
    print("screen: %s/screen.png" % OUT)
    if not keep:
        shutil.rmtree(ROOT, ignore_errors=True)

    print("\n%s (%d checks)" % ("ALL PASS" if all(results) else "FAILED", len(results)))
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
