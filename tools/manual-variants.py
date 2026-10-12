#!/usr/bin/env python3
"""The user manual for one board, from the one source.

docs/manual/user-manual.md is written once for both boards. A passage for
only one of them sits between marker lines, each alone on its line:

    <!-- v2 -->            the TS-Pico 2.x (v2.2) board only
    ...
    <!-- /v2 -->

    <!-- v3 -->            the v3 card only
    ...
    <!-- /v3 -->

This keeps a board's passages and drops the other's, and the marker lines
with them. Markers don't nest and must pair up. GitHub shows the source with
both boards' passages (the markers are HTML comments, invisible there).

Who uses it:
  * tools/manual-pdf/make.sh, with BOARD=v2 (the default: the website and
    the release PDFs) or BOARD=v3 (CI's artifact while the card is
    unreleased);
  * tools/build-site-docs.py, which publishes the v2 manual;
  * src/test/manual_variants_hosttest.py, which checks the markers and that
    the v2 manual says nothing of the v3 card.

Usage: python3 tools/manual-variants.py BOARD [IN [OUT]]
       BOARD is v2 or v3; IN defaults to docs/manual/user-manual.md, OUT to
       standard output.
"""
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(REPO, "docs", "manual", "user-manual.md")
BOARDS = ("v2", "v3")
MARK = re.compile(r"^<!-- (/?)(v2|v3) -->\s*$")


class MarkerError(ValueError):
    pass


def variant(text, board):
    """The text for `board`: its passages kept, the other's dropped, no
    marker lines. MarkerError (with the line number) if they don't pair up
    or nest."""
    if board not in BOARDS:
        raise ValueError("board %r: v2 or v3" % board)
    out, inside = [], None
    for n, line in enumerate(text.split("\n"), 1):
        m = MARK.match(line)
        if m:
            closing, which = m.group(1) == "/", m.group(2)
            if not closing:
                if inside:
                    raise MarkerError("line %d: <!-- %s --> inside <!-- %s -->" % (n, which, inside))
                inside = which
            else:
                if inside != which:
                    raise MarkerError("line %d: <!-- /%s --> with no <!-- %s --> open" % (n, which, which))
                inside = None
            continue
        if inside is None or inside == board:
            out.append(line)
    if inside:
        raise MarkerError("<!-- %s --> never closed" % inside)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out))


def main(argv):
    if len(argv) < 2 or argv[1] not in BOARDS:
        sys.stderr.write(__doc__)
        return 2
    src = argv[2] if len(argv) > 2 else SOURCE
    with open(src, encoding="utf-8") as f:
        text = variant(f.read(), argv[1])
    if len(argv) > 3:
        with open(argv[3], "w", encoding="utf-8") as f:
            f.write(text)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
