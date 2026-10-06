# TS-Pico ROM changes since v1.7

An assembly-level account of what changed on top of Gustavo Pane's v1.7 ROM:

- ROM 2.0: SYNC, BREAK and recovery.
- ROM 2.1: the disk commands, `f:` files and file channels.
- The ZX Spectrum ROM v3.

Addresses are Z80 addresses. In the 32 K image, HOME sits at file offset 0000h
and EXROM at 4000h, so a file offset equals the Z80 address within each half.
Each patch below replaces exactly the bytes shown. The build checks the base
bytes before it writes anything. Everything is assembled with sjasmplus. The
sources are listed [at the end](#sources).

## Lineage

| ROM | File | What it is |
|---|---|---|
| **v1.7** | `src/rom/TSPICO.ROM`, crc 09D4CA63 | Gustavo's ROM, the base for everything here. The only public release before this was v1.1. |
| **2.0** | `src/rom/TSPICO-SYNC.ROM`, from `tspico-sync.asm` | v1.7 plus SYNC, BREAK abort, the Pico-reset report and a BIOS wait that never raises a report. Its new code is at EXROM 2300h. It was never released on its own. |
| **2.1** | `src/rom/TSPICO-21.ROM`, crc 2B29F3E8 | 2.0 plus 16 HOME/EXROM patches and a 1919-byte module at EXROM 3000h–377Eh. This is the release ROM and the slot-1 image. |
| **ZX v3** | `src/rom/TSPICO-ZX48-V3.BIN`, from `tspico-zx48-v3.asm` | The ZX v2 Spectrum ROM (crc B3D40C73), with a WAIT_RDY fix and `LOAD "tpi:…"`. |
| **ZX v4** | `src/rom/TSPICO-ZX48-V4.BIN`, from the same source with `-DZXV=4` | v3 plus `SAVE "tpi:dir"`: it sends the op with bit 7 set and reads the reply in pieces (length 1–255, the bytes, … then 0), so a reply can be longer than 255 bytes. Flash slot 0's image (the flash image and the upgrade UF2) from 2026-10-03. |

From 2.0 on, the ROM and the firmware share one version number. ROM 2.0 and
later need firmware that understands the SYNC byte. Older firmware reads it as
the first byte of a command, so every command after it is misaligned.

## ROM 2.0: SYNC, BREAK and recovery

The problem: v1.7 has no way to get back in step when the Z80 and the Pico
disagree about where a transaction is. That happens after BREAK, after a crash
on either side, or after a dropped byte. The usual result is a long wait and
Report J, and every command after it fails the same way. 2.0 adds five things:

1. **SYNC.** Every transaction starts with `OUT (0Fh),03h`, then waits up to
   about 1 s for READY and IDLE. The Pico treats 03h on the status port as
   "abandon whatever you were doing", so each command starts from idle.
2. **BREAK aborts cleanly.** CAPS SHIFT+SPACE sends the same 03h, waits for
   the Pico to clean up, and raises Report D. v1.7 fell through to Report J
   instead.
3. **BREAK during long transfers.** BREAK is checked every 256 bytes in the
   SAVE and LOAD byte loops. It is also checked in the key wait of response
   functions 82h, 84h and 86h.
4. **A new report.** The Pico can drop a transaction on its own. It then
   raises READY with status bit 2 (RECOVERED, active low) clear. The ROM
   reports `T TS-Pico reset, try again` (ERR_NR 1Ch) at once, where it used
   to wait about 20 s for Report J.
5. **The BIOS keeps its contract.** WF_NPH and C_END now return with carry
   set on failure, without raising a report. A holds the reason: 02h for a
   timeout (as before), 0Ch for BREAK, 1Ch for a Pico reset.

The status port gained two bits in firmware 2.0:

- bit 3, IDLE: 1 means no transaction is open;
- bit 2, RECOVERED: 0 means the Pico dropped a transaction.

Bit 6, READY, is unchanged. Old firmware returns FFh, which reads as ready,
idle and not recovered, so the new tests never misfire on it.

### Patch sites

| Bank | Addr | v1.7 | 2.0 | Why |
|---|---|---|---|---|
| HOME | 0065h | `db 17h` | `db 20h` | Version marker (`PEEK 101`). |
| HOME | 0F12h–0F1Fh | `LD A,B / LD DE,0F65h / CALL 073Fh / XOR A / LD DE,1115h / CALL 073Fh` | `LD A,B / LD (5DCDh),HL / LD HL,EX_REPORT_MSG / CALL 03FCh / 4×NOP` | The report printer hands the message and the ", " to EXROM, which knows the new report 1Ch. Other codes print from HOME's table as before. |
| EXROM | 189Ah | `CALL 229Dh` | `CALL SYNC_WRITE` | SAVE: the header's pre-header. |
| EXROM | 1998h | `CALL 229Dh` | `CALL SYNC_WRITE` | LOAD, VERIFY and MERGE: every block. |
| EXROM | 1BAAh | `CALL 229Dh` | `CALL SYNC_WRITE` | TPI: and NET: commands. |
| EXROM | 1651h | `CALL 229Dh` | `CALL SYNC_WRITE` | LPRINT and LLIST characters. |
| EXROM | 16F6h | `CALL 229Dh` | `CALL SYNC_WRITE` | COPY in Pico printer mode. |
| EXROM | 06AAh | `POP BC / JP 1A61h` | `JP BRK_ABORT / NOP` | BREAK seen by the ready-wait aborts the Pico and raises D. v1.7 went to J. |
| EXROM | 18FDh | `INC IX / DEC DE` | `CALL STEP` | SAVE byte loop: checks BREAK every 256 bytes. |
| EXROM | 19EFh | `INC IX / DEC DE` | `CALL STEP` | LOAD byte loop: checks BREAK every 256 bytes. |
| EXROM | 0479h | `CALL 0546h` | `CALL KEYWAIT` | The key wait in response functions 82h, 84h and 86h. |
| EXROM | 1A58h | `CALL 0655h` | `CALL RD_STATUS` | WAIT_PICO_READY's status read. READY with RECOVERED low raises T at once. |
| EXROM | 184Ch | `JP 1A54h` | `JP BIOS_WF_NPH` | BIOS WF_NPH returns carry and a code, and never raises a report. |
| EXROM | 184Fh | `JP 2279h` | `JP BIOS_C_END` | BIOS C_END does the same wait, then runs v1.7's tail at 227Fh. |
| EXROM | 1853h | `db 17h` | `db 20h` | BIOS G_VERS: `LD BC,0020h`. |
| EXROM | 1C6Ch | boot line | `" 2026 TS-Pico ROM v2.0   "` | Same length as v1.7's line. |

### New code at EXROM 2300h

This code goes in the free FFh space after v1.7's last routine, which ends at
22FDh.

```z80
SYNC_WRITE:                     ; start a transaction; preserves every register (AF' is live in LOAD)
        push af
        push bc
        ld   a,03h
        out  (0Fh),a                ; SYNC
        call SYNC_WAIT
        pop  bc
        pop  af
        jp   229Dh                  ; v1.7's OUT (0Eh),A / AND A / RET

SYNC_WAIT:                      ; READY+IDLE, or give up after 65536 polls (~1.05 s)
        ld   bc,0
.poll:  in   a,(0Fh)
        and  48h                    ; bit 6 READY, bit 3 IDLE
        cp   48h
        ret  z
        dec  bc
        ld   a,b
        or   c
        jr   nz,.poll
        ret                         ; carry on: a silent Pico still gets J from the next wait

BRK_ABORT:                      ; tell the Pico, let it clean up, Report D
        ld   a,03h
        out  (0Fh),a
        call SYNC_WAIT
        rst  8
        db   0Ch                    ; RST 8 reloads SP from ERR_SP: safe at any depth, under DI

BRK_TEST:                       ; NC = CAPS SHIFT+SPACE; reads the port, so works under DI
        bit  6,(iy+7Dh)             ; the break-inhibit flag, as v1.7's 22F0h
        scf
        ret  nz
        ld   a,7Fh
        in   a,(0FEh)               ; SPACE
        rra
        ret  c
        ld   a,0FEh
        in   a,(0FEh)               ; CAPS SHIFT
        rra
        ret

STEP:                           ; replaces INC IX / DEC DE; BREAK test when E reaches 0
        inc  ix
        dec  de
        ld   a,e
        or   a
        ret  nz
        call BRK_TEST
        ret  c
        jp   BRK_ABORT

KEYWAIT:                        ; BREAK test in front of POLL_KEYPRESS (0546h), same Z contract
        call BRK_TEST
        jp   nc,BRK_ABORT
        jp   0546h

RD_STATUS:                      ; READ_STATUS (0655h), then: READY with RECOVERED low -> T
        call 0655h
        bit  6,a
        ret  z
        bit  2,a
        ret  nz
        rst  8
        db   1Ch                    ; T TS-Pico reset, try again

EX_REPORT_MSG:                  ; from HOME 0F12h via 03FCh; A = ERR_NR+1
        cp   1Dh
        jr   z,.pico
        ld   de,0F65h               ; HOME's report table, through the EXROM->HOME PO-MSG at 03EDh
        call 03EDh
        jr   .sep
.pico:  ld   hl,MSG_PICO_RESET      ; "TS-Pico reset, try again", bit 7 on the last char
.chr:   ld   a,(hl)
        and  7Fh
        push hl
        call EX_HOME_PRINT          ; HOME RST 10 via the 03DDh thunk
        pop  hl
        bit  7,(hl)
        inc  hl
        jr   z,.chr
.sep:   xor  a
        ld   de,1115h               ; ", "
        jp   03EDh

BIOS_WF_NPH:                    ; same ~19.9 s budget and debounced BREAK as v1.7; never raises
        push af
        push bc
        ld   b,0E2h
.poll:  call 069Fh                  ; CHECK_BREAK
        jr   nc,.brk
        in   a,(0Fh)
        bit  6,a
        jr   nz,.ready
        djnz .poll
        ld   c,02h                  ; timeout (as v1.7)
        jr   .fail
.ready: bit  2,a
        ld   c,1Ch                  ; RECOVERED
        jr   z,.fail
        pop  bc
        pop  af
        scf
        ccf                         ; NC, A and BC preserved
        ret
.brk:   ld   a,03h
        out  (0Fh),a
        call SYNC_WAIT
        ld   c,0Ch                  ; BREAK
.fail:  ld   a,c
        pop  bc
        inc  sp
        inc  sp                     ; drop the saved AF
        scf
        ret

BIOS_C_END:
        call BIOS_WF_NPH
        ret  c
        jp   227Fh                  ; v1.7's C_END read-status tail, unchanged
```

## ROM 2.1: HOME and EXROM patches

ROM 2.1 does three things:

- It gives CAT, MOVE, ERASE and FORMAT real meanings.
- It adds `SAVE/LOAD "f:path"` for plain files on the SD card.
- It adds file channels through `OPEN #`, `PRINT #`, `INPUT #` and `CLOSE #`.

Almost all of the work happens in a module at EXROM 3000h. The ROM patches
are only entry points into it, and most of them reuse dead HOME code:

- the 14-byte disk-command stub at 25D6h;
- the unreferenced SYSCON remnant at 1488h–14C6h, which no CALL, JP, LD or JR
  reaches.

Two problems turned up along the way, and they shaped every entry point.

- **Interrupts during a bank switch.** The 2068's switch writes port FFh, then
  F4h, with interrupts on. Between the two writes, chunk 0 can be the empty
  DOCK bank. An interrupt there runs RST 38h over FFh bytes until the machine
  is wiped. Stock code switches banks only a few times per command, but a
  channel switches for every character. In ZEsarUX that hit the window within
  a few hundred characters. So every HOME entry into the module is
  `DI / LD HL,vector / CALL 03FCh / EI`, which runs the whole round trip with
  interrupts off.
- **The bank stack leaks on errors.** The 03FCh thunk pushes a frame on the
  RAM bank stack at (65CEh) and pops it on return. A report raised inside a
  thunked call unwinds the Z80 stack but not the bank stack. Each such error
  left the bank stack 4–8 bytes lower, and after about 16 errors it overwrote
  the bank-switch code below it. The fix is an error trap in HOME at 14B2h,
  installed by the module's [GUARDED](#guarded-and-the-home-trap) wrapper.

| Bank | Addr | Before (2.0) | After (2.1) | Why |
|---|---|---|---|---|
| HOME | 1946h | `d0 c0 c4 c8` | `d2 c2 c6 ca` | These are the syntax-table offsets for CAT, FORMAT, MOVE and ERASE. They now skip the `0A 2C` (string, comma) prefix to the class-05h and routine pair, so a bare keyword is accepted. |
| HOME | 25D6h–25E3h | `CALL 2889h / JR NZ / CALL 2569h / CALL 1B44h / JP 2567h` | `DI / LD HL,3000h / CALL 03FCh / EI / RET / 5×00` | All four keywords fall into this disk-command stub. It now enters the module with B = the token, on both the syntax pass and the run-time pass. |
| EXROM | 01D2h | `JP 1A73h` | `JP 3003h` | This is SAVE-ETC's only jump to SESSION_SETUP. F_HOOK takes `"f:"` names; any other name goes on to 1A73h. |
| EXROM | 2213h | `CP 86h / RET NZ / CALL 02B9h` | `CP 87h / JP Z,3006h / RET` | The old second `CP 86h` follows 21FDh's JR NZ, so it could never match. It is now response function 88h: 86h's Y/N loop on the lower screen. |
| HOME | 1488h | dead SYSCON open path | `DI / LD HL,300Fh / CALL 03FCh / EI / RET C / JP 1465h` | The OPEN # trampoline. The module takes `f:` and `d:` specs and returns C. Anything else goes to the stock 1465h. |
| HOME | 1494h | 〃 | `DI / LD HL,3012h / CALL 03FCh / EI / RET C / JP 13BEh` | The CLOSE # trampoline, with the same pattern. |
| HOME | 14A0h | 〃 | `DI / LD HL,3009h / CALL 03FCh / EI / RET` | The output routine of every 'F' channel record. |
| HOME | 14A9h | 〃 | `DI / LD HL,300Ch / CALL 03FCh / EI / RET` | The input routine of every 'F' record. Records hold these fixed addresses, so nothing in a record moves. |
| HOME | 14B2h | 〃 | `POP HL / LD (65CEh),HL / POP HL / LD (5C3Dh),HL / LD SP,HL / EI / RET` | H_TRAP puts the bank stack back, re-enables interrupts and goes on to the previous ERR_SP handler. |
| HOME | 14BDh | `CALL 65D0h / POP DE / …` | `DI / LD HL,3018h / CALL 03FCh / EI / RET` | The OPEN # syntax trampoline, in the last 9 dead bytes. |
| HOME | 145Eh | `CALL 1465h` | `CALL 1488h` | OPEN # goes through the trampoline. 1465h has no other caller. |
| HOME | 1438h | `CALL 2569h` | `CALL 14BDh` | OPEN # syntax now parses `,mode[,reclen]`. Stock skipped everything after the comma, so a number's hidden five-byte form was never stored, and Report C followed at run time. |
| HOME | 13A5h | `CALL 13BEh` | `CALL 1494h` | CLOSE # goes through the trampoline. On an unknown channel letter, stock runs off the end of CL_TAB and crashes. |
| HOME | 03F3h | `LD (5DCDh),HL / LD HL,2000h / JP 03FCh` | `DI / LD (5DCDh),HL / LD HL,3015h / JR 041Ch` | This is the BEEPER thunk. BEEPER ends in EI, so the switch back to HOME ran with interrupts on. The editor clicks once per character, so INPUT # from a file crashed within a few hundred characters. |
| HOME | 041Ch | `00 00 10 d3 fe` (dead) | `CALL 03FCh / EI / RET` | The BEEPER thunk's tail. These bytes are left over from the relocated BEEPER, and nothing references them. |
| EXROM | 184Fh | `JP 23CDh` | `JP 301Bh` | BIOS C_END becomes [C_END2](#c_end2-a-timeout-is-j-not-f). 2.0's C_END returned A = 02h for a timeout and for status 3 alike, so callers reported a silent Pico as F. |
| EXROM | 20BEh | `CALL 1861h / JR 2108h` | `JP 301Eh / 00 00` | `tpi:tape` goes to [TAPE_MODE](#tape_mode-tpitape-keeps-the-printer-switch), which clears TPMODE bit 1 only. 2.0 set TPMODE to 0, turning the printer switch off too (#176). |
| HOME | 0065h | `20h` | `21h` | Version marker. |
| EXROM | 1852h | `LD BC,0020h` | `LD BC,0021h` | BIOS G_VERS. |
| EXROM | 1C7Eh | `"v2.0"` | `"v2.1"` | Boot banner. |

The build also checks anchor bytes elsewhere in the base ROM, including 23CDh,
227Fh and the BIOS table. A base that moves any of them fails the build
instead of jumping into the wrong code.

## ROM 2.1: the module at EXROM 3000h

The module is `src/rom/fdd/fddcmd.asm`. It is 1919 bytes, from 3000h to 377Eh,
with FDD_VERSION 8 and the signature `"FDDCMD"` at 30A8h. It starts with a jump
table, so the ROM patches point at fixed vectors rather than at routines that
move when the module is rebuilt.

### Vector table

| Vector | Target | Reached from |
|---|---|---|
| 3000h | `G_MAIN → FDD_MAIN` | HOME 25D6h, the disk-keyword hook |
| 3003h | `F_HOOK` | EXROM 01D2h, the SAVE/LOAD name check |
| 3006h | `LOWER_LOOP` | EXROM 2213h, response function 88h |
| 3009h | `G_OUT → CH_OUT` | HOME 14A0h, an F record's output |
| 300Ch | `G_IN → CH_IN` | HOME 14A9h, an F record's input |
| 300Fh | `G_OPEN → CH_OPEN_HOOK` | HOME 1488h, OPEN # |
| 3012h | `G_CLOSE → CH_CLOSE_HOOK` | HOME 1494h, CLOSE # |
| 3015h | `G_BEEP` | HOME 03F3h → 041Ch, BEEPER |
| 3018h | `G_OSYN → OPEN_SYNTAX` | HOME 14BDh, OPEN # syntax |
| 301Bh | `C_END2` | EXROM 184Fh, BIOS C_END |
| 301Eh | `TAPE_MODE` | EXROM 20BEh, `SAVE "tpi:tape"` |

### GUARDED and the HOME trap

Every entry that comes through the 03FCh thunk runs inside this frame. In both
ROMs, RST 8 ends with `LD SP,(ERR_SP)` and a RET with HOME paged, so the trap
has to live in HOME, at 14B2h.

```z80
G_MAIN: ld   hl,FDD_MAIN
        jr   GUARDED                ; G_OUT, G_IN, G_OPEN, G_OSYN and G_CLOSE are the same
GUARDED:
        push hl
        ld   hl,(5C3Dh)
        ex   (sp),hl                ; [old ERR_SP]
        push hl
        ld   hl,(65CEh)
        inc  hl
        inc  hl
        inc  hl
        inc  hl
        ex   (sp),hl                ; [the bank stack as it was before the thunk]
        push hl
        ld   hl,14B2h
        ex   (sp),hl                ; [H_TRAP]
        ld   (5C3Dh),sp
        call JP_HL
        di                          ; the switch back to HOME must not be interrupted
        inc  sp
        inc  sp
        inc  sp
        inc  sp                     ; drop the trap and the bank-stack value
        ex   (sp),hl
        ld   (5C3Dh),hl             ; restore ERR_SP
        pop  hl
        ret

; HOME 14B2h, H_TRAP -- an error inside the module lands here
        pop  hl
        ld   (65CEh),hl             ; the bank stack back as it was
        pop  hl
        ld   (5C3Dh),hl
        ld   sp,hl                  ; on to the previous handler, as RST 8 would have
        ei
        ret
```

### Disk commands

FDD_MAIN starts by setting IY to 5C3Ah. It then runs EI, because the hook
entered under DI, and CAT's "Scroll?" and the Y/N prompts wait with HALT.
Finally it dispatches on the token in B.

The two passes work like this:

- **Syntax pass** (FLAGS bit 7 clear): each command checks its string
  arguments through HOME's class-0Ah routine and returns.
- **Run-time pass**: the command builds a TPI command in the calculator-stack
  workspace. It sends it through the stock `SAVE "tpi:…"` machinery, entering
  at SESSION_NAMED (1AACh), which is just past the 6–31 character name gate.
  That lets an argument be up to 64 characters. The Pico's response and its
  scrolling display are the stock ones.

| BASIC | Sent as | Token |
|---|---|---|
| `CAT` | `tpi:dir` | CFh |
| `CAT ""` | `tpi:tapdir` (the mounted TAP) | CFh |
| `CAT x$` | `tpi:dir x` | CFh |
| `MOVE TO x$` | `tpi:cd x` (`""` sends `tpi:cd -`, the previous directory) | D1h |
| `MOVE a$ TO b$` | `tpi:copy a\|b` (a FAT name can't contain `\|`) | D1h |
| `ERASE x$` | `tpi:erase x` | D2h |
| `FORMAT x$` | `tpi:format x` | D0h |

### SAVE / LOAD "f:path"

F_HOOK (3208h) peeks at the name on the calculator stack. If the name doesn't
start with `f:` (in any case), it goes on to SESSION_SETUP (1A73h) exactly as
before. For an `f:` name, F_HOOK first makes a session id the way
SESSION_SETUP does: FRAMES+1, and never 0. It then sends `tpi:fopen <path>`
by hand through the BIOS (SEND_FOPEN, 3280h):

```
pre-header  'B', 00h (T-ADDR: a command), BANK, PMR1 lo = T-ADDR (0 SAVE, 1 LOAD, 2 VERIFY, 3 MERGE),
            PMR1 hi = the token after the name (CODE / SCREEN$ / DATA / LINE, else 0),
            PMR2 = session id, LEN lo, LEN hi = 0, XOR
            -> RX the preloaded status, BIOS_WF_NPH
body        'D', LEN, 00h, "tpi:fopen ", path, XOR
            -> BIOS C_END; an error status raises its report (F, Q, R ...)
```

After that, F_HOOK edits the name in place:

- For SAVE, it cuts the name to the path without `f:`, at most 10 characters.
- For LOAD, VERIFY and MERGE, it sets the length to 0, as for `LOAD ""`,
  because the one-shot tape holds one file.

Finally it clears MODE_SV bits 7–4, sets BC = 0011h and jumps to SAVE-ETC at
01D5h, the same place SESSION_SETUP's non-command exit goes. The Pico then
writes the SAVE to the path, or serves the file as a one-shot tape for the
LOAD.

### Response function 88h

The Pico sends 88h for the "Replace name? (Y/N)" prompt, when an `f:` SAVE
would overwrite an existing file. 88h is 86h's loop on the lower screen, so
the prompt doesn't draw over the picture that `SAVE "f:x" SCREEN$` is about to
save. The firmware sends 88h only after a `tpi:fopen`, and only this module
sends `tpi:fopen`.

```z80
LOWER_LOOP:                     ; 2213h: CP 87h / JP Z,3006h / RET, with A = function-1
        call 02B9h                  ; READ_STATUS (the first half of 01C3h)
        push af
        ld   a,0FDh                 ; stream -3, K: the lower screen (01C3h opens FEh)
        call 0426h                  ; OPEN_STREAM
        pop  af
        jp   21E6h                  ; 86h's loop body, which ends in its own POP AF / RET
```

### C_END2: a timeout is J, not F

```z80
C_END2: call BIOS_WF_NPH             ; 184Ch, as in 2.0
        jp   nc,227Fh               ; ready: v1.7's read-status tail
        cp   02h
        scf
        ret  nz                     ; 0Ch BREAK / 1Ch Pico reset, as before
        ld   a,09h                  ; the timeout: A = 09h -> Report J
        ret                         ; carry still set
```

On failure, A is now always ready for the status-to-report routine at 1BF3h:

- an error status: status−1 (01h R, 02h F … 09h J);
- a timeout: 09h;
- BREAK: 0Ch;
- a Pico reset: 1Ch.

0Ch and 1Ch can't be status−1 values, because the firmware's highest status is
11. WF_NPH itself is unchanged.

### PRELOAD: a pre-load of 0 is Report J

`SEND_FOPEN` and `CH_SEND` build their exchanges by hand through the BIOS, and
read the pre-load status with `BIOS_RX_A` -- and ignored it, so with no Pico (a
0) they went on into `BIOS_WF_NPH`'s timeout. They now call `PRELOAD` (3778h,
at the end of the module, so nothing else moved): `CALL BIOS_RX_A / RET NZ /
JP WF_FAIL`, Report J at once for a 0, as the ROM's own exchanges give it
(1A35h). Any other value goes on, as before: the ROM's "not 1 is a refusal"
would catch only a refused header LOAD's error, which the firmware stages for
two seconds for the LOAD's retry and which a channel command in that time
(an `ON ERR` handler doing `PRINT #`) would report as its own (#179).
`rom_preload_hosttest.py` runs it from the committed image.

### TAPE_MODE: tpi:tape keeps the printer switch

TPMODE (5DDBh) holds two switches: bit 1 sends LOAD and SAVE to the Pico,
bit 0 sends printing to it. `tpi:sdcard`, `tpi:picopt` and `tpi:ts2040` each
change their own bit, but `tpi:tape` (EXROM 20BEh, unchanged since v1.1) did
`CALL 1861h`, which is `XOR A` into S_MODE: TPMODE = 0. So `tpi:picopt`,
`tpi:tape`, `tpi:sdcard` quietly sent printing back to the 2068 (#176).

```z80
TAPE_MODE:                          ; 3021h, from JP TAPE_VEC at 20BEh
        ld   a,(5DDBh)              ; A held the length test's 8
        res  1,a                    ; cassette; bit 0, the printer, untouched
        jp   2105h                  ; CALL S_MODE / CALL 042Fh / JP 1B72h: "0 OK"
```

The five bytes at 20BEh can't hold the reload, the `RES` and the jump, so they
became `JP 301Eh` and two `00`s that nothing reaches. `rom_tpmode_hosttest.py`
runs the switch words from the committed image in the Z80 interpreter.

### File channels: OPEN #, PRINT #, INPUT #, CLOSE #

`OPEN #n,"f:path"[,"mode"[,reclen]]` builds an 'F' record in CHANS and points
stream n at it. A `"d:[pattern]"` spec opens a directory listing the same way.

Each record takes 200h bytes just before CHANS' closing 80h. The record is
placed so that both bytes of its STRMS offset are below 80h, because channel
select at 1239h tests D OR E. The allocation is a multiple of 256, so
reclaiming one record never changes the low byte of another's offset.

Record layout:

| Offset | Contents |
|---|---|
| +0 | output routine (14A0h) |
| +2 | input routine (14A9h) |
| +4 | `'F'` |
| +5 | stream |
| +6 | pad |
| +7 | bytes waiting to go out |
| +8 | bytes in |
| +9 | next byte in |
| +10 | flags (bit 0: record file) |
| +11 | 64-byte output buffer, then the 255-byte input buffer |

Each channel command is a 'B' command sent through the BIOS, with PMR1 = the
stream (CH_SEND, 3650h). Before its SYNC, CH_SEND waits up to about 1 s for
IDLE. The Pico answers a channel command with READY before it is IDLE again,
and a SYNC sent before then would be lost along with the pre-header behind it.

- `tpi:chopen` is sent on OPEN #.
- `tpi:chwr <hex>` is sent from CH_FLUSH, with the payload as hex so the
  command stays under 256 bytes. CH_FLUSH runs:
  - when 64 output bytes have built up;
  - at each CR in a record file, so a record that is too long gives Report Q
    on the PRINT that made it;
  - before each INPUT # fetch, so `INPUT #4;TAB n` seeks first;
  - on close.
- `tpi:chrd` is sent from CH_FETCH, with PMR2 = 255.
  - The reply is a status (1 = data, 7 = end of file, anything else a
    report), then a count, the bytes and an XOR.
  - The bytes are read with a 16-iteration delay between them (about 75 µs).
    This is the LOAD cadence for the Pico's 4-deep FIFO.
  - An XOR mismatch raises Report R.
  - At end of file, CH_IN returns NC NZ, which WAIT-KEY (11CFh) turns into
    Report 8.
- `tpi:chclose` is sent on CLOSE #, after a final flush. The record is then
  reclaimed, and C goes back to 13A8h, which only resets the STRMS entry.

Every exchange keeps CURCHL, because the command goes out in the middle of a
PRINT # or INPUT # statement.

G_BEEP (3029h) skips the editor's key click (HL = 00C8h) when CURCHL is an 'F'
record. It also puts DI back after BEEPER's EI.

### Routine index

| Addr | Routine | Addr | Routine |
|---|---|---|---|
| 3021h | TAPE_MODE | 332Dh | C_FAIL |
| 3029h | G_BEEP | 3338h | C_END2 |
| 3045h | G_MAIN … G_CLOSE (to 305Eh) | 334Fh | LOWER_LOOP |
| 3061h | GUARDED | 335Ch | CH_OPEN_HOOK |
| 3087h | FDD_MAIN | 348Eh | OPEN_SYNTAX |
| 30AFh | FDD_VERSION (08h) | 34B3h | CH_CLOSE_HOOK |
| 30B0h | FDD_CAT | 3562h | CH_OUT |
| 30D4h | FDD_ONE_ARG (ERASE, FORMAT) | 35A1h | CH_IN |
| 30EAh | FDD_MOVE | 35D4h | CH_FLUSH |
| 31E5h | TPI_SEND (→ SESSION_NAMED 1AACh) | 35ECh | CH_FETCH |
| 3208h | F_HOOK | 3641h | CH_STATUS |
| 3280h | SEND_FOPEN | 3650h | CH_SEND |
| 331Fh | WF_FAIL (J / D / T) | 3778h | PRELOAD (#179) |

## ZX Spectrum ROM v3

The base is the ZX v2 ROM (crc B3D40C73). v3 makes one fix and one addition.

### The fix: WAIT_RDY at 3874h

v2's WAIT_RDY used D as its outer counter and left D = 4. Its callers hold the
block length in DE: LD-BYTES (0563h), and SA-BYTES through 388Ah. So every
ZX48 LOAD and SAVE moved 0400h + (length AND FFh) bytes.

- A 6912-byte screen stopped after 1024 bytes, with Report R.
- A 17-byte header read 1041 bytes, filling zeros past the end of the block
  over whatever followed the header buffer. The checksum still passed.

The rewrite keeps the same entry point, the same 22 bytes and the same ~3.8 s
timeout, but it counts with B and HL. Both callers set B and HL again before
they use them, and DE and IX are kept.

```z80
WAIT_RDY_V3:                    ; 3874h; carry set = READY, clear = timed out; corrupts A, B, HL
        ld   b,4                    ; 4 x 65536 polls
.outer: ld   hl,0
.poll:  in   a,(0Fh)
        and  40h
        jr   nz,.ready
        dec  hl
        ld   a,h
        or   l                      ; also clears carry
        jr   nz,.poll
        djnz .outer
        ret
.ready: scf
        ret                         ; ends before SAVE_WAIT at 388Ah
```

### The addition: LOAD "tpi:name" in ZX48 mode

`LOAD "tpi:name"` mounts a file on the TS-Pico the way it does in 2068 mode.
A Spectrum program can then be mounted and loaded without going back to the
2068 ROM.

SAVE, LOAD, VERIFY and MERGE all fetch their name at 0631h, in SA-ALL, with
`CALL STK-FETCH`. That call now goes to TPI_CHK at 38B8h, before the ROM cuts
the name to 10 characters. TPI_CHK calls STK-FETCH itself, then:

- for any name that doesn't start with `tpi:` (in any case), it returns
  unchanged;
- for a `tpi:` name, it drops SA-ALL's return address, so the final RET goes
  to STMT-RET, and runs TPI_CMD.

TPI_CMD's exchange with the Pico:

```
Z80 ->  OUT (0Eh),'T'                                   ; 54h
Z80 <-  WAIT_RDY (~3.8 s, else J: no Pico, or firmware without 'T')
Z80 ->  op (T-ADDR: 0 SAVE, 1 LOAD, 2 VERIFY, 3 MERGE), length, name after "tpi:"
        ; each byte followed by ~50 us (TPI_OUT/TPI_DLY) for the Pico's 4-deep RX FIFO
Z80 <-  READY, up to 128 x ~0.24 s (~30 s; mounting copies the file to flash),
        BREAK_KEY (1F54h) between rounds -> Report D
Z80 <-  status: FFh = OK, else an ERR_NR (0Eh F, 19h Q ...)
Z80 <-  message length; the message into the workspace (RST 30h, BC-SPACES),
        then CHAN_OPEN 2 / PR_STRING / CR on the upper screen
```

The statement then ends with "0 OK" and the program goes on, or with the
report. TPI_ERR raises a report by hand, the way RST 8 would:

1. `LD (IY+0),A`
2. copy CH_ADD to X_PTR
3. `LD SP,(ERR_SP)`
4. `JP 16C5h` (SET_STK)

The new code runs from 38B8h to below 3D00h, and the banner byte at 38B7h
changes from '2' to '3'. Any other LOAD, SAVE, VERIFY or MERGE works exactly as
in v2.

## Version bytes

| Where | v1.7 | 2.0 | 2.1 |
|---|---|---|---|
| HOME 0065h (`PEEK 101`) | 17h | 20h | 21h |
| BIOS G_VERS (EXROM 1852h, `LD BC,nnnn`) | 0017h | 0020h | 0021h |
| Boot line (EXROM 1C6Ch) | v1.7 | `" 2026 TS-Pico ROM v2.0"` | `"… v2.1"` |
| Module FDD_VERSION (EXROM 30AFh) | — | — | 08h |

v1.1 reads 15h at 0065h.

## Sources

| File | What it does |
|---|---|
| [`src/rom/patches/tspico-sync.asm`](../src/rom/patches/tspico-sync.asm) | ROM 2.0, as patches over `src/rom/TSPICO.ROM` (v1.7). [`src/test/rom_sync_hosttest.py`](../src/test/rom_sync_hosttest.py) checks its sites and the v1.7 bytes. |
| [`src/rom/fdd/fddcmd.asm`](../src/rom/fdd/fddcmd.asm) | The 2.1 module. |
| [`tools/build-rom.py`](../tools/build-rom.py) | Assembles the module, splices it in at EXROM 3000h and applies the 2.1 patches. Each patch states its before and after bytes, and the build fails if the base doesn't match. |
| [`src/rom/patches/tspico-zx48-v3.asm`](../src/rom/patches/tspico-zx48-v3.asm) | ZX v3. [`src/test/rom_zx48_hosttest.py`](../src/test/rom_zx48_hosttest.py) checks it. |
| [`tools/build-rom.sh`](../tools/build-rom.sh) | Builds all of them (needs sjasmplus 1.20+). |

The firmware side of each change is in `src/TS/`: the SYNC capture, the IDLE
and RECOVERED bits, `tpi:fopen`, the channel commands, and the 'T' command for
ZX48 mode. [PROTOCOL.md](PROTOCOL.md) describes it byte for byte.
