#!/usr/bin/env python3
"""The v3 card's TS2050 modem layer (src/tsbus/modem2050.c), on the host.

Compiles modem2050.c and usart8251.c with modem2050_shim.c and drives them
through ctypes: the 2068's side as MTERM and the BASIC dialers drive the
8251 (docs/ts2050-software-notes.md, with MTERM's own timings), and the
line's side as Zimodem answers. Time is in milliseconds; a "pass" is one of
core 1's loop passes, every 5 ms here.

Needs a C compiler (cc). Run:  python3 src/test/modem2050_hosttest.py
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
ONHOOK, OFFHOOK, DIALING, CONNECTED, DEAD, HANGUP = range(6)


def check(ok, what):
    print(("  ok   " if ok else "  FAIL ") + what)
    if not ok:
        FAILS.append(what)


def build():
    d = tempfile.mkdtemp(prefix="m2050.")
    lib = os.path.join(d, "m2050.so")
    subprocess.run(["cc", "-shared", "-fPIC", "-O1", "-Wall", "-Werror", "-I", TSBUS,
                    os.path.join(TSBUS, "usart8251.c"), os.path.join(TSBUS, "modem2050.c"),
                    os.path.join(HERE, "modem2050_shim.c"), "-o", lib], check=True)
    return d, ctypes.CDLL(lib)


class Rig:
    def __init__(self, lib, mode):
        self.u = lib
        lib.shim_get.argtypes = [ctypes.c_char_p]
        lib.shim_number.restype = ctypes.c_char_p
        lib.shim_init(mode)
        self.t = 0
        self.sent = b""          # what Zimodem got
        self.shown = b""         # what the 2068 read

    def get(self, k):
        return self.u.shim_get(k.encode())

    def run(self, ms, read=True):
        """`ms` of passes every 5 ms; the 2068 reads what's ready, Zimodem
        takes what's sent."""
        end = self.t + ms
        while self.t < end:
            self.t += 5
            self.u.shim_poll(self.t)
            while True:
                b = self.u.shim_line_tx()
                if b < 0:
                    break
                self.sent += bytes([b])
            if read and self.u.shim_status() & 2:
                self.shown += bytes([self.u.shim_data_in()])

    def cmd(self, b, then=0):
        self.u.shim_control(b)
        self.run(then)

    def zimodem(self, data):
        for b in data:
            assert self.u.shim_line_rx(b) == 0
        self.run(50)

    def take_sent(self):
        s, self.sent = self.sent, b""
        return s

    def take_shown(self):
        s, self.shown = self.shown, b""
        return s

    def dsr(self):
        return bool(self.u.shim_status() & 0x80)


ONH, OFFH = 0x15, 0x17           # MTERM's commands: on-hook (DTR off), off-hook


def mterm_reset(r):
    for b in (0, 0, 0, 0x40, 0x7B, ONH):
        r.u.shim_control(b)
    r.run(10)


def mterm_dial(r, number):
    """MTERM's dialer (notes 2.8): off-hook, 2.38 s for dial tone, per digit
    n x (58 ms break, 47.5 ms make), 832 ms between digits."""
    r.cmd(OFFH, 2380)
    for ch in number:
        n = int(ch) or 10
        for _ in range(n):
            r.cmd(ONH, 58)
            r.cmd(OFFH, 48)
        r.run(832)


def main():
    d, lib = build()
    try:
        print("Hayes mode: straight through, DSR 1")
        r = Rig(lib, 0)
        mterm_reset(r)
        check(r.dsr(), "DSR held at 1")
        r.zimodem(b"\r\nOK\r\n")
        check(r.take_shown() == b"\r\nOK\r\n", "Zimodem's bytes reach the 2068 as they are")
        for c in b"ATI\r":
            r.u.shim_data_out(c)
        r.run(20)
        check(r.take_sent() == b"ATI\r", "the 2068's bytes reach Zimodem")

        print("2050 mode: on-hook")
        r = Rig(lib, 1)
        mterm_reset(r)
        check(r.get("state") == ONHOOK and not r.dsr(), "on-hook, DSR 0")
        r.zimodem(b"\r\nZimodem ESP32 Firmware\r\nREADY.\r\nRING\r\n")
        check(r.take_shown() == b"" and not r.dsr(),
              "Zimodem's banner and a RING aren't shown, and DSR doesn't move (MTERM counts DSR changes as rings)")
        r.u.shim_data_out(ord("x"))
        r.run(20)
        check(r.take_sent() == b"", "the 2068's bytes on-hook are dropped")

        print("MTERM dials 12")
        mterm_dial(r, "12")
        sent = r.take_sent()
        check(sent.startswith(b"ATE0V1X0F1\r"), "off-hook: Zimodem's init (%r)" % sent[:12])
        check(r.get("state") == OFFHOOK and sent == b"ATE0V1X0F1\r", "after the digits, not dialled yet")
        r.run(1600)
        check(r.take_sent() == b"ATDX12\r" and r.get("state") == DIALING and r.u.shim_number() == b"12",
              "1.5 s after the last digit: ATDX12 (X: the call obeys XOFF, #302)")
        r.zimodem(b"\r\nCONNECT\r\nWelcome to the BBS\r\n")
        check(r.get("state") == CONNECTED and r.dsr(), "CONNECT: connected, DSR 1 at once")
        r.run(3300)
        check(r.take_shown() == b"", "the host's banner held back while MTERM qualifies the carrier (3.5 s)")
        r.run(400)
        check(r.take_shown() == b"Welcome to the BBS\r\n", "then shown; the result line never reaches the 2068")
        check(r.u.shim_status() == 0x85, "idle connected status 85h: the BASIC dialers' IN 119=133")
        for c in b"hi":
            r.u.shim_data_out(c)
        r.run(20)
        check(r.take_sent() == b"hi", "connected: the 2068's bytes go to the far end")
        r.zimodem(b"\r\nNO CARRIAGE here\r\n")
        r.run(200)
        check(r.take_shown() == b"\r\nNO CARRIAGE here\r\n" and r.get("state") == CONNECTED,
              "a line that only starts like NO CARRIER is passed on whole")
        r.zimodem(b"NO CARRIER is just text")
        r.run(100)
        check(r.take_shown() == b"NO CARRIER is just text" and r.get("state") == CONNECTED,
              "NO CARRIER without a line ending after it is passed on")
        r.zimodem(b"\r\n> NNO CARRIER\r\n")
        r.run(100)
        check(r.get("state") == DEAD and not r.dsr() and r.get("carrier_lost") == 1,
              "> NO CARRIER<CR>, mid-line as Zimodem sent it on proto1: the far end went, DSR 0")
        check(r.take_shown() == b"\r\n> N", "... and it isn't shown (the extra N before it is)")
        r.cmd(ONH, 500)
        check(r.get("state") == ONHOOK and r.take_sent() == b"", "on-hook from dead: nothing to send")

        print("a failed call, and hanging up while dialling")
        mterm_dial(r, "9")
        r.run(1600)
        r.take_sent()
        r.zimodem(b"\r\nNO ANSWER\r\n")
        check(r.get("state") == DEAD and not r.dsr(), "NO ANSWER: dead, DSR stays 0")
        r.cmd(ONH, 500)
        mterm_dial(r, "9")
        r.run(1600)
        r.take_sent()
        r.cmd(ONH, 500)
        check(r.get("state") == ONHOOK and r.take_sent() == b"ATH\r", "on-hook while dialling: ATH")

        print("hanging up a call: guard, +++, guard, ATH")
        mterm_dial(r, "3")
        r.run(1600)
        r.take_sent()
        r.zimodem(b"\r\nCONNECT\r\n")
        for c in b"x":
            r.u.shim_data_out(c)
        r.run(10)
        r.take_sent()
        r.cmd(ONH, 450)
        check(r.get("state") == HANGUP and not r.dsr(), "400 ms of DTR off: hanging up, DSR 0 at once")
        r.run(500)
        check(r.take_sent() == b"", "no +++ before 1.1 s of silence")
        r.run(700)
        check(r.take_sent() == b"+++", "+++ after the guard")
        r.run(1300)
        check(r.take_sent() == b"ATH\r" and r.get("state") == ONHOOK, "ATH after the guard again: on-hook")

        print("a redial before the hang-up has finished")
        mterm_dial(r, "4")
        r.run(1600)
        r.take_sent()
        r.zimodem(b"\r\nCONNECT\r\n")
        r.cmd(ONH, 450)
        r.cmd(OFFH, 3000)
        sent = r.take_sent()
        check(sent == b"+++ATH\rATE0V1X0F1\r" and r.get("state") == OFFHOOK,
              "off-hook again during the escape: ATH, then a fresh init (%r)" % sent)

        print("flow control while connected")
        r = Rig(lib, 1)
        mterm_reset(r)
        mterm_dial(r, "5")
        r.run(1600)
        r.zimodem(b"\r\nCONNECT\r\n")
        r.take_sent()
        n = 0
        while r.get("lrx_level") < 32 and n < 64:
            lib.shim_line_rx(0x41); n += 1
            r.run(10, read=False)
        check(r.get("lrx_level") == 32 and r.get("xoff_sent") == 0 and r.take_sent() == b"",
              "the 2068 not reading: a ring exactly half full (32 of 64) is no XOFF yet")
        ok = all(lib.shim_line_rx(0x41) == 0 for i in range(60 - n))
        r.run(10, read=False)
        check(ok and r.get("xoff_sent") == 1 and r.take_sent() == b"\x13",
              "  over half full: XOFF, so Zimodem's 4 KB buffer still fits after it (%d)" % r.get("lrx_level"))
        ok = all(lib.shim_line_rx(0x42) == 0 for i in range(3))   # the LF after CONNECT waits too
        r.run(4000)
        check(ok and r.get("xoff_sent") == 0 and r.take_sent() == b"\x11", "read down below 1/4: XON")
        check(r.take_shown() == b"A" * 60 + b"B" * 3, "nothing lost or reordered; CONNECT's LF swallowed")

        print("waiting for Zimodem's READY. (#300)")

        def feed(r, data):
            """Zimodem's bytes as they arrive, core 1 looking every 16 (the
            ring is 64) until READY. comes: did it?"""
            up = False
            for i, b in enumerate(data):
                assert r.u.shim_line_rx(b) == 0
                if i % 16 == 15 and not up:
                    up = lib.shim_wait_ready() == 1
            return up or lib.shim_wait_ready() == 1

        r = Rig(lib, 0)
        mterm_reset(r)
        r.take_shown()
        up = feed(r, b"ESP-ROM:esp32c3\r\nentry 0x403cc710\r\n\r\nZimodem ESP32 Firmware v4.0.3.1\r\n"
                     b"CONNECTED TO home (192.168.1.229)\r\nREA")
        check(not up and r.get("lrx_level") == 0,
              "the ROM's lines and the banner, READY. not yet whole: no, and all dropped")
        check(feed(r, b"DY.\r\nOK\r\n") and r.get("lrx_level") == 6 and r.get("eol_swallow") == 2,
              "  the rest of it: yes, matched across calls; what follows READY. kept")
        r.run(200)
        check(r.take_shown() == b"OK\r\n", "  its line ending dropped, the rest reaches the 2068")
        r = Rig(lib, 0)
        mterm_reset(r)
        r.take_shown()
        check(feed(r, b"READYREADY.\rAT"), "a false start (READY without the dot) then READY.: yes")
        r.run(200)
        check(r.take_shown() == b"AT", "  a CR-only line ending dropped too, then the 2068 sees AT")
        r = Rig(lib, 0)
        check(feed(r, b"RREADY."), "RREADY.: the second R starts the match again")
        r = Rig(lib, 0)
        check(not feed(r, b"READY\r\nNOT READY\r\n") and r.get("lrx_level") == 0, "no READY. at all: no, all dropped")

        print("flow control in Hayes mode (#301)")
        r = Rig(lib, 0)
        mterm_reset(r)
        r.take_sent()
        ok = all(lib.shim_line_rx(0x41) == 0 for i in range(60))
        r.run(10, read=False)
        check(ok and r.get("xoff_sent") == 0 and r.take_sent() == b"",
              "off (the default): a full ring sends Zimodem nothing (%d)" % r.get("lrx_level"))
        r.run(2000)
        check(r.take_shown() == b"A" * 60, "  and the 2068 reads it all")
        lib.shim_flow(1)
        r.run(10)
        check(r.get("flow") == 1 and r.take_sent() == b"", "tsbus.modem_flow(True): taken on the next pass, nothing sent")
        ok = all(lib.shim_line_rx(0x43) == 0 for i in range(60))
        r.run(10, read=False)
        check(ok and r.get("xoff_sent") == 1 and r.take_sent() == b"\x13",
              "on: XOFF once the line ring is over half full, as 2050 mode (%d)" % r.get("lrx_level"))
        r.run(4000)
        check(r.get("xoff_sent") == 0 and r.take_sent() == b"\x11", "  read down below 1/4: XON")
        check(r.take_shown() == b"C" * 60, "  nothing lost or reordered")
        ok = all(lib.shim_line_rx(0x44) == 0 for i in range(60))
        r.run(10, read=False)
        check(ok and r.get("xoff_sent") == 1 and r.take_sent() == b"\x13", "stopped again...")
        lib.shim_flow(0)
        r.run(10, read=False)
        check(r.get("flow") == 0 and r.get("xoff_sent") == 0 and r.take_sent() == b"\x11",
              "  ...turned off while stopped: XON first, so Zimodem isn't left stopped")
        r.run(4000)
        r.take_shown()
        lib.shim_flow(1)
        r.run(10)
        lib.shim_init(0)
        check(r.get("flow") == 0, "a fresh m2050_init (tsbus.modem(True): a mode change, the boot) turns it off")

        print("a BASIC dialer (Loader V): OUT 3/4/1/2 a pulse, no pauses")
        r = Rig(lib, 1)
        r.cmd(31, 1000)                   # a fresh chip: off-hook (DTR on)
        for digit in (2, 7):
            for _ in range(digit):
                for e in (3, 4, 1, 2):
                    r.cmd(e, 5)
            r.run(500)                    # PAUSE 25
        r.run(1600)
        check(r.u.shim_number() == b"27" and r.take_sent().endswith(b"ATDX27\r"),
              "dials 27 (%r)" % r.u.shim_number())
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
