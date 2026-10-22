#!/usr/bin/env python3
"""Run the tour in the emulator (tools/emu: ZEsarUX + the real firmware),
answering its prompts as the presenter would, and record every screen.

    python3 promo/demo/emu_tour.py [--runs 2] [--out DIR] [--screens]

The card is a fresh copy of promo/demo/card plus the repo's "SD card/help",
in a temporary folder (the repo's card folder is never written). The tour is
mounted and loaded as on the 2068: LOAD "tpi:tour.tap", then LOAD "". Each
"Press any key" step is recorded (OUT/runN/wNN.txt and .bmp) and answered
with SPACE. Prompts are answered as the README says: Y at the first Scroll?
(chapter 2), ENTER at Start tape, Y N Y at ERASE's questions, BREAK at
chapter 10's Scroll?, Y at help's. Later runs are typed RUN, as a retake
would be, and their screens compared with the first run's. --stop-at N
BREAKs run 1 at step N (a stopped take: tour/ left behind, a tape mounted),
and run 2 then starts with RUN.

--screens writes the chosen key moments to promo/demo/screens/ as PNG
(with --runs 0 --out DIR: from an earlier run's pictures).
"""

import argparse
import os
import re
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "tools", "emu"))
import session as S                                           # noqa: E402

COUNTER = 64000                         # the tour counts its key waits here
ERASE_ANSWERS = ["y", "n", "y"]          # multi.tap, pics.tap, songs.tap
RUN = 0xF7

# The key moment of each chapter, by run 1's step number ("Press any key"
# count; the README's chapter table lists the steps).
SHOTS = {1: "00-title-card", 3: "01-welcome-info", 5: "02-cat", 9: "03-folders",
         12: "04-copies-new-tape", 19: "05-f-screen-loaded", 23: "06-streams-records",
         26: "07-printer", 30: "08-mounted-tape", 37: "09-erase-asks", 39: "10-break",
         42: "11-help-cat", 45: "12-end-card"}


def card(tmp):
    sd = os.path.join(tmp, "card")
    shutil.copytree(os.path.join(HERE, "card"), sd)
    shutil.copytree(os.path.join(REPO, "SD card", "help"), os.path.join(sd, "help"))
    return sd


def press(s, k):
    if k == "BREAK":                    # CAPS SHIFT + SPACE, held briefly
        s.cmd("send-keys-event 133 1")
        time.sleep(0.1)
        s.cmd("send-keys-event 128 1")
        time.sleep(0.3)
        s.cmd("send-keys-event 128 0")
        s.cmd("send-keys-event 133 0")
    elif k == "ENTER":
        s.key(129)
    else:
        s.key(ord(k), hold=0.25)


def chapter_of(txt):
    """The chapter a screen belongs to: its title card's "n of 12", or the
    number on its header bar."""
    m = re.search(r"(\d+) of 12", txt)
    if m:
        return int(m.group(1))
    w = (txt.splitlines() or [""])[0].split()
    return int(w[0]) if len(w) > 1 and w[0].isdigit() else None


def drive(s, outdir, timeout=180, stop_at=None):
    """Until the tour ends: record and answer. Returns [(kind, n, seconds, text)].
    stop_at: press BREAK at that step instead (a presenter stopping a take)."""
    os.makedirs(outdir, exist_ok=True)
    erase = list(ERASE_ANSWERS)
    n = s.peek(COUNTER, 1)[0]
    log, last, stable, chap = [], None, 0, None
    t0 = tstep = time.time()
    while time.time() - t0 < timeout:
        time.sleep(0.4)
        c = s.peek(COUNTER, 1)[0]
        txt = s.text()
        if c != n:                                           # a "Press any key" step
            time.sleep(0.8)
            txt = s.text()
            n = c
            chap = chapter_of(txt) or chap
            dt = time.time() - tstep
            s.screenshot(os.path.join(outdir, "w%02d.bmp" % n))
            open(os.path.join(outdir, "w%02d.txt" % n), "w").write(txt)
            log.append(("wait", n, round(dt, 1), txt))
            print("  wait %2d  chapter %s  %5.1fs" % (n, chap, dt), flush=True)
            press(s, "BREAK" if n == stop_at else " ")
            tstep = t0 = time.time()
            last = None
            continue
        stable = stable + 1 if txt == last else 0
        last = txt
        lines = [l.strip() for l in txt.splitlines() if l.strip()]
        if stable < 2 or not lines:
            continue
        tail = lines[-1]
        if tail.endswith("9999:1") or (", " in tail and tail[0].isalnum() and tail[1] == " "
                                       and tail.rsplit(", ", 1)[-1].replace(":", "").isdigit()):
            log.append(("end", n, 0, txt))
            return log
        k = None
        if "Scroll?" in tail:
            k = "BREAK" if chap == 10 else "y"
        elif "Start tape" in tail:
            k = "ENTER"
        elif tail.startswith("Erase") and tail.endswith("?"):
            k = erase.pop(0)
        if k:
            log.append(("prompt", k, 0, txt))
            print("  prompt %-28s -> %s" % (tail[-28:], k), flush=True)
            for _ in range(6):                               # a key the 2068 missed: again
                press(s, k)                                  # (README, finding 9)
                t1 = time.time()                             # until the screen shows the answer
                while s.text() == txt and time.time() - t1 < 3:
                    time.sleep(0.3)
                if s.text() != txt:
                    break
                print("    (missed; pressing %s again)" % k, flush=True)
            stable, last, t0 = 0, None, time.time()
    log.append(("timeout", n, 0, s.text()))
    return log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--out", default=None)
    ap.add_argument("--screens", action="store_true")
    ap.add_argument("--stop-at", type=int, help="run 1: BREAK at this step, then RUN for run 2")
    a = ap.parse_args()
    tmp = tempfile.mkdtemp(prefix="tour-")
    out = a.out or os.path.join(tmp, "out")
    logs = []
    s = S.Session(sd=card(tmp), root=os.path.join(tmp, "root")) if a.runs else None
    try:
        for r in range(a.runs):
            print("run %d" % (r + 1), flush=True)
            t = time.time()
            if r == 0:
                s.run(S.LOAD, '"tpi:tour.tap"')
                cmd = bytes([S.LOAD]) + b'""'
            else:
                cmd = bytes([RUN])
            s.wait_editor()
            s.cmd("send-keys-ascii 120 " + " ".join(["97"] * len(cmd)))
            time.sleep(1)
            el = int.from_bytes(s.peek(S.E_LINE, 2), "little")
            s.poke(el, cmd)
            s.key(129)
            log = drive(s, os.path.join(out, "run%d" % (r + 1)), stop_at=a.stop_at if r == 0 else None)
            print("  ended: %s  (%.0f s)" % (log[-1][3].strip().splitlines()[-1], time.time() - t))
            logs.append(log)
    finally:
        if s:
            s.close()
    if a.runs:
        print("firmware traceback:", "Traceback" in open("/tmp/pico_host.out").read())
    for r in range(1 if not a.stop_at else 2, len(logs)):
        a0 = [(k, x[:2] if k == "prompt" else x, t) for k, x, _, t in logs[0]]
        b0 = [(k, x[:2] if k == "prompt" else x, t) for k, x, _, t in logs[r]]
        same = [p[2] == q[2] for p, q in zip(a0, b0)]
        print("run %d vs run 1: %d/%d steps, %d identical screens%s" % (
            r + 1, len(b0), len(a0), sum(same),
            "" if all(same) and len(a0) == len(b0) else "  DIFFER at " +
            str([i for i, v in enumerate(same) if not v][:10])))
        try:                                                 # the pictures, pixel by pixel
            from PIL import Image, ImageChops
            steps = sorted(f for f in os.listdir(os.path.join(out, "run1")) if f.endswith(".bmp"))
            px = [f for f in steps if not os.path.exists(os.path.join(out, "run%d" % (r + 1), f))
                  or ImageChops.difference(
                      Image.open(os.path.join(out, "run1", f)).convert("RGB"),
                      Image.open(os.path.join(out, "run%d" % (r + 1), f)).convert("RGB")).getbbox()]
            print("  pictures: %d/%d the same%s" % (len(steps) - len(px), len(steps),
                                                    "" if not px else "; differ: " + " ".join(px)))
        except ImportError:
            pass
    print("output in", out)
    if a.screens:
        from PIL import Image
        dst = os.path.join(HERE, "screens")
        os.makedirs(dst, exist_ok=True)
        for n, name in sorted(SHOTS.items()):
            im = Image.open(os.path.join(out, "run1", "w%02d.bmp" % n)).convert("RGB")
            im.resize((im.width * 2, im.height * 2), Image.NEAREST).save(
                os.path.join(dst, name + ".png"), optimize=True)
            print("wrote promo/demo/screens/%s.png" % name)


if __name__ == "__main__":
    main()
