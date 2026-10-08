#!/usr/bin/env python3
"""End-to-end smoke test with no hardware: the TS-Pico ROM in ZEsarUX, the
real firmware behind it (tools/emu/pico_host.py). Checks what the 2068 shows
and what lands on the emulated card. About two minutes.

    python3 tools/emu/smoke.py [--keep]      (--keep: leave /tmp/tspico-root)
"""

import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import session as S                                           # noqa: E402

SEED = "/tmp/tspico-smoke-seed"
ROOT = "/tmp/tspico-root"
results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg, flush=True)


def seed():
    if os.path.isdir(SEED):
        shutil.rmtree(SEED)
    os.makedirs(os.path.join(SEED, "TAP", "GAMES"))
    shutil.copytree(os.path.join(S.REPO, "SD card", "help"), os.path.join(SEED, "help"))
    with open(os.path.join(SEED, "TAP", "hello.tap"), "wb") as f:
        f.write(S.basic_tap("hello", [(10, bytes([S.PRINT]) + b'"HELLO FROM THE TS-PICO"')]))


def main():
    seed()
    s = S.Session(root=ROOT, sd=SEED)
    try:
        print("CAT")
        t = s.run(S.CAT)
        check("000 hello.tap" in t and "<GAMES>" in t and "0 OK" in t, "lists the card")

        print('LOAD "tpi:hello.tap", LOAD "", LIST')
        s.run(S.LOAD, '"tpi:hello.tap"')
        t = s.run(S.LOAD, '""')
        check("Program: hello" in t and "0 OK" in t, "mounted and loaded")
        t = s.run(0xF0)                                        # LIST
        check('HELLO FROM THE TS-PI' in t, "the program arrived intact")

        print('SAVE "saved"')
        s.run(S.SAVE, '"saved"', until="press any key", timeout=15)
        s.key(129)
        t0 = time.time()
        p = os.path.join(ROOT, "sd", "TAP", "saved.tap")
        while not os.path.exists(p) and time.time() - t0 < 20:
            time.sleep(0.5)
        check(os.path.exists(p) and os.path.getsize(p) > 40, "saved.tap is on the card")

        print('SAVE "tpi:info"')
        t = s.run(S.SAVE, '"tpi:info"')
        check("interface status" in t and "uPython 1.29.0" in t and "0 OK" in t, "status screen")
        check("ROM       2.3" in t or "ROM 2.3" in " ".join(t.split()),
              "its ROM line is the version ROM 2.3 sent in the pre-header")

        print('SAVE "tpi:picopt", LPRINT')
        s.run(S.SAVE, '"tpi:picopt"')
        s.run(S.LPRINT, '"LPRINT through the emulator"')
        s.run(S.SAVE, '"tpi:path"')                            # another command writes the text out
        p = os.path.join(ROOT, "sd", "VLPRINT", "PRN0001.TXT")
        check(os.path.exists(p) and "LPRINT through the emulator" in open(p).read(), "printer text on the card")

        print('SAVE "tpi:cd" (the menu, then n)')
        t = s.run(S.SAVE, '"tpi:cd"', until="quit?", timeout=30)
        s.cmd("send-keys-ascii 120 110")                       # n: the Pico echoes it and ends the loop
        time.sleep(3)
        t = s.text()
        check("0 OK" in t, "n cancels the menu")
        t = s.run(S.SAVE, '"tpi:path"')
        check("/TAP" in t and "0 OK" in t, "and the next command reads a clean link")

        print('SAVE "tpi:cd" (the menu, then 0)')
        t = s.run(S.SAVE, '"tpi:cd"', until="quit?", timeout=30)
        check("0 GAMES" in t, "the folder menu")
        s.cmd("send-keys-ascii 120 48")
        time.sleep(3)
        t = s.text()
        check("Changing dir to:" in t and "0 OK" in t, "a key picks the folder")
        t = s.run(S.SAVE, '"tpi:path"')
        check("/TAP/GAMES" in t, "and the Pico is in it")
    finally:
        s.close()
    host = open("/tmp/pico_host.out").read()
    check("Traceback" not in host, "no firmware exception (/tmp/pico_host.out)")
    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    if "--keep" not in sys.argv:
        shutil.rmtree(ROOT, ignore_errors=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
