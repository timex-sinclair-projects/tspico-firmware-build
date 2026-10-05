#!/usr/bin/env python3
"""Step 4: a second look at the tapes LOAD "" didn't settle.

    python3 tools/sd-archive/followup.py [--workers 8]

  code   tapes with no BASIC program (machine code, screens, data):
         LOAD "" CODE instead                          -> results_code.json
  alt    damaged tapes: the zip's TZX, else its WAV, converted; kept when
         every block is sound, then load-tested         -> alt.json, alt/
  run    programs that stop with a report: does RUN start them?
                                                       -> results_run.json
  stock  everything still failing, on a stock 2068: the tape's fault, or
         the TS-Pico's?                                -> results_stock.json

Each part skips what it has already done, like loadtest.py.
"""

import argparse
import hashlib
import os
import zipfile

import common as C
import emulator as E
import plan as PL

FAILING = ("LOADED-ERR", "PARTIAL-ERR", "R-TAPE", "T-RESET", "NOTHING", "LOOP", "MOUNTFAIL")


def job(e, **kw):
    return dict(id=e["sha1"][:12], tap=C.tap_path(e["sha1"]), name=e["name"], **kw)


def alternates(plan, res):
    """For a damaged or failing tape, the same file's TZX or WAV in its zip."""
    os.makedirs(C.work("alt"), exist_ok=True)
    os.makedirs(C.work("conv"), exist_ok=True)
    alt = C.load("alt.json", {})
    for e in plan:
        sid = e["sha1"][:12]
        d = C.read(C.tap_path(e["sha1"]))
        bad = C.damage(d)[0] or C.classify(res[sid]) in ("R-TAPE", "T-RESET", "LOOP", "NOTHING")
        if not bad or sid in alt:
            continue
        alt[sid] = None
        z = zipfile.ZipFile(e["zip_file"])
        stem = os.path.splitext(e["member"])[0]
        for ext, conv in ((".tzx", PL.tzx_to_tap), (".wav", PL.wav_to_tap)):
            for n in z.namelist():
                if os.path.splitext(n)[0] != stem or not n.lower().endswith(ext):
                    continue
                t = conv(z.read(n), hashlib.md5((e["zip_file"] + n).encode()).hexdigest()[:8])
                if t and not C.damage(t)[0] and t != d:
                    p = C.work("alt", sid + ".tap")
                    with open(p, "wb") as f:
                        f.write(t)
                    alt[sid] = dict(tap=p, src=n)
                    break
            if alt[sid]:
                break
    C.save("alt.json", alt)
    return {k: v for k, v in alt.items() if v}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    plan = C.load("plan.json")
    res = C.load("results.json")
    res = {r["id"]: r for r in res}
    missing = [e["name"] for e in plan if e["sha1"][:12] not in res]
    if missing:
        raise SystemExit("%d tapes have no results.json entry yet: run loadtest.py" % len(missing))

    code = [job(e, code=True) for e in plan if not C.has_program(C.read(C.tap_path(e["sha1"])))]
    E.run_parallel(E.TSPico, code, "results_code.json", a.workers)

    alt = alternates(plan, res)
    by_id = {e["sha1"][:12]: e for e in plan}
    ajobs = [dict(id=k, tap=v["tap"], name=by_id[k]["name"], code=not C.has_program(C.read(v["tap"])))
             for k, v in alt.items()]
    E.run_parallel(E.TSPico, ajobs, "results_alt.json", a.workers)

    run = [job(e, run=True) for e in plan if C.classify(res[e["sha1"][:12]]) == "LOADED-ERR"]
    E.run_parallel(E.TSPico, run, "results_run.json", a.workers, fresh=True)

    stock = [job(e) for e in plan if C.classify(res[e["sha1"][:12]]) in FAILING
             and C.has_program(C.read(C.tap_path(e["sha1"])))]     # bytes-only: the code pass
    E.run_parallel(E.Stock, stock, "results_stock.json", a.workers, fresh=True)


if __name__ == "__main__":
    main()
