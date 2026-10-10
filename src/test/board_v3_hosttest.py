#!/usr/bin/env python3
"""TS/board.py picks board_v3 when the tsbus module is there, and board_v3
drives the v3 card as phase 4 of the v3 port plan says
(docs/v3-board-layer-proposal.md, step 4.3):

  - early_init starts tsbus; start_memory loads ROM_FILE's two halves into
    HOME and EXROM, serves EXROM and DOCK, and releases the 2068;
  - make_mq empties both queues (a new v2 state machine's FIFOs are empty);
    sd_take_bus keeps MQ (SD has its own pins);
  - the SD card is on SPI0 at 38/39/32 with CS 37, never GPIO 2-4;
  - the LED is the XL9555's bit 5, dimmed (LED_BRIGHTNESS %) by a 10 ms
    timer and a one-shot, written only on a change;
  - background runs on core 0; SLOTS and HAS_CORE1 are off, and tspico's
    slot commands refuse.

Run:  python3 src/test/board_v3_hosttest.py
"""

import os
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, SRC)
sys.path.insert(0, HERE)

FAILS = []
CALLS = []


def check(ok, what):
    print(("  ok   " if ok else "  FAIL ") + what)
    if not ok:
        FAILS.append(what)


class FakeMQ:
    def __init__(self):
        self.tx, self.rx = [], []

    def rx_fifo(self):
        return len(self.rx)

    def tx_fifo(self):
        return len(self.tx)

    def get(self):
        return self.rx.pop(0)

    def exec(self, instr):
        if instr.replace(" ", "") == "pull(noblock)" and self.tx:
            self.tx.pop(0)


THE_MQ = FakeMQ()


def fake_tsbus():
    t = types.ModuleType("tsbus")
    t.HOME, t.EXROM, t.DOCK = 0, 1, 2
    t.MQ = lambda: THE_MQ
    for name in ("start", "hold", "serve", "exrom", "dock"):
        setattr(t, name, (lambda n: lambda *a: CALLS.append((n,) + a))(name))
    t.load = lambda slot, data: CALLS.append(("load", slot, bytes(data)))
    return t


class FakePin:
    OUT, IN, PULL_UP = "OUT", "IN", "PULL_UP"

    def __init__(self, n, *a, **k):
        self.n = n
        CALLS.append(("Pin", n) + a)

    def value(self, v=None):
        CALLS.append(("value", self.n, v))


class FakeTimer:
    PERIODIC, ONE_SHOT = 1, 0
    made = []

    def __init__(self, **k):
        self.live = False
        FakeTimer.made.append(self)
        if k:
            self.init(**k)

    def init(self, mode=None, period=None, tick_hz=1000, callback=None):
        self.mode, self.us, self.callback, self.live = mode, period * 1_000_000 // tick_hz, callback, True

    def deinit(self):
        self.live = False


class FakeI2C:
    def __init__(self, bus):
        CALLS.append(("I2C", bus))

    def writeto_mem(self, addr, reg, data):
        CALLS.append(("i2c", addr, reg, bytes(data)))


def take():
    out = list(CALLS)
    del CALLS[:]
    return out


def main():
    import sync_io_hosttest as S
    S.install_fakes()
    m = sys.modules["machine"]
    m.Pin = FakePin
    m.I2C = FakeI2C
    m.Timer = FakeTimer
    m.SPI = lambda bus, **k: CALLS.append(("SPI", bus) + tuple(sorted((key, v.n) for key, v in k.items()))) or "spi"
    sys.modules["tsbus"] = fake_tsbus()

    from TS import board
    import TS.board_v3 as b3

    print("board.py picks the implementation")
    check(board.NAME == "v3" and board.make_mq is b3.make_mq, "tsbus present: v3")
    check(board.PIO_MQ is False and board.SLOTS is False and board.HAS_CORE1 is False,
          "no PIO MQ, no slots, core 1 not free")

    print("early_init and start_memory")
    take()
    board.early_init()
    check(take() == [("start",)], "early_init starts tsbus")
    rom = bytes(range(256)) * 128                           # 32K: HOME then EXROM
    d = tempfile.mkdtemp(prefix="board_v3.")
    b3.ROM_FILE = os.path.join(d, "TSPICO-23.ROM")
    with open(b3.ROM_FILE, "wb") as f:
        f.write(rom)
    board.start_memory(0x0A, 0x01)
    got = take()
    check(got[0] == ("hold", True) and got[-1] == ("hold", False), "held while loading, then released")
    check(("load", 0, rom[:16384]) in got and ("load", 1, rom[16384:]) in got,
          "HOME the first 16K, EXROM the second")
    check(("exrom", True) in got and ("dock", True) in got and ("serve", True) in got,
          "EXROM and DOCK chunks served, /BE live")
    check(got.index(("serve", True)) < got.index(("hold", False)), "serving before the release")

    print("MQ")
    THE_MQ.tx, THE_MQ.rx = [1, 2, 3], [0x41, 0x103]
    mq = board.make_mq()
    check(mq is THE_MQ and THE_MQ.tx == [] and THE_MQ.rx == [], "make_mq: tsbus.MQ(), both queues emptied")
    THE_MQ.tx = [9]
    check(board.sd_take_bus() is THE_MQ and THE_MQ.tx == [9], "sd_take_bus keeps MQ and its queue")
    board.restart_mq(mq)
    check(take() == [], "restart_mq: nothing to do")

    print("the SD card's own pins")
    board.sd_cs()
    check(take() == [("Pin", 37, "OUT", "PULL_UP")], "CS on GPIO 37")
    board.sd_spi()
    got = take()
    check(("SPI", 0, ("miso", 32), ("mosi", 39), ("sck", 38)) in got, "SPI0: SCK 38, MOSI 39, MISO 32")
    check(not [c for c in got if c[0] == "Pin" and c[1] in (2, 3, 4)], "never GPIO 2-4 (MD2-MD4 on this card)")
    board.sd_release_bus()
    check(take() == [("Pin", 37, "OUT", "PULL_UP"), ("value", 37, 1)], "release: CS high")

    print("the LED on the expander, dimmed")
    led = board.make_led()
    take()
    del FakeTimer.made[:]
    led.value(1)
    led.value(1)
    check(take() == [("i2c", 0x20, 2, b"\xc0")], "on: lit at once (bit 5 low), once")
    live = [t for t in FakeTimer.made if t.live]
    per = [t for t in live if t.mode == FakeTimer.PERIODIC]
    off = [t for t in live if t.mode == FakeTimer.ONE_SHOT]
    check(len(per) == 1 and per[0].us == 10_000 and len(off) == 1 and off[0].us == 500,
          "the default 5 %%: lit every 10 ms, dark after 500 us (%r)" % [(t.mode, t.us) for t in live])
    per, off = per[0], off[0]
    for _ in range(3):
        off.callback(off)
        per.callback(per)
    writes = [c[3] for c in take() if c[0] == "i2c"]
    check(writes == [b"\xe0", b"\xc0"] * 3, "two writes a period (%r)" % writes)
    check(off.live and off.us == 500, "the one-shot re-armed each period")
    led.brightness(30)
    check([t.us for t in FakeTimer.made if t.live and t.mode == FakeTimer.ONE_SHOT] == [3000],
          "brightness(30) while on: 3 ms of 10")
    led.off()
    check(not [t for t in FakeTimer.made if t.live] and led.value() == 0, "off: both timers stop")
    check(take()[-1:] == [("i2c", 0x20, 2, b"\xe0")], "and the LED is left dark")
    board.led_brightness(led, 100)
    del FakeTimer.made[:]
    led.toggle()
    check(led.value() == 1 and not FakeTimer.made and take() == [("i2c", 0x20, 2, b"\xc0")],
          "100 %: simply lit, no timers")
    led.off()
    take()

    print("background and the slot commands")
    ran = []
    board.background(lambda *a: ran.append(a), (1, 2))
    check(ran == [(1, 2)], "background runs fn on core 0, at once")

    mp = types.ModuleType("micropython")                # what tspico needs on top
    mp.const = lambda x: x
    sys.modules["micropython"] = mp
    import TS.tspico as t
    sent = []
    t.SEND_MSG = lambda msg, msg2, st, force=False: sent.append((msg, st))
    t.TLM = lambda *a, **k: None
    for name in ("MEMBOOT", "MEMDOCK", "BLKRCV"):
        del sent[:]
        getattr(t, name)(bytes(10), "")
        check(sent == [("Not on the v3 card yet", t._3_F_Invalid_file)], "%s refuses, Report F" % name)

    print()
    if FAILS:
        print("%d FAILED" % len(FAILS))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
