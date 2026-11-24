#!/usr/bin/env python3
"""The lower-screen bugs of #446 and #447, end to end in ZEsarUX with the
real firmware (session.py). About 2 minutes.

#446: after INPUT # from an f: stream, the next "scroll?" showed the last
command after it ("scroll?LOAD \"\"") and the lines after it were garbage,
or Report K (Ryan Gray's program, both forms of line 122).
#447: SAVE "f:pic.scr" SCREEN$ over an existing file, answered Y: the
"Start tape" line scrolled the picture up before it was saved.

    python3 tools/emu/lower_emu.py            # TSPICO_ROM=... for another ROM

Needs zmakebas on the PATH or built in tools/zmakebas (make -C tools/zmakebas).
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import session as S                                              # noqa: E402

R446 = """   10 OPEN #4,"f:test.txt","w"
   20 PRINT #4;"Enough to make it scroll...."
   30 CLOSE #4
  100 OPEN #5,"f:test.txt","r"
  110 INPUT #5;a$
  114 CLOSE #5
  118 PRINT \"\"\"\";a$;\"\"\"\"
  120 FOR a=1 TO LEN a$
  122 PRINT a,a$(a)
  124 NEXT a
  199 STOP
"""
R447 = """   10 CLS: PRINT AT 0,0;"TOP LINE";AT 21,0;"BOTTOM LINE"
   20 SAVE "f:pic.scr" SCREEN$
   30 STOP
"""
RUN = 0xF7
results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg, flush=True)


def zmakebas():
    vendored = os.path.join(S.REPO, "tools", "zmakebas", "zmakebas")
    return vendored if os.path.exists(vendored) else shutil.which("zmakebas")


def card(tmp):
    os.makedirs(os.path.join(tmp, "TAP"))
    zm = zmakebas()
    assert zm, "zmakebas not found: make -C tools/zmakebas"
    for name, src in (("r446", R446), ("r446b", R446.replace("PRINT a,a$(a)", "PRINT a$(a),a")),
                      ("r447", R447)):
        bas = os.path.join(tmp, name + ".bas")
        open(bas, "w").write(src)
        subprocess.run([zm, "-a", "10", "-n", name, "-o",
                        os.path.join(tmp, "TAP", name + ".tap"), bas], check=True)
    return tmp


def wait_for(s, text, timeout=20):
    t0 = time.time()
    while text not in s.text() and time.time() - t0 < timeout:
        time.sleep(0.5)
    time.sleep(0.5)
    return s.text()


def main():
    tmp = tempfile.mkdtemp(prefix="lower_emu_")
    with S.Session(sd=card(tmp)) as s:
        print("#446: f: INPUT #, then the scroll? prompt")
        s.run(S.LOAD, '"tpi:r446.tap"')
        s.run(S.LOAD, '""', until="scroll?", timeout=40)
        t = wait_for(s, "scroll?")
        prompt = [l for l in t.splitlines() if "scroll?" in l]
        check(prompt and prompt[0].strip() == "scroll?",
              "the prompt is scroll? alone (%r)" % (prompt[0] if prompt else None))
        s.cmd("send-keys-ascii 120 121")                     # y: go on
        t = wait_for(s, "STOP statement")
        lines = t.splitlines()
        check(any(l.split() == ["22", "o"] for l in lines), "line 22 is '22  o', no garbage")
        check("9 STOP statement" in t, "the program ends with 9 STOP")
        s.key(129)
        time.sleep(1)
        s.run(S.LOAD, '"tpi:r446b.tap"')
        s.run(S.LOAD, '""', until="scroll?", timeout=40)
        s.cmd("send-keys-ascii 120 121")
        t = wait_for(s, "statement")
        check("9 STOP statement" in t and "Invalid color" not in t,
              "PRINT a$(a),a ends with 9 STOP, not K Invalid color")
        s.key(129)
        time.sleep(1)

        print('#447: SAVE "f:pic.scr" SCREEN$ over an existing file')
        s.run(S.LOAD, '"tpi:r447.tap"')
        s.run(S.LOAD, '""', until="Start tape", timeout=40)
        s.key(129)
        time.sleep(3)
        s.run(RUN, until="Replace", timeout=40)
        time.sleep(1)
        s.cmd("send-keys-ascii 120 121")                     # y
        t = wait_for(s, "Start tape")
        lines = t.splitlines()
        check("Start tape" in t, "Y: on to Start tape")
        check(lines and lines[0].strip() == "TOP LINE",
              "the picture did not scroll (row 0: %r)" % (lines[0] if lines else None))
        check("Replace" not in t, "the question is gone from the lower screen")
        s.key(129)
        time.sleep(3)
    shutil.rmtree(tmp, ignore_errors=True)
    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
