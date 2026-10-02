# The 512K flash image

The TS-PICO's flash chip is 512K, laid out as **16 slots of 32K**, zero-filled
where unused. The firmware selects a slot with `ROM_SLOT` / `DCK_SLOT` in
`config.ini` (`tpi:boot` and `tpi:dock` at runtime), packed 4 bits each into
`bank_sm`. DCK entries are **64K** — two consecutive slots — which is why the
cartridge slot numbers step by 2.

| Slot | Offset | Kind | Contents | Source |
|---|---|---|---|---|
| 0 | `0x000000` | ROM/DCK | TS-Pico ZX Spectrum ROM v3 | [`src/rom/TSPICO-ZX48-V3.BIN`](../src/rom/TSPICO-ZX48-V3.BIN) (built from v2 by `tools/build-rom.sh`; v2's LOAD/SAVE are broken, see [`PATCH_ZX48_HANDSHAKE.md`](../docs/rom-analysis/PATCH_ZX48_HANDSHAKE.md)) |
| 1 | `0x008000` | ROM | TS-Pico TS-2068 ROM 2.1 | [`src/rom/TSPICO-21.ROM`](../src/rom/TSPICO-21.ROM): `tools/build-rom.py` output (ROM 2.0, [`src/rom/TSPICO-SYNC.ROM`](../src/rom/TSPICO-SYNC.ROM), plus the disk-command module `src/rom/fdd/` and its patches). CI checks the committed file matches a fresh build. |
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

`--slot N=FILE` replaces a slot's contents for one build without touching the
manifest. It works on the spare slots 4–7 too, which is the easy way to put a
test ROM on a board alongside the shipping ones:

```bash
# shipping image plus a test ROM in spare slot 4 (select it with ROM_SLOT=4)
./tools/build-flash.py build flash/manifest.json --base Pico-v15w.rom \
    --slot 4=build/TSPICO-fdd.ROM --out Pico-test.rom
```

A spare slot takes one 32K image, zero-padded if shorter. The build refuses —
exits non-zero and writes nothing — rather than drop an override: a file
bigger than its slot, a slot number outside 0–15, a slot given twice, or the
second half of a 64K cartridge (slots 9, 11, 13, 15). The summary marks every
override with `<- override`. `verify` only checks the manifest's slots, so it
ignores whatever you put in a spare one.

## Why a base image instead of vendoring everything

Six of the eight populated slots are other people's work: ZX Diagnostics
(Brendan Alford, GPL), Rodolfo Guerra's TK90/95 ROM, and four DCK cartridges.
Rather than commit them to a public repo, the build copies them out of a
known-good 512K image supplied at build time.

Release CI (`.github/workflows/release.yml`, step "Build 512K flash image")
gets that image from, in order:

1. **The `FLASH_BASE_URL` repo variable**, if set. It's an override and is
   normally left unset.
2. **The draft release tagged `flash-base`** in this repo, whose one asset is
   `Pico-v15w.rom`. A draft's assets aren't public, but the release job's
   `GITHUB_TOKEN` can read them. Leave it a draft: publishing it would expose
   the base image on its own and make it the "latest" release. To replace the
   base, delete the old asset from the draft and upload the new one.

With neither, the step is skipped and the release carries no flash image. It
never publishes a partial one. With a base, the release gets `Pico-<tag>.rom`,
built and then checked with `verify`.

**Decided (2026-09-28):** the released `Pico-<tag>.rom` may include the
third-party slots. The repo still doesn't vendor them as separate files; they
reach the release only inside the assembled image. If we ever want to vendor
them instead, the manifest supports it: give a slot a `file` instead of
`from_base`.

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
  itself.
- **You can't update the slot you booted from.** The Z80 erases the slot it's
  writing, so it would erase the ROM it's running on, and both machines hang
  with the slot half-written. With a `.ROM`/`.BIN`/`.DCK` mounted, the firmware
  refuses `tpi:memdock` to the boot slot, and `tpi:blkrcv` checks the DOCK again
  before it sends anything. The updater stops with Report Q ("Can't write
  Flash slot N: the 2068 is running from it"); nothing has been erased. A `.DCK`
  fills slots n and n+1, so it is refused when either one is the boot slot.
  Boot a different slot (`SAVE "tpi:boot" CODE 2,1: NEW`), then run the updater
  again.
