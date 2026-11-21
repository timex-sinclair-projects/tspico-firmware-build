"""The Timex bank API on the TS-2068 Megabank, in the Z80 interpreter.

src/rom/TSPICO-25.ROM's bank code (bankapi.asm spliced over the genuine
routines, plus build-rom.py's frame, Brzozowski and crossing patches) runs
here from RAM 6200h as the boot leaves it, and again from F7C0h as the
64-column copy leaves it. The model is the 2068's memory map with FFh bit 7
(DOCK/EXROM) and the board, with the HSR rule measured on hardware: a write to
a chunk the board owns lands in HOME RAM too unless the chunk's HSR bit (F4h)
is set. That is a failure here, as is any board or HSR write with interrupts
on.

    MB_DETECT  the bank count (6315h, MAXBNK) and BASE (6404h) from the board:
               SIZE cut at bank 253; no board, BASE 0: the count stays 0
    BANK_ENABLE  board banks own exactly what they are given; HOME, DOCK,
               EXROM (any chunks, not tied to 0-1) and banks the board doesn't
               have; registers kept; the interrupt state put back
    GET_STATUS, GET_NUMBER, GET_WORD, PUT_WORD (6.5.3: DE kept)
    SAVE_STATUS/RESTORE_STATUS  the 19-byte frame; only FFh bit 7 back (6.5.5)
    XFER_BYTES  between two banks, directly and through the stack buffer
               (Brzozowski's fixes: A returns 0, the copy is right)
    64 columns  the same from F7C0h with 6000h-683Fh cleared: an address the
               relocation table missed fetches or reads the cleared copy

Run:
    python3 src/test/rom_bankapi_hosttest.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

from z80core import Z80                                          # noqa: E402

ROM = os.path.join(REPO, "src", "rom", "TSPICO-25.ROM")

GET_WORD, PUT_WORD, GET_STATUS, GET_CHUNK = 0x6316, 0x633B, 0x6405, 0x644D
GET_NUMBER, BANK_ENABLE, SAVE_STATUS, RESTORE_STATUS = 0x645E, 0x6499, 0x651E, 0x654A
XFER = 0x6722
NBANKS, MBBASE, MAXBNK = 0x6315, 0x6404, 0x5CBE
MB_BOOT, SYSCON_END = 0x3998, 0x2082
RELOC = 0x97C0
DONE = 0xFFF0
SP = 0x5F00                       # chunk 2: never mapped here
HOME, EXROM, DOCK = 0xFF, 0xFE, 0x00
results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg)


class Machine:
    every = []

    def __init__(self, rom, base=1, size=64, board=True, wide=False):
        Machine.every.append(self)
        self.rom = rom
        self.home = bytearray(rom[0:0x4000])
        self.exrom = bytearray(rom[0x4000:0x8000])
        self.ram = bytearray(65536)
        self.board = bytearray(size * 65536) if board else None
        self.base, self.size = base, size
        self.own, self.sub = [0] * 8, list(range(8))
        self.wprot, self.sel, self.hsr, self.dec = 0, 0, 0, 0
        self.faults = []
        self.port_log = []
        self.wide = wide
        self.cpu = Z80(self.read, self.write, self.port_in, self.port_out)
        self.cpu.iy = 0x5C3A
        self.cpu.fetch_hook = self.fetch
        # what the boot leaves: the bank code at 6200h, the bank stack at 65CEh
        self.ram[0x6200:0x6830] = rom[0x5000:0x5630]
        self.ram[0x65CE:0x65D0] = w(0x65CE)
        self.ram[0x5CC0:0x5CC2] = w(0x5B00)          # XFER's buffer limit
        self.ram[NBANKS] = self.ram[MAXBNK] = size if board else 0    # MB_DETECT's work
        self.ram[MBBASE] = base if board else 0
        if wide:
            self.go_wide()

    def go_wide(self):
        """The boot's 64-column copy (EXROM $0DDD): 6000h-683Fh to F7C0h, every
        word X1D00 lists + 97C0h. Then 6000h-683Fh cleared, so anything the
        table missed shows."""
        self.ram[0xF7C0:0x10000] = self.ram[0x6000:0x6840]
        t = 0x1D00
        while True:
            e = self.exrom[t] | self.exrom[t + 1] << 8
            t += 2
            if not e:
                break
            a = e + RELOC
            v = (self.ram[a] | self.ram[a + 1] << 8) + RELOC
            self.ram[a:a + 2] = w(v)
        self.ram[0x6000:0x6840] = bytes(0x840)

    def at(self, addr):
        return addr + RELOC if self.wide else addr

    # --- memory ---
    def owner(self, c):
        o = self.own[c]
        if self.board is not None and self.base <= o < self.base + self.size:
            return o
        return None

    def page(self, c):
        return (self.own[c] - self.base) * 8 + self.sub[c]

    def read(self, a):
        c = a >> 13
        if self.owner(c) is not None:
            return self.board[self.page(c) * 8192 + (a & 0x1FFF)]
        if self.hsr >> c & 1:
            if self.dec & 0x80:
                return self.exrom[a & 0x3FFF]          # the 16K EXROM, mirrored
            return 0xFF                                # no cartridge
        return self.home[a] if c < 2 else self.ram[a]

    def write(self, a, v):
        c = a >> 13
        if self.owner(c) is not None:
            if not self.wprot >> c & 1:
                self.board[self.page(c) * 8192 + (a & 0x1FFF)] = v
            if not self.hsr >> c & 1:
                self.faults.append("write %04X to board-owned chunk %d with its HSR bit clear" % (a, c))
                self.ram[a] = v
            return
        if not self.hsr >> c & 1 and c >= 2:
            self.ram[a] = v

    def fetch(self, pc):
        if pc == DONE:
            return
        lo, hi = (0xF7C0, 0x10000) if self.wide else (0x6200, 0x6840)
        if not lo <= pc < hi and not (pc in (MB_BOOT, SYSCON_END) or 0x3998 <= pc < 0x4000):
            self.faults.append("fetch at %04X outside the bank code" % pc)
        if self.hsr >> (pc >> 13) & 1 or self.owner(pc >> 13) is not None:
            if not pc < 0x4000:
                self.faults.append("fetch at %04X from a chunk that isn't HOME" % pc)

    # --- ports ---
    def port_in(self, port):
        p = port & 0xFF
        if p == 0xF4:
            return self.hsr
        if p == 0xFF:
            return self.dec
        if p == 0xFD:
            return self.sel if self.board is not None else 0xFF
        if p == 0xFC:
            if self.board is None:
                return 0xFF
            r = self.sel
            if r < 8:
                return self.own[r]
            if r < 16:
                return self.sub[r - 8]
            return {0x10: self.wprot, 0x11: 0, 0x12: 0xA5, 0x13: 0x5A, 0x14: self.base,
                    0x15: self.size, 0x16: 3}.get(r, 0xFF)
        return 0xFF

    def port_out(self, port, v):
        p = port & 0xFF
        self.port_log.append((p, v))
        if p in (0xF4, 0xFC) and self.cpu.iff and self.board is not None:
            self.faults.append("OUT (%02Xh) with interrupts on" % p)
        if p == 0xF4:
            self.hsr = v
        elif p == 0xFF:
            self.dec = v
        elif p == 0xFD:
            self.sel = v
        elif p == 0xFC and self.board is not None:
            r = self.sel
            if r < 8:
                self.own[r], self.sub[r] = v, r
            elif r < 16:
                self.sub[r - 8] = v & 7
            elif r == 0x10:
                self.wprot = v

    # --- running ---
    def call(self, addr, iff=True, sp=SP, stop=(DONE,), **regs):
        cpu = self.cpu
        for k, v in regs.items():
            setattr(cpu, k, v)
        cpu.iff = iff
        cpu.sp = sp
        cpu.push(DONE)
        cpu.pc = self.at(addr) if addr >= 0x6000 else addr
        n = 0
        while cpu.pc not in stop:
            cpu.step()
            n += 1
            if n > 2_000_000:
                raise RuntimeError("runaway at %04X" % cpu.pc)
        return self

    def regs(self):
        c = self.cpu
        return (c.a, c.b, c.c, c.d, c.e, c.h, c.l, c.ix)

    def hsr_rule(self):
        return all(self.hsr >> c & 1 for c in range(8) if self.owner(c) is not None)

    def be(self, b, chunks, iff=True):
        """BANK_ENABLE: bank b gets `chunks` (bit n = chunk n, high active)."""
        return self.call(BANK_ENABLE, iff=iff, b=b, c=~chunks & 0xFF)


def w(*vals):
    return b"".join(bytes([v & 0xFF, v >> 8 & 0xFF]) for v in vals)


def suite(rom, wide):
    tag = "64 col: " if wide else ""

    # --- BANK_ENABLE ---
    m = Machine(rom, wide=wide)
    m.cpu.a, m.cpu.d, m.cpu.e, m.cpu.h, m.cpu.l, m.cpu.ix = 0x11, 0x22, 0x33, 0x44, 0x55, 0x6677
    m.be(3, 0x30)
    check(m.own[4:6] == [3, 3] and m.hsr == 0x30, tag + "BANK_ENABLE bank 3, chunks 4-5: OWN4-5 = 3, their HSR bits set")
    check(m.regs() == (0x11, 3, 0xCF, 0x22, 0x33, 0x44, 0x55, 0x6677) and m.cpu.iff,
          tag + "BANK_ENABLE: every register kept, interrupts back on")
    m.write(0x8000, 0xAB)
    check(m.board[(3 - 1) * 65536 + 4 * 8192] == 0xAB and m.ram[0x8000] == 0,
          tag + "a write to 8000h goes to bank 3's page 4, not HOME RAM")
    m.be(3, 0x10, iff=False)
    check(m.own[4:6] == [3, 0] and m.hsr == 0x10 and not m.cpu.iff,
          tag + "bank 3 given chunk 4 only: chunk 5 back to HOME (bit, then OWN); interrupts left off")
    m.be(7, 0x40)
    check(m.own[4] == 3 and m.own[6] == 7 and m.hsr == 0x50, tag + "bank 7 in chunk 6: bank 3 keeps chunk 4")
    m.be(HOME, 0x40)
    check(m.own[6] == 0 and m.hsr == 0x10 and m.own[4] == 3, tag + "HOME takes chunk 6 back, bank 3 untouched")
    m.be(EXROM, 0x40)
    check(m.dec & 0x80 and m.hsr == 0x50 and m.own[4] == 3,
          tag + "EXROM in chunk 6 alone (as LEAP puts it): FFh bit 7, HSR 50h, bank 3 kept")
    check(m.read(0xC000) == m.exrom[0], tag + "and chunk 6 reads the EXROM")
    m.be(DOCK, 0x60)
    check(not m.dec & 0x80 and m.hsr == 0x70 and m.own[4] == 3,
          tag + "DOCK in chunks 5-6: FFh bit 7 clear, exactly those, bank 3 kept")
    m.be(3, 0x60)
    check(m.own[4:7] == [0, 3, 3] and m.hsr == 0x60,
          tag + "bank 3 given chunks 5-6: takes them from the DOCK, gives up chunk 4")
    m.be(250, 0x60)
    check(m.own[5:7] == [0, 0] and m.hsr == 0, tag + "a bank the board doesn't have (250): its chunks to HOME")
    m.be(EXROM, 0x03)
    check(m.dec & 0x80 and m.hsr == 0x03, tag + "EXROM in chunks 0-1, as the crossings ask (FEFC)")
    check(m.hsr_rule(), tag + "every owned chunk has its HSR bit")

    # --- GET_STATUS, GET_NUMBER ---
    m = Machine(rom, wide=wide)
    m.be(5, 0x30)
    m.be(9, 0x80 >> 1)                                 # chunk 6
    m.be(EXROM, 0x03)
    m.call(GET_STATUS, a=0x77, b=5)
    check(m.cpu.c == 0xCF and m.cpu.b == 5 and m.cpu.a == 0x77, tag + "GET_STATUS bank 5: C = CFh (chunks 4-5), A and B kept")
    m.call(GET_STATUS, b=HOME)
    check(m.cpu.c == m.hsr == 0x73 and m.cpu.b == HOME, tag + "GET_STATUS HOME: C = the HSR (73h), B kept (6.5.2)")
    m.call(GET_STATUS, b=EXROM)
    check(m.cpu.c == 0xFC and m.cpu.b == EXROM, tag + "GET_STATUS EXROM: C = FCh (chunks 0-1, not the board's)")
    m.call(GET_STATUS, b=DOCK)
    check(m.cpu.c == 0xFF and m.cpu.b == DOCK, tag + "GET_STATUS DOCK, EXROM selected: FFh")
    m.call(GET_STATUS, b=200)
    check(m.cpu.c == 0xFF, tag + "GET_STATUS a bank the board doesn't have: FFh")
    for hl, want in ((0x8123, 5), (0xA000, 5), (0xC000, 9), (0x0100, EXROM), (0x4000, HOME), (0xE000, HOME)):
        m.call(GET_NUMBER, h=hl >> 8, l=hl & 0xFF, b=0x12, c=0x34)
        check(m.cpu.a == want and (m.cpu.b, m.cpu.c) == (0x12, 0x34),
              tag + "GET_NUMBER %04Xh: %02Xh, BC kept" % (hl, want))
    m.be(DOCK, 0x40)
    m.call(GET_NUMBER, h=0xC0, l=0)
    check(m.cpu.a == DOCK, tag + "GET_NUMBER C000h after DOCK in chunk 6: 0")

    # --- GET_WORD, PUT_WORD ---
    m = Machine(rom, wide=wide)
    m.call(PUT_WORD, b=12, d=0xBE, e=0xEF, h=0x80, l=0x10)
    pg = (12 - 1) * 65536 + 4 * 8192 + 0x10
    check(m.board[pg:pg + 2] == b"\xEF\xBE" and (m.cpu.d, m.cpu.e) == (0xBE, 0xEF),
          tag + "PUT_WORD BEEFh to 8010h in bank 12: on the board, DE kept (6.5.3)")
    check(m.own == [0] * 8 and m.hsr == 0 and m.ram[0x8010] == 0, tag + "PUT_WORD: chunk 4 HOME again, HOME RAM untouched")
    m.ram[0x8010:0x8012] = w(0x1234)
    m.call(GET_WORD, b=12, h=0x80, l=0x10)
    check((m.cpu.h, m.cpu.l) == (0xBE, 0xEF) and m.own == [0] * 8, tag + "GET_WORD 8010h from bank 12: BEEFh, chunk 4 put back")

    # --- SAVE_STATUS / RESTORE_STATUS ---
    m = Machine(rom, wide=wide)
    m.be(4, 0x30)
    m.cpu.iff = False                                   # (the test's own writes)
    m.port_out(0xFD, 0x0D)
    m.port_out(0xFC, 2)                                 # SUB5 = 2
    m.port_out(0xFD, 0x11)                              # a program's select
    m.dec = 0x80 | 0x06
    before = (list(m.own), list(m.sub), m.hsr, m.sel)
    m.call(SAVE_STATUS, ix=0x5E00, a=1, b=2, c=3, d=4, e=5)
    frame = bytes(m.ram[0x5E00:0x5E13])
    check(m.cpu.ix == 0x5E12 and (m.cpu.a, m.cpu.b, m.cpu.c, m.cpu.d, m.cpu.e) == (1, 2, 3, 4, 5),
          tag + "SAVE_STATUS: IX = the 19th byte, AF BC DE kept")
    check(frame == bytes([0x86, 0x30, 0, 0, 0, 0, 4, 4, 0, 0, 0, 1, 2, 3, 4, 2, 6, 7, 0x11]),
          tag + "SAVE_STATUS: FFh, F4h, OWN0-7, SUB0-7, the select")
    check(m.sel == 0x11, tag + "SAVE_STATUS: the select put back")
    m.be(9, 0x30)
    m.be(HOME, 0x30)
    m.be(2, 0x40)
    m.dec = 0x00 | 0x40                                 # DOCK, and a mode bit changed since
    m.call(RESTORE_STATUS, ix=0x5E00, iff=True)
    check((m.own, m.sub, m.hsr, m.sel) == before and m.cpu.ix == 0x5E12,
          tag + "RESTORE_STATUS: OWN, SUB, the HSR and the select back; IX = the 19th byte")
    check(m.dec == 0xC0 and m.cpu.iff, tag + "RESTORE_STATUS: FFh bit 7 back, the rest as now (6.5.5); interrupts on again")

    # --- XFER_BYTES ---
    for name, src, dst, srcb, dstb in (("direct (chunks 4 and 5)", 0x8000, 0xA100, 6, 8),
                                       ("through the buffer (both chunk 4)", 0x8000, 0x8100, 6, 8)):
        m = Machine(rom, wide=wide)
        n = 0x180
        data = bytes((i * 7 + 3) & 0xFF for i in range(n))
        sp_ = (srcb - 1) * 65536 + (src >> 13) * 8192 + (src & 0x1FFF)
        m.board[sp_:sp_ + n] = data
        m.be(3, 0x40)                                    # something mapped already: bank 3 in chunk 6
        state = (list(m.own), m.hsr)
        cpu = m.cpu
        cpu.sp = SP
        for v in (srcb << 8 | dstb, src, dst, n, 0):
            cpu.push(v)
        m.call(XFER, sp=cpu.sp, b=0x55, c=0x66, d=0x77, e=0x88, h=0x99, l=0xAA)
        dp = (dstb - 1) * 65536 + (dst >> 13) * 8192 + (dst & 0x1FFF)
        check(m.board[dp:dp + n] == data, tag + "XFER %s: bank %d %04Xh -> bank %d %04Xh" % (name, srcb, src, dstb, dst))
        check(cpu.a == 0 and (cpu.b, cpu.c, cpu.d, cpu.e, cpu.h, cpu.l) == (0x55, 0x66, 0x77, 0x88, 0x99, 0xAA)
              and cpu.sp == SP, tag + "XFER %s: A = 0, BC DE HL kept, the parameters gone" % name)
        check((m.own, m.hsr) == state, tag + "XFER %s: the banks put back" % name)

    # --- no board ---
    m = Machine(rom, board=False, wide=wide)
    m.be(5, 0x30)
    check(not any(p in (0xFC,) for p, _ in m.port_log) and m.hsr == 0,
          tag + "no board: BANK_ENABLE bank 5 writes nothing to FCh")
    m.call(GET_STATUS, b=5)
    check(m.cpu.c == 0xFF, tag + "no board: GET_STATUS bank 5 is FFh")
    m.be(EXROM, 0x40)
    check(m.dec & 0x80 and m.hsr == 0x40, tag + "no board: EXROM in chunk 6")
    m.call(SAVE_STATUS, ix=0x5E00)
    m.port_log = []
    m.call(RESTORE_STATUS, ix=0x5E00)
    check(not any(p == 0xFC for p, _ in m.port_log) and m.cpu.ix == 0x5E12 and m.hsr == 0x40,
          tag + "no board: SAVE/RESTORE keep the 19-byte frame, nothing written to FCh")


def call_home(rom):
    """CALL_HOME (EXROM $03DD) from EXROM code, as the module calls HOME: a
    target in HOME that RETs. HOME gets chunks 0-1 only (FFFC), a board bank
    in chunk 5 stays, and the stack comes back as it was. The parameter
    count must be 0: patched in place, FFFC made it FCh, and CALL_BANK's
    copy of 266 bytes from SP, which sits just below 6200h, moved the bank
    code (the interrupt handler at 62AEh included) for the whole call."""
    m = Machine(rom)
    Machine.every.remove(m)                              # it fetches the EXROM and HOME
    m.dec, m.hsr = 0x80, 0x03                            # the EXROM in chunks 0-1
    m.be(4, 0x20)
    m.dec, m.hsr = 0x80, 0x23
    m.home[0x3FF0] = 0xC9                                # the HOME target: RET
    seen = []
    m.cpu.fetch_hook = lambda pc: seen.append((pc, m.hsr, list(m.own))) if pc == 0x3FF0 else None
    cpu = m.cpu
    cpu.iff = False
    top = 0x61F0                                         # the 2068's machine stack: just
    code = bytes(m.ram[0x6200:0x6300])                   # below the bank code
    cpu.sp = top
    cpu.push(DONE)                                       # the preamble's caller
    cpu.push(0x1234)                                     # PUSH IX
    cpu.h, cpu.l = 0x3F, 0xF0                            # EXX / LD HL,target
    cpu.ix = 0
    cpu.pc = 0x03DD                                      # JP 03DDh
    n = moved = 0
    while cpu.pc != DONE and n < 200000:
        cpu.step()
        n += 1
        moved += m.ram[0x6200:0x6300] != code
    check(seen and seen[0][1] & 0x03 == 0 and seen[0][2][5] == 4,
          "CALL_HOME: HOME in chunks 0-1 for the call, bank 4 still in chunk 5 (%s)" % seen[:1])
    check(cpu.pc == DONE and cpu.sp == top and cpu.ix == 0x1234 and m.hsr == 0x23 and m.own[5] == 4
          and m.dec & 0x80, "CALL_HOME: back in the EXROM, SP and IX as they were, bank 4 kept "
          "(PC %04X SP %04X)" % (cpu.pc, cpu.sp))
    check(not moved, "CALL_HOME: the bank code at 6200h-62FFh untouched throughout (%d steps moved)" % moved)


def detect(rom, base, size, board=True):
    m = Machine(rom, base=base, size=size, board=board)
    m.ram[NBANKS] = m.ram[MAXBNK] = 0
    m.ram[MBBASE] = 0x99
    m.dec = 0x80
    m.hsr = 0x03
    m.ram[0x5CBC:0x5CBE] = w(0x5EEA)
    m.call(0x0A3E, stop=(SYSCON_END,), iff=False)
    Machine.every.remove(m)                              # its fetches are the EXROM's
    return m


def main():
    rom = open(ROM, "rb").read()

    m = detect(rom, 1, 64)
    hl = m.cpu.h << 8 | m.cpu.l
    check(m.ram[NBANKS] == m.ram[MAXBNK] == 64 and m.ram[MBBASE] == 1 and hl == 0x5EEA + 0x0D,
          "MB_DETECT BASE 1 SIZE 64: count 64, BASE 1, on to $2082 with HL = SYSCON + 0Dh")
    m = detect(rom, 193, 64)
    check(m.ram[NBANKS] == m.ram[MAXBNK] == 61 and m.ram[MBBASE] == 193,
          "MB_DETECT BASE 193 SIZE 64: count 61 (banks 193-253)")
    m = detect(rom, 0, 64)
    check(m.ram[NBANKS] == m.ram[MAXBNK] == 0, "MB_DETECT BASE 0: no board, count 0")
    m = detect(rom, 1, 64, board=False)
    check(m.ram[NBANKS] == m.ram[MAXBNK] == 0 and m.ram[MBBASE] == 0x99, "MB_DETECT with no board: count 0, nothing else written")

    call_home(rom)
    suite(rom, wide=False)
    suite(rom, wide=True)

    faults = sorted(set(f for mm in Machine.every for f in mm.faults))
    check(not faults, "no HSR leaks, no board or HSR write with interrupts on, no stray fetches")
    for f in faults[:20]:
        print("   ", f)
    print("\n%d/%d passed" % (sum(results), len(results)))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
