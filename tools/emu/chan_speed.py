#!/usr/bin/env python3
"""T-states per character through an r: (and an f:) channel, in ZEsarUX.

Megabank spec, open question 21 (the fast channel entry). A machine-code
loop selects a stream (HOME's CHAN-OPEN, 1230h) and sends N characters with
RST 10h, as PRINT # does. Breakpoints at the loop's start and end bracket it,
and ZRCP's partial T-state counter (reset at the first, read at the second)
gives the exact cost: the emulated CPU's T-states, with no frame counting
(the channel code runs with interrupts off, so FRAMES would miss ticks).
The same loop with each RST 10h replaced by a CALL to a RET is the overhead,
subtracted from both.

Per character, then, is everything RST 10h costs from HOME's PRINT-OUT
through the channel record's stub, the module, the board and back.

    ZESARUX=/path/to/zesarux-with-megabank python3 tools/emu/chan_speed.py [N]

Builds build/TSPICO-mb.ROM unless TSPICO_ROM names one. Prints a line per
case: T-states a character and microseconds at 3.528 MHz.
"""

import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

if "TSPICO_ROM" not in os.environ:
    subprocess.run([sys.executable, os.path.join(REPO, "tools", "build-rom.py"), "--megabank"],
                   check=True, stdout=subprocess.DEVNULL)
    os.environ["TSPICO_ROM"] = os.path.join(REPO, "build", "TSPICO-mb.ROM")
os.environ.setdefault("MEGABANK", "1")
os.environ["TSPICO_HOST"] = os.path.join(HERE, "megabank_host.py")
os.environ.setdefault("MEGABANK_HOST_LOG", "/tmp/megabank_host.jsonl")

sys.path.insert(0, HERE)
import session as S                                    # noqa: E402

FORMAT, OPENH, CLOSEH, CLEAR, RANDOMIZE, USR, POKE = 0xD0, 0xD3, 0xD4, 0xFD, 0xF9, 0xC0, 0xF4
CODE = 60000                     # above CLEAR 59999
CLOCK = 3.528e6                  # the TS-2068's Z80


def loop(stream, n, char=ord("x"), rst=True):
    """LD A,stream / CALL 1230h / LD BC,n / START: NOP / L: PUSH BC /
    LD A,char / RST 10h (or CALL to a RET) / POP BC / DEC BC / LD A,B / OR C /
    JR NZ,L / END: RET. Returns (bytes, START, END): each passed once."""
    c = bytearray([0x3E, stream, 0xCD, 0x30, 0x12, 0x01, n & 0xFF, n >> 8])
    start = CODE + len(c)
    c.append(0x00)
    body = [0xC5, 0x3E, char]
    body += [0xD7, 0x00, 0x00] if rst else [0xCD, 0, 0]     # RST 10h + 2 NOPs, or CALL RET
    body += [0xC1, 0x0B, 0x78, 0xB1]
    c += bytes(body)
    c += bytes([0x20, (-(len(body) + 2)) & 0xFF])
    end = CODE + len(c)
    c += bytes([0xC9])
    if not rst:
        ret = CODE + len(c) - 1                              # the RET at END
        i = c.index(0xCD, start - CODE)
        c[i + 1:i + 3] = bytes((ret & 0xFF, ret >> 8))
    return bytes(c), start, end


def timed(s, code, start, end):
    """Run the loop; the T-states from START to END. Breakpoint actions
    copy ZEsarUX's partial T-state counter into var0 and var1 as the CPU
    passes them (nothing stops)."""
    s.poke(CODE, code)
    s.cmd("enable-breakpoints")
    s.cmd("set-breakpoint 1 PC=%d" % start)
    s.cmd("set-breakpointaction 1 let var0=TSTATESP")
    s.cmd("set-breakpoint 2 PC=%d" % end)
    s.cmd("set-breakpointaction 2 let var1=TSTATESP")
    t = s.run(RANDOMIZE, USR, "%d" % CODE, timeout=600)
    assert "0 OK" in t, t
    v0 = int(s.cmd("evaluate var0").split()[-1])
    v1 = int(s.cmd("evaluate var1").split()[-1])
    s.cmd("disable-breakpoints")
    return v1 - v0


class Out(list):
    def append(self, x):
        super().append(x)
        print("  %-42s %8.0f T  %7.1f us" % (x[0], x[1], x[1] / CLOCK * 1e6), flush=True)


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    with S.Session() as s:
        t = s.run(FORMAT, '"r:"')
        assert "0 OK" in t, t
        s.run(CLEAR, "59999")
        out = Out()
        c, a, b = loop(2, n, rst=False)
        base = timed(s, c, a, b)
        out.append(("loop overhead", base / n))
        t = s.run(OPENH, '4,"r:speed","w"')
        assert "0 OK" in t, t
        c, a, b = loop(4, n)
        tr = timed(s, c, a, b)
        out.append(("r: text, a stream file (PRINT #4;\"x\";)", (tr - base) / n))
        c, a, b = loop(4, n, char=13)
        tc = timed(s, c, a, b)
        out.append(("r: CR (with the write-back)", (tc - base) / n))
        s.run(CLOSEH, "4")
        t = s.run(OPENH, '5,"f:speed.txt","w"')
        if "0 OK" in t:
            c, a, b = loop(5, n)
            tf = timed(s, c, a, b)
            out.append(("f: text (64-byte buffer, tpi:chwr)", (tf - base) / n))
            s.run(CLOSEH, "5")


if __name__ == "__main__":
    main()
