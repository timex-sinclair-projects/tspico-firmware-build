#!/usr/bin/env python3
"""Probe-and-compare: what a TS-Pico operation leaves the 2068 with.

The host tests check the bytes the firmware sends. Ryan's edge cases
(#446, #447, #370, #373, #314) were all correct bytes that left the 2068
in a wrong state, which showed one or two operations later: a TV_FLAG bit
left set, a lower screen one line too tall, colours that leaked. This runs
each operation inside a BASIC program in ZEsarUX, with the real firmware
behind it, and checks the machine after it, three ways:

  1. **System variables against a reference.** A machine-code routine
     (RANDOMIZE USR) copies the system variables at 5C00h into a slot,
     before and after a reference statement that does the same job the
     ROM's own way (a keyboard INPUT for an INPUT #, a no-op for a quiet
     command), and after the operation. The watched variables after the
     operation must equal the ones after the reference; a case lists the
     ones it may change (a listing moves the print position).
  2. **A follow-up probe.** After the operation the program prints 30
     numbered lines, so the ROM's own "scroll?" comes up. Its line must
     read exactly "scroll?" (#446 printed 'scroll?LOAD ""' instead), and the lines
     around it must be whole and in order.
  3. **The picture, for SCREEN$.** The display file is copied just before
     a SAVE "f:..." SCREEN$; the saved file must hold the same 6912 bytes
     (#447 scrolled it, #314 saved its own message into it).

Each case runs in a setup from SETUPS (the default colors, a blue screen,
messages on), each in its own fresh Session.

    python3 tools/emu/probe.py                 # every case, every setup (~75 min)
    python3 tools/emu/probe.py fin cat         # just these cases
    python3 tools/emu/probe.py --setup blue    # just this setup
    python3 tools/emu/probe.py --list

TSPICO_ROM / TSPICO_HOST pick another ROM or firmware, as for session.py
(an old ROM: TSPICO_ROM=src/rom/TSPICO-24.ROM shows #446). Session()
stops every other ZEsarUX and pico_host on the machine: check with pgrep
before running it next to another session.
"""

import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import session as S                                   # noqa: E402

REPO = S.REPO
ROOT = "/tmp/tspico-root"
TAP = os.path.join(ROOT, "sd", "TAP")

# ---- machine code, poked above RAMTOP (the program CLEARs 39999) ----
SNAP = 0xBF00          # RANDOMIZE USR 48896: system variables to the next slot
SCRCP = 0xBF20         # RANDOMIZE USR 48928: the display file to SCRBUF
COUNT = 0xBFF0         # slots taken so far
SLOTS = 0xC000         # slot k at SLOTS + 256*k
SCRBUF = 40000
SYSVARS, NSYS = 0x5C00, 0xB6

SNAP_CODE = bytes([
    0x21, COUNT & 0xFF, COUNT >> 8,     # ld hl,COUNT
    0x7E,                               # ld a,(hl)
    0x34,                               # inc (hl)
    0xC6, SLOTS >> 8,                   # add a,high SLOTS
    0x57,                               # ld d,a
    0x1E, 0x00,                         # ld e,0
    0x21, SYSVARS & 0xFF, SYSVARS >> 8,  # ld hl,5C00h
    0x01, NSYS, 0x00,                   # ld bc,NSYS
    0xED, 0xB0,                         # ldir
    0xC9,                               # ret
])
SCRCP_CODE = bytes([
    0x21, 0x00, 0x40,                   # ld hl,4000h
    0x11, SCRBUF & 0xFF, SCRBUF >> 8,   # ld de,SCRBUF
    0x01, 0x00, 0x1B,                   # ld bc,6912
    0xED, 0xB0,                         # ldir
    0xC9,                               # ret
])

# ---- the system variables compared (Spectrum layout, which the 2068 keeps) ----
WATCH = [  # name, address, size
    ("STRMS", 0x5C10, 38), ("FLAGS", 0x5C3B, 1), ("TV_FLAG", 0x5C3C, 1),
    ("ERR_SP", 0x5C3D, 2), ("MODE", 0x5C41, 1), ("CURCHL", 0x5C51, 2),
    ("FLAGS2", 0x5C6A, 1), ("DF_SZ", 0x5C6B, 1), ("BORDCR", 0x5C48, 1),
    ("DF_CC", 0x5C84, 2), ("DFCCL", 0x5C86, 2), ("S_POSN", 0x5C88, 2),
    ("S_POSNL", 0x5C8A, 2), ("SCR_CT", 0x5C8C, 1), ("ATTR_P", 0x5C8D, 1),
    ("MASK_P", 0x5C8E, 1), ("ATTR_T", 0x5C8F, 1), ("MASK_T", 0x5C90, 1),
    ("P_FLAG", 0x5C91, 1),
]
# What printing to the upper screen moves by itself.
PRINTS = ("DF_CC", "S_POSN", "SCR_CT", "ATTR_T", "MASK_T")
# The ROM's own way to print to the upper screen, for a case that prints:
# it leaves the channel (CURCHL, TV_FLAG bit 0, FLAGS2 bit 4) as printing does.
PRINT_REF = 'PRINT "";'
# Bits a printing case may leave different: FLAGS bit 0 is the leading-space
# flag, which follows the last character printed.
PRINT_MASKS = {"FLAGS": 0xFE}
# A difference the probe finds that is known and not fixed yet: it prints as
# KNOWN, not FAIL, so a run on main is clean and a new difference stands out.
# Take the entry out when the fix lands; a KNOWN that passes says so.
SCR_CT_FF = ("SCR_CT left at FFh: the ROM module prints with no scroll? stop "
             "(PRINT_A, src/rom/fdd/fddcmd.asm) and doesn't put it back, so the "
             "program's next 255 lines scroll without asking")


class Case:
    def __init__(self, name, what, op, ref="LET z=0", keys=None, allow=(), screen=False,
                 setups=None, pre=(), masks=None, known=None):
        self.name, self.what, self.op, self.ref = name, what, op, ref
        self.masks = masks or {}    # name: the bits of it compared
        self.known = known or {}    # check key ("sysvars", "scroll", ...): why it's known
        self.keys = keys            # typed at the reference's keyboard INPUT
        self.allow = set(allow)     # watched variables the operation may leave different
        self.screen = screen        # a SAVE "f:..." SCREEN$: check the saved picture
        self.setups = setups        # None = every setup
        self.pre = list(pre)        # lines before the reference (files the op needs)


CASES = [
    Case("fin", 'INPUT # from an f: file (#446)',
         ['OPEN #5,"f:probe.txt","r"', 'INPUT #5;a$', 'CLOSE #5'],
         ref="INPUT a$", keys="abc",
         pre=['OPEN #4,"f:probe.txt","w"', 'PRINT #4;"Enough to make it scroll...."',
              'CLOSE #4', 'PAUSE 10']),
    Case("fout", 'PRINT # to an f: file, then CLOSE #',
         ['OPEN #4,"f:probe2.txt","w"', 'PRINT #4;"one line"', 'CLOSE #4'],
         ref='OPEN #4,"s": PRINT #4;"";: CLOSE #4'),
    Case("din", 'INPUT # from a d: folder listing',
         ['OPEN #4,"d:*.tap"', 'INPUT #4;a$', 'CLOSE #4'], ref="INPUT a$", keys="abc"),
    Case("xin", 'PRINT #, INPUT # through x: (path)',
         ['OPEN #4,"x:"', 'PRINT #4;"path"', 'INPUT #4;a$', 'CLOSE #4'], ref="INPUT a$", keys="abc"),
    Case("cat", 'CAT (a coloured listing, #370 #373)',
         ['CAT'], ref=PRINT_REF, allow=PRINTS, masks=PRINT_MASKS, known={"scroll": SCR_CT_FF}),
    Case("info", 'SAVE "tpi:info" (a coloured screen)',
         ['SAVE "tpi:info"'], ref=PRINT_REF, allow=PRINTS, masks=PRINT_MASKS,
         known={"scroll": SCR_CT_FF}),
    Case("path", 'SAVE "tpi:path"', ['SAVE "tpi:path"'], ref=PRINT_REF, allow=PRINTS,
         masks=PRINT_MASKS, known={"scroll": SCR_CT_FF}),
    Case("scr", 'SAVE "f:" SCREEN$ over an old file: the Replace? question (#447, #314)',
         ['SAVE "f:probe.scr"SCREEN$'], screen=True, allow=PRINTS, known={"scroll": SCR_CT_FF},
         pre=['SAVE "f:probe.scr"SCREEN$']),
]

SETUPS = {  # name: lines run first (and whether messages are on)
    "plain": [],
    "blue": ["BORDER 1: PAPER 1: INK 7: CLS"],
    "verbose": ['SAVE "tpi:verbose on"'],
}


def check(results, cond, msg, known=None):
    if known and not cond:
        print("  KNOWN " + msg + "\n          " + known, flush=True)
        return
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg
          + ("  (listed as known: take it out of the case)" if known else ""), flush=True)


def zmakebas():
    d = os.path.join(REPO, "tools", "zmakebas")
    z = os.path.join(d, "zmakebas")
    if not os.access(z, os.X_OK) or os.path.getmtime(z) < os.path.getmtime(z + ".c"):
        subprocess.run(["make", "-C", d, "zmakebas"], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return z


def program(case, setup):
    """The case as zmakebas text. Slots: 0 before the reference, 1 after it,
    2 after the operation, 3 after the probe."""
    # The setup's own messages leave SCR_CT at FFh (the ROM module prints
    # them with no scroll? stop); POKE it back so only the case's own
    # operation can change it.
    L = ["CLEAR 39999"] + SETUPS[setup] + ["POKE 23692,1"]
    if case.screen:                     # something to see in the picture
        L += ['FOR i=0 TO 20: PRINT "row ";i;" ";CHR$ (65+i);"#=+-.": NEXT i']
    L += case.pre
    L += ["RANDOMIZE USR %d" % SNAP, case.ref, "RANDOMIZE USR %d" % SNAP]
    if case.screen:
        L += ["RANDOMIZE USR %d" % SCRCP]
    L += case.op
    L += ["RANDOMIZE USR %d" % SNAP,
          'FOR i=1 TO 30: PRINT "P";i: NEXT i',
          "RANDOMIZE USR %d" % SNAP,
          'PRINT "PROBE DONE"']
    return "".join("%d %s\n" % (10 * (n + 1), l) for n, l in enumerate(L))


def decode(raw):
    return {name: raw[a - SYSVARS:a - SYSVARS + n] for name, a, n in WATCH}


def show(name, v):
    if name == "STRMS":
        return " ".join("#%d=%d" % (i - 3, v[2 * i] | v[2 * i + 1] << 8)
                        for i in range(19) if v[2 * i] | v[2 * i + 1])
    if len(v) == 2 and name in ("S_POSN", "S_POSNL"):
        return "col %d line %d" % (v[0], v[1])
    if len(v) == 2:
        return "%04Xh" % (v[0] | v[1] << 8)
    return "%02Xh (%s)" % (v[0], format(v[0], "08b"))


def bottom(text):
    lines = text.splitlines()
    return lines[-1].rstrip() if lines else ""


def find_file(name):
    for d, _, fs in os.walk(os.path.join(ROOT, "sd")):
        if name in fs:
            return os.path.join(d, name)
    return None


def run_case(case, setup, results):
    print("\n== %s [%s]: %s" % (case.name, setup, case.what), flush=True)
    src = os.path.join("/tmp", "probe_%s.bas" % case.name)
    with open(src, "w") as f:
        f.write(program(case, setup))
    with S.Session(root=ROOT) as s:
        os.makedirs(TAP, exist_ok=True)
        subprocess.run([zmakebas(), "-a", "10", "-n", "probe", "-o", os.path.join(TAP, "probe.tap"), src],
                       check=True)
        s.poke(SNAP, SNAP_CODE)
        s.poke(SCRCP, SCRCP_CODE)
        s.poke(COUNT, b"\x00")
        t = s.run(S.LOAD, '"tpi:probe.tap"')
        if "0 OK" not in t:
            check(results, False, "mounted probe.tap:\n" + t)
            return
        s.run(S.LOAD, '""', until="\x00never", timeout=0)   # start it; the loop below follows it
        fed = False
        prompts = []                # the probe's scroll? lines
        replace_seen = 0
        t0 = time.time()
        text = ""
        while time.time() - t0 < 180:
            time.sleep(0.4)
            text = s.text()
            n = s.peek(COUNT, 1)[0]
            low = text.lower()
            if case.keys and n == 1 and not fed:
                time.sleep(0.8)                              # the INPUT's cursor is up
                s.cmd("send-keys-ascii 120 " + " ".join(str(ord(c)) for c in case.keys))
                s.key(129)
                fed = True
                continue
            if "scroll?" in low:
                if n >= 3:
                    prompts.append(bottom(text))
                s.cmd("send-keys-ascii 120 121")             # y
                time.sleep(0.6)
                continue
            if "replace" in low and "(y/n)" in low:
                replace_seen += 1
                s.cmd("send-keys-ascii 120 121")
                time.sleep(0.8)
                continue
            if "press any key" in low:
                s.key(129)
                time.sleep(0.8)
                continue
            if s.peek(S.ERR_NR, 1)[0] != 0xFF:
                break
        report = bottom(text)
        check(results, "PROBE DONE" in text and report.startswith("0 OK"),
              "ran to the end: %r" % report)
        n = s.peek(COUNT, 1)[0]
        slots = [decode(s.peek(SLOTS + 256 * k, NSYS)) for k in range(min(n, 4))]
        if len(slots) < 3:
            check(results, False, "only %d of 4 snapshots taken" % len(slots))
            return

        # 1. the watched system variables: after the operation as after the reference
        def seen(k, nm):
            m = case.masks.get(nm)
            return bytes(b & m for b in slots[k][nm]) if m is not None else slots[k][nm]
        diffs = [nm for nm, _, _ in WATCH if seen(2, nm) != seen(1, nm) and nm not in case.allow]
        for nm, _, _ in WATCH:
            if nm in diffs or (nm in case.allow and slots[2][nm] != slots[1][nm]):
                print("        %-8s after %r: %s   after the operation: %s%s"
                      % (nm, case.ref, show(nm, slots[1][nm]), show(nm, slots[2][nm]),
                         "" if nm in diffs else "   (allowed)"))
        check(results, not diffs, "system variables match the reference%s"
              % (" (differ: %s)" % ", ".join(diffs) if diffs else ""), case.known.get("sysvars"))
        check(results, slots[2]["DF_SZ"][0] == 2, "DF_SZ is 2 (lower screen two lines): %d"
              % slots[2]["DF_SZ"][0])

        # 2. the probe: every scroll? clean, the numbered lines whole and in order
        check(results, prompts and all(p == "scroll?" for p in prompts),
              "the probe's scroll? prompts read exactly 'scroll?': %r" % prompts, case.known.get("scroll"))
        nums = []
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("P") and line[1:].isdigit():
                nums.append(int(line[1:]))
            elif nums and line and not line.startswith(("PROBE DONE", "0 OK")):
                nums.append(None)                           # a broken line among them
        ok = nums and None not in nums and nums == list(range(nums[0], nums[0] + len(nums))) \
            and nums[-1] == 30
        check(results, ok, "the probe's lines after scroll? are whole and in order (%s)"
              % (",".join("?" if x is None else str(x) for x in nums[:6]) + ("..." if len(nums) > 6 else "")))

        # 3. SCREEN$: the saved picture is the screen from just before the SAVE
        if case.screen:
            check(results, replace_seen >= 1, "the second SAVE asked Replace?")
            p = find_file("probe.scr")
            if not p:
                check(results, False, "probe.scr on the card")
            else:
                saved = open(p, "rb").read()[-6912:]
                before = s.peek(SCRBUF, 6912)
                rows = [r for r in range(24) if row_bytes(saved, r) != row_bytes(before, r)]
                check(results, not rows, "the saved picture is the screen before the SAVE%s"
                      % (" (rows differ: %s)" % rows if rows else ""))


def row_bytes(scr, r):
    """Character row r of a SCREEN$: its 8 pixel lines and its attributes."""
    third, line = divmod(r, 8)
    px = b"".join(scr[third * 2048 + p * 256 + line * 32:][:32] for p in range(8))
    return px + scr[6144 + r * 32:][:32]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cases", nargs="*", help="case names (default: all)")
    ap.add_argument("--setup", action="append", choices=sorted(SETUPS), help="(default: all)")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list:
        for c in CASES:
            print("%-6s %s" % (c.name, c.what))
        return 0
    cases = [c for c in CASES if not a.cases or c.name in a.cases]
    if a.cases and len(cases) != len(set(a.cases)):
        ap.error("unknown case: %s" % ", ".join(set(a.cases) - {c.name for c in CASES}))
    results, failed = [], []
    for c in cases:
        for st in a.setup or sorted(SETUPS):
            if c.setups and st not in c.setups:
                continue
            k = len(results)
            for attempt in (1, 2):              # once more if the harness itself trips
                try:
                    run_case(c, st, results)
                    break
                except AssertionError as e:     # session.py: typing or start-up failed
                    del results[k:]
                    print("  harness error (try %d): %s" % (attempt, str(e).splitlines()[0]), flush=True)
                    if attempt == 2:
                        check(results, False, "the harness ran the case")
            if not all(results[k:]):
                failed.append("%s[%s]" % (c.name, st))
    print("\n%d/%d passed%s" % (sum(results), len(results),
                               ("; failed: " + " ".join(failed)) if failed else ""))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
