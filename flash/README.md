# The 512K flash image

The TS-PICO's flash chip is 512K, laid out as **16 slots of 32K**, zero-filled
where unused. The firmware selects a slot with `ROM_SLOT` / `DCK_SLOT` in
`config.ini` (`tpi:boot` and `tpi:dock` at runtime), packed 4 bits each into
`bank_sm`. DCK entries are **64K** — two consecutive slots — which is why the
cartridge slot numbers step by 2.

| Slot | Offset | Kind | Contents | Source |
|---|---|---|---|---|
| 0 | `0x000000` | ROM/DCK | TS-Pico ZX Spectrum ROM v2 | [`ROMs/TSPICO-ZX48-V2.BIN`](../ROMs/TSPICO-ZX48-V2.BIN) |
| 1 | `0x008000` | ROM | TS-Pico TS-2068 ROM | [`src/rom/TSPICO.ROM`](../src/rom/TSPICO.ROM) |
| 2 | `0x010000` | ROM/DCK | ZX Diagnostics v0.37 | base image |
| 3 | `0x018000` | ROM | Rodolfo Guerra's TK90/95 ROM | base image |
| 4–7 | `0x020000` | — | spare | — |
| 8 | `0x040000` | DCK | Pinball (LROS) | base image — **absent from Pico-v15w.rom** |
| 10 | `0x050000` | DCK | Flight Simulator (AROS) | base image |
| 12 | `0x060000` | DCK | Crazy Bugs (AROS) | base image |
| 14 | `0x070000` | DCK | Casino (AROS) | base image |

`ROM_SLOT` defaults to 1 and `DCK_SLOT` to 0, so a stock machine boots the
TS-2068 ROM with the Spectrum cartridge in the dock.

## Building an image

```bash
# our slots from the repo, third-party slots from a known-good image
./tools/build-flash.py build flash/manifest.json --base Pico-v15w.rom --out Pico-v18.rom

# check a built image against the manifest's checksums
./tools/build-flash.py verify flash/manifest.json Pico-v18.rom

# check the repo's ROMs against the manifest (CI runs this on every push)
./tools/build-flash.py check flash/manifest.json
```

Without `--base` the build reports the missing third-party slots and exits
non-zero, so a partial image can't be mistaken for a shippable one.

## Why a base image instead of vendoring everything

Six of the eight populated slots are other people's work: ZX Diagnostics
(Brendan Alford, GPL), Rodolfo Guerra's TK90/95 ROM, and four DCK cartridges.
Rather than commit them to a public repo, the build copies them out of a
known-good 512K image supplied at build time. Release CI fetches that image
from the `FLASH_BASE_URL` repo variable; if it isn't set, the release simply
carries no flash image.

**Open decision:** if we'd rather vendor those blobs (simpler builds, no
external dependency), that's a licensing call, not a technical one — the
manifest supports both: give a slot a `file` instead of `from_base`.

**Also open:** Pinball is listed at slot 8 but the whole 64K is `0x00` in
`Pico-v15w.rom`, so the current image ships three cartridges, not four. Its
manifest entry has `crc32: null` and `verify` skips it until we decide whether
to restore it.

## Deploying

- **New builds:** burn the assembled 512K image to the flash chip with a
  programmer. This is how boards are built.
- **In-place upgrades:** mount the 32K `.ROM` and `LOAD ""` to run
  `romupdate.tap`, which erases and writes the slot you pick. It does *not*
  set the boot slot — and `tpi:boot` is a one-shot override that `LOAD_CONFIG`
  resets to 1 on the next power-up, so a permanent change means writing slot 1
  itself. (`rompatch.tap` is unrelated: it applies a fixed 12K v1.2-era payload
  baked into the firmware and stamps `ROM_VERSION = 1.2`. Don't use it to
  upgrade to 1.5+.)
