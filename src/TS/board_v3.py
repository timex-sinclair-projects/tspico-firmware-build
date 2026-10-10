# The v3 card (RP2350B): the hardware behind TS/board.py.
#
# Phase 4 of the v3 port plan (docs/v3-board-layer-proposal.md). The card has
# no memory chips: the tsbus C module serves the 2068's ROM and DOCK from SRAM
# and answers ports 0Eh/0Fh from core 1 (docs/reference/firmware/tsbus.md).
# The SD card has its own SPI pins, so SD never takes the bus; the LED is on
# the XL9555 expander; core 1 belongs to tsbus. Same names as board_v2.py.

import tsbus
from machine import Pin, SPI, I2C, Timer

NAME = "v3"
PIO_MQ = False      # MQ is tsbus.MQ(): tspico_io must not touch PIO0 SM0
SLOTS = False       # no flash/SRAM slots until phase 5: the slot commands refuse
HAS_CORE1 = False   # core 1 runs tsbus; background() runs on core 0

# The ROM the 2068 boots: HOME (16K) then EXROM (16K), on the flash
# filesystem. Phase 5 replaces this with the slot files.
ROM_FILE = "/rom/TSPICO-23.ROM"

_SD_CS = 37
_SD_SCK, _SD_MOSI, _SD_MISO = 38, 39, 32

_IOX_ADDR = 0x20
_IOX_OUT0 = 2
_IOX_OUT0_SAFE = 0xE0   # no bus request, no NMI, OLED in reset, ESP32 off, LED off
_X_NLED = 0x20          # bit 5, active low

# The LED dimmer: D4 on R5 (100R) is far too bright at full current, so
# while it is on it is lit for the first LED_BRIGHTNESS % of every 10 ms
# (100 Hz). config.ini's LED_BRIGHTNESS sets it (led_brightness).
LED_PERIOD_US = 10_000
LED_BRIGHTNESS = 5


def early_init():
    """tsbus up: 250 MHz, the bus programs, core 1. The 2068 stays held in
    reset until start_memory. The safe pin state was set in C at start-up."""
    tsbus.start()


def start_memory(rom_sm, bank_sm):
    """Load ROM_FILE into the HOME and EXROM images and release the 2068
    into it. rom_sm and bank_sm (the v2 slot words) are not used."""
    with open(ROM_FILE, "rb") as f:
        rom = f.read()
    m = memoryview(rom)
    tsbus.hold(True)
    tsbus.load(tsbus.HOME, m[:16384])
    tsbus.load(tsbus.EXROM, m[16384:])
    tsbus.exrom(True)
    tsbus.dock(True)
    tsbus.serve(True)
    tsbus.hold(False)


def map_slots(rom_sm, bank_sm):
    """No slots yet: the slot commands refuse before they get here."""
    pass


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


def sd_take_bus():
    """The SD card has its own pins: the bus stays as it is. Returns MQ."""
    return tsbus.MQ()


def sd_cs():
    """The SD card's chip select: GPIO 37."""
    return Pin(_SD_CS, Pin.OUT, Pin.PULL_UP)


def sd_spi():
    """SPI0 on its own pins: SCK 38, MOSI 39, MISO 32."""
    return SPI(0, sck=Pin(_SD_SCK), mosi=Pin(_SD_MOSI), miso=Pin(_SD_MISO))


def sd_release_bus():
    """After the card is unmounted: CS high."""
    Pin(_SD_CS, Pin.OUT, Pin.PULL_UP).value(1)


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
        self._i2c = I2C(0)          # the board's defaults: SCL 25, SDA 24
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
