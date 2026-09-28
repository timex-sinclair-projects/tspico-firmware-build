"""Host-side test for the booted-slot guard in MEMDOCK / BLKRCV -- CPython, no Pico.

Hardware incident 2026-09-28: a test ROM booted from flash slot 4
(SAVE "tpi:boot" CODE 2,4), then romupdate.tap was told to write slot 4. It
sent tpi:memdock CODE 2,4 and tpi:blkrcv, the Z80 erased the ROM it was
running from, and both machines hung with slot 4 half-written.

Runs the REAL TS.tspico MEMDOCK and BLKRCV with a .ROM/.DCK "mounted" and
checks that writing the booted slot is refused with Report Q before the DOCK
moves or a byte is streamed, and that everything else still goes through:
another slot, the other memory, plain DOCK use with nothing mounted, and the
64K .DCK that spans pages n and n+1.

Run:  python3 src/test/boot_slot_guard_hosttest.py
"""

import os
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import process_cmd_hosttest as P                                # noqa: E402

results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg)


class MPFile:
    """A file with MicroPython's readinto(buf, nbytes)."""

    def __init__(self, f):
        self.f = f

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.f.close()

    def seek(self, n):
        self.f.seek(n)

    def readinto(self, buf, n=None):
        return self.f.readinto(memoryview(buf)[:n] if n is not None else buf)


class Rec:
    """A state machine that just records what it is given."""

    def __init__(self):
        self.puts = []

    def put(self, b):
        self.puts.append(b)


def pre_for(par1, par2):
    """A pre-header carrying CODE par1,par2 (PARAMS reads bytes 3..6)."""
    pre = bytearray(10)
    pre[3], pre[4] = par1 & 0xFF, par1 >> 8
    pre[5], pre[6] = par2 & 0xFF, par2 >> 8
    return pre


def setup(t, boot, dock, f_name, image):
    """boot / dock are (mem, page); mem 1 = SRAM, 2 = Flash."""
    sent = []
    t.TSP = types.SimpleNamespace(
        ROM_SM=boot[0] + dock[0] * 4, bank_sm=boot[1] + dock[1] * 16,
        f_name=f_name, dck_prev_mem=2, dck_prev_slot=0, VERBOSE=False)
    t.ROM, t.BANK, t.MQ = Rec(), Rec(), Rec()
    t.SEND_MSG = lambda msg, msg1, st, force=False: sent.append((msg, msg1, st, force))
    t.MQ_READY = lambda: None
    t.LOG = lambda *a: None
    t.BLINK_ERROR = lambda: None
    t.led = types.SimpleNamespace(value=lambda *a: None, toggle=lambda: None)
    t.os = types.SimpleNamespace(stat=lambda p: os.stat(image))
    t.open = lambda p, mode="r": MPFile(open(image, mode))
    return sent


def memdock(t, sent, par1, par2):
    del sent[:]
    t.MEMDOCK(pre_for(par1, par2), "xxxtpi:memdock")
    return sent[-1]


def blkrcv(t, sent):
    del sent[:]
    t.BLKRCV(pre_for(0, 0), "xxxtpi:blkrcv")
    return sent[-1] if sent else None


def test_rom(t, image):
    print(".ROM mounted, booted from Flash slot 4 (the 2026-09-28 incident)")
    sent = setup(t, (2, 4), (2, 0), "/sd/TAP/TEST.ROM", image)
    r = memdock(t, sent, 2, 4)
    check(r[2] == t._4_Q_Parameter, "tpi:memdock CODE 2,4: Report Q (%r)" % (r,))
    check("Flash slot 4" in r[0] and "running from it" in r[1] and r[3],
          "  says why, even with VERBOSE off")
    check(t.ROM.puts == [] and t.BANK.puts == [] and t.getDock() == (2, 0),
          "  DOCK left where it was")
    check(len(r[0]) <= 32 and all(len(s) <= 32 for s in r[1].split(chr(13))),
          "  every line fits 32 columns")

    r = memdock(t, sent, 2, 5)
    check(r[2] == t._1_OK and t.getDock() == (2, 5), "slot 5 instead: allowed")
    r = memdock(t, sent, 2, 3)
    check(r[2] == t._1_OK and t.getDock() == (2, 3), "slot 3: allowed (a ROM is one slot)")
    r = memdock(t, sent, 1, 4)
    check(r[2] == t._1_OK and t.getDock() == (1, 4), "SRAM slot 4: allowed (other memory)")

    print("  BLKRCV re-checks the DOCK itself")
    sent = setup(t, (2, 4), (2, 4), "/sd/TAP/TEST.ROM", image)   # DOCK got there anyway
    r = blkrcv(t, sent)
    check(r is not None and r[2] == t._4_Q_Parameter, "tpi:blkrcv with DOCK on the boot slot: Report Q")
    check(t.MQ.puts == [], "  nothing streamed, so the Z80 has nothing to erase/write with")

    sent = setup(t, (2, 4), (2, 6), "/sd/TAP/TEST.ROM", image)
    r = blkrcv(t, sent)
    check(r is None and t.MQ.puts[:1] == [t._1_OK], "tpi:blkrcv to slot 6: OK status")
    check(bytes(t.MQ.puts[1:]) == open(image, "rb").read(), "  and the whole image streamed")


def test_sram_boot(t, image):
    print("Booted from SRAM slot 2")
    sent = setup(t, (1, 2), (2, 0), "/sd/TAP/TEST.ROM", image)
    r = memdock(t, sent, 1, 2)
    check(r[2] == t._4_Q_Parameter and "SRAM slot 2" in r[0], "SRAM slot 2: Report Q")
    r = memdock(t, sent, 2, 2)
    check(r[2] == t._1_OK, "Flash slot 2: allowed")


def test_dck(t, image):
    print(".DCK mounted (64K: pages n and n+1), booted from Flash slot 5")
    sent = setup(t, (2, 5), (2, 0), "/sd/TAP/GAME.DCK", image)
    r = memdock(t, sent, 2, 4)
    check(r[2] == t._4_Q_Parameter and "slot 5" in r[0], "CODE 2,4 spans 4+5: Report Q")
    r = memdock(t, sent, 2, 6)
    check(r[2] == t._1_OK, "CODE 2,6 (6+7): allowed")
    sent = setup(t, (2, 4), (2, 0), "/sd/TAP/GAME.DCK", image)
    r = memdock(t, sent, 2, 4)
    check(r[2] == t._4_Q_Parameter, "booted from 4, CODE 2,4: Report Q")
    sent = setup(t, (2, 5), (2, 4), "/sd/TAP/GAME.DCK", image)
    r = blkrcv(t, sent)
    check(r is not None and r[2] == t._4_Q_Parameter and t.MQ.puts == [],
          "tpi:blkrcv with DOCK 2,4 while booted from 5: Report Q, nothing streamed")


def test_plain_dock(t, image):
    print("Nothing mounted (plain DOCK use, and romupdate's restore after tpi:close)")
    sent = setup(t, (2, 4), (2, 0), "", image)
    r = memdock(t, sent, 2, 4)
    check(r[2] == t._1_OK and t.getDock() == (2, 4), "tpi:dock CODE 2,4 while booted from 4: allowed")
    sent = setup(t, (2, 1), (2, 6), "", image)
    t.TSP.dck_prev_mem, t.TSP.dck_prev_slot = 2, 0
    r = memdock(t, sent, 0, 2)
    check(r[2] == t._1_OK and t.getDock() == (2, 0), "tpi:memdock CODE 0,2 restore to 2,0: allowed")
    sent = setup(t, (2, 4), (2, 4), "/sd/TAP/GAME.TAP", image)
    r = memdock(t, sent, 2, 4)
    check(r[2] == t._1_OK, "a .TAP mounted: not an update, allowed")


def main():
    P.install_fakes()
    ext = types.ModuleType("dev_extcmd")
    ext.EXT_SA_FUNCT = {}
    sys.modules["dev_extcmd"] = ext
    import TS.tspico as t
    t.TLM_ENABLED = False
    fd, image = tempfile.mkstemp(prefix="boot_guard.", suffix=".bin")
    with os.fdopen(fd, "wb") as f:
        f.write(bytes(range(256)) * 3 + b"tail")               # not a multiple of 256
    try:
        test_rom(t, image)
        test_sram_boot(t, image)
        test_dck(t, image)
        test_plain_dock(t, image)
    finally:
        os.remove(image)
    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
