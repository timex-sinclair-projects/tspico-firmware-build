#!/usr/bin/env python3
"""Assemble (or take apart) the TS-PICO's 512K flash image.

The flash is 16 slots of 32K, zero-filled where unused. Slot 1 is the TS-PICO's
own 2068 ROM (HOME 16K + EXROM 16K) -- the only slot that changes when we cut a
new ROM. See docs/rom-analysis/FLASH_LAYOUT.md.

    # take an existing production image apart (once, to seed the components)
    ./tools/build-flash.py extract Pico-v15w.rom --out flash/

    # build the shipping image: our slots from the repo, everything else
    # (third-party ROMs and cartridges) carried over from a base image
    ./tools/build-flash.py build flash/manifest.json --base Pico-v15w.rom \
                           --out Pico-v18.rom

    # rebuild with a new 2068 ROM in slot 1
    ./tools/build-flash.py build flash/manifest.json --slot 1=src/rom/TSPICO.ROM \
                           --out Pico-v18.rom

    # check a built image against the manifest's checksums
    ./tools/build-flash.py verify flash/manifest.json Pico-v18.rom
"""
import argparse, json, os, sys, zlib

SLOT_SIZE = 0x8000
SLOTS = 16
FLASH_SIZE = SLOT_SIZE * SLOTS
FILL = 0x00


def crc(b):
    return "%08X" % zlib.crc32(b)


def cmd_extract(args):
    img = open(args.image, "rb").read()
    if len(img) != FLASH_SIZE:
        sys.exit("expected %d bytes, got %d" % (FLASH_SIZE, len(img)))
    os.makedirs(os.path.join(args.out, "slots"), exist_ok=True)
    entries = []
    for s in range(SLOTS):
        blk = img[s * SLOT_SIZE:(s + 1) * SLOT_SIZE]
        if set(blk) == {FILL}:
            entries.append({"slot": s, "file": None, "crc32": None, "note": "empty"})
            continue
        name = "slots/slot%02d.bin" % s
        open(os.path.join(args.out, name), "wb").write(blk)
        entries.append({"slot": s, "file": name, "crc32": crc(blk), "note": ""})
    man = {"source": os.path.basename(args.image), "source_crc32": crc(img),
           "slot_size": SLOT_SIZE, "slots": entries}
    open(os.path.join(args.out, "manifest.json"), "w").write(json.dumps(man, indent=2) + "\n")
    print("extracted %d populated slots to %s" % (
        sum(1 for e in entries if e["file"]), args.out))
    for e in entries:
        if e["file"]:
            print("  slot %2d  %s  crc32 %s" % (e["slot"], e["file"], e["crc32"]))


def assemble(man, root, overrides, base=None):
    """Lay every slot into a 512K image.

    Slots with a "file" come from the repo. Slots marked "from_base" are
    third-party images (ZX Diagnostics, the TK90/95 ROM, the cartridges)
    that we don't vendor -- they're copied out of --base, which is a
    known-good 512K image. Without --base those slots are left as fill
    and the build reports them, so a partial image is never mistaken for
    a shipping one.
    """
    img = bytearray([FILL]) * FLASH_SIZE
    if base:
        blob = open(base, "rb").read()
        if len(blob) != FLASH_SIZE:
            sys.exit("--base %s is %d bytes, expected %d" % (base, len(blob), FLASH_SIZE))
    used = {}
    missing = []
    for e in man["slots"]:
        s = e["slot"]
        size = e.get("size", SLOT_SIZE)
        if e.get("from_base") and s not in overrides:
            if base:
                img[s * SLOT_SIZE:s * SLOT_SIZE + size] = blob[s * SLOT_SIZE:s * SLOT_SIZE + size]
                used[s] = ("base:" + e.get("name", "?"), crc(bytes(
                    img[s * SLOT_SIZE:s * SLOT_SIZE + size])), False, e.get("crc32"))
            else:
                missing.append(e)
            continue
        path = overrides.get(s, os.path.join(root, e["file"]) if e.get("file") else None)
        if not path:
            continue
        blk = open(path, "rb").read()
        if len(blk) > size:
            sys.exit("slot %d: %s is %d bytes, max %d" % (s, path, len(blk), size))
        blk = blk + bytes([FILL]) * (size - len(blk))            # pad short images
        img[s * SLOT_SIZE:s * SLOT_SIZE + size] = blk
        used[s] = (path, crc(blk), s in overrides, e.get("crc32"))
    return bytes(img), used, missing


def cmd_build(args):
    man = json.load(open(args.manifest))
    root = os.path.dirname(os.path.abspath(args.manifest))
    overrides = {}
    for o in args.slot or []:
        n, _, path = o.partition("=")
        overrides[int(n)] = path
    img, used, missing = assemble(man, root, overrides, args.base)
    open(args.out, "wb").write(img)
    print("%s  %d bytes  crc32 %s" % (args.out, len(img), crc(img)))
    for s in sorted(used):
        path, c, is_override, want = used[s]
        label = path[5:] if path.startswith("base:") else os.path.basename(path)
        flag = "  <- override" if is_override else ("" if want in (None, c) else "  CHANGED (manifest said %s)" % want)
        print("  slot %2d  %-40s crc32 %s%s" % (s, label, c, flag))
    for e in missing:
        print("  slot %2d  %-40s NOT INCLUDED (needs --base)" % (
            e["slot"], e.get("name", "?")))
    if missing:
        print("INCOMPLETE: %d third-party slot(s) missing; this image is not "
              "shippable. Pass --base <known-good 512K image>." % len(missing))
        return 2
    if man.get("source_crc32") and not overrides:
        ok = crc(img) == man["source_crc32"]
        print("round-trip vs %s: %s" % (man.get("source"), "MATCH" if ok else "MISMATCH"))
        return 0 if ok else 1
    return 0


def cmd_check(args):
    """Validate the manifest against the slot files in the repo.

    CI runs this on every push: if src/rom/TSPICO.ROM or the ZX ROM
    changes without the manifest's crc32 being updated, the build fails
    rather than silently shipping an image nobody checked.
    """
    man = json.load(open(args.manifest))
    root = os.path.dirname(os.path.abspath(args.manifest))
    bad = 0
    for e in man["slots"]:
        if not e.get("file"):
            continue
        path = os.path.join(root, e["file"])
        size = e.get("size", SLOT_SIZE)
        blk = open(path, "rb").read()
        if len(blk) > size:
            print("  slot %2d  %-40s TOO BIG (%d > %d)" % (e["slot"], e["file"], len(blk), size))
            bad += 1
            continue
        got = crc(blk + bytes([FILL]) * (size - len(blk)))
        ok = got == e.get("crc32")
        bad += not ok
        print("  slot %2d  %-40s %s%s" % (e["slot"], os.path.basename(path),
              "OK " + got, "" if ok else " != manifest %s" % e.get("crc32")))
    print("manifest check: %s" % ("PASS" if not bad else "FAIL"))
    return 1 if bad else 0


def cmd_verify(args):
    man = json.load(open(args.manifest))
    img = open(args.image, "rb").read()
    bad = 0
    if len(img) != FLASH_SIZE:
        sys.exit("expected %d bytes, got %d" % (FLASH_SIZE, len(img)))
    for e in man["slots"]:
        s = e["slot"]
        blk = img[s * SLOT_SIZE:s * SLOT_SIZE + e.get("size", SLOT_SIZE)]
        got = crc(blk)
        if e.get("crc32") is None:
            print("  slot %2d  %-12s %s" % (s, "(no crc32)", "skipped: " + e.get("name", "")))
            continue
        elif e.get("file") is None and not e.get("from_base"):
            ok = set(blk) == {FILL}
            print("  slot %2d  %-12s %s" % (s, "(empty)", "OK" if ok else "NOT EMPTY"))
        else:
            ok = got == e["crc32"]
            print("  slot %2d  %-12s %s%s" % (s, e["crc32"], "OK" if ok else "MISMATCH",
                                              "" if ok else " got " + got))
        bad += not ok
    print("crc32 %s" % crc(img))
    return 1 if bad else 0


p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
sub = p.add_subparsers(dest="cmd", required=True)
e = sub.add_parser("extract"); e.add_argument("image"); e.add_argument("--out", required=True); e.set_defaults(fn=cmd_extract)
b = sub.add_parser("build"); b.add_argument("manifest"); b.add_argument("--out", required=True)
b.add_argument("--slot", action="append", metavar="N=FILE")
b.add_argument("--base", help="known-good 512K image supplying the from_base slots")
b.set_defaults(fn=cmd_build)
c = sub.add_parser("check"); c.add_argument("manifest"); c.set_defaults(fn=cmd_check)
v = sub.add_parser("verify"); v.add_argument("manifest"); v.add_argument("image"); v.set_defaults(fn=cmd_verify)
a = p.parse_args()
sys.exit(a.fn(a) or 0)
