# TS-Pico Web Updater (prototype)

A single static page that uploads the TS-Pico Pico-flash files — `main.py`,
`config.ini`, `words.txt`, `assets/*.tap` (subfolders preserved) — onto a Pico
over **WebSerial**, replacing the manual file-copy step after the UF2 is
flashed. Prototype for
[issue #26](https://github.com/timex-sinclair-projects/tspico-firmware-build/issues/26);
see the research write-up for the full rationale.

> **Scope:** the over-serial uploader writes the Pico's internal **flash**
> filesystem only. SD-card content (the `SD card/` bundle — `help/` text and
> `TAP/` files) is installed by copying it to the card directly — the page
> offers it as a **Step 4** `.zip` download (for software testers), but does not
> write it over the serial link.

> **Wipe step:** the page opens with an optional **Step 1 · Wipe the Pico**, a
> plain download of the Raspberry Pi `flash/nuke` image (`flash_nuke.uf2`,
> dragged onto RPI-RP2 in BOOTSEL mode). It's needed when a board carries
> leftover files from an older distribution that block the current firmware from
> booting. This is a static same-origin download — not part of the serial flow.

It's a "very limited ViperIDE": it vendors ViperIDE's MIT-licensed WebSerial
transport and raw-REPL file-writing code, and adds a small connect → update →
verify → reboot UI on top.

## What's here

```
web-updater/
├── index.html          page + styling
├── app.js              UI glue (connect, update, verify, reboot, bootloader)
├── flash_nuke.uf2      Raspberry Pi flash-erase image, Step 1 (committed)
├── vendor/             ViperIDE code, MIT (copyright headers kept)
│   ├── transports.js     WebSerial transport (Transport + WebSerial only)
│   ├── rawmode.js        MpRawMode: raw REPL, writeFile, makePath, walkFs…
│   └── utils.js          sleep / Mutex / helpers (trimmed of UI deps)
├── build-payload.sh    assembles pico/ + sdcard.zip + manifest.json (for testing)
├── pico/               generated payload      (gitignored)
├── firmware-uf2.zip    generated zipped UF2, Step 2 fallback (gitignored)
├── sdcard.zip          generated SD-card bundle, Step 4 (gitignored)
└── manifest.json       generated file list    (gitignored)
```

`vendor/transports.js` and `vendor/utils.js` are trimmed copies of the
upstream files (Bluetooth/WebSocket/WebRTC transports and the
toastr/analytics/peerjs dependencies removed); `vendor/rawmode.js` is verbatim
apart from one import path. Each file's header notes exactly what changed.

## How it works

1. **Connect** — `navigator.serial.requestPort()` → open at 115200 → Ctrl-C to
   interrupt the running firmware → Ctrl-A into the raw REPL. Reads device info
   and the installed `FW_VERSION` from `/config.ini`.
2. **Update** — for each file in `manifest.json`: fetch `pico/<path>`
   same-origin, `makePath()` its directory, `writeFile()` the bytes. Writes go
   to a temp file and `os.rename()` into place (atomic), and are binary-safe so
   `.tap` files transfer fine.
3. **Verify** — `walkFs()` the device and compare names/sizes against the
   manifest.
4. **Reboot** — `machine.reset()` to restart the firmware, or
   `machine.bootloader()` to drop into the RPI-RP2 drive for a UF2 flash with no
   BOOTSEL button.

## Browser support

WebSerial is **Chromium-only**: Chrome, Edge, Opera on desktop/ChromeOS. No
Safari, no Firefox, no iOS. The page detects this and shows a notice. Only one
program can hold the serial port at a time — close any other program or
browser tab connected to the Pico first.

## Run it locally

WebSerial requires a secure context, which includes `http://localhost`. From
this directory:

```sh
./build-payload.sh          # generate pico/ + manifest.json from ../src
python3 -m http.server 8000 # or any static server
# open http://localhost:8000/ in Chrome or Edge
```

To include the UF2 download link, pass a built firmware:

```sh
./build-payload.sh ../src dev-local /path/to/firmware.uf2
```

## Deployment (the CORS gotcha)

A `github.io` page **cannot** fetch GitHub release assets — the download URL
redirects to `objects.githubusercontent.com`, which sends no
`Access-Control-Allow-Origin`, so the browser blocks the bytes. The fix is to
publish the payload to the **same origin** as the page.

This is **wired into `.github/workflows/pages.yml`**, which deploys the whole
site to GitHub Pages. It builds the Jekyll site in `../site/`, then mounts this
updater at **`/updater/`**: it runs `build-payload.sh` (UF2 + `pico/` payload +
`manifest.json`) and copies the static page + `vendor/` + payload + manifest +
`flash_nuke.uf2` into the built site under `updater/`. The page fetches its
payload from that same-origin `/updater/` path — no CORS, no proxy. The
firmware `.uf2` is downloaded from the latest GitHub **Release** at build time
(server-side, where CORS doesn't apply); creating a release (`release.yml`)
fires `pages.yml` to refresh the site with the new firmware.

**One-time repo setup** (can't be done from the workflow): in
**Settings → Pages**, set **Source → "GitHub Actions"**. After the next push or
release, the updater is live at `https://<owner>.github.io/<repo>/updater/`.
Until then, run it locally (above). The old "Deploy from a branch / `gh-pages`"
setup is no longer used.

### Remaining to productionize

- [ ] Test against a real TS-Pico in a TS-2068, including interrupting the
      firmware mid-`LOAD`.
- [ ] Per-file byte-level progress (currently file-level / size-weighted).
- [ ] Optional drag-drop `.zip` fallback for offline use
      ([fflate](https://github.com/101arrowz/fflate)).
- [ ] Win/macOS/Linux pass; `dialout` group note for Linux.

## License

The `vendor/` files are MIT, © Volodymyr Shymanskyy (ViperIDE). The rest is
part of this repository.
