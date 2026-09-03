# FDD native disk-command extension (EXROM module)

Z80 source for the native disk commands (`CAT`/`FORMAT`/`MOVE`/`ERASE`, and later
`OPEN #`/`CLOSE #`/`PRINT #`/`INPUT #`) described in
[`docs/FDD_COMMANDS_DESIGN.md`](../../../docs/FDD_COMMANDS_DESIGN.md).

- **`fddcmd.asm`** — the module, assembled at **`$3000`** and spliced into the
  EXROM half of `src/rom/TSPICO.ROM`. Today it is a skeleton: it establishes the
  base address, the `FDD_DISPATCH` entry point the HOME-ROM hook will call, and
  the signature the build verifies. The command handlers are stubs.

## Build

```bash
python3 tools/build-rom.py --verify      # -> build/TSPICO-fdd.ROM
```

Requires **sjasmplus** (`brew install sjasmplus`). The build:

1. assembles `fddcmd.asm` (→ raw slice + symbols),
2. copies the crc-checked base `src/rom/TSPICO.ROM`,
3. splices the module into free EXROM at `$3000` (asserts the region is `$FF`),
4. applies the declarative patch manifest in `tools/build-rom.py` (each patch
   asserts the bytes it overwrites),
5. writes `build/TSPICO-fdd.ROM` and, with `--verify`, asserts that *only* the
   module region and enabled patches changed.

Outputs land in `build/` (git-ignored). Load `build/TSPICO-fdd.ROM` in ZEsarUX
(`--romfile`) exactly like the shipping ROM.

### When the base ROM changes

`build-rom.py` refuses to patch a `src/rom/TSPICO.ROM` whose crc32 doesn't match
its recorded `BASE_ROM_CRC` — so a merged ROM update stops the build until you
re-base:

```bash
python3 tools/build-rom.py --rebase      # re-check patch sites, update the crc
```

`--rebase` confirms every patch's `before` bytes still match and the `$3000`
module region is still free, then rewrites `BASE_ROM_CRC`. If an anchor moved it
**refuses** (non-zero exit) and names the site, so a real conflict can't be
papered over. It doesn't touch `ROMs/` or `romdiff.py`'s `EXPECT_CRC` — update
those in the same pass if you keep the split halves in sync.

## Where things live

- **Base address `$3000`** is set by `FDD_BASE` in `fddcmd.asm` and mirrored by
  `FDD_ORG` in `tools/build-rom.py` — keep them in sync. `$3000–$3FFF` is our 4 KB;
  `$22A1–$2FFF` is left for Gustavo (design doc §2).
- **HOME-ROM patches** are data in `tools/build-rom.py`'s `PATCHES` list, not in
  this source (the source is EXROM-only). The syntax-offset-table fix is enabled;
  the `$25D6` disk-token hook is staged (needs the HOME→EXROM thunk stub).
