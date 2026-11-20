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

The result is ROM 2.4, the previous release: it is committed as
src/rom/TSPICO-24.ROM, and CI fails if that file differs from a fresh build.
After changing the module or the patches:
    python3 tools/build-rom.py --verify
    cp build/TSPICO-fdd.ROM src/rom/TSPICO-24.ROM

Requires sjasmplus (brew install sjasmplus).

Usage:
    python3 tools/build-rom.py            # build build/TSPICO-fdd.ROM
    python3 tools/build-rom.py --verify   # build, then assert clean hunk set
    python3 tools/build-rom.py --keep     # keep intermediate .bin/.sym
    python3 tools/build-rom.py --rebase   # after a new base ROM merges: re-check
                                          # the patch sites and update BASE_ROM_CRC
    python3 tools/build-rom.py --megabank --verify
                                          # ROM 2.5, the release ROM (below)

ROM 2.5, the release ROM and the slot-1 image (--megabank): the same build with -DMEGABANK, which adds
the TS-2068 Megabank's boot reset, SAVE/LOAD "r:name" and the mover after the
2.4 module (fddcmd.asm), plus MB_PATCHES and the `mb_after` bytes below. It
carries the version marker 25h ("v2.5") so the firmware can tell it from 2.4,
and is committed as src/rom/TSPICO-25.ROM (flash/manifest.json slot 1; CI
checks it too). It runs on a 2068 with or without the board. After a change:
    python3 tools/build-rom.py --megabank --verify
    cp build/TSPICO-25.ROM src/rom/TSPICO-25.ROM
and update slot 1's crc32 in flash/manifest.json. Megabank spec phase 4.
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
OUT_MB   = OUT_DIR / "TSPICO-25.ROM"           # --megabank

# --- ROM geometry (see docs/rom-analysis/MEMORY_MAP.md) ----------------------
# The 32K image is HOME (file $0000-$3FFF) + EXROM (file $4000-$7FFF). For each
# bank, file offset == Z80 address, so the EXROM's Z80 $3000 lives at file
# $4000+$3000 = $7000.
EXROM_FILE_BASE = 0x4000
FDD_ORG         = 0x3000          # must match FDD_BASE in fddcmd.asm
RCH_ORG         = 0x2400          # --megabank: the r: channels (rchan.asm), RCH_BASE
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
        mb_after="c3 61 3a 00 00 00",                 # JP FN_EXT: 88h as before, 89h the mover
        note="$2213's CP 86h follows $21FD's JR NZ, so it can never match (the "
             "duplicate-0x86 bug in PROTOCOL_FROM_ROM.md). Now CP 87h / JP Z / RET: "
             "function $88 = $86's Y/N loop on the lower screen. Every other "
             "function returns exactly as before.",
    ),
    dict(
        name="disk-token hook: $25D6 stub -> EXROM FDD_DISPATCH",
        bank="home", addr=0x25D6,
        before="cd 89 28 20 06 cd 69 25 cd 44 1b c3 67 25",
        after="f3 21 00 30 cd fc 03 fb d0 e9 06 ff 18 f2",
        note="Repurpose the 14-byte disk-command stub ($25D6-$25E3, which all of "
             "CAT/FORMAT/MOVE/ERASE fall into) as DI / LD HL,$3000 / CALL $03FC / "
             "EI / RET NC / JP (HL) -- the returning HOME->EXROM thunk, under DI "
             "for the reason given on the $1488 patch -- entering FDD_DISPATCH "
             "with the EXROM paged and B = the token, on BOTH the syntax and "
             "runtime pass. The module tests BIT 7,(IY+1): syntax pass consumes "
             "the argument and returns to accept the statement; runtime pass "
             "builds and sends the TPI command. It returns NC, except a bare COPY "
             "at run time: C with HL = $0A02, HOME's COPY (the printer). $25E0 is "
             "COPY's routine (the $19D7 patch): LD B,FFh / JR $25D6. LIST and "
             "RESTORE come straight here (the $19AF and $19D0 patches) with no "
             "token in B; the module tells them by T-ADDR, and hands their other "
             "forms back the same way: C with HL = $1545 (LIST) or $1E9D "
             "(RESTORE). Nothing external jumps into this region except the "
             "command fall-throughs; $2567 is untouched.",
    ),
    dict(
        name="COPY's parameter list: $19D7 class 00 / $0A02 -> class 05 / $25E0",
        bank="home", addr=0x19D7,
        before="00 02 0a", after="05 e0 25",
        note="Class 00 accepted only a bare COPY (CHECK-END on the syntax pass). "
             "Class 05 hands the rest of the statement to the routine on both "
             "passes, so COPY \"a\" TO \"b\" reaches the module (FDD_COPY), as "
             "the $1946 patch did for CAT/FORMAT/MOVE/ERASE. Both classes leave "
             "T-ADDR at $19D8, so the bare COPY the module hands back to $0A02 "
             "still reads as COPY (D8h) in the printer path at EXROM $1781.",
    ),
    dict(
        name="LIST's parameter list: $19AF class 05 / $1545 -> class 05 / $25D6",
        bank="home", addr=0x19AF,
        before="05 45 15", after="05 d6 25",
        note="LIST \"name\" shows a file (FDD_LIST, tpi:list). LIST was class "
             "05 already, so only the routine changes: the hook, which the "
             "module answers for a string and hands back to $1545 for LIST, "
             "LIST n and LIST #n on both passes. T-ADDR stays $19B0, which is "
             "how the module knows the statement.",
    ),
    dict(
        name="RESTORE's parameter list: $19D0 class 03 / $1E9D -> class 05 / $25D6",
        bank="home", addr=0x19D0,
        before="03 9d 1e", after="05 d6 25",
        note="RESTORE #n rewinds an OPEN # file (FDD_RESTORE). Class 03 (an "
             "optional number) refused the #. Class 05 hands the statement to "
             "the module, which does class 03's part itself for RESTORE and "
             "RESTORE n (the number through $1BE5, or 0 through $1C51) and "
             "hands over to $1E9D at run time. T-ADDR is $19D1.",
    ),
    dict(
        name="channel trampolines, stubs and the error trap in the dead $1488-$14BC",
        bank="home", addr=0x1488,
        before="cd 74 13 30 e1 c1 0b 78 b1 20 db d5 eb cd b9 25 "
               "eb 46 0e 88 23 23 5e 23 56 62 6b 3a cb 5c 5f 16 "
               "00 d5 e5 c5 2a 65 5c 4e 2b 22 65 5c 06 00 03 03 "
               "c5 01 00 00 c5",
        after="f3 21 0f 30 cd fc 03 fb d8 c3 65 14 "   # $1488 OPEN: EXROM, else $1465
              "f3 21 12 30 cd fc 03 fb d8 c3 be 13 "   # $1494 CLOSE: EXROM, else $13BE
              "f3 21 09 30 cd fc 03 fb c9 "            # $14A0 an F record's output
              "f3 21 0c 30 cd fc 03 fb c9 "            # $14A9 its input
              "e1 22 ce 65 e1 22 3d 5c f9 fb c9",      # $14B2 GUARDED's error trap
        mb_after="f3 21 0f 30 cd fc 03 fb d8 c3 65 14 "
                 "f3 21 12 30 cd fc 03 fb d8 c3 be 13 "
                 "21 09 30 c3 65 12 ff ff ff "         # $14A0: LD HL,3009 / JP FASTH
                 "21 0c 30 c3 65 12 ff ff ff "         # $14A9: LD HL,300C / JP FASTH
                 "e1 22 ce 65 e1 22 3d 5c f9 fb c9",
        note="$1488-$14C6 is an unreferenced remnant of a SYSCON open path (no "
             "CALL/JP/LD/JR reaches it). Each entry is DI / LD HL,vector / CALL "
             "$03FC (the returning thunk) / EI: the 2068's bank switch writes port "
             "FFh then F4h with interrupts on, and an interrupt between the two "
             "finds the empty DOCK at $0038 -- a channel switches banks for every "
             "character, so it has to run the round trip under DI. The trampolines "
             "RET C when the module handled it, else go on to the stock routine "
             "(the module rebuilt HL). The stubs are every 'F' record's out/in "
             "addresses, so records hold nothing that moves. The trap puts the RAM "
             "bank stack ($65CE) back when a report is raised inside a thunked "
             "call, re-enables interrupts, and goes on to the old ERR_SP handler "
             "(fddcmd.asm GUARDED). Spec §4.",
    ),
    dict(
        name="BEEPER thunk under DI: $03F3 -> $041C tail -> EXROM BEEP_VEC ($3015)",
        bank="home", addr=0x03F3,
        before="22 cd 5d 21 00 20 c3 fc 03",
        after="f3 22 cd 5d 21 15 30 18 20",           # DI / LD (5DCD),HL / LD HL,3015 / JR 041C
        note="TS-Pico moved BEEPER to EXROM behind this thunk. BEEPER ends in EI, "
             "so the switch back ran with interrupts on and could land an interrupt "
             "on the empty DOCK bank (see the $1488 patch). The editor clicks once "
             "per character, so INPUT # from a file crashed within a few hundred "
             "characters in ZEsarUX. Now the round trip runs under DI and G_BEEP "
             "re-disables after BEEPER's EI.",
    ),
    dict(
        name="BEEPER thunk tail in the dead $041C-$0420",
        bank="home", addr=0x041C,
        before="00 00 10 d3 fe",
        after="cd fc 03 fb c9",                       # CALL 03FC / EI / RET
        mb_after="c3 65 12 fb c9",                    # JP FASTH (the Megabank build)
        note="$041C-$041D follow the thunk's unconditional JP 65D0; $041E-$0421 are "
             "remnants of the relocated BEEPER (DIFF_HOME_vs_STOCK.md). Nothing "
             "references them.",
    ),
    dict(
        name="OPEN #: $145E CALL $1465 -> CALL $1488",
        bank="home", addr=0x145E,
        before="cd 65 14", after="cd 88 14",
        note="$1465 is only called from here. HL = the STRMS entry, the spec string "
             "on the calculator stack; C back from the module = DE is the offset "
             "$1461 stores.",
    ),
    dict(
        name="OPEN # syntax: $1438 CALL $2569 -> CALL $14BD (parse ,mode[,reclen])",
        bank="home", addr=0x1438,
        before="cd 69 25", after="cd bd 14",
        note="Stock OPEN # skipped everything after the spec's comma in the syntax "
             "pass, which also skipped storing each number's hidden five-byte form, "
             "so a record length (stage 2) couldn't be evaluated at run time (Report "
             "C). $2569 is still called from its other callers.",
    ),
    dict(
        name="OPEN # syntax trampoline in the dead $14BD-$14C5",
        bank="home", addr=0x14BD,
        before="cd d0 65 d1 7a c6 80 57 e1",
        after="f3 21 18 30 cd fc 03 fb c9",          # DI / LD HL,3018 / CALL 03FC / EI / RET
        note="The last 9 bytes of the unreferenced $1488-$14C6 block.",
    ),
    dict(
        name="CLOSE #: $13A5 CALL $13BE -> CALL $1494",
        bank="home", addr=0x13A5,
        before="cd be 13", after="cd 94 14",
        note="Stock CLOSE # on an unknown letter runs off the end of CL_TAB and "
             "crashes; the module closes 'F' records itself and returns C, so $13A8 "
             "only resets the STRMS entry.",
    ),
    dict(
        name="BIOS C_END: $184F JP $23CD -> JP $301B (C_END2)",
        bank="exrom", addr=0x184F,
        before="c3 cd 23", after="c3 1b 30",
        note="ROM 2.0's C_END failed with A = 02h for a timeout AND for status 3 "
             "(Report F), so callers reported a silent Pico as F. The module's "
             "C_END2 ($301B, C_END_VEC) returns a timeout as 09h (J); status "
             "errors, BREAK (0Ch) and a Pico reset (1Ch) come back as before. "
             "WF_NPH ($184C) is unchanged.",
    ),
    dict(
        name="tpi:tape: $20BE CALL $1861 / JR $2108 -> JP TAPE_VEC ($301E)",
        bank="exrom", addr=0x20BE,
        before="cd 61 18 18 45", after="c3 1e 30 00 00",
        note="ROM 2.0 set TPMODE to 0 (XOR A / S_MODE), clearing the printer "
             "switch (bit 0) as well as LOAD/SAVE (bit 1); tpi:sdcard sets only "
             "bit 1, so picopt -> tape -> sdcard left printing on the 2068 (#176). "
             "The module's TAPE_MODE clears bit 1 alone and ends at $2105 as "
             "tpi:sdcard does. The five bytes don't fit the fix in place: A holds "
             "the length test's 8 here. $20C1-$20C2 (the JR) become unreachable; "
             "nothing else jumps to $20BE-$20C2 ($20C3 is tpi:sdcard's entry).",
    ),
    dict(
        name="boot banner: \"TS-Pico ROM v2.0\" -> \"v2.4\"",
        bank="exrom", addr=0x1C7E,
        before="76 32 2e 30", after="76 32 2e 34", mb_after="76 32 2e 35",
        note="The copyright line at $1C6C (tspico-sync.asm) shown at start-up. "
             "Same length, so nothing else moves.",
    ),
    dict(
        name="version marker: HOME $0065 20h -> 24h (ROM 2.4)",
        bank="home", addr=0x0065,
        before="20", after="24", mb_after="25",
        note="PEEK 101 tells a program which ROM it has: 15h v1.1, 17h v1.7, "
             "20h 2.0 (tspico-sync.asm), 21h 2.1 (the disk commands), 22h 2.2 "
             "(2.1 plus the tpi:tape and pre-load fixes), 23h 2.3 (keys as typed, "
             "the Pico ends the $86 loop, the new string reader), 24h this ROM, "
             "2.4 (COPY and MOVE as two verbs, LIST \"x\", RESTORE #, CAT #, "
             "the card label).",
    ),
    dict(
        name="version marker: BIOS G_VERS LD BC,0020h -> LD BC,0024h",
        bank="exrom", addr=0x1852,
        before="01 20 00 c9", after="01 24 00 c9", mb_after="01 25 00 c9",
        note="The Pico Interface BIOS G_VERS ($1844 -> $1852) returns the same "
             "version as HOME $0065.",
    ),
    dict(
        name="command pre-header byte 2: LD A,(BANK_SV) -> LD A,24h (ROM_ID)",
        bank="exrom", addr=0x1BB5,
        before="3a cf 5d", after="3e 24 00", mb_after="3e 25 00",
        note="BUILD_PREHEADER_B sent BANK_SV, which is always FFh, and the Pico "
             "ignored it. From ROM 2.3 on it sends the version marker instead, so the "
             "firmware knows which ROM sent each command (tpi:info shows it; "
             "#227). fddcmd.asm's SEND_FOPEN and CH_SEND send ROM_ID too. "
             "FFh = ROM 2.2 or earlier.",
    ),
    dict(
        name="function $86: every key goes on round the loop ($21F0 -> JP YN_LOOP_GUARD)",
        bank="exrom", addr=0x21F0,
        before="e6 5f fe 4e c2 a1 22", after="c3 a1 22 00 00 00 00",
        note="Was AND 5Fh / CP 'N' / JP NZ,YN_LOOP_GUARD, then JP LOOP_EXIT_OK "
             "($21F7): N printed itself and left the loop with nothing more read. "
             "Now N is a key like any other (#227): the ROM waits for READY and "
             "reads what the Pico sends next, and the Pico ends the loop with "
             "03h. $21F7 and LOOP_EXIT_OK ($0810) become unreachable. $88 joins "
             "this loop at $21E6 (LOWER_LOOP), so it changes too.",
    ),
    dict(
        name="POLL_KEYPRESS: keys as typed ($0572 AND 0DFh -> NOP NOP)",
        bank="exrom", addr=0x0572,
        before="e6 df", after="00 00",
        note="POLL_KEYPRESS ended CP 61h / RET C / CP 7Bh / RET NC / AND 0DFh: "
             "a lower-case letter went to the Pico upper case. Now the key goes "
             "as typed and the firmware decides what case means (#227). After "
             "the CP 7Bh the flags are already NZ, so 'Z = no key' still holds. "
             "Its only caller is KEYWAIT ($2346), from GET_KEY_AND_SEND ($0479): "
             "the key waits of functions $82, $84 and $86/$88.",
    ),
    dict(
        name="PRINT_STRING_FROM_PICO: $045F -> JP PS_READ ($377F)",
        bank="exrom", addr=0x045F,
        before="f5 18 03", after="c3 7f 37",
        note="The v1.1 reader (PUSH AF / JR $0465) tested every byte for 00h, "
             "03h and >= 80h, the parameter bytes after a control code "
             "included, so INK 0 or PAPER 3 ended the text and graphics, UDGs "
             "and tokens could not be sent. The module's PS_READ passes "
             "parameters through and ends only on 00h and 03h (#228). Its three "
             "callers enter at $045F ($027A for $81, $219E for $82, $21E7 for "
             "$86/$88); $0462-$046F, $068E and $06F2-$06FC become unreachable.",
    ),
]

# Module symbols the patches above jump to by a fixed address: the build fails
# if the module moves one, rather than patch a jump into the wrong code.
FIXED_SYMS = {"PS_READ": 0x377F}


# --- The Megabank test ROM (--megabank) ---------------------------------------
# Applied after PATCHES (with their `mb_after` bytes where they have them). Each
# jumps to Megabank code appended to the module (fddcmd.asm, IFDEF MEGABANK);
# MB_FIXED_SYMS pins those addresses. Megabank spec "Minimal ROM: detection,
# reset, mover, `r:` (phase 4)".
MB_PATCHES = [
    dict(
        name="boot: the bank search at $0A3E -> JP MB_BOOT ($3998)",
        bank="exrom", addr=0x0A3E,
        before="2a bc 5c", after="c3 98 39",
        note="Timex's search (X0A3E-X0DAF) probed for banks through the "
             "memory-mapped, IOA5-gated registers. Its two entries both land "
             "at $0A3E: the fall-through from $09F4 and CALL $0A3E at $1CA8 (D "
             "held at power-on). Nothing else enters $0A3F-$0DAF: the JP $0D31 "
             "at $0057 is in the 11 bytes $1CAE copies to RAM, where it runs "
             "after OUT (F4h),0 and so reaches HOME's $0D31, and the "
             "renumbering at $0CFB is called only from inside the range. "
             "MB_BOOT writes OWN0-OWN7 and WPROT = 0; MB_DETECT sets the bank "
             "count from the board (BASE and SIZE) and ends with $2082 "
             "(SYSCON's 80h end marker) as the old code did. $0A41-$0DAF "
             "become free.",
    ),
    dict(
        name="SA-BYTES: $0068 JP $1879 -> JP R_SA ($39F5)",
        bank="exrom", addr=0x0068,
        before="c3 79 18", after="c3 f5 39",
        note="R_SA sends the block to the RAM disk when TPMODE bit 5 is set "
             "(an \"r:\" statement, F_HOOK); otherwise JP $1879 as before.",
    ),
    dict(
        name="LD-BYTES: $00FC JP $196D -> JP R_LD ($3A06)",
        bank="exrom", addr=0x00FC,
        before="c3 6d 19", after="c3 06 3a",
        note="The same for LOAD, VERIFY and MERGE; otherwise JP $196D.",
    ),

    # --- The Timex bank API (Megabank spec phase 8). The bank code runs in
    # RAM: the boot copies EXROM $1000-$162F to $6200 (RAM = EXROM + $5200),
    # so these are given as EXROM addresses with the RAM address in the name.
    # bankapi.asm replaces RAM $6316-$6571 (bank_api_splice below).
    dict(
        name="the bank count (RAM $6315): 0 in the image, not FFh",
        bank="exrom", addr=0x1115, before="ff", after="00",
        note="The boot zeroes it ($221F, $09F4, $1C86) and MB_DETECT sets it, "
             "but the bank code now trusts it (no board below a count of 0), "
             "so the copy starts at 0 too.",
    ),
    dict(
        name="interrupt handler (RAM $62B7): the frame is 19 bytes, not the bank count + 2",
        bank="exrom", addr=0x10B7,
        before="3a 15 63 5f 16 00 13 13", after="11 13 00 00 00 00 00 00",
        note="LD A,($6315) / LD E,A / LD D,0 / INC DE / INC DE -> LD DE,19 and "
             "NOPs. SAVE_STATUS/RESTORE_STATUS now save FFh, F4h, the board's 16 "
             "registers and its select whatever the bank count. The X1D00 entry "
             "for $62B8 is dropped with it.",
    ),
    dict(
        name="CALL_BANK (RAM $65F8): the frame is 19 bytes",
        bank="exrom", addr=0x13F8,
        before="3a 15 63 4f 06 00 03 03", after="01 13 00 00 00 00 00 00",
        note="LD BC,19. Its return path is size-agnostic (it finds the frame "
             "from its own parameters). The X1D00 entry for $65F9 is dropped.",
    ),
    dict(
        name="XFER_BYTES (RAM $672F): the frame is 19 bytes",
        bank="exrom", addr=0x152F,
        before="3a 15 63 4f 06 00", after="01 11 00 00 00 00",
        note="LD BC,17: the two DEC HL after it make 19. The X1D00 entry for "
             "$6730 is dropped.",
    ),
    dict(
        name="XFER_BYTES (RAM $6722): no PUSH AF, so A returns the result",
        bank="exrom", addr=0x1522, before="f5", after="00",
        note="Brzozowski: the genuine code saved AF and restored it at $67FF, "
             "losing the 0/1 result. With the POP at $67FF and the offset at "
             "$672B.",
    ),
    dict(
        name="XFER_BYTES (RAM $672B): the parameters are 8 bytes above SP, not 10",
        bank="exrom", addr=0x152B, before="0a", after="08",
        note="Brzozowski: one push fewer ($6722).",
    ),
    dict(
        name="XFER_BYTES (RAM $67FF): no POP AF",
        bank="exrom", addr=0x15FF, before="f1", after="00",
        note="Brzozowski: the other half of $6722.",
    ),
    dict(
        name="XFER_BYTES (RAM $676A): the same-bank mask to E, not B",
        bank="exrom", addr=0x156A, before="47", after="5f",
        note="Technical Manual 6.5.8 / Brzozowski: $6778 takes the chunks from "
             "E, as the other path ($6773) leaves them.",
    ),
    dict(
        name="XFER_BYTES (RAM $67C2): the no-room exit keeps A = 1",
        bank="exrom", addr=0x15C2, before="2b", after="2c",
        note="Brzozowski: JR to $67EF, past the XOR A at $67EE.",
    ),
    dict(
        name="XFER_BYTES's copier (RAM $66DF): the destination advances by DE",
        bank="exrom", addr=0x14DF, before="75 04 dd 74", after="73 04 dd 72",
        note="Brzozowski: LD (IX+4),L / LD (IX+5),H stored the source; the "
             "destination is DE.",
    ),
    dict(
        name="XFER_BYTES's end address (RAM $66F3): length - 1, direction FFh",
        bank="exrom", addr=0x14F3, before="07 0f 38", after="0b 3c 28",
        note="Brzozowski: RLCA / RRCA / JR C -> DEC BC / INC A / JR Z: the last "
             "byte is start + length - 1 (the chunk check was one byte off).",
    ),
    dict(
        name="CALL_HOME (EXROM $03DE): LD HL,FF00h -> JP MB_CALL_HOME ($3E43)",
        bank="exrom", addr=0x03DE, before="21 00 ff", after="c3 43 3e",
        note="MB_CALL_HOME pushes the bank word FFFC (HOME in chunks 0-1) and "
             "the two zero words. FF00 gave HOME every chunk, so BANK_ENABLE "
             "took them from any board bank mapped there. Not patchable in "
             "place: the thunk's LD H,0 makes its zeros from FF00's L, so "
             "FFFC would push a parameter count of FCh and CALL_BANK would "
             "copy 252 bytes more each call. HOME's own crossings already use "
             "FEFC.",
    ),
    dict(
        name="EXROM $08DF: the same crossing, FF00 -> FFFC",
        bank="exrom", addr=0x08DF, before="00", after="fc",
        note="LD L,0 -> LD L,FCh (with LD H,FFh after it).",
    ),
    dict(
        name="EXROM $001E: the same crossing, FF00 -> FFFC",
        bank="exrom", addr=0x001E, before="00", after="fc",
        note="LD H,FFh / LD L,0 -> LD L,FCh.",
    ),

    # --- The fast channel entry (Megabank spec, open question 21). Every
    # character through an F or R record, and the editor's key click, used to
    # cross through Timex's bank call (03FCh -> CALL_BANK at 65D0h:
    # SAVE_STATUS, BANK_ENABLE, RESTORE_STATUS, each reading or writing the
    # board's 16 registers) and GUARDED's error trap. FASTH switches with an
    # OUT to FFh and one to F4h each way. The F4h OUTs run from ROM, and the
    # TS-Pico follows a write to F4h some time after it (a v3 card: a polled
    # loop on core 1, about a microsecond; nothing bounds it). So each is a
    # loop, OUT (F4h),A / JR, at the same address in both ROMs ($128B in,
    # $128F out) with the same bytes but the JR's displacement: whichever ROM
    # a read comes from, the Z80 repeats the OUT until the displacement is
    # read from the other one. The rule: no bank switch from ROM unless the
    # code after the OUT is the same in both ROMs until one read tells them
    # apart.
    dict(
        name="SELECT's banked branch: $1241 JR NC,$1265 -> JR NC,$123D (Report O)",
        bank="home", addr=0x1241, before="30 22", after="30 fa",
        note="A STRMS entry whose bytes OR to 80h or more sent CHAN-OPEN to "
             "Timex's SYSCON lookup at $1265, the banked channels: never "
             "reachable (the banked OPEN path at $1488 was dead and is the "
             "module's), and its CALL_BANK would jump through whatever SYSCON "
             "held. Now O Invalid stream, the RST 8 at $123D, so $1265-$1292 "
             "is free for FASTH. Nothing else enters it.",
    ),
    dict(
        name="FASTH, the fast entry, in the freed $1265-$1292",
        bank="home", addr=0x1265,
        before="2a bc 5c d6 80 57 19 22 51 5c 7e 32 bf 5c fd cb 30 a6 23 23 23 23 "
               "23 23 3a bf 5c 47 0e 88 56 23 5e 62 6b e5 c5 01 00 00 c5 c5 cd d0 65 c9",
        after="f3 4f 45 db f4 e6 03 20 16 "              # DI / LD C,A / LD B,L / IN A,(F4) / AND 3 / JR NZ,.slow
              "db ff f5 f6 80 d3 ff "                    # IN A,(FF) / PUSH AF / OR 80 / OUT (FF),A
              "db f4 f6 03 c3 8b 12 "                    # IN A,(F4) / OR 3 / JP SW_IN
              "d1 f1 d3 ff d5 f1 fb c9 "                 # $127C FH_BACK: POP DE / POP AF / OUT (FF),A / PUSH DE / POP AF / EI / RET
              "79 cd fc 03 fb c9 "                       # $1284 .slow: LD A,C / CALL 03FC / EI / RET
              "ff "
              "d3 f4 18 fc "                             # $128B SW_IN: OUT (F4),A / JR SW_IN (the EXROM's JR goes on)
              "d3 f4 18 e9",                             # $128F SW_OUT: OUT (F4),A / JR FH_BACK (the EXROM's JR loops)
        note="HL = the vector (3009h out, 300Ch in, 3015h BEEPER), A = the "
             "character; B = the vector's low byte for FX_ENTRY, since HL is "
             "used on the way in. With F4h bits 0-1 clear (HOME in chunks "
             "0-1: anything else there, such as a program's board page, takes "
             "the old path, Timex's bank call through 03FCh and GUARDED): FFh "
             "bit 7 set (the EXROM, not the DOCK) and FFh as it was pushed, "
             "then F4h bits 0-1 set by SW_IN at $128B, which repeats its OUT "
             "until the JR's displacement at $128E is read from the EXROM "
             "(04h: on to $1293) and not from HOME (FCh: round again). "
             "FX_ENTRY (rchan.asm) comes back through SW_OUT at $128F with AF "
             "on the stack: the EXROM's displacement at $1292 is FCh (round "
             "again), HOME's E9h, to FH_BACK at $127C: FFh back (all of it, "
             "where RESTORE_STATUS puts back bit 7 only), AF, EI.",
    ),
    dict(
        name="the EXROM's half of the switch loops, and the landing: $128B-$1296",
        bank="exrom", addr=0x128B,
        before="00 00 00 00 00 00 00 00 00 00 00 00",
        after="d3 f4 18 04 "                             # $128B SW_IN: OUT (F4),A / JR $1293
              "d3 f4 18 fc "                             # $128F SW_OUT (FX_BACK): OUT (F4),A / JR SW_OUT
              "21 8c 2c e9",                             # $1293: LD HL,2C8C / JP (HL)
        note="bankapi.asm's zero padding between GET_NUMBER and BANK_ENABLE "
             "(RAM $648B-$6498; the manifest is applied after the splice). "
             "The boot copies these bytes to RAM $648B-$6496 with the bank "
             "code, where nothing reads or runs them. $128B-$1292 hold the "
             "same bytes as HOME's but the two displacements. The landing "
             "checks chunk 1, where FX_ENTRY is: it jumps to $2C8C with HL = "
             "$2C8C. While chunk 1 is still HOME the byte there is HOME's E9h, "
             "JP (HL), which jumps to itself; once it is the EXROM, the JP "
             "FX_ENTRY below.",
    ),
    dict(
        name="the fast entry's landing in chunk 1: EXROM $2C8C JP FX_ENTRY ($2400)",
        bank="exrom", addr=0x2C8C, before="ff ff ff", after="c3 00 24",
        note="Free EXROM after rchan.asm (fddcmd.asm asserts RCH_END <= "
             "$2C8C), at the address of a JP (HL) in HOME (MB_ANCHORS).",
    ),
]

MB_FIXED_SYMS = {"MB_BOOT": 0x3998, "R_SA": 0x39F5, "R_LD": 0x3A06, "FN_EXT": 0x3A61,
                 "MB_CALL_HOME": 0x3E43, "FX_ENTRY": 0x2400}

# Base-ROM code the Megabank code relies on (checked with ANCHORS when
# building --megabank).
MB_ANCHORS = [
    dict(name="HOME's JP (HL) at $2C8C: the fast entry waits on it until chunk 1 is the EXROM",
         bank="home", addr=0x2C8C, bytes="e9"),
    dict(name="SYSCON_END: DEC HL / LD (HL),80h / CALL_HOME $0A35 (MB_BOOT ends here)",
         bank="exrom", addr=0x2082, bytes="2b 36 80 dd e5 d9 21 35 0a c3 dd 03"),
    dict(name="the old search's end: CALL $2082 / CALL $0CFB / RET",
         bank="exrom", addr=0x0AD4, bytes="cd 82 20 cd fb 0c c9"),
    dict(name="SA_RET: the tape routines' exit (border, BREAK, EI, POP AF)",
         bank="exrom", addr=0x00E5, bytes="f5 3a 48 5c e6 38"),
    dict(name="PICO_SA: SA-BYTES's TPMODE bit-1 gate",
         bank="exrom", addr=0x1879, bytes="f5 3a db 5d e6 02"),
    dict(name="PICO_LD: LD-BYTES's TPMODE bit-1 gate",
         bank="exrom", addr=0x196D, bytes="f5 3a db 5d e6 02"),
    dict(name="the 64-column copy: 6000h-683Fh to F7C0h, then X1D00's list + 97C0h",
         bank="exrom", addr=0x0DDD, bytes="11 c0 f7 21 00 60 01 40 08 ed b0 21 00 1d 01 c0 97"),
    dict(name="the boot's bank-stack pointer (65CEh) starts at 65CEh",
         bank="home", addr=0x0DFF, bytes="21 ce 65 22 ce 65"),
    dict(name="SESSION_SETUP's non-command exit clears TPMODE bits 7-4 (bit 5 too)",
         bank="exrom", addr=0x1A3B, bytes="3a db 5d e6 0f 32 db 5d"),
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
    dict(name="ROM 2.0 BIOS_C_END: CALL WF_NPH / RET C / JP C_END_TAIL ($227F)",
         bank="exrom", addr=0x23CD, bytes="cd 9e 23 d8 c3 7f 22"),
    dict(name="C_END_TAIL: C_END after its wait (C_END2 jumps here)",
         bank="exrom", addr=0x227F, bytes="0e 0e cd 98 22 38 0e a7"),
    dict(name="Pico Interface BIOS table (TX_A, RX_A, C_END, WF_NPH)",
         bank="exrom", addr=0x1846, bytes="18 25 18 20 18 03 c3 9e 23 c3 cd 23"),
    dict(name="$86's pieces LOWER_LOOP reuses: READ_STATUS_BYTE, OPEN_STREAM via $04F1, the loop",
         bank="exrom", addr=0x01C3, bytes="cd b9 02 c3 f1 04"),
    dict(name="$04F1: open stream $FE through $0426",
         bank="exrom", addr=0x04F1, bytes="f5 3e fe cd 26 04 f1 c9"),
    dict(name="$86 handler: CALL $01C3, then the loop at $21E6",
         bank="exrom", addr=0x21E3, bytes="cd c3 01 f5 cd 5f 04"),
    dict(name="HOME->EXROM returning thunk the $25D6 hook jumps to",
         bank="home", addr=0x03FC, bytes="e5 21 fc fe"),
    dict(name="H_COPY: HOME's COPY, where the $25D6 hook sends a bare COPY",
         bank="home", addr=0x0A02, bytes="d9 21 30 16 c3 e3 3c"),
    dict(name="H_LIST: HOME's LIST, where FDD_LIST sends LIST, LIST n, LIST #n",
         bank="home", addr=0x1545, bytes="3e 02 fd 36 02 00"),
    dict(name="H_RESTORE: HOME's RESTORE after class 03 (FIND-INT2 first)",
         bank="home", addr=0x1E9D, bytes="cd 23 1f 2a bc 5c"),
    dict(name="H_USE_ZERO: USE-ZERO, a 0 on the calculator stack at run time",
         bank="home", addr=0x1C51, bytes="cd 89 28 c8 ef a0 38 c9"),
    dict(name="EXROM $2000: JP to the relocated BEEPER (G_BEEP calls it)",
         bank="exrom", addr=0x2000, bytes="c3 3f 20"),
    dict(name="MODE_SET_OK: CALL S_MODE / CALL $042F / JP $1B72 (\"0 OK\"), TAPE_MODE ends here",
         bank="exrom", addr=0x2105, bytes="cd 62 18 cd 2f 04 c3 72 1b"),
    dict(name="H_MAKE_ROOM (OPEN # appends a record)",
         bank="home", addr=0x12BB, bytes="e5 cd bb 1f e1 cd ca 12"),
    dict(name="H_RECLAIM (CLOSE # removes it)",
         bank="home", addr=0x1750, bytes="c5 78 2f 47 79 2f 4f 03"),
    dict(name="H_CHAN_OPEN: select stream A; its D OR E >= $80 test sets the offset rule",
         bank="home", addr=0x1230, bytes="87 c6 16 6f 26 5c 5e 23 56 7a b3 20 02 cf 17 fe 80"),
    dict(name="OPEN/CLOSE # stream fetch: ($5CCB) = n",
         bank="home", addr=0x140F, bytes="cd 1e 1f 32 cb 5c fe 10 38 02 cf 17"),
    dict(name="OPEN #: $1461 stores DE at the STRMS entry after the $145E call",
         bank="home", addr=0x1461, bytes="73 23 72 c9"),
    dict(name="CLOSE #: $13A8 resets the STRMS entry after the $13A5 call",
         bank="home", addr=0x13A8, bytes="01 00 00 11 e2 a3 eb 19"),
    dict(name="RST 10 output: CURCHL's record, HL restored after (the stubs rely on it)",
         bank="home", addr=0x11ED, bytes="d9 e5 2a 51 5c"),
]


# --- The Timex bank API (--megabank) -----------------------------------------
# bankapi.asm is RAM $6316-$6571 (GET_WORD to RESTORE_STATUS), stored at EXROM
# $1116-$1371. In 64-column mode the boot copies RAM $6000-$683F to $F7C0 and
# adds $97C0 to every word the table at EXROM $1D00 lists (a RAM address each,
# 0000 at the end; zeros follow it to $1EDB). The module is assembled twice,
# RB = 0 and RB = $97C0: every word that differs by $97C0 is one the table
# must list.
BANKAPI_SRC    = ROOT / "src" / "rom" / "fdd" / "bankapi.asm"
BANK_RAM_DELTA = 0x5200                     # RAM = EXROM + this
BANKAPI_RAM    = (0x6316, 0x6572)
RELOC_DELTA    = 0x97C0
RELOC_TABLE    = 0x1D00                     # EXROM
RELOC_LIMIT    = 0x1EDC                     # first byte the table can't use
# Entries outside bankapi.asm: the frame-size operands the patches turn into
# constants, and the genuine table's one wrong entry (674Fh is the CALL's
# opcode; the SAVE_STATUS call's operand at 6744h was missing).
RELOC_DROP     = {0x62B8, 0x65F9, 0x6730}
RELOC_FIX      = {0x674F: 0x6744}


def assemble_bankapi(workdir, rb):
    d = workdir / ("bankapi_%x" % rb)
    d.mkdir()
    r = subprocess.run(["sjasmplus", "--nologo", f"-DRB={rb:#x}",
                        f"--sym={d / 'bankapi.sym'}", str(BANKAPI_SRC)],
                       cwd=d, capture_output=True, text=True)
    if r.returncode != 0:
        die("sjasmplus failed on bankapi.asm (RB=%#x):\n" % rb + r.stdout + r.stderr)
    return (d / "bankapi.bin").read_bytes()


def bank_api_relocs(b0, b1):
    """RAM addresses of the words that differ by RELOC_DELTA between the two
    assemblies; dies on any other difference."""
    relocs, i = [], 0
    while i < len(b0):
        if b0[i] == b1[i]:
            i += 1
            continue
        w0 = b0[i] | b0[i + 1] << 8 if i + 1 < len(b0) else None
        w1 = b1[i] | b1[i + 1] << 8 if i + 1 < len(b1) else None
        if w0 is None or (w1 - w0) & 0xFFFF != RELOC_DELTA:
            die("bankapi.asm: RAM $%04X differs between RB=0 and RB=$97C0 but "
                "is not an address in the copied block" % (BANKAPI_RAM[0] + i))
        relocs.append(BANKAPI_RAM[0] + i)
        i += 2
    return relocs


def bank_api_splice(base, out, workdir, touched):
    b0 = assemble_bankapi(workdir, 0)
    b1 = assemble_bankapi(workdir, RELOC_DELTA)
    size = BANKAPI_RAM[1] - BANKAPI_RAM[0]
    if len(b0) != size or len(b1) != size:
        die("bankapi.bin is %d bytes, expected %d" % (len(b0), size))
    off = file_offset("exrom", BANKAPI_RAM[0] - BANK_RAM_DELTA)
    out[off:off + size] = b0
    touched.append((off, off + size - 1))
    new = bank_api_relocs(b0, b1)

    t = file_offset("exrom", RELOC_TABLE)
    old = []
    while True:
        w = base[t] | base[t + 1] << 8
        t += 2
        if w == 0:
            break
        old.append(w)
    kept = [RELOC_FIX.get(w, w) for w in old
            if not BANKAPI_RAM[0] <= w < BANKAPI_RAM[1] and w not in RELOC_DROP]
    table = sorted(set(kept + new))
    data = b"".join(bytes((w & 255, w >> 8)) for w in table) + b"\0\0"
    t = file_offset("exrom", RELOC_TABLE)
    if t + len(data) > file_offset("exrom", RELOC_LIMIT):
        die("the relocation table (%d entries) overruns EXROM $%04X"
            % (len(table), RELOC_LIMIT))
    end_old = t + 2 * len(old) + 2
    if any(base[end_old:t + len(data)]):
        die("EXROM after the relocation table is not zero")
    out[t:t + len(data)] = data
    touched.append((t, t + len(data) - 1))
    print(f"bank API: {size} bytes at RAM ${BANKAPI_RAM[0]:04X} (EXROM "
          f"${BANKAPI_RAM[0] - BANK_RAM_DELTA:04X}); relocation table "
          f"{len(old)} -> {len(table)} entries ({len(new)} from bankapi.asm)")


def check_anchors(base, anchors=None):
    """Messages for every anchor whose bytes differ in base (empty = all good)."""
    bad = []
    for a in (ANCHORS if anchors is None else anchors):
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


def assemble(workdir, megabank=False):
    """Assemble the module; return (bytes, symbols dict)."""
    binf = workdir / "fddcmd.bin"
    symf = workdir / "fddcmd.sym"
    # SAVEBIN in the source writes relative to CWD, so run in workdir.
    r = subprocess.run(
        ["sjasmplus", "--nologo", f"--sym={symf}"]
        + (["-DMEGABANK"] if megabank else []) + [str(ASM_SRC)],
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
    ap.add_argument("--megabank", action="store_true",
                    help="build ROM 2.5 (the release ROM, with the Megabank), build/TSPICO-25.ROM")
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

    mb = args.megabank
    out_rom = OUT_MB if mb else OUT_ROM
    workdir = pathlib.Path(tempfile.mkdtemp(prefix="buildrom."))
    module, syms = assemble(workdir, mb)
    entry = syms.get("FDD_DISPATCH")
    if entry != FDD_ORG:
        die(f"FDD_DISPATCH is {entry:#06x}, expected FDD_ORG {FDD_ORG:#06x}")
    for name, addr in (dict(FIXED_SYMS, **MB_FIXED_SYMS) if mb else FIXED_SYMS).items():
        if syms.get(name) != addr:
            die(f"{name} is at {syms.get(name, 0):#06x}; the patches jump to "
                f"{addr:#06x}. Update FIXED_SYMS and the patch bytes together.")

    out = bytearray(base)
    touched = []   # (start, end) file-offset ranges we intend to change

    bad = check_anchors(base, ANCHORS + (MB_ANCHORS if mb else []))
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

    if mb:
        # the r: channels, assembled with the module (fddcmd.asm INCLUDEs
        # rchan.asm at RCH_BASE): free EXROM in the same chunk
        rch = (workdir / "rchan.bin").read_bytes()
        if syms.get("RCH_BASE") != RCH_ORG:
            die(f"RCH_BASE is {syms.get('RCH_BASE', 0):#06x}, expected {RCH_ORG:#06x}")
        rstart = file_offset("exrom", RCH_ORG)
        rend = rstart + len(rch)
        if rend > file_offset("exrom", FDD_ORG) or any(b != 0xFF for b in base[rstart:rend]):
            die(f"EXROM ${RCH_ORG:04X}..${RCH_ORG+len(rch):04X} is not free for rchan.asm")
        out[rstart:rend] = rch
        touched.append((rstart, rend - 1))
        print(f"r: channels: {len(rch)} bytes at EXROM ${RCH_ORG:04X}")
        bank_api_splice(base, out, workdir, touched)

    # --- 4. apply the manifest ---
    for p in PATCHES + (MB_PATCHES if mb else []):
        if not p.get("enabled", True):
            print(f"skip  : {p['name']} (staged, not enabled)")
            continue
        if p["after"] is None:
            die(f"patch {p['name']!r} enabled but has no 'after' bytes")
        before = bytes.fromhex(p["before"])
        after = bytes.fromhex(p.get("mb_after", p["after"]) if mb else p["after"])
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
    out_rom.write_bytes(out)
    stem = "TSPICO-25" if mb else "TSPICO-fdd"
    (OUT_DIR / f"{stem}-home.bin").write_bytes(out[0:0x4000])
    (OUT_DIR / f"{stem}-exrom.bin").write_bytes(out[0x4000:0x8000])
    print(f"\nwrote {out_rom.relative_to(ROOT)}  "
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
