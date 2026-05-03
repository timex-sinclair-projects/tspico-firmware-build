# MicroPython freeze manifest for the TS-Pico firmware build.
#
# This replaces ports/rp2/boards/manifest.py in v1.20.0. The default
# rp2 manifest only includes uasyncio + a few sensor libraries; it does
# NOT auto-freeze ports/rp2/modules/. We add explicit freeze() calls
# for the TS/ package.

# Default rp2 dependencies (matches stock v1.20.0 manifest content)
include("$(MPY_DIR)/extmod/uasyncio")
require("dht")
require("ds18x20")
require("onewire")

# Freeze the TS package. The base path is the directory holding this
# manifest (ports/rp2/boards/), so we walk up to ports/rp2/modules/
# where we staged the .py files.
freeze("$(PORT_DIR)/modules", "TS/__init__.py")
freeze("$(PORT_DIR)/modules", "TS/tspico.py")
freeze("$(PORT_DIR)/modules", "TS/tspico_io.py")
freeze("$(PORT_DIR)/modules", "TS/sdcard.py")
freeze("$(PORT_DIR)/modules", "TS/extcmd.py")
freeze("$(PORT_DIR)/modules", "TS/help.py")
