#!/usr/bin/env python3
"""Make the user manual's section references links (#335).

The manual refers to its own parts by number: "(10.1)", "See 4.3.",
"Chapter 7", "Appendix D", "Appendix D.1", "G.9". The source stays as it is
written, plain text, so GitHub shows it unchanged. This runs on the copy that
is built, after tools/manual-variants.py has picked one board's passages:

  * every numbered heading gets an id of its own, written after it as
    {#id} (pandoc reads it with -f gfm+attributes, kramdown as is):

        # Chapter 7: The Virtual Printer      {#ch-7}
        # Appendix D: Settings, ...           {#app-D}
        ## 7.1 Switching the printer          {#s7-1}
        ## D.1 config.ini                     {#sD-1}

  * every reference to one of them becomes a link to it: "(10.1)" is
    "([10.1](#s10-1))", "Chapter 7" is "[Chapter 7](#ch-7)", "Appendix D.1"
    is "[Appendix D.1](#sD-1)";
  * the Contents list's entries link to their chapters.

A number is a reference only if a heading has it, and not when it is a
version or a size: after "version", "ROM", "firmware", "release" and the
like, or before "GB"/"MB". Code (fenced or `inline`), links already there,
headings, HTML comments and raw HTML lines are left alone.

Who uses it: tools/manual-pdf/make.sh and tools/build-site-docs.py, for
the user manual only. src/test/manual_links_hosttest.py checks it.

Usage: python3 tools/manual-links.py [IN [OUT]]   (standard input/output)
       python3 tools/manual-links.py --list [IN]  every link it makes, with
                                                  its context, to check
"""
import re
import sys

CHAPTER = re.compile(r"^# (Chapter (\d+)|Appendix ([A-G])):")
SECTION = re.compile(r"^##+ ((\d+|[A-G])\.(\d+))\s")
# Words that make the number after them a version or a value, not a section.
NOT_AFTER = {"version", "versions", "rom", "roms", "firmware", "release", "releases",
             "micropython", "python", "pandoc", "v", "beta", "board", "upgrade", "old"}
NOT_BEFORE = re.compile(r"\s*(GB|MB|KB|K\b|V\b|in\b|%|x\b|×)")

NUM = re.compile(r"(?<![\w.$])(\d{1,2}|[A-G])\.(\d{1,2})(?![\w]|\.\d)")
CHREF = re.compile(r"\b(Chapters?) (\d{1,2})\b((?: (?:and|or|to) \d{1,2}\b)?)")
APREF = re.compile(r"\b(Appendix|Appendices) ([A-G])(?:\.(\d{1,2}))?\b((?: (?:and|or) [A-G]\b)?)")


def ids(lines):
    """The id of every numbered heading: {"ch:7": "ch-7", "s:7.1": "s7-1", ...}."""
    out = {}
    for line in lines:
        m = CHAPTER.match(line)
        if m:
            if m.group(2):
                out["ch:" + m.group(2)] = "ch-" + m.group(2)
            else:
                out["app:" + m.group(3)] = "app-" + m.group(3)
            continue
        m = SECTION.match(line)
        if m:
            out["s:" + m.group(1)] = "s%s-%s" % (m.group(2), m.group(3))
    return out


def heading_id(line, table):
    m = CHAPTER.match(line)
    if m:
        return table["ch:" + m.group(2)] if m.group(2) else table["app:" + m.group(3)]
    m = SECTION.match(line)
    if m:
        return table["s:" + m.group(1)]
    return None


# Pieces of a line that are never touched: inline code, links and images,
# autolinks and inline HTML tags.
PROTECT = re.compile(r"(`+)[^`]*?\1|!?\[[^\]]*\]\([^)]*\)|<[^>\n]*>")


def last_word(text):
    m = re.search(r"([A-Za-z]+)\W*$", text)
    return m.group(1).lower() if m else ""


def link_text(text, before, table, made):
    """Links in one stretch of prose. before: the prose just before it
    (the line above too), to see the word in front of a number."""
    def sub(rx, fn, s):
        out, at = [], 0
        for m in rx.finditer(s):
            r = fn(m, s)
            if r is None:
                continue
            out.append(s[at:m.start()])
            out.append(r)
            at = m.end()
        out.append(s[at:])
        return "".join(out)

    def note(label, target, s, m):
        made.append((label, target, (before + s)[max(0, len(before) + m.start() - 30):
                                                len(before) + m.end() + 10].replace("\n", " ")
                     .replace("\x00", "")))
        return "[%s](#%s)" % (label, target)

    # Placeholders keep a link already made from being linked again.
    held = []

    def hold(s):
        held.append(s)
        return "\x00%d\x00" % (len(held) - 1)

    def chapter(m, s):
        word, n, more = m.group(1), m.group(2), m.group(3)
        t = table.get("ch:" + n)
        if not t:
            return None
        out = hold(note("%s %s" % (word, n), t, s, m)) if word == "Chapter" else \
            word + " " + hold(note(n, t, s, m))
        if more:
            n2 = more.split()[-1]
            t2 = table.get("ch:" + n2)
            out += more[:-len(n2)] + (hold(note(n2, t2, s, m)) if t2 else n2)
        return out

    def appendix(m, s):
        word, x, sec, more = m.groups()
        if sec:
            t = table.get("s:%s.%s" % (x, sec))
            label = "%s %s.%s" % (word, x, sec)
        else:
            t = table.get("app:" + x)
            label = "%s %s" % (word, x)
        if not t:
            return None
        if word == "Appendices":
            out = word + " " + hold(note(x, t, s, m))
        else:
            out = hold(note(label, t, s, m))
        if more:
            x2 = more.split()[-1]
            t2 = table.get("app:" + x2)
            out += more[:-1] + (hold(note(x2, t2, s, m)) if t2 else x2)
        return out

    def number(m, s):
        key = "s:%s.%s" % (m.group(1), m.group(2))
        t = table.get(key)
        if not t:
            return None
        if last_word(before + s[:m.start()]) in NOT_AFTER:
            return None
        if NOT_BEFORE.match(s[m.end():]):
            return None
        return hold(note(m.group(0), t, s, m))

    text = sub(CHREF, chapter, text)
    text = sub(APREF, appendix, text)
    text = sub(NUM, number, text)
    return re.sub("\x00(\\d+)\x00", lambda m: held[int(m.group(1))], text)


def link(text, made=None):
    """The manual with its headings' ids and its references linked."""
    made = [] if made is None else made
    lines = text.split("\n")
    table = ids(lines)
    out = []
    fence = None
    in_comment = False
    in_contents = False
    prev = ""
    for line in lines:
        s = line.strip()
        if fence:
            out.append(line)
            if s.startswith(fence):
                fence = None
            continue
        m = re.match(r"^\s*(```+|~~~+)", line)
        if m:
            fence = m.group(1)
            out.append(line)
            continue
        if in_comment or s.startswith("<!--"):
            in_comment = "-->" not in s
            out.append(line)
            continue
        if line.startswith("#"):
            in_contents = line.startswith("## Contents")
            hid = heading_id(line, table)
            out.append(line + " {#%s}" % hid if hid else line)
            prev = ""
            continue
        if in_contents:
            m = re.match(r"^(\d+)\. (.+)$", line) or re.match(r"^- ([A-G])\. (.+)$", line)
            if m:
                key = ("ch:" if m.group(1).isdigit() else "app:") + m.group(1)
                if key in table:
                    line = line[:m.start(2)] + "[%s](#%s)" % (m.group(2), table[key])
            out.append(line)
            continue
        if s.startswith("<") and not s.startswith("<!--"):
            out.append(line)          # a raw HTML line
            prev = ""
            continue
        parts, at = [], 0
        for p in PROTECT.finditer(line):
            parts.append(link_text(line[at:p.start()], prev + " " + line[:at], table, made))
            parts.append(p.group(0))
            at = p.end()
        parts.append(link_text(line[at:], prev + " " + line[:at], table, made))
        out.append("".join(parts))
        prev = line if s else ""
    return "\n".join(out)


def main(argv):
    listing = argv[:1] == ["--list"]
    if listing:
        argv = argv[1:]
    text = open(argv[0], encoding="utf-8").read() if argv else sys.stdin.read()
    made = []
    result = link(text, made)
    if listing:
        for label, target, ctx in made:
            print("%-14s #%-8s %s" % (label, target, ctx))
        print("%d links" % len(made), file=sys.stderr)
        return
    if len(argv) > 1:
        open(argv[1], "w", encoding="utf-8").write(result)
    else:
        sys.stdout.write(result)


if __name__ == "__main__":
    main(sys.argv[1:])
