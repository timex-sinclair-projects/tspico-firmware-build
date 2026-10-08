"""ROM 2.1's switch words (SAVE "tpi:tape" and friends) in the Z80 interpreter.

TPMODE (5DDBh) holds two switches: bit 0 sends printing to the Pico
(tpi:picopt sets it, tpi:ts2040 clears it), bit 1 sends LOAD and SAVE to it
(tpi:sdcard sets it, tpi:tape clears it). ROM 2.0's tpi:tape set the whole
byte to 0, so tpi:picopt, tpi:tape, tpi:sdcard left printing on the 2068
(#176). ROM 2.1 jumps from $20BE to the fdd module's TAPE_MODE, which clears
bit 1 alone. This runs the built ROM's EXROM from the switch-word dispatch
($1B4F, the runtime pass of SAVE "tpi:...") with each word in RAM and checks
TPMODE after it:

    tpi:tape   from 3 -> 1, from 2 -> 0, from 1 -> 1, from 0 -> 0
    picopt, tape, sdcard from 2 -> 3 (printing stays on the Pico)
    tpi:sdcard, tpi:picopt, tpi:ts2040 as before
    tpi:tapex (length 9) -> not a switch word: sent to the Pico
    ROM 2.0, for contrast: tpi:tape from 3 -> 0

Uses the committed slot-1 image, src/rom/TSPICO-23.ROM (CI checks it is
what tools/build-rom.py builds). Run:
    python3 src/test/rom_tpmode_hosttest.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

from z80core import Z80                                          # noqa: E402

FDD = os.path.join(REPO, "src", "rom", "TSPICO-23.ROM")
BASE = os.path.join(REPO, "src", "rom", "TSPICO-SYNC.ROM")

TPMODE = 0x5DDB
NAME_LEN = 0x5DD5           # SESSION_SETUP keeps the name's length here
NAME = 0x8000
DISPATCH = 0x1B4F           # POP HL / ... / the first letter: just past $1B48's
                            # runtime test, BIT 7,(IY+1) (z80core has no IY)
STORED = 0x2108             # after S_MODE: "0 OK" follows
SENT = 0x210E               # not a switch word: on to the Pico

results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg)


def switch(rom, word, tpmode):
    """Run SAVE "word" through the switch words; return (where, TPMODE)."""
    mem = bytearray(65536)
    mem[0:0x4000] = rom[0x4000:0x8000]                    # the EXROM paged in
    mem[NAME:NAME + len(word)] = word.encode()
    mem[NAME_LEN], mem[NAME_LEN + 1] = len(word), 0
    mem[TPMODE] = tpmode | 0x80                           # SESSION_NAMED: a TPI: name

    cpu = Z80(lambda a: mem[a], lambda a, v: mem.__setitem__(a, v) if a >= 0x4000 else None,
              lambda port: 0xFF, lambda port, v: None)
    cpu.sp = 0xFE00
    cpu.push(NAME + 3)                                    # the ':' -- $1B4F's POP HL, INC HL
    cpu.pc = DISPATCH
    while cpu.pc not in (STORED, SENT) and cpu.t < 1_000_000:
        cpu.step()
    return cpu.pc, mem[TPMODE]


def main():
    if not os.path.exists(FDD):
        print("src/rom/TSPICO-23.ROM missing")
        return 1
    fdd = open(FDD, "rb").read()
    base = open(BASE, "rb").read()

    print("tpi:tape clears bit 1 only (#176)")
    for before, after in ((3, 1), (2, 0), (1, 1), (0, 0)):
        pc, mode = switch(fdd, "tpi:tape", before)
        check(pc == STORED and mode == after,
              "TPMODE %d -> %d (got %d, ended at %04Xh)" % (before, after, mode, pc))

    print("picopt, tape, sdcard: printing stays on the Pico")
    mode = 2
    for word in ("tpi:picopt", "tpi:tape", "tpi:sdcard"):
        pc, mode = switch(fdd, word, mode)
        check(pc == STORED, "%s handled by the ROM (TPMODE now %d)" % (word, mode))
    check(mode == 3, "TPMODE ends at 3, both switches on (got %d)" % mode)

    print("the other words, unchanged")
    for word, before, after in (("tpi:sdcard", 0, 2), ("tpi:sdcard", 1, 3),
                                ("tpi:picopt", 2, 3), ("tpi:ts2040", 3, 2),
                                ("TPI:TAPE", 3, 1)):
        pc, mode = switch(fdd, word, before)
        check(pc == STORED and mode == after, "%s: %d -> %d (got %d)" % (word, before, after, mode))
    pc, mode = switch(fdd, "tpi:tapex", 3)
    check(pc == SENT and mode == 3, "tpi:tapex: not a switch word, sent to the Pico, TPMODE kept")

    print("ROM 2.0, for contrast")
    pc, mode = switch(base, "tpi:tape", 3)
    check(pc == STORED and mode == 0, "tpi:tape from 3 -> 0, the printer switch cleared too (got %d)" % mode)

    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
