# The v3 board definition

Source: [`src/boards/TSPICO_V3/`](../../../src/boards/TSPICO_V3/):
`mpconfigboard.cmake`, `mpconfigboard.h`, `board_init.c`, `tspico_v3.h`,
`manifest.py`, `pins.csv`.

The MicroPython board for the TS-Pico v3 card (RP2350B), phase 3 of the v3
port plan (`docs/v3-firmware-port-plan.md` in the tspico-hardware repo). It
builds MicroPython v1.29.0 for the card with the bus pins held safe, and
nothing else yet: no TS modules and no bus code. The `tsbus` C module (the
phase 1 PIO programs and core 1 code) and the board layer under the firmware
(phase 4) come later. The v2 firmware does not use any of it. CI builds it in
the `build-v3` job ([boot.md](boot.md#ci-buildyml)).

The pin map is the bring-up firmware's (`firmware/bringup/board.h` in
tspico-hardware, from the schematic netlist), not the v2 map in
[hardware.md](../hardware.md).

## Map

| File | What it is |
|---|---|
| `mpconfigboard.cmake` | the build settings: platform, SDK board header, GPIO count, flash size, manifest, board C source, filesystem size |
| `mpconfigboard.h` | the compile-time settings: name, no PSRAM, the default peripheral pins, the start-up hook |
| `board_init.c` | `tspico_v3_safe_init()`, the safe pin state |
| `tspico_v3.h` | the pico-sdk board header |
| `manifest.py` | the freeze manifest |
| `pins.csv` | names for `machine.Pin` |

## `mpconfigboard.cmake`

Read by the port's `CMakeLists.txt` when `make` is given
`BOARD_DIR=…/src/boards/TSPICO_V3` (the board name, `TSPICO_V3`, is the
directory's name; the build goes to `build-TSPICO_V3/`).

| Setting | Value | Why |
|---|---|---|
| `PICO_PLATFORM` | `rp2350` | the Arm cores (the SDK's default for `rp2350`) |
| `PICO_BOARD_HEADER_DIRS`, `PICO_BOARD` | this directory, `tspico_v3` | the SDK takes `tspico_v3.h` from here |
| `PICO_NUM_GPIOS` | 48 | the QFN-80 package: without it `machine.Pin` stops at GP29, and SD, the OLED, the ESP32 and audio are on GP30-GP47 |
| `PICO_FLASH_SIZE_BYTES` | 16777216 | the port's CMake fails without it as a variable ("PICO_FLASH_SIZE_BYTES must be defined"). `tspico_v3.h` defines it for the compiler only, having no `pico_cmake_set` lines |
| `MICROPY_FROZEN_MANIFEST` | `manifest.py` here | see below |
| `MICROPY_SOURCE_BOARD` | `board_init.c` | adds the safe-init function to the build |
| `MICROPY_HW_FLASH_STORAGE_BYTES` | 14680064 (14 MB) | everything above the first 2 MB is the LittleFS filesystem, room for the slot images of phase 5. The firmware is about 316 KB of its 2 MB. Overridable from the command line |

## `mpconfigboard.h`

### `MICROPY_HW_BOARD_NAME`

`"TS-Pico v3"`: what `sys.implementation._machine` and the REPL banner say
("TS-Pico v3 with RP2350").

### `MICROPY_HW_ENABLE_PSRAM`

0. The APS6404L footprint (U22) is not fitted on proto1; images will live in
SRAM.

### Default peripheral pins

What `machine.UART(n)`, `I2C(n)` and `SPI(n)` use when no pins are given, set
to what each is wired to on the card:

| Peripheral | Pins | Wired to |
|---|---|---|
| `UART0` | TX 44, RX 45, no CTS/RTS | the ESP32-C3 |
| `UART1` | TX 36, RX 41, no CTS/RTS | nothing: 36 is a spare pad, 41 is OLED_CS. Pass pins to use it |
| `I2C0` | SCL 25, SDA 24 | the XL9555 expander at 20h |
| `I2C1` | SCL 43, SDA 42 | J3, for an I2C OLED |
| `SPI0` | SCK 38, MOSI 39, MISO 32 | the microSD socket |
| `SPI1` | SCK 42, MOSI 43, MISO 40 | J3, the SPI OLED (MISO is a spare pad) |

Why: the port's defaults would put UART0 on GP0/1, UART1 on GP4/5, I2C1 on
GP6/7 and SPI1 on GP8-GP11, which are MD0-MD7, the buffer enables and /BE on
this card. A peripheral made at the REPL without pins would drive the local
bus. The SPI0 and UART0 defaults also differ from the port's (GP6/7/4 and
GP0/1).

### `tspico_v3_safe_init()` and `MICROPY_BOARD_STARTUP`

The prototype, and the port's start-up hook defined to call it. `main()`
calls `MICROPY_BOARD_STARTUP()` right after `set_sys_clock_khz()`, before the
flash timing, the heap, USB or any Python (checked in the v1.29.0 build:
`bl tspico_v3_safe_init` follows `set_sys_clock_pll` in `main`). That is the
point where the bring-up firmware calls `board_safe_init()`.

## `board_init.c`

### Pin constants

`PIN_MD0` (0), `PIN_NAEN_LO` (8), `PIN_NAEN_HI` (9), `PIN_NDATA_OE` (10),
`PIN_BE_REQ` (11), `PIN_WAIT_REQ` (12), `PIN_Z80_A14` (13), `PIN_TAPE_IN`
(22), `PIN_TAPE_OUT` (23), `PIN_RESET_HOLD` (29), `PIN_OLED_DC` (34),
`PIN_NIOX_INT` (35), `PIN_SD_CS` (37), `PIN_OLED_CS` (41), `PIN_PSRAM_CS`
(47): the pins it sets, with the bring-up's names. Local to the file. The
`tsbus` module will need the same map, and one header should then hold it.

### `out(pin, v)`, `in_nopull(pin)`

`gpio_init`, then drive `v` as an output; or `gpio_init` and no pulls.

### `tspico_v3_safe_init()`

What: puts every pin that touches the 2068 or a chip select into a safe state
before anything else runs.

Steps, in order:

1. GP8-GP10 (the /OE of U1, U2 and U3, the 74LVC245s on the local bus):
   outputs, high. The buffers are off.
2. /BE request, /WAIT request and tape out: outputs, low.
3. MD0-MD7: inputs, no pulls.
4. GP13-GP22 (inputs from U4 and U6: A14 on GP13, /IORD on GP17, tape in
   on GP22): inputs, no pulls.
5. RESET_HOLD (GP29): input, no pulls, so R1 holds the 2068 in reset.
6. The expander's /INT (GP35): input, no pulls (it has a 10k pull-up).
7. PSRAM CS (GP47): input with the pull-up.
8. SD CS and OLED CS: outputs, high. OLED DC: output, low.

Why: GP8-GP10 have no external pull-ups and the RP2350 resets its pads with
pull-downs on, so until firmware runs all three buffers are enabled and U3
can drive the Z80's data bus. MD has no pulls because it is only sampled
while a buffer drives it, and RP2350 erratum E9 can latch a pad with its
input and pull-down both on at about 2 V. The same state as the bring-up's
`board_safe_init()` (`firmware/bringup/board.c` in tspico-hardware).

State: GPIO only. The pads keep their reset pull-downs on the outputs, as in
the bring-up firmware. MicroPython's soft reset (`machine_pin_deinit`) only
turns off pin interrupts, so the state holds across Ctrl-D. RESET_HOLD is
never driven here: releasing the 2068 is `tsbus`'s job.

Checked on proto1 board 1 (2026-10-09, REPL): GP8-GP10 out and high, /BE and
/WAIT requests out and low, RESET_HOLD an input reading 1, SD CS high, PSRAM
CS pulled up.

## `tspico_v3.h`

The pico-sdk board header: `TSPICO_V3`, `PICO_RP2350A 0` (48 GPIOs), 16 MB
flash, the crystal start-up multiplier 64, A2 silicon supported. A copy of
`firmware/bringup/boards/tspico_v3.h` in tspico-hardware, which phase 1's
bus test was built with; only the opening comment differs, and the two
should stay the same. `PICO_BOOT_STAGE2_CHOOSE_W25Q080` and
`PICO_FLASH_SPI_CLKDIV` are carried over; the RP2350 has no boot stage 2,
and MicroPython sets the flash timing itself (`rp2_flash_set_timing`).

## `manifest.py`

Freezes `_boot.py` (mounts or creates the LittleFS filesystem) and `rp2.py`
(`asm_pio`, `StateMachine`, `PIO`) from the port's `modules/`, and nothing
else.

Why not `$(PORT_DIR)/boards/manifest.py`, the port's default: CI's v2 job
replaces that file with `src/manifest.py` (the TS modules), and the stock
one adds `asyncio`, `onewire`, `ds18x20`, `dht` and `neopixel`, which this
board has no use for. The TS modules come in with the board layer (phase 4).

## `pins.csv`

Names for `machine.Pin("…")`: `MD0`-`MD7`, `NAEN_LO`, `NAEN_HI`, `NDATA_OE`,
`BE_REQ`, `WAIT_REQ`, `TAPE_IN`, `TAPE_OUT`, `I2C_SDA`, `I2C_SCL`,
`RESET_HOLD`, `AUDIO_R`, `SD_MISO`, `OLED_DC`, `NIOX_INT`, `SD_CS`, `SD_SCK`,
`SD_MOSI`, `OLED_CS`, `OLED_SCK`, `OLED_MOSI`, `WIFI_TX`, `WIFI_RX`,
`AUDIO_L`, `PSRAM_CS`. GP13-GP21 (inputs from U4 and U6) are not named:
the bring-up's `board.h`, which this follows, names only A14 (GP13). Naming
a pin does not reserve it: Python can still drive a bus pin by hand.

## Where comments and the code disagree

None known.
