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
# the manifest only as a download link). Also offered zipped: some Windows
# antivirus/SmartScreen setups block or quarantine a raw .uf2 download, so the
# .zip (firmware.uf2 at its root) is a fallback the user can unzip and drag.
UF2_FIELD="null"
UF2_ZIP_FIELD="null"
UF2_ZIP="$HERE/firmware-uf2.zip"
rm -f "$UF2_ZIP"
if [ -n "$UF2" ] && [ -f "$UF2" ]; then
  cp "$UF2" "$OUT/firmware.uf2"
  UF2_FIELD='"pico/firmware.uf2"'
  ( cd "$OUT" && zip -q "$UF2_ZIP" firmware.uf2 )
  UF2_ZIP_FIELD='"firmware-uf2.zip"'
  echo "Wrote $UF2_ZIP"
fi

# SD card bundle (Step 3 on the page — software testers only). The firmware
# reads TAP programs and tpi:help text from a FAT SD card at runtime; testers
# copy this onto a card to exercise the firmware end-to-end. This is OUTSIDE the
# over-serial updater's scope (that writes Pico flash only) — it's offered as a
# plain same-origin .zip download. Zipped with its *contents* (TAP/, help/) at
# the zip root so "unzip → copy to card root" is a direct drag.
#
# Located relative to SRC: the "SD card/" folder is a sibling of src/ at the
# repo root (release.yml calls this with SRC=<repo>/src).
SDCARD_SRC="$(cd "$SRC/.." && pwd)/SD card"
SDCARD_ZIP="$HERE/sdcard.zip"
SDCARD_FIELD="null"
rm -f "$SDCARD_ZIP"
if [ -d "$SDCARD_SRC" ]; then
  TMP="$(mktemp -d)"
  cp -R "$SDCARD_SRC/." "$TMP/"
  find "$TMP" -name '.DS_Store' -delete
  ( cd "$TMP" && zip -rq "$SDCARD_ZIP" . )
  rm -rf "$TMP"
  SDCARD_BYTES="$(wc -c < "$SDCARD_ZIP" | tr -d ' ')"
  SDCARD_NFILES="$(find "$SDCARD_SRC" -type f ! -name '.DS_Store' | wc -l | tr -d ' ')"
  SDCARD_FIELD="{\"path\": \"sdcard.zip\", \"size\": ${SDCARD_BYTES}, \"files\": ${SDCARD_NFILES}}"
  echo "Wrote $SDCARD_ZIP (${SDCARD_NFILES} files, ${SDCARD_BYTES} bytes)"
else
  echo "No SD card dir at $SDCARD_SRC — skipping sdcard.zip"
fi

# Generate manifest.json. Paths are relative to pico/; the page fetches each
# as pico/<path>. fw_version is pulled from config.ini so the page can compare
# installed-vs-latest.
FW_VERSION="$(python3 -c "import json,sys; print(json.load(open('$OUT/config.ini')).get('FW_VERSION','?'))")"

python3 - "$OUT" "$TAG" "$FW_VERSION" "$UF2_FIELD" "$UF2_ZIP_FIELD" "$SDCARD_FIELD" > "$HERE/manifest.json" <<'PY'
import json, os, sys
out, tag, fw, uf2, uf2_zip, sdcard = sys.argv[1:7]
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
    'uf2_zip': None if uf2_zip == 'null' else uf2_zip.strip('"'),
    'sdcard': None if sdcard == 'null' else json.loads(sdcard),
    'files': files,
}
print(json.dumps(manifest, indent=2))
PY

echo "Wrote $OUT ($(find "$OUT" -type f | wc -l | tr -d ' ') files) and $HERE/manifest.json"
echo "Firmware version: $FW_VERSION  Tag: $TAG"
