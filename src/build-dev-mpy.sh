#!/usr/bin/env bash
# Compile dev_tspico.py -> dev_tspico.mpy for memory-constrained Pico boots.
#
# The Pico's MicroPython parser is memory-hungry. Once dev_tspico.py grew
# past ~4000 lines (post stage-9 telemetry additions), parsing it at boot
# started to OOM. Pre-compiled .mpy bytecode skips the parser entirely
# and uses ~80% less storage besides.
#
# Usage:
#   src/build-dev-mpy.sh                  # builds src/dev_tspico.mpy
#   src/build-dev-mpy.sh /path/to/file.py # builds <file>.mpy alongside the .py
#
# The script resolves its own location, so the default source path
# (`<script-dir>/dev_tspico.py`) works whether you run it from the repo
# root, from src/, or anywhere else.
#
# Setup (one-time):
#   pip install --user mpy-cross==1.29.*  # match the UF2's MicroPython version
#                                          # (mpy v6.3 bytecode for MP 1.29.0)
#
# After build: upload <name>.mpy to the Pico's flash root (tools/pico-serial.py
# put), and delete any /dev_tspico.py there: MicroPython imports name.py before
# name.mpy (checked on a TS-Pico, MicroPython 1.29, #175), so a .py beside it
# wins. main.py's `from dev_tspico import TS2068_IO` then uses the bytecode.
# To go back to the .py, delete the .mpy and put the .py.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="${1:-${SCRIPT_DIR}/dev_tspico.py}"

if ! command -v mpy-cross >/dev/null 2>&1; then
    if [ -x "$HOME/.local/bin/mpy-cross" ]; then
        MPYC="$HOME/.local/bin/mpy-cross"
    else
        echo "error: mpy-cross not found. install with:" >&2
        echo "    pip install --user mpy-cross==1.29.*" >&2
        exit 1
    fi
else
    MPYC="mpy-cross"
fi

# Confirm version compatibility with UF2's MicroPython.
"$MPYC" --version 2>&1 | head -1

"$MPYC" "$SRC"

OUT="${SRC%.py}.mpy"
echo "built: $OUT"
ls -la "$OUT"
