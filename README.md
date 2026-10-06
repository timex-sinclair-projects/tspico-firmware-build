# TS-Pico Firmware Build

GitHub Actions builds a MicroPython UF2 for the TS-Pico (Raspberry Pi
Pico-based storage interface for the Timex Sinclair TS-2068) with the
TS-Pico Python modules **frozen** into the firmware.

> **Using a TS-Pico?** [`docs/manual/user-manual.md`](docs/manual/user-manual.md)
> covers every command, with examples, and how to upgrade.
> [`docs/manual/programmers-manual.md`](docs/manual/programmers-manual.md) shows
> how to reach the TS-Pico from Z80 machine code and how to add commands to the
> Pico; its examples are in [`docs/manual/examples/`](docs/manual/examples/).
>
> **New to the code?** In reading order:
>
> 1. [`docs/PROTOCOL_GUIDE.md`](docs/PROTOCOL_GUIDE.md) — how the 2068 and
>    the Pico talk, in plain language.
> 2. [`docs/PROTOCOL.md`](docs/PROTOCOL.md) — the byte-level reference,
>    with the list of pitfalls. Read this when you're ready to write or
>    modify code.
> 3. [`docs/GUSTAVO_PROTOCOL.md`](docs/GUSTAVO_PROTOCOL.md) — the original
>    design, as history: what Gustavo built and why the ROM was modified.
> 4. [`docs/DUAL_PORT_DEVELOPMENT.md`](docs/DUAL_PORT_DEVELOPMENT.md) —
>    development narrative: how the dual-port architecture was developed
>    and tested, the wrong turns, and the patterns that proved out.
>
> **Want to contribute?** Start here:
>
> - [`docs/GETTING_STARTED.md`](docs/GETTING_STARTED.md) — the
>   entry-point orientation for new contributors. Tools, repo
>   layout, the workflow, paths for hand-coders vs Claude-Code
>   users, and multi-session coordination if you're running more
>   than one workspace.
> - [`docs/DEVELOPER_GUIDE.md`](docs/DEVELOPER_GUIDE.md) — the
>   comprehensive hand-coder reference (referenced from
>   GETTING_STARTED): the `.mpy` build flow, the dev-override
>   pattern, the `/TS/` shadowing trap, debugging recipes.

> Changing the platform? [`docs/reference/`](docs/reference/README.md) is the
> programmer's reference: the firmware and the ROM explained down to every
> function, variable, PIO instruction and ROM routine, one chapter per source
> file. CI keeps it in step with the code.

Freezing the modules eliminates the `MemoryError: memory allocation
failed, allocating XXXX bytes` that occurs when MicroPython tries to
import the modules from the flash filesystem at runtime — frozen
modules live in flash as pre-compiled bytecode and don't consume RAM
during import.

## Repo layout

Two payloads live in the repo, separated by what they deploy to:

- **`src/`** — everything that ends up on the Pico (firmware sources,
  the Pico-flash filesystem contents, and the Z80 EXROM image).
- **`SD card/`** — everything that ends up on the SD card the user
  plugs into the TS-Pico (the `tpi:help` text and the test/protocol
  `.tap` library).

```
.
├── README.md
├── docs/                  # protocol, architecture, dev guides
├── archive/               # historical reference material
├── SD card/               # goes on the user's SD card
│   ├── TAP/               #   /TAP/ — test + protocol TAPs (incl. test/, pico/ subdirs)
│   └── help/              #   /help/ — tpi:help <topic> text
└── src/                   # goes on the Pico (or the EXROM chip)
    ├── CLAUDE.md          # contributor conventions (Claude Code)
    ├── main.py            # Pico boot entry → flash root
    ├── config.ini         # runtime config → flash root
    ├── words.txt          # word list for tpi:.rndw → flash root
    ├── manifest.py        # MicroPython frozen-module manifest
    ├── build-dev-mpy.sh   # dev_tspico.py → dev_tspico.mpy
    ├── dev_tspico.py      # dev-override of TS.tspico
    ├── dev_extcmd.py      # dev-override of TS.extcmd
    ├── TS/                # frozen package (tspico, tspico_io, sdcard, extcmd, help)
    ├── assets/            # internal protocol .tap files → /assets/ on Pico
    ├── rom/               # Z80-side EXROM image (programmed into TS-2068 chip)
    └── test/              # bus-level harnesses (developer-only)
```

The CI workflows (`.github/workflows/{build,release}.yml`) reference
files under `src/` and `SD card/` directly, so no symlinks or path
tricks are needed.

## Deploy

The system has three deploy targets — the Pico's internal flash, the
TS-2068 EXROM chip, and the SD card you plug into the TS-Pico:

| Target | Source in repo | Lands at |
|---|---|---|
| Pico flash | `src/main.py`        | `/main.py` |
| Pico flash | `src/config.ini`     | `/config.ini` |
| Pico flash | `src/words.txt`      | `/words.txt` |
| Pico flash | `src/assets/*.tap`   | `/assets/*.tap` |
| TS-2068 EXROM | `src/rom/*.ROM`   | flashed into the expansion-board ROM chip |
| SD card | `SD card/TAP/`         | `/TAP/` on the SD card |
| SD card | `SD card/help/`        | `/help/` on the SD card |

### Step-by-step

1. **Flash the firmware:** hold BOOTSEL → plug in USB → drag
   `firmware.uf2` (from the latest GitHub Release, or the per-branch
   Actions artifact) onto the `RPI-RP2` drive.

   **Going back to an older MicroPython erases the Pico's files.** Builds
   from `main` run MicroPython v1.29; the v2.1 release and everything before
   it run v1.20. v1.29 writes the Pico's filesystem in a format v1.20 can't
   read, so a v1.20 UF2 dragged over a v1.29 board formats the flash on its
   first boot: `main.py`, `config.ini`, `words.txt`, `assets/` and the log
   are gone, and the Pico sits at the REPL until they're copied back. Copy
   off anything you want first. (The web updater warns before doing this.)

2. **Connect via Thonny.** You should be at a bare REPL.

3. **Quick verify** at the REPL:
   ```python
   import rp2
   import TS.tspico
   ```
   Both should succeed silently.

4. **Copy `src/main.py`, `src/config.ini`, and `src/words.txt`** to
   the Pico's root via Thonny.

5. **Create `/assets/` folder** on the Pico, then copy the three .tap
   files from `src/assets/` into it (`tools/build-basic.sh` builds them):
   - `dckupdate.tap`
   - `nofile.tap`
   - `romupdate.tap`

6. **Program the EXROM image** (`src/rom/*.ROM`) into the TS-2068
   expansion-board ROM chip with your usual ROM programmer. Raw
   binary; load at offset 0.

7. **Copy the contents of `SD card/`** to the root of the SD card you
   intend to use with the TS-Pico — both the `TAP/` and `help/`
   subfolders. The `tpi:help <topic>` command reads `/help/<topic>.txt`
   from the SD card.

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
  `TS/printer.py`, `TS/catalog.py`, `TS/native.py`, `TS/channels.py`
  (TS-Pico modules)

The default rp2 manifest also freezes `uasyncio`, `onewire`, `ds18x20`,
`dht`, and `neopixel` — drivers for peripherals the TS-Pico doesn't have.
We strip those to save ~6KB of flash and ~20KB of RAM.

`main.py` is intentionally **not** frozen so the user can interrupt
boot via Ctrl-C in Thonny or by deleting/renaming `/main.py`.

## Build details

- **MicroPython:** v1.29.0 (v1.20.0 until 2026-10; RP2350 support needs v1.24+)
- **Target:** Raspberry Pi Pico (`RPI_PICO` board on rp2 port)
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

## License

**Code: [MIT](LICENSE).** The firmware (`src/`), the tools (`tools/`), the web
updater (`web-updater/`), the BASIC programs (`basic/`), the CI workflows, the
site's code and templates, and the TS-Pico team's own ROM patches and module
(`src/rom/patches/`, `src/rom/fdd/`, `tools/build-rom.py`).

**Documentation: [CC BY 4.0](LICENSE-docs.txt).** The documents in `docs/`, the
help files in `SD card/help/`, the site's text, and the README and other
Markdown files. You may share and adapt them, with credit to the TS-Pico team.

**Not covered by either licence**, and remaining the property of their owners:

- **ROM images** (`src/rom/*.ROM`, `src/rom/*.BIN`, `ROMs/`). The TS-Pico ROMs
  are the Timex Computer Corporation TS-2068 ROM with the team's changes, and
  the ZX Spectrum ROMs are Sinclair Research (now Amstrad) code with the
  team's changes. Only the changes are ours; the MIT licence covers the
  sources that make them, not the images.
- **Disassemblies of Timex's ROM** (`docs/rom-analysis/disasm/genuine-2068-*`).
- **`docs/ZEBRA_FDD_TOS_MANUAL.md`**, a transcription of the Zebra Systems FDD
  manual.
- **Gustavo Pane's specification documents** (`docs/LOW-LEVEL-PROTOCOL-V5.TXT`,
  `docs/TS-PICO_FILE_SYSTEM-SPECS-BETA-PRE-RELEASE-V25.pdf`), © Gustavo Pane.
- **Photographs and illustrations** in `site/assets/img/`, © their creators.
- **Third-party code, under its own licence:** `web-updater/vendor/`
  (ViperIDE, MIT, © Volodymyr Shymanskyy; Pico⚡Flash, MIT, © Piers
  Finlayson), `tools/zmakebas/` (public domain, Russell Marks) and
  `web-updater/flash_nuke.uf2` (Raspberry Pi, BSD-3-Clause).

**The TS-Pico team:** Ricardo Calcagno, Gustavo Pane, Jeff Burrell, Ryan Gray,
Tim H and David Anderson. The board design is in
[jburrell7/TSPICO](https://github.com/jburrell7/TSPICO).

Thanks to Paul Anderson, David Green and Adam Trionfo for beta testing.
