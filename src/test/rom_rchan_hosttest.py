"""The r: channels' per-character code (rchan.asm), in the Z80 interpreter.

src/rom/TSPICO-25.ROM's MB_OUT and MB_IN (what HOME's 14A0h and 14A9h stubs
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
                256 bytes; the write-protect switch on: J, and the length,
                position and column back to the slot's (the bytes the board
                refused aren't counted, so CLOSE # writes the right length)
    records     a CR pads the record and isn't stored; too long: Q and back to
                its start; TAB n; a blank record; TAB 0 then a read: the count
    text in     LF and CRLF as CR, controls dropped, a last line ends with CR,
                then 8 End of file (NC NZ)
    modes       r drops output; w is Q on a read
    the window  chunk 0, under the module in chunk 1, and only chunk 0: OWN0
                back to 0 after every byte; a program's own page in chunk 4
                survives; the HSR rule holds throughout

With sjasmplus on the PATH the module is assembled again and the addresses
below are checked against it (CI has none: the table is the contract).

Run:
    python3 src/test/rom_rchan_hosttest.py
"""

import os
import random
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

ROM = os.path.join(REPO, "src", "rom", "TSPICO-25.ROM")
ASM = os.path.join(REPO, "src", "rom", "fdd", "fddcmd.asm")

SYM = {"MB_OUT": 0x2447, "MB_IN": 0x2455, "RCH_ENDREC": 0x28FD, "RCH_WB": 0x2A37, "CH_SEND": 0x3642, "CH_STATUS": 0x3633, "RCH_END": 0x2C78, "RCH_OUT": 0x271B, "RCH_SYNC": 0x277E,
       "STUB_IMG": 0x2731, "STUB_LEN": 0x1C, "RR_STUB": 0x64, "RR_FMAX": 0x39, "RCH_FIX": 0x2750}
CURCHL, STRMS, CHANS = 0x5C51, 0x5C10, 0x5C4F
REC = 0x7100                     # the record, in chunk 3
DONE = 0xFFF0
SP = 0x6100
HOME_OK = (0x03F3, 0x03F4, 0x03F7, 0x03FA, 0x041C)   # BEEPER's thunk
LAND = 0x2C8C                    # HOME: JP (HL); the EXROM: JP FX_ENTRY
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
              "TSPICO-25.ROM holds the assembled rchan.asm at EXROM 2400h")
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
        self.nslow = 0                                 # RCH_OUT's entries
        self.disk = rd.Disk()
        self.disk.mv = Mover(self)
        self.disk.mount(need=False)
        self.disk.format(32)
        self.disk.mount()
        self.sent = []
        self.mapped = set()
        self.cpu.fetch_hook = None
        # The card's view of F4h and FFh, which decides the ROM a read of
        # chunks 0-1 comes from. `lag` (a function, or None for at once) is
        # the memory reads it stays behind each write; chunk 1 follows chunk
        # 0 by `skew` more. Writes apply in order, as the card's FIFO does.
        self.lag, self.skew, self.pend = None, 0, []
        self.c_hsr, self.c_dec = self.hsr, self.dec
        self.ram[CHANS:CHANS + 2] = w(0x7000)

    def port_in(self, port):
        if port & 0xFF == 0xFC and self.sel == 0x11:
            return self.status
        return super().port_in(port)

    def port_out(self, port, v):
        if port & 0xFF == 0xFC and self.sel < 8 and v:
            self.mapped.add(self.sel)                # the chunks the ROM gave a bank
        if self.lag is not None and port & 0xFF in (0xF4, 0xFF):
            n = max([self.lag()] + [q[0] for q in self.pend])
            self.pend.append([n, port & 0xFF, v, False])
        super().port_out(port, v)

    def card(self):
        """Apply the writes that are due to the card's view."""
        for q in self.pend:
            if q[0] <= 0 and not q[3]:
                q[3] = True
                if q[1] == 0xF4:
                    self.c_hsr = (self.c_hsr & 0xFE) | (q[2] & 1)
                else:
                    self.c_dec = q[2]
        while self.pend and self.pend[0][0] <= -self.skew:
            _, p, v, _ = self.pend.pop(0)
            if p == 0xF4:
                self.c_hsr = v

    def exrom_at(self, a):
        """Whether a read at `a` (below 4000h) comes from the EXROM."""
        if self.lag is None:
            return bool(self.hsr >> (a >> 13) & 1)
        self.card()
        return bool(self.c_hsr >> (a >> 13) & 1)

    def read(self, a):
        if self.lag is None:
            return super().read(a)
        self.card()
        for q in self.pend:
            q[0] -= 1
        c = a >> 13
        if c < 2 and self.owner(c) is None:
            if self.c_hsr >> c & 1:
                return self.exrom[a & 0x3FFF] if self.c_dec & 0x80 else 0xFF
            return self.home[a]
        return super().read(a)

    def run(self, addr, home=False, **regs):
        """From MB_OUT or MB_IN, as the module calls them; or, home=True,
        from a HOME stub (14A0h, 14A9h) with interrupts on, as RST 10h and
        the editor reach it, through FASTH and the fast entry: HOME code
        runs while the card serves HOME there, and the only EXROM addresses
        below 2000h are the switch loops and the landing (128Bh-1296h). In
        chunk 1 the only HOME fetch is the landing's JP (HL) at 2C8Ch. 03FCh,
        Timex's bank call, stops the run (self.slow = the vector in HL)."""
        cpu = self.cpu
        for k, v in regs.items():
            setattr(cpu, k, v)
        cpu.iff = home
        cpu.sp = SP
        cpu.push(DONE)
        cpu.pc = addr
        self.report = self.slow = None
        self.pend, self.c_hsr, self.c_dec = [], self.hsr, self.dec
        n = 0
        while cpu.pc != DONE:
            pc = cpu.pc
            if pc == SYM["RCH_OUT"] and (not home or self.exrom_at(pc)):
                self.nslow += 1
            if pc == 0x0008 and self.exrom_at(pc):   # the EXROM's RST 8: the report
                self.report = self.read(cpu.r16(cpu.sp))
                return self
            if home and 0x2000 <= pc < 0x4000 and not self.exrom_at(pc):
                if pc != LAND:
                    self.faults.append("HOME fetch at %04X" % pc)
                    return self
                cpu.step()
                n += 1
                if n > 5_000_000:
                    raise RuntimeError("runaway at %04X" % cpu.pc)
                continue
            if home and pc < 0x2000:
                if not self.exrom_at(pc):
                    if pc == 0x03FC:
                        self.slow = cpu.h << 8 | cpu.l
                        return self
                    if not (pc in HOME_OK or 0x1265 <= pc < 0x1293 or 0x14A0 <= pc < 0x14B2):
                        self.faults.append("HOME fetch at %04X" % pc)
                        return self
                elif not 0x128B <= pc < 0x1297:
                    self.faults.append("EXROM fetch at %04X" % pc)
                    return self
                cpu.step()
                n += 1
                if n > 5_000_000:
                    raise RuntimeError("runaway at %04X" % cpu.pc)
                continue
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
        r = bytearray(128)
        stub = rec + SYM["RR_STUB"]                    # the output routine, in the record
        r[0:4] = w(stub, 0x14A9)
        r[SYM["RR_STUB"]:] = self.exrom[SYM["STUB_IMG"]:SYM["STUB_IMG"] + SYM["STUB_LEN"]]
        assert len(r) == 128
        r[4], r[5] = ord("R"), stream
        r[19:34] = blk
        r[8] = blk[12]
        fl = (1 if blk[12] else 0) | (2 if blk[13] & 1 else 0)
        fl |= 4 if blk[14] in b"ru" else 0
        fl |= 8 if blk[14] in b"wau" else 0
        r[7] = fl
        self.ram[rec:rec + 128] = r
        self.ram[CURCHL:CURCHL + 2] = w(rec)
        off = rec - 0x7000 + 1
        self.ram[STRMS + 6 + 2 * stream:STRMS + 8 + 2 * stream] = w(off)
        self.rec = rec
        return sl

    def put(self, data, home=False):
        for c in data:
            if home:                                   # as PRINT-A-2 does: the record's R_OUT
                self.run(self.ram[self.rec] | self.ram[self.rec + 1] << 8, home=True, a=c)
            else:
                self.run(SYM["MB_OUT"], a=c)
            if self.report is not None:
                return self.report
        return None

    def get(self, limit=400, home=False):
        out = bytearray()
        for _ in range(limit):
            self.run(0x14A9, home=True) if home else self.run(SYM["MB_IN"])
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
    check(not m.faults and m.hsr_rule() and m.own[0] == 0 and m.mapped == {0},
          "no faults; the window is chunk 0 and put back (%s)" % sorted(m.mapped))

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

    print("Write-protect: the length after J")
    m = RMachine(rom)
    m.open(4, "wp")
    m.put(b"one\r")                                   # PRINT #4;"one"
    m.status = 1                                       # the switch on
    r = m.put(b"two\r")                               # PRINT #4;"two"
    check(r == 0x12, "the switch on: PRINT #4;\"two\" is J")
    check((m.field(25), m.field(27)) == (4, 4) and m.ram[REC + 34] == 0,
          "after J the length and position are the slot's, 4 and 4, the column 0 (%d, %d, %d)"
          % (m.field(25), m.field(27), m.ram[REC + 34]))
    m.status = 0                                       # the switch off: CLOSE #4's write-back
    m.run(SYM["RCH_WB"], ix=REC)
    check(m.report is None and m.slot_lp(4) == (4, 4),
          "the switch off: the write-back leaves the file 4 bytes, not 8 (%d, %d)" % m.slot_lp(4))
    m.put(b"two\r")
    check(m.file(4) == b"one\rtwo\r", "PRINT # goes on where the file ends (%r)" % m.file(4))
    m = RMachine(rom)
    m.open(4, "wpr", "u", reclen=10)
    m.put(b"A\rBC")                                   # record 1 ended, record 2 open
    m.status = 1
    check(m.put(b"\r") == 0x12 and (m.field(25), m.field(27), m.ram[REC + 34]) == (10, 10, 0),
          "a record file: J, back to the slot's length and position (record 2's start), column 0")
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
    r = bytearray(43)
    p, o = m.disk.block_loc(7)
    r[0:4] = w(0x14A0, 0x14A9)
    r[4], r[5] = ord("R"), 7
    r[19:34] = m.board[p * 8192 + o:p * 8192 + o + rd.BLOCK_LEN]
    r[8], r[7] = 10, 1 | 4
    m.ram[REC:REC + 43] = r
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
    check(m.file(4) == b"window\r" and (m.own[4], m.sub[4], m.hsr) == (9, 2, 0x13)
          and m.mapped == {0} and m.own[0] == 0,
          "a program's page in chunk 4 and a record in chunk 5: the window is chunk 0, "
          "chunk 4 as it was")
    check(not m.faults and m.hsr_rule(), "no faults (%s)" % m.faults[:2])

    print("The fast entry, from HOME (14A0h, 14A9h, 03F3h)")
    m = RMachine(rom)
    m.open(4, "fast", "u")
    m.hsr, m.dec = 0x10, 0x05                         # HOME in 0-1, a program's chunk 4; FFh bit 7 clear
    m.own[4], m.sub[4] = 9, 2
    m.put(b"via 14A0h\r", home=True)
    cpu = m.cpu
    check(m.file(4) == b"via 14A0h\r" and m.report is None and m.slow is None,
          "PRINT # through FASTH and FX_ENTRY: the bytes on the board")
    check((m.hsr, m.dec, cpu.sp, cpu.iff) == (0x10, 0x05, SP, True),
          "F4h and FFh as they were, the stack balanced, interrupts back on "
          "(%02X %02X %04X %s)" % (m.hsr, m.dec, cpu.sp, cpu.iff))
    check(any(p == 0xFF and v == 0x85 for p, v in m.port_log), "FFh bit 7 set while the EXROM is in")
    m.put(bytes((23, 1, 0)), home=True)
    got, end = m.get(home=True)
    check(got == b"via 14A0h\r" and end == "eof",
          "INPUT # through 14A9h: the bytes with C, then NC NZ (%r %r)" % (got, end))
    check(not m.faults and (m.own[4], m.sub[4], m.own[0]) == (9, 2, 0), "no faults (%s)" % m.faults[:2])
    m.open(5, "cursor", "u")                           # the stub and its buffer, RCH_FILL, RCH_SYNC
    line = bytes(32 + (i * 13) % 95 for i in range(99))
    text = (line + b"\r") * 90                          # 9000 bytes: 256-byte, 8K and extent edges
    n0, m.nslow = len(m.sent), 0
    m.put(text, home=True)
    grows = [s for s in m.sent[n0:] if s[0] == "tpi:rchgrow "]
    check(m.file(5) == text and m.field(25) == 9000 and m.field(27) == 9000 and grows
          and m.report is None, "9000 bytes of text through the fast entry: all on the board, "
          "the length and position right, %d tpi:rchgrow" % len(grows))
    check(m.slot_lp(5) == (9000, 9000), "the last CR wrote the length and position back (%s)"
          % (m.slot_lp(5),))
    check(m.nslow < 9000 // 4, "most bytes stay in the record: RCH_OUT for %d of 9000" % m.nslow)
    p0, m.nslow = len(m.port_log), 0
    m.put(b"abc", home=True)
    check(m.field(25) == 9000 and m.ram[m.rec + 34] == 0 and m.ram[m.rec + 42] == 3
          and bytes(m.ram[m.rec + 43:m.rec + 46]) == b"abc" and len(m.port_log) == p0
          and m.nslow == 0 and cpu.iff,
          "bytes of 32 or more wait in the record's buffer: no port written, no ROM entered, "
          "the length and column not yet moved")
    m.hsr, m.dec = 0x13, 0x85                          # the EXROM in, as RCH_IN has it
    m.run(SYM["RCH_SYNC"], ix=m.rec)
    m.hsr, m.dec = 0x10, 0x05
    check((m.field(25), m.field(27), m.ram[m.rec + 34], m.ram[m.rec + 41], m.ram[m.rec + 42])
          == (9003, 9003, 3, 0, 0) and m.file(5)[-3:] == b"abc",
          "RCH_SYNC: the buffer on the board, the position, length and column on by 3, the cursor ended")
    m.put(bytes((23, 8801 & 0xFF, 8801 >> 8)), home=True)
    got, end = m.get(300, home=True)
    check(got == text[8800:] + b"abc\r" and end == "eof",
          "TAB 8801 and INPUT #: the same bytes back (and a CR for the open line)")
    m.open(6, "fbin", binary=True)
    data = bytes((i * 37) & 0xFF for i in range(3000)).replace(b"\x17", b"\x18")
    m.put(data, home=True)
    m.hsr, m.dec = 0x13, 0x85
    m.run(SYM["RCH_SYNC"], ix=m.rec)
    m.hsr, m.dec = 0x10, 0x05
    check(m.file(6) == data, "binary through the fast entry: every byte (controls through RCH_OUT)")
    check(not m.faults and m.own[0] == 0 and m.hsr == 0x10, "no faults (%s)" % m.faults[:2])
    m.open(8, "full")                                   # no CR: only a full buffer goes in
    m.nslow = 0
    m.put(b"y" * 400, home=True)
    m.hsr, m.dec = 0x13, 0x85
    m.run(SYM["RCH_SYNC"], ix=m.rec)
    m.hsr, m.dec = 0x10, 0x05
    check(m.file(8) == b"y" * 400 and m.nslow <= 400 // SYM["RR_FMAX"] + 4,
          "400 bytes and no CR: the buffer (%d bytes) emptied when full, RCH_OUT %d times"
          % (SYM["RR_FMAX"], m.nslow))
    recs = {4: 0x7300, 5: 0x7480, 9: 0x7800}            # CLOSE # moved these: R_OUT is stale
    for st, a in recs.items():
        m.ram[a:a + 5] = w(0x1234, 0x14A9) + b"R"
        m.ram[STRMS + 6 + 2 * st:STRMS + 8 + 2 * st] = w(a - 0x7000 + 1)
    m.ram[0x7600:0x7605] = w(0x14A0, 0x14A9) + b"F"     # an f: record, and K on stream 0
    m.ram[STRMS + 6 + 20:STRMS + 6 + 22] = w(0x7600 - 0x7000 + 1)
    k0 = bytes(m.ram[0x7000:0x7005])
    m.ram[STRMS + 6:STRMS + 8] = w(1)
    m.hsr, m.dec = 0x13, 0x85
    m.run(SYM["RCH_FIX"])
    m.hsr, m.dec = 0x10, 0x05
    check(all(m.ram[a] | m.ram[a + 1] << 8 == a + SYM["RR_STUB"] for a in recs.values())
          and bytes(m.ram[0x7600:0x7602]) == w(0x14A0) and bytes(m.ram[0x7000:0x7005]) == k0,
          "RCH_FIX: every R record's R_OUT is its own stub again; an F record and K untouched")
    m.open(6, "fbin2", binary=True)
    m.hsr = 0x12
    m.put(b"\r", home=True)
    check(m.slow == 0x3009 and m.hsr == 0x12, "F4h bit 1 set (chunk 1 not HOME): the old path, "
          "03FCh with HL = 3009h, nothing switched")
    m.hsr = 0x00
    m.ram[0x5DCD:0x5DCF] = w(0x00C8)                 # the editor's key click, HL at 5DCDh
    m.run(0x03F3, home=True, h=0x00, l=0xC8, d=0, e=0)
    check(not m.faults and m.slow is None and m.report is None and m.hsr == 0 and cpu.iff,
          "BEEPER's thunk (03F3h) through FASTH: the click skipped for an R record, back to HOME")

    print("The switch, with the card late (F4h and FFh followed N memory reads after the write)")
    text = b"The quick brown fox 0123456789\r" * 6

    def late(lag, skew=0):
        m = RMachine(rom)
        m.open(4, "late", "u")
        m.hsr, m.dec = 0x00, 0x05
        m.lag, m.skew = lag, skew
        cpu = m.cpu

        def back():
            return (not m.faults and m.report is None and m.slow is None
                    and (m.hsr, m.dec, cpu.sp, cpu.iff) == (0x00, 0x05, SP, True))
        m.put(text, home=True)
        if not (back() and m.file(4) == text):
            return "PRINT #: %s" % (m.faults[:1] or m.report)
        m.put(bytes((23, 1, 0)), home=True)
        got, end = m.get(home=True)
        if not (got == text and end == "eof" and not m.faults):
            return "INPUT #: %s" % (m.faults[:1] or end)
        m.ram[0x5DCD:0x5DCF] = w(0x00C8)
        m.run(0x03F3, home=True, h=0x00, l=0xC8, d=0, e=0)
        return None if back() else "the key click: %s" % m.faults[:1]

    bad = [(n, r) for n in (0, 1, 2, 3, 5, 8, 13, 40, 200) for r in [late(lambda n=n: n)] if r]
    check(not bad, "PRINT #, INPUT # and the key click with the card 0 to 200 reads late %s" % (bad[:2] or ""))
    bad = []
    for seed in range(1, 9):
        rnd = random.Random(seed)
        r = late(lambda: rnd.choice((0, 0, 0, 1, 2, 7, 30)), seed % 3)
        if r:
            bad.append((seed, r))
    check(not bad, "the same with a random delay for each write, eight seeds %s" % (bad[:2] or ""))
    bad = [(k, r) for k in (1, 3, 9, 50) for r in [late(lambda: 2, k)] if r]
    check(not bad, "the same with chunk 1 following chunk 0 by 1 to 50 reads: the landing waits "
          "at 2C8Ch %s" % (bad[:2] or ""))

    ok = sum(results)
    print("%d/%d passed" % (ok, len(results)))
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
