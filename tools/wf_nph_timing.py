#!/usr/bin/env python3
"""Compute the real WAIT_PICO_READY (WF_NPH) timeout from the shipped EXROM.

This exists because the timeout is the single most misreported number in the
TS-PICO documentation, and the reason is subtle: the poll *counter* is small
(B=0xE2=226), but each poll is enormously expensive, because reading the status
port goes through a debounced keyboard scan:

    1A54 WF_NPH -> 0655 READ_STATUS -> 069F CHECK_BREAK -> 0856 -> 10x 07F6

and 07F6 burns a 6x256 nested DJNZ delay before every keyboard read.

Reading `LD B,0E2h` alone and concluding "226 quick polls, so milliseconds" is
wrong. So is the docs' explanation that the shipped counter is larger than the
disassembly's -- it is not. Both the small counter AND the ~20s timeout are true.

    python3 tools/wf_nph_timing.py

Verify the instruction stream it models with:

    z80dasm -a -t -g 0x07f6 <(dd if=ROMs/TSPICO-11-exrom bs=1 skip=2038 count=18)
"""

CLOCK_HZ = 3_528_000  # TS2068 Z80 clock

# --- 07F6: debounced keyboard read -----------------------------------------
#   07F6 C5      PUSH BC            11
#   07F7 06 06   LD B,06h            7
#   07F9 C5      PUSH BC            11   <- outer loop
#   07FA 06 00   LD B,00h            7        (B=0 -> 256 iterations)
#   07FC 3E 7F   LD A,7Fh            7   <- inner loop
#   07FE 10 FC   DJNZ 07FC          13 taken / 8 final
#   0800 C1      POP BC             10
#   0801 10 F6   DJNZ 07F9          13 taken / 8 final
#   0803 C1      POP BC             10
#   0804 DB FE   IN A,(0FEh)        11
#   0806 C9      RET                10
inner = 255 * (7 + 13) + (7 + 8)                 # 256 iterations of LD A / DJNZ
outer_body = 11 + 7 + inner + 10                 # PUSH BC, LD B,0, inner, POP BC
outer = 5 * (outer_body + 13) + (outer_body + 8)  # 6 iterations
t_07f6 = 11 + 7 + outer + 10 + 11 + 10

# --- 0856: ten of them ------------------------------------------------------
#   0856 C5      PUSH BC            11
#   0857 06 0A   LD B,0Ah            7
#   0859 CD F6 07 CALL 07F6         17 + t_07f6
#   085C 10 FB   DJNZ 0859          13 taken / 8 final
#   085E C1      POP BC             10
#   085F C9      RET                10
call_body = 17 + t_07f6
t_0856 = 11 + 7 + 9 * (call_body + 13) + (call_body + 8) + 10 + 10

# --- 069F -> 0655 -> one 1A54 poll iteration --------------------------------
t_069f = 17 + t_0856 + 4 + 5 + 7 + 11 + 4 + 10   # CALL, RRA, RET C (nt), LD, IN, RRA, RET
t_0655 = 17 + t_069f + 10 + 11 + 10              # CALL 069F, JP NC (nt), IN A,(0Fh), RET
t_poll = 17 + t_0655 + 8 + 7 + 13                # CALL 0655, BIT 6,A, JR NZ (nt), DJNZ

B = 0xE2  # LD B,0E2h at 0x1A56
t_total = B * t_poll

print(f"  07F6 debounced keyboard read : {t_07f6:>12,} T  "
      f"= {t_07f6 / CLOCK_HZ * 1e3:8.2f} ms")
print(f"  0856 (10x 07F6)              : {t_0856:>12,} T  "
      f"= {t_0856 / CLOCK_HZ * 1e3:8.2f} ms")
print(f"  one WF_NPH poll iteration    : {t_poll:>12,} T  "
      f"= {t_poll / CLOCK_HZ * 1e3:8.2f} ms")
print(f"  full timeout (B=0x{B:02X}={B})   : {t_total:>12,} T  "
      f"= {t_total / CLOCK_HZ:8.2f} s")
print()
print(f"  => the Z80 polls port 0x0F only ~{CLOCK_HZ / t_poll:.0f} times/second,")
print(f"     and the FIRST poll lands ~{t_poll / CLOCK_HZ * 1e3:.0f} ms after entry.")
print(f"     Every WF_NPH call therefore costs at least ~{t_poll / CLOCK_HZ * 1e3:.0f} ms,")
print("     even on success. BREAK is likewise only sampled at that rate.")
