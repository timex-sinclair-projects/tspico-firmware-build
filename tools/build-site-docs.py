#!/usr/bin/env python3
"""Put the manuals and the programmer's reference into the Jekyll site.

The site (site/) is built by .github/workflows/pages.yml. Before Jekyll runs,
this script copies

    docs/reference/**.md      -> site/reference/   (README.md -> index.md)
    docs/manual/*.md          -> site/manual/
    docs/manual/images/       -> site/manual/images/

so the website always shows the docs as they are on main. The copies are
generated, never committed (.gitignore), and the docs stay where they are:
GitHub renders them as before.

Each page gets front matter (the site's `page` layout, its first heading as
the title, Liquid off) and a line saying where it comes from. Its links are
rewritten for the site:

  * a link to another published doc becomes a link to its page (.md -> .html,
    README.md -> index.html), anchor kept;
  * a link to anything else in the repository (src/..., ROM_CHANGES.md, a
    folder) becomes a link to it on GitHub at main, anchor kept (#L123 too);
  * web links, mailto: and in-page anchors are left alone, and so is
    everything inside code.

Usage: python3 tools/build-site-docs.py [--check]
  --check   build into a temporary folder and report broken links only
"""
import os
import posixpath
import re
import shutil
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GITHUB = "https://github.com/timex-sinclair-projects/tspico-firmware-build"
BRANCH = "main"

# repo path prefix -> site folder
SOURCES = [("docs/reference", "reference"), ("docs/manual", "manual")]
COPY_DIRS = [("docs/manual/images", "manual/images")]

# Lines added under a page's "From ... on GitHub" note. The user manual's
# PDFs are built into the same folder by tools/manual-pdf/make.sh in pages.yml.
EXTRA = {
    "docs/manual/user-manual.md":
        "<p class=\"doc-pdf\">As a PDF: <a href=\"user-manual-half-letter.pdf\">for reading</a> "
        "(5.5 &times; 8.5 in), or <a href=\"user-manual-saddle-stitch-letter.pdf\">as a booklet to "
        "print</a> (letter, double-sided, flip on the short edge; fold and staple).</p>",
}

LINK = re.compile(r"(!?\[(?:[^\[\]]|\[[^\]]*\])*\])\(([^)\s]+)((?:\s+\"[^\"]*\")?)\)")
FENCE = re.compile(r"^\s*(```|~~~)")


def published():
    """repo path of every published .md -> its path in the site (.md)."""
    out = {}
    for src, dst in SOURCES:
        root = os.path.join(REPO, src)
        for d, _dirs, files in os.walk(root):
            for f in files:
                if not f.endswith(".md"):
                    continue
                rel = os.path.relpath(os.path.join(d, f), root).replace(os.sep, "/")
                if src == "docs/manual" and "/" in rel:
                    continue                    # only the two manuals, not examples/
                site = posixpath.join(dst, "index.md" if f == "README.md" else rel)
                out[posixpath.join(src, rel)] = site
    return out


def html_of(site_md):
    return site_md[:-3] + ".html"


def rewrite(target, repo_md, pages):
    """The link target for the site, given the repo path of the page it is in."""
    if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I) or target.startswith("#"):
        return target
    path, frag = (target.split("#", 1) + [""])[:2]
    frag = "#" + frag if frag else ""
    if not path:
        return target
    repo_path = posixpath.normpath(posixpath.join(posixpath.dirname(repo_md), path))
    here = pages[repo_md]
    if repo_path in pages:
        return posixpath.relpath(html_of(pages[repo_path]), posixpath.dirname(here)) + frag
    if repo_path + "/README.md" in pages:                 # a folder that is published
        return posixpath.relpath(html_of(pages[repo_path + "/README.md"]), posixpath.dirname(here)) + frag
    for src, dst in COPY_DIRS:                            # images copied beside the page
        if repo_path == src or repo_path.startswith(src + "/"):
            return posixpath.relpath(dst + repo_path[len(src):], posixpath.dirname(here)) + frag
    kind = "tree" if os.path.isdir(os.path.join(REPO, repo_path)) else "blob"
    if repo_path.startswith(".."):
        return target                                     # outside the repo: leave it
    return "%s/%s/%s/%s%s" % (GITHUB, kind, BRANCH, repo_path, frag)


def convert(text, repo_md, pages):
    site_md = pages[repo_md]
    lines = text.split("\n")
    title = None
    out = []        # finished lines
    run = []        # prose lines waiting for their links to be rewritten
    fenced = False

    def flush():
        # a link can wrap onto the next line, so rewrite a run of prose at once;
        # `code spans` are masked first (a link's text may be code: [`x.py`](../x.py))
        if not run:
            return
        spans = []

        def mask_text(t):
            spans.append(t)
            return "\x00%d\x00" % (len(spans) - 1)

        # A code span may wrap onto the next line; GitHub renders the break as a
        # space, but kramdown reads a line that then starts with "<hex>`" as raw
        # HTML and stops parsing Markdown. So a wrapped span is joined up.
        masked = re.sub(r"(`+)(?!`)((?:(?!\1)(?!\n[ \t]*\n).)*?\S(?:(?!\1)(?!\n[ \t]*\n).)*?)\1",
                        lambda m: mask_text(m.group(0).replace("\n", " ")), "\n".join(run), flags=re.S)
        masked = LINK.sub(lambda m: "%s(%s%s)" % (m.group(1), rewrite(m.group(2), repo_md, pages), m.group(3)),
                          masked)
        out.append(re.sub(r"\x00(\d+)\x00", lambda m: spans[int(m.group(1))], masked))
        del run[:]

    for line in lines:
        if FENCE.match(line):
            flush()
            fenced = not fenced
            out.append(line)
            continue
        if fenced:
            out.append(line)
            continue
        if title is None and line.startswith("# "):
            title = line[2:].strip()
            continue                                      # the layout prints it
        run.append(line)
    flush()
    title = title or posixpath.basename(repo_md)[:-3]
    title = re.sub(r"`([^`]*)`", r"\1", title)
    # An explicit permalink: the site's own `permalink: /updates/:title/` would
    # otherwise turn every page into a folder, and these links name .html files.
    link = "/" + (site_md[:-len("index.md")] if site_md.endswith("index.md") else html_of(site_md))
    front = ["---", "layout: page", "title: %s" % yaml_str(title), "permalink: %s" % link,
             "render_with_liquid: false", "---", ""]
    note = ("<p class=\"doc-source\">From <a href=\"%s/blob/%s/%s\"><code>%s</code></a> on GitHub, "
            "as it is on <code>%s</code>.</p>" % (GITHUB, BRANCH, repo_md, repo_md, BRANCH))
    extra = EXTRA.get(repo_md)
    return "\n".join(front + [note] + ([extra] if extra else []) + [""] + out)


def yaml_str(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def build(site_dir):
    pages = published()
    for _src, dst in SOURCES:
        shutil.rmtree(os.path.join(site_dir, dst), ignore_errors=True)
    for repo_md, site_md in sorted(pages.items()):
        out = os.path.join(site_dir, site_md)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(os.path.join(REPO, repo_md), encoding="utf-8") as f:
            text = f.read()
        with open(out, "w", encoding="utf-8") as f:
            f.write(convert(text, repo_md, pages))
    for src, dst in COPY_DIRS:
        shutil.copytree(os.path.join(REPO, src), os.path.join(site_dir, dst))
    return pages


def check_links(site_dir, pages):
    """Every relative link in the generated pages names a generated file."""
    bad = []
    for site_md in pages.values():
        here = os.path.join(site_dir, site_md)
        text = open(here, encoding="utf-8").read()
        text = re.sub(r"```.*?```", "", text, flags=re.S)
        for m in LINK.finditer(text):
            t = m.group(2)
            if re.match(r"^[a-z][a-z0-9+.-]*:", t, re.I) or t.startswith("#"):
                continue
            path = t.split("#", 1)[0]
            p = os.path.normpath(os.path.join(os.path.dirname(here), path))
            if path.endswith(".html"):
                p = p[:-5] + ".md"
            if not os.path.exists(p):
                bad.append((site_md, t))
    return bad


def main():
    if "--check" in sys.argv:
        tmp = tempfile.mkdtemp()
        pages = build(tmp)
        bad = check_links(tmp, pages)
        shutil.rmtree(tmp)
    else:
        site = os.path.join(REPO, "site")
        pages = build(site)
        bad = check_links(site, pages)
    for page, t in bad:
        print("broken link in %s: %s" % (page, t))
    print("%d pages, %d broken links" % (len(pages), len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
