"""A small Z80 interpreter for host tests -- CPython, no dependencies.

Not cycle-exact and not a full emulator: it decodes the unprefixed opcodes,
the ED group and the CB rotates/shifts/bit operations (no IX/IY), keeps the
flags the code under test branches on (S, Z, H, P/V, N, C), and counts
T-states per instruction closely enough to check delay loops. Memory and
I/O are callbacks, so a test can model banking, flash chips and the Pico.

    cpu = Z80(read=..., write=..., port_in=..., port_out=...)
    cpu.pc = 0x6000
    cpu.step()            # one instruction; cpu.t counts T-states

`fetch_hook(addr)`, if set, is called for every opcode fetch (to catch code
running from memory it mustn't).
"""

R8 = ("b", "c", "d", "e", "h", "l", None, "a")     # index 6 = (HL)


class Halted(Exception):
    pass


def _parity(v):
    v ^= v >> 4
    v ^= v >> 2
    v ^= v >> 1
    return not (v & 1)


class Z80:
    def __init__(self, read, write, port_in, port_out):
        self.read, self.write = read, write
        self.port_in, self.port_out = port_in, port_out
        self.a = self.b = self.c = self.d = self.e = self.h = self.l = 0
        self.f = 0
        self.alt = [0, 0, 0, 0]                     # AF' BC' DE' HL' (as words)
        self.sp = 0xFFFF
        self.pc = 0
        self.iff = False
        self.t = 0
        self.halted = False
        self.fetch_hook = None

    # ---- registers and flags --------------------------------------------
    def get_rp(self, p, af=False):
        if p == 0:
            return self.b << 8 | self.c
        if p == 1:
            return self.d << 8 | self.e
        if p == 2:
            return self.h << 8 | self.l
        return (self.a << 8 | self.f) if af else self.sp

    def set_rp(self, p, v, af=False):
        v &= 0xFFFF
        if p == 0:
            self.b, self.c = v >> 8, v & 0xFF
        elif p == 1:
            self.d, self.e = v >> 8, v & 0xFF
        elif p == 2:
            self.h, self.l = v >> 8, v & 0xFF
        elif af:
            self.a, self.f = v >> 8, v & 0xFF
        else:
            self.sp = v

    def hl(self):
        return self.h << 8 | self.l

    def get_r(self, i):
        if i == 6:
            self.t += 3
            return self.read(self.hl())
        return getattr(self, R8[i])

    def set_r(self, i, v):
        if i == 6:
            self.t += 3
            self.write(self.hl(), v & 0xFF)
        else:
            setattr(self, R8[i], v & 0xFF)

    @property
    def cf(self):
        return bool(self.f & 1)

    @property
    def zf(self):
        return bool(self.f & 0x40)

    def _szp(self, v, c=0, h=0, n=0):
        self.f = (v & 0x80) | (0x40 if v == 0 else 0) | (0x10 if h else 0) \
            | (0x04 if _parity(v) else 0) | (0x02 if n else 0) | (1 if c else 0)

    def cond(self, y):
        f = self.f
        return (not f & 0x40, f & 0x40, not f & 1, f & 1,
                not f & 4, f & 4, not f & 0x80, f & 0x80)[y]

    # ---- memory helpers ----------------------------------------------------
    def fetch(self):
        v = self.read(self.pc)
        self.pc = (self.pc + 1) & 0xFFFF
        return v

    def fetch16(self):
        lo = self.fetch()
        return lo | self.fetch() << 8

    def rel(self):
        d = self.fetch()
        return d - 256 if d > 127 else d

    def push(self, v):
        self.sp = (self.sp - 1) & 0xFFFF
        self.write(self.sp, v >> 8 & 0xFF)
        self.sp = (self.sp - 1) & 0xFFFF
        self.write(self.sp, v & 0xFF)

    def pop(self):
        lo = self.read(self.sp)
        hi = self.read((self.sp + 1) & 0xFFFF)
        self.sp = (self.sp + 2) & 0xFFFF
        return lo | hi << 8

    def r16(self, a):
        return self.read(a) | self.read((a + 1) & 0xFFFF) << 8

    def w16(self, a, v):
        self.write(a, v & 0xFF)
        self.write((a + 1) & 0xFFFF, v >> 8 & 0xFF)

    # ---- ALU ---------------------------------------------------------------
    def alu(self, y, v):
        a = self.a
        c = self.f & 1
        if y in (0, 1):                             # ADD, ADC
            r = a + v + (c if y == 1 else 0)
            self._szp(r & 0xFF, c=r > 0xFF, h=((a & 0xF) + (v & 0xF) + (c if y == 1 else 0)) > 0xF)
            ov = (~(a ^ v) & (a ^ r) & 0x80) != 0
            self.f = (self.f & ~0x04) | (0x04 if ov else 0)
            self.a = r & 0xFF
        elif y in (2, 3, 7):                        # SUB, SBC, CP
            cc = c if y == 3 else 0
            r = a - v - cc
            self._szp(r & 0xFF, c=r < 0, h=((a & 0xF) - (v & 0xF) - cc) < 0, n=1)
            ov = ((a ^ v) & (a ^ r) & 0x80) != 0
            self.f = (self.f & ~0x04) | (0x04 if ov else 0)
            if y != 7:
                self.a = r & 0xFF
        elif y == 4:
            self.a = a & v
            self._szp(self.a, h=1)
        elif y == 5:
            self.a = a ^ v
            self._szp(self.a)
        else:
            self.a = a | v
            self._szp(self.a)

    def inc8(self, v, d):
        r = (v + d) & 0xFF
        c = self.f & 1
        h = ((v & 0xF) + d) > 0xF if d > 0 else (v & 0xF) == 0
        self._szp(r, c=c, h=h, n=d < 0)
        ov = (r == 0x80) if d > 0 else (r == 0x7F)
        self.f = (self.f & ~0x04) | (0x04 if ov else 0)
        return r

    # ---- one instruction ----------------------------------------------------
    def step(self):
        if self.halted:
            raise Halted()
        if self.fetch_hook is not None:
            self.fetch_hook(self.pc)
        op = self.fetch()
        self.t += 4
        x, y, z = op >> 6, (op >> 3) & 7, op & 7
        p, q = y >> 1, y & 1

        if op == 0xCB:
            return self._cb()
        if op == 0xED:
            return self._ed()
        if op in (0xDD, 0xFD):
            raise NotImplementedError("IX/IY at %04X" % ((self.pc - 1) & 0xFFFF))

        if x == 1:
            if op == 0x76:
                self.halted = True
                raise Halted()
            self.set_r(y, self.get_r(z))
            return
        if x == 2:
            self.alu(y, self.get_r(z))
            return
        if x == 0:
            if z == 0:
                if y == 0:
                    return
                if y == 1:
                    af = self.a << 8 | self.f
                    self.a, self.f = self.alt[0] >> 8, self.alt[0] & 0xFF
                    self.alt[0] = af
                    return
                if y == 2:                          # DJNZ
                    d = self.rel()
                    self.b = (self.b - 1) & 0xFF
                    self.t += 4
                    if self.b:
                        self.pc = (self.pc + d) & 0xFFFF
                        self.t += 5
                    return
                d = self.rel()
                self.t += 3
                if y == 3 or self.cond(y - 4):
                    self.pc = (self.pc + d) & 0xFFFF
                    self.t += 5
                return
            if z == 1:
                if q == 0:
                    self.set_rp(p, self.fetch16())
                    self.t += 6
                else:
                    hl, v = self.hl(), self.get_rp(p)
                    r = hl + v
                    self.f = (self.f & 0xC4) | (1 if r > 0xFFFF else 0) \
                        | (0x10 if ((hl & 0xFFF) + (v & 0xFFF)) > 0xFFF else 0)
                    self.set_rp(2, r)
                    self.t += 7
                return
            if z == 2:
                if q == 0:
                    if p == 0:
                        self.write(self.get_rp(0), self.a)
                    elif p == 1:
                        self.write(self.get_rp(1), self.a)
                    elif p == 2:
                        self.w16(self.fetch16(), self.hl())
                        self.t += 12
                    else:
                        self.write(self.fetch16(), self.a)
                        self.t += 6
                else:
                    if p == 0:
                        self.a = self.read(self.get_rp(0))
                    elif p == 1:
                        self.a = self.read(self.get_rp(1))
                    elif p == 2:
                        self.set_rp(2, self.r16(self.fetch16()))
                        self.t += 12
                    else:
                        self.a = self.read(self.fetch16())
                        self.t += 6
                self.t += 3
                return
            if z == 3:
                self.set_rp(p, self.get_rp(p) + (1 if q == 0 else -1))
                self.t += 2
                return
            if z == 4:
                self.set_r(y, self.inc8(self.get_r(y), 1))
                if y == 6:
                    self.t += 1
                return
            if z == 5:
                self.set_r(y, self.inc8(self.get_r(y), -1))
                if y == 6:
                    self.t += 1
                return
            if z == 6:
                n = self.fetch()
                self.set_r(y, n)
                self.t += 3
                return
            # z == 7
            a, c = self.a, self.f & 1
            if y == 0:                              # RLCA
                c = a >> 7
                self.a = (a << 1 | c) & 0xFF
            elif y == 1:                            # RRCA
                c = a & 1
                self.a = a >> 1 | c << 7
            elif y == 2:                            # RLA
                self.a = (a << 1 | c) & 0xFF
                c = a >> 7
            elif y == 3:                            # RRA
                self.a = a >> 1 | c << 7
                c = a & 1
            elif y == 5:                            # CPL
                self.a = a ^ 0xFF
                self.f |= 0x12
                return
            elif y == 6:                            # SCF
                self.f = (self.f & 0xC4) | 1
                return
            elif y == 7:                            # CCF
                self.f = (self.f & 0xC4) | (0 if c else 1)
                return
            else:
                raise NotImplementedError("DAA")
            self.f = (self.f & 0xC4) | c
            return
        # x == 3
        if z == 0:
            self.t += 1
            if self.cond(y):
                self.pc = self.pop()
                self.t += 6
            return
        if z == 1:
            if q == 0:
                self.set_rp(p, self.pop(), af=True)
                self.t += 6
                return
            if p == 0:
                self.pc = self.pop()
                self.t += 6
            elif p == 1:                            # EXX
                for i, rp in enumerate((0, 1, 2)):
                    v = self.get_rp(rp)
                    self.set_rp(rp, self.alt[i + 1])
                    self.alt[i + 1] = v
            elif p == 2:
                self.pc = self.hl()
            else:
                self.sp = self.hl()
                self.t += 2
            return
        if z == 2:
            a = self.fetch16()
            self.t += 6
            if self.cond(y):
                self.pc = a
            return
        if z == 3:
            if y == 0:
                self.pc = self.fetch16()
                self.t += 6
            elif y == 2:
                n = self.fetch()
                self.t += 7
                self.port_out(self.a << 8 | n, self.a)
            elif y == 3:
                n = self.fetch()
                self.t += 7
                self.a = self.port_in(self.a << 8 | n)
            elif y == 4:                            # EX (SP),HL
                v = self.r16(self.sp)
                self.w16(self.sp, self.hl())
                self.set_rp(2, v)
                self.t += 15
            elif y == 5:                            # EX DE,HL
                de = self.get_rp(1)
                self.set_rp(1, self.hl())
                self.set_rp(2, de)
            elif y == 6:
                self.iff = False
            elif y == 7:
                self.iff = True
            return
        if z == 4:
            a = self.fetch16()
            self.t += 6
            if self.cond(y):
                self.push(self.pc)
                self.pc = a
                self.t += 7
            return
        if z == 5:
            if q == 0:
                self.push(self.get_rp(p, af=True))
                self.t += 7
                return
            a = self.fetch16()
            self.push(self.pc)
            self.pc = a
            self.t += 13
            return
        if z == 6:
            self.alu(y, self.fetch())
            self.t += 3
            return
        self.push(self.pc)                          # RST
        self.pc = y * 8
        self.t += 7

    def _cb(self):
        op = self.fetch()
        self.t += 4
        x, y, z = op >> 6, (op >> 3) & 7, op & 7
        v = self.get_r(z)
        if x == 1:                                  # BIT
            r = v & (1 << y)
            self.f = (self.f & 1) | 0x10 | (0x44 if r == 0 else 0) | (r & 0x80)
            return
        if x == 2:
            self.set_r(z, v & ~(1 << y))
            return
        if x == 3:
            self.set_r(z, v | (1 << y))
            return
        c = self.f & 1
        if y == 0:
            c, r = v >> 7, (v << 1 | v >> 7)
        elif y == 1:
            c, r = v & 1, (v >> 1 | (v & 1) << 7)
        elif y == 2:
            r, c = (v << 1 | c), v >> 7
        elif y == 3:
            r, c = (v >> 1 | c << 7), v & 1
        elif y == 4:
            c, r = v >> 7, v << 1
        elif y == 5:
            c, r = v & 1, (v >> 1 | (v & 0x80))
        elif y == 7:
            c, r = v & 1, v >> 1
        else:
            raise NotImplementedError("SLL")
        r &= 0xFF
        self.set_r(z, r)
        self._szp(r, c=c)

    def _ed(self):
        op = self.fetch()
        self.t += 4
        x, y, z = op >> 6, (op >> 3) & 7, op & 7
        p, q = y >> 1, y & 1
        if x == 1:
            if z == 0:                              # IN r,(C)
                v = self.port_in(self.get_rp(0))
                if y != 6:
                    setattr(self, R8[y], v)
                self._szp(v, c=self.f & 1)
                self.t += 4
                return
            if z == 1:                              # OUT (C),r
                self.port_out(self.get_rp(0), 0 if y == 6 else getattr(self, R8[y]))
                self.t += 4
                return
            if z == 2:                              # SBC/ADC HL,rp
                hl, v, c = self.hl(), self.get_rp(p), self.f & 1
                r = hl - v - c if q == 0 else hl + v + c
                self.set_rp(2, r)
                r16 = r & 0xFFFF
                self.f = (0x80 if r16 & 0x8000 else 0) | (0x40 if r16 == 0 else 0) \
                    | (0x02 if q == 0 else 0) | (1 if (r < 0 or r > 0xFFFF) else 0)
                self.t += 7
                return
            if z == 3:
                a = self.fetch16()
                if q == 0:
                    self.w16(a, self.get_rp(p))
                else:
                    self.set_rp(p, self.r16(a))
                self.t += 12
                return
            if op == 0x44:                          # NEG
                v = self.a
                self.a = 0
                self.alu(2, v)
                return
            if op in (0x47, 0x4F, 0x57, 0x5F, 0x46, 0x56, 0x5E, 0x45, 0x4D):
                return                              # LD I,A / IM / RETN: not modelled
        if op in (0xB0, 0xB8):                      # LDIR / LDDR
            d = 1 if op == 0xB0 else -1
            while True:
                self.write(self.get_rp(1), self.read(self.hl()))
                self.set_rp(2, self.hl() + d)
                self.set_rp(1, self.get_rp(1) + d)
                self.set_rp(0, self.get_rp(0) - 1)
                self.t += 21
                if self.get_rp(0) == 0:
                    self.t -= 5
                    break
            self.f &= 0xC1
            return
        raise NotImplementedError("ED %02X" % op)
