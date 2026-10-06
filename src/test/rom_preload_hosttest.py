"""ROM 2.1's PRELOAD (#179) in the Z80 interpreter.

SEND_FOPEN and CH_SEND, the fdd module's hand-built exchanges, read the
pre-load status through PRELOAD (EXROM 3778h): a 0 -- no Pico, or a link
out of step -- is Report J at once, as the ROM's own exchanges give it
(1A35h); anything else goes on, as it always did. (Not the ROM's whole
rule: the only other value the firmware stages is a refused header LOAD's
error, meant for the LOAD's retry.) This runs PRELOAD from the committed
slot-1 image against a Pico that answers 0, 1 or 2 on port 0Eh, and checks
that both call sites call it.

Uses src/rom/TSPICO-21.ROM (CI checks it is what tools/build-rom.py builds).
Run:
    python3 src/test/rom_preload_hosttest.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

from z80core import Z80                                          # noqa: E402

ROM21 = os.path.join(REPO, "src", "rom", "TSPICO-21.ROM")
PRELOAD = 0x3778
CALLS = {"SEND_FOPEN": 0x32DE, "CH_SEND": 0x369F}
DONE = 0xFF00
RST8 = 0x0008

results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg)


def run(exrom, answer):
    """CALL PRELOAD with the Pico's TX holding `answer`; (where, A, report)."""
    mem = bytearray(65536)
    mem[0:0x4000] = exrom

    def port_in(port):
        return answer if port & 0xFF == 0x0E else 0xFF

    cpu = Z80(lambda a: mem[a], lambda a, v: mem.__setitem__(a, v) if a >= 0x4000 else None,
              port_in, lambda port, v: None)
    cpu.sp = 0xFE00
    cpu.push(DONE)
    cpu.pc = PRELOAD
    while cpu.pc not in (DONE, RST8) and cpu.t < 1_000_000:
        cpu.step()
    if cpu.pc == RST8:
        return "rst8", cpu.a, mem[cpu.pop()]      # the byte after RST 8: the report
    return ("ret" if cpu.pc == DONE else "lost"), cpu.a, None


def main():
    exrom = open(ROM21, "rb").read()[0x4000:]
    check(exrom[PRELOAD:PRELOAD + 5] == bytes([0xCD, 0x48, 0x18, 0xC0, 0xC3]),
          "PRELOAD at 3778h: CALL BIOS_RX_A / RET NZ / JP WF_FAIL")
    for name, at in CALLS.items():
        check(exrom[at:at + 3] == bytes([0xCD, PRELOAD & 0xFF, PRELOAD >> 8]),
              "%s calls it (%04Xh)" % (name, at))
    where, a, report = run(exrom, 0x00)
    check(where == "rst8" and report == 0x12,
          "pre-load 00h (no Pico): RST 8 with 12h, Report J (%s, %r)" % (where, report))
    where, a, report = run(exrom, 0x01)
    check(where == "ret" and a == 0x01, "pre-load 01h: returns, A = 01h (%s, A=%02X)" % (where, a))
    where, a, report = run(exrom, 0x02)
    check(where == "ret" and a == 0x02,
          "pre-load 02h (a refused LOAD's, meant for its retry): returns, as before (%s)" % where)
    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
