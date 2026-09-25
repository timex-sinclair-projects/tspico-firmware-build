; =============================================================================
; TS-Pico 1.8b "sync" TEST ROM -- patches applied on top of v1.7 TSPICO.ROM
; =============================================================================
;
; Build:  tools/build-rom.sh        (needs sjasmplus 1.20+)
; Input:  src/rom/TSPICO.ROM        v1.7, crc32 09D4CA63 (HOME 16K + EXROM 16K)
; Output: src/rom/TSPICO-SYNC.ROM   test build -- NOT the shipping slot-1 ROM
;
; What it adds (see the "TS-Pico BREAK abort proposal", version 4+):
;
;   1. SYNC: every Pico transaction starts with OUT (0Fh),03h and a short wait
;      for READY+IDLE, so the Pico is back at idle whatever happened before.
;   2. BREAK: CAPS SHIFT+SPACE sends the same abort byte, waits for the Pico to
;      clean up, and raises Report D instead of falling into Report J.
;   3. BREAK is checked every 256 bytes inside the SAVE and LOAD byte loops,
;      and inside the Y/N / key-wait prompts (functions 0x82, 0x84, 0x86).
;   4. Status bit 2 (RECOVERED, active low) seen while waiting for READY raises
;      a new report, "T TS-Pico reset, try again" (ERR_NR 1Ch).
;   5. The Pico Interface BIOS keeps its documented contract: WF_NPH (1840h
;      table, entry 184Ch) and C_END (184Ah) return carry set on failure
;      instead of raising a report, with A = 02h timeout (as before),
;      0Ch BREAK, 1Ch Pico reset the transaction. BREAK still sends the abort
;      byte so the Pico cleans up.
;
; REQUIRES matching firmware. Old firmware reads the SYNC byte as the first
; byte of a command and every command after it is misaligned.
;
; Addresses are Z80 addresses. The file is HOME at offset 0, EXROM at 4000h,
; and file offset == Z80 address within each half. All sites and the v1.7
; bytes they replace are checked by src/test/rom_sync_hosttest.py.
; =============================================================================

; ---- protocol ---------------------------------------------------------------
ABORT_BYTE      equ 03h         ; Ctrl-C: SYNC and BREAK-abort, written to 0Fh
PORT_DATA       equ 0Eh
PORT_STATUS     equ 0Fh
ST_READY        equ 6           ; 1 = ready (unchanged)
ST_IDLE         equ 3           ; 1 = no transaction open (active high)
ST_RECOVERED    equ 2           ; 0 = Pico dropped a transaction (active low)
                                ; 0xFF from old firmware = ready, idle, not
                                ; recovered, so a missing bit never misfires

; ---- BASIC reports (ERR_NR = code byte after RST 8) -------------------------
ERR_D_BREAK     equ 0Ch         ; D BREAK - CONT repeats
ERR_T_PICO      equ 1Ch         ; T TS-Pico reset, try again   (new)

; ---- existing v1.7 routines -------------------------------------------------
READ_STATUS     equ 0655h       ; EXROM: BREAK check, then IN A,(0Fh)
CHECK_BREAK     equ 069Fh       ; EXROM: debounced SPACE, then CAPS; NC = BREAK
C_END_TAIL      equ 227Fh       ; EXROM: 2279h's read-status tail, after its wait
POLL_KEYPRESS   equ 0546h       ; EXROM: Z = no key yet
TSPICO_WRITE    equ 229Dh       ; EXROM: OUT (0Eh),A / AND A / RET
EX_PO_MSG       equ 03EDh       ; EXROM->HOME PO-MSG: A = entry, DE = table
EX_TO_HOME      equ 03DDh       ; EXROM->HOME returning thunk (PUSH IX/EXX/LD HL,t/JP)
HOME_TO_EX      equ 03FCh       ; HOME->EXROM returning thunk (LD (5DCD),HL/LD HL,t/CALL)
HOME_MSG_TABLE  equ 0F65h       ; HOME report text table (dummy first entry)
HOME_MSG_SEP    equ 1115h       ; HOME ", " separator (dummy first entry)
HOME_RST10      equ 0010h       ; HOME print A

EXROM           equ 4000h       ; file offset of the EXROM half

        OUTPUT "TSPICO-SYNC.ROM"
        INCBIN "TSPICO.ROM"

        MACRO HOMEAT addr
        FPOS addr
        ORG addr
        ENDM

        MACRO EXAT addr
        FPOS EXROM+addr
        ORG addr
        ENDM

; =============================================================================
; HOME patches
; =============================================================================

        HOMEAT 0065h
        db 18h                  ; HOME version marker (v1.7 = 17h)

; Report printer. v1.7:  0F12 LD A,B / LD DE,0F65h / CALL 073Fh
;                        0F19 XOR A / LD DE,1115h / CALL 073Fh
; Hand the text (report message + ", ") to EXROM, which knows code 1Ch.
        HOMEAT 0F12h
        ld a,b                  ; A = ERR_NR+1 (unchanged)
        ld (5DCDh),hl           ; HOME->EXROM thunk convention
        ld hl,EX_REPORT_MSG
        call HOME_TO_EX
        nop
        nop
        nop
        nop
        ASSERT $ == 0F20h

; =============================================================================
; EXROM version marks
; =============================================================================

        EXAT 1853h
        db 18h                  ; BIOS G_VERS: LD BC,0018h (v1.7 = 0017h)

        EXAT 1C6Ch              ; boot copyright line, same length as v1.7's
        db " 2026 TS-Pico 1.8b sync t", "1" | 80h
        ASSERT $ == 1C86h

; =============================================================================
; EXROM call-site patches (each replaces one 3-byte instruction)
; =============================================================================

; First write of each transaction: CALL 229Dh -> CALL SYNC_WRITE
        EXAT 189Ah              ; SAVE header pre-header
        call SYNC_WRITE
        EXAT 1998h              ; LOAD/VERIFY/MERGE, every block
        call SYNC_WRITE
        EXAT 1BAAh              ; TPI:/NET: command
        call SYNC_WRITE
        EXAT 1651h              ; LPRINT / LLIST character
        call SYNC_WRITE
        EXAT 16F6h              ; COPY in Pico printer mode
        call SYNC_WRITE

; BREAK found by the ready-wait. v1.7: POP BC / JP 1A61h (-> Report J)
        EXAT 06AAh
        jp BRK_ABORT
        nop
        ASSERT $ == 06AEh

; Byte loops. v1.7: INC IX / DEC DE at 18FDh (SAVE) and 19EFh (LOAD)
        EXAT 18FDh
        call STEP
        EXAT 19EFh
        call STEP

; Key wait (functions 0x82/0x84/0x86). v1.7: CALL 0546h
        EXAT 0479h
        call KEYWAIT

; WAIT_PICO_READY's status read. v1.7: CALL 0655h
        EXAT 1A58h
        call RD_STATUS

; Pico Interface BIOS. v1.7: 184C JP 1A54h (WF_NPH), 184F JP 2279h (C_END)
        EXAT 184Ch
        jp BIOS_WF_NPH
        EXAT 184Fh
        jp BIOS_C_END

; =============================================================================
; New EXROM code, in the free 0xFF space after v1.7's last routine (22FDh)
; =============================================================================

        EXAT 2300h

; SYNC_WRITE -- start a transaction: SYNC, wait, then the original first write.
; Preserves every register (AF' is live in LOAD).
SYNC_WRITE:
        push af
        push bc
        ld a,ABORT_BYTE
        out (PORT_STATUS),a
        call SYNC_WAIT
        pop bc
        pop af
        jp TSPICO_WRITE

; SYNC_WAIT -- poll until READY and IDLE, or give up after ~1.05 s
; (65536 x 56 T). Carries on either way: a Pico that never answers still gets
; today's Report J from the next ready-wait. Clobbers A, F, BC.
SYNC_WAIT:
        ld bc,0
.poll:  in a,(PORT_STATUS)
        and (1 << ST_READY) | (1 << ST_IDLE)
        cp (1 << ST_READY) | (1 << ST_IDLE)
        ret z
        dec bc
        ld a,b
        or c
        jr nz,.poll
        ret

; BRK_ABORT -- the user pressed BREAK mid-transaction. Tell the Pico, let it
; clean up, then Report D. RST 8 reloads SP from ERR_SP and re-enables
; interrupts, so this is safe from any stack depth and from DI code.
BRK_ABORT:
        ld a,ABORT_BYTE
        out (PORT_STATUS),a
        call SYNC_WAIT
        rst 8
        db ERR_D_BREAK

; BRK_TEST -- carry clear = CAPS SHIFT + SPACE held. Reads the keyboard port
; directly (works with interrupts off) and honours the break-inhibit flag the
; way v1.7's 22F0h does. Clobbers A, F.
BRK_TEST:
        bit 6,(iy+7Dh)
        scf
        ret nz                  ; BREAK inhibited
        ld a,7Fh
        in a,(0FEh)             ; row 7FFE: bit 0 = SPACE
        rra
        ret c                   ; SPACE up
        ld a,0FEh
        in a,(0FEh)             ; row FEFE: bit 0 = CAPS SHIFT
        rra
        ret

; STEP -- replaces INC IX / DEC DE in the SAVE and LOAD loops. Checks BREAK
; each time the low byte of the counter reaches zero (every 256 bytes).
; Clobbers A, F only; the loops recompute both straight after.
STEP:
        inc ix
        dec de
        ld a,e
        or a
        ret nz
        call BRK_TEST
        ret c
        jp BRK_ABORT

; KEYWAIT -- BREAK check in front of POLL_KEYPRESS (same Z contract).
KEYWAIT:
        call BRK_TEST
        jp nc,BRK_ABORT
        jp POLL_KEYPRESS

; RD_STATUS -- WAIT_PICO_READY's status read. READY with RECOVERED low means
; the Pico gave up on this transaction on its own: report it at once instead
; of waiting ~20 s for Report J.
RD_STATUS:
        call READ_STATUS
        bit ST_READY,a
        ret z
        bit ST_RECOVERED,a
        ret nz
        rst 8
        db ERR_T_PICO

; EX_REPORT_MSG -- called from HOME's report printer through the 03FCh thunk,
; with A = ERR_NR+1. Prints the report text and the ", " that follows it.
EX_REPORT_MSG:
        cp ERR_T_PICO + 1
        jr z,.pico
        ld de,HOME_MSG_TABLE
        call EX_PO_MSG
        jr .sep
.pico:  ld hl,MSG_PICO_RESET
.chr:   ld a,(hl)
        and 7Fh
        push hl
        call EX_HOME_PRINT
        pop hl
        bit 7,(hl)
        inc hl
        jr z,.chr
.sep:   xor a
        ld de,HOME_MSG_SEP
        jp EX_PO_MSG

; EX_HOME_PRINT -- print A through HOME's RST 10.
EX_HOME_PRINT:
        push ix
        exx
        ld hl,HOME_RST10
        jp EX_TO_HOME

MSG_PICO_RESET:
        db "TS-Pico reset, try agai", "n" | 80h

; BIOS_WF_NPH -- WAIT_PICO_READY for machine-code callers of the BIOS. Same
; ~19.9 s budget and debounced BREAK test as v1.7, but never raises a report:
;   ready      carry clear, A and BC preserved (as v1.7)
;   timeout    carry set, A = 02h (as v1.7), BC preserved
;   BREAK      abort byte to the Pico, carry set, A = 0Ch
;   RECOVERED  carry set, A = 1Ch
BIOS_WF_NPH:
        push af
        push bc
        ld b,0E2h
.poll:  call CHECK_BREAK
        jr nc,.brk
        in a,(PORT_STATUS)
        bit ST_READY,a
        jr nz,.ready
        djnz .poll
        ld c,02h
        jr .fail
.ready: bit ST_RECOVERED,a
        ld c,ERR_T_PICO
        jr z,.fail
        pop bc
        pop af
        scf
        ccf
        ret
.brk:   ld a,ABORT_BYTE
        out (PORT_STATUS),a
        call SYNC_WAIT
        ld c,ERR_D_BREAK
.fail:  ld a,c
        pop bc
        inc sp                  ; drop the saved AF
        inc sp
        scf
        ret

; BIOS_C_END -- C_END (2279h) with the BIOS wait: carry and A from
; BIOS_WF_NPH on failure, otherwise v1.7's read-status tail unchanged.
BIOS_C_END:
        call BIOS_WF_NPH
        ret c
        jp C_END_TAIL

NEW_CODE_END:
        ASSERT NEW_CODE_END < 4000h
