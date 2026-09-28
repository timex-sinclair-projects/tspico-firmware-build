# Pico⚡Flash (vendored)

The PICOBOOT-over-WebUSB library from
[piersfinlayson/picoflash](https://github.com/piersfinlayson/picoflash),
MIT, © Piers Finlayson (see `LICENSE`). Upstream commit `6783554`
(2026-08-25).

Copied verbatim:

- `pkg/{picoboot,connection,commands,constants,errors,target}.js`
- `js/uf2/uf2.js` → `uf2.js`

Not copied: `pkg/index.js`, which re-exports `FLASH_END_RP2040` /
`FLASH_END_RP2350` that `constants.js` does not define, so importing it
fails. `../../flasher.js` imports `picoboot.js` and `uf2.js` directly.

To update: copy the same files from a newer upstream checkout and bump the
commit above.
