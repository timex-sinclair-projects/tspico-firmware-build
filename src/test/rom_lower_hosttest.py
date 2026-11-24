"""The lower-screen fixes of #446 and #447 in the Z80 interpreter.

#446: WAIT-KEY (HOME 11CFh) sets TV_FLAG bit 3 before every character the
editor takes, and only the keyboard's input routine cleared it (ED-COPY).
After INPUT # from an f: or r: stream the bit stayed set, and the next
"scroll?" copied the edit line to the lower screen ("scroll?RUN") and left
garbage after it. CH_IN and RCH_IN now clear it.

#447: function 88h (LOWER_LOOP), the "Replace NAME? (Y/N)" question of
SAVE "f:...", left the question on the lower screen; SAVE's "Start tape"
line then made three lines and scrolled the picture. LOWER_LOOP now ends
with HOME's CLS-LOWER (EXROM 22E7h's stub), keeping the loop's AF.

Runs CH_IN and LOWER_LOOP from both committed ROMs (2.4 and the slot-1
2.5; CI checks each is what tools/build-rom.py builds), with LOWER_LOOP's
callees stubbed, and checks RCH_IN's first instructions in 2.5.
The whole behavior, on a 2068 with the real firmware: tools/emu/lower_emu.py.
Run:
    python3 src/test/rom_lower_hosttest.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

from z80core import Z80                                          # noqa: E402

ROMS = {"2.4": os.path.join(REPO, "src", "rom", "TSPICO-24.ROM"),
        "2.5": os.path.join(REPO, "src", "rom", "TSPICO-25.ROM")}
CH_IN, LOWER_LOOP, RCH_IN = 0x3599, 0x334F, 0x2AFC
READ_STATUS_BYTE, OPEN_STREAM, LOOP_BODY, CLS_LOWER_X = 0x02B9, 0x0426, 0x21E6, 0x22E7
TV_FLAG, CURCHL = 0x5C3C, 0x5C51
R_INN, R_INP, R_INBUF = 8, 9, 11 + 64
REC, MARK, DONE = 0x7000, 0xF000, 0xFF00

results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg)


def machine(exrom):
    mem = bytearray(65536)
    mem[0:0x4000] = exrom
    cpu = Z80(lambda a: mem[a], lambda a, v: mem.__setitem__(a, v) if a >= 0x4000 else None,
              lambda port: 0xFF, lambda port, v: None)
    cpu.sp = 0xFE00
    cpu.push(DONE)
    return cpu, mem


def go(cpu):
    while cpu.pc != DONE and cpu.t < 200_000:
        cpu.step()
    return cpu.pc == DONE


def ch_in(exrom):
    """CH_IN with a byte waiting in the record and TV_FLAG 2Fh (bit 3 set)."""
    cpu, mem = machine(exrom)
    mem[CURCHL:CURCHL + 2] = REC.to_bytes(2, "little")
    mem[REC + 4] = ord("F")
    mem[REC + R_INN], mem[REC + R_INP] = 3, 1
    mem[REC + R_INBUF + 1] = ord("X")
    mem[TV_FLAG] = 0x2F
    cpu.iy = 0x1234                    # the bank call clobbers IY: CH_IN sets it
    cpu.pc = CH_IN
    ok = go(cpu)
    return ok, cpu.cf, cpu.a, mem[TV_FLAG], mem[REC + R_INP]


def lower_loop(exrom, carry):
    """LOWER_LOOP with its callees stubbed: the loop returns A = 05h and the
    given carry; CLS-LOWER's stub marks MARK and clobbers AF."""
    ex = bytearray(exrom)
    ex[READ_STATUS_BYTE:READ_STATUS_BYTE + 3] = bytes([0x3E, 0x01, 0xC9])   # LD A,1 / RET
    ex[OPEN_STREAM] = 0xC9
    ex[LOOP_BODY:LOOP_BODY + 4] = bytes([0x3E, 0x05, 0x37 if carry else 0xB7, 0xC9])
    ex[CLS_LOWER_X:CLS_LOWER_X + 5] = bytes([0x32, MARK & 0xFF, MARK >> 8, 0xAF, 0xC9])
    cpu, mem = machine(bytes(ex))
    mem[MARK] = 0
    cpu.pc = LOWER_LOOP
    ok = go(cpu)
    return ok, mem[MARK] == 0x05, cpu.a, cpu.cf


def main():
    for ver, path in ROMS.items():
        exrom = open(path, "rb").read()[0x4000:]
        print("ROM %s" % ver)
        check(exrom[CH_IN:CH_IN + 8] == bytes.fromhex("fd213a5cfdcb029e"),
              "CH_IN at %04Xh: LD IY,5C3Ah / RES 3,(IY+2)" % CH_IN)
        ok, c, a, tv, inp = ch_in(exrom)
        check(ok and c and a == ord("X") and inp == 2,
              "CH_IN hands out the waiting byte (carry, A = 'X', R_INP 2)")
        check(tv == 0x27, "TV_FLAG bit 3 cleared, the other bits kept (2Fh -> %02Xh)" % tv)
        check(exrom[CLS_LOWER_X:CLS_LOWER_X + 9] == bytes.fromhex("dde5d921a908c3dd03"),
              "22E7h: PUSH IX / EXX / LD HL,08A9h / JP CALL_HOME (CLS-LOWER)")
        for carry in (False, True):
            ok, cls, a, c = lower_loop(exrom, carry)
            check(ok and cls, "LOWER_LOOP calls CLS-LOWER after the loop (carry %d)" % carry)
            check(a == 0x05 and c == carry,
                  "  and returns the loop's AF (A = %02Xh, carry %d)" % (a, c))
        if ver == "2.5":
            check(exrom[RCH_IN:RCH_IN + 8] == bytes.fromhex("fd213a5cfdcb029e"),
                  "RCH_IN at %04Xh: LD IY,5C3Ah / RES 3,(IY+2)" % RCH_IN)
    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
