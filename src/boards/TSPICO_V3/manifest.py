# Freeze manifest for the TS-Pico v3 board (phase 3 of the v3 port plan).
#
# Only what the port needs to boot: _boot.py mounts the LittleFS filesystem,
# rp2.py wraps the _rp2 module. Not $(PORT_DIR)/boards/manifest.py: CI's v2
# build replaces that file with src/manifest.py, and the default one adds
# drivers (onewire, dht, neopixel, asyncio) this board has no use for. The
# TS modules come in with the board layer (phase 4).

freeze("$(PORT_DIR)/modules", "_boot.py")
freeze("$(PORT_DIR)/modules", "rp2.py")
