# TS-Pico Firmware Build

GitHub Actions builds a MicroPython UF2 for the TS-Pico (Raspberry Pi
Pico-based storage interface for the Timex Sinclair TS-2068) with the
TS-Pico Python modules **frozen** into the firmware.

> **New here?** Three documents, in reading order:
>
> 1. [`docs/GUSTAVO_PROTOCOL.md`](docs/GUSTAVO_PROTOCOL.md) — the
>    high-level design view. What is the TPI protocol? Why are there
>    two ROMs? What does Gustavo's modified Z80 ROM actually do?
>    Read this first if you've never worked on the project before.
> 2. [`docs/PROTOCOL.md`](docs/PROTOCOL.md) — the firmware-implementation
>    view. What does the Pico do, instruction by instruction, to honor
>    the protocol? Read this when you're ready to write or modify code.
> 3. [`docs/DUAL_PORT_DEVELOPMENT.md`](docs/DUAL_PORT_DEVELOPMENT.md) —
>    development narrative. Walks through how the dual-port
>    architecture was developed and tested, the test harnesses in
>    `/test`, wrong turns we took, three latent bugs we found and
>    fixed, and patterns that proved out. Read this if you're going
>    to extend or modify the protocol code — it explains *why* the
>    patterns are the way they are.

Freezing the modules eliminates the `MemoryError: memory allocation
failed, allocating XXXX bytes` that occurs when MicroPython tries to
import the modules from the flash filesystem at runtime — frozen
modules live in flash as pre-compiled bytecode and don't consume RAM
during import.

## Repo layout

All firmware sources live under `src/`. The repo root only carries
this README and the GitHub-managed folders:

```
.
├── README.md
├── docs/                  # protocol, architecture, dev guides
├── archive/               # historical reference material
└── src/
    ├── CLAUDE.md          # contributor conventions (Claude Code)
    ├── main.py            # Pico boot entry
    ├── config.ini         # runtime config
    ├── words.txt          # word list for tpi:.rndw
    ├── manifest.py        # MicroPython frozen-module manifest
    ├── build-dev-mpy.sh   # dev_tspico.py → dev_tspico.mpy
    ├── dev_tspico.py      # dev-override of TS.tspico
    ├── dev_extcmd.py      # dev-override of TS.extcmd
    ├── TS/                # frozen package (tspico, tspico_io, sdcard, extcmd, help)
    ├── assets/            # internal protocol .tap files
    ├── help/              # tpi:help <topic> text
    ├── rom/               # Z80-side EXROM image
    ├── pico/              # test artifacts (.dck / .rom)
    ├── test/              # bus-level harnesses
    └── test-progs/        # BASIC test programs
```

The CI workflows (`.github/workflows/{build,release}.yml`) reference
files under `src/` directly, so no symlinks or path tricks are
needed.

## Deploy to the Pico

After flashing the UF2, you need these things on the Pico's flash
filesystem (use Thonny):

| Pico path | What it is | Source |
|---|---|---|
| `/main.py` | Boot entry point | `src/main.py` in this repo |
| `/config.ini` | TS-Pico runtime config (log level, ROM/DCK slots, etc.) | `src/config.ini` in this repo |
| `/assets/*.tap` | Internal protocol .TAP files | `src/assets/` in this repo |
| `/help/*.txt` | Help text shown by `tpi:help <topic>` | `src/help/` in this repo |
| `/words.txt` | Word list read by `tpi:.rndw` external command | `src/words.txt` in this repo |
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
   files from `src/assets/` into it:
   - `dckupdate.tap`
   - `nofile.tap`
   - `rompatch.tap`
   - `romupdate.tap`

6. **Create `/help/` folder** on the Pico, then copy all `.txt` files
   from this repo's `src/help/` directory into it. The `tpi:help <topic>`
   command reads these from `/help/<topic>.txt`.

7. **Copy `src/words.txt`** to the Pico's root (`/words.txt`). Required by
   the `tpi:.rndw` external-command example. If you don't plan to use
   `.rndw` you can skip this — but other extcmd handlers may also use
   it in the future.

8. **Reboot.** You should see:
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

**`dev_extcmd.py` works the same way** for the `TS.extcmd` module:
copy a modified `extcmd.py` to the Pico as `/dev_extcmd.py` and the
dev override picks it up. Useful for iterating on user-extensible
`TPI:.XXX` command handlers without rebuilding the UF2. See the
header comment in `dev_extcmd.py` for details.

## What's frozen

All files under `TS/` plus only the rp2-port stdlib bits we actually use:

- `_boot.py` — runs at startup, mounts LittleFS
- `_boot_fat.py` — FAT support (used by SD card driver)
- `rp2.py` — wraps the C `_rp2` module; provides `asm_pio`, `StateMachine`, etc.
- `TS/__init__.py` (package marker)
- `TS/tspico.py`, `TS/tspico_io.py`, `TS/sdcard.py`, `TS/extcmd.py`,
  `TS/help.py` (TS-Pico modules)

The default rp2 manifest also freezes `uasyncio`, `onewire`, `ds18x20`,
`dht`, and `neopixel` — drivers for peripherals the TS-Pico doesn't have.
We strip those to save ~6KB of flash and ~20KB of RAM.

`main.py` is intentionally **not** frozen so the user can interrupt
boot via Ctrl-C in Thonny or by deleting/renaming `/main.py`.

## Build details

- **MicroPython:** v1.20.0
- **Target:** Raspberry Pi Pico (`PICO` board on rp2 port)
- **Toolchain:** `gcc-arm-none-eabi` on Ubuntu 22.04 runner
- **Build time:** ~2 minutes per run
- **Custom manifest:** `src/manifest.py` (overrides default rp2
  manifest to add the `TS/` package while keeping `rp2.py` etc.)

## Iteration workflow

1. Edit `src/TS/...` files on a feature branch (`git checkout -b my-fix`).
2. Commit and push the branch.
3. Open a pull request against `main`.
4. GitHub Actions builds a UF2 **for the branch / PR** as well as for
   `main` — you can download the artifact from any PR's checks before
   it merges. (See `.github/workflows/build.yml`.)
5. Flash to Pico (BOOTSEL + drag-and-drop).
6. The `/main.py`, `/config.ini`, `/assets/*.tap`, `/help/*.txt`, and
   `/words.txt` already on the Pico are preserved — only the firmware
   itself is replaced.
7. When the change looks good, get a review and squash-merge the PR
   into `main`. CI builds one more UF2 from the merge commit.

**For quick `tspico.py` / `extcmd.py` tweaks** that don't need a UF2
rebuild, use the `/dev_tspico.py` / `/dev_extcmd.py` override pattern
described above — far faster iteration loop.
