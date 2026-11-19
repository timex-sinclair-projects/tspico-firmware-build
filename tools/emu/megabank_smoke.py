#!/usr/bin/env python3
"""The Megabank test ROM end to end in ZEsarUX's Megabank model.

Builds build/TSPICO-mb.ROM (tools/build-rom.py --megabank) unless
TSPICO_ROM names one, starts ZEsarUX with the board fitted (MEGABANK=1;
the model is in the zesarux-tspico fork's tspico-device branch, MEGABANK.md)
and pico_host -- the real firmware, with the RAM disk (src/TS/ramdisk.py) and
one test-only command added (megabank_host.py) -- and checks:

  - the boot: the version marker (PEEK 101 = 37, 25h), the board's owner
    table empty, the bank count (5CBEh, 6315h) and BASE (6404h) from the
    board, SYSCON's end marker; BANK_ENABLE mapping a bank and back;
  - the mover's operations 4-7 and its range and XOR checks (tpi:mbtest),
    and an answer after op 0 that is a function (81h);
  - no RAM disk until FORMAT "r:"; then SAVE / LOAD / VERIFY "r:name" for a
    program and for CODE, a VERIFY that fails (R), LOAD of a name the disk
    hasn't got (F);
  - CAT "r:", MOVE (rename), ERASE, COPY both ways between the card and the
    RAM disk and on the RAM disk, SAVE "tpi:ram", FORMAT asked twice, a
    backup to the card and a restore;
  - a program's own page mapped in chunk 5 (OWN5, SUB5) survives r:
    transfers whose window is chunk 5. (Its HSR bit doesn't: every tpi:
    command clears the HSR, ROM 2.4 included; the run prints it as a NOTE);
  - an ordinary SAVE to the card after all that (TPMODE bit 5 cleared).

ZEsarUX's model ignores the HSR (an owned chunk is the board's whatever F4h
says), so it can't catch a missing HSR bit; src/test/rom_megabank_hosttest.py
models that rule.

    ZESARUX=/path/to/zesarux-with-megabank python3 tools/emu/megabank_smoke.py
"""

import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
LOG = "/tmp/megabank_host.jsonl"

if "TSPICO_ROM" not in os.environ:
    subprocess.run([sys.executable, os.path.join(REPO, "tools", "build-rom.py"), "--megabank", "--verify"],
                   check=True, stdout=subprocess.DEVNULL)
    os.environ["TSPICO_ROM"] = os.path.join(REPO, "build", "TSPICO-mb.ROM")
os.environ.setdefault("MEGABANK", "1")
os.environ["TSPICO_HOST"] = os.path.join(HERE, "megabank_host.py")
os.environ["MEGABANK_HOST_LOG"] = LOG
if os.path.exists(LOG):
    os.remove(LOG)

sys.path.insert(0, HERE)
import session as S                                    # noqa: E402

PRINT, LIST, NEW, VERIFY, OUT, POKE, LET = 0xF5, 0xF0, 0xE6, 0xD6, 0xDF, 0xF4, 0xF1
FORMAT, ERASE, COPY = 0xD0, 0xD2, 0xFF
TAP = "/tmp/tspico-root/sd/TAP/"
IN, PEEK, USR = 0xBF, 0xBE, 0xC0
results = []


def check(cond, msg, extra=""):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg + ("" if cond else "\n" + extra))


def report(t):
    """The report line at the bottom of the screen."""
    lines = [l for l in t.splitlines() if l.strip()]
    return lines[-1].strip() if lines else ""


def save(s, *line):
    """A SAVE: answer "Start tape, then press any key" (stock SAVE asks for
    the card too), then wait for the report; the screen text."""
    s.run(S.SAVE, *line, until="press any key", timeout=15)
    s.key(129)
    t0 = time.time()
    while time.time() - t0 < 60:
        time.sleep(0.5)
        t = s.text()
        if re.search(r"\b0 OK, \d+:\d+", t) or s.peek(S.ERR_NR, 1)[0] != 0xFF:
            return t
    return s.text()


def value(s, *line):
    """Run a line that PRINTs one number; the number (the screen's first line)."""
    s.run(0xFB)                                        # CLS
    t = s.run(*line)
    first = [l for l in t.splitlines() if l.strip()][0].strip()
    return int(first)


def main():
    with S.Session() as s:
        # --- boot ---
        check(value(s, PRINT, PEEK, "101") == 0x25, "PEEK 101 = 37: the Megabank test ROM (2.5)")
        owners = [value(s, OUT, "253,%d:" % n, PRINT, IN, "252") for n in range(8)]
        check(owners == [0] * 8, "after the boot every OWNn is 0", str(owners))
        base = value(s, OUT, "253,20:", PRINT, IN, "252")
        size = value(s, OUT, "253,21:", PRINT, IN, "252")
        want = min(size, 254 - base)
        mb = s.peek(0x5CBE, 1)[0], s.peek(0x6315, 1)[0], s.peek(0x6404, 1)[0]
        check(mb == (want, want, base), "the bank count %d (5CBEh, 6315h) and BASE %d (6404h), from the board"
              % (want, base), str(mb))

        # --- the Timex bank API (bankapi.asm): BANK_ENABLE there and back ---
        # F000h: BANK_ENABLE(BASE, chunk 6); A = (C000h); (C000h) = (F020h);
        # BANK_ENABLE(HOME, chunk 6); BC = the byte read.
        s.poke(0xF000, bytes([0x06, base, 0x0E, 0xBF, 0xCD, 0x99, 0x64, 0x3A, 0x00, 0xC0, 0xF5,
                              0x3A, 0x20, 0xF0, 0x32, 0x00, 0xC0, 0x06, 0xFF, 0x0E, 0xBF,
                              0xCD, 0x99, 0x64, 0xF1, 0x4F, 0x06, 0x00, 0xC9]))
        s.poke(0xC000, b"\x11")
        s.poke(0xF020, b"\x55")
        value(s, PRINT, USR, "61440")
        s.poke(0xF020, b"\x66")
        got = value(s, PRINT, USR, "61440")
        check(got == 0x55 and s.peek(0xC000, 1)[0] == 0x11,
              "BANK_ENABLE: bank %d in chunk 6 and back; its byte kept (55h: %02Xh), HOME's C000h untouched"
              % (base, got), str(s.peek(0xC000, 1)))
        sc = int.from_bytes(s.peek(0x5CBC, 2), "little")
        check(sc == 0x5EEA and s.peek(sc + 12, 1)[0] == 0x80,
              "SYSCON is 5EEAh and its first bank entry is the 80h end marker",
              "%04X %s" % (sc, s.peek(sc, 16).hex()))

        # --- the mover's operations 4-7 ---
        t = s.run(S.SAVE, '"tpi:mbtest"')
        check("mbtest ok" in t and "0 OK" in report(t), "tpi:mbtest: ops 4-7, range, XOR, 81h after op 0", t)

        # --- no RAM disk until FORMAT ---
        s.run("10 ", PRINT, '"MEGA"', until="")
        time.sleep(0.5)
        t = save(s, '"r:prog"')
        check("J Invalid I/O device" in report(t), 'SAVE "r:prog" before FORMAT "r:": J', t)
        t = s.run(FORMAT, '"r:"')
        check("0 OK" in report(t), 'FORMAT "r:"', t)
        t = s.run(S.SAVE, '"tpi:ram"')
        check("RAM disk: 2048K, pages 256-511" in t and "0 files, 2040K free" in t
              and "Megabank: 4096K, banks 1-64" in t, 'SAVE "tpi:ram": half the board, empty', t)

        # --- a program to the RAM disk and back ---
        t = save(s, '"r:prog"')
        check("0 OK" in report(t), 'SAVE "r:prog"', t)
        s.run(NEW, until="")
        time.sleep(1.5)
        t = s.run(S.LOAD, '"r:prog"')
        check("0 OK" in report(t), 'LOAD "r:prog"', t)
        t = s.run(LIST)
        check('10 PRINT "MEGA"' in t, "the program came back", t)
        t = s.run(VERIFY, '"r:prog"')
        check("0 OK" in report(t), 'VERIFY "r:prog"', t)

        # --- CODE, with a program's own page in chunk 5 ---
        pat = bytes((i * 13 + 5) & 0xFF for i in range(3000))
        s.poke(32768, pat)                                # chunk 4 only (8000h-8BB7h)
        s.run(OUT, "253,5:", OUT, "252,3:", OUT, "244,32:", POKE, "40960,123")
        t = save(s, '"r:code"', S.CODE, "32768,3000")
        check("0 OK" in report(t), 'SAVE "r:code" CODE 32768,3000 (window: chunk 5, a program\'s)', t)
        s.poke(32768, bytes(3000))
        t = s.run(S.LOAD, '"r:code"', S.CODE)
        check("0 OK" in report(t) and s.peek(32768, 3000) == pat, 'LOAD "r:code" CODE: the bytes came back', t)
        t = s.run(VERIFY, '"r:code"', S.CODE)
        check("0 OK" in report(t), 'VERIFY "r:code" CODE', t)
        s.poke(33768, b"\x00" if pat[1000] else b"\x01")
        t = s.run(VERIFY, '"r:code"', S.CODE)
        check("R Tape loading error" in report(t), "VERIFY after a change: R", t)
        check(value(s, OUT, "253,5:", PRINT, IN, "252") == 3 and value(s, PRINT, PEEK, "40960") == 123,
              "chunk 5 is still bank 3, its byte still 123")
        # Not a check: every tpi: command leaves the HSR at 0, in ROM 2.4 too
        # (the TS-Pico's bank crossings; the Megabank spec, phase 8 item 4).
        # The mover puts back the HSR it found, which by then is already 0.
        print("  NOTE  the HSR after the r: commands: %d (ROM 2.4's crossings clear it)"
              % value(s, PRINT, IN, "244"))
        check(all(value(s, OUT, "253,%d:" % n, PRINT, IN, "252") == 0 for n in (4, 6, 7)),
              "OWN4, OWN6, OWN7 are 0 again")
        s.run(OUT, "253,5:", OUT, "244,0:", OUT, "252,0")   # unmap: HSR, then OWN5

        # --- CAT, MOVE, ERASE, COPY ---
        t = s.run(S.CAT, '"r:"')
        check("2 files" in t and "prog" in t and "Program" in t and "code" in t and "3000" in t,
              'CAT "r:" lists both', t)
        t = s.run(S.MOVE, '"r:code"', S.TO, '"r:bytes"')
        check("0 OK" in report(t), 'MOVE "r:code" TO "r:bytes"', t)
        s.poke(32768, bytes(3000))
        t = s.run(S.LOAD, '"r:bytes"', S.CODE)
        check("0 OK" in report(t) and s.peek(32768, 3000) == pat, "LOAD the renamed file", t)
        t = s.run(COPY, '"r:bytes"', S.TO, '"mbcopy"')
        check("0 OK" in report(t) and os.path.exists(TAP + "mbcopy.tap"), 'COPY "r:bytes" TO "mbcopy" (the card)', t)
        try:
            raw = open(TAP + "mbcopy.tap", "rb").read()
        except OSError:
            raw = b""
        check(raw[:3] == b"\x13\x00\x00" and raw[3] == 3 and raw[24:24 + 3000] == pat,
              "mbcopy.tap: a header and the 3000 bytes")
        t = s.run(COPY, '"mbcopy"', S.TO, '"r:back"')
        check("0 OK" in report(t), 'COPY "mbcopy" TO "r:back"', t)
        s.poke(32768, bytes(3000))
        t = s.run(S.LOAD, '"r:back"', S.CODE)
        check("0 OK" in report(t) and s.peek(32768, 3000) == pat, "it loads", t)
        t = s.run(COPY, '"r:back"', S.TO, '"r:back2"')
        check("0 OK" in report(t), 'COPY "r:back" TO "r:back2" (on the board)', t)
        t = s.run(ERASE, '"r:back2"')
        check("0 OK" in report(t), 'ERASE "r:back2"', t)
        t = s.run(ERASE, '"r:back*"')
        check("1 file: back. ERASE again" in t, 'ERASE "r:back*" says what it would do', t)
        t = s.run(ERASE, '"r:back*"')
        check("0 OK" in report(t), "and does it the second time", t)
        t = s.run(S.CAT, '"r:"')
        check("2 files" in t and "back" not in t and "bytes" in t, "CAT: prog and bytes left", t)

        # --- backup and restore, on a small RAM disk ---
        t = s.run(FORMAT, '"r:64"')
        check("holds 2 files. FORMAT again" in t.replace("\n", ""), 'FORMAT "r:64" over files asks to be repeated', t)
        t = s.run(FORMAT, '"r:64"')
        check("0 OK" in report(t), "FORMAT again: done", t)
        t = save(s, '"r:small"', S.CODE, "32768,3000")
        check("0 OK" in report(t), 'SAVE "r:small" CODE onto the 64K disk', t)
        t = s.run(S.SAVE, '"tpi:ram backup mbimg"', timeout=120)
        sz = os.path.getsize(TAP + "mbimg.rdi") if os.path.exists(TAP + "mbimg.rdi") else 0
        check("0 OK" in report(t) and sz == 65536, 'SAVE "tpi:ram backup mbimg": 64K on the card', t)
        t = s.run(ERASE, '"r:small"')
        t = s.run(S.SAVE, '"tpi:ram restore mbimg"', timeout=120)
        check("0 OK" in report(t), 'SAVE "tpi:ram restore mbimg"', t)
        s.poke(32768, bytes(3000))
        t = s.run(S.LOAD, '"r:small"', S.CODE)
        check("0 OK" in report(t) and s.peek(32768, 3000) == pat, "the erased file is back", t)

        # --- errors, and the next ordinary SAVE ---
        t = s.run(S.LOAD, '"r:nofile"')
        check("F Invalid file name" in report(t), 'LOAD "r:nofile": F', t)
        t = save(s, '"mbplain"', S.CODE, "40000,10")
        check("0 OK" in report(t) and os.path.exists("/tmp/tspico-root/sd/TAP/mbplain.tap"),
              'then SAVE "mbplain" CODE goes to the card', t)
        t = s.run(S.LOAD, '"r:small"', S.CODE)
        check("0 OK" in report(t), 'and LOAD "r:small" CODE still works', t)

    try:
        with open(LOG) as f:
            for line in f:
                d = json.loads(line)
                if d.get("cmd") == "mbtest":
                    print("  mbtest:", d)
    except OSError:
        pass
    print("%d/%d passed" % (sum(results), len(results)))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
