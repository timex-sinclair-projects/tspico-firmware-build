# MicroPython freeze manifest for the UPGRADE UF2 (not the TS-Pico firmware).
#
# The upgrade UF2 carries everything it needs frozen into flash: the bus
# programs and streaming from tspico_io, the upgrade loop, the generated
# payload (the updater tape and both ROM images, from tools/build-upgrade.py)
# and main.py -- a frozen main.py runs at boot even with an empty filesystem,
# which is what the web updater leaves after flash_nuke. CI stages these files
# in ports/rp2/modules-upgrade/ (see .github/workflows/build.yml).
freeze("$(PORT_DIR)/modules", "_boot.py")
freeze("$(PORT_DIR)/modules", "rp2.py")
freeze("$(PORT_DIR)/modules-upgrade", "TS/__init__.py")
freeze("$(PORT_DIR)/modules-upgrade", "TS/tspico_io.py")
freeze("$(PORT_DIR)/modules-upgrade", "TS/sdcard.py")
freeze("$(PORT_DIR)/modules-upgrade", "upgrade.py")
freeze("$(PORT_DIR)/modules-upgrade", "upgrade_data.py")
freeze("$(PORT_DIR)/modules-upgrade", "main.py")
