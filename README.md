# TS-Pico Firmware Build

GitHub Actions builds a MicroPython UF2 for the TS-Pico (Raspberry Pi
Pico-based storage interface for the Timex Sinclair TS-2068) with the
TS-Pico Python modules **frozen** into the firmware.

> **New here?** Two documents to start with:
>
> - [`docs/GUSTAVO_PROTOCOL.md`](docs/GUSTAVO_PROTOCOL.md) — the
>   high-level design view. What is the TPI protocol? Why are there
>   two ROMs? What does Gustavo's modified Z80 ROM actually do? Read
>   this first if you've never worked on the project before.
> - [`docs/PROTOCOL.md`](docs/PROTOCOL.md) — the firmware-implementation
>   view. What does the Pico do, instruction by instruction, to honor
>   the protocol? Read this when you're ready to write or modify code.

Freezing the modules eliminates the `MemoryError: memory allocation
failed, allocating XXXX bytes` that occurs when MicroPython tries to
import the modules from the flash filesystem at runtime — frozen
modules live in flash as pre-compiled bytecode and don't consume RAM
during import.

## Deploy to the Pico

After flashing the UF2, you need these things on the Pico's flash
filesystem (use Thonny):

| Pico path | What it is | Source |
|---|---|---|
| `/main.py` | Boot entry point | `main.py` in this repo |
| `/config.ini` | TS-Pico runtime config (log level, ROM/DCK slots, etc.) | `config.ini` in this repo |
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

4. **Copy `main.py` and `config.ini` to the Pico's root** via Thonny.

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

## Iterating on `tspico.py` without rebuilding the UF2

MicroPython resolves a package once based on where it finds
`__init__.py`. If `/TS/` exists on the Pico's flash, MicroPython uses
*that* folder for the entire `TS` package and never falls back to
the frozen submodules. So you can't simply drop a new `/TS/tspico.py`
on flash — the other frozen TS modules (`tspico_io`, `sdcard`, etc.)
become unreachable.

`main.py` includes a **dev override** for `tspico.py` specifically:

```python
try:
    from dev_tspico import TS2068_IO
    print("[DEV] Using /dev_tspico.py override")
except ImportError:
    from TS.tspico import TS2068_IO
```

**To override `tspico.py` for a debug session:**

1. Edit `src/TS/tspico.py` locally
2. Copy the edited file to the Pico's flash as `/dev_tspico.py`
   (note the rename — root path, with `dev_` prefix)
3. Reboot — REPL prints `[DEV] Using /dev_tspico.py override`
4. Test on the TS-2068
5. To revert: delete `/dev_tspico.py` from flash and reboot — main.py
   falls back to the frozen `TS.tspico` automatically

The override file does not need to be inside a `/TS/` folder. It still
imports `from TS.tspico_io import ...` etc. which resolves to the
frozen modules (because nothing on flash shadows the `TS` package).

**For overriding other files** (`tspico_io.py`, etc.): the override
trick only works for `tspico.py`. For other files, push to GitHub and
let CI rebuild the UF2.

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
