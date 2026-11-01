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
# and, from docs/manual/quick-start.md and quick-reference.md (quick.py):
#
#   quick-start-half-letter.pdf           the Quick Start Guide: the cover,
#                                         six pages, the back cover
#   quick-start-saddle-stitch-letter.pdf  the same as a booklet on two letter
#                                         sheets, printed and folded as above
#   quick-reference-card-letter.pdf       the Quick Reference Guide, after the
#                                         2068's: one letter sheet, landscape,
#                                         printed double-sided (flip on the
#                                         short edge) and folded in three
#
# Usage: [BOARD=v2|v3] [PRINT=1 [PAPER=white|cream]] tools/manual-pdf/make.sh [OUTDIR]
#        (default build/manual-pdf). Only the five PDFs go into OUTDIR.
#        pages.yml builds them into site/manual for the website;
#        release.yml attaches them.
#
# PRINT=1 makes the files for printing on demand instead, the paperback
# on Amazon KDP and the coil-bound book on Lulu (manual.yml's artifact). With
# no OUTDIR they go on the Desktop, ready to upload (build/manual-print if
# there is no ~/Desktop):
#
#   user-manual-print-interior.pdf   the manual without its cover, 5.5 x 8.5
#                                    in, an even number of pages: the
#                                    interior for both, with a wider inside
#                                    margin for the binding (GUTTER=0.8 in)
#   user-manual-kdp-cover.pdf        back, spine and front on one sheet with
#                                    0.125 in of bleed all round; the spine
#                                    is the page count times KDP's paper
#                                    thickness (PAPER, white by default:
#                                    pick the same paper in KDP)
#   user-manual-lulu-coil-cover.pdf  back and front, no spine, with bleed:
#                                    11.25 x 8.75 in
#
# BOARD picks the manual (tools/manual-variants.py: user-manual.md holds
# both boards' passages between <!-- v2 --> / <!-- v3 --> markers, and so do
# the quick guides): v2, the TS-Pico 2.x, is the default and the published
# one; v3, the v3 card, makes user-manual-v3-half-letter.pdf and
# user-manual-v3-saddle-stitch-letter.pdf, and quick-start-v3-* and
# quick-reference-card-v3-letter.pdf (manual.yml's artifact while the card
# is unreleased). PRINT=1 makes only the manual's print files.
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
if [ -n "$1" ]; then OUT="$1"
elif [ -n "$PRINT" ] && [ -d "$HOME/Desktop" ]; then OUT="$HOME/Desktop"   # ready to upload
elif [ -n "$PRINT" ]; then OUT="$REPO/build/manual-print"
else OUT="$REPO/build/manual-pdf"; fi
BOARD="${BOARD:-v2}"
case "$BOARD" in
  v2) TITLE="TS-Pico User Manual"; T3="USER MANUAL"; NAME=user-manual ;;
  v3) TITLE="TS-Pico v3 User Manual"; T3="V3 CARD USER MANUAL"; NAME=user-manual-v3 ;;
  *)  echo "BOARD must be v2 or v3" >&2; exit 1 ;;
esac
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"
# Everything but the PDFs is made in a scratch folder, so OUTDIR can be
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
      "$HERE/$1" > "${DEST:-$WORK}/$1"
}
for f in print.css cover.css front.html back.html mask.html; do fill $f; done
# A perfect-bound paperback loses some of the inside margin into the spine,
# so the print interior gets a wider gutter (GUTTER, inches; 0.8 by default
# against the reading PDF's 0.62) and a slightly narrower outside margin.
if [ -n "$PRINT" ]; then
  GUTTER="${GUTTER:-0.8}"
  sed -i.bak -e "s|^@page :left  { margin-left: 0.5in;  margin-right: 0.62in; }|@page :left  { margin-left: 0.45in; margin-right: ${GUTTER}in; }|" \
             -e "s|^@page :right { margin-left: 0.62in; margin-right: 0.5in; }|@page :right { margin-left: ${GUTTER}in; margin-right: 0.45in; }|" \
             "$WORK/print.css"
  grep -q "margin-right: ${GUTTER}in" "$WORK/print.css" || { echo "GUTTER: print.css margins not found" >&2; exit 1; }
fi
cp -R "$HERE/img" "$WORK/img"

if pandoc --help | grep -q -- --embed-resources; then EMBED=--embed-resources; else EMBED=--self-contained; fi
python3 "$REPO/tools/manual-variants.py" "$BOARD" "$REPO/docs/manual/user-manual.md" "$WORK/user-manual.md"
pandoc "$WORK/user-manual.md" -f gfm -t html5 --standalone --section-divs $EMBED \
       --resource-path="$REPO/docs/manual" --metadata pagetitle="$TITLE" \
       --lua-filter "$HERE/manual.lua" \
       --css "$WORK/print.css" -o "$WORK/manual.html"

# The rest (title page, contents, chapter openers on right-hand pages, the
# covers, the one-up PDF and the booklet) is book.py's.
PRINT="$PRINT" PAPER="$PAPER" CHROME="$CHROME" FW="$FW" ROM="$ROM" DATE="$DATE" TITLE="$TITLE" T3="$T3" python3 "$HERE/book.py" "$WORK"
if [ -n "$PRINT" ]; then
  for f in print-interior kdp-cover lulu-coil-cover; do
    cp "$WORK/$f.pdf" "$OUT/$NAME-$f.pdf"; echo "$OUT/$NAME-$f.pdf"
  done
  exit 0
fi
cp "$WORK/user-manual-half-letter.pdf" "$OUT/$NAME-half-letter.pdf"
cp "$WORK/user-manual-saddle-stitch-letter.pdf" "$OUT/$NAME-saddle-stitch-letter.pdf"
echo "$OUT/$NAME-half-letter.pdf"
echo "$OUT/$NAME-saddle-stitch-letter.pdf"

# The Quick Start Guide and the Quick Reference Guide (quick.py), in a
# folder of their own: the guide's front cover is the manual's with its own
# title.
QW="$WORK/quick"
mkdir -p "$QW"
TITLE="TS-Pico Quick Start Guide"; T3="QUICK START"
for f in print.css quick.css card.css cover.css front.html quick-back.html; do DEST="$QW" fill $f; done
cp -R "$HERE/img" "$QW/img"
case "$BOARD" in v3) SUFFIX=-v3 ;; *) SUFFIX= ;; esac
for doc in quick-start quick-reference; do
  python3 "$REPO/tools/manual-variants.py" "$BOARD" "$REPO/docs/manual/$doc.md" "$QW/$doc.md"
done
pandoc "$QW/quick-start.md" -f gfm -t html5 --standalone --section-divs $EMBED \
       --resource-path="$REPO/docs/manual" --metadata pagetitle="$TITLE" \
       --css "$QW/print.css" --css "$QW/quick.css" -o "$QW/quick-start.html"
pandoc "$QW/quick-reference.md" -f gfm -t html5 --standalone $EMBED \
       --metadata pagetitle="TS-Pico Quick Reference Guide" --css "$QW/card.css" -o "$QW/quick-reference.html"
for what in start card; do
  SUFFIX="$SUFFIX" CHROME="$CHROME" FW="$FW" ROM="$ROM" DATE="$DATE" python3 "$HERE/quick.py" $what "$QW"
done
for f in quick-start$SUFFIX-half-letter quick-start$SUFFIX-saddle-stitch-letter quick-reference-card$SUFFIX-letter; do
  cp "$QW/$f.pdf" "$OUT/$f.pdf"; echo "$OUT/$f.pdf"
done
