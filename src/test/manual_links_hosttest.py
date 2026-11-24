#!/usr/bin/env python3
"""The user manual's section references as links (tools/manual-links.py, #335).

Checks:
  - headings get their ids ({#ch-7}, {#app-D}, {#s7-1}, {#sD-1});
  - references become links: "(7.1)", "See 4.3.", "Chapter 7",
    "Chapters 8 and 9", "Appendix D", "Appendix D.1", "G.9";
  - versions and sizes don't: "version 1.1", "ROM\\n2.5", "the old 1.1",
    "7.4 GB"; nor numbers no heading has, nor code, links or comments;
  - the Contents list links to its chapters;
  - the real manual, for both boards: every link has its heading, no link is
    made inside a version phrase, and there are links to make.

Run:  python3 src/test/manual_links_hosttest.py
"""

import importlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "tools"))
ml = importlib.import_module("manual-links")
mv = importlib.import_module("manual-variants")

FAILS = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else ": " + detail))
    if not ok:
        FAILS.append(name)


DOC = """# TS-Pico User Manual

## Contents

1. Meet the TS-Pico
7. The Virtual Printer

Appendices

- D. Settings

# Chapter 1: Meet the TS-Pico

## 1.1 What is it?

Coming from version 1.1? The old 1.1 update program is gone. Firmware 2.5 needs ROM
2.5. The card holds 7.4 GB. See 4.3. Section 9.9 doesn't exist.

## 4.3 Appending

Print it (7.1), as Chapter 7 says; Chapters 1 and 7 too. `SAVE "tpi:x" CODE 7.1` and
[a link 7.1](#elsewhere) stay. Set it in Appendix D.1, or see Appendix D. Speech, G.9.

<!-- keywords: 7.1 -->

```basic
10 REM see 7.1
```

# Chapter 7: The Virtual Printer

## 7.1 Switching the printer

# Appendix D: Settings

## D.1 config.ini

## G.9 A greeting
"""

made = []
out = ml.link(DOC, made)

check("chapter id", "# Chapter 7: The Virtual Printer {#ch-7}" in out)
check("appendix id", "# Appendix D: Settings {#app-D}" in out)
check("section id", "## 7.1 Switching the printer {#s7-1}" in out)
check("appendix section id", "## D.1 config.ini {#sD-1}" in out)
check("unnumbered heading has no id", "# TS-Pico User Manual\n" in out and "## Contents\n" in out)

check("(7.1)", "Print it ([7.1](#s7-1))" in out)
check("See 4.3.", "See [4.3](#s4-3)." in out)
check("Chapter 7", "as [Chapter 7](#ch-7) says" in out)
check("Chapters 1 and 7", "Chapters [1](#ch-1) and [7](#ch-7) too" in out)
check("Appendix D.1", "[Appendix D.1](#sD-1)" in out)
check("Appendix D", "see [Appendix D](#app-D)." in out)
check("G.9", "Speech, [G.9](#sG-9)." in out)

check("version 1.1", "Coming from version 1.1?" in out)
check("the old 1.1", "The old 1.1 update" in out)
check("ROM across a line break", "ROM\n2.5." in out)
check("Firmware 2.5", "Firmware 2.5 needs" in out)
check("7.4 GB", "7.4 GB" in out)
check("no heading, no link", "Section 9.9 doesn't" in out)
check("inline code", '`SAVE "tpi:x" CODE 7.1`' in out)
check("existing link", "[a link 7.1](#elsewhere)" in out)
check("comment", "<!-- keywords: 7.1 -->" in out)
check("code block", "10 REM see 7.1\n" in out)

check("contents chapter", "7. [The Virtual Printer](#ch-7)" in out)
check("contents appendix", "- D. [Settings](#app-D)" in out)
check("made list", len(made) == 8, "%d links: %r" % (len(made), made))

# The real manual, both boards.
src = open(os.path.join(REPO, "docs", "manual", "user-manual.md"), encoding="utf-8").read()
for board in mv.BOARDS:
    text = mv.variant(src, board)
    made = []
    out = ml.link(text, made)
    have = set(re.findall(r"\{#([\w-]+)\}", out))
    want = set(re.findall(r"\]\(#((?:ch|app|s)[\w-]*)\)", out))
    check("%s: every link has its heading" % board, want <= have, str(sorted(want - have)))
    check("%s: links made" % board, len(made) > 50, "%d" % len(made))
    check("%s: ids unique" % board, len(re.findall(r"\{#[\w-]+\}", out)) == len(have))
    bad = [ctx for _l, _t, ctx in made
           if re.search(r"(?i)\b(version|rom|firmware|release)\s*\[?$", ctx.split(_l)[0])]
    check("%s: no version linked" % board, not bad, repr(bad))

print("\n%d failed" % len(FAILS))
sys.exit(1 if FAILS else 0)
