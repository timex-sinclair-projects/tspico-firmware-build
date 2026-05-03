# TS-Pico Firmware Build

GitHub Actions builds a MicroPython UF2 for the TS-Pico (Raspberry Pi
Pico-based storage interface for the Timex Sinclair TS-2068) with the
TS-Pico Python modules **frozen** into the firmware.

Freezing the modules eliminates the `MemoryError: memory allocation
failed, allocating XXXX bytes` that occurs when MicroPython tries to
import the modules from the flash filesystem at runtime — frozen
modules live in flash as pre-compiled bytecode and don't consume RAM
during import.

## Deploy to the Pico

After flashing the UF2, you need three things on the Pico's flash
filesystem (use Thonny):

| Pico path | What it is | Source |
|---|---|---|
| `/main.py` | Boot entry point | `main.py` in this repo |
| `/assets/*.tap` | Internal protocol .TAP files | `assets/` in this repo |
| `/SD/...` | (existing) — your SD card | unchanged |

### Step-by-step

1. **Flash the firmware:** hold BOOTSEL → plug in USB → drag
   `firmware.uf2` (download from Actions artifacts) onto the
   `RPI-RP2` drive.

2. **Connect via Thonny.** You should be at a bare REPL.

3. **Quick verify** at the REPL:
   ```python
   import rp2
   import TS.tspico
   ```
   Both should succeed silently.

4. **Copy `main.py` to `/main.py`** on the Pico via Thonny.

5. **Create `/assets/` folder** on the Pico, then copy the four .tap
   files from `assets/` into it:
   - `dckupdate.tap`
   - `nofile.tap`
   - `rompatch.tap`
   - `romupdate.tap`

6. **Reboot.** You should see:
   ```
   270000000
   INFO: SD Card initialized and mounted OK
   ```

## Why `/assets/` instead of `/TS/`?

The Python modules (`tspico.py`, `tspico_io.py`, etc.) are now baked
into the firmware as the **frozen `TS` package**. If a `/TS/` folder
also exists on the Pico's flash, MicroPython prefers it for the `TS`
package and never sees the frozen submodules — `import TS.tspico`
fails because the flash folder doesn't have those Python files (only
the .tap data files).

Putting the .tap files in a different folder (`/assets/`) sidesteps
the conflict cleanly. The Python code references them by absolute
path, so the rename has no other implications.

## Iterating on Python without rebuilding the UF2

MicroPython checks the flash filesystem first and falls back to frozen
modules. So you can override any frozen file by putting your edited
version on flash at the same path:

- Override `TS.tspico` → put your edited `tspico.py` at `/TS/tspico.py`
  on flash. **But** then you lose access to ALL frozen TS submodules
  (see above) — so you'd need to put the entire TS package on flash.

A more practical pattern: only override one file at a time by placing
it directly on the flash filesystem, but understand that overriding
**any** file inside the `TS` package shadows the entire frozen
package. For single-module debugging it's often easier to flash the
new UF2 from CI.

## What's frozen

All files under `src/TS/` plus the rp2 port's own essentials:

- `_boot.py`, `_boot_fat.py`, `rp2.py` (rp2 port stdlib)
- `uasyncio`, `onewire`, `ds18x20`, `dht`, `neopixel` (default deps)
- `TS/__init__.py` (package marker)
- `TS/tspico.py`, `TS/tspico_io.py`, `TS/sdcard.py`, `TS/extcmd.py`,
  `TS/help.py` (TS-Pico modules)

`main.py` is intentionally **not** frozen so the user can interrupt
boot via Ctrl-C in Thonny or by deleting/renaming `/main.py`.

## Build details

- **MicroPython:** v1.20.0
- **Target:** Raspberry Pi Pico (`PICO` board on rp2 port)
- **Toolchain:** `gcc-arm-none-eabi` on Ubuntu 22.04 runner
- **Build time:** ~2 minutes per run
- **Custom manifest:** `manifest.py` in repo root (overrides default
  rp2 manifest to add the `TS/` package while keeping `rp2.py` etc.)

## Iteration workflow

1. Edit `src/TS/...` files
2. Commit, push to `main`
3. GitHub Actions rebuilds the UF2
4. Download from the run's artifacts
5. Flash to Pico (BOOTSEL + drag-and-drop)
6. The `/main.py` and `/assets/*.tap` already on the Pico are
   preserved — only the firmware itself is replaced.
