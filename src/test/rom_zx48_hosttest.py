"""Host-side check of the TS-Pico ZX Spectrum ROM v3 -- CPython, no Pico.

src/rom/TSPICO-ZX48-V3.BIN is the ZX v2 ROM (ROMs/TSPICO-ZX48-V2.BIN) plus
src/rom/patches/tspico-zx48-v3.asm: LOAD "tpi:name" in ZX48 mode.

Two parts:

  * the image: the base really is v2, only the call site at 0631h, the
    banner digit and the new code changed, the new code went into space
    that was free (FFh) in v2, and -- with sjasmplus installed -- the
    committed image is exactly what the source builds;

  * the code: a small Z80 interpreter (just the instructions this code and
    v2's WAIT_RDY use, with T-state counts) runs the NEW BYTES from the
    image, entered at the patched CALL in SA-ALL (0631h), against a scripted Pico
    on ports 0Eh/0Fh. The stock ROM routines it calls (STK-FETCH,
    CHAN-OPEN, PR-STRING, BREAK-KEY, BC-SPACES, RST 10h, ERROR-2's SET-STK)
    are stubbed at their addresses. It checks the stack comes back
    balanced, the bytes on the wire, their spacing, the message printed
    and the report raised.

It can't check the rest of the Spectrum ROM or real bus timing; that is
for hardware.

Run:  python3 src/test/rom_zx48_hosttest.py
"""

import os
import shutil
import subprocess
import sys
import tempfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
BASE = os.path.join(REPO, "ROMs", "TSPICO-ZX48-V2.BIN")
PATCHED = os.path.join(REPO, "src", "rom", "TSPICO-ZX48-V3.BIN")
ASM = os.path.join(REPO, "src", "rom", "patches", "tspico-zx48-v3.asm")

V2_CRC = "B3D40C73"
NEW_CODE, NEW_END = 0x38B8, 0x3D00
CALL_SITE = 0x0631

STK_FETCH, CHAN_OPEN, PR_STRING = 0x2BF1, 0x1601, 0x203C
BREAK_KEY, SET_STK = 0x1F54, 0x16C5
T_ADDR, CH_ADD, X_PTR, ERR_SP = 0x5C74, 0x5C5D, 0x5C5F, 0x5C3D
IY = 0x5C3A
STMT_RET = 0x1B76
MHZ = 3.5                       # T-states per microsecond

results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg)


# ---- a Z80, just enough of one ----------------------------------------------

class Stop(Exception):
    pass


class Z80:
    def __init__(self, rom, pico):
        self.m = bytearray(65536)
        self.m[:16384] = rom
        self.pico = pico
        self.a = self.b = self.c = self.d = self.e = self.h = self.l = 0
        self.zf = self.cf = False
        self.sp = 0xFF00
        self.pc = 0
        self.t = 0
        self.printed = bytearray()
        self.channel = None
        self.ws = 0xC000            # BC-SPACES hands out room from here
        self.exit = None

    # registers
    def bc(self):
        return self.b << 8 | self.c

    def de(self):
        return self.d << 8 | self.e

    def hl(self):
        return self.h << 8 | self.l

    def set_bc(self, v):
        self.b, self.c = v >> 8 & 0xFF, v & 0xFF

    def set_de(self, v):
        self.d, self.e = v >> 8 & 0xFF, v & 0xFF

    def set_hl(self, v):
        self.h, self.l = v >> 8 & 0xFF, v & 0xFF

    def w(self, a):
        return self.m[a] | self.m[a + 1] << 8

    def push(self, v):
        self.sp = (self.sp - 2) & 0xFFFF
        self.m[self.sp], self.m[self.sp + 1] = v & 0xFF, v >> 8

    def pop(self):
        v = self.w(self.sp)
        self.sp = (self.sp + 2) & 0xFFFF
        return v

    def fetch(self):
        v = self.m[self.pc]
        self.pc = (self.pc + 1) & 0xFFFF
        return v

    def fetch16(self):
        v = self.fetch()
        return v | self.fetch() << 8

    def rel(self):
        d = self.fetch()
        return d - 256 if d > 127 else d

    def logic(self, v):
        self.a = v & 0xFF
        self.zf, self.cf = self.a == 0, False

    def compare(self, v):
        r = self.a - v
        self.zf, self.cf = (r & 0xFF) == 0, r < 0
        return r & 0xFF

    def ret(self):
        self.pc = self.pop()

    # the stock ROM routines this code calls
    def stub(self):
        pc = self.pc
        if pc == STK_FETCH:
            self.set_de(self.string_at)
            self.set_bc(self.string_len)
        elif pc == CHAN_OPEN:
            self.channel = self.a
        elif pc == PR_STRING:
            self.printed += self.m[self.de():self.de() + self.bc()]
        elif pc == BREAK_KEY:
            self.cf = not self.pico.break_now(self.t)
        elif pc == 0x0030:                      # BC-SPACES
            self.set_de(self.ws)
            self.ws += self.bc()
        elif pc == 0x0010:                      # RST 10h
            self.printed.append(self.a)
        elif pc == SET_STK:
            raise Stop("report")
        elif pc == STMT_RET:
            raise Stop("ok")
        elif pc == 0x0634:
            raise Stop("stock")                 # back in SA-ALL after the CALL
        else:
            return False
        if pc not in (SET_STK, STMT_RET, 0x0634):
            self.ret()
        self.t += 20
        return True

    def run(self, limit_t):
        try:
            while self.t < limit_t:
                if self.stub():
                    continue
                self.step()
            raise Stop("hung")
        except Stop as e:
            self.exit = str(e)

    def step(self):
        op = self.fetch()
        t = 4
        if op == 0xCD:
            a = self.fetch16(); self.push(self.pc); self.pc = a; t = 17
        elif op == 0xC3:
            self.pc = self.fetch16(); t = 10
        elif op == 0xC9:
            self.ret(); t = 10
        elif op in (0xC0, 0xC8, 0xD8):
            cond = {0xC0: not self.zf, 0xC8: self.zf, 0xD8: self.cf}[op]
            t = 5
            if cond:
                self.ret(); t = 11
        elif op in (0xD7, 0xF7):
            self.push(self.pc); self.pc = 0x10 if op == 0xD7 else 0x30; t = 11
        elif op in (0x3E, 0x06, 0x16):
            v = self.fetch(); t = 7
            setattr(self, {0x3E: "a", 0x06: "b", 0x16: "d"}[op], v)
        elif op == 0x01:
            self.set_bc(self.fetch16()); t = 10
        elif op == 0x21:
            self.set_hl(self.fetch16()); t = 10
        elif op == 0x78:
            self.a = self.b
        elif op == 0x79:
            self.a = self.c
        elif op == 0x4F:
            self.c = self.a
        elif op == 0x41:
            self.b = self.c
        elif op == 0x1A:
            self.a = self.m[self.de()]; t = 7
        elif op == 0x12:
            self.m[self.de()] = self.a; t = 7
        elif op == 0xB7:
            self.logic(self.a)
        elif op == 0xB1:
            self.logic(self.a | self.c)
        elif op == 0xB3:
            self.logic(self.a | self.e)
        elif op == 0xB5:
            self.logic(self.a | self.l)
        elif op == 0x7C:
            self.a = self.h
        elif op == 0x2B:
            self.set_hl((self.hl() - 1) & 0xFFFF); t = 6
        elif op == 0xF6:
            self.logic(self.a | self.fetch()); t = 7
        elif op == 0xE6:
            self.logic(self.a & self.fetch()); t = 7
        elif op == 0xFE:
            self.compare(self.fetch()); t = 7
        elif op == 0xBE:
            self.compare(self.m[self.hl()]); t = 7
        elif op == 0xD6:
            self.a = self.compare(self.fetch()); t = 7
        elif op == 0x13:
            self.set_de((self.de() + 1) & 0xFFFF); t = 6
        elif op == 0x23:
            self.set_hl((self.hl() + 1) & 0xFFFF); t = 6
        elif op == 0x0B:
            self.set_bc((self.bc() - 1) & 0xFFFF); t = 6
        elif op == 0x15:
            self.d = (self.d - 1) & 0xFF; self.zf = self.d == 0
        elif op == 0x37:
            self.cf = True
        elif op == 0x10:
            d = self.rel(); self.b = (self.b - 1) & 0xFF; t = 8
            if self.b:
                self.pc = (self.pc + d) & 0xFFFF; t = 13
        elif op in (0x18, 0x20, 0x28, 0x30):
            d = self.rel()
            cond = {0x18: True, 0x20: not self.zf, 0x28: self.zf, 0x30: not self.cf}[op]
            t = 7
            if cond:
                self.pc = (self.pc + d) & 0xFFFF; t = 12
        elif op in (0xC5, 0xD5, 0xF5):
            v = {0xC5: self.bc(), 0xD5: self.de(),
                 0xF5: self.a << 8 | (0x40 if self.zf else 0) | (1 if self.cf else 0)}[op]
            self.push(v); t = 11
        elif op in (0xC1, 0xD1, 0xE1, 0xF1):
            v = self.pop(); t = 10
            if op == 0xC1:
                self.set_bc(v)
            elif op == 0xD1:
                self.set_de(v)
            elif op == 0xE1:
                self.set_hl(v)
            else:
                self.a, self.zf, self.cf = v >> 8, bool(v & 0x40), bool(v & 1)
        elif op == 0xDB:
            port = self.fetch(); self.t += 11
            self.a = self.pico.z80_in(port, self.t); return
        elif op == 0xD3:
            port = self.fetch(); self.t += 11
            self.pico.z80_out(port, self.a, self.t); return
        elif op == 0x3A:
            self.a = self.m[self.fetch16()]; t = 13
        elif op == 0x2A:
            self.set_hl(self.w(self.fetch16())); t = 16
        elif op == 0x22:
            a = self.fetch16(); self.m[a], self.m[a + 1] = self.l, self.h; t = 16
        elif op == 0xED and self.m[self.pc] == 0x7B:
            self.pc += 1; self.sp = self.w(self.fetch16()); t = 20
        elif op == 0xFD and self.m[self.pc] == 0x77:
            self.pc += 1; self.m[(IY + self.rel()) & 0xFFFF] = self.a; t = 19
        else:
            raise AssertionError("opcode %02X at %04X not in this interpreter"
                                 % (op, (self.pc - 1) & 0xFFFF))
        self.t += t


# ---- the Pico, scripted -----------------------------------------------------

class Pico:
    """Ports 0Eh / 0Fh as the firmware's 'T' handler drives them: every Z80
    OUT drops READY (PIO auto-busy); READY after 'T', then after the whole
    name, with the reply queued first. An IN from an empty TX reads 00."""

    def __init__(self, reply=None, answer_t=True, reply_after_us=500, break_at_us=None):
        self.reply = reply              # (status, message) or None = never replies
        self.answer_t = answer_t
        self.reply_after = reply_after_us * MHZ
        self.break_at = None if break_at_us is None else break_at_us * MHZ
        self.ready_at = None            # T-state when READY rises
        self.tx = []
        self.rx = []
        self.out_t = []
        self.in_t = []
        self.underrun = 0

    def z80_out(self, port, v, t):
        assert port == 0x0E, "OUT to %02Xh" % port
        self.rx.append(v)
        self.out_t.append(t)
        self.ready_at = None
        if self.rx == [0x54]:
            if self.answer_t:
                self.ready_at = t + 300 * MHZ   # dispatch, then READY
        elif len(self.rx) >= 3 and len(self.rx) == 3 + self.rx[2]:
            if self.reply is not None:
                st, msg = self.reply
                self.tx = [st, len(msg)] + list(msg)
                self.ready_at = t + self.reply_after

    def z80_in(self, port, t):
        if port == 0x0F:
            return 0xFF if self.ready_at is not None and t >= self.ready_at else 0x00
        self.in_t.append(t)
        if not self.tx:
            self.underrun += 1
            return 0x00
        return self.tx.pop(0)

    def break_now(self, t):
        return self.break_at is not None and t >= self.break_at


def run(rom, name, t_addr=1, **pico_kw):
    pico = Pico(**pico_kw)
    z = Z80(rom, pico)
    s = name.encode()
    z.m[0x8000:0x8000 + len(s)] = s
    z.string_at, z.string_len = 0x8000, len(s)
    z.m[T_ADDR] = t_addr
    z.m[CH_ADD], z.m[CH_ADD + 1] = 0x34, 0x12
    z.m[IY] = 0xFF                          # ERR_NR: no error
    # the statement loop's return, then SA-ALL's CALL at 0631h
    z.push(STMT_RET)
    sp_stmt = z.sp
    z.m[ERR_SP], z.m[ERR_SP + 1] = 0x00, 0xFE
    z.pc = CALL_SITE
    z.run(int(40e6 * MHZ))                  # 40 s of Z80 time at most
    return z, pico, sp_stmt


def main():
    base = open(BASE, "rb").read()
    rom = open(PATCHED, "rb").read()

    print("the image")
    check("%08X" % zlib.crc32(base) == V2_CRC, "base is the ZX v2 ROM (crc32 %s)" % V2_CRC)
    check(len(rom) == 16384, "v3 is 16K")
    diff = [i for i in range(16384) if rom[i] != base[i]]
    outside = [i for i in diff if not (CALL_SITE <= i < CALL_SITE + 3 or i == 0x38B7
                                       or 0x3874 <= i < 0x388A or NEW_CODE <= i < NEW_END)]
    check(not outside, "only the call site, WAIT_RDY, the banner digit and the new code changed (%s)"
          % [hex(i) for i in outside[:5]])
    check(base[CALL_SITE:CALL_SITE + 3] == bytes.fromhex("CDF12B")
          and rom[CALL_SITE:CALL_SITE + 3] == bytes.fromhex("CDB838"),
          "0631h: CALL STK-FETCH became CALL 38B8h")
    check(all(b == 0xFF for b in base[NEW_CODE:NEW_END]), "38B8h-3CFFh was free (FFh) in v2")
    check(base[0x38B7] == 0xB2 and rom[0x38B7] == 0xB3, "banner: 'ZX v2' -> 'ZX v3'")
    check(rom[0x388A:0x3891] == base[0x388A:0x3891], "SAVE_WAIT at 388Ah untouched")
    if shutil.which("sjasmplus"):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "src", "rom", "patches")
            os.makedirs(src)
            os.makedirs(os.path.join(tmp, "ROMs"))
            shutil.copy(ASM, src)
            shutil.copy(BASE, os.path.join(tmp, "ROMs"))
            subprocess.run(["sjasmplus", "--nologo", "--msg=err", "-Wno-fileorg",
                            "patches/tspico-zx48-v3.asm"],
                           cwd=os.path.join(tmp, "src", "rom"), check=True)
            built = open(os.path.join(tmp, "src", "rom", "TSPICO-ZX48-V3.BIN"), "rb").read()
            check(built == rom, "the committed image is what the source builds")
    else:
        print("  SKIP  sjasmplus not installed: rebuild check")

    print("WAIT_RDY keeps DE (v2 left D = 4: LOAD/SAVE moved 0400h + E bytes)")
    for ready, what in ((True, "READY"), (False, "timeout")):
        z = Z80(rom, Pico())
        z.pico.ready_at = 1000 if ready else None
        z.set_de(0x1B00)                    # a 6912-byte block's length
        z.m[0xFE00:0xFE02] = b"\x00\x00"
        z.push(0x0566)                      # LD-BYTES' RET NC after the call
        z.pc = 0x3874
        try:
            while z.pc != 0x0566 and z.t < 20e6 * MHZ:
                z.step()
        except AssertionError as e:
            check(False, str(e))
        secs = z.t / MHZ / 1e6
        check(z.pc == 0x0566 and z.cf == ready and z.de() == 0x1B00
              and (ready or 3 < secs < 5),
              "%s: carry %s, DE still 1B00h (%04Xh)%s"
              % (what, z.cf, z.de(), "" if ready else ", after %.1f s" % secs))

    print("names that aren't tpi: take the stock path")
    for name in ("hello", "tpi:", "tpx:abc", "ab"):
        z, p, sp = run(rom, name)
        check(z.exit == "stock" and z.de() == 0x8000 and z.bc() == len(name)
              and z.sp == sp and not p.rx,
              "%r: back in SA-ALL with DE, BC from STK-FETCH, stack as it was, nothing sent" % name)
    z, p, sp = run(rom, "tpi:" + "x" * 300)
    check(z.exit == "stock" and not p.rx, "a 304-character tpi: name: stock path (it's cut to 10)")

    print('LOAD "TPI:Manic.tap" -- mounted')
    msg = b"File mounted OK manic.tap"
    z, p, sp = run(rom, "TPI:Manic.tap", reply=(0xFF, msg))
    check(z.exit == "ok" and z.sp == sp + 2,
          "0 OK: returns to the statement loop with the stack balanced (%s)" % z.exit)
    check(p.rx == [0x54, 1, 9] + list(b"Manic.tap"),
          "on the wire: 'T', op 1 (LOAD), length 9, the name after 'tpi:' (%r)" % bytes(p.rx))
    gaps = [(b - a) / MHZ for a, b in zip(p.out_t[1:], p.out_t[2:])]
    check(min(gaps) >= 40, "name bytes >= 40 us apart for the 4-deep RX FIFO (min %.0f us)" % min(gaps))
    gaps = [(b - a) / MHZ for a, b in zip(p.in_t, p.in_t[1:])]
    check(min(gaps) >= 35 and p.underrun == 0,
          "reply bytes read >= 35 us apart, none from an empty TX (min %.0f us)" % min(gaps))
    check(z.channel == 2 and bytes(z.printed) == msg + b"\r",
          "message printed on the upper screen, then ENTER (%r)" % bytes(z.printed))
    check(z.m[IY] == 0xFF, "no report")

    print("an error from the Pico: F, with its message")
    z, p, sp = run(rom, "tpi:nothere.tap", reply=(0x0E, b"File does not exist: nothere.tap"))
    check(z.exit == "report" and z.m[IY] == 0x0E and z.sp == 0xFE00
          and z.w(X_PTR) == 0x1234 and z.printed.startswith(b"File does not exist"),
          "message printed, then ERR_NR 0Eh (F), SP from ERR_SP, X_PTR = CH_ADD, into SET-STK")

    print("no message")
    z, p, sp = run(rom, "tpi:3", reply=(0xFF, b""))
    check(z.exit == "ok" and z.sp == sp + 2 and not z.printed, "0 OK, nothing printed")

    print('SAVE "tpi:dir" sends op 0 (the Pico refuses it)')
    z, p, sp = run(rom, "tpi:dir", t_addr=0, reply=(0x19, b"Only LOAD in ZX48 mode"))
    check(p.rx[:2] == [0x54, 0] and z.m[IY] == 0x19, "op 0; Report Q (19h)")

    print("no Pico, or firmware without 'T'")
    z, p, sp = run(rom, "tpi:x.tap", answer_t=False)
    secs = z.t / MHZ / 1e6
    check(z.exit == "report" and z.m[IY] == 0x12 and p.rx == [0x54] and 3 < secs < 5,
          "Report J after v2's WAIT_RDY (%.1f s), nothing more sent" % secs)

    print("the Pico never replies")
    z, p, sp = run(rom, "tpi:x.tap", reply=None, break_at_us=2_000_000)
    secs = z.t / MHZ / 1e6
    check(z.exit == "report" and z.m[IY] == 0x0C and secs < 2.5,
          "BREAK: Report D within ~0.25 s of the key (%.2f s)" % secs)
    z, p, sp = run(rom, "tpi:x.tap", reply=None)
    secs = z.t / MHZ / 1e6
    check(z.exit == "report" and z.m[IY] == 0x12 and 20 < secs < 40,
          "no BREAK: Report J after %.0f s" % secs)
    z, p, sp = run(rom, "tpi:big.tap", reply=(0xFF, b"ok"), reply_after_us=8_000_000)
    check(z.exit == "ok", "a slow mount (8 s, a big file copied to flash) still completes")

    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
