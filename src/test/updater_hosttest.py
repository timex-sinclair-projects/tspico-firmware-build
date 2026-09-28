"""Host-side test of the ROM updater's Z80 code -- CPython, no hardware.

Runs src/upgrade/updater.bin in z80core.py on a model of a TS-2068 running
the Spectrum ROM from the TS-Pico's dock bank:

  * memory in 8K chunks: a chunk whose HSR (port F4h) bit is set is the dock
    bank, page 0 of the flash chip (slots 0 and 1: chip address = Z80
    address); otherwise chunks 0-1 are the home ROM, flash slot 1 (chip
    address 8000h + address), and chunks 2-7 are RAM;
  * the flash chip, an SST39SF040: command sequences on A14-A0 = 5555h /
    2AAAh, 4K sector erase, byte program (bits only go 1 -> 0), and a busy
    time during which EVERY read of the chip returns status (DQ7 = the
    complement of the data being written) -- with writes that never reach
    it when the P10 jumper is missing, and optional stuck bits;
  * the Pico: a request is a port-0Fh write, its arguments come on 0Eh,
    READY (0Fh bit 6) goes up when the reply is queued, every OUT drops it.

It checks the stack comes back balanced where the code returns to BASIC,
that no instruction is ever fetched from the flash chip after the start
(the chip is busy during writes; a fetch then would crash a real 2068),
the bytes ending up in flash, the statuses the Pico gets, the text on the
screen, and the I/O cadence.

Run:  python3 src/test/updater_hosttest.py
"""

import os
import shutil
import subprocess
import sys
import tempfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from z80core import Z80, Halted                                  # noqa: E402

UPDATER = os.path.join(REPO, "src", "upgrade", "updater.bin")
MHZ = 3.5
BASIC_RET = 0x1303                  # where RANDOMIZE USR returns to, in the ROM
results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg)


class Flash:
    """An SST39SF040 as far as the updater can tell."""

    def __init__(self, image, we=True, stuck=None):
        self.m = bytearray(image)
        self.we = we                # False: P10 not fitted, writes never arrive
        self.stuck = stuck or {}    # chip address -> bits that won't clear
        self.seq = []
        self.busy_until = 0
        self.busy_dq7 = 0
        self.log = []               # ("erase", addr) / ("prog", addr)

    def busy(self, t):
        return t < self.busy_until

    def read(self, a, t):
        if self.busy(t):
            return self.busy_dq7 | (0x40 if (t // 50) & 1 else 0)   # DQ7 + toggling DQ6
        return self.m[a]

    def write(self, a, v, t):
        if not self.we or self.busy(t):
            return
        k = a & 0x7FFF
        self.seq.append((k, v))
        s = self.seq[-6:]
        if len(s) >= 4 and s[-4:-1] == [(0x5555, 0xAA), (0x2AAA, 0x55), (0x5555, 0xA0)]:
            new = self.m[a] & v | self.stuck.get(a, 0) & self.m[a]
            self.m[a] = new
            self.busy_until = t + int(20 * MHZ)
            self.busy_dq7 = (~v) & 0x80
            self.log.append(("prog", a))
            self.seq = []
        elif len(s) == 6 and s[:5] == [(0x5555, 0xAA), (0x2AAA, 0x55), (0x5555, 0x80),
                                       (0x5555, 0xAA), (0x2AAA, 0x55)] and v == 0x30:
            base = a & ~0xFFF
            self.m[base:base + 0x1000] = b"\xFF" * 0x1000
            self.busy_until = t + int(25000 * MHZ)
            self.busy_dq7 = 0
            self.log.append(("erase", base))
            self.seq = []


class Pico:
    """The upgrade firmware's service loop, as the Z80 sees it."""

    def __init__(self, images, bad_xor=0, answer=True):
        self.images = images        # {1: 32K, 0: 16K}
        self.bad_xor = bad_xor      # this many replies to 'R' come with a wrong XOR
        self.answer = answer
        self.tx = []
        self.cmd = None
        self.args = []
        self.ready_at = None
        self.statuses = []
        self.out_t = []
        self.in_t = []
        self.underrun = 0

    def out(self, port, v, t):
        self.ready_at = None                        # PIO auto-busy
        if port == 0x0F:
            self.cmd, self.args = v, []
            self.out_t = [t]
        else:
            self.args.append(v)
            self.out_t.append(t)
        need = {ord("I"): 0, ord("R"): 2, ord("S"): 2}.get(self.cmd, 0)
        if self.cmd is not None and len(self.args) == need and self.answer:
            self.reply(t)

    def reply(self, t):
        c, a = chr(self.cmd), self.args
        if c == "I":
            self.tx = list(b"TP") + [1, 0]
        elif c == "R":
            img, blk = a
            data = self.images[img][blk * 256:blk * 256 + 256]
            x = 0
            for b in data:
                x ^= b
            if self.bad_xor:
                self.bad_xor -= 1
                x ^= 0x5A
            self.tx = list(data) + [x]
        elif c == "S":
            self.statuses.append((chr(a[0]), a[1]))
            self.tx = [0]
        self.cmd = None
        self.ready_at = t + int(300 * MHZ)          # Python's reaction time

    def status(self, t):
        return 0xFF if self.ready_at is not None and t >= self.ready_at else 0x00

    def read_data(self, t):
        self.in_t.append(t)
        if not self.tx:
            self.underrun += 1
            return 0
        return self.tx.pop(0)


def run(image, images, we=True, stuck=None, bad_xor=0, answer=True, limit_s=60):
    flash = Flash(image, we=we, stuck=stuck)
    pico = Pico(images, bad_xor=bad_xor, answer=answer)
    ram = bytearray(0x10000)
    code = open(UPDATER, "rb").read()
    ram[0x6000:0x6000 + len(code)] = code
    st = {"hsr": 0x03, "rom_fetch": [], "busy_fetch": []}
    cpu = None

    def chip_addr(a):
        chunk = a >> 13
        if st["hsr"] >> chunk & 1:
            return a                                # dock page 0: slots 0-1
        if chunk < 2:
            return 0x8000 + a                       # home ROM: slot 1
        return None

    def read(a):
        c = chip_addr(a)
        if c is None:
            return ram[a]
        return flash.read(c, cpu.t)

    def write(a, v):
        c = chip_addr(a)
        if c is None:
            ram[a] = v
        else:
            flash.write(c, v, cpu.t)

    def port_in(port):
        p = port & 0xFF
        if p == 0x0F:
            return pico.status(cpu.t)
        if p == 0x0E:
            return pico.read_data(cpu.t)
        return 0xFF

    def port_out(port, v):
        p = port & 0xFF
        if p == 0xF4:
            st["hsr"] = v
        elif p in (0x0E, 0x0F):
            pico.out(p, v, cpu.t)

    cpu = Z80(read, write, port_in, port_out)

    def fetch_hook(a):
        if chip_addr(a) is not None:
            st["rom_fetch"].append(a)
            if flash.busy(cpu.t):
                st["busy_fetch"].append(a)

    # BASIC's RANDOMIZE USR: the ROM font is at 3D00h in the Spectrum ROM, and
    # USR returns to the ROM. Only the start of the updater is called from it.
    cpu.sp = 0xFF40
    cpu.push(BASIC_RET)
    sp0 = cpu.sp
    cpu.pc = 0x6000
    cpu.fetch_hook = fetch_hook
    end = "limit"
    try:
        while cpu.t < limit_s * 1e6 * MHZ:
            if cpu.pc == BASIC_RET:
                end = "basic"
                break
            cpu.step()
    except Halted:
        end = "halt"
    return dict(end=end, cpu=cpu, flash=flash, pico=pico, ram=ram, st=st, sp0=sp0)


def screen_text(ram, row):
    """Read row `row` back off the screen, using the font the updater copied."""
    out = ""
    font = ram[0x7000:0x7300]
    for col in range(32):
        cell = bytes(ram[0x4000 | (row & 0x18) << 8 | (row & 7) << 5 | col | line << 8]
                     for line in range(8))
        ch = " "
        for k in range(96):
            if bytes(font[k * 8:k * 8 + 8]) == cell:
                ch = chr(0x20 + k)
                break
        out += ch
    return out.rstrip()


def main():
    # A 1.5-era board: the 1.5w TS-2068 ROM in slot 1, a Spectrum ROM in slot
    # 0 (ZX v2 stands in for the original: same font at 3D00h), and a pattern
    # everywhere else so a stray write shows.
    rom = lambda *p: open(os.path.join(REPO, *p), "rb").read()
    base = bytearray(bytes((i * 7 + 3) & 0xFF for i in range(0x80000)))
    base[0:0x8000] = rom("ROMs", "TSPICO-ZX48-V2.BIN") + bytes(0x4000)
    base[0x8000:0x10000] = rom("ROMs", "TSPICO-15w-home") + rom("ROMs", "TSPICO-15w-exrom")
    base = bytes(base)
    rom17 = open(os.path.join(REPO, "src", "rom", "TSPICO-SYNC.ROM"), "rb").read()   # ROM 2.0
    zx3 = open(os.path.join(REPO, "src", "rom", "TSPICO-ZX48-V3.BIN"), "rb").read()
    images = {1: rom17, 0: zx3}

    def untouched_except(fl, lo, hi):
        return fl.m[:lo] == base[:lo] and fl.m[hi:] == base[hi:]

    if shutil.which("sjasmplus"):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copy(os.path.join(REPO, "src", "upgrade", "updater.asm"), tmp)
            subprocess.run(["sjasmplus", "--nologo", "--msg=err", "updater.asm"], cwd=tmp, check=True)
            check(open(os.path.join(tmp, "updater.bin"), "rb").read() == open(UPDATER, "rb").read(),
                  "the committed updater.bin is what updater.asm builds")
    else:
        print("  SKIP  sjasmplus not installed: rebuild check")

    print("a normal update")
    r = run(base, images)
    fl, pico = r["flash"], r["pico"]
    check(r["end"] == "halt" and not r["cpu"].iff, "ends halted with interrupts off (%s)" % r["end"])
    check(bytes(fl.m[0x8000:0x10000]) == rom17, "slot 1 holds the TS-2068 ROM (crc32 %08X)"
          % zlib.crc32(bytes(fl.m[0x8000:0x10000])))
    check(bytes(fl.m[0:0x4000]) == zx3, "slot 0's lower 16K holds ZX v3")
    check(fl.m[0x4000:0x8000] == base[0x4000:0x8000] and fl.m[0x10000:] == base[0x10000:],
          "slot 0's upper half and every other slot are untouched")
    check([e for e in fl.log if e[0] == "erase"] ==
          [("erase", 0x8000 + i * 0x1000) for i in range(8)] + [("erase", i * 0x1000) for i in range(4)],
          "slot 1's 8 sectors erased, then slot 0's lower 4")
    check(not r["st"]["busy_fetch"], "no instruction fetched from the chip while it was busy")
    check(r["st"]["rom_fetch"] == [], "no instruction fetched from the chip at all (%d)"
          % len(r["st"]["rom_fetch"]))
    s = pico.statuses
    check(s[0] == ("P", 1) and ("E", 1) in s and ("V", 1) in s and ("P", 0) in s
          and ("V", 0) in s and s[-1] == ("D", 0)
          and len([x for x in s if x[0] == "W"]) == 128 + 64,
          "statuses: P1 E1 W x128 V1, P0 E0 W x64 V0, D (%d)" % len(s))
    check(screen_text(r["ram"], 16).startswith("DONE."), "the screen says %r" % screen_text(r["ram"], 16))
    gaps = [(b - a) / MHZ for a, b in zip(pico.in_t, pico.in_t[1:])]
    check(min(gaps) >= 40 and pico.underrun == 0,
          "replies read >= 40 us apart (min %.0f us), none from an empty TX" % min(gaps))
    secs = r["cpu"].t / MHZ / 1e6
    print("        (%.1f s of Z80 time)" % secs)

    print("P10 not fitted: the flash can't be written")
    r = run(base, images, we=False)
    check(r["end"] == "basic" and r["cpu"].sp == r["sp0"] + 2 and r["st"]["hsr"] == 0x03 and r["cpu"].iff,
          "back to BASIC: stack balanced, HSR 03h (the Spectrum ROM), interrupts on")
    check(bytes(r["flash"].m) == base, "the flash is unchanged")
    check(r["pico"].statuses[-1] == ("X", 2), "the Pico hears X 2 (blocked)")
    check("P10" in screen_text(r["ram"], 17), "the screen says %r" % screen_text(r["ram"], 17))

    print("the Pico's data comes in wrong")
    r = run(base, images, bad_xor=3)
    check(r["end"] == "halt" and bytes(r["flash"].m[0x8000:0x10000]) == rom17,
          "three bad XORs: retried, and the update completes")
    r = run(base, images, bad_xor=10 ** 6)
    check(r["end"] == "basic" and r["pico"].statuses[-1] == ("X", 3)
          and bytes(r["flash"].m[0:0x8000]) == base[0:0x8000],
          "always bad: X 3, back to BASIC, the Spectrum ROM intact")

    def stuck_at(img, start):
        """An address whose byte in img has bit 0 clear: a stuck bit 0 there fails."""
        i = start
        while img[i] & 1:
            i += 1
        return i

    print("a byte that won't program in slot 1")
    r = run(base, images, stuck={0x8000 + stuck_at(rom17, 0x123): 0x01})
    check(r["end"] == "basic" and r["pico"].statuses[-1] == ("X", 4)
          and len([e for e in r["flash"].log if e == ("erase", 0x8000)]) == 2,
          "erased and tried again, then X 4 and back to BASIC")
    check(bytes(r["flash"].m[0:0x8000]) == base[0:0x8000], "the Spectrum ROM, slot 0, is intact")

    print("a byte that won't program in slot 0")
    r = run(base, images, stuck={stuck_at(zx3, 0x123): 0x01})
    check(r["end"] == "halt" and r["pico"].statuses[-1] == ("X", 4)
          and bytes(r["flash"].m[0x8000:0x10000]) == rom17,
          "X 4 and it stops (no ROM to go back to); slot 1 is already new")
    check("finish on" in screen_text(r["ram"], 21), "the screen says %r" % screen_text(r["ram"], 21))

    print("no answer from the Pico")
    r = run(base, images, answer=False)
    check(r["end"] == "basic" and bytes(r["flash"].m) == base
          and "No answer" in screen_text(r["ram"], 16),
          "back to BASIC, nothing changed: %r" % screen_text(r["ram"], 16))

    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
