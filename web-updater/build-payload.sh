#!/usr/bin/env bash
#
# Assemble the updater payload: copy the Pico-flash files out of ../src into
# web-updater/pico/ and generate manifest.json (file list + sizes + firmware
# version). This mirrors what the release workflow will publish to the
# gh-pages branch alongside index.html, so the page can fetch everything
# same-origin (GitHub's release-asset CDN blocks browser CORS — see README).
#
# Usage:
#   ./build-payload.sh [SRC_DIR] [TAG] [UF2_PATH]
#
#   SRC_DIR   firmware source dir (default: ../src)
#   TAG       release tag string for the manifest (default: dev-local)
#   UF2_PATH  optional firmware.uf2 to include for the download link
#
# Output (gitignored): web-updater/pico/ and web-updater/manifest.json
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="${1:-$HERE/../src}"
TAG="${2:-dev-local}"
UF2="${3:-}"

OUT="$HERE/pico"
rm -rf "$OUT"
mkdir -p "$OUT/assets"

# Pico-flash filesystem content (everything except the UF2). Matches the
# src/ side of the release.yml bundle layout.
#
# NOTE: help/ is deliberately NOT included. As of the src/ re-org the BASIC
# help text lives on the SD card (SD card/help/ in the bundle, read by the
# firmware from /help/ on the mounted card at runtime), not on the Pico's
# internal flash. The web updater only writes Pico flash, so help text is
# out of its scope — it's installed by copying "SD card/" to the SD card.
cp "$SRC/main.py"      "$OUT/main.py"
cp "$SRC/config.ini"   "$OUT/config.ini"
cp "$SRC/words.txt"    "$OUT/words.txt"
cp "$SRC"/assets/*.tap "$OUT/assets/"

# Optional UF2 (flashed via BOOTSEL, not written over serial — referenced by
# the manifest only as a download link).
UF2_FIELD="null"
if [ -n "$UF2" ] && [ -f "$UF2" ]; then
  cp "$UF2" "$OUT/firmware.uf2"
  UF2_FIELD='"pico/firmware.uf2"'
fi

# Generate manifest.json. Paths are relative to pico/; the page fetches each
# as pico/<path>. fw_version is pulled from config.ini so the page can compare
# installed-vs-latest.
FW_VERSION="$(python3 -c "import json,sys; print(json.load(open('$OUT/config.ini')).get('FW_VERSION','?'))")"

python3 - "$OUT" "$TAG" "$FW_VERSION" "$UF2_FIELD" > "$HERE/manifest.json" <<'PY'
import json, os, sys
out, tag, fw, uf2 = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
files = []
for root, _dirs, names in os.walk(out):
    for n in sorted(names):
        if n == 'firmware.uf2':
            continue  # not a filesystem file
        full = os.path.join(root, n)
        rel = os.path.relpath(full, out).replace(os.sep, '/')
        files.append({'path': rel, 'size': os.path.getsize(full)})
files.sort(key=lambda f: f['path'])
manifest = {
    'tag': tag,
    'fw_version': fw,
    'uf2': None if uf2 == 'null' else uf2.strip('"'),
    'files': files,
}
print(json.dumps(manifest, indent=2))
PY

echo "Wrote $OUT ($(find "$OUT" -type f | wc -l | tr -d ' ') files) and $HERE/manifest.json"
echo "Firmware version: $FW_VERSION  Tag: $TAG"
