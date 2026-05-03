# MicroPython freeze manifest for the TS-Pico firmware build.
#
# This replaces ports/rp2/boards/manifest.py in v1.20.0. The default
# rp2 manifest does `freeze("$(PORT_DIR)/modules")` which freezes
# rp2.py, _boot.py, and _boot_fat.py. We need to keep those AND add
# our TS/ package on top.

# Default rp2 dependencies
include("$(MPY_DIR)/extmod/uasyncio")
require("onewire")
require("ds18x20")
require("dht")
require("neopixel")

# Default rp2 port Python modules that the firmware needs at runtime.
# rp2.py wraps the C-level _rp2 module and adds asm_pio + PIOASMEmit.
# _boot.py runs at startup to mount the LittleFS filesystem.
freeze("$(PORT_DIR)/modules", "_boot.py")
freeze("$(PORT_DIR)/modules", "_boot_fat.py")
freeze("$(PORT_DIR)/modules", "rp2.py")

# Our TS package
freeze("$(PORT_DIR)/modules", "TS/__init__.py")
freeze("$(PORT_DIR)/modules", "TS/tspico.py")
freeze("$(PORT_DIR)/modules", "TS/tspico_io.py")
freeze("$(PORT_DIR)/modules", "TS/sdcard.py")
freeze("$(PORT_DIR)/modules", "TS/extcmd.py")
freeze("$(PORT_DIR)/modules", "TS/help.py")
