#!/usr/bin/env python3
"""The user manual's two boards (tools/manual-variants.py).

docs/manual/user-manual.md holds both boards' passages; <!-- v2 --> and
<!-- v3 --> marker lines fence the ones for one board. Checks:
  - variant() keeps a board's passages, drops the other's and every marker,
    and refuses markers that nest or don't pair up;
  - the real manual builds for both boards, each with every chapter and
    appendix it should have and no marker left;
  - the v2 manual (the published one: the website and the release PDFs)
    says nothing of the v3 card while the card is unreleased;
  - build-site-docs.py publishes the v2 variant.

Run:  python3 src/test/manual_variants_hosttest.py
"""

import importlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "tools"))
mv = importlib.import_module("manual-variants")

FAILS = []


def check(ok, what):
    print(("  ok   " if ok else "  FAIL ") + what)
    if not ok:
        FAILS.append(what)


def refused(text):
    try:
        mv.variant(text, "v2")
    except mv.MarkerError:
        return True
    return False


def main():
    print("variant()")
    src = "a\n<!-- v2 -->\nold\n<!-- /v2 -->\n<!-- v3 -->\nnew\n<!-- /v3 -->\nb\n"
    check(mv.variant(src, "v2") == "a\nold\nb\n", "v2: its passage kept, v3's and the markers gone")
    check(mv.variant(src, "v3") == "a\nnew\nb\n", "v3: the other way round")
    check(refused("<!-- v2 -->\n<!-- v3 -->\n<!-- /v3 -->\n<!-- /v2 -->"), "nested markers: refused")
    check(refused("<!-- v2 -->\nx"), "an unclosed marker: refused")
    check(refused("x\n<!-- /v3 -->"), "a closing marker with none open: refused")
    check(mv.variant("a\n\n<!-- v3 -->\nx\n<!-- /v3 -->\n\nb", "v2") == "a\n\nb",
          "a dropped passage leaves no run of blank lines")

    print("the user manual")
    with open(mv.SOURCE, encoding="utf-8") as f:
        text = f.read()
    v2, v3 = mv.variant(text, "v2"), mv.variant(text, "v3")
    for name, out in (("v2", v2), ("v3", v3)):
        check(not mv.MARK.search(out) and not re.search(r"<!-- /?v[23] -->", out),
              "%s: no marker left" % name)
        chapters = re.findall(r"^# Chapter (\d+):", out, re.M)
        check(chapters == [str(n) for n in range(1, len(chapters) + 1)] and len(chapters) >= 11,
              "%s: chapters 1-%d, in order" % (name, len(chapters)))
    apps = lambda out: re.findall(r"^# Appendix ([A-Z]):", out, re.M)
    check(apps(v2) == list("ABCDE"), "v2: appendices A-E (%s)" % "".join(apps(v2)))
    check(apps(v3)[:6] == list("ABCDEF"), "v3: appendices A-F (%s)" % "".join(apps(v3)))
    hits = [l for l in v2.split("\n") if re.search(r"\bv3\b|RP2350|Appendix F|ESP32|Zimodem", l, re.I)]
    check(not hits, "v2: nothing about the v3 card (%r)" % hits[:3])

    print("the website")
    site = importlib.import_module("build-site-docs")
    check(site.VARIANTS.get("docs/manual/user-manual.md") == "v2", "build-site-docs publishes the v2 manual")
    import fnmatch
    imgs = os.listdir(os.path.join(REPO, "docs", "manual", "images"))
    kept = [f for f in imgs if not any(fnmatch.fnmatch(f, p) for p in site.COPY_IGNORE)]
    check("info-v3.png" not in kept and "info.png" in kept,
          "the site copies the v2 pictures, not the v3 manual's (*-v3.*)")
    for name, out in (("v2", v2), ("v3", v3)):
        refs = set(re.findall(r"\(images/([^)]+)\)", out))
        v3_refs = sorted(r for r in refs if "-v3." in r)
        check(all(os.path.exists(os.path.join(REPO, "docs", "manual", "images", r)) for r in refs)
              and v3_refs == ([] if name == "v2" else ["info-v3.png"]),
              "%s: every picture exists; -v3 pictures %s" % (name, v3_refs))

    print()
    if FAILS:
        print("%d FAILED" % len(FAILS))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
