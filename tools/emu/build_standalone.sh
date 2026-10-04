#!/usr/bin/env bash
# Build the standalone pico_host: the TS-Pico firmware for emulators, one
# executable with no Python install needed (docs/EMULATOR_BRIDGE.md).
#
#   tools/emu/build_standalone.sh            -> dist/pico_host (dist/pico_host.exe on Windows)
#
# Needs: python3 with PyInstaller (pip install pyinstaller), and the generated
# TAPs in src/assets (tools/build-basic.sh) -- CI builds those first. Bundles
# src/TS, config.ini, words.txt, assets/, and a starter card (sd-seed/: the
# help files and an empty TAP folder). Run from the repository root.
set -euo pipefail
cd "$(dirname "$0")/../.."
for f in src/assets/nofile.tap src/assets/romupdate.tap src/assets/dckupdate.tap; do
  [ -f "$f" ] || { echo "missing $f: run tools/build-basic.sh first" >&2; exit 1; }
done
[ -f src/TS/buildinfo.py ] || "${PYTHON:-python3}" tools/gen-buildinfo.py
STAGE="build/pico_host-stage"
rm -rf "$STAGE" && mkdir -p "$STAGE/src" "$STAGE/sd-seed/TAP"
cp -R src/TS "$STAGE/src/TS"
find "$STAGE/src" -name '__pycache__' -prune -exec rm -rf {} +
cp src/config.ini src/words.txt "$STAGE/src/"
cp -R src/assets "$STAGE/src/assets"
cp -R "SD card/help" "$STAGE/sd-seed/help"
SEP=":"; HERE="$PWD"
case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) SEP=";"; HERE="$(cygpath -w "$PWD")";; esac
"${PYTHON:-python3}" -m PyInstaller --noconfirm --clean --onefile --name pico_host \
  --distpath dist --workpath build/pyinstaller --specpath build/pyinstaller \
  --add-data "$HERE/$STAGE/src${SEP}src" --add-data "$HERE/$STAGE/sd-seed${SEP}sd-seed" \
  tools/emu/pico_host.py
echo "built: $(ls dist/pico_host*)"
