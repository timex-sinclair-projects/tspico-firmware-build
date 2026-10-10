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

# Flash divider 3 in boot2 (tspico_v3.h has 2, the bring-up's boot value).
# After every flash erase or program the SDK re-enables XIP through boot2,
# before MicroPython's own divider is restored by code in flash; at tsbus's
# 250 MHz divider 2 would run the flash at 125 MHz, and core 0 hangs on the
# first LittleFS write. Divider 3: 50 MHz at boot, 83 MHz under tsbus.
add_compile_definitions(PICO_FLASH_SPI_CLKDIV=3)

# The bus: the tsbus C module (src/tsbus), always built into this board.
set(USER_C_MODULES ${MICROPY_BOARD_DIR}/../../tsbus/micropython.cmake)

# Ends the GC heap at 0x20040000 (memmap/), leaving the top 256 KB of SRAM to
# tsbus. MicroPython adds its own linker-script override directories to the
# firmware target after this file is read, and the first directory holding a
# file wins, so this one is put in front of them once the whole port's
# CMakeLists has run.
function(tspico_v3_linker_override)
    get_property(paths TARGET ${MICROPY_TARGET} PROPERTY PICO_TARGET_LINKER_SCRIPT_OVERRIDE_PATHS)
    set_property(TARGET ${MICROPY_TARGET} PROPERTY PICO_TARGET_LINKER_SCRIPT_OVERRIDE_PATHS
        ${MICROPY_BOARD_DIR}/memmap ${paths})
endfunction()
cmake_language(DEFER CALL tspico_v3_linker_override)

# The filesystem takes everything above the first 2 MB: room for the slot
# images (phase 5) on the QSPI flash.
if(NOT DEFINED MICROPY_HW_FLASH_STORAGE_BYTES)
    set(MICROPY_HW_FLASH_STORAGE_BYTES 14680064)  # 16 MB - 2 MB
endif()
