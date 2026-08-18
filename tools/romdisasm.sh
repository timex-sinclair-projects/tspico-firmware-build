#!/usr/bin/env bash
# Regenerate the TS-PICO ROM disassemblies under docs/rom-analysis/disasm/.
#
#   ./tools/romdisasm.sh
#
# Requires z80dasm (brew install z80dasm).
#
# Every image disassembles at org 0x0000 because file offset == Z80 address for
# all of them; the EXROM is a flat 16K occupying TS2068 chunks 0+1. See
# docs/rom-analysis/MEMORY_MAP.md.
#
# The baseline images are ROMs/GENUINE-*.bin (crc32 bf44ec3f / ae16233a). Other
# TS2068 ROM images are in circulation and are not interchangeable with these;
# run tools/romdiff.py to have every image crc32-checked.
#
# NOTE: these are LINEAR sweeps. Data tables, text and 0xFF filler decode as
# nonsense instructions, and a misaligned start desynchronises a whole region.
# Use them to locate code, not as ground truth -- prefer the hand-verified
# listings in the Markdown docs. See the caveats in docs/rom-analysis/README.md.

set -euo pipefail

cd "$(dirname "$0")/.."

OUT=docs/rom-analysis/disasm
SYMS=docs/rom-analysis/tspico-exrom-symbols.sym

command -v z80dasm >/dev/null || {
    echo "z80dasm not found. Install with: brew install z80dasm" >&2
    exit 1
}

mkdir -p "$OUT"

# image:output-basename
PLAIN="
TSPICO-11-exrom:tspico-11-exrom
TSPICO-15w-exrom:tspico-15w-exrom
TSPICO-11-home:tspico-home
GENUINE-2068-exrom.bin:genuine-2068-exrom
GENUINE-2068-home.bin:genuine-2068-home
"

for pair in $PLAIN; do
    src="ROMs/${pair%%:*}"
    name="${pair##*:}"
    [ -f "$src" ] || { echo "missing $src -- see docs/rom-analysis/README.md" >&2; exit 1; }
    z80dasm -a -l -t -g 0x0000 -o "$OUT/$name.asm" -s "$OUT/$name.sym" "$src" 2>/dev/null
    echo "  $OUT/$name.asm  ($(wc -l < "$OUT/$name.asm" | tr -d ' ') lines)"
done

# Labelled EXROM listings, using our curated symbol names. These are the ones
# worth reading: the v1.5w fix renders as `jp nz,YN_LOOP_GUARD` /
# `call WAIT_PICO_READY` instead of bare addresses.
for v in 11 15w; do
    z80dasm -a -l -t -g 0x0000 -S "$SYMS" \
            -o "$OUT/tspico-$v-exrom.labelled.asm" "ROMs/TSPICO-$v-exrom" 2>/dev/null
    echo "  $OUT/tspico-$v-exrom.labelled.asm  (labelled)"
done

echo
echo "TSPICO-11-home and TSPICO-15w-home are byte-identical -- only one HOME"
echo "listing (tspico-home.asm) is produced."
