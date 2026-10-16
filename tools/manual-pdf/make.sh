#!/bin/sh
# Build the TS-Pico User Manual as PDFs, from docs/manual/user-manual.md:
#
#   user-manual-half-letter.pdf           cover + manual, 5.5 x 8.5 in, one page
#                                         per page, links live: for reading
#   user-manual-saddle-stitch-letter.pdf  the same as a booklet: front cover,
#                                         blank, manual, blanks to a multiple
#                                         of 4, blank, back cover, imposed two
#                                         up on letter landscape for printing
#                                         double-sided (flip on the short edge)
#                                         and stapling on the fold
#
# Usage: [BOARD=v2|v3] tools/manual-pdf/make.sh [OUTDIR]  (default build/manual-pdf)
#        Only the two PDFs go into OUTDIR. pages.yml builds them into
#        site/manual for the website; release.yml attaches them.
#
# BOARD picks the manual (tools/manual-variants.py: user-manual.md holds
# both boards' passages between <!-- v2 --> / <!-- v3 --> markers): v2, the
# TS-Pico 2.x, is the default and the published one; v3, the v3 card, makes
# user-manual-v3-half-letter.pdf and user-manual-v3-saddle-stitch-letter.pdf
# (build.yml's artifact while the card is unreleased).
#
# The pages are styled after the 1983 Timex Sinclair 2068 User Manual
# (print.css, cover.css); every chapter opens on a right-hand page (book.py).
#
# Needs pandoc (2.19 or later), Google Chrome or Chromium (set CHROME to its
# path if it isn't found), and Python 3 with pypdf. The version on the cover
# and in the page headers comes from src/config.ini; the date is the month of
# the last commit. The heading and cover fonts (Arvo, Inter, Poppins; SIL OFL)
# and the code font (Timex TS2068; CC BY 3.0, credited in the colophon) are in
# fonts/; CI (build.yml, release.yml) installs the Linux fonts the
# stylesheets fall back to for the rest: Charis SIL, Nimbus Sans, DejaVu Sans
# Mono.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
OUT="${1:-$REPO/build/manual-pdf}"
BOARD="${BOARD:-v2}"
case "$BOARD" in
  v2) TITLE="TS-Pico User Manual"; T3="USER MANUAL"; NAME=user-manual ;;
  v3) TITLE="TS-Pico v3 User Manual"; T3="V3 CARD USER MANUAL"; NAME=user-manual-v3 ;;
  *)  echo "BOARD must be v2 or v3" >&2; exit 1 ;;
esac
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"
# Everything but the two PDFs is made in a scratch folder, so OUTDIR can be
# a folder of the website (pages.yml uses site/manual) without stray files.
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

if [ -z "$CHROME" ]; then
  for c in "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
           google-chrome google-chrome-stable chromium chromium-browser; do
    if [ -x "$c" ] || command -v "$c" >/dev/null 2>&1; then CHROME="$c"; break; fi
  done
fi
[ -n "$CHROME" ] || { echo "Chrome or Chromium not found; set CHROME" >&2; exit 1; }

# The version, from config.ini; the month of the last commit.
eval "$(python3 -c "
import json; c = json.load(open('$REPO/src/config.ini'))
print('FW=%s ROM=%s' % (c['FW_VERSION'], c['ROM_VERSION']))")"
DATE="$(cd "$REPO" && git log -1 --format=%cd --date=format:'%B %Y' 2>/dev/null || date +'%B %Y')"
fill() {
  sed -e "s|{{FW}}|$FW|g" -e "s|{{ROM}}|$ROM|g" -e "s|{{DATE}}|$DATE|g" \
      -e "s|{{TITLE}}|$TITLE|g" -e "s|{{T3}}|$T3|g" \
      -e "s|{{IMG}}|file://$REPO/site/assets/img|g" -e "s|{{FONTS}}|file://$HERE/fonts|g" \
      "$HERE/$1" > "$WORK/$1"
}
for f in print.css cover.css front.html back.html mask.html; do fill $f; done
cp -R "$HERE/img" "$WORK/img"

if pandoc --help | grep -q -- --embed-resources; then EMBED=--embed-resources; else EMBED=--self-contained; fi
python3 "$REPO/tools/manual-variants.py" "$BOARD" "$REPO/docs/manual/user-manual.md" "$WORK/user-manual.md"
pandoc "$WORK/user-manual.md" -f gfm -t html5 --standalone --section-divs $EMBED \
       --resource-path="$REPO/docs/manual" --metadata pagetitle="$TITLE" \
       --css "$WORK/print.css" -o "$WORK/manual.html"

# The rest (title page, contents, chapter openers on right-hand pages, the
# covers, the one-up PDF and the booklet) is book.py's.
CHROME="$CHROME" FW="$FW" ROM="$ROM" DATE="$DATE" TITLE="$TITLE" T3="$T3" python3 "$HERE/book.py" "$WORK"
cp "$WORK/user-manual-half-letter.pdf" "$OUT/$NAME-half-letter.pdf"
cp "$WORK/user-manual-saddle-stitch-letter.pdf" "$OUT/$NAME-saddle-stitch-letter.pdf"
echo "$OUT/$NAME-half-letter.pdf"
echo "$OUT/$NAME-saddle-stitch-letter.pdf"
