"""Host-side check of ROM 2.0 (was the 1.8b "sync" test ROM) -- CPython, no Pico.

src/rom/TSPICO-SYNC.ROM is v1.7 (src/rom/TSPICO.ROM) plus the patches in
src/rom/patches/tspico-sync.asm. This test pins down, byte for byte:

  * the base really is v1.7, and every patch site still holds the v1.7
    instruction the patch expects to replace;
  * nothing outside the patch sites changed;
  * the new code went into space that was free (0xFF) in v1.7;
  * every redirected CALL/JP lands on the routine it should;
  * the report letter for the new error code prints as 'T'.

If sjasmplus is installed, it also rebuilds the ROM into a temp directory and
checks the committed image is exactly what the source produces.

It can't run the Z80 code; behaviour is tested in the ZEsarUX lab and on
hardware.

Run:  python3 src/test/rom_sync_hosttest.py
"""

import os
import shutil
import subprocess
import sys
import tempfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROM_DIR = os.path.join(os.path.dirname(HERE), "rom")
BASE = os.path.join(ROM_DIR, "TSPICO.ROM")
PATCHED = os.path.join(ROM_DIR, "TSPICO-SYNC.ROM")
ASM = os.path.join(ROM_DIR, "patches", "tspico-sync.asm")

V17_CRC = "09D4CA63"
EX = 0x4000                      # file offset of the EXROM half
NEW_CODE = 0x2300                # EXROM address of the new routines
ABORT_BYTE = 0x03

# (half, address, v1.7 bytes, what it becomes)
SITES = [
    ("home", 0x0065, "17", "version marker"),
    ("home", 0x0F13, "11650F CD3F07 AF 111511 CD3F07", "report printer -> EXROM"),
    ("ex", 0x06AA, "C1 C3611A", "BREAK_ABORT -> new abort"),
    ("ex", 0x0479, "CD4605", "key wait"),
    ("ex", 0x1651, "CD9D22", "LPRINT first write"),
    ("ex", 0x16F6, "CD9D22", "COPY first write"),
    ("ex", 0x184C, "C3541A", "BIOS WF_NPH -> JP 1A54h"),
    ("ex", 0x184F, "C37922", "BIOS C_END -> JP 2279h"),
    ("ex", 0x1853, "17", "G_VERS"),
    ("ex", 0x189A, "CD9D22", "SAVE first write"),
    ("ex", 0x18FD, "DD23 1B", "SAVE loop INC IX/DEC DE"),
    ("ex", 0x1998, "CD9D22", "LOAD first write"),
    ("ex", 0x19EF, "DD23 1B", "LOAD loop INC IX/DEC DE"),
    ("ex", 0x1A58, "CD5506", "WAIT_PICO_READY status read"),
    ("ex", 0x1BAA, "CD9D22", "TPI: command first write"),
    ("ex", 0x1C6C, None, "copyright line (26 chars)"),
]


def hexb(s):
    return bytes.fromhex(s.replace(" ", ""))


def off(half, addr):
    return addr + (EX if half == "ex" else 0)


def word(b, i):
    return b[i] | (b[i + 1] << 8)


results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg)


def main():
    base = open(BASE, "rb").read()
    rom = open(PATCHED, "rb").read()

    print("base and output")
    check("%08X" % zlib.crc32(base) == V17_CRC, "TSPICO.ROM is v1.7 (crc32 %s)" % V17_CRC)
    check(len(rom) == 0x8000, "TSPICO-SYNC.ROM is 32K")

    print("v1.7 bytes at every patch site")
    allowed = set()
    for half, addr, orig, what in SITES:
        o = off(half, addr)
        if orig is not None:
            want = hexb(orig)
            check(base[o:o + len(want)] == want,
                  "%s %04X holds %s (%s)" % (half, addr, orig, what))
            allowed.update(range(o, o + len(want)))
        else:
            allowed.update(range(o, o + 26))

    # New code: from NEW_CODE up to the last byte that differs from v1.7
    last = max(i for i in range(len(base)) if base[i] != rom[i])
    new_end = last - EX + 1
    check(all(b == 0xFF for b in base[EX + NEW_CODE:EX + new_end]),
          "new code %04X-%04X was free (0xFF) in v1.7" % (NEW_CODE, new_end - 1))
    allowed.update(range(EX + NEW_CODE, EX + new_end))

    print("nothing else changed")
    stray = [i for i in range(len(base)) if base[i] != rom[i] and i not in allowed]
    check(not stray, "no changes outside the patch sites" +
          ("" if not stray else " (first stray at file offset %04X)" % stray[0]))

    print("redirects")
    ex = rom[EX:]
    in_new = lambda a: NEW_CODE <= a < new_end

    sync = {word(ex, a + 1) for a in (0x189A, 0x1998, 0x1BAA, 0x1651, 0x16F6)}
    check(len(sync) == 1 and all(ex[a] == 0xCD for a in (0x189A, 0x1998, 0x1BAA, 0x1651, 0x16F6)),
          "all five first writes CALL one routine")
    sync_write = sync.pop()
    check(sync_write == NEW_CODE, "that routine is SYNC_WRITE at %04X" % NEW_CODE)
    body = ex[sync_write:sync_write + 6]
    check(body == bytes([0xF5, 0xC5, 0x3E, ABORT_BYTE, 0xD3, 0x0F]),
          "SYNC_WRITE saves AF/BC, then OUT (0Fh),%02Xh" % ABORT_BYTE)
    tail = ex.find(bytes([0xC3, 0x9D, 0x22]), sync_write)
    check(sync_write < tail < sync_write + 16, "SYNC_WRITE ends by JP 229Dh (the original write)")

    step = {word(ex, a + 1) for a in (0x18FD, 0x19EF)}
    check(len(step) == 1 and ex[0x18FD] == ex[0x19EF] == 0xCD and in_new(min(step)),
          "SAVE and LOAD loops CALL one STEP routine")
    s = min(step)
    check(ex[s:s + 3] == hexb("DD23 1B"), "STEP starts with the INC IX / DEC DE it replaced")

    check(ex[0x06AA] == 0xC3 and in_new(word(ex, 0x06AB)) and ex[0x06AD] == 0x00,
          "06AA jumps into new code")
    abort = word(ex, 0x06AB)
    check(ex[abort:abort + 4] == bytes([0x3E, ABORT_BYTE, 0xD3, 0x0F]),
          "BRK_ABORT starts with OUT (0Fh),%02Xh" % ABORT_BYTE)
    rst = ex.find(bytes([0xCF, 0x0C]), abort)
    check(abort < rst < abort + 12, "BRK_ABORT ends with RST 8 / 0Ch (Report D)")

    check(ex[0x0479] == 0xCD and in_new(word(ex, 0x047A)), "key wait CALLs new code")
    kw = word(ex, 0x047A)
    check(bytes([0xC3, 0x46, 0x05]) in ex[kw:kw + 12], "KEYWAIT falls through to POLL_KEYPRESS 0546h")

    check(ex[0x1A58] == 0xCD and in_new(word(ex, 0x1A59)), "WAIT_PICO_READY status read CALLs new code")
    rd = word(ex, 0x1A59)
    check(ex[rd:rd + 3] == hexb("CD5506"), "RD_STATUS starts with CALL 0655h (READ_STATUS)")
    check(bytes([0xCF, 0x1C]) in ex[rd:rd + 16], "RD_STATUS raises RST 8 / 1Ch")

    print("Pico Interface BIOS keeps its carry contract")
    check(ex[0x184C] == 0xC3 and in_new(word(ex, 0x184D)), "184C WF_NPH jumps to a BIOS-only wait in new code")
    bw = word(ex, 0x184D)
    body = ex[bw:bw + 48]
    ret_at = body.find(bytes([0x37, 0xC9]), body.find(bytes([0x33, 0x33])))  # inc sp x2 ; scf ; ret
    bios = body[:ret_at + 2] if ret_at > 0 else body
    check(ret_at > 0, "BIOS wait ends with INC SP / INC SP / SCF / RET (fail path)")
    check(0xCF not in bios, "BIOS wait contains no RST 8 (never raises a report)")
    check(bytes([0xCD, 0x9F, 0x06]) in bios, "BIOS wait keeps v1.7's debounced CHECK_BREAK (069Fh)")
    check(bytes([0x06, 0xE2]) in bios, "BIOS wait keeps v1.7's 226-poll (~19.9 s) budget")
    check(bytes([0x0E, 0x02]) in bios and bytes([0x0E, 0x0C]) in bios and bytes([0x0E, 0x1C]) in bios,
          "failure codes: A = 02h timeout, 0Ch BREAK, 1Ch recovered")
    check(bytes([0x3E, ABORT_BYTE, 0xD3, 0x0F]) in bios, "BIOS BREAK still sends the abort byte")
    check(ex[0x184F] == 0xC3 and in_new(word(ex, 0x1850)), "184F C_END jumps into new code")
    ce = word(ex, 0x1850)
    check(ex[ce:ce + 7] == bytes([0xCD, bw & 0xFF, bw >> 8, 0xD8, 0xC3, 0x7F, 0x22]),
          "BIOS_C_END = CALL BIOS wait / RET C / JP 227Fh (v1.7 read-status tail)")
    check(word(ex, 0x2279 + 1) == 0x1A54, "ROM's own 2279h path still uses WAIT_PICO_READY (reports D/T)")

    print("HOME report printer")
    home = rom[:EX]
    check(home[0x0F12:0x0F16] == hexb("78 22CD5D"), "0F12 keeps LD A,B, then LD (5DCDh),HL")
    target = word(home, 0x0F17)
    check(home[0x0F16] == 0x21 and in_new(target), "0F16 LD HL,<EXROM routine in new code>")
    check(home[0x0F19:0x0F1C] == hexb("CDFC03"), "0F19 CALL 03FCh (returning HOME->EXROM thunk)")
    check(home[0x0F1C:0x0F20] == bytes(4) and home[0x0F20:0x0F24] == base[0x0F20:0x0F24],
          "0F1C-0F1F padded with NOPs; 0F20 onward untouched")
    check(ex[target:target + 2] == bytes([0xFE, 0x1D]), "EX_REPORT_MSG tests A = 1Dh (ERR_NR 1Ch + 1)")
    letter = 0x1C + 1
    letter = letter + 7 if letter >= 0x0A else letter
    check(chr(letter + 0x30) == "T", "HOME prints ERR_NR 1Ch as report letter 'T'")
    msg = ex.find(b"TS-Pico reset, try agai")
    check(msg > 0 and ex[msg + 23] == ord("n") | 0x80, "report text 'TS-Pico reset, try again' ends with bit 7")

    print("version marks")
    check(home[0x0065] == 0x20 and ex[0x1853] == 0x20, "HOME 0065 and G_VERS say 20h: version 2.0")
    line = ex[0x1C6C:0x1C86]
    check(line[-1] & 0x80 and ex[0x1C86] == base[EX + 0x1C86], "copyright line same length, bit 7 on last char")
    print("         banner:%s" % (line[:-1] + bytes([line[-1] & 0x7F])).decode())

    sj = shutil.which("sjasmplus")
    print("rebuild")
    if not sj:
        print("  SKIP  sjasmplus not installed; committed image not rebuilt")
    else:
        with tempfile.TemporaryDirectory() as t:
            shutil.copy(BASE, t)
            r = subprocess.run([sj, "--nologo", "--msg=err", "-Wno-fileorg", ASM],
                               cwd=t, capture_output=True, text=True)
            built = os.path.join(t, "TSPICO-SYNC.ROM")
            ok = r.returncode == 0 and os.path.exists(built)
            check(ok and open(built, "rb").read() == rom,
                  "committed TSPICO-SYNC.ROM matches a fresh build" +
                  ("" if ok else ": " + (r.stdout + r.stderr).strip()))

    print("\ncrc32 of TSPICO-SYNC.ROM: %08X" % zlib.crc32(rom))
    ok = all(results)
    print("%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
