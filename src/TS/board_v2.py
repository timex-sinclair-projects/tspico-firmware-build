# The v2 TS-Pico (RP2040): the hardware behind TS/board.py.
#
# The code here was in main.py and TS/tspico.py until phase 4 of the v3 port
# plan (docs/v3-board-layer-proposal.md) moved it behind the board layer,
# unchanged. The 2068's memory is a parallel flash and an SRAM, steered by two
# PIO state machines (set_ctrl, sel_bank); ports 0Eh/0Fh are TS_IO_DUAL on
# PIO0 SM0; the SD card's SPI lines are the Z80 data lines D0-D2, so SD and the
# bus take turns.

import utime
import _thread

from machine import Pin, SPI, freq
from rp2 import StateMachine, asm_pio

from TS.tspico_io import TS_IO_DUAL, set_ctrl, sel_bank

NAME = "v2"
PIO_MQ = True       # MQ is a PIO state machine: tspico_io may use its registers and DMA

# Holds SM0 while the SD card has GPIO 2-4 (sd_take_bus).
@asm_pio(
    autopull=True,
    pull_thresh=8,
)
def NULL_SM():
    nop()


_rom = None         # set_ctrl on SM4: /BE, A14_L and the flash/SRAM chip enables
_bank = None        # sel_bank on SM5: the A15-A18 slot lines


def early_init():
    """The bus-control pins at their idle levels, and the clock. main.py calls
    this first thing, before TS2068_IO."""
    U6_EN = Pin(12, Pin.OUT, Pin.PULL_UP)
    WAIT = Pin(14, Pin.OUT, Pin.PULL_DOWN)     # TS_IO_DUAL waits on GPIO 14 as /PICOSEL (the name is unverified: hardware.md)
    U10_ENA = Pin(19, Pin.OUT, Pin.PULL_UP)
    U13_ENA = Pin(20, Pin.OUT, Pin.PULL_UP)
    BE = Pin(21, Pin.OUT, Pin.PULL_UP)
    Pin(26, Pin.IN, Pin.PULL_DOWN)             # ROSCS
    U10_WE = Pin(27, Pin.OUT, Pin.PULL_UP)

    U6_EN.value(1)
    WAIT.value(1)
    U10_ENA.value(1)
    U13_ENA.value(1)
    BE.value(1)
    U10_WE.value(1)

    freq(270_000_000)


def start_memory(rom_sm, bank_sm):
    """Start the two slot state machines and map the boot and dock slots."""
    global _rom, _bank
    # For DCK access and no ROM mapping, set_dck instead:
    #     StateMachine(4, set_dck, freq=150_000_000, jmp_pin=Pin(26), out_base=Pin(19, Pin.OUT))
    _rom = StateMachine(4, set_ctrl, freq=150_000_000, in_base=Pin(0, Pin.IN), jmp_pin=Pin(26), set_base=Pin(21, Pin.OUT), out_base=Pin(19, Pin.OUT))
    _rom.active(1)
    _bank = StateMachine(5, sel_bank, freq=150_000_000, jmp_pin=Pin(26), out_base=Pin(15, Pin.OUT))
    _bank.active(1)
    map_slots(rom_sm, bank_sm)


def map_slots(rom_sm, bank_sm):
    """Switch the boot and dock slots, under a running 2068."""
    _rom.put(rom_sm)
    _bank.put(bank_sm)


def make_mq():
    """A new MQ: TS_IO_DUAL on PIO0 SM0, not started. It keeps the old SM's Y."""
    return StateMachine(0, TS_IO_DUAL, freq=30_000_000, out_base=Pin(2, Pin.OUT),
                        in_base=Pin(2, Pin.IN), jmp_pin=Pin(11),
                        sideset_base=Pin(12, Pin.OUT))


def restart_mq(MQ):
    """Stop MQ for 10 ms and start it again."""
    MQ.active(0)
    utime.sleep(0.01)
    MQ.active(1)


def sd_take_bus():
    """Give GPIO 2-4 to the SD card: SM0 parked on NULL_SM (returned, as the
    new MQ), and U6 held off (GPIO 12 high) so the 2068 can't fight the card.
    make_mq() hands the bus back."""
    sm = StateMachine(0, NULL_SM, freq=15_000_000)
    sm.active(1)
    sm.active(0)
    Pin(12, Pin.OUT, value=1)
    return sm


def sd_cs():
    """The SD card's chip select: GPIO 28."""
    return Pin(28, Pin.OUT, Pin.PULL_UP)


def sd_spi():
    """SPI0 on GPIO 2-4 (SCK, MOSI, MISO): Z80 D0-D2."""
    return SPI(0, sck=Pin(2, Pin.IN), mosi=Pin(3, Pin.IN), miso=Pin(4, Pin.IN))


def sd_release_bus():
    """After the card is unmounted: CS high, GPIO 2-4 driven low until the bus
    state machine takes them back. Whether the clamp is needed (U6 keeps the
    2068 off these pins during SD use since #61) needs a scope (audit §4)."""
    Pin(28, Pin.OUT, Pin.PULL_UP).value(1)
    for p in (2, 3, 4):
        Pin(p, Pin.OUT).value(0)


def make_led():
    """The LED: GPIO 25."""
    return Pin(25, Pin.OUT)


def background(fn, args):
    """Run fn(*args) on core 1."""
    _thread.start_new_thread(fn, args)
