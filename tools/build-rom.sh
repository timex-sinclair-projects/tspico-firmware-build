#!/bin/bash
# Build the TS-Pico 1.8b "sync" test ROM from v1.7 plus the patches in
# src/rom/patches/tspico-sync.asm, then check it.
#
#   tools/build-rom.sh            -> src/rom/TSPICO-SYNC.ROM
#
# Needs sjasmplus (https://github.com/z00m128/sjasmplus). The shipping ROM,
# src/rom/TSPICO.ROM (slot 1 in flash/manifest.json), is never modified.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root/src/rom"
# -Wno-fileorg: every patch is FPOS + ORG into the INCBIN'd image, which is
# exactly the "ORG without padding" that warning describes.
sjasmplus --nologo --msg=war -Wno-fileorg --lst=patches/tspico-sync.lst patches/tspico-sync.asm
python3 "$root/src/test/rom_sync_hosttest.py"
