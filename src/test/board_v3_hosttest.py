#!/usr/bin/env python3
"""TS/board.py picks board_v3 when the tsbus module is there, and board_v3
drives the v3 card as phase 4 of the v3 port plan says
(docs/v3-board-layer-proposal.md, step 4.3):

  - early_init starts tsbus; start_memory loads ROM_FILE's two halves into
    HOME and EXROM, serves EXROM and DOCK, and releases the 2068;
  - make_mq empties both queues (a new v2 state machine's FIFOs are empty);
    sd_take_bus keeps MQ (SD has its own pins);
  - the SD card is on SPI0 at 38/39/32 with CS 37, never GPIO 2-4;
  - the card-detect switch (XL9555 port 1 bit 7) gates every mount: an
    empty socket is never clocked, a new card settles first, and the lines
    are released (inputs, no pulls) after every unmount;
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
IMG = [bytearray(65536) for _ in range(3)]  # tsbus's HOME, EXROM and DOCK images


def fake_tsbus():
    t = types.ModuleType("tsbus")
    t.HOME, t.EXROM, t.DOCK = 0, 1, 2
    t.MQ = lambda: THE_MQ
    for name in ("start", "hold", "serve", "exrom", "dock"):
        setattr(t, name, (lambda n: lambda *a: CALLS.append((n,) + a))(name))

    def fill(slot, data):                       # load: repeated to fill 64K
        data = bytes(data)
        for i in range(0, 65536, len(data)):
            IMG[slot][i:i + len(data)] = data[:65536 - i]

    def load(slot, data):
        CALLS.append(("load", slot, bytes(data)))
        fill(slot, data)

    def load_at(slot, off, data):
        assert 0 <= off and off + len(data) <= 65536
        CALLS.append(("load_at", slot, off, len(data)))
        IMG[slot][off:off + len(data)] = bytes(data)

    def read(slot, buf, off=0):
        CALLS.append(("read", slot, off))
        buf[:] = IMG[slot][off:off + len(buf)]

    def switch(**k):
        CALLS.append(("switch",) + tuple(sorted((n, bytes(v)) for n, v in k.items())))
        for n, v in k.items():
            fill({"home": 0, "exrom": 1, "dock": 2}[n], v)
    t.load, t.load_at, t.read, t.switch = load, load_at, read, switch
    t.dock_writes = lambda on: CALLS.append(("dock_writes", bool(on)))
    return t


class FakePin:
    OUT, IN, PULL_UP = "OUT", "IN", "PULL_UP"

    def __init__(self, n, *a, **k):
        self.n = n
        CALLS.append(("Pin", n) + a + tuple("%s=%r" % kv for kv in sorted(k.items())))

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


IN1 = [0xFF]            # the expander's input port 1: bit 7 high = no card


class FakeI2C:
    def __init__(self, bus):
        CALLS.append(("I2C", bus))

    def writeto_mem(self, addr, reg, data):
        CALLS.append(("i2c", addr, reg, bytes(data)))

    def readfrom_mem(self, addr, reg, n):
        CALLS.append(("i2c-read", addr, reg))
        if IN1[0] is None:
            raise OSError(5, "EIO")
        return bytes((IN1[0],))


class Clock:
    def __init__(self):
        self.ms, self.slept = 1000, []

    def ticks_ms(self):
        return self.ms

    @staticmethod
    def ticks_diff(a, b):
        return a - b

    def sleep_ms(self, n):
        self.slept.append(n)
        self.ms += n


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

    print("the slot files")
    b3.SLOTS_DIR = os.path.join(d, "slots")
    os.makedirs(b3.SLOTS_DIR)

    def put_slot(name, fill, n=32768):
        with open(os.path.join(b3.SLOTS_DIR, name), "wb") as f:
            f.write(bytes((fill + i) & 0xFF for i in range(n)))

    def loads(got):
        return {c[1]: c[2] for c in got if c[0] == "load"}

    put_slot("F01.bin", 0x10)                               # ROM 2.3's slot
    put_slot("F04.bin", 0x40)
    put_slot("F03.bin", 0x30, 1000)                         # not 32K: not a slot
    put_slot("F08.bin", 0x80)                               # a cartridge: both halves
    put_slot("F09.bin", 0x90)
    put_slot("F11.bin", 0xB0)                               # AROS-style: only the upper half
    put_slot("S02.bin", 0x22)
    put_slot("S05.bin", 0x55)
    take()
    note = board.start_memory(0x0A, 0x84)                   # flash/flash, dock 8, ROM 4
    got = loads(take())
    f04 = open(os.path.join(b3.SLOTS_DIR, "F04.bin"), "rb").read()
    check(note is None and got[0] == f04[:16384] and got[1] == f04[16384:],
          "ROM_SM 0Ah, bank_sm 84h: HOME and EXROM from F04.bin, no note")
    f08 = open(os.path.join(b3.SLOTS_DIR, "F08.bin"), "rb").read()
    f09 = open(os.path.join(b3.SLOTS_DIR, "F09.bin"), "rb").read()
    check(IMG[2] == f08 + f09, "dock 8: F08 then F09, 64K")
    check(not [n for n in os.listdir(b3.SLOTS_DIR) if n.startswith("S")],
          "the SRAM slots are deleted at boot")
    note = board.start_memory(0x0A, 0xA1)                   # dock 10, ROM 1
    take()
    f11 = open(os.path.join(b3.SLOTS_DIR, "F11.bin"), "rb").read()
    check(IMG[2] == bytes(32768) + f11, "dock 10, no F10: zeros below, F11 above, not mirrored")
    board.start_memory(0x0A, 0x91)                          # dock 9: odd
    take()
    check(IMG[2] == f09 + bytes(32768), "an odd dock slot: that slot below, zeros above")
    board.start_memory(0x0A, 0xE1)                          # dock 14: no files
    take()
    check(IMG[2] == bytes(65536), "an empty dock: zeros")

    print("the boot ROM's fallbacks")
    f01 = open(os.path.join(b3.SLOTS_DIR, "F01.bin"), "rb").read()
    note = board.start_memory(0x0A, 0x07)                   # flash slot 7: no file
    got = loads(take())
    check(got[0] == f01[:16384] and note == "no ROM in flash slot 7: booted flash slot 1",
          "an empty slot: flash slot 1, and a note (%r)" % note)
    note = board.start_memory(0x0A, 0x03)
    take()
    check(note and "flash slot 3" in note, "a file that isn't 32K counts as empty (%r)" % note)
    note = board.start_memory(0x09, 0x02)                   # SRAM slot 2: deleted at boot
    take()
    check(note == "no ROM in SRAM slot 2: booted flash slot 1", "SRAM boot slots are empty at boot (%r)" % note)
    os.remove(os.path.join(b3.SLOTS_DIR, "F01.bin"))
    note = board.start_memory(0x0A, 0x07)
    got = loads(take())
    check(got[0] == rom[:16384] and note == "no ROM in flash slot 7 or flash slot 1: booted %s" % b3.ROM_FILE,
          "no slot 1 either: ROM_FILE, and the note says so (%r)" % note)
    note = board.start_memory(0x0A, 0x01)
    take()
    check(note == "no ROM in flash slot 1: booted %s" % b3.ROM_FILE,
          "slot 1 asked for and missing: straight to ROM_FILE (%r)" % note)

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
    check(take() == [("Pin", 37, "OUT", "value=1")], "CS on GPIO 37, driven high (deselected)")
    board.sd_spi()
    got = take()
    check(("SPI", 0, ("miso", 32), ("mosi", 39), ("sck", 38)) in got, "SPI0: SCK 38, MOSI 39, MISO 32")
    check(not [c for c in got if c[0] == "Pin" and c[1] in (2, 3, 4)], "never GPIO 2-4 (MD2-MD4 on this card)")
    board.sd_release_bus()
    check(take() == [("Pin", p, "IN", "pull=None") for p in (37, 38, 39, 32)],
          "release: CS, SCK, MOSI and MISO back to inputs, no pulls (nothing drives the socket)")

    print("the card-detect switch")
    clock = Clock()
    b3.time = clock
    IN1[0] = 0xFF
    check(board.card_present() is False, "bit 7 high: no card")
    take()
    check(board.sd_card_ready() is False and not clock.slept, "sd_card_ready: False, no wait")
    IN1[0] = 0x7F
    check(board.card_present() is True, "bit 7 low: a card")
    IN1[0] = 0x7F
    ok = board.sd_card_ready()
    check(ok is True and clock.slept == [b3.SD_SETTLE_MS], "a card just seen: it settles %d ms first (%r)"
          % (b3.SD_SETTLE_MS, clock.slept))
    clock.slept = []
    check(board.sd_card_ready() is True and not clock.slept, "and not again while it stays in")
    IN1[0] = 0xFF
    board.sd_card_ready()
    IN1[0] = 0x7F
    clock.ms += 100
    board.sd_card_ready()
    check(clock.slept == [b3.SD_SETTLE_MS], "out and in again: it settles again (%r)" % clock.slept)
    IN1[0] = None
    check(board.card_present() is None and board.sd_card_ready() is True,
          "expander not answering: unknown, and the mount decides")
    IN1[0] = 0xFF
    take()

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
    t.TSP = types.SimpleNamespace(f_name="")
    t.MQ = types.SimpleNamespace(put=lambda b: None)
    t.LOG = lambda *a: None
    del sent[:]
    t.BLKRCV(bytes(10), "")
    check(sent == [("No ROM image mounted", t._3_F_Invalid_file)], "BLKRCV with nothing mounted: Report F, as v2")

    print("tpi:boot and tpi:dock switch slots")
    os.chdir(d)
    with open("config.ini", "w") as f:
        f.write('{"ROM_SLOT": 1, "ROM_SM": 10}')
    t.TSP = types.SimpleNamespace(ROM_SM=10, bank_sm=0x01, dck_prev_mem=2, dck_prev_slot=0, f_name="")
    t.LOG = lambda *a: None
    t.utime = types.SimpleNamespace(sleep=lambda s: None)
    put_slot("F01.bin", 0x10)
    board.start_memory(0x0A, 0x01)                          # served: boot F01, dock F00/F01
    take()

    def pre(m, s):
        return bytes((0, 0, 0, m & 0xFF, m >> 8, s & 0xFF, s >> 8, 0, 0, 0))

    def switches():
        return [c for c in take() if c[0] == "switch"]

    del sent[:]
    t.MEMBOOT(pre(2, 7), "")                                 # F07: no file
    check(sent and sent[-1][1] == t._3_F_Invalid_file and "No ROM in Flash slot 7" in sent[-1][0],
          "tpi:boot CODE 2,7 with no F07.bin: Report F (%r)" % sent[-1:])
    check(t.TSP.bank_sm == 0x01 and not switches(), "  and nothing changed, nothing switched")
    with open("config.ini") as f:
        check('"ROM_SLOT": 1' in f.read(), "  config.ini untouched")
    del sent[:]
    t.MEMBOOT(pre(2, 4), "")
    sw = switches()
    f04 = open(os.path.join(b3.SLOTS_DIR, "F04.bin"), "rb").read()
    check(sent and sent[-1][1] == t._1_OK and len(sw) == 1 and sw[0][1:] == (("exrom", f04[16384:]), ("home", f04[:16384])),
          "tpi:boot CODE 2,4: one switch, HOME and EXROM from F04 (a 200 ms reset), the dock untouched")
    with open("config.ini") as f:
        check('"ROM_SLOT": 4' in f.read(), "  config.ini: ROM_SLOT 4 (LOAD_CONFIG uses it once)")
    del sent[:]
    t.MEMDOCK(pre(2, 8), "")
    got = take()
    names = [c[0] for c in got]
    check(IMG[2] == f08 + f09 and "switch" not in names and "hold" not in names,
          "tpi:dock CODE 2,8: the dock alone, live (no reset): F08 then F09")
    check(got.index(("dock", False)) < names.index("load_at") and names.index("load_at") < got.index(("dock", True)),
          "  DOCK serving off for the copy, on again after")
    check(all(c[3] <= 32768 for c in got if c[0] == "load_at"), "  in halves of 32K at most: no 64K buffer")
    t.MEMBOOT(pre(2, 4), "")
    check(not switches(), "tpi:boot to the slot already booted: no switch, no reset")

    print("writes into the dock")
    board.start_memory(0x0A, 0x01)
    check(("dock_writes", False) in take(), "a flash dock at boot: read-only")
    t.MEMDOCK(pre(1, 4), "")                                 # RAM slots 4 and 5: empty, 64K of RAM
    got = take()
    check(("dock_writes", True) in got and not [c for c in got if c[0] == "read"],
          "tpi:dock CODE 1,4: writes stored; nothing saved on leaving a flash dock")
    data = bytes(range(256)) * 256
    IMG[2][:] = data                                         # the program's data, written by the Z80
    t.MEMDOCK(pre(2, 10), "")
    got = take()
    s4 = open(os.path.join(b3.SLOTS_DIR, "S04.bin"), "rb").read()
    s5 = open(os.path.join(b3.SLOTS_DIR, "S05.bin"), "rb").read()
    check(s4 + s5 == data, "leaving the RAM dock: its 64K saved to S04 and S05")
    names = [c[0] for c in got]
    check(names.index("read") < names.index("load_at") and ("dock_writes", False) in got,
          "  before the new dock is loaded; the flash dock that follows is read-only")
    t.MEMDOCK(pre(1, 4), "")
    take()
    check(IMG[2] == data, "back to RAM slot 4: the data is there again")
    board.start_memory(0x0A, 0x01)
    take()
    check(not os.path.exists(os.path.join(b3.SLOTS_DIR, "S04.bin")), "and a boot clears it, as v2's power-off")

    print("writing slots (tpi:blkrcv on v3)")
    img = os.path.join(d, "temp.bin")

    def image(n, fill=0x5A):
        with open(img, "wb") as f:
            f.write(bytes((fill + i) & 0xFF for i in range(n)))
        return open(img, "rb").read()

    rom16 = image(16384)
    take()
    check(board.write_slot(2, 6, img) == "Flash slot 6", "a 16K .ROM into flash slot 6")
    f06 = open(os.path.join(b3.SLOTS_DIR, "F06.bin"), "rb").read()
    check(f06 == rom16 + bytes(16384), "  F06.bin: the image, zero-padded to 32K")
    dck = image(65536, 0x33)
    check(board.write_slot(1, 12, img) == "SRAM slots 12-13", "a 64K .DCK into SRAM slots 12-13")
    s12 = open(os.path.join(b3.SLOTS_DIR, "S12.bin"), "rb").read()
    s13 = open(os.path.join(b3.SLOTS_DIR, "S13.bin"), "rb").read()
    check(s12 + s13 == dck, "  S12 and S13: the two halves")
    for bad, why in ((7, "an odd slot"), (14 + 2, "past slot 15")):
        try:
            board.write_slot(2, bad, img)
            ok = False
        except ValueError:
            ok = True
        check(ok, "a 64K image into %s: ValueError" % why)
    image(65537)
    try:
        board.write_slot(2, 4, img)
        ok = False
    except ValueError:
        ok = True
    check(ok, "an image over 64K: ValueError")
    board.start_memory(0x0A, 0xA1)                          # dock flash 10-11 served
    take()
    cart = image(65536, 0x77)
    board.write_slot(2, 10, img)
    got = take()
    check(IMG[2] == cart and ("dock", False) in got and ("dock", True) in got,
          "writing the slots in the DOCK: reloaded there, live")
    image(32768, 0x11)
    board.write_slot(2, 1, img)
    check(not [c for c in take() if c[0] in ("switch", "load", "hold")],
          "writing the booted slot: the running ROM isn't touched (next boot)")

    sent_w = []
    t.SEND_MSG = lambda msg, msg2, st, force=False: sent_w.append((msg, msg2, st))
    t.LOG = lambda *a: None
    t.TSP = types.SimpleNamespace(f_name="/sd/TAP/game.dck")
    calls_w = []
    real_ws = t.board.write_slot
    t.board.write_slot = lambda m, s_, p: calls_w.append((m, s_, p)) or "Flash slots 4-5"
    t.BLKRCV(pre(2, 5), "")
    check(not calls_w and sent_w[-1][2] == t._8_A_Invalid_arg, "BLKRCV, a .DCK into odd slot 5: Report A, nothing written")
    t.BLKRCV(pre(3, 4), "")
    check(not calls_w and sent_w[-1][2] == t._8_A_Invalid_arg, "MEM 3: Report A")
    t.BLKRCV(pre(2, 4), "")
    check(calls_w == [(2, 4, "/TMP/temp.bin")] and sent_w[-1][:1] == ("Wrote Flash slots 4-5",) and sent_w[-1][2] == t._1_OK,
          "CODE 2,4: /TMP/temp.bin into flash 4, 0 OK (%r)" % sent_w[-1:])
    t.board.write_slot = lambda m, s_, p: (_ for _ in ()).throw(OSError(28, "ENOSPC"))
    t.BLKRCV(pre(2, 4), "")
    check(sent_w[-1][0] == "Writing the slot failed" and sent_w[-1][2] == t._3_F_Invalid_file,
          "a write that fails: Report F, said so")
    t.board.write_slot = real_ws

    print("ACTIVATE_SD with the socket empty")
    logs = []
    t.LOG = lambda msg, lvl=0: logs.append(msg)
    t.SAVE_LOG = lambda: None
    t.TSP = types.SimpleNamespace(sd_present=True, sd_cid=None)
    t.SDCard = lambda *a: CALLS.append(("SDCard",)) or (_ for _ in ()).throw(AssertionError("SPI on an empty socket"))
    IN1[0] = 0xFF
    take()
    try:
        t.ACTIVATE_SD()
        raised = None
    except OSError as e:
        raised = e
    got = take()
    check(raised is not None and raised.args[0] == 19, "OSError(19), as a failed mount (%r)" % (raised,))
    check(not [c for c in got if c[0] in ("Pin", "SPI", "SDCard")],
          "no SD line touched, no SPI: only the switch read (%r)" % got)
    check(t.TSP.sd_present is False and logs and "detect switch" in logs[-1],
          "sd_present False; logged as a card that went (%r)" % logs[-1:])

    print()
    if FAILS:
        print("%d FAILED" % len(FAILS))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
