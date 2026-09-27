#!/bin/bash
# Build the TS-Pico test ROMs from their bases plus the patches, then check them:
#
#   src/rom/patches/tspico-sync.asm      v1.7 + SYNC/BREAK -> src/rom/TSPICO-SYNC.ROM
#   src/rom/patches/tspico-zx48-v3.asm   ZX v2 + tpi: LOAD -> src/rom/TSPICO-ZX48-V3.BIN
#
# Needs sjasmplus (https://github.com/z00m128/sjasmplus). The shipping ROM,
# src/rom/TSPICO.ROM (slot 1 in flash/manifest.json), is never modified.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root/src/rom"
# -Wno-fileorg: every patch is FPOS + ORG into the INCBIN'd image, which is
# exactly the "ORG without padding" that warning describes.
sjasmplus --nologo --msg=war -Wno-fileorg --lst=patches/tspico-sync.lst patches/tspico-sync.asm
sjasmplus --nologo --msg=war -Wno-fileorg --lst=patches/tspico-zx48-v3.lst patches/tspico-zx48-v3.asm
python3 "$root/src/test/rom_sync_hosttest.py"
python3 "$root/src/test/rom_zx48_hosttest.py"
