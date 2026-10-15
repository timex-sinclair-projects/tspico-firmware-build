#!/usr/bin/env python3
"""Check that the v3 card's core 1 never touches flash, from the linked ELF.

Core 1 serves the 2068's bus, the modem and speech from RAM. A flash read
(an instruction fetch, or data in .rodata) stalls while core 0 erases or
programs flash, the APB/XIP stall of issue #254, and core 1 has about 600 ns
for an IN. A source-level rule (__not_in_flash_func, U8251_FN, SP0256_DATA,
`volatile` on a local string) is only as good as what gcc does with it: in
#305 a `static char s_ready[]` that was never written went to .rodata. So
this reads firmware.elf itself:

1. Walk core 1's call graph from ROOTS: every direct branch (bl, b.w, b,
   cbz...) out of a function, and every literal-pool word, or movw/movt
   pair, that is the address of a function (a function pointer, a veneer).
2. Every function reached must be in RAM (0x20000000 and up).
3. No function reached may hold a flash address (FLASH_LO..FLASH_HI): a
   literal-pool word, a movw/movt pair, or a branch target. That is a
   flash function called (memcpy, __aeabi_*, an SDK helper left out of
   line), or flash data read (.rodata, .flashdata, a const table).

What it can't see: a pointer to flash held in RAM at run time (core 0 could
store one in a struct core 1 reads) and indirect calls (blx rN), which it
lists. Core 1's exception vectors other than PIO2_IRQ_0 are core 0's and in
flash; a fault on core 1 is already the end.

Usage: check-core1-ram.py firmware.elf [--tools PREFIX] [-v]
Exit status 0: clean; 1: something core 1 reaches is in flash.
"""

import argparse
import bisect
import re
import subprocess
import sys

# Core 1's entry points: core1_main (multicore_launch_core1) and iord_isr,
# the one handler in core 1's own vector table (tsbus.c, core1_vectors).
ROOTS = ("core1_main", "iord_isr")

# Every XIP alias of the flash: cached, uncached, maintenance, cache-as-SRAM.
FLASH_LO, FLASH_HI = 0x10000000, 0x1FFFFFFF
RAM_LO = 0x20000000

FUNC_RE = re.compile(r"^([0-9a-f]{8}) <([^>]+)>:$")
INSN_RE = re.compile(r"^\s*([0-9a-f]+):\s+(\S+)\s*(.*)$")
BRANCH_RE = re.compile(r"^(bl|blx|b|b\.w|b\.n|b[a-z]{2}(\.[nw])?|cbn?z)$")
TARGET_RE = re.compile(r"\b([0-9a-f]{8}) <([^>]+)>")
MOVW_RE = re.compile(r"^(r\d+|ip|lr|sl|fp),\s*#(\d+)")


def run(cmd):
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout


def is_flash(a):
    return FLASH_LO <= a <= FLASH_HI


class Elf:
    def __init__(self, path, prefix):
        # The symbol table: names for addresses, and which symbols are
        # functions (F). .data holds code (.time_critical) as well as
        # variables, so objdump labels both; only an F symbol is a function.
        self.syms = []   # (addr, size, section, name), by address
        fsyms = set()
        for line in run([prefix + "objdump", "-t", path]).splitlines():
            if len(line) < 17 or not re.match(r"[0-9a-f]{8} ", line):
                continue
            f = line[17:].split()
            if len(f) != 3 or f[0] == "*UND*":
                continue
            a, kind = int(line[:8], 16), line[15]
            self.syms.append((a, int(f[1], 16), f[0], f[2]))
            if kind == "F":
                fsyms.add(f[2])
        self.syms.sort()
        self.addrs = [s[0] for s in self.syms]
        # The disassembly, cut at function symbols.
        self.funcs = {}  # name -> (addr, [(addr, mnemonic, operands)])
        self.func_at = {}  # addr -> name
        cur = None
        for line in run([prefix + "objdump", "-d", "--no-show-raw-insn", path]).splitlines():
            m = FUNC_RE.match(line)
            if m:
                a, name = int(m.group(1), 16), m.group(2)
                if name in fsyms:
                    cur = []
                    self.funcs[name] = (a, cur)
                    self.func_at.setdefault(a, name)
                else:
                    cur = None   # a variable in .data, or a mapping label
                continue
            m = INSN_RE.match(line)
            if m and cur is not None:
                cur.append((int(m.group(1), 16), m.group(2), m.group(3)))
        self.starts = sorted(self.func_at)

    def sym(self, a):
        """The symbol a is in, as (name+off, section), or None."""
        i = bisect.bisect_right(self.addrs, a) - 1
        while i >= 0:
            sa, sz, sec, n = self.syms[i]
            if sa <= a < sa + max(sz, 1):
                return (n if a == sa else "%s+0x%x" % (n, a - sa)), sec
            if a - sa > 0x10000:
                break
            i -= 1
        return None

    def name(self, a):
        s = self.sym(a)
        return s[0] if s else "?"

    def refs(self, fname):
        """(kind, address, where) for every address fname uses: "branch"
        (a direct branch's target), "word" (a literal-pool word), "movw/movt"
        (a 32-bit constant built in a register), "indirect" (blx or bx to a
        register: no address)."""
        out = []
        movw = {}
        for a, mn, ops in self.funcs[fname][1]:
            base = mn.split(".")[0]
            if mn == ".word":
                out.append(("word", int(ops.split()[0], 16), a))
            elif BRANCH_RE.match(mn):
                t = TARGET_RE.search(ops)
                if t:
                    out.append(("branch", int(t.group(1), 16), a))
                elif base == "blx":
                    out.append(("indirect", 0, a))
            elif base == "bx" and ops.strip() != "lr":
                out.append(("indirect", 0, a))
            elif base in ("movw", "movt"):
                m = MOVW_RE.match(ops.strip())
                if m:
                    reg, v = m.group(1), int(m.group(2))
                    if base == "movw":
                        movw[reg] = v
                    elif reg in movw:
                        out.append(("movw/movt", (v << 16) | movw.pop(reg), a))
        return out

    def func_of(self, a):
        """The function a is in, or None."""
        i = bisect.bisect_right(self.starts, a) - 1
        if i >= 0:
            f = self.func_at[self.starts[i]]
            insns = self.funcs[f][1]
            if insns and a <= insns[-1][0]:
                return f
        return None

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("elf")
    ap.add_argument("--tools", default="arm-none-eabi-",
                    help="binutils prefix (default arm-none-eabi-)")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="list every function core 1 reaches, and the RAM data it addresses")
    args = ap.parse_args()
    elf = Elf(args.elf, args.tools)

    bad, notes, data = [], [], {}
    seen, todo = set(), []
    for r in ROOTS:
        if r not in elf.funcs:
            bad.append("root %s is not in the ELF (renamed? update ROOTS)" % r)
        else:
            todo.append(r)
    while todo:
        f = todo.pop()
        if f in seen:
            continue
        seen.add(f)
        fa, insns = elf.funcs[f]
        if fa < RAM_LO:
            bad.append("%s is in flash at %08x" % (f, fa))
            continue
        lo, hi = fa, (insns[-1][0] if insns else fa)
        for kind, v, where in elf.refs(f):
            at = "%s (%08x)" % (elf.name(where), where)
            if kind == "indirect":
                notes.append("indirect call or jump in %s: not followed" % at)
                continue
            t = v & ~1
            if lo <= t <= hi:
                continue   # a branch within the function, or a pool word for its own address
            # A branch goes into a function; a word or constant is a function
            # pointer only if it is a function's start with the Thumb bit set.
            if kind == "branch":
                callee = elf.func_of(t)
            else:
                callee = elf.func_at.get(t) if v & 1 else None
            if is_flash(t):
                what = "calls" if kind == "branch" or callee else "reads"
                bad.append("%s %s %s at %08x (%s)" % (at, what, callee or elf.name(t), t, kind))
            elif callee and callee in elf.funcs:
                todo.append(callee)
            elif kind != "branch" and t >= RAM_LO:
                s = elf.sym(v)
                if s:
                    data[s[0].split("+")[0]] = (v, s[1])

    if args.verbose:
        for f in sorted(seen, key=lambda n: elf.funcs[n][0]):
            print("  %08x %s" % (elf.funcs[f][0], f))
        print("data core 1 addresses (RAM):")
        for n, (v, sec) in sorted(data.items(), key=lambda d: d[1][0]):
            print("  %08x %-10s %s" % (v, sec, n))
    for n in notes:
        print("note:", n)
    if bad:
        for b in bad:
            print("FLASH:", b)
        print("core 1 reaches flash: %d problem(s) in %d functions" % (len(bad), len(seen)))
        return 1
    print("core 1 stays in RAM: %d functions from %s, no flash address" % (len(seen), ", ".join(ROOTS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
