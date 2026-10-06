# TS-Pico upgrade firmware -- frozen as main.py in the upgrade UF2 only.
#
# Board setup as in src/main.py and TS2068_IO, with the default mapping (the
# TS-2068 ROM in flash slot 1, the dock on flash page 0), then upgrade.serve.
# See src/upgrade/upgrade.py.
from machine import Pin, freq
from rp2 import StateMachine
from TS.tspico_io import TS_IO_DUAL, set_ctrl, sel_bank
import upgrade
import upgrade_data

U6_EN = Pin(12, Pin.OUT, Pin.PULL_UP)
WAIT = Pin(14, Pin.OUT, Pin.PULL_DOWN)     # TS_IO_DUAL waits on GPIO 14 as /PICOSEL (the name is unverified: hardware.md)
U10_ENA = Pin(19, Pin.OUT, Pin.PULL_UP)
U13_ENA = Pin(20, Pin.OUT, Pin.PULL_UP)
BE = Pin(21, Pin.OUT, Pin.PULL_UP)
ROSCS = Pin(26, Pin.IN, Pin.PULL_DOWN)
U10_WE = Pin(27, Pin.OUT, Pin.PULL_UP)
U3_CS = Pin(28, Pin.OUT, Pin.PULL_UP)       # the SD card, not used here
U6_EN.value(1)
WAIT.value(1)
U10_ENA.value(1)
U13_ENA.value(1)
BE.value(1)
U10_WE.value(1)
U3_CS.value(1)
freq(270_000_000)

ROM = StateMachine(4, set_ctrl, freq=150_000_000, in_base=Pin(0, Pin.IN), jmp_pin=Pin(26),
                   set_base=Pin(21, Pin.OUT), out_base=Pin(19, Pin.OUT))
ROM.active(1)
BANK = StateMachine(5, sel_bank, freq=150_000_000, jmp_pin=Pin(26), out_base=Pin(15, Pin.OUT))
BANK.active(1)
ROM.put(10)                                 # config.ini's ROM_SM default: both from flash
BANK.put(1)                                 # ROM = flash slot 1, dock = flash page 0

MQ = StateMachine(0, TS_IO_DUAL, freq=30_000_000, out_base=Pin(2, Pin.OUT),
                  in_base=Pin(2, Pin.IN), jmp_pin=Pin(11), sideset_base=Pin(12, Pin.OUT))
MQ.active(1)

upgrade.serve(MQ, upgrade_data)
