# TS-Pico Updater for Windows

A small Windows program that does what the [web updater](../web-updater/)
does: erase the Pico, update the TS-2068 ROM, install the firmware and copy
its files. It exists because the browser can't finish that job on Windows:

- **WebUSB** can't open the RP2040's boot ROM ("RP2 Boot"). Windows binds no
  driver to it, since the boot ROM has no Microsoft OS descriptors, so it needs
  WinUSB installed with Zadig first. That's too much to ask of users.
- **The RPI-RP2 drive route** relies on Chrome's folder picker handing the
  page a drive root, which doesn't work there.

A native program has neither problem. It copies each UF2 onto the RPI-RP2
drive letter, as a drag would, and talks to MicroPython over the COM port
with pyserial.

Users download **`TS-Pico-Updater.exe`** from the
[latest release](https://github.com/timex-sinclair-projects/tspico-firmware-build/releases/latest)
and run it. There's nothing to install. The exe isn't signed, so the first
run shows Windows SmartScreen: **More info → Run anyway**.

## What a run does

The same six steps as the web page, with the same rules. `core.py` follows
`web-updater/app.js` closely, so a change to one usually belongs in the
other.

1. **Connect**: find the Pico's COM port (USB vendor 2E8A), Ctrl-C the
   firmware, raw REPL, read the running `FW_VERSION` (else `/config.ini`'s)
   and the MicroPython release. The ROM step is pre-ticked by `rom_behind()`.
2. **BOOTSEL**: `machine.bootloader()`, then wait for a removable drive
   whose `INFO_UF2.TXT` says `RPI-RP2`. A Pico already in BOOTSEL skips
   step 1.
3. **Wipe**: copy `flash_nuke.uf2`, which the exe carries. The Pico erases
   itself and comes back as RPI-RP2.
4. **ROM update**: copy the channel's `upgrade.uf2` and follow its
   `UPG {json}` serial lines while the user types `OUT 244,3` and `LOAD ""`
   on the 2068. Then the 2068 goes off and the Pico goes back to BOOTSEL.
5. **Firmware**: copy `firmware.uf2`. The drive vanishing is the success
   signal.
6. **Files**: reopen the COM port, write each file over the raw REPL
   (base64, 1 KB per exec), check names and sizes, then `machine.reset()`.

Before a run that would install an older MicroPython than the Pico runs, the
program warns that the first boot will reformat the filesystem, as the web
page does.

## Where the firmware comes from

From the published web updater's channels, fetched at run time:
`https://timex-sinclair-projects.github.io/tspico-firmware-build/updater/{release,main}/`
(the `manifest.json`, the UF2s and `pico/`). One exe therefore keeps
installing the newest release, and only needs rebuilding when the program
itself changes. `--channel main` opens on the testers' channel. `--base`
points at another copy of `/updater/`, either a URL or a local folder such as
`web-updater/` after `build-payload.sh`.

## Files

```
windows-updater/
├── core.py            the run: serial + raw REPL, drive, the six stages (no GUI)
├── app.py             the tkinter window; talks to core only through core.Ui
├── requirements.txt   pyserial, pyinstaller (pinned)
└── test/core_test.py  a whole run against a fake Pico
```

## Build and test

[`.github/workflows/windows-updater.yml`](../.github/workflows/windows-updater.yml)
builds the exe on `windows-latest` with PyInstaller (`--onefile --windowed`,
`flash_nuke.uf2` bundled). It runs on every change here and uploads the exe
as an artifact. When the Release workflow finishes, it attaches the exe to
that release. **Run workflow** with a tag attaches it to an existing release.

The host test needs only Python and runs anywhere:

```sh
python3 windows-updater/test/core_test.py
```

The test's fake Pico speaks the raw REPL and runs the code it receives
against a temporary directory that stands in for the flash. Its RPI-RP2
"drive" is another directory: a UF2 copied there reboots the fake into
firmware, the ROM updater (which replays a full set of `UPG` lines) or the
flash eraser.

`core.py` also runs on macOS and Linux (`/Volumes/RPI-RP2`,
`/media/*/RPI-RP2`), so you can try it against a real board without a
Windows machine:

```sh
pip install pyserial
python3 windows-updater/app.py            # needs a Python with Tk
```
