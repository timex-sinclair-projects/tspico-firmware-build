; =============================================================================
; TS-Pico ZX Spectrum ROM v3 -- LOAD "tpi:..." in ZX48 mode
; =============================================================================
;
; Build:  tools/build-rom.sh        (needs sjasmplus 1.20+)
; Input:  ROMs/TSPICO-ZX48-V2.BIN   the ZX v2 ROM, crc32 B3D40C73 (16K)
; Output: src/rom/TSPICO-ZX48-V3.BIN
;
; What it fixes: v2's WAIT_RDY left D = 4, so every ZX48 LOAD and SAVE moved
; 0400h + (length AND FFh) bytes -- see WAIT_RDY_V3 below.
;
; What it adds: LOAD "tpi:name" mounts a file on the TS-Pico, as it does in
; TS-2068 mode, so a Spectrum program can be mounted and loaded without
; going back to the 2068 ROM:
;
;       LOAD "tpi:manic.tap"        mount it (a number picks from the dir)
;       LOAD ""                     load it, as before
;
; How: SAVE/LOAD/VERIFY/MERGE all fetch their name at 0631h, in SA-ALL, with
; CALL STK-FETCH. That call now goes to TPI_CHK, which calls STK-FETCH and
; returns unchanged unless the name starts with "tpi:" (any case) -- every
; other name takes the stock path. This is before the ROM cuts a name to 10
; characters, so the whole name gets through. For a "tpi:" name, TPI_CMD
; finishes the statement itself:
;
;   Z80  -> OUT (0Eh),'T'                   (84)
;   Z80  <- waits for READY on 0Fh          (WAIT_RDY, ~3.8 s, else J)
;   Z80  -> op (0 SAVE, 1 LOAD, 2 VERIFY, 3 MERGE), length, the name after
;           "tpi:" -- about 54 us per byte, for the Pico's 4-deep RX FIFO
;   Z80  <- waits for READY again, up to ~30 s (mounting copies the file to
;           the Pico's flash), checking BREAK (Report D)
;   Z80  <- status: FFh = OK, else a report code (ERR_NR: 0Eh F, 19h Q...)
;   Z80  <- message length, then the message, read at the LOAD cadence into
;           the workspace, then printed on the upper screen
;
; then "0 OK" -- the program goes on -- or the report.
;
; Firmware without the 'T' command treats it as an unknown byte and never
; raises READY: Report J after ~3.8 s. Any other LOAD, SAVE, VERIFY or MERGE
; is exactly as in v2. Checked by src/test/rom_zx48_hosttest.py.
; =============================================================================

PORT_DATA       equ 0Eh
PORT_STATUS     equ 0Fh

; ---- v2 and stock 48K ROM routines and variables ----------------------------
WAIT_RDY        equ 3874h       ; poll 0Fh bit 6, carry = READY (~3.8 s); v3 below
STK_FETCH       equ 2BF1h       ; DE = start, BC = length of the string on the stack
CHAN_OPEN       equ 1601h       ; A = stream
PR_STRING       equ 203Ch       ; print BC bytes from DE
BREAK_KEY       equ 1F54h       ; NC = BREAK (CAPS SHIFT + SPACE) pressed
SET_STK         equ 16C5h       ; ERROR-2's tail
T_ADDR          equ 5C74h       ; SA-ALL: 0 SAVE, 1 LOAD, 2 VERIFY, 3 MERGE
CH_ADD          equ 5C5Dh
X_PTR           equ 5C5Fh
ERR_SP          equ 5C3Dh

ERR_D           equ 0Ch         ; D BREAK - CONT repeats
ERR_J           equ 12h         ; J Invalid I/O device

NEW_CODE        equ 38B8h       ; free (FFh) after v2's banner, to 3CFFh

        OUTPUT "TSPICO-ZX48-V3.BIN"
        INCBIN "../../ROMs/TSPICO-ZX48-V2.BIN"

        MACRO AT addr
        FPOS addr
        ORG addr
        ENDM

; ---- the one call site ------------------------------------------------------
        AT 0631h
        call TPI_CHK            ; was CALL STK_FETCH (CD F1 2B)

; ---- WAIT_RDY, rewritten: v2's left D = 4 ---------------------------------------
; v2's WAIT_RDY used D as its outer counter. Its callers, LD-BYTES ($0563) and
; SA-BYTES (via $388A), hold the block length in DE, so every ZX48 LOAD and
; SAVE moved 0400h + (length AND FFh) bytes: a 6912-byte block stopped after
; 1024 (Report R), and a 17-byte header read 1041 bytes, zeros past the end
; of the block (the checksum still passed), over whatever followed the header
; buffer. Found on hardware 2026-09-27. Same entry, same size (fits the old
; 22 bytes), same ~3.8 s timeout; the counters are now B and HL, which both
; callers set again before they use them. DE and IX are kept.
; Out: carry set = READY; carry clear = timed out. Corrupts A, B, HL.
        AT 3874h
WAIT_RDY_V3:
        ld b,4                  ; 4 x 65536 polls
.outer: ld hl,0
.poll:  in a,(PORT_STATUS)
        and 40h                 ; bit 6 = READY
        jr nz,.ready
        dec hl
        ld a,h
        or l                    ; also leaves carry clear
        jr nz,.poll
        djnz .outer
        ret                     ; timed out, carry clear
.ready: scf
        ret
        ASSERT $ <= 388Ah       ; SAVE_WAIT at 388Ah is kept

; ---- banner: "... TS-Pico ZX v2" -> "v3" --------------------------------------
        AT 38B7h
        db '3' | 80h

; =============================================================================
        AT NEW_CODE

; TPI_CHK: STK-FETCH, and back to SA-ALL unless the name is "tpi:<something>".
TPI_CHK:
        call STK_FETCH
        ld a,b
        or a
        ret nz                  ; 256+ characters: not ours
        ld a,c
        cp 5
        ret c                   ; "tpi:" and at least one more
        push de
        push bc
        ld hl,TPI_TXT
        ld b,4
.cmp:   ld a,(de)
        or 20h                  ; any case; ':' stays ':'
        cp (hl)
        jr nz,.stock
        inc de
        inc hl
        djnz .cmp
        pop bc
        pop hl
        pop af                  ; drop the return into SA-ALL: RET now goes to STMT-RET
        jr TPI_CMD              ; DE = the name after "tpi:", C = whole length
.stock: pop bc
        pop de
        ret

TPI_TXT:
        db "tpi:"

; TPI_CMD: send the command, show the Pico's message, OK or report.
TPI_CMD:
        ld a,c
        sub 4
        ld c,a                  ; C = length of the name after "tpi:"
        ld a,'T'
        out (PORT_DATA),a
        push de
        push bc
        call WAIT_RDY           ; corrupts A, B, HL
        pop bc
        pop de
        ld a,ERR_J
        jr nc,TPI_ERR           ; no Pico, or firmware without 'T'
        ld a,(T_ADDR)
        call TPI_OUT            ; op
        ld a,c
        call TPI_OUT            ; length
        ld b,c
.name:  ld a,(de)
        call TPI_OUT
        inc de
        djnz .name

        ld d,128                ; 128 x ~0.24 s
.wait:  ld bc,16384
.poll:  in a,(PORT_STATUS)
        and 40h
        jr nz,.reply
        dec bc
        ld a,b
        or c
        jr nz,.poll
        call BREAK_KEY
        ld a,ERR_D
        jr nc,TPI_ERR
        dec d
        jr nz,.wait
        ld a,ERR_J
        jr TPI_ERR

.reply: in a,(PORT_DATA)        ; status
        push af
        call TPI_DLY
        in a,(PORT_DATA)        ; message length
        or a
        jr z,.done
        ld c,a
        ld b,0
        rst 30h                 ; BC-SPACES: DE = room in the workspace, BC kept
        push de
        push bc
        ld b,c
.read:  call TPI_DLY
        in a,(PORT_DATA)
        ld (de),a
        inc de
        djnz .read
        ld a,2
        call CHAN_OPEN          ; the upper screen
        pop bc
        pop de
        call PR_STRING
        ld a,0Dh
        rst 10h
.done:  pop af
        cp 0FFh
        ret z                   ; 0 OK: on to the next statement

; TPI_ERR: raise the report in A, as RST 8 would.
TPI_ERR:
        ld (iy+0),a             ; ERR_NR
        ld hl,(CH_ADD)
        ld (X_PTR),hl
        ld sp,(ERR_SP)
        jp SET_STK

; TPI_OUT: one byte to the Pico, then ~50 us for its RX FIFO. Keeps BC, DE.
TPI_OUT:
        out (PORT_DATA),a
; TPI_DLY: ~45 us. Keeps DE, and B and C.
TPI_DLY:
        push bc
        ld b,10
.d:     djnz .d
        pop bc
        ret

TPI_END:
        ASSERT TPI_END <= 3D00h
