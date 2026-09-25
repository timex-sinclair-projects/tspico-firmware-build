"""Host-side test for tools/build-flash.py's `build --slot N=FILE` — CPython, no Pico.

Drives the real script as a subprocess (it parses argv at import time)
against a synthetic manifest and a synthetic 512K base image, so it needs
none of the third-party slot contents.

Regression coverage:
  * An override for a slot the manifest doesn't list (the spare slots 4-7)
    used to be silently dropped: the image came out without it, the build
    printed no "<- override" line and exited 0.

Also pinned:
  * overriding a listed slot still works and is reported as an override
  * a file bigger than its slot is refused
  * an override on the second half of a 64K DCK entry is refused
  * a refused build writes no image

Run:  python3 src/test/build_flash_hosttest.py
"""

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
TOOL = os.path.join(REPO, "tools", "build-flash.py")

SLOT = 0x8000
FLASH = SLOT * 16


def setup(tmp):
    """A two-entry manifest (ROM in slot 1 from a file, 64K DCK at 8 from
    base) and a base image whose every slot is filled with its own number."""
    open(os.path.join(tmp, "rom1.bin"), "wb").write(b"\x11" * SLOT)
    man = {"slot_size": SLOT, "fill": 0, "slots": [
        {"slot": 1, "kind": "ROM", "size": SLOT, "name": "rom one",
         "file": "rom1.bin", "crc32": None},
        {"slot": 8, "kind": "DCK", "size": 2 * SLOT, "name": "cart",
         "from_base": True, "crc32": None},
    ]}
    open(os.path.join(tmp, "manifest.json"), "w").write(json.dumps(man))
    open(os.path.join(tmp, "base.rom"), "wb").write(
        b"".join(bytes([0x80 + s]) * SLOT for s in range(16)))
    open(os.path.join(tmp, "test.rom"), "wb").write(b"\xA5" * 0x4000)   # 16K
    open(os.path.join(tmp, "big.rom"), "wb").write(b"\x5A" * (SLOT + 1))


def build(tmp, *slots):
    out = os.path.join(tmp, "out.rom")
    if os.path.exists(out):
        os.remove(out)
    cmd = [sys.executable, TOOL, "build", os.path.join(tmp, "manifest.json"),
           "--base", os.path.join(tmp, "base.rom"), "--out", out]
    for s in slots:
        cmd += ["--slot", s]
    r = subprocess.run(cmd, capture_output=True, text=True)
    img = open(out, "rb").read() if os.path.exists(out) else None
    return r.returncode, r.stdout + r.stderr, img


def check(name, cond, detail=""):
    print("  %s  %s%s" % ("PASS" if cond else "FAIL", name,
                          "" if cond else "\n        " + detail.replace("\n", "\n        ")))
    return cond


def test_listed_slot_override(tmp):
    print("override of a listed slot")
    rc, out, img = build(tmp, "1=" + os.path.join(tmp, "test.rom"))
    ok = check("exit 0", rc == 0, out)
    ok &= check("image written", img is not None and len(img) == FLASH)
    if img:
        ok &= check("slot 1 holds the file, zero-padded",
                    img[SLOT:SLOT + 0x4000] == b"\xA5" * 0x4000
                    and img[SLOT + 0x4000:2 * SLOT] == bytes(0x4000))
        ok &= check("DCK still from base", img[8 * SLOT:10 * SLOT] ==
                    bytes([0x88]) * SLOT + bytes([0x89]) * SLOT)
    ok &= check("reported as override", "slot  1" in out and "<- override" in out, out)
    return ok


def test_spare_slot_override(tmp):
    print("override of an unlisted spare slot")
    rc, out, img = build(tmp, "4=" + os.path.join(tmp, "test.rom"))
    ok = check("exit 0", rc == 0, out)
    ok &= check("image written", img is not None and len(img) == FLASH)
    if img:
        ok &= check("slot 4 holds the file, zero-padded",
                    img[4 * SLOT:4 * SLOT + 0x4000] == b"\xA5" * 0x4000
                    and img[4 * SLOT + 0x4000:5 * SLOT] == bytes(0x4000))
        ok &= check("slot 5 untouched (fill)", img[5 * SLOT:6 * SLOT] == bytes(SLOT))
        ok &= check("slot 1 still from repo", img[SLOT:2 * SLOT] == b"\x11" * SLOT)
    line = [l for l in out.splitlines() if l.startswith("  slot  4")]
    ok &= check("summary lists slot 4 as override",
                len(line) == 1 and "test.rom" in line[0] and "<- override" in line[0], out)
    return ok


def test_oversized_file(tmp):
    print("oversized file")
    ok = True
    for n in ("1", "4"):
        rc, out, img = build(tmp, n + "=" + os.path.join(tmp, "big.rom"))
        ok &= check("slot %s: exit non-zero" % n, rc != 0, out)
        ok &= check("slot %s: no image written" % n, img is None)
        ok &= check("slot %s: says why" % n, "max %d" % SLOT in out, out)
    return ok


def test_dck_collision(tmp):
    print("override colliding with a 64K DCK entry")
    rc, out, img = build(tmp, "9=" + os.path.join(tmp, "test.rom"))
    ok = check("exit non-zero", rc != 0, out)
    ok &= check("no image written", img is None)
    ok &= check("names the DCK at slot 8", "slot 8" in out and "cart" in out, out)
    return ok


def main():
    with tempfile.TemporaryDirectory(prefix="build-flash-") as tmp:
        setup(tmp)
        ok = True
        ok &= test_listed_slot_override(tmp)
        ok &= test_spare_slot_override(tmp)
        ok &= test_oversized_file(tmp)
        ok &= test_dck_collision(tmp)
    print("\n%s" % ("ALL PASS" if ok else "FAILURES"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
