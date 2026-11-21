"""Host-side test for the Megabank RAM disk's commands in TS/tspico.py (RD_*).

CPython, no Pico. The REAL handlers -- tpi:ropen, tpi:rblk, tpi:ram, and the
disk keywords with r: names (DIR, DISK_ERASE, DISK_FORMAT, DISK_REN,
DISK_COPY) -- with the mover replaced by ramdisk_hosttest.py's model board,
the card by a temporary directory (catalog_hosttest.HostOS) and the answers
recorded. The bytes on the wire are tools/emu/megabank_smoke.py's (ZEsarUX);
this pins the handlers' logic, in CI.

What it pins down: r: is refused on a ROM before 2.5 (J, and no 89h); every
answer comes after op 0 (the mover's end), never before; SAVE / LOAD /
VERIFY through tpi:ropen + tpi:rblk, with F for a missing file, R for a
second header and for a VERIFY that differs; CAT, MOVE, ERASE (one, and a
pattern asked twice), FORMAT (asked twice over files), COPY between the card
and the RAM disk both ways and on the board; tpi:ram, backup and restore;
which commands need the card (RD_ONLY).

Run:  python3 src/test/rd_cmds_hosttest.py
"""

import os
import shutil
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


def main():
    P.install_fakes()
    ext = types.ModuleType("dev_extcmd")
    ext.EXT_SA_FUNCT = {}
    sys.modules["dev_extcmd"] = ext
    import TS.tspico as t
    import ramdisk_hosttest as RH
    import catalog_hosttest as CH
    t.TLM_ENABLED = False

    root = tempfile.mkdtemp(prefix="rd_hosttest.")
    try:
        run_tests(t, RH, CH, root)
    finally:
        shutil.rmtree(root)
    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


def run_tests(t, RH, CH, root):
    hos = CH.HostOS(root)
    ev = []                                         # answers and the mover's end, in order
    board = RH.Board(banks=8)                       # 512K: 64 pages

    class FakeMover(RH.Mover):
        def __init__(self, err):
            RH.Mover.__init__(self, board)
            self.n0 = len(board.ops)

        def end(self):
            if len(board.ops) > self.n0:
                ev.append(("END",))

    t.RD_MOVER = FakeMover
    clock = P.FakeTime()
    t.time = clock
    t.os = hos
    t.open = lambda p, mode="r": open(hos.real(p), mode)
    # The SD card as the board has it: mounted only inside SD_CALL. REFRESH_IF
    # (os.chdir and DIR_FILES on the card) fails, as on the board, when it
    # isn't: the J after a tpi:ram backup into the current folder.
    sd = {"on": False}
    t.ACTIVATE_SD = lambda *a, **k: sd.__setitem__("on", True)
    t.DEACTIVATE_SD = lambda *a, **k: sd.__setitem__("on", False)
    t.ACTIVATE_MQ = lambda *a, **k: None

    def refresh_if(*dirs):
        if not sd["on"] and any(d.upper() == t.TSP.cur_path.upper() for d in dirs):
            raise OSError(2, "ENOENT: REFRESH_IF with the card unmounted")
    t.REFRESH_IF = refresh_if
    # r: answers are CH_REPLY's, READY without IDLE (the next tpi:rblk
    # follows at once); SEND_STATUS would say IDLE too, so it is a failure.
    t.CH_REPLY = lambda st: ev.append(("ST", st))
    t.SEND_STATUS = lambda st: ev.append(("SEND_STATUS, not CH_REPLY", st))
    t.SEND_MSG = lambda msg, msg1, st, force=False: ev.append(("MSG", msg, st, force))
    t.SEND_MSG2 = lambda msg, st, exp=True, colour=False: ev.append(("MSG2", msg, st))
    t.led = types.SimpleNamespace(value=lambda *a: None)
    t.LOG = lambda *a: None
    t.TSP = types.SimpleNamespace(cur_path="/sd/TAP", f_name="", offset_tbl=[], tap_idx=0,
                                  VERBOSE=False, LOG_LEVEL=2, sd_present=True)
    t.RD = None

    def pre(p1=0, p2=0):
        b = bytearray(10)
        b[3], b[4], b[5], b[6] = p1 & 0xFF, p1 >> 8, p2 & 0xFF, p2 >> 8
        return b

    def cmd(handler, text, p1=0, p2=0):
        del ev[:]
        handler(pre(p1, p2), "D.." + text)
        return ev[-1] if ev else None

    def rblk(kind, flag, addr, n):
        return cmd(t.RD_RBLK, "tpi:rblk %02x%02x%02x%02x" % (addr & 0xFF, addr >> 8, n & 0xFF, n >> 8),
                   kind, flag)

    def ended():
        """The mover's op 0 came before the answer, and only once."""
        return [e[0] for e in ev].count("END") == 1 and ev[-2] == ("END",)

    print("Not the Megabank ROM")
    t.rom_id = 0x24
    n = len(board.ops)
    r = cmd(t.RD_ROPEN, "tpi:ropen prog", 0)
    check(r == ("ST", 10) and len(board.ops) == n, "tpi:ropen on ROM 2.4: J, no mover")
    r = cmd(t.DIR, "tpi:dir r:")
    check(r[0] == "MSG" and r[2] == 10 and "Megabank ROM" in r[1] and len(board.ops) == n,
          "CAT \"r:\" on ROM 2.4: J, no 89h")
    t.rom_id = 0xFF
    r = cmd(t.DISK_FORMAT, "tpi:format r:")
    check(r[2] == 10, "and on a ROM that sends no version")

    t.rom_id = 0x25
    print("No RAM disk yet")
    r = cmd(t.DIR, "tpi:dir r:")
    check(r[0] == "MSG" and r[2] == 10 and "No RAM disk" in r[1] and r[3] and ended(),
          "CAT \"r:\": J, 'No RAM disk', shown; op 0 first")
    r = cmd(t.RD_RAM, "tpi:ram")
    check(r[0] == "MSG2" and "Megabank: 512K" in r[1] and "No RAM disk" in r[1] and ended(),
          "tpi:ram: the board, no RAM disk")
    r = cmd(t.DISK_FORMAT, "tpi:format r:")
    check(r[0] == "MSG" and r[2] == 1 and "256K" in r[1] and ended(), "FORMAT \"r:\": half the board")

    print("SAVE, LOAD, VERIFY")
    hdr = bytes([3]) + b"prog      " + bytes([0xB8, 0x0B, 0x00, 0x80, 0, 0])
    data = bytes((i * 11 + 3) & 0xFF for i in range(3000))
    board.z80[0x6000:0x6011] = hdr
    board.z80[0x8000:0x8000 + 3000] = data
    check(cmd(t.RD_ROPEN, "tpi:ropen prog", 0) == ("ST", 1), "tpi:ropen prog (SAVE)")
    check(rblk(0, 0, 0x6000, 17) == ("ST", 1) and ended(), "the header block")
    check(rblk(0, 0xFF, 0x8000, 3000) == ("ST", 1) and ended(), "the data block")
    check(t.RD_OPEN is None, "RD_OPEN cleared after the data")
    board.z80[0x7000:0x7011] = bytes(17)
    board.z80[0x9000:0x9000 + 3000] = bytes(3000)
    cmd(t.RD_ROPEN, "tpi:ropen prog", 1)
    check(rblk(1, 0, 0x7000, 17) == ("ST", 1) and bytes(board.z80[0x7000:0x7011]) == hdr,
          "LOAD: the header comes from the directory entry")
    check(rblk(1, 0xFF, 0x9000, 3000) == ("ST", 1) and bytes(board.z80[0x9000:0x9000 + 3000]) == data,
          "LOAD: the data")
    cmd(t.RD_ROPEN, "tpi:ropen prog", 1)
    rblk(1, 0, 0x7000, 17)
    check(rblk(1, 0, 0x7000, 17) == ("ST", 2), "a second header in one statement: R")
    cmd(t.RD_ROPEN, "tpi:ropen prog", 2)
    rblk(1, 0, 0x7000, 17)
    check(rblk(2, 0xFF, 0x8000, 3000) == ("ST", 1), "VERIFY: the same")
    board.z80[0x8000 + 100] ^= 1
    cmd(t.RD_ROPEN, "tpi:ropen prog", 2)
    rblk(1, 0, 0x7000, 17)
    check(rblk(2, 0xFF, 0x8000, 3000) == ("ST", 2), "VERIFY after a change: R")
    board.z80[0x8000 + 100] ^= 1
    check(cmd(t.RD_ROPEN, "tpi:ropen nofile", 1) == ("ST", 1) and rblk(1, 0, 0x7000, 17) == ("ST", 3),
          "LOAD of a missing name: F at the first block")
    check(cmd(t.RD_ROPEN, "tpi:ropen elevenchars", 0) == ("ST", 3), "an 11-character name: F")
    check(rblk(1, 0xFF, 0x9000, 3000) == ("ST", 3), "tpi:rblk with no tpi:ropen: F")

    print("CAT, MOVE, COPY, ERASE")
    r = cmd(t.DIR, "tpi:dir r:")
    check(r[0] == "MSG2" and "1 file," in r[1] and "prog       Bytes       3000" in r[1] and ended(),
          "CAT \"r:\"")
    r = cmd(t.DISK_REN, "tpi:ren r:prog|r:code")
    check(r[2] == 1 and ended(), "MOVE \"r:prog\" TO \"r:code\"")
    r = cmd(t.DISK_REN, "tpi:ren r:code|card")
    check(r[2] == 4 and "COPY" in r[1], "MOVE between the RAM disk and the card: Q")
    r = cmd(t.DISK_COPY, "tpi:copy r:code|saved")
    raw = open(os.path.join(root, "saved.tap"), "rb").read() if os.path.exists(os.path.join(root, "saved.tap")) else b""
    check(r[2] == 1 and ended() and raw[:3] == b"\x13\x00\x00" and raw[4:14] == b"code      "
          and raw[24:3024] == data, "COPY \"r:code\" TO \"saved\": saved.tap, header named code")
    r = cmd(t.DISK_COPY, "tpi:copy r:code|saved")
    check(r[2] == 3 and "Exists" in r[1] and ended(), "again: the card file exists, F")
    r = cmd(t.DISK_COPY, "tpi:copy saved|r:")
    check(r[2] == 1 and "r:code" in r[1], "COPY \"saved\" TO \"r:\": the header's name (code)")
    r = cmd(t.DISK_COPY, "tpi:copy saved.tap|r:back")
    check(r[2] == 1 and ended(), "COPY \"saved.tap\" TO \"r:back\"")
    r = cmd(t.DISK_COPY, "tpi:copy r:back|r:back2")
    check(r[2] == 1 and ended(), "COPY on the board")
    r = cmd(t.DISK_COPY, "tpi:copy nothere|r:x")
    check(r[2] == 3 and not any(e[0] == "END" for e in ev), "COPY of a missing card file: F, before any 89h")
    cmd(t.RD_ROPEN, "tpi:ropen back2", 1)
    rblk(1, 0, 0x7000, 17)
    board.z80[0x9000:0x9000 + 3000] = bytes(3000)
    check(rblk(1, 0xFF, 0x9000, 3000) == ("ST", 1) and bytes(board.z80[0x9000:0x9000 + 3000]) == data,
          "the copy of a copy loads")
    r = cmd(t.DISK_ERASE, "tpi:erase r:back2")
    check(r[2] == 1 and ended(), "ERASE \"r:back2\"")
    r = cmd(t.DISK_ERASE, "tpi:erase r:b*")
    check(r[2] == 1 and r[3] and "ERASE again" in r[1] and "back" in r[1], "ERASE \"r:b*\": says what, shown")
    r = cmd(t.DISK_ERASE, "tpi:erase r:b*")
    check(r[2] == 1 and "Erased 1 file" in r[1], "the same again: done")
    r = cmd(t.DISK_ERASE, "tpi:erase r:zz*")
    check(r[2] == 3, "a pattern with no match: F")

    print("FORMAT over files, backup, restore")
    r = cmd(t.DISK_FORMAT, "tpi:format r:64")
    check(r[2] == 1 and r[3] and "FORMAT again" in r[1], "FORMAT over files: asks to be repeated")
    r = cmd(t.DISK_FORMAT, "tpi:format r:128")
    r = cmd(t.DISK_FORMAT, "tpi:format r:64")
    check(r[2] == 1 and r[3] and "FORMAT again" in r[1], "another FORMAT in between: asks again")
    r = cmd(t.DIR, "tpi:dir r:")
    r = cmd(t.DISK_FORMAT, "tpi:format r:64")
    check(r[2] == 1 and "64K" in r[1], "repeated straight away: done")
    cmd(t.RD_ROPEN, "tpi:ropen gone", 0)
    rblk(0, 0, 0x6000, 17)
    rblk(0, 0xFF, 0x8000, 10)
    r = cmd(t.DISK_FORMAT, "tpi:format r:64")
    clock.t += 61_000
    r = cmd(t.DISK_FORMAT, "tpi:format r:64")
    check("FORMAT again" in r[1], "repeated after a minute: asks again")
    cmd(t.DISK_FORMAT, "tpi:format r:64")
    cmd(t.RD_ROPEN, "tpi:ropen keep", 0)
    board.z80[0x6000:0x6011] = bytes([3]) + b"keep      " + hdr[11:]
    rblk(0, 0, 0x6000, 17)
    rblk(0, 0xFF, 0x8000, 3000)
    r = cmd(t.RD_RAM, "tpi:ram backup img")
    img = os.path.join(root, "img.rdi")
    check(r[2] == 1 and os.path.exists(img) and os.path.getsize(img) == 65536 and ended(),
          "tpi:ram backup img: img.rdi, 64K")
    r = cmd(t.RD_RAM, "tpi:ram backup img")
    check(r[2] == 3, "backup over an existing file: F")
    cmd(t.DISK_ERASE, "tpi:erase r:keep")
    r = cmd(t.RD_RAM, "tpi:ram restore img")
    check(r[2] == 1 and "1 files" in r[1] and ended(), "restore onto an empty RAM disk")
    cmd(t.RD_ROPEN, "tpi:ropen keep", 1)
    rblk(1, 0, 0x7000, 17)
    board.z80[0x9000:0x9000 + 3000] = bytes(3000)
    check(rblk(1, 0xFF, 0x9000, 3000) == ("ST", 1) and bytes(board.z80[0x9000:0x9000 + 3000]) == data,
          "the erased file is back")
    big = RH.Board(banks=16)                         # the image onto a bigger board
    big.mem[:] = bytes(len(big.mem))
    board_saved = board.mem
    board.mem = big.mem
    board.size = 16
    t.RD = None
    r = cmd(t.RD_RAM, "tpi:ram restore img")
    check(r[2] == 1 and t.RD.first == 120 and t.RD.last == 127, "restored onto a 1 MB board: at its top")
    cmd(t.RD_ROPEN, "tpi:ropen keep", 1)
    rblk(1, 0, 0x7000, 17)
    board.z80[0x9000:0x9000 + 3000] = bytes(3000)
    check(rblk(1, 0xFF, 0x9000, 3000) == ("ST", 1) and bytes(board.z80[0x9000:0x9000 + 3000]) == data,
          "and loads there")
    board.mem, board.size = board_saved, 8
    t.RD = None
    r = cmd(t.RD_RAM, "tpi:ram restore nothere")
    check(r[2] == 3, "restore of a missing image: F")
    r = cmd(t.RD_RAM, "tpi:ram alloc 4")
    check(r[2] == 4 and not ev[:-1], "tpi:ram alloc: not yet (Q, no 89h)")

    print("Write-protect")
    board.wp = True
    cmd(t.RD_ROPEN, "tpi:ropen w", 0)
    check(rblk(0, 0, 0x6000, 17) == ("ST", 10), "SAVE with the switch on: J")
    r = cmd(t.DISK_ERASE, "tpi:erase r:keep")
    check(r[2] == 10 and "write-protected" in r[1], "ERASE: J, says why")
    board.wp = False

    print("Which commands need the card")
    O = t.RD_ONLY
    check(O("TPI:DIR", "TPI:DIR R:") and O("TPI:ERASE", "TPI:ERASE R:X") and O("TPI:FORMAT", "TPI:FORMAT R:"),
          "CAT, ERASE, FORMAT with r:: no card")
    check(O("TPI:COPY", "TPI:COPY R:A|R:B") and not O("TPI:COPY", "TPI:COPY A|R:B"),
          "COPY: no card only when both sides are r:")
    check(O("TPI:RAM", "TPI:RAM") and not O("TPI:RAM", "TPI:RAM BACKUP X") and O("TPI:ROPEN", "TPI:ROPEN X"),
          "tpi:ram: the card only for backup and restore")
    check(not O("TPI:DIR", "TPI:DIR") and not O("TPI:DIR", "TPI:DIR GAMES"), "CAT of the card: the card")
    check(not t.SD_NEEDED(0, "TPI:DIR", "TPI:DIR R:", {"TPI:DIR": 1})
          and t.SD_NEEDED(0, "TPI:DIR", "TPI:DIR GAMES", {"TPI:DIR": 1}), "SD_NEEDED asks RD_ONLY")


if __name__ == "__main__":
    sys.exit(main())
