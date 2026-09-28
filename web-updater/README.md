# TS-Pico Web Updater

A single static page that takes a TS-Pico from whatever it has — 1.1, 1.5,
2.x, or a blank or wiped Pico — to the current firmware, from the browser,
with no files to drag. Started as the prototype for
[issue #26](https://github.com/timex-sinclair-projects/tspico-firmware-build/issues/26).

## What a run does

The user connects, ticks what they need, and presses **Start**:

1. **Connect** — Web Serial → Ctrl-C the firmware → raw REPL. Reads
   `FW_VERSION` from `/config.ini` (1.1 has none) and pre-ticks the ROM update
   for a board on 1.x.
2. **BOOTSEL** — `machine.bootloader()` over the REPL, then a handle on the
   boot ROM: **WebUSB/PICOBOOT** if the browser can open it, else the
   **RPI-RP2 drive** through the File System Access API (see below). A Pico
   that won't connect can be put in BOOTSEL by hand; Start then skips step 1.
3. **Wipe** — erase all 2 MB (WebUSB), or write `flash_nuke.uf2` onto the
   drive and wait for it to come back. Clears old files such as a `/TS/`
   folder that would shadow the frozen modules.
4. **ROM update** (boards from 1.1/1.5) — write `upgrade.uf2`
   ([src/upgrade/](../src/upgrade/)), reboot, reopen the serial port, and
   follow its `UPG {json}` lines while the user types `OUT 244,3` and
   `LOAD ""` on the 2068: tape loading, each block written, verify, DONE, or a
   failure (e.g. the P10 jumper). Then `machine.bootloader()` again.
5. **Firmware** — write `firmware.uf2` (WebUSB also reads it back to verify)
   and reboot.
6. **Files** — reopen the serial port (Chrome remembers the permission, so no
   picker), write `main.py`, `config.ini`, `words.txt`, `assets/*.tap`,
   verify names and sizes, `machine.reset()`.

Every step can be rerun; a Pico left in BOOTSEL is always recoverable.

## Writing a UF2 without dragging

| Path | How | Works on |
|---|---|---|
| **WebUSB (PICOBOOT)** | [Pico⚡Flash](https://github.com/piersfinlayson/picoflash)'s protocol code talks to the boot ROM's vendor interface: erase, write, read back, reboot. | Chrome/Edge on macOS, ChromeOS, Android. Linux needs picotool's udev rule. **An RP2040 on Windows needs WinUSB bound to “RP2 Boot” (Zadig)** — its boot ROM has no Microsoft OS descriptors. |
| **RPI-RP2 drive** | `showDirectoryPicker()` on the drive (checked by its `INFO_UF2.TXT`), then the UF2 is written onto it, as a drag would. The Pico reboots on the last block, so a failing close/rename afterwards is expected; the drive disappearing is the success signal. The handle is by path, so it works again when the drive comes back. | Any desktop Chrome/Edge, no driver. |

The page offers WebUSB first and falls back to the drive when the device
can't be opened. `?via=drive` forces the drive route (for testing it, or when
WebUSB misbehaves on a machine). Chrome titles the drive picker "select where this site
can save changes", so the page tells users to pick the RPI-RP2 drive itself
there; a wrong folder is caught by the `INFO_UF2.TXT` check and the button is
offered again. The logic is in [flasher.js](flasher.js); a host test runs it
against a fake PICOBOOT device with real UF2s:

```sh
node test/flasher.test.mjs [firmware.uf2 ...]
```

CI runs it on every build with the two UF2s it just built.

## Channels

The page installs from one of two payloads, chosen at the top of the page
(also `?channel=main`):

- **`release/`** — the latest GitHub Release: its `firmware.uf2` and
  `upgrade.uf2` assets, and the Pico files from its tag.
- **`main/`** — the latest green `build.yml` run on `main`, for testers: its
  `tspico-firmware-uf2` and `tspico-upgrade-uf2` artifacts, and the Pico files
  from its commit.

The Pico files are the channel's `src/` from `git archive`, plus the TAPs
`tools/build-basic.sh` generates from that same commit (`nofile`, `romupdate`
and `dckupdate` are gitignored, so the archive alone doesn't have them).
`build-payload.sh` refuses to build a channel without those three.

Each channel is a directory with `manifest.json`, `pico/`, `firmware.uf2`,
`firmware-uf2.zip`, `upgrade.uf2` and `sdcard.zip`. A release from before
`upgrade.uf2` existed simply has no ROM update; the page says so and points at
the other channel.

## What's here

```
web-updater/
├── index.html          page + styling
├── app.js              the guided run (serial, stages, ROM-update monitor)
├── flasher.js          BOOTSEL writing: UsbBootsel (WebUSB) + DriveBootsel (drive)
├── flash_nuke.uf2      Raspberry Pi flash-erase image (drive path + manual download)
├── build-payload.sh    assembles one channel directory
├── test/               host test for flasher.js
├── vendor/
│   ├── transports.js     ViperIDE WebSerial transport (trimmed)
│   ├── rawmode.js        ViperIDE MpRawMode: raw REPL, writeFile, walkFs…
│   ├── utils.js          ViperIDE helpers (trimmed)
│   └── picoflash/        Pico⚡Flash PICOBOOT library (see its README)
├── release/            generated channel (gitignored)
└── main/               generated channel (gitignored)
```

## Browser support

Web Serial is **Chromium-only**: Chrome, Edge, Opera on desktop/ChromeOS. No
Safari, Firefox or iOS; the page says so. Only one program can hold the serial
port — close Thonny or other tabs first.

## Run it locally

Web Serial and WebUSB need a secure context, which includes
`http://localhost`. From the repo root:

```sh
# a channel from local sources (no UF2 -> the page offers only the file copy)
web-updater/build-payload.sh
# or the main channel from a CI run's artifacts
gh run download <run-id> -n tspico-firmware-uf2 -D /tmp/fw
gh run download <run-id> -n tspico-upgrade-uf2 -D /tmp/upg
CHANNEL=main OUT_DIR=web-updater/main \
  UPGRADE_UF2="$(find /tmp/upg -path '*build-UPGRADE/firmware.uf2')" \
  web-updater/build-payload.sh src main@local /tmp/fw/firmware.uf2
python3 -m http.server 8000 --directory web-updater
```

## Deployment

[pages.yml](../.github/workflows/pages.yml) builds the Jekyll site and mounts
this page at **`/updater/`** with both channels next to it. It runs on pushes to
`main` touching the site or updater, when a Release is published, when the
Release workflow finishes, and when a `build.yml` run on `main` goes green (so
`main/` follows main).

Everything the page loads is **same-origin**: a `github.io` page can't fetch
release assets (their CDN sends no `Access-Control-Allow-Origin`) or CI
artifacts (they need a token), so the workflow downloads them server-side and
publishes them with the page.

One-time repo setup: **Settings → Pages → Source → “GitHub Actions”**.

## Still to do

- [ ] Hardware pass on a 1.1 board and a 1.5 board end to end, on macOS
      (WebUSB) and Windows (drive path).
- [ ] Confirm Chrome on Windows lets `showDirectoryPicker()` pick a drive root.
- [ ] Per-file byte-level progress for the file copy.

## License

`vendor/transports.js`, `rawmode.js`, `utils.js`: MIT, © Volodymyr Shymanskyy
(ViperIDE). `vendor/picoflash/`: MIT, © Piers Finlayson (Pico⚡Flash). The rest
is part of this repository.
