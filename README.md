# TS-Pico Firmware Build

GitHub Actions builds a MicroPython UF2 for the TS-Pico (Raspberry Pi
Pico-based storage interface for the Timex Sinclair TS-2068) with the
TS-Pico Python modules **frozen** into the firmware.

Freezing the modules eliminates the `MemoryError: memory allocation
failed, allocating XXXX bytes` that occurs when MicroPython tries to
import the modules from the flash filesystem at runtime — frozen
modules live in flash as pre-compiled bytecode and don't consume RAM
during import.

## How to use

1. **Push to `main`** (or trigger manually via the Actions tab) → the
   workflow runs and produces `firmware.uf2` as a build artifact.

2. **Download the artifact** from the workflow run page (Actions →
   click the run → "tspico-firmware-uf2" at the bottom).

3. **Flash the Pico**:
   - Hold the BOOTSEL button while plugging in USB
   - The Pico mounts as a USB drive named `RPI-RP2`
   - Drag `firmware.uf2` onto the drive
   - The Pico reboots automatically with the new firmware

The frozen modules will load instantly without consuming RAM. No need
to copy `tspico.py` or `tspico_io.py` to the Pico's flash filesystem.

## What's frozen

All files under `src/` are baked into the firmware:

- `main.py` — boot entry point
- `TS/__init__.py` — package marker
- `TS/tspico.py` — main I/O loop and command dispatcher
- `TS/tspico_io.py` — PIO programs (includes `TS_IO_DUAL` for dual-port)
- `TS/sdcard.py` — SD card SPI driver
- `TS/extcmd.py` — extension command handlers
- `TS/help.py` — help text

## Iterating

Edit any file under `src/`, commit, push. The workflow rebuilds and
publishes a new UF2.

## Build details

- **MicroPython**: v1.20.0
- **Target**: Raspberry Pi Pico (RPI_PICO board)
- **Toolchain**: `gcc-arm-none-eabi` on Ubuntu 22.04 runner
- **Build time**: ~5 minutes per run

## Notes

- This build does NOT include Ricardo's custom `mpconfig.h`. If you
  have it, copy it to `src/mpconfig.h` and add a step in the workflow
  to copy it over `micropython/py/mpconfig.h` before building. Stock
  config should work fine for testing.

- If the build succeeds but the Pico won't boot, check the workflow
  logs — the build sometimes succeeds with warnings that indicate
  package import won't work at runtime.
