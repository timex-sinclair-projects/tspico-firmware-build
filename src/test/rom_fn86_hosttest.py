"""ROM 2.3's string reader and function $86 loop in the Z80 interpreter (#227, #228).

Runs the built EXROM against a model Pico (the status port always READY, the
data port a queue the model refills when the Z80 sends a key) and checks:

  #228, PRINT_STRING_FROM_PICO ($045F -> the module's PS_READ):
    - the parameter bytes after INK..OVER (one) and AT/TAB (two) reach
      RST 10h whatever their value, 00h and 03h included;
    - bytes of 80h and above are printed, not taken for the end;
    - 00h ends the text with carry clear, 03h with carry set.
  #227, function $86:
    - a key goes to the Pico as typed ('n', not 'N');
    - after N the ROM waits for READY and reads on: the Pico's echo and 03h
      end the loop, and nothing is left unread;
  ROM 2.0 (TSPICO-SYNC.ROM, the same v1.1 reader and loop) for contrast:
    the text stops at INK 0, a key goes upper case, N ends the loop at once.

HOME is not modelled, so the calls into it are trapped: $05FA (print A through
RST 10h) records A; $04F1 (open the main screen) and $03C1 (KEY-SCAN, DE = FFFFh:
no key held) return; BRK_TEST ($2327, which reads IY) says no BREAK; and
POLL_KEYPRESS ($0546) is entered past its IY prologue at $0566 with a key in
LAST_K, so the case logic under test runs as it is in the ROM.

Uses the committed slot-1 image, src/rom/TSPICO-22.ROM (CI checks it is what
tools/build-rom.py builds). Run:
    python3 src/test/rom_fn86_hosttest.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
from z80core import Z80                                          # noqa: E402

ROM23 = os.path.join(REPO, "src", "rom", "TSPICO-22.ROM")
ROM20 = os.path.join(REPO, "src", "rom", "TSPICO-SYNC.ROM")
DONE = 0xFF00
LAST_K = 0x5C08
PRINT_A = 0x05FA
OPEN_MAIN = 0x04F1
KEY_SCAN = 0x03C1
BRK_TEST = 0x2327
POLL_KEYPRESS = 0x0546
POLL_TAIL = 0x0566          # RET Z / LD A,(LAST_K) / AND 7Fh / the case test
READER = 0x045F             # PRINT_STRING_FROM_PICO
FN_86 = 0x21E3              # function $86, after the chain has read the $86

results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg)


def run(rom, pc, tx, keys=(), replies=(), a=0):
    """Run EXROM code from pc until it returns. tx: the bytes in the Pico's TX.
    keys: what the user types at each key wait. replies: what the Pico queues
    after each key the Z80 sends. Returns (returned, carry, printed, sent, left)."""
    mem = bytearray(65536)
    mem[0:0x4000] = rom[0x4000:0x8000]                    # the EXROM paged in
    tx = list(tx)
    keys = list(keys)
    replies = [list(r) for r in replies]
    printed, sent = [], []

    def port_in(port):
        p = port & 0xFF
        if p == 0x0F:
            return 0xFF                                   # READY, IDLE, not recovered
        if p == 0x0E:
            return tx.pop(0) if tx else 0                 # an empty FIFO reads 00h
        return 0xFF                                       # no key down

    def port_out(port, v):
        if port & 0xFF == 0x0E:
            sent.append(v)
            if replies:
                tx.extend(replies.pop(0))

    cpu = Z80(lambda ad: mem[ad], lambda ad, v: mem.__setitem__(ad, v) if ad >= 0x4000 else None,
              port_in, port_out)
    cpu.sp = 0xFE00
    cpu.push(DONE)
    cpu.pc = pc
    cpu.a = a
    steps = 0
    while cpu.pc != DONE and steps < 2_000_000:
        steps += 1
        if cpu.pc == PRINT_A:
            printed.append(cpu.a)
            cpu.pc = cpu.pop()
        elif cpu.pc in (OPEN_MAIN,):
            cpu.pc = cpu.pop()
        elif cpu.pc == KEY_SCAN:
            cpu.d = cpu.e = 0xFF
            cpu.pc = cpu.pop()
        elif cpu.pc == BRK_TEST:
            cpu.f |= 1                                    # carry: no BREAK
            cpu.pc = cpu.pop()
        elif cpu.pc == POLL_KEYPRESS:
            mem[LAST_K] = keys.pop(0) if keys else 0
            cpu.f &= ~0x40                                # NZ: a new key
            cpu.pc = POLL_TAIL
        else:
            cpu.step()
    return cpu.pc == DONE, cpu.f & 1, bytes(printed), bytes(sent), bytes(tx)


def main():
    for f in (ROM23, ROM20):
        if not os.path.exists(f):
            print("missing: " + f)
            return 1
    rom23 = open(ROM23, "rb").read()
    rom20 = open(ROM20, "rb").read()

    check(rom23[0x0065] == 0x23, "HOME $0065 is 23h, ROM 2.3 (PEEK 101)")

    # ── #228: the reader ────────────────────────────────────────────────────
    text = bytes([0x41,                     # A
                  0x10, 0x00, 0x11, 0x03,   # INK 0, PAPER 3
                  0x12, 0x00, 0x15, 0x00,   # FLASH 0, OVER 0
                  0x16, 0x03, 0x00,         # AT 3,0
                  0x17, 0x00, 0x03,         # TAB (0, 3)
                  0x0D, 0x80, 0x90, 0xA5,   # ENTER, a block graphic, UDG A, RND
                  0x5A])                    # Z
    ok, c, out, _, left = run(rom23, READER, text + b"\x00junk", a=1)
    check(ok and not c and out == text and left == b"junk",
          "2.3 reader: every parameter and byte >= 80h printed, 00h ends it, carry clear "
          "(printed %s)" % out.hex(" "))
    ok, c, out, _, left = run(rom23, READER, b"AB\x10\x03C\x03junk", a=1)
    check(ok and c and out == b"AB\x10\x03C" and left == b"junk",
          "2.3 reader: a 03h parameter is printed, a 03h after it ends the loop (carry set)")
    ok, c, out, _, _ = run(rom20, READER, text + b"\x00", a=1)
    check(ok and out == b"A\x10",
          "2.0 reader for contrast: INK 0's 00h ends the text (printed %s)" % out.hex(" "))
    ok, c, out, _, _ = run(rom20, READER, b"A\x90B\x00", a=1)
    check(ok and out == b"A", "2.0 reader for contrast: a UDG (90h) ends the text")

    # ── #227: function $86, keys as typed, the Pico ends the loop ──────────
    st = 0x01
    ok, c, out, sent, left = run(rom23, FN_86, bytes([st]) + b"PAGE1\x00",
                                 keys=[ord("n")], replies=[b"n\r\x03"])
    check(ok and sent == b"n", "2.3 $86: 'n' goes to the Pico as typed (sent %s)" % sent.hex(" "))
    check(ok and out == b"PAGE1n\r" and left == b"",
          "2.3 $86: after N the ROM reads the Pico's echo and 03h, nothing left in TX "
          "(printed %r)" % out)
    ok, c, out, sent, left = run(rom23, FN_86, bytes([st]) + b"P1\x00",
                                 keys=[ord("y"), ord("N")], replies=[b"P2\x00", b"x\x03"])
    check(ok and sent == b"yN" and out == b"P1P2x" and left == b"",
          "2.3 $86: 'y' then 'N': two pages, each key as typed, the Pico's 03h ends it")
    ok, c, out, sent, left = run(rom23, FN_86, bytes([st]) + b"Q?\x00",
                                 keys=[ord("5")], replies=[b"\x10\x00ok\x03"])
    check(ok and sent == b"5" and out == b"Q?\x10\x00ok",
          "2.3 $86: a digit unchanged; the next page's INK 0 is printed, not taken for its end")

    ok, c, out, sent, left = run(rom20, FN_86, bytes([st]) + b"PAGE1\x00",
                                 keys=[ord("n")], replies=[b"n\r\x03"])
    check(ok and sent == b"N" and out == b"PAGE1N" and left == b"n\r\x03",
          "2.0 $86 for contrast: 'n' sent as 'N', the ROM prints N and leaves at once, "
          "the reply unread (sent %s, printed %r)" % (sent.hex(" "), out))

    print("\n%d/%d passed" % (sum(results), len(results)))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
