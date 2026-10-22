#!/bin/sh
# Build the TS-Pico 2.3 flyer: promo/flyer/flyer.html -> tspico-2.3-flyer.pdf
# (letter, front and back), plus a PNG of each side for posting online.
#
# Usage: promo/flyer/make.sh [OUTDIR]   (default build/flyer)
#
# Needs Google Chrome or Chromium (set CHROME if it isn't found) and, for the
# PNGs, pdftoppm (poppler). Fonts and the Timex Sinclair badge come from
# tools/manual-pdf, the screenshots and the photo from site/assets/img and
# docs/manual/images.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
OUT="${1:-$REPO/build/flyer}"
mkdir -p "$OUT"; OUT="$(cd "$OUT" && pwd)"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT

if [ -z "$CHROME" ]; then
  for c in "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
           google-chrome google-chrome-stable chromium chromium-browser; do
    if [ -x "$c" ] || command -v "$c" >/dev/null 2>&1; then CHROME="$c"; break; fi
  done
fi
[ -n "$CHROME" ] || { echo "Chrome or Chromium not found; set CHROME" >&2; exit 1; }

for f in flyer.html flyer.css; do
  sed -e "s|{{FONTS}}|file://$REPO/tools/manual-pdf/fonts|g" \
      -e "s|{{TOOLS}}|file://$REPO/tools/manual-pdf|g" \
      -e "s|{{IMG}}|file://$REPO/site/assets/img|g" \
      -e "s|{{MAN}}|file://$REPO/docs/manual/images|g" \
      -e "s|{{DEMO}}|file://$REPO/promo/demo/screens|g" "$HERE/$f" > "$WORK/$f"
done
cp "$HERE/qr-updater.svg" "$WORK/"

"$CHROME" --headless=new --disable-gpu --no-sandbox --no-pdf-header-footer \
  --print-to-pdf="$OUT/tspico-2.3-flyer.pdf" "file://$WORK/flyer.html" 2>/dev/null
if command -v pdftoppm >/dev/null 2>&1; then
  pdftoppm -png -r 150 "$OUT/tspico-2.3-flyer.pdf" "$OUT/tspico-2.3-flyer"
fi
ls "$OUT"
