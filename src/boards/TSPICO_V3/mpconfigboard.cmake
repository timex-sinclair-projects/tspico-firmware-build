# TS-Pico v3 (proto1): RP2350B, 48 GPIOs, 16 MB QSPI flash, no PSRAM.
# Built from outside the MicroPython tree:
#   make -C ports/rp2 BOARD_DIR=<this repo>/src/boards/TSPICO_V3

set(PICO_PLATFORM "rp2350")

# The SDK board header lives here, not in the SDK.
list(APPEND PICO_BOARD_HEADER_DIRS ${MICROPY_BOARD_DIR})
set(PICO_BOARD "tspico_v3")

# QFN-80: GP30-GP47 exist (SD, the OLED, the ESP32, audio).
set(PICO_NUM_GPIOS 48)

# The port's CMake needs the flash size as a variable; tspico_v3.h only sets
# it for the compiler (it has no pico_cmake_set lines).
set(PICO_FLASH_SIZE_BYTES 16777216)  # GD25Q128E, 16 MB

# Only _boot.py and rp2.py; see manifest.py.
set(MICROPY_FROZEN_MANIFEST ${MICROPY_BOARD_DIR}/manifest.py)

# tspico_v3_safe_init(), run by MICROPY_BOARD_STARTUP (mpconfigboard.h).
set(MICROPY_SOURCE_BOARD ${MICROPY_BOARD_DIR}/board_init.c)

# The filesystem takes everything above the first 2 MB: room for the slot
# images (phase 5) on the QSPI flash.
if(NOT DEFINED MICROPY_HW_FLASH_STORAGE_BYTES)
    set(MICROPY_HW_FLASH_STORAGE_BYTES 14680064)  # 16 MB - 2 MB
endif()
