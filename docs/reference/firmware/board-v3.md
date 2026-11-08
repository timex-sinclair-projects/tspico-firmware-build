# The v3 board definition

Source: [`src/boards/TSPICO_V3/`](../../../src/boards/TSPICO_V3/):
`mpconfigboard.cmake`, `mpconfigboard.h`, `board_init.c`, `tspico_v3_pins.h`,
`tspico_v3.h`, `memmap/section_extra_post_platform_end.incl`,
`memmap/pico_psram_region.ld`, `manifest.py`,
`pins.csv`.

The MicroPython board for the TS-Pico v3 card (RP2350B), phase 3 of the v3
port plan (`docs/v3-firmware-port-plan.md` in the tspico-hardware repo). It
builds MicroPython v1.29.0 for the card with the bus pins held safe and the
`tsbus` C module, the card's bus ([tsbus.md](tsbus.md)), built in. The board
sets up what `tsbus` needs from MicroPython: SRAM above the GC heap for the
images, core 1 free of `_thread`, and a flash divider that survives 250 MHz.
It also brings up the 8 MB PSRAM (U22): 1 MB of it goes to the GC heap and 7
MB is kept for the board.
No TS modules yet; the board layer under the firmware is phase 4. The v2
firmware does not use any of it. CI builds it in the `build-v3` job
([boot.md](boot.md#ci-buildyml)).

The pin map is the bring-up firmware's (`firmware/bringup/board.h` in
tspico-hardware, from the schematic netlist), not the v2 map in
[hardware.md](../hardware.md).

## Map

| File | What it is |
|---|---|
| `mpconfigboard.cmake` | the build settings: platform, SDK board header, GPIO count, flash size and boot2 divider, PSRAM, manifest, board C source, `tsbus`, the linker override, filesystem size |
| `mpconfigboard.h` | the compile-time settings: name, no `_thread`, the flash clock limit, the default peripheral pins, the start-up hook |
| `board_init.c` | `tspico_v3_safe_init()`, the safe pin and expander state; the PSRAM reserve |
| `tspico_v3_pins.h` | the pin map and the expander's registers, shared with `tsbus` |
| `tspico_v3.h` | the pico-sdk board header |
| `memmap/section_extra_post_platform_end.incl` | ends the GC heap at `0x20040000` |
| `memmap/pico_psram_region.ld` | the linker's PSRAM region, 8 MB |
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
| `MICROPY_HW_ENABLE_PSRAM`, `MICROPY_HW_PSRAM_CS_PIN` | 1, 47 | U22, the APS6404L (8 MB QSPI PSRAM), on QMI chip select 1 at GP47. The port's `CMakeLists.txt` turns them into compile definitions, links `hardware_psram` and, as no board header sets `PICO_PSRAM_SIZE_BYTES`, adds `PICO_PSRAM_CS_PIN=47` and `PICO_AUTO_DETECT_PSRAM_SIZE=1`. The SDK's `runtime_init_setup_psram` then gives GP47 to `XIP_CS1`, reads the chip's ID for its size and sets QMI window 1 up for quad reads (EBh) and writes (38h) with writes enabled. `main()` sets the QMI timing again for the 150 MHz boot clock and adds the PSRAM above `__psram_end__` to the GC heap as a second area (`MICROPY_GC_SPLIT_HEAP`, on with PSRAM); see `tspico_v3_psram_reserve` for why that is 1 MB. On a card without the chip nothing is found and the heap is SRAM only. Fitted 2026-11-08; `src/test/psram_test.py` checks it |
| `MICROPY_FROZEN_MANIFEST` | `manifest.py` here | see below |
| `MICROPY_SOURCE_BOARD` | `board_init.c` | adds the safe-init function to the build |
| `PICO_FLASH_SPI_CLKDIV` (compile definition) | 3 | the flash divider boot2 sets. After every flash erase or program the SDK re-enables XIP through boot2, and MicroPython only restores its own divider afterwards, in code that runs from flash. At `tsbus`'s 250 MHz, `tspico_v3.h`'s 2 ran the flash at 125 MHz there, and core 0 hung on the first LittleFS write (found 2026-10-09). 3 gives 50 MHz at boot and 83 MHz at 250 MHz. A compile definition so `tspico_v3.h` stays the bring-up's |
| `USER_C_MODULES` | `src/tsbus/micropython.cmake` | builds `tsbus` in; CI needs no extra argument |
| `tspico_v3_linker_override()`, deferred | puts `memmap/` first in the firmware's linker-script override paths | MicroPython adds its own override directories (`memmap_rp2350`, `memmap_rp2`) to the target after this file is read, and the first directory holding a file wins. `cmake_language(DEFER CALL …)` runs once the port's `CMakeLists.txt` is done and prepends this board's directory |
| `MICROPY_HW_FLASH_STORAGE_BYTES` | 14680064 (14 MB) | everything above the first 2 MB is the LittleFS filesystem, room for the slot images of phase 5. The firmware is about 316 KB of its 2 MB. Overridable from the command line |

## `mpconfigboard.h`

### `MICROPY_HW_BOARD_NAME`

`"TS-Pico v3"`: what `sys.implementation._machine` and the REPL banner say
("TS-Pico v3 with RP2350").

### `MICROPY_HW_ENABLE_PSRAM`

Not set here: `mpconfigboard.cmake` sets it (1) and the port passes it as a
`-D` flag, which a definition here would clash with. The comment says so. The
2068's images stay in SRAM: the PSRAM shares the QSPI bus with the flash and
sits behind the XIP cache, so its delay is not steady enough for a Z80 memory
cycle (`docs/v3-slots-proposal.md`).

### `MICROPY_PY_THREAD`

0. `_thread` would run Python on core 1, which belongs to `tsbus`.

### `MICROPY_HW_FLASH_MAX_FREQ`

84 MHz. MicroPython picks the smallest flash divider that keeps the flash at
or under this: 2 at the boot clock (150 MHz, 75 MHz) and 3 at `tsbus`'s 250
MHz (83 MHz), the divider phase 1 ran with. The port's default,
150 MHz ÷ `PICO_FLASH_SPI_CLKDIV`, would give 50 MHz and divider 5 at 250 MHz.

Why the board boots at 150 MHz and not 250: the SDK sets the boot clock
before MicroPython sets the flash divider, so booting at 250 MHz would run
the flash at 125 MHz first. A build that did so never came up on USB
(2026-10-09). `tsbus.start()` raises the clock ([tsbus.md](tsbus.md)).

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

### `tspico_v3_psram_reserve`, `TSPICO_V3_PSRAM_RESERVE`

What: a 7 MB array (`TSPICO_V3_PSRAM_RESERVE`), 4 KB aligned, in the linker
section `.psram_uninitialised.tspico_v3_reserve`. It is the only thing in the
PSRAM's sections, so it sits at the bottom of the chip, `0x11000000` to
`0x11700000`, and `__psram_end__` is its end. Only with
`MICROPY_HW_ENABLE_PSRAM`.

Why: MicroPython's `main()` gives the GC heap the PSRAM from `__psram_end__`
to the top of the chip, so this block decides the heap's share: the top 1 MB
(`gc.mem_free()` about 1.2 MB with SRAM's part). 1 MB is room for the 64 KB slot
buffers and the 2068's big operations; all 8 MB would make every
`gc.collect()` mark and sweep 8 MB at PSRAM speed. The 7 MB is kept for the
board's own use, the RAM slots or a slot-image cache of
`docs/v3-slots-proposal.md`. Nothing uses it yet.

State: none at boot. The section is NOLOAD, so the startup code neither
copies nor clears it, and it holds whatever the chip powered up with.
`tspico_v3_safe_init()` names it in an empty `asm` so the linker's
`--gc-sections` keeps it (the linker script lists the section without
`KEEP`); without that the heap would get all 8 MB.

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
7. PSRAM CS (GP47): left alone with PSRAM on. The SDK's `runtime_init`
   has already given it to the QMI (`XIP_CS1`) and the heap may be in the
   PSRAM, so `gpio_init` would cut the chip off. Instead the empty `asm`
   that keeps `tspico_v3_psram_reserve`. On a build without PSRAM: input
   with the pull-up.
8. The SD socket's four lines (CS 37, SCK 38, MOSI 39, MISO 32): inputs, no
   pulls. Nothing drives the socket until the firmware has seen a card on
   the detect switch and powered the socket (`board_v3.sd_card_ready`); on
   proto1 R34 holds CS high and R35 holds MISO (on proto2 they are on the
   socket's switched rail, off until then). Then OLED CS: output, high; OLED DC: output, low.
9. The XL9555 expander, over I2C0 at 400 kHz (GP24/25, internal pulls off;
   R6/R7 pull up): output register `IOX_OUT0_SAFE` first, then port 1's
   polarity 0 and direction all inputs, then port 0's direction
   (`IOX_CFG0_SAFE`: bits 0-6 outputs, bit 7 an input). If a write is not
   acknowledged it stops there.

Why the expander: its port 0 drives the /BUSRQ and /NMI requests (through
the 74LVC06), the OLED reset, the ESP32's EN and IO9, the LED and, on
proto2, the SD socket's power switch (bit 6, `SD_PWR_EN`; R43 holds it off
while the bit is an input), and it powers up as inputs with the output
register at FFh. The socket is left off here: `board_v3.sd_power` turns it
on for a mount, after the SD lines above are inputs (#262). Until 2026-11-08
bit 6 stayed an input (direction C0h), so a proto2 socket never had power. Writing the outputs
before the direction brings them up safe, as `iox_init()` does in the
bring-up. On proto1 the request lines are also pulled low on the board: with
the expander unconfigured they read low (port 0 read E0h). The LED stays off
(`X_NLED` high); the bring-up's dimmer is not ported.

Why the pins: GP8-GP10 have no external pull-ups and the RP2350 resets its pads with
pull-downs on, so until firmware runs all three buffers are enabled and U3
can drive the Z80's data bus. MD has no pulls because it is only sampled
while a buffer drives it, and RP2350 erratum E9 can latch a pad with its
input and pull-down both on at about 2 V. The same state as the bring-up's
`board_safe_init()` (`firmware/bringup/board.c` in tspico-hardware).

State: GPIO, I2C0 (left initialized; `machine.I2C(0)` sets it up again) and
the expander. The pads keep their reset pull-downs on the outputs, as in
the bring-up firmware. MicroPython's soft reset (`machine_pin_deinit`) only
turns off pin interrupts, so the state holds across Ctrl-D. RESET_HOLD is
never driven here: releasing the 2068 is `tsbus`'s job.

Checked on proto1 board 1 (2026-10-09, REPL): GP8-GP10 out and high, /BE and
/WAIT requests out and low, RESET_HOLD an input reading 1, SD CS high, PSRAM
CS pulled up (before PSRAM was on); expander output register E0h, port 0 direction C0h. Until
2026-10-10 SD CS was driven high here. Now all four SD lines are inputs: read
back on the card with the socket empty, GP32, 37, 38 and 39 `mode=IN`.

Why the SD lines are not driven: two cards died that day the moment they
went into the socket, each resetting the RP2350B. A line driven into a card
before its VDD contact makes can power it through its I/O pins.
tspico-hardware [#21](https://github.com/factus10/tspico-hardware/issues/21)
has the hardware side.

## `tspico_v3_pins.h`

The card's pin map, from the bring-up's `board.h`, shared by `board_init.c`
and `tsbus`:

| Name | GPIO | What |
|---|---|---|
| `PIN_MD0` | 0 | MD0-MD7 on GP0-GP7 |
| `PIN_NAEN_LO`, `PIN_NAEN_HI`, `PIN_NDATA_OE` | 8, 9, 10 | the /OE of U1 (A7..A0 onto MD), U2 (A15..A8) and U3 (MD onto the Z80's data bus) |
| `PIN_BE_REQ`, `PIN_WAIT_REQ` | 11, 12 | /BE and /WAIT through the 74LVC06 |
| `PIN_Z80_A14` | 13 | first of the inputs from U4/U6 (GP13-GP22) |
| `PIN_NMEMRD`, `PIN_NMEMWR`, `PIN_NIORD`, `PIN_NIOWR` | 15, 16, 17, 18 | /MREQ, /IORQ ORed with /RD or /WR: the strobes the PIO programs and core 1 wait on. `PIN_NMEMWR` was added for `tsbus`'s power check (all three write/I/O strobes low together: the 2068 is off) |
| `PIN_TAPE_IN`, `PIN_TAPE_OUT` | 22, 23 | tape |
| `PIN_I2C_SDA`, `PIN_I2C_SCL` | 24, 25 | I2C0: the expander |
| `PIN_RESET_HOLD` | 29 | high (or floating: R1) holds the 2068 in reset |
| `PIN_SD_MISO` | 32 | SPI0 MISO; R35 pulls it up |
| `PIN_OLED_DC`, `PIN_NIOX_INT` | 34, 35 | |
| `PIN_SD_CS`, `PIN_SD_SCK`, `PIN_SD_MOSI` | 37, 38, 39 | the SD socket's chip select (R34 pulls it up), clock and data out |
| `PIN_OLED_CS`, `PIN_PSRAM_CS` | 41, 47 | |

And the XL9555's registers and port 0 bits: `IOX_ADDR` (20h), `IOX_OUT0`,
`IOX_POL1`, `IOX_CFG0`, `IOX_CFG1`; `X_BUSRQ`, `X_NMI_REQ`, `X_NOLED_RST`,
`X_WIFI_EN`, `X_WIFI_DL`, `X_NLED` (bits 0-5), `X_SD_PWR_EN` (bit 6: proto2's
SD socket power, high = on; unconnected on proto1); `IOX_OUT0_SAFE` (`X_NLED`
and the spare bit 7 high, the rest low: no bus request, no NMI, the OLED in
reset, the ESP32 off and booting normally, the LED off, the SD socket off);
`IOX_CFG0_SAFE` (80h: bits 0-6 outputs, bit 7 an input).

## `tspico_v3.h`

The pico-sdk board header: `TSPICO_V3`, `PICO_RP2350A 0` (48 GPIOs), 16 MB
flash, the crystal start-up multiplier 64, A2 silicon supported. A copy of
`firmware/bringup/boards/tspico_v3.h` in tspico-hardware, which phase 1's
bus test was built with; only the opening comment differs, and the two
should stay the same. `PICO_BOOT_STAGE2_CHOOSE_W25Q080` selects the boot2
the build embeds (`picotool info` shows `boot2_name: boot2_w25q080`): the
SDK runs it to re-enable XIP after each flash erase or program. Its
`PICO_FLASH_SPI_CLKDIV` of 2 is overridden to 3 from
`mpconfigboard.cmake` (above).

## `memmap/section_extra_post_platform_end.incl`

MicroPython's RP2350 file of that name, with two changes, found first in the
linker search path (`tspico_v3_linker_override()`, above):

- `__GcHeapEnd` is `0x20040000`, `TSBUS_IMAGE_REGION`, instead of the top
  of RAM less 4 KB. The top 256 KB of SRAM is `tsbus`'s images. That leaves
  the GC heap about 196 KB (`gc.mem_free()` 191 KB at the REPL; 470 KB
  before `tsbus`). That is the heap's SRAM area; with the PSRAM the heap
  has a second, 1 MB area there (`tspico_v3_psram_reserve`, above).
- `__StackBottom` is the start of scratch Y, so the C stack is scratch Y's
  8 KB. MicroPython's RP2350 layout adds 4 KB at the top of main RAM below
  scratch Y, which would fall inside the image region.

It asserts that `.bss` ends below the image region and that the heap is over
64 KB. `tsbus.start()` checks `__GcHeapEnd` again at run time.

## `memmap/pico_psram_region.ld`

The linker's `PSRAM` memory region: `ORIGIN = 0x11000000, LENGTH = 8M`. The
SDK generates a file of this name with `LENGTH = PICO_PSRAM_SIZE_BYTES`,
which this build leaves unset (the size is auto-detected at boot), so its
region is 0 bytes and the link fails once anything is placed in it: "PSRAM:
7 MB of 0 GB", `ld returned 1` in CI on 2026-11-08, with
`tspico_v3_psram_reserve` in it. This board's `memmap/` is ahead of the
SDK's directory in the linker search path (`tspico_v3_linker_override()`),
so this copy is the one used. It only sizes the region for the linker: the C
code still sees no `PICO_PSRAM_SIZE_BYTES`, and the chip's size comes from
its ID at boot.

## `manifest.py`

Freezes `_boot.py` (mounts or creates the LittleFS filesystem) and `rp2.py`
(`asm_pio`, `StateMachine`, `PIO`) from the port's `modules/`, and the `TS`
package straight from the repo's `src/` (`$(BOARD_DIR)/../..`): the same
modules as `src/manifest.py`, with `board_v3.py` in place of `board_v2.py`
(`board.py` picks `board_v3` on this build, [board.md](board.md#board_v3py)),
plus `speech.py` and `speech_rules.py`, the speech the v2 build has no use
for ([speech.md](speech.md)), and `net.py`, `tpi:net`'s indexes for the
WiFi downloads ([net.md](net.md)).
Freezing from `src/` needs no staging step; `TS/buildinfo.py` is generated
there first (`tools/gen-buildinfo.py`, CI's "Generate the build stamp"
step), as for the v2 build. A new file under `src/TS/` needs a line here
too.

Why not `$(PORT_DIR)/boards/manifest.py`, the port's default: CI's v2 job
replaces that file with `src/manifest.py` (the TS modules), and the stock
one adds `asyncio`, `onewire`, `ds18x20`, `dht` and `neopixel`, which this
board has no use for.

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
