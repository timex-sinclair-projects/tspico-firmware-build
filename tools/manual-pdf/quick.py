#!/usr/bin/env python3
"""The Quick Start Guide and the Quick Reference Guide as PDFs (run by make.sh).

    quick.py start WORKDIR    quick-start.html -> quick-start-half-letter.pdf
                              and quick-start-saddle-stitch-letter.pdf
    quick.py card WORKDIR     quick-reference.html -> quick-reference-card-letter.pdf

WORKDIR holds pandoc's HTML of the document, the stylesheets and cover pages
with their placeholders filled (print.css, quick.css, card.css, cover.css,
front.html, quick-back.html) and img/. $CHROME is the browser; $ROM, $FW,
$DATE go on the covers.

The Quick Start Guide (docs/manual/quick-start.md) is eight half-letter
pages, two letter sheets as a saddle-stitched booklet: the front cover (the
manual's), six pages, one for each "##" section, and a back cover. A section
that runs over its page fails the build, as does a seventh section.

The Quick Reference Guide (docs/manual/quick-reference.md) is a card after
the one that came with the 2068: one letter sheet, landscape, printed on both
sides (flip on the short edge) and folded in three, each side three tall
panels. The Markdown's "<!-- panel: NAME -->" comments start the panels;
the cover is drawn here. Side 1, the outside, is flap | back | cover; side 2,
the inside, is inside-left | inside-middle | inside-right. Folded, the cover
is in front, the back behind it; open the cover and you see inside-left
beside the flap, open the flap and you see the whole inside. The flap folds
in first, so it and the panel behind it (inside-right) are a little narrower.
A panel that runs over fails the build.
"""
import html, os, re, subprocess, sys
import pypdf

W, H = 5.5 * 72, 8.5 * 72
what, work = sys.argv[1], sys.argv[2]
os.chdir(work)
FW, ROM, DATE = os.environ["FW"], os.environ["ROM"], os.environ["DATE"]
SUFFIX = os.environ.get("SUFFIX", "")      # make.sh: "-v3" for the v3 card


def chrome(src, dst):
    if os.path.exists(dst):
        os.remove(dst)
    subprocess.run([os.environ["CHROME"], "--headless=new", "--disable-gpu", "--no-sandbox",
                    "--no-pdf-header-footer", "--print-to-pdf=" + dst, "file://" + os.path.abspath(src)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    if not (os.path.exists(dst) and os.path.getsize(dst)):
        sys.exit("Chrome produced no " + dst)


def text(h):
    """HTML to plain text."""
    return html.unescape(re.sub(r"<[^>]+>", "", h)).strip()


def parts(name):
    """pandoc's HTML of a document: its head and its body."""
    src = open(name, encoding="utf-8").read()
    return re.match(r"(?s)(.*<body>)(.*)(?=</body>)", src).groups()


def booklet(seq, out, title):
    """Impose half-letter pages two up on letter for saddle stitching: sheet
    k's front is [n-1-2k | 2k], its back [2k+1 | n-2-2k]."""
    n = len(seq)
    assert n % 4 == 0, "%d pages is not a booklet" % n
    w = pypdf.PdfWriter()
    for k in range(n // 4):
        for left, right in ((n - 1 - 2 * k, 2 * k), (2 * k + 1, n - 2 - 2 * k)):
            side = pypdf.PageObject.create_blank_page(width=2 * W, height=H)
            side.merge_transformed_page(seq[left], pypdf.Transformation())
            side.merge_transformed_page(seq[right], pypdf.Transformation().translate(W, 0))
            w.add_page(side)
    w.add_metadata({"/Author": "The TS-Pico team", "/Title": title})
    w.write(out)


def start():
    TITLE = "TS-Pico Quick Start Guide"
    PAGES = 6
    FOOT = ('vertical-align: top; padding-top: .2in; font: 8pt "Charter", "Charis SIL", Georgia, serif;'
            ' color: #1a1a1a;')
    head, body = parts("quick-start.html")
    # The "##" sections, each a page; the "#" title is the cover's.
    secs = re.findall(r'(?s)<section id="([^"]*)" class="level2">\s*<h2>(.*?)</h2>(.*?)</section>', body)
    assert len(secs) == PAGES, "the Quick Start Guide has %d sections, not %d (one per page)" % (len(secs), PAGES)
    # Body page i (1-based) is page i+1 of the booklet: even pages are
    # left-hand pages, with the page number at the outer foot.
    css, out = [], []
    for i, (sid, h2, rest) in enumerate(secs, 1):
        left = (i + 1) % 2 == 0
        side = "left" if left else "right"
        css.append('@page p%d { margin-%s: .5in; margin-%s: .62in; @bottom-%s { content: "%d"; %s } }'
                   % (i, "left" if left else "right", "right" if left else "left", side, i + 1, FOOT))
        out.append('<section id="%s" class="page" style="page: p%d"><div class="opener"><div class="top">'
                   '<h1>%s</h1></div></div>\n%s</section>\n' % (sid, i, h2, rest))
    head = head.replace("</head>", "<style>\n%s\n</style>\n</head>" % "\n".join(css))
    open("guide.html", "w", encoding="utf-8").write(head + "".join(out) + "</body></html>\n")
    chrome("guide.html", "guide.pdf")
    # Each page must open (after its page number) with its own section's title: one that runs over
    # pushes the rest down a page.
    r = pypdf.PdfReader("guide.pdf")
    squash = lambda t: re.sub(r"\W+", "", t).lower()
    titles = [squash(text(h)) for _, h, _ in secs]
    over = [text(secs[i][1]) for i in range(PAGES)
            if i >= len(r.pages) or not re.sub(r"^\d+", "", squash(r.pages[i].extract_text())).startswith(titles[i])]
    assert not over and len(r.pages) == PAGES, \
        "the Quick Start Guide is %d pages, not %d: a section runs over its page (%s)" % (
            len(r.pages), PAGES, ", ".join(over) or "the last")

    chrome("front.html", "front.pdf")
    chrome("quick-back.html", "back.pdf")
    front, back = pypdf.PdfReader("front.pdf").pages[0], pypdf.PdfReader("back.pdf").pages[0]
    for name, p in [("guide", r.pages[0]), ("front cover", front), ("back cover", back)]:
        w_, h_ = float(p.mediabox.width), float(p.mediabox.height)
        assert abs(w_ - W) < 1 and abs(h_ - H) < 1, "%s is %.1f x %.1f pt, not half letter" % (name, w_, h_)

    w = pypdf.PdfWriter()
    w.add_page(front)
    w.append("guide.pdf")
    w.add_page(back)
    for i, (sid, h2, _) in enumerate(secs, 1):
        w.add_outline_item(text(h2), i)
    w.add_metadata({"/Author": "The TS-Pico team", "/Title": TITLE})
    one_up = "quick-start%s-half-letter.pdf" % SUFFIX
    w.write(one_up)
    booklet(pypdf.PdfReader(one_up).pages, "quick-start%s-saddle-stitch-letter.pdf" % SUFFIX,
            TITLE + " (booklet: letter, saddle stitch)")
    print("quick start: %d pages; booklet on 2 letter sheets" % (PAGES + 2))


# The card: panel widths in inches. The flap and the panel behind it fold in
# first, so they are 1/16 in narrower than the others.
NARROW = 3.62
WIDE = (11 - NARROW) / 2
SIDES = [("outside", ["flap", "back", "cover"]),
         ("inside", ["inside-left", "inside-middle", "inside-right"])]


def card():
    TITLE = "TS-Pico Quick Reference Guide"
    head, body = parts("quick-reference.html")
    bits = re.split(r"<!--\s*panel:\s*([a-z-]+)\s*-->", body)
    panels = dict(zip(bits[1::2], bits[2::2]))        # bits[0]: the title, dropped
    want = {p for _, ps in SIDES for p in ps} - {"cover"}
    assert set(panels) == want, "the card's panels are %s, not %s" % (sorted(panels), sorted(want))
    panels["cover"] = """
<div class="cover-title">
  <div class="c1">Timex<br>Sinclair<br>2068</div>
  <div class="c2">TS-Pico<br>Mass Storage<br>Interface</div>
  <div class="rule"></div>
  <div class="c3">Quick Reference Guide</div>
</div>
<div class="cover-foot"><div class="slash"></div>
  <div class="by">by the TS-Pico team<br><span>Version %s · %s</span></div></div>
""" % (ROM, DATE)
    narrow = {"flap", "inside-right"}
    sides = []
    for name, ps in SIDES:
        cells = "".join('<div class="panel %s" data-panel="%s" style="width: %.4fin">%s</div>'
                        % (p, p, NARROW if p in narrow else WIDE, panels[p]) for p in ps)
        sides.append('<div class="side %s">%s</div>' % (name, cells))
    # Marks each panel that runs over (once the fonts are in), for the check below.
    check = """<script>
document.fonts.ready.then(() => {
  const over = [...document.querySelectorAll('.panel')].filter(p => p.scrollHeight > p.clientHeight + 1)
    .map(p => p.dataset.panel + ' by ' + Math.round(p.scrollHeight - p.clientHeight) + 'px');
  document.body.setAttribute('data-overflow', over.join(', ') || 'none');
});
</script>"""
    doc = head + "".join(sides) + check + "</body></html>\n"
    open("card.html", "w", encoding="utf-8").write(doc)
    dom = subprocess.run([os.environ["CHROME"], "--headless=new", "--disable-gpu", "--no-sandbox",
                          "--virtual-time-budget=10000", "--dump-dom", "file://" + os.path.abspath("card.html")],
                         capture_output=True, text=True).stdout
    m = re.search(r'data-overflow="([^"]*)"', dom)
    assert m, "Chrome didn't run the card's overflow check"
    assert m.group(1) == "none", "the Quick Reference Guide runs over: %s" % m.group(1)

    out = "quick-reference-card%s-letter.pdf" % SUFFIX
    chrome("card.html", "card.pdf")
    r = pypdf.PdfReader("card.pdf")
    p = r.pages[0]
    got = float(p.mediabox.width) / 72, float(p.mediabox.height) / 72
    assert len(r.pages) == 2 and abs(got[0] - 11) < .01 and abs(got[1] - 8.5) < .01, \
        "the card is %d pages of %.2f x %.2f in, not 2 of 11 x 8.5" % (len(r.pages), got[0], got[1])
    w = pypdf.PdfWriter()
    w.append("card.pdf")
    w.add_metadata({"/Author": "The TS-Pico team", "/Title": TITLE + " (letter, both sides, folded in three)"})
    w.write(out)
    print("quick reference: 2 letter pages (outside, inside)")


{"start": start, "card": card}[what]()
