#!/usr/bin/env python3
"""Delete old GitHub Actions artifacts, keeping the newest few of each name.

Artifacts in a private repo count against the organization's Actions
storage. Every push used to leave ~3.5 MB of UF2s, ROMs, taps, manuals and
emulator builds for 30 to 90 days, which came to 4,400 artifacts and 16 GB
by 2026-11-05. Only the newest of each are ever used, so for every artifact
name this keeps:

  * the KEEP newest (default 2), from any branch, and
  * the newest from a successful push run on main, however old.

The second rule is what pages.yml needs: its main/ channel downloads the
newest green main build's tspico-firmware-uf2, tspico-upgrade-uf2 and
tspico-v3-firmware-uf2, and with no Zimodem in the release it takes the
newest green main zimodem.yml run's tspico-zimodem. Zimodem builds only when
its inputs change, so its artifact can be months older than everything else.

Run by .github/workflows/prune-artifacts.yml after each build. By hand
(needs gh, logged in with access to the repo):

  python3 tools/prune-artifacts.py            # list what it would delete
  python3 tools/prune-artifacts.py --delete   # delete it
"""

import argparse
import json
import subprocess
import sys
from collections import defaultdict


def gh_json(path):
    """GET a paginated list endpoint with gh; return the parsed pages."""
    out = subprocess.run(
        ["gh", "api", "--paginate", "--slurp", path],
        check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", default="timex-sinclair-projects/tspico-firmware-build")
    ap.add_argument("--keep", type=int, default=2,
                    help="newest artifacts to keep per name (default 2)")
    ap.add_argument("--delete", action="store_true",
                    help="delete; without it, only list")
    args = ap.parse_args()

    pages = gh_json(f"repos/{args.repo}/actions/artifacts?per_page=100")
    by_name = defaultdict(list)
    for page in pages:
        for a in page["artifacts"]:
            if not a["expired"]:
                by_name[a["name"]].append(a)

    run_ok = {}   # run id -> successful push run on main?

    def green_main(a):
        run = a.get("workflow_run") or {}
        if run.get("head_branch") != "main":
            return False
        rid = run["id"]
        if rid not in run_ok:
            r = json.loads(subprocess.run(
                ["gh", "api", f"repos/{args.repo}/actions/runs/{rid}"],
                check=True, capture_output=True, text=True).stdout)
            run_ok[rid] = (r["event"] == "push" and r["conclusion"] == "success")
        return run_ok[rid]

    doomed = []
    for name, arts in sorted(by_name.items()):
        arts.sort(key=lambda a: a["created_at"], reverse=True)
        keep = {a["id"] for a in arts[:args.keep]}
        for a in arts:
            if green_main(a):
                keep.add(a["id"])
                break
        gone = [a for a in arts if a["id"] not in keep]
        mb = sum(a["size_in_bytes"] for a in gone) / 1e6
        print(f"{name:32} {len(arts):5} live, keep {len(keep)}, "
              f"delete {len(gone):5} ({mb:8.1f} MB)")
        doomed += gone

    total = sum(a["size_in_bytes"] for a in doomed) / 1e6
    print(f"{'total':32} delete {len(doomed)} artifacts, {total:.1f} MB")
    if not args.delete:
        print("(listing only; --delete to delete)")
        return 0

    failed = 0
    for a in doomed:
        r = subprocess.run(
            ["gh", "api", "-X", "DELETE", f"repos/{args.repo}/actions/artifacts/{a['id']}"],
            capture_output=True, text=True)
        if r.returncode:
            failed += 1
            print(f"could not delete {a['id']} ({a['name']}): {r.stderr.strip()}",
                  file=sys.stderr)
    print(f"deleted {len(doomed) - failed}, failed {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
