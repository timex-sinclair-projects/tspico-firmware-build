#!/usr/bin/env bash
# Compile dev_tspico.py -> dev_tspico.mpy for memory-constrained Pico boots.
#
# The Pico's MicroPython parser is memory-hungry. Once dev_tspico.py grew
# past ~4000 lines (post stage-9 telemetry additions), parsing it at boot
# started to OOM. Pre-compiled .mpy bytecode skips the parser entirely
# and uses ~80% less storage besides.
#
# Usage:
#   ./build-dev-mpy.sh                    # builds dev_tspico.mpy in repo root
#   ./build-dev-mpy.sh /path/to/file.py   # builds <file>.mpy alongside the .py
#
# Setup (one-time):
#   pip install --user mpy-cross==1.20.*  # match the UF2's MicroPython version
#                                          # (mpy v6.1 bytecode for MP 1.20.0)
#
# After build: upload <name>.mpy to the Pico's flash root via Thonny. Python's
# import system picks up .mpy in preference to .py, so main.py's
# `from dev_tspico import TS2068_IO` will use the compiled bytecode without
# any code changes. If you want to revert to .py, delete the .mpy from the
# Pico.

set -euo pipefail

SRC="${1:-dev_tspico.py}"

if ! command -v mpy-cross >/dev/null 2>&1; then
    if [ -x "$HOME/.local/bin/mpy-cross" ]; then
        MPYC="$HOME/.local/bin/mpy-cross"
    else
        echo "error: mpy-cross not found. install with:" >&2
        echo "    pip install --user mpy-cross==1.20.*" >&2
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
