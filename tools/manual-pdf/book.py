#!/usr/bin/env python3
"""Turn pandoc's HTML of the user manual into the two PDFs (run by make.sh).

    book.py WORKDIR

WORKDIR holds manual.html (pandoc, --section-divs), print.css, front.html,
back.html and mask.html with their placeholders filled; the PDFs are written
there. $CHROME is the browser; $FW, $ROM, $DATE go on the title page.

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
  <div class="t3">USER MANUAL</div>
  <div class="by"><b>The TS-Pico team</b><br>For the Timex Sinclair 2068<br>Version %s · %s</div>
</div>
<div class="colophon">
  <img class="sticker" src="img/ts2068-sticker.svg" alt="TS 2068">
  <p><b>TS-Pico User Manual</b>, version %s (ROM %s, firmware %s), %s.</p>
  <p>© 2021–2026 the TS-Pico team. This manual is licensed under the Creative Commons
  Attribution 4.0 International licence (CC BY 4.0).</p>
  <p>Timex, Sinclair and Timex Sinclair are trademarks of their respective owners. The TS-Pico
  is a community project, not a product of Timex Computer Corporation or Sinclair Research.</p>
  <p>Website: timex-sinclair-projects.github.io/tspico-firmware-build<br>
  Source and releases: github.com/timex-sinclair-projects/tspico-firmware-build</p>
</div>
""" % (ROM, DATE, ROM, ROM, FW, DATE))
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

# One-up: the cover, then the manual (its page 1 is the title page), with
# the running heads painted out on the opener pages and a bookmark for each
# chapter. append() keeps the contents' links.
w = pypdf.PdfWriter()
w.append("body.pdf")
for ch in chapters:
    w.pages[pages[ch["id"]] - 1].merge_page(mask)
w.insert_page(front, 0)
for ch in chapters:
    w.add_outline_item("%s %s: %s" % (ch["kind"], ch["num"], text(ch["title"])), pages[ch["id"]])
w.add_metadata(dict(meta, **{"/Title": "TS-Pico User Manual"}))
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
w.add_metadata(dict(meta, **{"/Title": "TS-Pico User Manual (booklet: letter, saddle stitch)"}))
w.write("user-manual-saddle-stitch-letter.pdf")
assert n % 4 == 0
print("manual %d pages (%d blank before a chapter); one-up %d pages; booklet %d pages (%d blank padding), "
      "%d letter sheets" % (n_body, len(blanks), n_body + 1, n, pad, n // 4))
