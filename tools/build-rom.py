#!/usr/bin/env python3
"""Build a patched TS-PICO ROM carrying the native disk-command extension.

Pipeline (see docs/FDD_COMMANDS_DESIGN.md §8):

  1. assemble src/rom/fdd/fddcmd.asm with sjasmplus  -> module binary + symbols
  2. copy the base ROM (src/rom/TSPICO-SYNC.ROM, the shipping ROM 2.0 = v1.7 +
     patches/tspico-sync.asm), verifying its crc32 first
  3. splice the module into the EXROM at its ORG ($3000 -> file $7000),
     after asserting that region is free ($FF)
  4. apply the declarative PATCHES manifest below; every patch states the bytes
     it expects to overwrite, so a ROM that has changed under us fails loudly
  5. write build/TSPICO-fdd.ROM (+ split halves) and print a hunk report,
     asserting that ONLY the intended regions changed

Requires sjasmplus (brew install sjasmplus).

Usage:
    python3 tools/build-rom.py            # build build/TSPICO-fdd.ROM
    python3 tools/build-rom.py --verify   # build, then assert clean hunk set
    python3 tools/build-rom.py --keep     # keep intermediate .bin/.sym
    python3 tools/build-rom.py --rebase   # after a new base ROM merges: re-check
                                          # the patch sites and update BASE_ROM_CRC
"""

import argparse
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import zlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE_ROM = ROOT / "src" / "rom" / "TSPICO-SYNC.ROM"   # ROM 2.0 (flash/manifest.json)
ASM_SRC  = ROOT / "src" / "rom" / "fdd" / "fddcmd.asm"
OUT_DIR  = ROOT / "build"
OUT_ROM  = OUT_DIR / "TSPICO-fdd.ROM"

# --- ROM geometry (see docs/rom-analysis/MEMORY_MAP.md) ----------------------
# The 32K image is HOME (file $0000-$3FFF) + EXROM (file $4000-$7FFF). For each
# bank, file offset == Z80 address, so the EXROM's Z80 $3000 lives at file
# $4000+$3000 = $7000.
EXROM_FILE_BASE = 0x4000
FDD_ORG         = 0x3000          # must match FDD_BASE in fddcmd.asm
BASE_ROM_CRC    = 0x56bd89a4      # guard: rebuilt only against this exact base

# --- Declarative patch manifest ----------------------------------------------
# bank: "home" or "exrom" (selects the file offset); addr: Z80 address in that
# bank; before/after: equal-length hex byte strings. `enabled=False` documents a
# planned patch without applying it yet.
PATCHES = [
    dict(
        name="syntax-offset-table: bare CAT/FORMAT/MOVE/ERASE reach the routine",
        bank="home", addr=0x1946,
        before="d0 c0 c4 c8", after="d2 c2 c6 ca",
        note="Advance each disk command's syntax offset past the '0A 2C' "
             "(string,comma) prefix to the 'class $05 + routine' pair, so a bare "
             "keyword is accepted. Verified in ZEsarUX; see design doc §2/§10.5.",
    ),
    dict(
        name="SAVE/LOAD hook: $01D2 JP SESSION_SETUP -> JP F_HOOK_VEC ($3003)",
        bank="exrom", addr=0x01D2,
        before="c3 73 1a", after="c3 03 30",
        note="The runtime SAVE-ETC's only jump to SESSION_SETUP. F_HOOK sends "
             "tpi:fopen for an \"f:\" name, shortens it and continues at $01D5; "
             "any other name goes on to $1A73 as before. Spec §4a.",
    ),
    dict(
        name="response function $88: the dead $2213 check -> LOWER_VEC ($3006)",
        bank="exrom", addr=0x2213,
        before="fe 86 c0 cd b9 02", after="fe 87 ca 06 30 c9",
        note="$2213's CP 86h follows $21FD's JR NZ, so it can never match (the "
             "duplicate-0x86 bug in PROTOCOL_FROM_ROM.md). Now CP 87h / JP Z / RET: "
             "function $88 = $86's Y/N loop on the lower screen. Every other "
             "function returns exactly as before.",
    ),
    dict(
        name="disk-token hook: $25D6 stub -> EXROM FDD_DISPATCH",
        bank="home", addr=0x25D6,
        before="cd 89 28 20 06 cd 69 25 cd 44 1b c3 67 25",
        after="21 00 30 c3 fc 03 00 00 00 00 00 00 00 00",
        note="Repurpose the 14-byte disk-command stub ($25D6-$25E3, which all of "
             "CAT/FORMAT/MOVE/ERASE fall into) as LD HL,$3000 / JP $03FC — the "
             "returning HOME->EXROM thunk — entering FDD_DISPATCH with the EXROM "
             "paged and B = the token, on BOTH the syntax and runtime pass. The "
             "module tests BIT 7,(IY+1): syntax pass consumes the argument and "
             "returns to accept the statement; runtime pass builds and sends the "
             "TPI command. Nothing external jumps into this region except the "
             "command fall-throughs; $2567 is untouched.",
    ),
]


# --- Anchors: base-ROM code the module calls or jumps into --------------------
# Not patched, only relied on. Each is checked in the base before building (and
# by --rebase), so a new base ROM that moves one fails loudly instead of the
# module jumping into the wrong code. Keep in sync with fddcmd.asm's EQUs.
ANCHORS = [
    dict(name="SESSION_SETUP entry (TPI_SEND repeats $1A73-$1A7D)",
         bank="exrom", addr=0x1A73, bytes="e5 d5 2a 78 5c 23 7c b5 28 fb 22 d1 5d"),
    dict(name="SESSION_NAMED: SESSION_SETUP past the 5-31 char name gate",
         bank="exrom", addr=0x1AAC, bytes="d5 d5 e1 22 d3 5d ed 43 d5 5d"),
    dict(name="CALL_HOME: EXROM->HOME returning thunk",
         bank="exrom", addr=0x03DD, bytes="e5 21 00 ff e5 26 00 e5 e5 d9 cd 99 0f dd e1 c9"),
    dict(name="EXROM RST 8 error restart (Reports C/F from the module)",
         bank="exrom", addr=0x0008, bytes="2a 5d 5c 22 5f 5c"),
    dict(name="H_EXPT_STR: syntax class $0A (string expression)",
         bank="home", addr=0x1BEF, bytes="cd 54 28 fd cb 01 76 c8"),
    dict(name="H_TEST_ROOM",
         bank="home", addr=0x1FBB, bytes="2a 65 5c 09 38 0e"),
    dict(name="SAVE_ETC_BODY: stock SAVE-ETC after SESSION_SETUP's non-command exit",
         bank="exrom", addr=0x01D5, bytes="3a 74 5c a7 28 02 0e 22"),
    dict(name="SESSION_SETUP's non-command exit F_HOOK copies ($1A45)",
         bank="exrom", addr=0x1A45, bytes="d1 e1 01 11 00 c3 d5 01"),
    dict(name="STATUS_REPORT: status-1 in A -> report",
         bank="exrom", addr=0x1BF3, bytes="fb 3d ca 3e 1c 3d ca 39 1c"),
    dict(name="SYNC_WRITE",
         bank="exrom", addr=0x2300, bytes="f5 c5 3e 03 d3 0f cd 0e 23 c1 f1 c3 9d 22"),
    dict(name="Pico Interface BIOS table (TX_A, RX_A, C_END, WF_NPH)",
         bank="exrom", addr=0x1846, bytes="18 25 18 20 18 03 c3 9e 23 c3 cd 23"),
    dict(name="$86's pieces LOWER_LOOP reuses: READ_STATUS, OPEN_STREAM via $04F1, the loop",
         bank="exrom", addr=0x01C3, bytes="cd b9 02 c3 f1 04"),
    dict(name="$04F1: open stream $FE through $0426",
         bank="exrom", addr=0x04F1, bytes="f5 3e fe cd 26 04 f1 c9"),
    dict(name="$86 handler: CALL $01C3, then the loop at $21E6",
         bank="exrom", addr=0x21E3, bytes="cd c3 01 f5 cd 5f 04"),
    dict(name="HOME->EXROM returning thunk the $25D6 hook jumps to",
         bank="home", addr=0x03FC, bytes="e5 21 fc fe"),
]


def check_anchors(base):
    """Messages for every anchor whose bytes differ in base (empty = all good)."""
    bad = []
    for a in ANCHORS:
        want = bytes.fromhex(a["bytes"])
        off = file_offset(a["bank"], a["addr"])
        got = bytes(base[off:off + len(want)])
        if got != want:
            bad.append("%s $%04X (%s) holds %s, the module expects %s"
                       % (a["bank"], a["addr"], a["name"], got.hex(" "), want.hex(" ")))
    return bad


def die(msg):
    sys.exit("build-rom: " + msg)


def need_sjasmplus():
    if shutil.which("sjasmplus") is None:
        die("sjasmplus not found. Install with: brew install sjasmplus")


def assemble(workdir):
    """Assemble the module; return (bytes, symbols dict)."""
    binf = workdir / "fddcmd.bin"
    symf = workdir / "fddcmd.sym"
    # SAVEBIN in the source writes relative to CWD, so run in workdir.
    r = subprocess.run(
        ["sjasmplus", "--nologo", f"--sym={symf}", str(ASM_SRC)],
        cwd=workdir, capture_output=True, text=True,
    )
    if r.returncode != 0:
        die("sjasmplus failed:\n" + r.stdout + r.stderr)
    if not binf.exists():
        die("assembler produced no fddcmd.bin (check SAVEBIN in fddcmd.asm)")
    syms = {}
    for line in symf.read_text().splitlines():
        # "NAME: EQU 0x0000XXXX"
        if ":" in line and "EQU" in line:
            name, _, rest = line.partition(":")
            syms[name.strip()] = int(rest.strip().split()[-1], 16)
    return binf.read_bytes(), syms


def file_offset(bank, addr):
    if bank == "home":
        return addr
    if bank == "exrom":
        return EXROM_FILE_BASE + addr
    die(f"unknown bank {bank!r}")


def rebase():
    """Re-base onto the current BASE_ROM after a new ROM merges.

    Confirms every patch's `before` bytes still match and the module region is
    still free, then rewrites BASE_ROM_CRC in this file. Refuses (non-zero exit)
    if any anchor moved — a moved site means a patch is now wrong and needs a
    human, not a silent crc bump.
    """
    if not BASE_ROM.exists():
        die(f"base ROM missing: {BASE_ROM}")
    base = BASE_ROM.read_bytes()
    new_crc = zlib.crc32(base) & 0xFFFFFFFF
    print(f"current base crc32 = {new_crc:#010x}  (recorded {BASE_ROM_CRC:#010x})")
    if new_crc == BASE_ROM_CRC:
        print("already current — nothing to do.")
        return

    problems = []

    # every patch's `before` must still be present in the (unpatched) base
    for p in PATCHES:
        before_hex = p.get("before")
        if not before_hex:
            continue
        before = bytes.fromhex(before_hex)
        off = file_offset(p["bank"], p["addr"])
        actual = bytes(base[off:off + len(before)])
        state = "enabled" if p.get("enabled", True) else "staged "
        if actual == before:
            print(f"  ok    [{state}] {p['bank']} ${p['addr']:04X}: "
                  f"{before.hex(' ')}")
        else:
            problems.append(
                f"{p['bank']} ${p['addr']:04X} now holds {actual.hex(' ')}, "
                f"patch {p['name']!r} expects {before.hex(' ')}")

    for m in check_anchors(base):
        problems.append("anchor moved: " + m)

    # the module region we own ($3000..$3FFF of the EXROM) must still be free
    mstart = file_offset("exrom", FDD_ORG)
    mend = EXROM_FILE_BASE + 0x4000
    if all(b == 0xFF for b in base[mstart:mend]):
        print(f"  ok    module region EXROM ${FDD_ORG:04X}-$3FFF is free ($FF)")
    else:
        first = next(i for i in range(mstart, mend) if base[i] != 0xFF)
        problems.append(
            f"EXROM ${first - EXROM_FILE_BASE:04X} is no longer $FF — our "
            f"${FDD_ORG:04X} region is occupied in the new base")

    if problems:
        print("\nrebase REFUSED — a patch anchor moved:")
        for m in problems:
            print("  !! " + m)
        die("re-examine the patch manifest against the new ROM before rebasing.")

    src = pathlib.Path(__file__)
    text = src.read_text()
    new_text, n = re.subn(
        r"^BASE_ROM_CRC\s*=\s*0x[0-9a-fA-F]+",
        f"BASE_ROM_CRC    = {new_crc:#010x}",
        text, count=1, flags=re.M)
    if n != 1:
        die("could not locate the BASE_ROM_CRC assignment to update")
    src.write_text(new_text)
    print(f"\nrebased: BASE_ROM_CRC {BASE_ROM_CRC:#010x} -> {new_crc:#010x}")
    print("All patch anchors survived the new base. Run --verify to rebuild.")
    print("NOTE: if you keep the split halves in ROMs/ and romdiff.py's "
          "EXPECT_CRC, update those too.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true",
                    help="assert the built ROM differs from the base only in the "
                         "module region and the enabled patch sites")
    ap.add_argument("--keep", action="store_true",
                    help="keep intermediate fddcmd.bin/.sym next to the output")
    ap.add_argument("--rebase", action="store_true",
                    help="after a new base ROM merges: re-check the patch sites "
                         "and rewrite BASE_ROM_CRC (no build)")
    args = ap.parse_args()

    if args.rebase:
        rebase()
        return

    need_sjasmplus()
    if not BASE_ROM.exists():
        die(f"base ROM missing: {BASE_ROM}")
    base = bytearray(BASE_ROM.read_bytes())
    crc = zlib.crc32(base) & 0xFFFFFFFF
    if crc != BASE_ROM_CRC:
        die(f"base ROM crc32 {crc:#010x} != expected {BASE_ROM_CRC:#010x}. "
            f"Refusing to patch an unexpected image.")

    workdir = pathlib.Path(tempfile.mkdtemp(prefix="buildrom."))
    module, syms = assemble(workdir)
    entry = syms.get("FDD_DISPATCH")
    if entry != FDD_ORG:
        die(f"FDD_DISPATCH is {entry:#06x}, expected FDD_ORG {FDD_ORG:#06x}")

    out = bytearray(base)
    touched = []   # (start, end) file-offset ranges we intend to change

    bad = check_anchors(base)
    if bad:
        die("the base ROM no longer has code the module relies on:\n  " + "\n  ".join(bad))
    print("anchors: %d base-ROM entry points the module uses are where it expects"
          % len(ANCHORS))

    # --- 3. splice the module into free EXROM ---
    mstart = file_offset("exrom", FDD_ORG)
    mend = mstart + len(module)
    if mend > EXROM_FILE_BASE + 0x4000:
        die(f"module overruns EXROM end (${mend-EXROM_FILE_BASE:04X} > $4000)")
    if any(b != 0xFF for b in base[mstart:mend]):
        die(f"EXROM target ${FDD_ORG:04X}..${FDD_ORG+len(module):04X} is not free "
            f"($FF); refusing to overwrite existing code")
    out[mstart:mend] = module
    touched.append((mstart, mend - 1))
    print(f"module: {len(module)} bytes at EXROM ${FDD_ORG:04X} "
          f"(file ${mstart:04X}); entry FDD_DISPATCH=${entry:04X}")

    # --- 4. apply the manifest ---
    for p in PATCHES:
        if not p.get("enabled", True):
            print(f"skip  : {p['name']} (staged, not enabled)")
            continue
        if p["after"] is None:
            die(f"patch {p['name']!r} enabled but has no 'after' bytes")
        before = bytes.fromhex(p["before"])
        after = bytes.fromhex(p["after"])
        if len(before) != len(after):
            die(f"patch {p['name']!r}: before/after length mismatch")
        off = file_offset(p["bank"], p["addr"])
        actual = bytes(out[off:off + len(before)])
        if actual != before:
            die(f"patch {p['name']!r}: {p['bank']} ${p['addr']:04X} holds "
                f"{actual.hex(' ')}, expected {before.hex(' ')}")
        out[off:off + len(after)] = after
        touched.append((off, off + len(after) - 1))
        print(f"patch : {p['bank']} ${p['addr']:04X} {before.hex(' ')} -> "
              f"{after.hex(' ')}  ({p['name']})")

    # --- 5. write outputs ---
    OUT_DIR.mkdir(exist_ok=True)
    OUT_ROM.write_bytes(out)
    (OUT_DIR / "TSPICO-fdd-home.bin").write_bytes(out[0:0x4000])
    (OUT_DIR / "TSPICO-fdd-exrom.bin").write_bytes(out[0x4000:0x8000])
    print(f"\nwrote {OUT_ROM.relative_to(ROOT)}  "
          f"crc32={zlib.crc32(out) & 0xFFFFFFFF:#010x}  size={len(out)}")

    # hunk report vs base
    diffs = [i for i in range(len(base)) if base[i] != out[i]]
    hunks = []
    for i in diffs:
        if hunks and i - hunks[-1][1] <= 8:
            hunks[-1][1] = i
        else:
            hunks.append([i, i])
    print(f"\nchanged {len(diffs)} bytes in {len(hunks)} hunk(s) vs base:")
    for s, e in hunks:
        bank = "HOME " if s < EXROM_FILE_BASE else "EXROM"
        za = s if s < EXROM_FILE_BASE else s - EXROM_FILE_BASE
        print(f"  {bank} ${za:04X}-${za + (e - s):04X} ({e - s + 1} B)")

    if args.verify:
        allowed = set()
        for s, e in touched:
            allowed.update(range(s, e + 1))
        stray = [i for i in diffs if i not in allowed]
        if stray:
            die(f"verify FAILED: {len(stray)} byte(s) changed outside the "
                f"module/patch regions, first at file ${stray[0]:04X}")
        print("\nverify OK: only the module region and enabled patches changed.")

    if args.keep:
        shutil.copy(workdir / "fddcmd.bin", OUT_DIR / "fddcmd.bin")
        if (workdir / "fddcmd.sym").exists():
            shutil.copy(workdir / "fddcmd.sym", OUT_DIR / "fddcmd.sym")
    shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    main()
