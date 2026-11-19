#!/usr/bin/env python3
"""pico_host with one test-only command, to exercise the Megabank ROM's mover.

The firmware's RAM disk (src/TS/ramdisk.py; tspico.py's RD_* handlers: tpi:ropen,
tpi:rblk, tpi:ram, and r: names in CAT, ERASE, FORMAT, MOVE and COPY) uses
the mover's operations 1-7 as the file system needs them. This adds

  tpi:mbtest         ops 4-7 and the range and XOR checks; prints a verdict

to the firmware's EXT_SA_FUNCT, test-only, for the operations and refusals
the file system never provokes (an offset of 2000h, a run past the board, a
bad XOR). It writes pages 40-60 and the board's last page, so run it before
FORMAT "r:". Results go to $MEGABANK_HOST_LOG (JSON lines) for
tools/emu/megabank_smoke.py.

Run as pico_host.py is (the same arguments); megabank_smoke.py starts it
through TSPICO_HOST.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pico_host as ph                                 # noqa: E402

LOG = os.environ.get("MEGABANK_HOST_LOG", "/tmp/megabank_host.jsonl")
FN_MOVER = 0x89
OK = 1


def log(**kw):
    with open(LOG, "a") as f:
        f.write(json.dumps(kw) + "\n")


class Mover:
    """The firmware's side of response function 89h: one operation at a time."""

    def __init__(self, fw):
        self.fw = fw
        self.first = True

    def _send(self, data):
        out = self.fw.CmdOut()
        if self.first:
            out(FN_MOVER)
            self.first = False
        for b in data:
            out(b)
        out.send()                     # READY once the first bytes are queued

    def _rx(self, n=1):
        return bytes(self.fw.CMD_KEY() for _ in range(n))

    @staticmethod
    def _w(*vals):
        return b"".join(bytes([v & 0xFF, v >> 8 & 0xFF]) for v in vals)

    def copy_in(self, addr, n, page, off):           # op 1: 2068 -> board
        self._send(b"\x01" + self._w(addr, n, page, off))
        return self._rx()[0]

    def copy_out(self, addr, n, page, off):          # op 2: board -> 2068
        self._send(b"\x02" + self._w(addr, n, page, off))
        return self._rx()[0]

    def compare(self, addr, n, page, off):           # op 3
        self._send(b"\x03" + self._w(addr, n, page, off))
        return self._rx()[0]

    def read(self, n, page, off):                    # op 4: board -> Pico
        self._send(b"\x04" + self._w(n, page, off))
        data = self._rx(n)
        x, st = self._rx(2)
        return data, x, st

    def write(self, data, page, off, bad_xor=False):  # op 5: Pico -> board
        x = 0
        for b in data:
            x ^= b
        self._send(b"\x05" + self._w(len(data), page, off) + bytes(data) + bytes([x ^ (1 if bad_xor else 0)]))
        return self._rx()[0]

    def move(self, n, page, off, page2, off2):       # op 6
        self._send(b"\x06" + self._w(n, page, off, page2, off2))
        return self._rx()[0]

    def info(self):                                  # op 7
        self._send(b"\x07")
        return self._rx(5)

    def done(self, answer):
        """Op 0, then the command's answer: a status, or a response function."""
        self._send(b"\x00" + bytes(answer))
        self.fw.CMD_DRAIN()


class MbTest:
    def __init__(self, fw):
        self.fw = fw

    def mbtest(self, MQ, TSP, pre, cmd):
        """Ops 4-7 and the checks, then the verdict printed with function 81h
        after op 0 (which also tests that the answer after op 0 can be one)."""
        fw = self.fw
        mv = Mover(fw)
        res = {}
        res["info"] = list(mv.info())
        pat = bytes((i * 7 + (i >> 8)) & 0xFF for i in range(10000))
        res["w1"] = mv.write(pat, 40, 5000)                # runs over into page 41
        data, x, st = mv.read(10000, 40, 5000)
        xx = 0
        for b in data:
            xx ^= b
        res["r1"] = [st, data == pat, x == xx]
        res["mv"] = mv.move(10000, 40, 5000, 50, 8000)     # page to page, both over a boundary
        data2, _, st2 = mv.read(10000, 50, 8000)
        res["r2"] = [st2, data2 == pat]
        res["range"] = mv.write(b"x", 0xFFFF, 0)           # past the board: 4, nothing done
        res["range2"] = mv.read(1, 0, 0x2000)[2]           # an offset of 2000h: 4
        res["last"] = mv.write(b"end", 511, 8189)          # the last 3 bytes of a 4 MB board
        res["over"] = mv.write(b"xyzw", 511, 8189)         # one past it: 4
        res["xor"] = mv.write(b"abc", 60, 0, bad_xor=True)  # 5
        ok = (res["info"][0] == 1 and res["w1"] == 1 and res["r1"] == [1, True, True]
              and res["mv"] == 1 and res["r2"] == [1, True] and res["range"] == 4
              and res["range2"] == 4 and res["last"] == 1 and res["over"] == 4 and res["xor"] == 5)
        res["ok"] = ok
        log(cmd="mbtest", **res)
        text = ("mbtest ok" if ok else "mbtest FAILED").encode()
        mv.done([0x81, OK] + list(text) + [0])        # PRINT STRING, status 1


def install(fs, _inst=ph.install_firmware):
    """The firmware takes its external table from dev_extcmd when that
    imports (src/ has the copy) and from TS.extcmd otherwise, at the start of
    its main loop; so the commands go into whichever table PROCESS_CMD is
    handed."""
    fw = _inst(fs)
    ours = {"TPI:MBTEST": MbTest(fw).mbtest}
    process = fw.PROCESS_CMD

    def PROCESS_CMD(pre, SA_funct, EXT_SA_FUNCT):
        EXT_SA_FUNCT.update(ours)
        return process(pre, SA_funct, EXT_SA_FUNCT)
    fw.PROCESS_CMD = PROCESS_CMD
    return fw


if __name__ == "__main__":
    ph.install_firmware = install
    ph.main()
