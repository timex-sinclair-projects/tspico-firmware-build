#!/usr/bin/env python3
"""The v3 card's TS2050 8251 (src/tsbus/usart8251.c), on the host.

Compiles usart8251.c with usart8251_shim.c into a shared library and drives
it through ctypes with what the 2068's software does (docs/ts2050-software-
notes.md): MTERM's reset and polling loops, the BASIC dialers' bare command
writes and `IN 119=133`, and the line on the other side (Zimodem) sending
and taking bytes. The shim's rings are small (64 in, 16 out) so full and
overflow are reached quickly.

Needs a C compiler (cc). Run:  python3 src/test/usart8251_hosttest.py
"""

import ctypes
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TSBUS = os.path.normpath(os.path.join(HERE, "..", "tsbus"))

FAILS = []


def check(ok, what):
    print(("  ok   " if ok else "  FAIL ") + what)
    if not ok:
        FAILS.append(what)


def build():
    d = tempfile.mkdtemp(prefix="u8251.")
    lib = os.path.join(d, "u8251.so")
    subprocess.run(["cc", "-shared", "-fPIC", "-O1", "-Wall", "-Werror", "-I", TSBUS,
                    os.path.join(TSBUS, "usart8251.c"), os.path.join(HERE, "usart8251_shim.c"),
                    "-o", lib], check=True)
    return d, ctypes.CDLL(lib)


def main():
    d, u = build()
    try:
        u.shim_get.argtypes = [ctypes.c_char_p]
        get = lambda k: u.shim_get(k.encode())
        st = u.shim_status

        def mterm_init(mode=0x7B, cmd=0x15):
            for b in (0x00, 0x00, 0x00, 0x40, mode, cmd):
                u.shim_control(b)

        print("power-up")
        u.shim_init()
        check(get("expect_mode") == 1, "a fresh chip expects a mode byte")
        check(st() == 0x05, "status TxRDY + TxEMPTY, no DSR (%02Xh)" % st())

        print("MTERM's reset: 00h x3, 40h, mode 7Bh, command 15h")
        mterm_init()
        check(get("expect_mode") == 0 and get("mode") == 0x7B and get("mask") == 0x7F,
              "mode 7Bh taken: 7 bits (mask %02Xh)" % get("mask"))
        check(get("cmd") == 0x05, "command 15h kept as 05h: TxEN, RxE (ER is a one-shot)")
        mterm_init()
        check(get("mode") == 0x7B and get("cmd") == 0x05, "the same from command state (00h is a command there)")
        u.shim_control(0x40)
        u.shim_control(0x00)
        check(get("expect_mode") == 1, "after IR, a sync-mode byte (00h) is ignored: still expecting a mode byte")

        print("Hayes mode: DSR held at 1")
        u.shim_init()
        u.shim_set(0, 1, 0)
        mterm_init()
        u.shim_poll(0)
        check(st() == 0x85, "idle status 85h, what the BASIC dialers' IN 119=133 wants (%02Xh)" % st())

        print("transmit (MTERM: IN 77h / RRCA / JR NC, then OUT 73h)")
        sent = []
        for ch in b"ATZ\r":
            while not st() & 1:
                pass
            u.shim_data_out(ch)
        check(not st() & 0x04, "TxEMPTY clear with bytes queued")
        while True:
            b = u.shim_line_tx()
            if b < 0:
                break
            sent.append(b)
        u.shim_poll(0)
        check(bytes(sent) == b"ATZ\r", "the line got ATZ<CR> (%r)" % bytes(sent))
        check(st() & 0x04, "TxEMPTY set again once the line took them")
        u.shim_data_out(0xC1)
        check(u.shim_line_tx() == 0x41, "7-bit mode: bit 7 masked off on the way out")
        for i in range(16):
            u.shim_data_out(0x30 + i)
        check(not st() & 1, "16 queued: the ring is full, TxRDY clear")
        u.shim_data_out(0x7A)
        check(get("tx_dropped") == 1, "a write with no room is dropped and counted")
        while u.shim_line_tx() >= 0:
            pass
        u.shim_poll(0)
        u.shim_control(0x04)                        # TxEN off
        u.shim_data_out(0x41)
        check(get("tx_dropped") == 2 and st() & 0x05 == 0x05,
              "TxEN off: dropped; TxRDY and TxEMPTY still set (the status bit ignores TxEN)")
        u.shim_control(0x15)

        print("receive, paced (MTERM: IN 77h / BIT 1, then IN 73h)")
        u.shim_set(100, 1, 0)                       # 100 ticks a character
        for ch in b"HI\xc8":
            u.shim_line_rx(ch)
        u.shim_poll(1000)
        check(st() & 2, "a character waiting: RxRDY")
        check(u.shim_data_in() == ord("H") and not st() & 2, "IN 73h gives H and clears RxRDY")
        u.shim_poll(1050)
        check(not st() & 2, "50 ticks later: not yet (paced)")
        u.shim_poll(1100)
        check(st() & 2 and u.shim_data_in() == ord("I"), "100 ticks after the last: I")
        u.shim_poll(1200)
        check(u.shim_data_in() == 0x48, "7-bit mode: C8h arrives as 48h")
        check(get("rx_chars") == 3, "three characters read")
        u.shim_poll(1210)
        check(st() == 0x85, "nothing left: status 85h again")
        u.shim_line_rx(ord("x"))
        u.shim_poll(1250)
        check(not st() & 2, "a byte 50 ticks after the last release: held back")
        u.shim_control(0x11)                        # RxE off
        u.shim_poll(5000)
        check(not st() & 2, "RxE off: RxRDY held clear")
        u.shim_control(0x15)
        u.shim_poll(5001)
        check(st() & 2 and u.shim_data_in() == ord("x"), "RxE on again: the waiting x")

        print("overrun")
        u.shim_set(0, 1, 0)
        for i in range(70):
            u.shim_line_rx(0x20 + i)
        u.shim_poll(0)
        check(get("rx_lost") == 6 and st() & 0x10, "70 bytes into a 64-byte ring: 6 lost, OE set")
        check(u.shim_data_in() == 0x20 + 6, "the oldest kept byte comes first")
        u.shim_poll(0)
        check(st() & 0x10, "OE stays until ER")
        u.shim_control(0x15)                        # MTERM's error reset: ER is in its command
        check(not st() & 0x10, "a command with ER clears OE")
        u.shim_poll(0)
        while st() & 2:                             # drain the rest
            u.shim_data_in()
            u.shim_poll(0)

        print("flow control (XOFF at 3/4, XON below 1/4)")
        u.shim_init()
        u.shim_set(0, 1, 1)
        mterm_init()
        for i in range(50):
            u.shim_line_rx(0x41)
        u.shim_poll(0)
        check(get("xoff_sent") == 1 and u.shim_line_tx() == 0x13, "49 waiting: XOFF to the line")
        for i in range(34):
            u.shim_data_in()
            u.shim_poll(0)
        check(get("xoff_sent") == 0 and u.shim_line_tx() == 0x11, "drained below 16: XON")

        print("the BASIC dialer on a fresh chip")
        u.shim_init()
        u.shim_set(0, 1, 0)
        u.shim_control(31)                          # Modem's line 15: OUT 119,31
        check(get("expect_mode") == 0 and get("mode") == 31,
              "OUT 119,31 is taken as the mode byte, as on a real 8251")
        u.shim_control(3)
        check(get("cmd") == 3, "the next write is a command (DTR, TxEN)")

        print("the 2068 BBS: answer sequence after a hang-up")
        u.shim_init()
        u.shim_set(0, 1, 0)
        mterm_init()
        for b in (64, 0, 0):                        # line 9201: IR, 0, 0
            u.shim_control(b)
        for b in (2, 34, 64, 123, 55):              # line 1010
            u.shim_control(b)
        check(get("mode") == 123 and get("cmd") == 0x27,
              "ends in mode 7Bh, command 37h less ER (27h: TxEN, DTR, RxE, RTS)")
    finally:
        shutil.rmtree(d)

    print()
    if FAILS:
        print("%d FAILED" % len(FAILS))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
