#!/usr/bin/env python3
"""Step 3: try every tape on the TS-Pico: LOAD "tpi:name", then LOAD "".

    python3 tools/sd-archive/loadtest.py [--workers 12] [--only REGEX]

Writes results.json (and emu/shots/<id>.bmp) in the work folder. Tapes
already in results.json are skipped, so it can be stopped and started again;
delete results.json to test everything afresh. About 1400 tapes take ~45
minutes with 12 workers on an M-series Mac. Needs ZEsarUX from the
zesarux-tspico fork ($ZESARUX, see tools/emu/README.md).
"""

import argparse
import collections
import re

import common as C
import emulator as E


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--only", help="only tapes whose folder/name matches this regex")
    a = ap.parse_args()
    plan = C.load("plan.json")
    jobs = [dict(id=e["sha1"][:12], tap=C.tap_path(e["sha1"]), name=e["name"]) for e in plan
            if not a.only or re.search(a.only, e["folder"] + "/" + e["name"])]
    res = E.run_parallel(E.TSPico, jobs, "results.json", a.workers)
    print(dict(collections.Counter(C.classify(res[j["id"]]) for j in jobs if j["id"] in res)))


if __name__ == "__main__":
    main()
