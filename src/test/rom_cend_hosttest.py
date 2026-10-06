"""ROM 2.1's BIOS C_END (EXROM $184A -> C_END2) in the Z80 interpreter.

ROM 2.0's C_END failed with A = 02h both for a timeout and for status 3
(Report F). ROM 2.1 sends the table entry to the fdd module's C_END2, which
returns a timeout as 09h (J). This runs the built ROM's EXROM from the $184A
entry against a model Pico (the status port and the data FIFO) and checks
every outcome:

    status 1                -> carry clear, A = 0
    status 3                -> carry, A = 02h (F)
    status 10               -> carry, A = 09h (J)
    Pico never READY        -> carry, A = 09h (J, was 02h = F)
    RECOVERED (status FBh)  -> carry, A = 1Ch (T)
    ROM 2.0 on a timeout    -> carry, A = 02h (the ambiguity, for contrast)

Uses the committed slot-1 image, src/rom/TSPICO-22.ROM (CI checks it is
what tools/build-rom.py builds). Run:
    python3 src/test/rom_cend_hosttest.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from z80core import Z80                                          # noqa: E402

FDD = os.path.join(REPO, "src", "rom", "TSPICO-22.ROM")
BASE = os.path.join(REPO, "src", "rom", "TSPICO-SYNC.ROM")
DONE = 0xFF00
results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg)


def run(rom, status, answer):
    """Call EXROM $184A. status: what port 0Fh reads; answer: the TX bytes."""
    mem = bytearray(65536)
    mem[0:0x4000] = rom[0x4000:0x8000]                    # the EXROM paged in
    tx = list(answer)

    def port_in(port):
        p = port & 0xFF
        if p == 0x0F:
            return status
        if p == 0x0E:
            return tx.pop(0) if tx else 0
        return 0xFF                                       # no key down

    cpu = Z80(lambda a: mem[a], lambda a, v: mem.__setitem__(a, v) if a >= 0x4000 else None,
              port_in, lambda port, v: None)
    cpu.sp = 0xFE00
    cpu.push(DONE)
    cpu.pc = 0x184A
    while cpu.pc != DONE and cpu.t < 200_000_000:
        cpu.step()
    return cpu.pc == DONE, cpu.f & 1, cpu.a, cpu.t


def main():
    if not os.path.exists(FDD):
        print("src/rom/TSPICO-22.ROM missing")
        return 1
    fdd = open(FDD, "rb").read()
    base = open(BASE, "rb").read()

    ok, c, a, _ = run(fdd, 0xFF, [1])
    check(ok and not c and a == 0, "status 1: carry clear, A = 0 (C=%d A=%02X)" % (c, a))
    ok, c, a, _ = run(fdd, 0xFF, [3])
    check(ok and c and a == 0x02, "status 3: carry, A = 02h, F (C=%d A=%02X)" % (c, a))
    ok, c, a, _ = run(fdd, 0xFF, [10])
    check(ok and c and a == 0x09, "status 10: carry, A = 09h, J (C=%d A=%02X)" % (c, a))
    ok, c, a, t = run(fdd, 0xFB, [1])
    check(ok and c and a == 0x1C, "RECOVERED: carry, A = 1Ch, T (C=%d A=%02X)" % (c, a))
    ok, c, a, t = run(fdd, 0x00, [])
    check(ok and c and a == 0x09, "no READY: carry, A = 09h, J -- not F (C=%d A=%02X, %.1f s)"
          % (c, a, t / 3.528e6))
    ok, c, a, _ = run(base, 0x00, [])
    check(ok and c and a == 0x02, "ROM 2.0 for contrast: timeout gives 02h, the same as F (A=%02X)" % a)

    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
