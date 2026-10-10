# Boot, configuration and the build

Source: [`src/main.py`](../../../src/main.py) (all of it),
[`src/config.ini`](../../../src/config.ini),
[`src/manifest.py`](../../../src/manifest.py),
[`tools/gen-buildinfo.py`](../../../tools/gen-buildinfo.py),
[`src/build-dev-mpy.sh`](../../../src/build-dev-mpy.sh),
[`.github/workflows/build.yml`](../../../.github/workflows/build.yml),
[`.github/workflows/release.yml`](../../../.github/workflows/release.yml),
[`flash/manifest.json`](../../../flash/manifest.json),
[`tools/build-flash.py`](../../../tools/build-flash.py).

How the firmware gets onto a Pico and starts: the one file that is not
frozen (`main.py`, which picks the firmware and has the board set its pins), the
configuration file it and `LOAD_CONFIG` read, how the UF2 is built and
stamped, how a developer runs a changed `tspico.py` without rebuilding,
what CI checks on every push and what a release publishes, and the 512K
flash image of ROMs the 2068 runs from. What happens once `TS2068_IO`
starts is [tspico-dispatch.md](tspico-dispatch.md) and
[the boot flow](../flows/boot.md); the separate upgrade UF2 is
[upgrade.md](upgrade.md); the pins themselves are
[hardware.md](../hardware.md).

## Map

| Piece | What it is |
|---|---|
| `src/main.py` | `/main.py` on the Pico's flash: telemetry switch, the dev override, the board's pins and clock, the fatal-error wrapper |
| `src/config.ini` | `/config.ini`: nine settings, JSON |
| `src/manifest.py` | the freeze manifest: which modules go into the UF2 |
| `tools/gen-buildinfo.py` | writes `src/TS/buildinfo.py`, the build stamp |
| `src/dev_tspico.py`, `src/dev_extcmd.py`, `src/build-dev-mpy.sh` | the dev overrides |
| `.github/workflows/build.yml` | every push: tests, ROM checks, the two v2 UF2s, the v3 UF2, the user manual PDFs, artifacts |
| `.github/workflows/release.yml` | a `v*` tag: the release assets |
| `flash/manifest.json`, `tools/build-flash.py` | the 512K flash image |
| `tools/pico-serial.py` | the USB console from a shell |

Symbols of `src/main.py`, in source order:

| Symbol | Line |
|---|---|
| `_telemetry()` | 27 |
| `log_msg` | 70 |

## `src/main.py`

MicroPython runs `/main.py` from the flash filesystem after `_boot.py`
has mounted it. It is deliberately **not** frozen into the UF2 (the
comment in `build.yml`'s staging step): a file on flash can be renamed or
deleted, or interrupted with Ctrl-C in Thonny, to stop the firmware
starting, which is how a developer gets a REPL on a board whose firmware
misbehaves. Everything else is frozen.

What it does, in order:

1. `import TS.tspico` — the whole frozen module is imported, which runs its
   top level: the constants and globals, the PIO programs' assembly, the
   build-stamp print ([tspico-state.md](tspico-state.md)). Nothing touches
   the bus yet.
2. `TS.tspico.TLM_ENABLED = _telemetry()`: the telemetry switch from
   `/config.ini`, set before any `TLM()` call so the first events of boot
   already follow it. Telemetry is the `TLM` event trace on the USB serial
   console ([DEVELOPER_GUIDE.md §8](../../DEVELOPER_GUIDE.md#8-the-tlm-telemetry-switch)).
   Before the 2026-09-30 audit (§4) `main.py` forced it on for every
   board; releases now ship it off.
3. **The dev override**: `from dev_tspico import TS2068_IO` — a
   `/dev_tspico.py` or `/dev_tspico.mpy` at the flash root, if there is
   one. If that works, `dev_tspico.TLM_ENABLED` is set to the same value
   (the flag was set on `TS.tspico`, which is not the module running; the
   comment records that this was missed once, in stage-9 testing, and the
   diagnostics silently vanished) and `[DEV] Using /dev_tspico override` is
   printed. `ImportError` (no file): `from TS.tspico import TS2068_IO`, the
   frozen firmware. `ValueError` — "incompatible .mpy file", a
   `/dev_tspico.mpy` compiled for another MicroPython (every MicroPython
   upgrade changes the bytecode version) — also falls back to the frozen
   module, with a message; before this a leftover override stopped
   `main.py` before the TS-Pico started.
4. `board.early_init()` (66–67, [board.md](board.md#early_init)): on v2
   the seven bus-control pins to their idle levels, then
   `machine.freq(270_000_000)`, the RP2040 at 270 MHz, which `main.py`
   prints. The PIO clock dividers are computed from it when `TS2068_IO`
   builds its state machines. (Until the board layer, step 4.1, the pins
   and the clock were set here; the pin table is now in
   [board.md](board.md#early_init).)
5. `print(freq())`.
6. `log_msg = ""`.
7. The run loop: `collect()`, then `TS2068_IO()`.

`TS2068_IO` does not return in normal operation; its own restart loop
recovers a dropped bus link up to three times a minute
([tspico-dispatch.md](tspico-dispatch.md#ts2068_io)). If it raises an
`Exception`, `main.py` appends `"[ticks_us] FATAL ERROR in TS2068_IO:"` and
the traceback to `/activity.log` (any failure to write is ignored), prints
the same to the console, and **breaks out of the loop**: `main.py` ends and
MicroPython drops to the REPL. The Pico is then quiescent — the LED stops,
the 2068 gets Report J on its next command — but the post-mortem is on
flash, readable with `tpi:log` after a restart or with Thonny. Before the
wrapper an exception (an `OSError` from starting core 1, say)
left nothing on flash at all. The `break` is there so the same exception
is not retried for ever. A `BaseException` that is not an `Exception`
(Ctrl-C from the host, a `CmdAbort` that escaped) is not caught: it ends
`main.py` at once with nothing logged.

### `_telemetry()`

`True` if `/config.ini` is JSON with `"TELEMETRY": true` (the JSON value
`true`, tested with `is True`, so `1` or `"yes"` do not count); `False` for
anything else, including a missing or broken file. Imports `json` inside
the function. Read once, at step 2. `LOAD_CONFIG` adds the key with
`False` when it is missing but never reads it.

### `log_msg`

`str`, `""`, then the header line of a fatal-error entry. Module-level only
because the `with` block assigns it; nothing reads it. Harmless.

## `config.ini`

`/config.ini` on the Pico's flash, JSON despite the extension — one
object, nine keys. The shipped file is
[`src/config.ini`](../../../src/config.ini); the web updater writes it to
the flash with the other Pico files (`web-updater/build-payload.sh`), as
the release bundle's instructions do — replacing whatever settings the
board had. It is read at boot by `_telemetry`
(above) and `LOAD_CONFIG` ([tspico-dispatch.md](tspico-dispatch.md#load_config)),
which fills in any missing key, refuses a bad `ROM_SM`, and writes the
file back when it changed anything; `PICO_STATUS` is built from what
`LOAD_CONFIG` returns ([tspico-state.md](tspico-state.md#pico_status__init__self-init_values)).

| Key | Type | Shipped | Meaning | Read by | Written by |
|---|---|---|---|---|---|
| LOG_LEVEL | int 0–4 | 2 | lowest level `LOG` keeps (0 INFO … 3 CRITICAL, 4 SPECIAL) | `LOAD_CONFIG` → `TSP.LOG_LEVEL` | `LOAD_CONFIG` (default) |
| FW_VERSION | str | `"2.3"` | the firmware's version, for tools: `PICO_STATUS` ignores it and takes the module's own `FW_VERSION` | the web updater, to tell what a board runs (`web-updater/app.js` `readInstalled`, ~314–346; 1.1's file has none) | `LOAD_CONFIG` (default); the release |
| DCK_SLOT | int 0–15 | 0 | DOCK slot at power-on | `LOAD_CONFIG` → `TSP.DCK_SLOT`, `bank_sm` | `LOAD_CONFIG` (default) |
| ZX_TAPE_COMPAT | bool | `false` | ZX48 mode loads with `LOAD_ZX_C` (the whole tape in RAM) | → `TSP.ZX_TAPE_COMPAT` | `LOAD_CONFIG` (default) |
| ROM_SM | int 5, 6, 9, 10 | 10 | `set_ctrl`'s word: DOCK memory × 4 + BOOT memory, 1 SRAM, 2 flash | → `TSP.ROM_SM` | `LOAD_CONFIG` (default; the one-shot), `MEMBOOT` (low bits) |
| ROM_VERSION | str | `"2.3"` | the release ROM, for the updaters (their `rom_version`); `tpi:info` shows it only for a ROM that doesn't send its version; nothing switches on it | → `TSP.ROM_VERSION` | `LOAD_CONFIG` (default) |
| ROM_SLOT | int 0–15 | 1 | BOOT slot at power-on | → `TSP.ROM_SLOT`, `bank_sm` | `LOAD_CONFIG` (the one-shot back to 1), `MEMBOOT` |
| VERBOSE | bool | `false` | `SEND_MSG` prints messages | → `TSP.VERBOSE` | `LOAD_CONFIG` (default) |
| TELEMETRY | bool | `false` | the `TLM` trace on USB serial | `_telemetry()` only | `LOAD_CONFIG` (default) |
| LED_BRIGHTNESS | int 1–100 | 5 | the v3 card's LED brightness, % (the v2 Pico's LED isn't dimmed) | `LOAD_CONFIG` → `board.led_brightness` in `TS2068_IO` | `LOAD_CONFIG` (default, or a bad value replaced) |

**The one-shot boot.** `tpi:boot CODE m,s` writes `ROM_SLOT = s` and
`ROM_SM`'s low bits `= m` ([tspico-commands.md](tspico-commands.md#membootpre-cmd)).
At the next power-on `LOAD_CONFIG` boots from that pair once and writes
flash slot 1 back to the file, so a ROM under test that hangs the 2068
is gone after one more power cycle. Hand-editing `ROM_SLOT` gives the same
one-shot. A permanent change of ROM means writing flash slot 1 itself
([flash/README.md](../../../flash/README.md#deploying)).

Nothing else writes the file at run time: `tpi:verbose`, `tpi:loglevel`,
`tpi:dock` and the printer settings last until power-off. The file is
opened by the relative name `"config.ini"` in `LOAD_CONFIG` and `MEMBOOT`,
which relies on the current directory being the flash root (it is at boot;
see `MEMBOOT`'s entry).

## The UF2: what is frozen, and the build stamp

[`src/manifest.py`](../../../src/manifest.py) replaces MicroPython
v1.29.0's `ports/rp2/boards/manifest.py`. The stock manifest freezes
`_boot.py`, `_boot_fat.py`, `rp2.py` and drivers for peripherals a stock
Pico might have (onewire, ds18x20, dht, neopixel, uasyncio); the TS-Pico
has none of those, and dropping them saves about 6 KB of flash and 20 KB
of RAM (the comment). It freezes:

- `_boot.py`, which mounts the LittleFS filesystem on the Pico's flash at
  start-up, and `rp2.py`, which provides `asm_pio` and `StateMachine`;
- the `TS` package: `__init__.py`, `tspico.py`, `buildinfo.py`,
  `tspico_io.py`, `sdcard.py`, `extcmd.py`, `printer.py`, `catalog.py`,
  `native.py`, `channels.py`, and the board layer, `board.py` and
  `board_v2.py` ([board.md](board.md)). `board_v3.py` is for the v3 card's
  build only, which freezes from `src/` with its own manifest
  ([board-v3.md](board-v3.md#manifestpy)).

`_boot_fat.py` was frozen once "for the SD card"; it is not SD support —
it mounts the Pico's own flash as FAT, formatting it if it is not, and
MicroPython runs it only in a build with USB mass storage, which this is
not (2026-09-30 audit, §3). **A new file under `src/TS/` needs a
`freeze()` line here and a `cp` line in both workflows' staging steps**,
or it is not in the UF2 and its import fails on the Pico (but not in the
host tests, which import from `src/`).

The upgrade UF2 has its own manifest, `src/upgrade/manifest.py`
([upgrade.md](upgrade.md)).

### `TS/buildinfo.py` and `tools/gen-buildinfo.py`

`gen-buildinfo.py` writes `src/TS/buildinfo.py`:

```python
COMMIT = "<git rev-parse --short HEAD>"
BRANCH = "<GITHUB_REF_NAME, or git rev-parse --abbrev-ref HEAD>"
DIRTY = True|False      # git status --porcelain -uno is non-empty
```

`tspico.py` imports it in a `try` and builds `BUILD_VERSION` =
`"<commit>[+dirty] (<branch>)"` from it, or `"unknown (no buildinfo)"`
when the module is missing (a hand build that skipped the step still
runs; [tspico-state.md](tspico-state.md#build_version)). It is printed at
import, logged by `LOAD_CONFIG`, and shown by `tpi:info`.

- In CI the checkout is a detached HEAD, so git says `HEAD` for the
  branch; the runner's `GITHUB_REF_NAME` is preferred, and a plain `HEAD`
  becomes `detached`.
- `-uno`: only tracked modifications make a build "+dirty". A plain
  `--porcelain` counted untracked files too, and CI clones MicroPython into
  the workspace, so every CI build said "+dirty" because of
  `?? micropython/`. Untracked files cannot reach the UF2 anyway.
- No timestamp, on purpose: two builds of the same commit make the same
  UF2, which matters in a repo that crc-checks its images. The build date
  is in MicroPython's own banner.
- A failing `git` gives `"unknown"`.

The file is generated and gitignored; the stamp replaced a hand-written
literal that had rotted.

## The dev overrides

A developer can run a changed `tspico.py` or `extcmd.py` without building
a UF2 ([DEVELOPER_GUIDE.md §5–6](../../DEVELOPER_GUIDE.md#6-the-dev-override-pattern)):

- **`/dev_tspico.py` or `/dev_tspico.mpy`** at the flash root replaces the
  frozen `TS.tspico`: `main.py` imports `TS2068_IO` from it (above).
  Inside it, `from TS.tspico_io import …` and the other `TS` imports still
  resolve to the frozen modules.
- **`/dev_extcmd.py`** replaces the frozen `TS.extcmd`: `TS2068_IO` tries
  `from dev_extcmd import EXT_SA_FUNCT` first (6294;
  [extcmd.md](extcmd.md)).
- To go back: delete the file and restart.

[`src/dev_tspico.py`](../../../src/dev_tspico.py) and
[`src/dev_extcmd.py`](../../../src/dev_extcmd.py) are kept **identical**
to `src/TS/tspico.py` and `src/TS/extcmd.py` (line endings aside):
[`dev_sync_hosttest.py`](../../../src/test/dev_sync_hosttest.py) fails CI
when they drift, and `build.yml`'s stamp step checks `tspico.py` again
with `cmp`. Before the check, `dev_tspico.py` was 1063 diff lines behind
and had none of the catalog, native or channel commands, so deploying it
silently took commands away. **Any change to `tspico.py` is copied to
`dev_tspico.py` in the same commit.**

**The `.mpy`.** MicroPython's parser needs a lot of RAM: once the file
grew past about 4 000–4 500 lines, parsing it at boot ran out of memory.
Bytecode compiled on the host skips the parser and is about 80 % smaller.
[`src/build-dev-mpy.sh`](../../../src/build-dev-mpy.sh) runs `mpy-cross`
(installed with `pip install mpy-cross==1.29.*`, matching the UF2's
MicroPython: bytecode v6.3) on `src/dev_tspico.py`, or a file given as its
argument, and writes the `.mpy` beside it. CI builds the same file with the
`mpy-cross` it built for the UF2 and uploads it as the `dev_tspico-mpy`
artifact. A `.mpy` built for another MicroPython is rejected at import
with `ValueError`, which `main.py` turns into "use the frozen module".

With both `/dev_tspico.py` and `/dev_tspico.mpy` on the flash, the `.py` is
loaded: MicroPython's importer looks for `name.py` before `name.mpy` in each
directory. Checked on a TS-Pico (MicroPython 1.29, #175): with only a
`probe.mpy` on flash, `import probe` loaded it; with a `probe.py` beside it, a
fresh import loaded the `.py`. So a stale `.py` shadows a fresh `.mpy`, and
DEVELOPER_GUIDE §5's rule is the one to follow: never have both. (Until #175
`main.py`'s and `build-dev-mpy.sh`'s comments said the `.mpy` was preferred.)

**The `/TS/` trap.** A folder `/TS/` on the flash makes MicroPython
resolve the whole `TS` package from it and stop looking at the frozen
modules; a partial copy there means `ImportError` and a Pico that does not
boot. That is why the overrides and the assets live at the root and in
`/assets/`, never under `/TS/` ([DEVELOPER_GUIDE.md §6](../../DEVELOPER_GUIDE.md#6-the-dev-override-pattern)).

## CI: `build.yml`

Runs on every push to any branch, on pull requests to `main`, and by hand;
Ubuntu 22.04. The steps, in order:

1. **Build tools**: `git`, `build-essential`, `cmake`,
   `gcc-arm-none-eabi`, `libnewlib-arm-none-eabi`, `python3` from apt.
   Each attempt has 4 minutes and is retried up to three times: apt on the
   hosted runners hung mid-download four times on 2026-09-30.
2. **BASIC → TAP**: `tools/build-basic.sh` tokenizes every `basic/**/*.bas`
   with the vendored `zmakebas` (catches a `.bas` that will not tokenize).
   The outputs — `src/assets/*.tap` for the Pico's flash, `SD card/…` for
   the card — are gitignored. The paths the script reports are staged
   (not a glob: `SD card/` also holds committed `.tap` files) and uploaded
   as the `basic-taps` artifact, so a branch's programs can be tested
   without a local toolchain.
3. **Host tests**: 44 `src/test/*_hosttest.py` scripts on CPython, each
   running the real firmware modules with `machine`/`rp2` faked — including
   `reference_hosttest.py`, the test that keeps this reference current
   ([README](../README.md#keeping-it-current)). They pin invariants that
   used to be checked only by flashing a UF2; they do not observe the Z80
   bus.
4. **The flash manifest**: `tools/build-flash.py check flash/manifest.json`
   (below).
5. **sjasmplus** v1.22.0, built from source (no Ubuntu package), then the
   **programmer's manual examples**: `docs/manual/examples/test_examples.py`
   (the Z80 routines against a simulated Pico) and `test_extcmd_host.py`
   (the example commands through the real `PROCESS_CMD`).
6. **ROM 2.3**: `tools/build-rom.py --verify` assembles the fdd module and
   splices it onto the SYNC/BREAK layer's image (`src/rom/TSPICO-SYNC.ROM`), failing if any patch's "before" bytes or any
   anchor no longer match ([../rom/overview.md](../rom/overview.md)); then
   `cmp` of `build/TSPICO-fdd.ROM` against `src/rom/TSPICO-23.ROM`: the
   committed slot-1 image must be exactly what the sources build. Then
   `rom_cend_hosttest.py` runs the ROM's BIOS `C_END`, and
   `rom_tpmode_hosttest.py` its switch words (`tpi:tape` and the rest),
   `rom_preload_hosttest.py` the module's pre-load check, and
   `rom_fn86_hosttest.py` the string reader and function 86h's loop, in a
   Z80 interpreter.
   The ROM and its two halves are uploaded as `tspico-fdd-rom`.
7. **MicroPython v1.29.0**, cloned shallow.
8. **The build stamp**: `cmp` of `src/TS/tspico.py` with
   `src/dev_tspico.py` (fails with the first 40 lines of `diff`), then
   `gen-buildinfo.py`.
9. **Staging**: `src/TS/*.py` (the twelve files the manifest names) copied to
   `ports/rp2/modules/TS/`, and `src/manifest.py` over
   `ports/rp2/boards/manifest.py`.
10. `mpy-cross`, `make submodules`, `make clean`, `make` for the default
    board, `RPI_PICO`: `build-RPI_PICO/firmware.uf2`, uploaded as
    `tspico-firmware-uf2`.
11. **The upgrade UF2** ([upgrade.md](upgrade.md)): `tools/build-upgrade.py`
    makes the updater tape and ROM images; `tspico_io.py`, `sdcard.py`,
    `native.py`, `__init__.py`, `upgrade.py`, `main.py` and the generated
    `upgrade_data.py` are staged in `modules-upgrade/`; `make
    BUILD=build-UPGRADE FROZEN_MANIFEST=…/manifest_upgrade.py`. Uploaded as
    `tspico-upgrade-uf2`, with `updater.tap`.
12. **The web updater's flasher** (`node web-updater/test/flasher.test.mjs`)
    against a fake PICOBOOT device with both UF2s: every block lands where
    the UF2 says, and the read-back verify catches a write that did not
    take.
13. **`dev_tspico.mpy`** with the `mpy-cross` from step 10, uploaded as
    `dev_tspico-mpy`.
14. On failure, the CMake logs.

A second job, `build-v3`, runs alongside: the v3 board's UF2
([board-v3.md](board-v3.md)). It installs the same tools with the same
retries, clones MicroPython v1.29.0 itself, builds `mpy-cross`, and runs
`make submodules`, generates the build stamp (`tools/gen-buildinfo.py`:
the board's manifest freezes `src/TS/` directly, `buildinfo.py` among them),
and runs `make` with
`BOARD_DIR=$GITHUB_WORKSPACE/src/boards/TSPICO_V3`, so nothing is copied
into the MicroPython tree. It needs its own clone because step 9 replaces
the port's `boards/manifest.py`. The UF2, `build-TSPICO_V3/firmware.uf2`,
is uploaded as `tspico-v3-firmware-uf2`. The board brings in the `tsbus`
module itself (`USER_C_MODULES`), so the job needs no extra arguments. The
UF2 is the whole firmware, `TS.tspico` on `board_v3` (step 4.3 of the v3
port plan); `pico-serial.py flash --v3 --branch B` fetches it.

A third job, `manual-pdf`, runs alongside too: `tools/manual-pdf/ci-setup.sh`
installs a pinned pandoc (3.5; Ubuntu's 2.9 has no `--embed-resources`),
the Linux fonts the stylesheets fall back to (Charis SIL, Nimbus Sans,
DejaVu Sans Mono) and `pypdf`; the heading and cover fonts (Arvo, Inter,
Poppins) are in `tools/manual-pdf/fonts/`. `tools/manual-pdf/make.sh` turns
`docs/manual/user-manual.md` into HTML with pandoc, and
`tools/manual-pdf/book.py` adds the title page, contents and chapter
openers, prints the manual and the two covers with the runner's Chrome, and
assembles the half-letter one-up (cover + manual) and the saddle-stitch
booklet (covers, blank inside covers, padding to a multiple of 4, imposed
two up on letter). Chrome ignores `break-before: right`, so the manual is
printed twice: the first print says where each chapter starts, and a blank
page goes in before each one that would open on a left-hand page. The
cover's version comes from `config.ini` and its date from the last commit.
The script checks the page size and count and that every chapter opens on
an odd page; the two PDFs are uploaded as
`tspico-manual-pdf`. Building them on every push means a manual change that
breaks them fails here, not at release time.

Artifacts are kept 30 days. `tools/pico-serial.py flash --branch B`
downloads the `tspico-firmware-uf2` of B's current head and flashes it
(below). The list of host tests in step 3 is the authority on what CI
runs; a new test needs a line there.

A second workflow, `emu-host.yml`, builds the standalone emulator host
(`tools/emu`) for each platform on pushes that touch `src/`, `basic/` or
the emulator, and attaches the binaries to a release
([docs/EMULATOR_BRIDGE.md](../../EMULATOR_BRIDGE.md)).

## Releases: `release.yml`

Fires on a pushed tag `v*` (or by hand with a tag). Version numbers: the
major.minor are the ROM's, the patch digit is firmware-only (2.2.1 is
firmware 2.2.1 on ROM 2.2). The job, at the tag:

1. Builds as `build.yml` does — the stamp check, staging, the firmware
   UF2, `dev_tspico.mpy`, the upgrade UF2, the BASIC TAPs. **It runs no
   tests**: the commit is expected to have passed `build.yml` already.
2. **The bundle** `ts-pico-<tag>.zip`: `firmware.uf2`, a generated
   `DEPLOY.md`, `src/` (`main.py`, `config.ini`, `words.txt`,
   `assets/*.tap`, `rom/TSPICO-23.ROM`) for the Pico's flash, and
   `SD card/` (`TAP/` recursively, `help/`, the loose `*.tap` of the card's
   root).
3. **The 512K flash image** `Pico-<tag>.rom`, if a base image can be
   found (below): `build-flash.py check`, `build --base`, `verify`.
4. **The user manual PDFs**, as `build.yml`'s `manual-pdf` job makes them,
   from the manual at the tag.
5. **The release**: assets the zip, `firmware.uf2` (raw, for an in-place
   reflash), `upgrade.uf2`, `user-manual-half-letter.pdf`,
   `user-manual-saddle-stitch-letter.pdf`, and the flash image when there
   is one. If the
   release already exists, the assets are uploaded to it (`--clobber`) and
   its notes left alone; otherwise it is created with the notes in
   `.github/release-notes/<tag>.md` if that file exists at the tag, else
   GitHub's generated notes. Prefer the file: creating the release is what
   starts the Pages deploy, so a release made by hand first would publish
   the updater before these assets were attached.

**Pages** (`pages.yml`) runs when the release workflow completes (a
`workflow_run`: GitHub does not fire `release` events for releases made
by a workflow's token), on a green build of `main`, and on pushes to
`main` that touch `site/`, `web-updater/`, `SD card/`, the manuals or the
reference. It copies the two manuals and this reference into the site
(`tools/build-site-docs.py`, links rewritten for the site), builds the user
manual's two PDFs into `site/manual/` (`tools/manual-pdf/make.sh`, linked
from the Docs page), builds the Jekyll site and mounts the web updater at `/updater/`, with the latest
release's payload under `/updater/release/` and the latest green `main`
build under `/updater/main/` — served from the site itself because
GitHub's release CDN sends no CORS header, so a browser cannot fetch
release assets from another origin.

## The 512K flash image

The flash chip the 2068's ROMs run from is 512K: **16 slots of 32K**,
`00h` where unused. A ROM fills one slot; a DCK cartridge two consecutive
slots (64K), so cartridges sit at even slots. The firmware picks the BOOT
and DOCK slots by the `bank_sm` word, a nibble each
([pio.md](pio.md#sel_bank), [hardware.md](../hardware.md)).

[`flash/manifest.json`](../../../flash/manifest.json) lists what ships:

| Slot | Size | Contents | Source | crc32 |
|---|---|---|---|---|
| 0 | 32K | TS-Pico ZX Spectrum ROM v4 | `src/rom/TSPICO-ZX48-V4.BIN` | `083655BF` |
| 1 | 32K | TS-Pico TS-2068 ROM 2.3 | `src/rom/TSPICO-23.ROM` | `1338F0D5` |
| 2 | 32K | ZX Diagnostics v0.37 | base image | `FA54FB1D` |
| 3 | 32K | Rodolfo Guerra's TK90/95 ROM | base image | `9554B434` |
| 4–7 | — | spare | — | — |
| 8 | 64K | Pinball (LROS) | base image | none: all `00h` in the base |
| 10 | 64K | Flight Simulator (AROS) | base image | `377A9681` |
| 12 | 64K | Crazy Bugs (AROS) | base image | `AD7E5D44` |
| 14 | 64K | Casino (AROS) | base image | `BADC1E9D` |

`ROM_SLOT` 1 and `DCK_SLOT` 0 are the defaults: a stock board boots the
2068 ROM with the Spectrum ROM in the dock. Six of the eight are other
people's work, which the repository does not vendor; they come from a
**base image**, a known-good 512K dump (`Pico-v15w.rom`) kept as the one
asset of a *draft* release tagged `flash-base` (a draft's assets are not
public, but the release job's token can read them), or from the
`FLASH_BASE_URL` repository variable if set
([flash/README.md](../../../flash/README.md)). With neither, the release
has no flash image; it never publishes a partial one. The released image
may contain the third-party slots (decided 2026-09-28).

[`tools/build-flash.py`](../../../tools/build-flash.py), four commands (and `--slots`):

- **`build manifest --out F [--base B] [--slot N=FILE …]`**: a fill-`00h`
  image; every `from_base` slot copied from `B` (which must be exactly
  512K), every `file` slot from the repo, padded with `00h` if short.
  `--slot` replaces a slot for one build without touching the manifest,
  including a spare slot (4–7: one 32K image), which is how a test ROM goes
  on a board beside the shipping ones. Refused, writing nothing: a file
  bigger than its slot, a slot outside 0–15, a slot given twice, the second
  half of a 64K cartridge (9, 11, 13, 15), an unreadable file. Prints each
  slot's crc32, marking overrides and any slot that differs from the
  manifest ("CHANGED"). Without `--base` the missing slots are listed,
  "INCOMPLETE … not shippable", exit 2.
- **`verify manifest image`**: each listed slot's crc32 against the
  manifest (a `null` crc is skipped, so Pinball's slot is not checked).
  Spare slots are not looked at.
- **`check manifest`**: each `file` slot in the repo, padded, against the
  manifest's crc32. CI runs it on every push, so a ROM that changes without
  its manifest entry fails the build instead of shipping an unchecked image.
- **`extract image --out DIR`**: takes a production image apart into slot
  files (used once, to seed the manifest).
- **`build … --slots DIR`** also cuts the built image into the v3 card's
  slot files, `DIR/F00.bin` … `F15.bin`, 32K each (`write_slots`). A slot
  that is all `00h` gets no file, and a stale one is removed: on the card a
  missing file is an empty slot ([board.md](board.md#board_v3py)). From the
  v15w base this writes F00–F03 and F11, F13, F15, because the AROS
  cartridges keep their content in their upper half. They go into the
  card's `/slots` over USB for now
  ([docs/v3-slots-proposal.md](../../v3-slots-proposal.md)).

The module docstring names `src/rom/TSPICO-23.ROM` for slot 1 and points at
the manifest and this chapter (until #181 it named `TSPICO.ROM` and a
`FLASH_LAYOUT.md` that does not exist). [`build_flash_hosttest.py`](../../../src/test/build_flash_hosttest.py)
pins the build's refusals.

Deploying: a new board's flash is programmed with the whole image on a
chip programmer. In the field a slot is rewritten from the 2068 itself:
mount a `.ROM` or `.DCK` and `LOAD ""` runs `romupdate.tap` or
`dckupdate.tap`, which pick a slot with `tpi:dock` and stream the image
with `tpi:blkrcv` ([tspico-commands.md](tspico-commands.md#blkrcvpre-cmd)).
Never the slot the 2068 booted from: the firmware refuses it.

## `tools/pico-serial.py`

The Pico's USB console from a shell, standard library only, for people and
AI agents who would otherwise ask someone to copy text out of Thonny:
`watch` (read-only, timestamped, reattaches after an unplug), `break`
(Ctrl-C to the REPL — this stops the firmware), `run` (a statement or a
file in paste mode), `softreset` (Ctrl-D: `main.py` again), `put` and
`get` (files over the REPL, base64), and `flash` (a UF2 file, or the
`tspico-firmware-uf2` / `tspico-upgrade-uf2` / `tspico-v3-firmware-uf2`
(`--v3`) artifact of a branch's current head or of a given successful run,
via `gh`; it reboots the board into BOOTSEL with `machine.bootloader()`, so
no buttons, and finds either chip's drive, `RPI-RP2` or `RP2350`). Before
copying, `flash` compares the UF2's family IDs with the drive's
`INFO_UF2.TXT` Board-ID and refuses a UF2 built for the other chip, leaving
the board in BOOTSEL. `--sd` on `put`, `get` and `run` mounts the SD card
at `/sd` first, as `ACTIVATE_SD` does (`board.sd_take_bus`, `sd_spi`,
`sd_cs`, then `TS.sdcard.SDCard`; so on either board), and unmounts it and
calls `board.sd_release_bus` after; a `put`/`get` path gets `/sd` in front.
That is how test tapes go onto the card without a card reader
(`src/test/sd_roundtrip.py`). Like `put`, it needs the firmware stopped
(`break`), and `softreset` after. Every command refuses
to start if another process holds the port. Never `break` while the Pico
may be in the middle of an SD access: a card left mid-transfer needed a
power cycle before the driver learned to recover it
([sdcard.md](sdcard.md)).

## The Pico's flash filesystem at run time

| Path | What | Made by | Used by |
|---|---|---|---|
| `/main.py` | the start-up script | the web updater, the release bundle, Thonny | MicroPython at boot |
| `/config.ini` | the settings | the same; rewritten by `LOAD_CONFIG` and `MEMBOOT` | `_telemetry`, `LOAD_CONFIG`, the web updater |
| `/words.txt` | a word list | the same | the example external command `tpi:.rndw` |
| `/assets/nofile.tap` | the tape `LOAD ""` serves with nothing mounted | `build-basic.sh` → the same | `TS2068_IO` opens it at boot ([tspico_io.md](tspico_io.md#open_nofile_tap)) |
| `/assets/romupdate.tap`, `/assets/dckupdate.tap` | the slot updaters | `build-basic.sh` → the same | `MOUNT_FILE` for a `.ROM`/`.BIN`/`.DCK` |
| `/activity.log` | the log | `SAVE_LOG`; `main.py` on a fatal error | `tpi:log`; trimmed to 64 KB at boot |
| `/TMP/` | scratch: removed and re-made at every boot (`TS2068_IO`, 6218–6219) | `TS2068_IO` | below |
| `/TMP/temp.tap` | the mounted TAP, copied from the card (or the updater tape) | `MOUNT_FILE` | `LOAD_TS`, `FWD`/`REW` via the table; removed by `FORGET_MOUNT` |
| `/TMP/temp.bin` | the mounted ROM or DCK image (a DCK rebuilt to a full 64K by `DCK_IMAGE`) | `MOUNT_FILE`, `DCK_IMAGE` | `BLKRCV`; removed by `FORGET_MOUNT` |
| `/TMP/native.tap` | the one-shot tape for `LOAD "f:…"` | `NATIVE_LOAD_PREP` | `LOAD_TS` |
| `/dev_tspico.py`/`.mpy`, `/dev_extcmd.py` | the dev overrides | a developer | `main.py`, `TS2068_IO` |

The tapes are on the flash, not the card, because `LOAD_TS` streams from a
file while the card cannot have the bus ([tspico-files.md](tspico-files.md)).
A flash write stops both cores, which is why nothing may be written there
while a transfer runs ([PROTOCOL.md §13](../../PROTOCOL.md#13-pitfalls),
"Wait for core1"). A MicroPython **downgrade** (a v1.20 UF2 over v1.29)
reformats the flash and loses every file here (seen on hardware); back
them up first.

## Where comments and the code disagree

- The `WAIT` name for GPIO 14 (above); the line's comment now says
  `TS_IO_DUAL` uses it as /PICOSEL, and that the name is unverified.
