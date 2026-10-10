#!/usr/bin/env python3
"""TS/board.py picks board_v2 off the v3 card, and board_v2 sets up the v2
hardware exactly as main.py and tspico.py did before phase 4 of the v3 port
plan moved the code behind it (docs/v3-board-layer-proposal.md).

The fakes record every Pin, StateMachine, SPI and freq call, so a change to a
state machine's number, program, clock or pins, or to a pin's level, fails
here and not on a 2068.

Run:  python3 src/test/board_hosttest.py
"""

import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, SRC)

FAILS = []
CALLS = []


def check(ok, what):
    print(("  ok   " if ok else "  FAIL ") + what)
    if not ok:
        FAILS.append(what)


class FakePin:
    OUT, IN, PULL_UP, PULL_DOWN = "OUT", "IN", "PULL_UP", "PULL_DOWN"

    def __init__(self, n, *a, **k):
        self.n = n
        CALLS.append(("Pin", n) + a + tuple(sorted(k.items())))

    def value(self, v=None):
        CALLS.append(("value", self.n, v))


class FakeSM:
    def __init__(self, sm, prog, **k):
        self.sm, self.prog = sm, prog
        pins = {key: (v.n if isinstance(v, FakePin) else v) for key, v in k.items()}
        CALLS.append(("SM", sm, getattr(prog, "__name__", prog)) + tuple(sorted(pins.items())))

    def active(self, v):
        CALLS.append(("active", self.sm, v))

    def put(self, v):
        CALLS.append(("put", self.sm, v))


def install_fakes():
    import builtins
    builtins.const = lambda x: x
    machine = types.ModuleType("machine")
    machine.Pin = FakePin
    machine.SPI = lambda bus, **k: CALLS.append(("SPI", bus) + tuple(
        sorted((key, v.n) for key, v in k.items()))) or "spi"
    machine.freq = lambda hz=None: CALLS.append(("freq", hz))
    sys.modules["machine"] = machine
    rp2 = types.ModuleType("rp2")
    rp2.StateMachine = FakeSM
    rp2.asm_pio = lambda *a, **k: (lambda f: f)
    rp2.PIO = types.SimpleNamespace(OUT_LOW=0, OUT_HIGH=1, IN_LOW=0, IN_HIGH=1,
                                    SHIFT_LEFT=0, SHIFT_RIGHT=1, JOIN_TX=1, JOIN_RX=2)
    sys.modules["rp2"] = rp2
    utime = types.ModuleType("utime")
    utime.sleep = lambda s: CALLS.append(("sleep", s))
    sys.modules["utime"] = utime
    micropython = types.ModuleType("micropython")
    micropython.const = lambda x: x
    sys.modules["micropython"] = micropython
    sdcard = types.ModuleType("TS.sdcard")
    sdcard.SDCard = lambda *a, **k: None
    sys.modules["TS.sdcard"] = sdcard


def take():
    out = list(CALLS)
    del CALLS[:]
    return out


def main():
    install_fakes()
    from TS import board
    import TS.board_v2 as b2
    # _thread can't be replaced in sys.modules (CPython's imports use it).
    b2._thread = types.SimpleNamespace(
        start_new_thread=lambda fn, args: CALLS.append(("thread", fn.__name__, args)))

    print("board.py picks the implementation")
    check(board.NAME == "v2" and board.PIO_MQ is True, "no tsbus here: v2 (%r)" % board.NAME)
    check(board.make_mq is b2.make_mq, "board's names are board_v2's")

    print("early_init: main.py's pins and clock")
    take()
    board.early_init()
    got = take()
    pins = [c for c in got if c[0] == "Pin"]
    check([p[1] for p in pins] == [12, 14, 19, 20, 21, 26, 27], "the seven pins, in order (%r)" % [p[1] for p in pins])
    check(("Pin", 14, "OUT", "PULL_DOWN") in got and ("Pin", 26, "IN", "PULL_DOWN") in got,
          "WAIT out with pull-down, ROSCS in with pull-down")
    check([c[1] for c in got if c[0] == "value" and c[2] == 1] == [12, 14, 19, 20, 21, 27],
          "six outputs driven high (ROSCS is an input)")
    check(got[-1] == ("freq", 270_000_000), "then 270 MHz")

    print("start_memory / map_slots: the slot state machines")
    board.start_memory(0x0A, 0x01)
    got = take()
    check(("SM", 4, "set_ctrl", ("freq", 150_000_000), ("in_base", 0), ("jmp_pin", 26),
           ("out_base", 19), ("set_base", 21)) in got, "ROM: SM4 set_ctrl at 150 MHz")
    check(("SM", 5, "sel_bank", ("freq", 150_000_000), ("jmp_pin", 26), ("out_base", 15)) in got,
          "BANK: SM5 sel_bank")
    check(got[-2:] == [("put", 4, 0x0A), ("put", 5, 0x01)], "both started, then the slots put (%r)" % got[-2:])
    board.map_slots(0x09, 0x23)
    check(take() == [("put", 4, 0x09), ("put", 5, 0x23)], "map_slots: ROM then BANK")

    print("make_mq / restart_mq: TS_IO_DUAL on SM0")
    mq = board.make_mq()
    got = take()
    check(got == [("SM", 0, "TS_IO_DUAL", ("freq", 30_000_000), ("in_base", 2), ("jmp_pin", 11),
                   ("out_base", 2), ("sideset_base", 12))]
          or [c for c in got if c[0] == "SM"] == [("SM", 0, "TS_IO_DUAL", ("freq", 30_000_000), ("in_base", 2),
                                                   ("jmp_pin", 11), ("out_base", 2), ("sideset_base", 12))],
          "SM0 TS_IO_DUAL at 30 MHz, D0-D7 from GPIO 2, jmp GPIO 11, side-set GPIO 12; not started")
    check(not [c for c in got if c[0] == "active"], "make_mq doesn't start it (ACTIVATE_MQ sets BUSY first)")
    board.restart_mq(mq)
    check(take() == [("active", 0, 0), ("sleep", 0.01), ("active", 0, 1)], "restart: stop, 10 ms, start")

    print("the SD card's turn on GPIO 2-4")
    sm = board.sd_take_bus()
    got = take()
    check(got[0] == ("SM", 0, "NULL_SM", ("freq", 15_000_000)) and got[1:3] == [("active", 0, 1), ("active", 0, 0)],
          "SM0 parked on NULL_SM at 15 MHz (%r)" % got[:3])
    check(("Pin", 12, "OUT", ("value", 1)) in got, "U6 held off (GPIO 12 high)")
    check(isinstance(sm, FakeSM), "the parked SM is returned (the caller's MQ)")
    board.sd_cs()
    check(take() == [("Pin", 28, "OUT", "PULL_UP")], "CS on GPIO 28")
    board.sd_spi()
    got = take()
    check(("SPI", 0, ("miso", 4), ("mosi", 3), ("sck", 2)) in got, "SPI0: SCK 2, MOSI 3, MISO 4")
    board.sd_release_bus()
    got = take()
    check(got[:2] == [("Pin", 28, "OUT", "PULL_UP"), ("value", 28, 1)]
          and [c[1] for c in got if c[0] == "value" and c[2] == 0] == [2, 3, 4],
          "release: CS high, GPIO 2-4 driven low")

    print("the LED and core 1")
    board.make_led()
    check(take() == [("Pin", 25, "OUT")], "LED on GPIO 25")

    def SAVE_LOG():
        pass
    board.background(SAVE_LOG, ())
    check(take() == [("thread", "SAVE_LOG", ())], "background runs on core 1")

    print()
    if FAILS:
        print("%d FAILED" % len(FAILS))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
