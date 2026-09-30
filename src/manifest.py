# MicroPython freeze manifest for the TS-Pico firmware build.
#
# This file replaces ports/rp2/boards/manifest.py in v1.20.0. The default
# rp2 manifest freezes rp2.py, _boot.py, _boot_fat.py PLUS a bunch of
# peripheral drivers (onewire, ds18x20, dht, neopixel, uasyncio) for
# stock Raspberry Pi Pico use. The TS-Pico hardware doesn't have any of
# those peripherals, so we strip them out — saving ~6KB of flash and
# ~20KB of RAM that would otherwise be wasted on unused module init.
#
# What we DO need from the default rp2 manifest:
#   _boot.py     — runs at startup to mount the LittleFS filesystem
#   _boot_fat.py — FAT filesystem support (used by SD card)
#   rp2.py       — wraps the C-level _rp2 module; provides asm_pio,
#                  PIOASMEmit, StateMachine constructor, etc.
#
# What we ADD on top: the TS package — five modules that hold the
# protocol implementation and command handlers. See docs/PROTOCOL.md
# for what each one does.
#
# CONTRIBUTORS — if you add a new file under TS/, also add a freeze()
# line for it here, otherwise it won't be baked into the UF2 and your
# code won't be visible at runtime.

# Default rp2 port Python modules that the firmware needs at runtime.
freeze("$(PORT_DIR)/modules", "_boot.py")
freeze("$(PORT_DIR)/modules", "_boot_fat.py")
freeze("$(PORT_DIR)/modules", "rp2.py")

# Our TS package — the actual TS-Pico firmware.
freeze("$(PORT_DIR)/modules", "TS/__init__.py")
freeze("$(PORT_DIR)/modules", "TS/tspico.py")
freeze("$(PORT_DIR)/modules", "TS/tspico_io.py")
freeze("$(PORT_DIR)/modules", "TS/sdcard.py")
freeze("$(PORT_DIR)/modules", "TS/extcmd.py")
freeze("$(PORT_DIR)/modules", "TS/printer.py")
freeze("$(PORT_DIR)/modules", "TS/catalog.py")
freeze("$(PORT_DIR)/modules", "TS/native.py")
freeze("$(PORT_DIR)/modules", "TS/channels.py")
