# The v3 card (RP2350B): the hardware behind TS/board.py.
#
# Phase 4 of the v3 port plan (docs/v3-board-layer-proposal.md). The card has
# no memory chips: the tsbus C module serves the 2068's ROM and DOCK from SRAM
# and answers ports 0Eh/0Fh from core 1 (docs/reference/firmware/tsbus.md).
# The SD card has its own SPI pins, so SD never takes the bus; the LED is on
# the XL9555 expander; core 1 belongs to tsbus. Same names as board_v2.py.

import os
import time
import tsbus
from machine import Pin, SPI, I2C, Timer

NAME = "v3"
PIO_MQ = False      # MQ is tsbus.MQ(): tspico_io must not touch PIO0 SM0
SLOTS = False       # tpi:blkrcv refuses until phase 5 step 4 (NO_SLOTS); boot and dock work
HAS_CORE1 = False   # core 1 runs tsbus; background() runs on core 0

# The slots (phase 5, docs/v3-slots-proposal.md): v2's two chips of sixteen
# 32K slots, as files. Fnn.bin is flash slot nn, kept; Snn.bin is SRAM slot
# nn, deleted at every boot (v2's SRAM loses its contents at power-off). A
# missing file is an empty slot. A ROM slot is HOME (16K) then EXROM (16K).
SLOTS_DIR = "/slots"
SLOT_SIZE = 32768
MEM_SRAM, MEM_FLASH = 1, 2      # ROM_SM's two-bit memory codes

# The last fallback for the boot ROM, when neither the boot slot nor flash
# slot 1 has a file: the 2068 is never released into an empty ROM.
ROM_FILE = "/rom/TSPICO-23.ROM"

_SD_CS = 37
_SD_SCK, _SD_MOSI, _SD_MISO = 38, 39, 32

_IOX_ADDR = 0x20
_IOX_IN1 = 1            # input port 1: the joystick, nBUSAK_L, SD_CD
_IOX_OUT0 = 2
_IOX_OUT0_SAFE = 0xE0   # no bus request, no NMI, OLED in reset, ESP32 off, LED off
_X_NLED = 0x20          # bit 5, active low
_X_SD_CD = 0x80         # port 1 bit 7: low = a card in (the TF-01A's switch closes to GND; R38 pulls it up)

# A card the switch has only just seen is left alone this long before the
# first SPI clock, so it is seated and powered before its lines are driven.
SD_SETTLE_MS = 250

_i2c = None             # I2C(0), shared by the LED and the card-detect read
_cd_since = None        # ticks_ms when the switch was first seen closed; None: no card


def _iox():
    global _i2c
    if _i2c is None:
        _i2c = I2C(0)               # the board's defaults: SCL 25, SDA 24
    return _i2c

# The LED dimmer: D4 on R5 (100R) is far too bright at full current, so
# while it is on it is lit for the first LED_BRIGHTNESS % of every 10 ms
# (100 Hz). config.ini's LED_BRIGHTNESS sets it (led_brightness).
LED_PERIOD_US = 10_000
LED_BRIGHTNESS = 5


def early_init():
    """tsbus up: 250 MHz, the bus programs, core 1. The 2068 stays held in
    reset until start_memory. The safe pin state was set in C at start-up."""
    tsbus.start()


_served = None      # ((boot mem, slot), (dock mem, slot)) the 2068 is served now

# The one buffer every slot passes through: a ROM, each half of the dock, a
# RAM dock being saved. Allocated here, at import, while the heap is clean:
# once the firmware runs, the v3 heap (about 190K) has no 64K block, and a
# 32K one isn't certain either (hardware, 2026-10-10: tpi:dock failed with
# MemoryError building a 64K dock image).
_buf = bytearray(SLOT_SIZE)
_zeros = bytes(1024)                # for an empty half, without another 32K


def _keys(rom_sm, bank_sm):
    """The boot and dock (mem, slot) pairs of v2's two words."""
    return (rom_sm & 3, bank_sm & 15), ((rom_sm >> 2) & 3, (bank_sm >> 4) & 15)


def slot_path(mem, slot):
    """The file behind slot `slot` (0-15) of memory `mem` (MEM_FLASH, MEM_SRAM)."""
    return "%s/%s%02d.bin" % (SLOTS_DIR, "S" if mem == MEM_SRAM else "F", slot)


def read_slot_into(mem, slot, buf):
    """Read a slot's 32K into buf (32K, a bytearray or memoryview), in
    place. False if the slot has no file or the file isn't 32K; buf is then
    untouched."""
    path = slot_path(mem, slot)
    try:
        if os.stat(path)[6] != SLOT_SIZE:
            return False
        with open(path, "rb") as f:
            f.readinto(buf)
    except OSError:
        return False
    return True


def rom_slot_empty(mem, slot):
    """True if slot `slot` of memory `mem` has no 32K file: tpi:boot refuses
    it, rather than boot_rom falling back to another ROM unasked."""
    try:
        return os.stat(slot_path(mem, slot))[6] != SLOT_SIZE
    except OSError:
        return True


def clear_sram_slots():
    """Delete every Snn.bin: the SRAM slots start empty, as v2's chip does."""
    try:
        names = os.listdir(SLOTS_DIR)
    except OSError:
        return
    for n in names:
        if n.startswith("S") and n.endswith(".bin"):
            try:
                os.remove(SLOTS_DIR + "/" + n)
            except OSError:
                pass


def boot_rom(rom_sm, bank_sm):
    """Read the ROM to boot into _buf; return a note if it isn't the one
    asked for, else None.

    The boot memory is rom_sm's bits 0-1 and the slot bank_sm's bits 0-3.
    If that slot has no 32K file: flash slot 1, then ROM_FILE."""
    mem, slot = rom_sm & 3, bank_sm & 15
    if read_slot_into(mem, slot, _buf):
        return None
    want = "%s slot %d" % ("SRAM" if mem == MEM_SRAM else "flash", slot)
    if (mem, slot) != (MEM_FLASH, 1):
        if read_slot_into(MEM_FLASH, 1, _buf):
            return "no ROM in %s: booted flash slot 1" % want
        want += " or flash slot 1"
    with open(ROM_FILE, "rb") as f:
        f.readinto(_buf)
    return "no ROM in %s: booted %s" % (want, ROM_FILE)


def load_dock(rom_sm, bank_sm):
    """The dock slots into the DOCK image, a 32K half at a time through
    _buf (tsbus.load_at): the dock slot, then for an even slot the next one,
    as v2's 64K cartridge spans two slots numbered by the even one. A half
    with no file is zeros, as an empty v2 slot reads. The caller turns DOCK
    serving off around it if the 2068 is running."""
    mem, slot = (rom_sm >> 2) & 3, (bank_sm >> 4) & 15
    for half, s in ((0, slot), (1, slot + 1 if slot % 2 == 0 else None)):
        base = half * SLOT_SIZE
        if s is not None and read_slot_into(mem, s, _buf):
            tsbus.load_at(tsbus.DOCK, base, _buf)
        else:
            for off in range(0, SLOT_SIZE, len(_zeros)):
                tsbus.load_at(tsbus.DOCK, base + off, _zeros)


def save_ram_dock(dock):
    """Before a RAM dock (MEM_SRAM) is switched away: its image, with the
    Z80's writes in it, back to Snn (and Snn+1 for an even slot), so
    switching back finds the data, as v2's SRAM keeps it until power-off.
    A 32K half at a time through _buf; about 64K of flash writes."""
    mem, slot = dock
    if mem != MEM_SRAM:
        return
    try:
        os.mkdir(SLOTS_DIR)
    except OSError:
        pass
    for half, s in ((0, slot), (1, slot + 1 if slot % 2 == 0 else None)):
        if s is None:
            continue
        tsbus.read(tsbus.DOCK, _buf, half * SLOT_SIZE)
        with open(slot_path(mem, s), "wb") as f:
            f.write(_buf)


def start_memory(rom_sm, bank_sm):
    """Clear the SRAM slots, load the boot ROM (HOME, EXROM) and the dock
    from the slot files (boot_rom, load_dock), and release the 2068 into
    them. Returns boot_rom's note, for the caller to log, or None."""
    global _served
    clear_sram_slots()
    tsbus.hold(True)
    note = boot_rom(rom_sm, bank_sm)
    m = memoryview(_buf)
    tsbus.load(tsbus.HOME, m[:16384])
    tsbus.load(tsbus.EXROM, m[16384:])
    load_dock(rom_sm, bank_sm)
    tsbus.dock_writes((rom_sm >> 2) & 3 == MEM_SRAM)   # a flash dock is read-only, as v2's chip
    tsbus.exrom(True)
    tsbus.dock(True)
    tsbus.serve(True)
    tsbus.hold(False)
    _served = _keys(rom_sm, bank_sm)
    if note:
        print("[board] " + note)
    return note


def map_slots(rom_sm, bank_sm):
    """tpi:boot and tpi:dock: show the 2068 what the two words now say.

    Only what changed is loaded, through _buf. The dock first, live, as
    v2's tpi:dock: a RAM dock being left is saved back first
    (save_ram_dock), DOCK serving is off for the copy (a read sees an empty
    dock, never half the new one, as tsbus.switch does), and dock writes are
    stored for a RAM dock and ignored for a flash one (tsbus.dock_writes).
    Then the ROM, which tsbus.switch loads with the 2068 held for RESET_MS
    (200 ms), so it starts cleanly in the new ROM rather than running a mix
    of the two (docs/v3-slots-proposal.md, decision 2). Returns boot_rom's
    note if the ROM fell back, else None; MEMBOOT refuses an empty slot
    first."""
    global _served
    boot, dock = _keys(rom_sm, bank_sm)
    note = None
    if _served is None or dock != _served[1]:
        if _served is not None:
            save_ram_dock(_served[1])
        tsbus.dock(False)
        load_dock(rom_sm, bank_sm)
        tsbus.dock_writes(dock[0] == MEM_SRAM)
        tsbus.dock(True)
    if _served is None or boot != _served[0]:
        note = boot_rom(rom_sm, bank_sm)
        m = memoryview(_buf)
        tsbus.switch(home=m[:16384], exrom=m[16384:])
    _served = (boot, dock)
    return note


def make_mq():
    """tsbus.MQ(), with both queues emptied, as a new v2 state machine's
    FIFOs are. The status byte is left alone (ACTIVATE_MQ sets BUSY)."""
    mq = tsbus.MQ()
    while mq.rx_fifo():
        mq.get()
    while mq.tx_fifo():
        mq.exec("pull (noblock)")
    return mq


def restart_mq(MQ):
    """Nothing to restart: core 1 is always serving."""
    pass


def card_present():
    """The socket's detect switch: True with a card in, False without, None
    if the expander doesn't answer (then only a mount can tell)."""
    try:
        return not (_iox().readfrom_mem(_IOX_ADDR, _IOX_IN1, 1)[0] & _X_SD_CD)
    except OSError:
        return None


def sd_card_ready():
    """ACTIVATE_SD asks this before it touches an SD line. False: the switch
    says the socket is empty, so no SPI at all. True: a card is in, and has
    been for SD_SETTLE_MS (it waits out the rest when the card is new), or
    the switch can't be read and the mount will find out."""
    global _cd_since
    p = card_present()
    if p is None:
        return True
    if not p:
        _cd_since = None
        return False
    now = time.ticks_ms()
    if _cd_since is None:
        _cd_since = now
    wait = SD_SETTLE_MS - time.ticks_diff(now, _cd_since)
    if wait > 0:
        time.sleep_ms(wait)
    return True


def sd_take_bus():
    """The SD card has its own pins: the bus stays as it is. Returns MQ."""
    return tsbus.MQ()


def sd_cs():
    """The SD card's chip select, GPIO 37, driven high (deselected)."""
    return Pin(_SD_CS, Pin.OUT, value=1)


def sd_spi():
    """SPI0 on its own pins: SCK 38, MOSI 39, MISO 32."""
    return SPI(0, sck=Pin(_SD_SCK), mosi=Pin(_SD_MOSI), miso=Pin(_SD_MISO))


def sd_release_bus():
    """After the card is unmounted: nothing drives the socket. CS, SCK,
    MOSI and MISO go back to plain inputs, no pulls (RP2350 erratum E9: a
    pull-down can latch the pad), as board_init.c leaves them at power-on.
    R34 holds CS high, so a card that is in stays deselected, and R35 holds
    MISO; SCK and MOSI float behind their 33R. A card going in then
    meets no driven line, which could power it through its I/O pins before
    its VDD contact makes."""
    for p in (_SD_CS, _SD_SCK, _SD_MOSI, _SD_MISO):
        Pin(p, Pin.IN, pull=None)


class ExpanderLED:
    """D4, on the XL9555's port 0 bit 5 (active low), with Pin's value, on,
    off and toggle, dimmed to LED_BRIGHTNESS %.

    While it is on, a periodic machine.Timer lights it every LED_PERIOD_US
    and a one-shot timer darkens it again after the on-time: two I2C writes
    (about 100 us each) per period, whatever the brightness; none while it
    is off (both timers stopped). At 100 % it is simply lit. The timers'
    callbacks are soft (scheduled on core 0), so a long C call there stretches
    a period: a flicker, not a fault. The other port 0 bits stay at their
    safe values (board_init.c)."""

    def __init__(self):
        self._i2c = _iox()
        self._v = 0
        self._lit = False
        self._on_us = LED_PERIOD_US * LED_BRIGHTNESS // 100
        self._period = None
        self._off = None
        self._light_cb = self._light    # bound once: the callbacks allocate nothing
        self._dark_cb = self._dark

    def _write(self, lit):
        if lit != self._lit:
            self._lit = lit
            out = _IOX_OUT0_SAFE & ~_X_NLED if lit else _IOX_OUT0_SAFE
            try:
                self._i2c.writeto_mem(_IOX_ADDR, _IOX_OUT0, bytes((out,)))
            except OSError:
                pass                # no expander answering: the LED is cosmetic

    def _light(self, t):
        self._write(True)
        self._off.init(mode=Timer.ONE_SHOT, period=self._on_us, tick_hz=1_000_000, callback=self._dark_cb)

    def _dark(self, t):
        self._write(False)

    def _stop(self):
        for t in (self._period, self._off):
            if t is not None:
                t.deinit()
        self._period = self._off = None

    def _start(self):
        self._write(True)
        if self._on_us < LED_PERIOD_US:
            self._off = Timer()
            self._off.init(mode=Timer.ONE_SHOT, period=self._on_us, tick_hz=1_000_000, callback=self._dark_cb)
            self._period = Timer(mode=Timer.PERIODIC, period=LED_PERIOD_US, tick_hz=1_000_000, callback=self._light_cb)

    def brightness(self, pct):
        """The on-time as a percentage of the period, 1-100."""
        self._on_us = LED_PERIOD_US * pct // 100
        if self._v:
            self._stop()
            self._start()

    def value(self, v=None):
        if v is None:
            return self._v
        v = 1 if v else 0
        if v != self._v:
            self._v = v
            if v:
                self._start()
            else:
                self._stop()
                self._write(False)
        return None

    def on(self):
        self.value(1)

    def off(self):
        self.value(0)

    def toggle(self):
        self.value(not self._v)


def make_led():
    """The LED: D4 through the expander."""
    return ExpanderLED()


def led_brightness(led, pct):
    """config.ini's LED_BRIGHTNESS (1-100, %) for the LED make_led gave."""
    led.brightness(pct)


def background(fn, args):
    """Core 1 belongs to tsbus: run fn(*args) here, on core 0."""
    fn(*args)
