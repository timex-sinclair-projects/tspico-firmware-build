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
# Usage: tools/manual-pdf/make.sh [OUTDIR]     (default build/manual-pdf)
#        Only the two PDFs go into OUTDIR. pages.yml builds them into
#        site/manual for the website; release.yml attaches them.
#
# Needs pandoc (2.19 or later), Google Chrome or Chromium (set CHROME to its
# path if it isn't found), and Python 3 with pypdf. The version on the cover
# and in the page headers comes from src/config.ini; the date is the month of
# the last commit. CI (build.yml, release.yml) installs the Linux fonts the
# stylesheets fall back to: Charis SIL, Nimbus Sans, DejaVu Sans Mono.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
OUT="${1:-$REPO/build/manual-pdf}"
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
      -e "s|{{IMG}}|file://$REPO/site/assets/img|g" "$HERE/$1" > "$WORK/$1"
}
fill print.css; fill cover.css; fill front.html; fill back.html

pdf() {
  "$CHROME" --headless=new --disable-gpu --no-sandbox --no-pdf-header-footer \
            --print-to-pdf="$WORK/$2" "file://$WORK/$1" >/dev/null 2>&1
  [ -s "$WORK/$2" ] || { echo "Chrome produced no $2" >&2; exit 1; }
}

if pandoc --help | grep -q -- --embed-resources; then EMBED=--embed-resources; else EMBED=--self-contained; fi
pandoc "$REPO/docs/manual/user-manual.md" -f gfm -t html5 --standalone $EMBED \
       --resource-path="$REPO/docs/manual" --metadata pagetitle="TS-Pico User Manual" \
       --css "$WORK/print.css" -o "$WORK/user-manual.html"
pdf user-manual.html body.pdf
pdf front.html front.pdf
pdf back.html back.pdf

cd "$WORK"
python3 - <<'PY'
import pypdf
W, H = 5.5 * 72, 8.5 * 72
body = list(pypdf.PdfReader("body.pdf").pages)
front = pypdf.PdfReader("front.pdf").pages[0]
back = pypdf.PdfReader("back.pdf").pages[0]
for name, p in [("manual", body[0]), ("front cover", front), ("back cover", back)]:
    w, h = float(p.mediabox.width), float(p.mediabox.height)
    assert abs(w - W) < 1 and abs(h - H) < 1, "%s is %.1f x %.1f pt, not half letter" % (name, w, h)
assert len(body) > 20, "the manual came out as %d pages" % len(body)
blank = lambda: pypdf.PageObject.create_blank_page(width=W, height=H)
meta = {"/Author": "The TS-Pico team"}

# One-up: the cover, then the manual (its page 1 is the title page).
w = pypdf.PdfWriter()
for p in [front] + body:
    w.add_page(p)
w.add_metadata(dict(meta, **{"/Title": "TS-Pico User Manual"}))
w.write("user-manual-half-letter.pdf")

# Booklet: front, blank inside front, the manual, blanks to a multiple of 4,
# blank inside back, back. The manual's page 1 stays a right-hand page.
pad = (-(len(body) + 4)) % 4
seq = [front, blank()] + body + [blank() for _ in range(pad)] + [blank(), back]
n = len(seq)
w = pypdf.PdfWriter()
for k in range(n // 4):                      # sheet k: front [n-1-2k | 2k], back [2k+1 | n-2-2k]
    for left, right in ((n - 1 - 2 * k, 2 * k), (2 * k + 1, n - 2 - 2 * k)):
        side = pypdf.PageObject.create_blank_page(width=2 * W, height=H)
        side.merge_transformed_page(seq[left], pypdf.Transformation())
        side.merge_transformed_page(seq[right], pypdf.Transformation().translate(W, 0))
        w.add_page(side)
w.add_metadata(dict(meta, **{"/Title": "TS-Pico User Manual (booklet: letter, saddle stitch)"}))
w.write("user-manual-saddle-stitch-letter.pdf")
assert n % 4 == 0
print("manual %d pages; one-up %d pages; booklet %d pages (%d blank padding), %d letter sheets"
      % (len(body), len(body) + 1, n, pad, n // 4))
PY
cp user-manual-half-letter.pdf user-manual-saddle-stitch-letter.pdf "$OUT/"
echo "$OUT/user-manual-half-letter.pdf"
echo "$OUT/user-manual-saddle-stitch-letter.pdf"
