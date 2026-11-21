"""The Megabank test ROM's boot reset, block gates and mover in the Z80 interpreter.

src/rom/TSPICO-25.ROM (tools/build-rom.py --megabank; CI checks it is what
the build makes) runs here against a model of the 2068's memory map with the
TS-2068 Megabank fitted, including the rule measured on hardware that
ZEsarUX's model leaves out: /BE keeps the 2068's own memory off a read, but
a write to a chunk the board owns still lands in HOME RAM unless the chunk's
HSR bit (port F4h) is set. Any such write is a failure here, as is a window
mapped with interrupts on, or into chunks 0-3.

    MB_BOOT    (EXROM $0A3E): every OWNn and WPROT written 0, the bank count
               set from the board (MB_DETECT; rom_bankapi_hosttest has the
               cases), SYSCON_END ($2082) reached with HL = SYSCON + 0Dh
    the mover  (response function 89h, through FN_EXT as the $2213 patch
               reaches it): ops 1-7, pieces over chunk and page boundaries,
               the window never the 2068 memory's chunk nor the stack's, a
               program's page in the window chunk put back (OWN, SUB, HSR),
               the interrupt state put back, refusals that keep the stream
               in step, no board, op 0 and the status after it
    R_SA/R_LD  ($0068/$00FC): TPMODE bit 5 clear goes on to $1879/$196D;
               set, the block goes out as tpi:rblk and the mover moves it,
               leaving through SA_RET with carry set; bit 5 cleared after a
               data block, kept after a header

Run:
    python3 src/test/rom_megabank_hosttest.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

from z80core import Z80                                          # noqa: E402

ROM = os.path.join(REPO, "src", "rom", "TSPICO-25.ROM")

MB_BOOT, FN_EXT, R_SA, R_LD = 0x3998, 0x3A61, 0x39F5, 0x3A06
SYSCON_END, PICO_SA, PICO_LD, SA_RET = 0x2082, 0x1879, 0x196D, 0x00E5
TPMODE = 0x5DDB
DONE = 0xFFF0                    # a return address: the call has finished
results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg)


class Machine:
    """The 2068 with the EXROM paged in (FFh bit 7 set), the board and a Pico."""
    every = []

    def __init__(self, rom, base=1, size=64, board=True):
        Machine.every.append(self)
        self.home = bytearray(rom[0:0x4000])
        self.exrom = bytearray(rom[0x4000:0x8000])
        self.ram = bytearray(65536)                  # HOME RAM, 4000h up
        self.board = bytearray(size * 65536) if board else None
        self.base, self.size = base, size
        self.own, self.sub = [0] * 8, list(range(8))
        self.wprot, self.sel = 0, 0
        self.hsr = 0x03                              # chunks 0-1: EXROM
        self.pico_in = bytearray()                   # what IN (0Eh) will read
        self.pico_out = bytearray()                  # what OUT (0Eh) wrote
        self.port_log = []
        self.faults = []
        self.windows = []                            # (chunk, addr chunk) of each mapping
        self.cpu = Z80(self.read, self.write, self.port_in, self.port_out)
        self.cpu.iy = 0x5C3A
        self.ram[0x5CB7] |= 0x40                     # FLAGX-ish bit WF_NPH's BREAK test skips on
        self.cpu.fetch_hook = self.fetch

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
            return self.exrom[a] if c < 2 else 0xFF
        return self.home[a] if c < 2 else self.ram[a]

    def write(self, a, v):
        c = a >> 13
        if self.owner(c) is not None:
            if not self.wprot >> c & 1:
                self.board[self.page(c) * 8192 + (a & 0x1FFF)] = v
            if not self.hsr >> c & 1:
                self.faults.append("write %04X to board-owned chunk %d with its HSR bit clear" % (a, c))
                self.ram[a] = v                      # what the hardware does
            return
        if not self.hsr >> c & 1 and c >= 2:
            self.ram[a] = v

    def fetch(self, pc):
        if pc >= 0x4000 or not self.hsr >> (pc >> 13) & 1:
            if pc not in (DONE, SYSCON_END, PICO_SA, PICO_LD):
                self.faults.append("fetch at %04X outside the EXROM" % pc)

    # --- ports ---
    def port_in(self, port):
        p = port & 0xFF
        if p == 0x0E:
            if not self.pico_in:
                self.faults.append("IN (0Eh) with nothing queued")
                return 0
            v = self.pico_in[0]
            del self.pico_in[0]
            return v
        if p == 0x0F:
            return 0xFF                                # READY, IDLE, not RECOVERED
        if p == 0xF4:
            return self.hsr
        if p == 0xFE:
            return 0xFF                                # no keys: no BREAK
        if p == 0xFD:
            return self.sel
        if p == 0xFC:
            if self.board is None:
                return 0x7F
            r = self.sel
            if r < 8:
                return self.own[r]
            if r < 16:
                return self.sub[r - 8]
            return {0x10: self.wprot, 0x11: 0, 0x12: 0xA5, 0x13: 0x5A, 0x14: self.base,
                    0x15: self.size, 0x16: 1}.get(r, 0xFF)
        return 0xFF

    def port_out(self, port, v):
        p = port & 0xFF
        self.port_log.append((p, v))
        if p == 0x0E:
            self.pico_out.append(v)
        elif p == 0xF4:
            self.hsr = v
        elif p == 0xFD:
            self.sel = v
        elif p == 0xFC and self.board is not None:
            r = self.sel
            if r < 8:
                self.own[r], self.sub[r] = v, r
                if self.owner(r) is not None:
                    if self.cpu.iff:
                        self.faults.append("chunk %d mapped with interrupts on" % r)
                    if r < 4:
                        self.faults.append("a window in chunk %d" % r)
            elif r < 16:
                self.sub[r - 8] = v & 7
            elif r == 0x10:
                self.wprot = v

    # --- running ---
    def call(self, addr, sp=0xFF00, limit=3_000_000, stop=(DONE,)):
        cpu = self.cpu
        cpu.sp = sp
        cpu.push(DONE)
        cpu.pc = addr
        n = 0
        while cpu.pc not in stop:
            cpu.step()
            n += 1
            if n > limit:
                raise RuntimeError("runaway at %04X" % cpu.pc)
        return cpu.pc


def w(*vals):
    return b"".join(bytes([v & 0xFF, v >> 8 & 0xFF]) for v in vals)


def mover(m, ops, status=1, iff=False, sp=0xFF00, a=0x88):
    """Run response function 89h (FN_EXT with A = 88h) over `ops` (the bytes
    the Pico sends after 89h, op 0 and the status included: appended here)."""
    m.pico_in = bytearray(ops) + bytes([0, status])
    m.pico_out = bytearray()
    m.cpu.iff = iff
    m.cpu.a = a
    m.call(FN_EXT, sp=sp)
    return m


def main():
    rom = open(ROM, "rb").read()

    # --- MB_BOOT ---
    m = Machine(rom)
    m.own = [200] * 8                               # not the board: chunks 0-1 still the EXROM
    m.wprot = 0xFF
    m.ram[0x5CBC:0x5CBE] = w(0x5EEA)
    m.ram[0x5CBE] = m.ram[0x6315] = 0x00
    m.call(0x0A3E, stop=(SYSCON_END,))
    hl = m.cpu.h << 8 | m.cpu.l
    check(m.own == [0] * 8 and m.wprot == 0, "MB_BOOT: OWN0-OWN7 and WPROT written 0")
    check(hl == 0x5EEA + 0x0D, "MB_BOOT: on to $2082 with HL = SYSCON + 0Dh (%04X)" % hl)
    check(m.ram[0x5CBE] == 64 and m.ram[0x6315] == 64 and m.ram[0x6404] == 1,
          "MB_BOOT: the bank count 64 (SIZE), BASE 1 at 6404h")

    # --- the mover: op 1, one piece, window choice and no leaks ---
    m = Machine(rom)
    src = bytes((i * 3 + 1) & 0xFF for i in range(0x300))
    m.ram[0x8100:0x8400] = src                       # chunk 4
    mover(m, b"\x01" + w(0x8100, 0x300, 10, 0x100))
    check(m.board[10 * 8192 + 0x100:10 * 8192 + 0x400] == src, "op 1: 2068 memory to page 10")
    check(m.pico_out == b"\x01", "op 1: reply 1")
    check(m.own == [0] * 8 and m.hsr == 0x03, "op 1: OWN and the HSR put back")
    check(m.ram[0xA000:0xC000] == bytes(0x2000), "op 1: the window's HOME RAM untouched")

    # --- op 1 over a chunk boundary and a page boundary ---
    m = Machine(rom)
    src = bytes((i * 5 + 7) & 0xFF for i in range(0x300))
    m.ram[0x9F00:0xA200] = src                       # chunks 4 and 5
    log = []
    orig = m.port_out

    def spy(port, v, m=m):
        if port & 0xFF == 0xFC and m.sel < 8 and v:
            log.append(m.sel)
        orig(port, v)
    m.cpu.port_out = spy
    mover(m, b"\x01" + w(0x9F00, 0x300, 3, 0x1F80))
    got = m.board[3 * 8192 + 0x1F80:3 * 8192 + 0x2000] + m.board[4 * 8192:4 * 8192 + 0x280]
    check(got == src, "op 1 over A000h and a page end: three pieces, the bytes right")
    check(log == [5, 5, 4], "op 1: windows 5, 5, then 4 (never the 2068 side's chunk): %s" % log)

    # --- the stack across a chunk boundary: SP = C010h ---
    m = Machine(rom)
    log = []
    orig = m.port_out
    m.cpu.port_out = lambda port, v, m=m: (log.append(m.sel) if port & 0xFF == 0xFC and m.sel < 8 and v else None,
                                           orig(port, v))
    m.ram[0x8000:0x8010] = b"0123456789abcdef"
    mover(m, b"\x01" + w(0x8000, 16, 7, 0), sp=0xC010)
    check(log == [7] and m.board[7 * 8192:7 * 8192 + 16] == b"0123456789abcdef",
          "SP = C010h: chunks 4 (data), 5 and 6 (the stack, the frame) skipped: window 7 %s" % log)

    # --- a program's page in the window chunk survives ---
    m = Machine(rom)
    m.own[5], m.sub[5], m.hsr = 3, 2, 0x03 | 0x20     # bank 3, its third 8K, HSR bit 5
    prog = (3 - 1) * 8 + 2
    m.board[prog * 8192:prog * 8192 + 4] = b"PROG"
    m.ram[0x8000:0x8004] = b"DATA"
    mover(m, b"\x01" + w(0x8000, 4, 20, 0) + b"\x02" + w(0x9000, 4, 20, 0))
    check(m.board[20 * 8192:20 * 8192 + 4] == b"DATA" and m.ram[0x9000:0x9004] == b"DATA",
          "ops 1 and 2 through window 5")
    check(m.own[5] == 3 and m.sub[5] == 2 and m.hsr == 0x23 and m.read(0xA000) == ord("P"),
          "the program's chunk 5 is back: OWN5 = 3, SUB5 = 2, HSR bit 5, its bytes")

    # --- op 2, op 3, op 4, op 5, op 6, op 7 ---
    m = Machine(rom)
    pat = bytes((i * 7 + (i >> 8)) & 0xFF for i in range(10000))
    m.board[40 * 8192 + 5000:40 * 8192 + 15000] = pat
    x = 0
    for b in pat:
        x ^= b
    ops = (b"\x02" + w(0x6000, 10000, 40, 5000)          # board -> 2068 (chunks 3, 4)
           + b"\x03" + w(0x6000, 10000, 40, 5000)        # the same: 1
           + b"\x04" + w(10000, 40, 5000)                # board -> Pico
           + b"\x05" + w(5, 60, 8190) + b"hello" + bytes([0x62])   # Pico -> board (xor of hello)
           + b"\x06" + w(10000, 40, 5000, 50, 8000)      # page to page
           + b"\x07")
    mover(m, ops)
    check(m.ram[0x6000:0x6000 + 10000] == pat, "op 2: page 40:5000 to 6000h, over a page and a chunk")
    out = bytes(m.pico_out)
    check(out[0:2] == b"\x01\x01", "op 2 and op 3 (the same) reply 1, 1")
    check(out[2:10002] == pat and out[10002] == x and out[10003] == 1, "op 4: 10000 bytes, their XOR, 1")
    check(m.board[60 * 8192 + 8190:60 * 8192 + 8195] == b"hello" and out[10004] == 1,
          "op 5: written over a page boundary, XOR good: 1")
    check(m.board[50 * 8192 + 8000:50 * 8192 + 18000] == pat and out[10005] == 1, "op 6: page to page")
    check(out[10006:10011] == bytes([1, 1, 64, 0, 1]), "op 7: found, BASE 1, SIZE 64, STATUS 0, VERSION 1")
    check(len(out) == 10011 and not m.pico_in and m.cpu.a == 0 and not m.cpu.f & 1,
          "op 0 and status 1: every byte read, A = 0, NC")
    check(m.own == [0] * 8 and m.hsr == 0x03, "all put back")

    # --- compare that differs, refusals, a bad XOR, the status after op 0 ---
    m = Machine(rom)
    m.ram[0x8000:0x8003] = b"abc"
    m.board[0:3] = b"abd"
    ops = (b"\x03" + w(0x8000, 3, 0, 0)                  # differs: 2
           + b"\x05" + w(3, 0xFFFF, 0) + b"xyz\x00"      # past the board: 4, bytes still read
           + b"\x04" + w(2, 0, 0x2000)                   # offset 2000h: 4, still 2 + XOR sent
           + b"\x05" + w(4, 511, 8189) + b"wxyz\x00"     # runs past page 511: 4
           + b"\x05" + w(3, 511, 8189) + b"end" + bytes([ord("e") ^ ord("n") ^ ord("d")])   # the last bytes: 1
           + b"\x05" + w(2, 9, 0) + b"ab\x00")           # bad XOR: 5
    mover(m, ops, status=2)
    out = bytes(m.pico_out)
    check(out == bytes([2, 4, 0, 0, 0, 4, 4, 1, 5]), "replies 2, 4, (0 0 0) 4, 4, 1, 5: %s" % out.hex())
    check(m.board[511 * 8192 + 8189:] == b"end" and not m.pico_in, "the board's last bytes written; all read")
    check(m.cpu.a == 1 and m.cpu.f & 1, "status 2 after op 0: C with A = 1 (Report R)")

    # --- no board; interrupts put back ---
    m = Machine(rom, board=False)
    mover(m, b"\x01" + w(0x8000, 3, 0, 0) + b"\x07", iff=True)
    check(bytes(m.pico_out[:2]) == b"\x03\x00", "no board: op 1 replies 3, op 7 says not found")
    check(m.cpu.iff, "interrupts on before: on after")
    m = Machine(rom)
    mover(m, b"\x07", iff=False)
    check(not m.cpu.iff, "interrupts off before: off after")
    m = Machine(rom)
    m.pico_in = bytearray(b"\x09")
    m.cpu.a = 0x88
    m.call(FN_EXT)
    check(m.cpu.a == 9 and m.cpu.f & 1, "an unknown operation: C, A = 09h (J)")
    m = Machine(rom)
    m.cpu.a = 0x89
    m.call(FN_EXT)
    check(m.cpu.a == 0x89 and not m.pico_in, "FN_EXT: 8Ah and up return untouched (Report D)")

    # --- R_SA / R_LD ---
    for entry, cont, name in ((R_SA, PICO_SA, "R_SA"), (R_LD, PICO_LD, "R_LD")):
        m = Machine(rom)
        m.ram[TPMODE] = 0x02
        m.cpu.a, m.cpu.ix, m.cpu.d, m.cpu.e = 0xFF, 0x8000, 0, 17
        pc = m.call(entry, stop=(DONE, cont))
        check(pc == cont and m.cpu.a == 0xFF, "%s: TPMODE bit 5 clear: on to $%04X" % (name, cont))

    hdr = bytes([3]) + b"code      " + w(0x1234, 0x8000, 0)
    for flag, n, addr in ((0x00, 17, 0x5C00 + 0x40), (0xFF, 0x1234, 0x8000)):
        m = Machine(rom)
        m.ram[TPMODE] = 0x22
        m.ram[0x5C48] = 0x38
        m.ram[addr:addr + n] = (hdr if flag == 0 else bytes((i * 11) & 0xFF for i in range(n)))
        m.pico_in = bytearray(b"\x01" + b"\x89" + b"\x01" + w(addr, n, 100, 0) + b"\x00\x01")
        m.cpu.a, m.cpu.ix, m.cpu.d, m.cpu.e = flag, addr, n >> 8, n & 0xFF
        m.cpu.f = 0
        m.call(R_SA)
        out = bytes(m.pico_out)
        text = "tpi:rblk %02x%02x%02x%02x" % (addr & 0xFF, addr >> 8, n & 0xFF, n >> 8)
        pre = bytes([0x42, 0, 0x25, 0, 0, flag, 0, len(text), 0])
        x = 0
        for b in pre:
            x ^= b
        body = b"D" + bytes([len(text), 0]) + text.encode()
        bx = 0
        for b in body:
            bx ^= b
        want = pre + bytes([x]) + body + bytes([bx, 1])
        check(out == want, "R_SA flag %02X: tpi:rblk, PMR1 0 (SAVE), PMR2 the flag, then the reply: %s"
              % (flag, out[:24].hex()))
        check(m.board[100 * 8192:100 * 8192 + n] == m.ram[addr:addr + n], "R_SA flag %02X: the block on the board" % flag)
        check(m.cpu.f & 1 and m.cpu.ix == addr, "R_SA flag %02X: carry set (done), IX kept" % flag)
        check((m.ram[TPMODE] & 0x20) == (0x20 if flag == 0 else 0),
              "R_SA flag %02X: TPMODE bit 5 %s" % (flag, "kept after a header" if flag == 0 else "cleared"))

    m = Machine(rom)
    m.ram[TPMODE] = 0x22
    m.board[0:6] = b"loaded"
    m.pico_in = bytearray(b"\x01\x89\x02" + w(0x9000, 6, 0, 0) + b"\x00\x01")
    m.cpu.a, m.cpu.ix, m.cpu.d, m.cpu.e = 0xFF, 0x9000, 0, 6
    m.cpu.f = 1                                       # LOAD
    m.call(R_LD)
    check(m.ram[0x9000:0x9006] == b"loaded" and m.cpu.f & 1, "R_LD: LOAD, op 2: the block in memory, C")
    check(m.pico_out[3] == 1, "R_LD: PMR1 1 (LOAD)")
    m = Machine(rom)
    m.ram[TPMODE] = 0x22
    m.pico_in = bytearray(b"\x01\x89\x00\x01")
    m.cpu.a, m.cpu.ix, m.cpu.d, m.cpu.e = 0xFF, 0x9000, 0, 6
    m.cpu.f = 0                                       # VERIFY
    m.call(R_LD)
    check(m.pico_out[3] == 2, "R_LD: carry clear: PMR1 2 (VERIFY)")

    # --- the model itself: a write to an owned chunk with its HSR bit clear is caught ---
    m = Machine(rom)
    m.own[6] = 2
    m.write(0xC000, 1)
    caught = bool(m.faults)
    Machine.every.remove(m)
    check(caught, "the model flags a write to an owned chunk whose HSR bit is clear")

    faults = sorted(set(f for mm in Machine.every for f in mm.faults))
    check(not faults, "no HSR leaks, no window with interrupts on, none in chunks 0-3")
    for f in faults:
        print("   ", f)
    print("\n%d/%d passed" % (sum(results), len(results)))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
