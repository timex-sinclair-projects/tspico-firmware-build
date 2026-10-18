#!/usr/bin/env python3
"""Turn pandoc's HTML of the user manual into the two PDFs (run by make.sh).

    book.py WORKDIR

WORKDIR holds manual.html (pandoc, --section-divs), print.css, front.html,
back.html and mask.html with their placeholders filled; the PDFs are written
there. $CHROME is the browser; $FW, $ROM, $DATE go on the title page.
With $PRINT set it also writes the files for printing on demand (see the
end): print-interior.pdf, kdp-cover.pdf and lulu-coil-cover.pdf ($PAPER,
white or cream, sets the KDP spine).

What it does to the HTML:
  - drops the Markdown's own title and contents list, and puts in a title
    page, a colophon and a table of contents in the style of the 2068 User
    Manual (chapter, title, the chapter's keywords, page);
  - turns each "# Chapter N: Title" / "# Appendix X: Title" into an opener
    (title, big number, heavy rule; a leading blockquote becomes the
    "Chapter Preview") and gives the chapter a named page carrying its
    running head and, at the inner foot, its keywords in red. The keywords
    come from a comment after the heading in the Markdown:
        <!-- keywords: LOAD · SAVE · VERIFY -->

Chapters open on a right-hand (odd) page. Chrome ignores break-before:
right, so the body is printed twice: the first print says where each chapter
starts, a blank page goes in before each one that lands on a left-hand page,
and the second print, with the page numbers in the contents, is the one used.
Chrome has no @page :first for a chapter either, so the running head is
painted out on each opener page afterwards (mask.html).
"""
import html, os, re, subprocess, sys
import pypdf

W, H = 5.5 * 72, 8.5 * 72
work = sys.argv[1]
os.chdir(work)
FW, ROM, DATE = os.environ["FW"], os.environ["ROM"], os.environ["DATE"]
TITLE = os.environ.get("TITLE", "TS-Pico User Manual")   # make.sh: the board's manual
T3 = os.environ.get("T3", "USER MANUAL")


def chrome(src, dst):
    if os.path.exists(dst):
        os.remove(dst)
    subprocess.run([os.environ["CHROME"], "--headless=new", "--disable-gpu", "--no-sandbox",
                    "--no-pdf-header-footer", "--print-to-pdf=" + dst, "file://" + os.path.abspath(src)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    if not (os.path.exists(dst) and os.path.getsize(dst)):
        sys.exit("Chrome produced no " + dst)


def text(h):
    """HTML to plain text, for a running head."""
    return html.unescape(re.sub(r"<[^>]+>", "", h)).strip()


def css_str(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


src = open("manual.html", encoding="utf-8").read()
head, body = re.match(r"(?s)(.*<body>)(.*)(?=</body>)", src).groups()

# Split the body at its level-1 sections; the first is the title and contents.
starts = [m.start() for m in re.finditer(r'<section id="[^"]*" class="level1">', body)]
chunks = [body[a:b] for a, b in zip(starts, starts[1:] + [len(body)])]
chapters = []
for c in chunks:
    m = re.match(r'(?s)<section id="([^"]*)" class="level1">\s*<h1>(.*?)</h1>\s*', c)
    sid, h1 = m.group(1), m.group(2)
    t = re.match(r"(Chapter|Appendix) ([0-9A-Z]+): (.*)", h1, re.S)
    if not t:
        continue                                   # the Markdown's title block
    rest = c[m.end():]
    kw = re.match(r"(?s)<!--\s*keywords:\s*(.*?)\s*-->\s*", rest)
    keywords = ""
    if kw:
        keywords, rest = html.unescape(kw.group(1)), rest[kw.end():]
    preview = ""
    bq = re.match(r"(?s)<blockquote>\s*(.*?)\s*</blockquote>\s*", rest)
    if bq:
        preview = re.sub(r"^<p><strong>Chapter Preview\.</strong>\s*", "<p>", bq.group(1))
        rest = rest[bq.end():]
    chapters.append(dict(id=sid, kind=t.group(1), num=t.group(2), title=t.group(3), keywords=keywords,
                         preview=preview, rest=rest))
assert len(chapters) >= 10, "found %d chapters" % len(chapters)

# Section numbers ("2.1", "A.3") in grey.
num_re = re.compile(r"<(h[23])>((?:\d+|[A-Z])\.\d+)\s")


def page_css(i, ch, heads=True):
    name = "s%d" % i
    head = css_str("%s %s: %s" % (ch["kind"], ch["num"], text(ch["title"])))
    kw = css_str(ch["keywords"])
    run = ('@top-left { content: %s; width: 100%%; vertical-align: bottom; padding-bottom: 3pt;'
           ' margin-bottom: .16in; border-bottom: 4.5pt solid #2a2a2a;'
           ' font: italic 700 10.5pt "Arvo", Georgia, serif; color: #1a1a1a;'
           ' font-variant-numeric: lining-nums; }' % head)
    foot = 'vertical-align: top; padding-top: .2in; font: 8pt "Charter", "Charis SIL", Georgia, serif; color: #1a1a1a;'
    kwb = ('vertical-align: top; padding-top: .19in; font: italic 700 8.5pt "Arvo", Georgia, serif;'
           ' color: #d7262e; font-variant-numeric: lining-nums;')
    return ("@page %s:left { %s @bottom-left { content: counter(page); %s } @bottom-right { content: %s; %s } }\n"
            "@page %s:right { %s @bottom-right { content: counter(page); %s } @bottom-left { content: %s; %s } }\n"
            % (name, run, foot, kw, kwb, name, run, foot, kw, kwb))


TOC_CSS = ('@page toc { @top-left { content: "Table of Contents"; width: 100%; vertical-align: bottom;'
           ' padding-bottom: 3pt; margin-bottom: .2in; border-bottom: 4.5pt solid #2a2a2a;'
           ' font: italic 700 12pt "Arvo", Georgia, serif; color: #1a1a1a; } }\n')


def build(blanks, pages):
    style = TOC_CSS + "".join(page_css(i, ch) for i, ch in enumerate(chapters))
    out = [head.replace("</head>", "<style>\n%s</style>\n</head>" % style)]
    out.append("""
<div class="titlepage">
  <img class="logo" src="img/timex-sinclair-logo.svg" alt="Timex Sinclair">
  <div class="stripes"><i></i><i></i><i></i></div>
  <div class="t1">TS-Pico</div>
  <div class="t2">Mass Storage<br>Interface</div>
  <div class="t3">%s</div>
  <div class="by"><b>The TS-Pico team</b><br>For the Timex Sinclair 2068<br>Version %s · %s</div>
</div>
<div class="colophon">
  <img class="sticker" src="img/ts2068-sticker.svg" alt="TS 2068">
  <p><b>%s</b>, version %s (ROM %s, firmware %s), %s.</p>
  <p>© 2021–2026 the TS-Pico team. This manual is licensed under the Creative Commons
  Attribution 4.0 International licence (CC BY 4.0).</p>
  <p>Timex, Sinclair and Timex Sinclair are trademarks of their respective owners. The TS-Pico
  is a community project, not a product of Timex Computer Corporation or Sinclair Research.</p>
  <p>Website: timex-sinclair-projects.github.io/tspico-firmware-build<br>
  Source and releases: github.com/timex-sinclair-projects/tspico-firmware-build</p>
</div>
""" % (T3, ROM, DATE, TITLE, ROM, ROM, FW, DATE))
    rows, part = [], None
    for ch in chapters:
        if ch["kind"] != part and ch["kind"] == "Appendix":
            rows.append('<tr class="part"><td colspan="3">Appendices</td></tr>')
        part = ch["kind"]
        kw = '<span class="kw">%s</span>' % html.escape(ch["keywords"]) if ch["keywords"] else ""
        rows.append('<tr><td class="kind">%s %s:</td><td class="title"><a href="#%s"><b>%s</b></a>%s</td>'
                    '<td class="page">%s</td></tr>'
                    % (ch["kind"], ch["num"], ch["id"], ch["title"], kw, pages.get(ch["id"], "00")))
    out.append('<div class="toc"><table>%s</table></div>\n' % "\n".join(rows))
    for i, ch in enumerate(chapters):
        if ch["id"] in blanks:
            out.append('<div class="blank"></div>\n')
        preview = ""
        if ch["preview"]:
            preview = ('<div class="preview"><div class="label">Chapter Preview</div>'
                       '<div class="text">%s</div></div>' % ch["preview"])
        rest = num_re.sub(r'<\1><span class="secnum">\2</span>', ch["rest"])
        out.append('<section id="%s" class="level1" style="page: s%d">\n<div class="opener">'
                   '<div class="kind">%s %s</div><div class="top"><h1>%s</h1><div class="num">%s</div></div>'
                   '%s</div>\n%s' % (ch["id"], i, ch["kind"], ch["num"], ch["title"], ch["num"], preview, rest))
    out.append("</body></html>\n")
    return "".join(out)


def starts_of(pdf):
    """The page (1-based) each chapter starts on, from the PDF's named destinations."""
    r = pypdf.PdfReader(pdf)
    d = {k.lstrip("/"): r.get_destination_page_number(v) + 1 for k, v in r.named_destinations.items()}
    missing = [ch["id"] for ch in chapters if ch["id"] not in d]
    assert not missing, "no destination for %s" % missing
    return d, r


# Pass 1: where does each chapter start?
open("book.html", "w", encoding="utf-8").write(build(set(), {}))
chrome("book.html", "pass1.pdf")
first, _ = starts_of("pass1.pdf")
blanks, pages, shift = set(), {}, 0
for ch in chapters:
    p = first[ch["id"]] + shift
    if p % 2 == 0:
        blanks.add(ch["id"])
        shift += 1
        p += 1
    pages[ch["id"]] = p

# Pass 2: the real thing.
open("book.html", "w", encoding="utf-8").write(build(blanks, pages))
chrome("book.html", "body.pdf")
got, body_reader = starts_of("body.pdf")
for ch in chapters:
    assert got[ch["id"]] == pages[ch["id"]], "%s moved: page %d, expected %d" % (
        ch["id"], got[ch["id"]], pages[ch["id"]])
    assert pages[ch["id"]] % 2 == 1

for f in ("front", "back", "mask"):
    chrome(f + ".html", f + ".pdf")
front = pypdf.PdfReader("front.pdf").pages[0]
back = pypdf.PdfReader("back.pdf").pages[0]
mask = pypdf.PdfReader("mask.pdf").pages[0]
for name, p in [("manual", body_reader.pages[0]), ("front cover", front), ("back cover", back), ("mask", mask)]:
    w, h = float(p.mediabox.width), float(p.mediabox.height)
    assert abs(w - W) < 1 and abs(h - H) < 1, "%s is %.1f x %.1f pt, not half letter" % (name, w, h)
n_body = len(body_reader.pages)
assert n_body > 20, "the manual came out as %d pages" % n_body
meta = {"/Author": "The TS-Pico team"}


def one_up(cover):
    """The manual (its page 1 is the title page), with the running heads
    painted out on the opener pages and a bookmark for each chapter, after
    the cover page if there is one. append() keeps the contents' links."""
    w = pypdf.PdfWriter()
    w.append("body.pdf")
    for ch in chapters:
        w.pages[pages[ch["id"]] - 1].merge_page(mask)
    if cover is not None:
        w.insert_page(cover, 0)
    for ch in chapters:
        w.add_outline_item("%s %s: %s" % (ch["kind"], ch["num"], text(ch["title"])),
                           pages[ch["id"]] - (cover is None))
    return w


# One-up: the cover, then the manual.
w = one_up(front)
w.add_metadata(dict(meta, **{"/Title": TITLE}))
w.write("user-manual-half-letter.pdf")

# Booklet: front, blank inside front, the manual, blanks to a multiple of 4,
# blank inside back, back. The manual's page 1 stays a right-hand page.
body = pypdf.PdfReader("user-manual-half-letter.pdf").pages[1:]
blank = lambda: pypdf.PageObject.create_blank_page(width=W, height=H)
pad = (-(len(body) + 4)) % 4
seq = [front, blank()] + list(body) + [blank() for _ in range(pad)] + [blank(), back]
n = len(seq)
w = pypdf.PdfWriter()
for k in range(n // 4):                      # sheet k: front [n-1-2k | 2k], back [2k+1 | n-2-2k]
    for left, right in ((n - 1 - 2 * k, 2 * k), (2 * k + 1, n - 2 - 2 * k)):
        side = pypdf.PageObject.create_blank_page(width=2 * W, height=H)
        side.merge_transformed_page(seq[left], pypdf.Transformation())
        side.merge_transformed_page(seq[right], pypdf.Transformation().translate(W, 0))
        w.add_page(side)
w.add_metadata(dict(meta, **{"/Title": TITLE + " (booklet: letter, saddle stitch)"}))
w.write("user-manual-saddle-stitch-letter.pdf")
assert n % 4 == 0
print("manual %d pages (%d blank before a chapter); one-up %d pages; booklet %d pages (%d blank padding), "
      "%d letter sheets" % (n_body, len(blanks), n_body + 1, n, pad, n // 4))

if not os.environ.get("PRINT"):
    sys.exit(0)

# For printing on demand ($PRINT set): the interior, the manual without the
# cover, padded to an even page count, the same for both printers (its 0.62
# in inside margin is what Lulu recommends for a 61-150 page paperback and
# KDP's minimum is 0.375 in; coil needs no gutter); and a cover for each,
# one sheet: bleed, back, spine, front, bleed, 0.125 in of bleed all round
# (the cover art runs out to it). Lulu's coil cover has no spine; KDP's
# spine is the page count times the paper's thickness, and KDP puts the
# barcode at the foot of the back cover by the spine, so the back's links
# move up out of its way. Spine text only where it fits with 0.125 in clear
# each side (Lulu's figure; KDP's is 1/16 in): about 0.35 in of spine.
BLEED, SAFE = 0.125, 0.125
PAPER = os.environ.get("PAPER") or "white"
KDP_PAGE = {"white": 0.002252, "cream": 0.0025}[PAPER]     # inches per page
w = one_up(None)
if len(w.pages) % 2:
    w.add_blank_page(width=W, height=H)
n_int = len(w.pages)
w.add_metadata(dict(meta, **{"/Title": TITLE}))
w.write("print-interior.pdf")


def page_div(f):
    """The <div class="page ..."> of a filled-in cover page."""
    return re.search(r'(?s)<body>(.*)</body>', open(f, encoding="utf-8").read()).group(1)


def wrap(name, spine, kdp):
    cw, ch = 2 * (BLEED + 5.5) + spine, 8.5 + 2 * BLEED
    spine_text = ""
    room = spine - 2 * SAFE
    if room >= 0.1:
        spine_text = ('<div class="spine-text" style="font-size: %.1fpt">TS-Pico &nbsp; %s</div>'
                      % (min(room * 72 * 0.8, 13), T3))
    doc = """<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="cover.css">
<title>%s</title><style>
@page { size: %.4fin %.4fin; margin: 0; }
.wrap { position: relative; width: %.4fin; height: %.4fin; overflow: hidden; background: #b4b1ab;
  -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.panel { position: absolute; top: 0; width: %.4fin; height: 100%%; overflow: hidden; }
.panel .page { position: absolute; top: %.4fin; overflow: visible; background: none; }
.p-back { left: 0; } .p-back .page { left: %.4fin; }
.p-front { right: 0; } .p-front .page { left: 0; }
.kdp .page.back .links { bottom: 1.7in; }
.spine { position: absolute; top: 0; left: %.4fin; width: %.4fin; height: 100%%;
  display: flex; align-items: center; justify-content: center; }
.spine-text { writing-mode: vertical-rl; white-space: nowrap; font-weight: 700; letter-spacing: .04em;
  text-transform: uppercase; line-height: 1; }
</style></head><body><div class="wrap%s">
<div class="panel p-back">%s</div>
<div class="spine">%s</div>
<div class="panel p-front">%s</div>
</div></body></html>
""" % (TITLE, cw, ch, cw, ch, BLEED + 5.5, BLEED, BLEED, BLEED + 5.5, spine,
       " kdp" if kdp else "", page_div("back.html"), spine_text, page_div("front.html"))
    open(name + ".html", "w", encoding="utf-8").write(doc)
    chrome(name + ".html", name + ".pdf")
    r = pypdf.PdfReader(name + ".pdf")
    p = r.pages[0]
    got = float(p.mediabox.width) / 72, float(p.mediabox.height) / 72
    assert len(r.pages) == 1 and abs(got[0] - cw) < .01 and abs(got[1] - ch) < .01, \
        "%s is %d pages, %.3f x %.3f in, not %.3f x %.3f" % (name, len(r.pages), got[0], got[1], cw, ch)
    print("%s: %.3f x %.3f in, spine %.3f in%s" % (name, cw, ch, spine, ", spine text" if spine_text else ""))


wrap("lulu-coil-cover", 0, False)
wrap("kdp-cover", n_int * KDP_PAGE, True)
print("interior %d pages (KDP: %s paper)" % (n_int, PAPER))
