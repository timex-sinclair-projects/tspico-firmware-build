#!/usr/bin/env python3
"""Step 5: lay out the card.

    python3 tools/sd-archive/build_card.py OUTDIR

  OUTDIR/TAP/<CATEGORY>[/<COLLECTION>]/<name>.tap   the tapes that load and start
  OUTDIR/help/                                       the help files from "SD card/"
  OUTDIR/catalog.csv                                 every tape: where it is, what
                                                     it is, how to load it, why one
                                                     is left out
  OUTDIR-not-loading/                                the rest, same layout + catalog

On the card: a program that loads and starts (by itself, or after RUN); bytes
that load with LOAD "" CODE; the ECMview pictures, which its slideshow loads.
Left out: damaged tapes, loaders whose code isn't on the tape, and programs
that stop with a report even after RUN.
"""

import collections
import csv
import os
import shutil
import sys

import common as C

ECM = "GRAPHICS/ECMVIEW"


def results(name):
    return {r["id"]: r for r in C.load(name, [])}


def verdict(e, r, tap, code, alt, run, stock):
    """(on the card, how to load it, note)."""
    d = C.read(tap)
    if alt:
        if C.classify(alt) in ("OK", "PARTIAL") or (alt.get("served", 0) >= 2 and C.report(alt) in (None, "0")):
            return True, 'LOAD ""' if C.has_program(C.read(alt["tap"])) else 'LOAD "" CODE', \
                "the archive's .tap is damaged; this is its %s, converted" % os.path.splitext(alt["src"])[1][1:].upper()
    nbad, n = C.damage(d)
    if nbad:
        return False, "", "damaged tape: %d of %d blocks have bad checksums or are cut short" % (nbad, n)
    if not C.has_program(d):
        if e["folder"] == ECM:
            return True, "with ecmvpico.tap", "ECM picture for the ECMview slideshow (ecmvpico.tap)"
        if code and code.get("served", 0) >= 2 and C.report(code) in (None, "0"):
            return True, 'LOAD "" CODE', "machine code, screen or data; no BASIC loader"
        return False, "", 'bytes only, and LOAD "" CODE fails (%s)' % (C.last_line(code and code.get("screen")) or "?")
    k = C.classify(r)
    same = " (same on a stock 2068)" if stock and C.report(stock) == C.report(r) else ""
    if k in ("R-TAPE", "T-RESET", "NOTHING", "MOUNTFAIL", "ERROR", "FIRMWARE-EXC"):
        return False, "", "%s: %s%s" % (k, C.last_line(r.get("screen")), same)
    if k == "LOOP":
        return False, "", "the program loads, then waits for a file that isn't on the tape"
    if r["served"] < 2:
        return False, "", "the 2068 rejects the first block"
    if k in ("OK", "PARTIAL", "PARTIAL-ERR"):
        return True, 'LOAD ""' if C.autoruns(d) else 'LOAD "", then RUN', ""
    if k == "LOADED-ERR":
        if run and run.get("run_err") == 0xFF:
            return True, 'LOAD "", then RUN', "the autostart stops with '%s'; RUN starts it" % C.last_line(r["screen"])
        return False, "", "loads, then stops with '%s', RUN too%s" % (C.last_line(r["screen"]), same)
    return False, "", k


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    out = os.path.abspath(sys.argv[1])
    left = out.rstrip("/") + "-not-loading"
    for d in (out, left):
        if os.path.exists(d):
            raise SystemExit("%s exists: move it away first" % d)
    plan = C.load("plan.json")
    res = results("results.json")
    code, run, stock, ares = (results(n) for n in ("results_code.json", "results_run.json",
                                                    "results_stock.json", "results_alt.json"))
    alt = C.load("alt.json", {})
    desc = C.load("descriptions.json", {})         # describe.py; optional
    rows = []
    for e in plan:
        sid = e["sha1"][:12]
        r = res[sid]
        a = dict(ares[sid], **alt[sid]) if alt.get(sid) and sid in ares else None
        on, how, note = verdict(e, r, C.tap_path(e["sha1"]), code.get(sid), a, run.get(sid), stock.get(sid))
        src = alt[sid]["tap"] if on and a and note.startswith("the archive's") else C.tap_path(e["sha1"])
        dst = os.path.join(out if on else left, "TAP", e["folder"])
        os.makedirs(dst, exist_ok=True)
        shutil.copyfile(src, os.path.join(dst, e["name"]))
        about = desc.get(e["page"], {})
        rows.append(dict(on_card="yes" if on else "no", folder="TAP/" + e["folder"], file=e["name"],
                         title=e["title"], summary=about.get("summary", ""),
                         description=about.get("description", ""), load=how, note=note,
                         original_file=os.path.basename(e["member"]),
                         tags=e["tags"], blocks_loaded="%s of %s" % (r.get("served"), r.get("blocks")),
                         converted_from=e["src"] if e["src"] != "tap" else "",
                         also_listed_as="; ".join(e["also"]), page=e["page"], download=e["url"]))
    shutil.copytree(os.path.join(C.REPO, "SD card", "help"), os.path.join(out, "help"))
    rows.sort(key=lambda x: (x["folder"], x["file"]))
    for d in (out, left):
        with open(os.path.join(d, "catalog.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    on = [r for r in rows if r["on_card"] == "yes"]
    print("on the card: %d   left out: %d" % (len(on), len(rows) - len(on)))
    print(dict(collections.Counter(r["load"] for r in on)))
    print(dict(collections.Counter(r["note"].split(":")[0].split(" (")[0][:50]
                                   for r in rows if r["on_card"] == "no")))


if __name__ == "__main__":
    main()
