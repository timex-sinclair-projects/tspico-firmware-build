# Freeze manifest for the TS-Pico v3 board.
#
# _boot.py mounts the LittleFS filesystem, rp2.py wraps the _rp2 module. Not
# $(PORT_DIR)/boards/manifest.py: CI's v2 job replaces that file with
# src/manifest.py, and the default one adds drivers (onewire, dht, neopixel,
# asyncio) this board has no use for.
#
# The TS package is frozen straight from the repo's src/ (two levels up from
# this board directory), so the v3 build needs no staging step. buildinfo.py
# is generated there first (tools/gen-buildinfo.py), as for the v2 build.
# board_v2.py is left out: board.py picks board_v3 on this build.

freeze("$(PORT_DIR)/modules", "_boot.py")
freeze("$(PORT_DIR)/modules", "rp2.py")

freeze("$(BOARD_DIR)/../..", (
    "TS/__init__.py",
    "TS/tspico.py",
    "TS/buildinfo.py",
    "TS/tspico_io.py",
    "TS/sdcard.py",
    "TS/extcmd.py",
    "TS/printer.py",
    "TS/catalog.py",
    "TS/native.py",
    "TS/channels.py",
    "TS/board.py",
    "TS/board_v3.py",
))
