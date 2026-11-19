"""The r: channels' per-character code (rchan.asm), in the Z80 interpreter.

src/rom/TSPICO-MB.ROM's MB_OUT and MB_IN (what HOME's 14A0h and 14A9h stubs
reach for an 'R' record) run here against the firmware's own ramdisk.py, on
one model board: the firmware opens the stream (Disk.open_stream, as
tpi:rchopen does) and the record is built from the slot's block as RCH_OPEN
builds it; then every PRINT # and INPUT # character goes through the ROM,
which reads and writes the board through a window chunk. CH_SEND and
CH_STATUS are the TS-Pico: tpi:rchgrow runs Disk.grow and copies the block
back (op 2). The board model is rom_bankapi_hosttest's (the HSR rule:
a write to a board-owned chunk with its F4h bit clear is a fault, and so is
an OUT to F4h or FCh with interrupts on). RST 8 stops a run with its report.

    text out    controls dropped (16-21 and their parameter, 22 and two),
                comma to the next 16-column stop, keywords kept, CR kept
    binary out  every byte, but 23 is TAB
    TAB         a stream's byte n; a gap padded by the next write
    growth      past the extent: tpi:rchgrow, the bytes where Disk says
    write-back  the length and position in the slot at a CR and every
                256 bytes; the write-protect switch on: J
    records     a CR pads the record and isn't stored; too long: Q and back to
                its start; TAB n; a blank record; TAB 0 then a read: the count
    text in     LF and CRLF as CR, controls dropped, a last line ends with CR,
                then 8 End of file (NC NZ)
    modes       r drops output; w is Q on a read
    the window  never the record's chunk or the stack's; a program's own page
                in chunk 4 survives; the HSR rule holds throughout

With sjasmplus on the PATH the module is assembled again and the addresses
below are checked against it (CI has none: the table is the contract).

Run:
    python3 src/test/rom_rchan_hosttest.py
"""

import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "src"))

from rom_bankapi_hosttest import Machine, w                     # noqa: E402
from TS import ramdisk as rd                                    # noqa: E402

ROM = os.path.join(REPO, "src", "rom", "TSPICO-MB.ROM")
ASM = os.path.join(REPO, "src", "rom", "fdd", "fddcmd.asm")

SYM = {"MB_OUT": 0x2400, "MB_IN": 0x240E, "RCH_ENDREC": 0x2785, "RCH_WB": 0x28CA,
       "CH_SEND": 0x3642, "CH_STATUS": 0x3633, "RCH_END": 0x2AE7}
CURCHL, STRMS, CHANS = 0x5C51, 0x5C10, 0x5C4F
REC = 0x7100                     # the record, in chunk 3
DONE = 0xFFF0
SP = 0x6100
results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg)


def check_syms():
    if shutil.which("sjasmplus") is None:
        print("  (no sjasmplus: the address table is taken as it is)")
        return
    d = tempfile.mkdtemp()
    try:
        subprocess.run(["sjasmplus", "--nologo", "-DMEGABANK", "--sym=f.sym", ASM], cwd=d,
                       capture_output=True, check=True)
        syms = {}
        for line in open(os.path.join(d, "f.sym")):
            if ":" in line and "EQU" in line:
                n, _, r = line.partition(":")
                syms[n.strip()] = int(r.split()[-1], 16)
        bad = [k for k, v in SYM.items() if syms.get(k) != v]
        check(not bad, "the address table matches the assembled module %s" % (bad or ""))
        rom = open(ROM, "rb").read()
        rch = open(os.path.join(d, "rchan.bin"), "rb").read()
        check(rom[0x4000 + 0x2400:0x4000 + 0x2400 + len(rch)] == rch,
              "TSPICO-MB.ROM holds the assembled rchan.asm at EXROM 2400h")
    finally:
        shutil.rmtree(d, ignore_errors=True)


class Mover:
    """The mover's operations, over the Machine's board and RAM."""

    def __init__(self, m):
        self.m = m

    def _a(self, n, page, off):
        assert off < 0x2000 and (page * 8192 + off + n) <= len(self.m.board)
        return page * 8192 + off

    def info(self):
        return (1, self.m.base, self.m.size, self.m.status, 3)

    def read(self, n, page, off):
        a = self._a(n, page, off)
        return bytes(self.m.board[a:a + n])

    def write(self, data, page, off):
        a = self._a(len(data), page, off)
        self.m.board[a:a + len(data)] = data

    def move(self, n, page, off, page2, off2):
        a, d = self._a(n, page, off), self._a(n, page2, off2)
        self.m.board[d:d + n] = self.m.board[a:a + n]

    def copy_out(self, addr, n, page, off):
        a = self._a(n, page, off)
        self.m.ram[addr:addr + n] = self.m.board[a:a + n]


class RMachine(Machine):
    """The EXROM in chunks 0-1 (as when the module runs), the firmware behind
    CH_SEND / CH_STATUS, RST 8 caught."""

    def __init__(self, rom, size=8):
        super().__init__(rom, base=1, size=size)
        self.hsr, self.dec = 0x03, 0x80
        self.status = 0
        self.disk = rd.Disk()
        self.disk.mv = Mover(self)
        self.disk.mount(need=False)
        self.disk.format(32)
        self.disk.mount()
        self.sent = []
        self.cpu.fetch_hook = None
        self.ram[CHANS:CHANS + 2] = w(0x7000)

    def port_in(self, port):
        if port & 0xFF == 0xFC and self.sel == 0x11:
            return self.status
        return super().port_in(port)

    def run(self, addr, **regs):
        cpu = self.cpu
        for k, v in regs.items():
            setattr(cpu, k, v)
        cpu.iff = False
        cpu.sp = SP
        cpu.push(DONE)
        cpu.pc = addr
        self.report = None
        n = 0
        while cpu.pc != DONE:
            pc = cpu.pc
            if pc == 0x0008:                         # RST 8: the report
                self.report = self.read(cpu.r16(cpu.sp))
                return self
            if pc == SYM["CH_SEND"]:
                prefix = bytearray()
                a = cpu.h << 8 | cpu.l
                while self.read(a):
                    prefix.append(self.read(a))
                    a += 1
                pay = bytes(self.read(cpu.ix + 11 + i) for i in range(cpu.b))
                self.sent.append((prefix.decode(), cpu.a, cpu.c, pay))
                cpu.pc = cpu.pop()
                continue
            if pc == SYM["CH_STATUS"]:
                word, stream, _, pay = self.sent[-1]
                try:
                    if word == "tpi:rchgrow ":
                        self.disk.mount()
                        self.disk.grow(stream, pay[4] | pay[5] << 8)
                        p, o = self.disk.block_loc(stream)
                        self.disk.mv.copy_out(pay[2] | pay[3] << 8, rd.BLOCK_LEN, p, o)
                    cpu.f &= ~1
                except rd.RdError as e:
                    self.report = {rd.Q_PARAM: 0x19, rd.J_IO: 0x12, rd.F_NAME: 0x0E}[e.status]
                    return self
                cpu.pc = cpu.pop()
                continue
            if pc < 0x2000 and pc != 0x0008:
                self.faults.append("fetch at %04X: outside the module" % pc)
            cpu.step()
            n += 1
            if n > 5_000_000:
                raise RuntimeError("runaway at %04X" % cpu.pc)
        return self

    # --- the channel, as BASIC drives it ---
    def open(self, stream, name, mode="w", binary=False, reclen=0, rec=REC):
        sl = self.disk.open_stream(stream, name, mode, binary, reclen)
        p, o = self.disk.block_loc(stream)
        blk = self.board[p * 8192 + o:p * 8192 + o + rd.BLOCK_LEN]
        r = bytearray(37)
        r[0:4] = w(0x14A0, 0x14A9)
        r[4], r[5] = ord("R"), stream
        r[19:34] = blk
        r[8] = blk[12]
        fl = (1 if blk[12] else 0) | (2 if blk[13] & 1 else 0)
        fl |= 4 if blk[14] in b"ru" else 0
        fl |= 8 if blk[14] in b"wau" else 0
        r[7] = fl
        self.ram[rec:rec + 37] = r
        self.ram[CURCHL:CURCHL + 2] = w(rec)
        off = rec - 0x7000 + 1
        self.ram[STRMS + 6 + 2 * stream:STRMS + 8 + 2 * stream] = w(off)
        self.rec = rec
        return sl

    def put(self, data):
        for c in data:
            self.run(SYM["MB_OUT"], a=c)
            if self.report is not None:
                return self.report
        return None

    def get(self, limit=400):
        out = bytearray()
        for _ in range(limit):
            self.run(SYM["MB_IN"])
            if self.report is not None:
                return bytes(out), self.report
            if not self.cpu.cf:
                return bytes(out), "eof" if not self.cpu.zf else "?"
            out.append(self.cpu.a)
        return bytes(out), None

    def line(self):
        """One INPUT #: up to and with the CR."""
        out = bytearray()
        while not out.endswith(b"\r"):
            got, end = self.get(1)
            if not got:
                return bytes(out), end
            out += got
        return bytes(out), None

    def field(self, off):
        return self.ram[self.rec + off] | self.ram[self.rec + off + 1] << 8

    def set_field(self, off, v):
        self.ram[self.rec + off:self.rec + off + 2] = w(v)

    def file(self, stream):
        """The stream's bytes on the board, up to the ROM's length."""
        sp, so, ln = self.field(19), self.field(21), self.field(25)
        a = sp * 8192 + so
        return bytes(self.board[a:a + ln])

    def slot_lp(self, stream):
        p, o = self.disk.block_loc(stream)
        a = p * 8192 + o + 6
        return rd.r16(self.board, a), rd.r16(self.board, a + 2)


def main():
    rom = open(ROM, "rb").read()
    check_syms()

    print("Text out")
    m = RMachine(rom)
    m.open(4, "log")
    m.put(b"HI" + bytes((16, 2)) + b"A" + bytes((22, 1, 2)) + b"B" + bytes((7, 0xF5)) + b"\r")
    check(m.file(4) == b"HIAB\xf5\r", "colour and AT controls and their parameters dropped, "
          "a keyword kept, CR kept (%r)" % m.file(4))
    check(m.slot_lp(4) == (6, 6), "the CR wrote the length and position back to the slot")
    m.put(b"ab\x06c\r")
    check(m.file(4)[6:] == b"ab" + b" " * 14 + b"c\r", "comma: spaces to the next 16-column stop")
    check(not m.faults and m.hsr_rule() and m.own[4] == 0, "no faults; the window put back")

    print("Binary, TAB, growth, write-back")
    m = RMachine(rom)
    m.open(5, "bin", binary=True)
    m.put(bytes((16, 2, 22, 1, 2, 13, 0)))
    check(m.file(5) == bytes((16, 2, 22, 1, 2, 13, 0)), "binary: every byte as it is")
    m.put(bytes((23, 21, 0)) + b"X")
    check(m.file(5) == bytes((16, 2, 22, 1, 2, 13, 0)) + bytes(13) + b"X",
          "TAB 21 then a byte: byte 21, the gap padded (0 in binary)")
    n0 = len(m.sent)
    data = bytes((i * 7) & 0xFF for i in range(9000))
    m.put(bytes((23, 1, 0)) + data.replace(b"\x17", b"\x18"))
    data = data.replace(b"\x17", b"\x18")
    grows = [s for s in m.sent[n0:] if s[0] == "tpi:rchgrow "]
    check(grows and m.file(5) == data and m.field(25) == 9000,
          "9000 bytes past an 8K extent: %d tpi:rchgrow, the bytes where Disk put them" % len(grows))
    check(grows and grows[0][3][4] | grows[0][3][5] << 8 == 8193, "the growth asked for 8193 bytes")
    check(m.slot_lp(5) == (9000, 9000) or m.slot_lp(5)[0] >= 8960,
          "the slot follows within 256 bytes (%d, %d)" % m.slot_lp(5))
    m.status = 1
    r = m.put(b"\r" * 300)
    check(r == 0x12, "the write-protect switch on: J at the next write-back")
    m.status = 0
    check(not m.faults and m.hsr_rule(), "no faults")

    print("Records")
    m = RMachine(rom)
    m.open(4, "data", "u", reclen=10)
    m.put(b"ABC\r")
    check(m.file(4) == b"ABC" + b" " * 7 and m.field(27) == 10, "a CR pads the record, isn't stored")
    m.put(b"\r")
    check(m.file(4)[10:] == b" " * 10, "a CR alone: a blank record")
    r = m.put(b"0123456789X")
    check(r == 0x19 and m.field(27) == 20, "too long for the record: Q, back at its start")
    m.put(bytes((23, 5, 0)) + b"FIVE\r")
    check(m.file(4)[40:50] == b"FIVE      " and m.field(25) == 50, "TAB 5: record 5, the gap padded")
    m.put(bytes((23, 2, 0)))
    got, end = m.line()
    check(got == b" " * 10 + b"\r", "TAB 2 then a read: record 2 and a CR")
    got, end = m.line()
    check(got == b"0123456789\r", "the next read: record 3 (the 10 bytes before the Q stay)")
    m.put(bytes((23, 0, 0)))
    got, end = m.line()
    check(got == b"5\r", "TAB 0 then a read: the count (5) and a CR (%r)" % got)
    m.put(bytes((23, 0, 0)))
    check(m.put(b"x") == 0x19, "TAB 0 then a write: Q")
    m.put(bytes((23, 1, 0)) + b"AB")                 # PRINT #4;TAB 1;"AB";
    m.run(SYM["RCH_ENDREC"], ix=REC)
    check(m.file(4)[:10] == b"AB        ", "CLOSE's padding of a record left open")
    check(not m.faults and m.hsr_rule(), "no faults")

    print("Text in")
    m = RMachine(rom)
    m.open(4, "txt")
    m.put(b"one\r")
    p0 = m.field(19) * 8192 + m.field(21)
    raw = b"one\rtwo\nthree\r\nfo\x01ur\rlast"
    m.board[p0:p0 + len(raw)] = raw
    m.set_field(25, len(raw))
    m.disk.slots[4].length = len(raw)
    m.put(bytes((23, 1, 0)))
    m.ram[REC + 7] |= 4                                # u: readable too
    got, end = m.get()
    check(got == b"one\rtwo\rthree\rfour\rlast\r" and end == "eof",
          "LF and CRLF read as CR, a control dropped, the last line ends with CR, "
          "then the end of the file: NC NZ (%r)" % got)
    m.ram[REC + 7] &= ~4
    got, end = m.get()
    check(end == 0x19, "a stream opened w: INPUT # is Q")

    print("Modes, the listing, the window")
    m = RMachine(rom)
    m.disk.put("names", bytes((3,)) + rd.tape_name("names") + w(0, 0, 0x8000), b"x")
    m.open(6, "names", "r")
    m.put(b"prompt> ")
    check(m.file(6) == b"x", "mode r: what is printed (INPUT #'s prompt) is dropped")
    m.disk.close(6)
    m.disk.open_list(7, ["alpha", "b", "gamma"])
    r = bytearray(37)
    p, o = m.disk.block_loc(7)
    r[0:4] = w(0x14A0, 0x14A9)
    r[4], r[5] = ord("R"), 7
    r[19:34] = m.board[p * 8192 + o:p * 8192 + o + rd.BLOCK_LEN]
    r[8], r[7] = 10, 1 | 4
    m.ram[REC:REC + 37] = r
    m.ram[CURCHL:CURCHL + 2] = w(REC)
    m.rec = REC
    got, end = m.get()
    check(got == b"alpha\rb\rgamma\r" and end == "eof", "a listing: one name a read, its 0 pad dropped")
    m.put(bytes((23, 0, 0)))
    got, end = m.get(3)
    check(got[:2] == b"3\r", "TAB 0 on a listing: the number of names")

    m = RMachine(rom)
    m.own[4], m.sub[4], m.hsr = 9, 2, 0x13             # a program's page in chunk 4
    m.open(4, "w4", rec=0xA100)                        # and the record in chunk 5
    m.put(b"window\r")
    check(m.file(4) == b"window\r" and (m.own[4], m.sub[4], m.hsr) == (9, 2, 0x13),
          "a program's page in chunk 4 and a record in chunk 5: the window is 6 or 7, "
          "chunk 4 as it was")
    check(not m.faults and m.hsr_rule(), "no faults (%s)" % m.faults[:2])

    ok = sum(results)
    print("%d/%d passed" % (ok, len(results)))
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
