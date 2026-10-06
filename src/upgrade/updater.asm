; =============================================================================
; TS-Pico ROM updater -- rewrites flash slots 1 (TS-2068 ROM) and 0 (ZX ROM)
; =============================================================================
;
; Build:  tools/build-upgrade.py    (sjasmplus; also makes the .tap and the
;                                    upgrade UF2's data module)
; Runs on the ORIGINAL slot-0 Spectrum ROM, which every shipped flash image
; has: the user upgrades the Pico to the upgrade UF2, types OUT 244,3 on the
; 2068 (the Spectrum ROM, whatever the 2068 ROM is) and LOAD "". The upgrade
; UF2 streams this program's tape; its BASIC loader does
;       CLEAR 24575: LOAD ""CODE: RANDOMIZE USR 24576
;
; Why it can rewrite the ROM it is running under: the flash chip (SST39SF040)
; is busy for the whole of an erase or a byte program, and reads return
; status bits from EVERY slot meanwhile -- so nothing may be fetched from the
; chip until it's done. This code runs from RAM with interrupts off, calls no
; ROM routine, prints with its own copy of the font, and never goes back to a
; ROM it has touched. The flash is reached through the TS-2068 dock bank, the
; way romupdate.tap (basic/assets/) does it:
;
;   slot 1 (odd, 32K)   HSR = F6h: chunks 1,2 (for the command addresses
;                       5555h/2AAAh) and 4-7 = the slot, at 8000h-FFFFh
;   slot 0 (even, 16K)  HSR = 07h: chunks 0-2; the ZX ROM is the lower 16K,
;                       0000h-3FFFh; the upper half (zeros) isn't touched
;
; Chunk 3 (6000h-7FFFh) is RAM under both, so the code, the font copy, the
; buffer and the stack all live there. The screen (chunk 2) is only written
; with HSR = 0.
;
; Order: slot 1 first. Until it is written and verified, slot 0 -- the
; Spectrum ROM, the only way back in -- is untouched, so any failure there
; returns to BASIC and LOAD "" tries again.
;
; The Pico: a request is OUT (0Fh),cmd (the port-0Fh write marks it: the
; tape stream never has one), its argument bytes on 0Eh ~50 us apart, then
; READY (0Fh bit 6) when the reply is queued; replies are read ~44 us apart,
; the cadence LOAD already proved.
;
;   'I'              -> 'T','P', version, 0      hello; the Pico stops the tape
;   'R' image,block  -> 256 bytes + their XOR    image 1 = slot 1, 0 = slot 0
;   'S' code,arg     -> 1 byte                   progress, for the web page
;
; Status codes ('S'): 'P' phase start (arg image), 'E' erased, 'W' block
; written (arg block), 'V' image verified, 'D' done, 'X' failed (arg reason).
; =============================================================================

PORT_DATA       equ 0Eh
PORT_STAT       equ 0Fh
PORT_HSR        equ 0F4h

ROMFONT         equ 3D00h       ; the Spectrum ROM's character set, 20h-7Fh
SCREEN          equ 4000h
ATTRS           equ 5800h

CODE_AT         equ 6000h
FONT            equ 7000h       ; 96 x 8 bytes
BUF             equ 7400h       ; one 256-byte block (+1: its XOR)
; (VARS equ 7600h used to be here, unused: the variables live in the code block)
STACK           equ 7FF0h

HSR_SLOT1       equ 0F6h
HSR_SLOT0       equ 07h

; failure reasons ('X' arg), also the message table index
X_PICO          equ 1           ; no answer from the Pico
X_BLOCKED       equ 2           ; the erase didn't take: P10 not fitted
X_XFER          equ 3           ; a block kept failing its XOR check
X_WRITE         equ 4           ; a byte didn't program / a block didn't verify

        OUTPUT "updater.bin"
        ORG CODE_AT

start:
        di
        ld (saved_sp),sp
        ld sp,STACK
        xor a
        ld (touched),a
        ld hl,ROMFONT                   ; the ROM is still intact: copy its font
        ld de,FONT
        ld bc,768
        ldir
        ld hl,FONT + (7Fh - 20h) * 8    ; glyph 7Fh: a solid cell, for the progress bars
        ld b,8
.solid: ld (hl),0FFh
        inc hl
        djnz .solid
        call cls
        ld hl,m_title
        call print_msgs

        ld a,'I'                        ; hello: the Pico stops the tape
        call request
        jr nc,.nopico
        ld hl,BUF
        ld de,4
        call recv
        ld a,(BUF)
        cp 'T'
        jr nz,.nopico
        ld a,(BUF+1)
        cp 'P'
        jr z,.go
.nopico:
        ld a,X_PICO
        jp fail

.go:    ld a,1                          ; the TS-2068 ROM, slot 1
        call phase
        ld a,0                          ; the ZX Spectrum ROM, slot 0
        call phase
        ld a,'D'
        ld c,0
        call status
        ld hl,m_done
        call print_msgs
        di
.stop:  halt                            ; DI + HALT: stays here, harmlessly
        jr .stop

; ---- one image: erase, then block by block fetch, program, verify ----------
; In: A = image (1: slot 1, 32K; 0: slot 0, lower 16K). Two tries.
phase:
        ld (img),a
        ld a,2
        ld (tries),a
.again:
        ld a,(img)
        ld c,a
        ld a,'P'
        call status
        ld a,(img)
        or a
        ld a,HSR_SLOT1
        ld hl,8000h
        ld b,8                          ; 8 x 4K sectors
        jr nz,.map
        ld a,HSR_SLOT0
        ld hl,0000h
        ld b,4
.map:   ld (hsr),a
        ld a,(img)
        or a
        jr nz,.not0
        ld a,1                          ; slot 0 is about to be erased: no way back to BASIC
        ld (zx_touched),a
.not0:  ld a,(hsr)
        ld (base),hl
        ld a,b
        add a,a
        add a,a
        add a,a
        add a,a                         ; sectors x 16 = blocks
        ld (nblocks),a
        ld a,(hsr)
        out (PORT_HSR),a
.erase: call erase
        jp nc,.eraseerr
        ld de,1000h
        add hl,de
        djnz .erase
        xor a
        out (PORT_HSR),a
        ld a,(img)
        ld c,a
        ld a,'E'
        call status

        xor a
        ld (blk),a
.block: call fetch                      ; BUF = block (blk) of image (img)
        jr nc,.xfererr
        ld a,(hsr)
        out (PORT_HSR),a
        ld hl,(base)
        ld a,(blk)
        add a,h
        ld h,a                          ; HL = base + blk x 256
        push hl
        ld de,BUF
        ld b,0
.prog:  ld a,(de)
        call program
        jr nc,.progerr
        inc hl
        inc de
        djnz .prog
        pop hl
        ld de,BUF
        ld b,0
.verify:
        ld a,(de)
        cp (hl)
        jr nz,.writeerr
        inc hl
        inc de
        djnz .verify
        xor a
        out (PORT_HSR),a
        call tick                       ; one progress cell
        ld a,(blk)
        ld c,a
        ld a,'W'
        call status
        ld a,(blk)
        inc a
        ld (blk),a
        ld hl,nblocks
        cp (hl)
        jr nz,.block
        ld a,(img)
        ld c,a
        ld a,'V'
        jp status                       ; and return (status's carry: nobody reads it)

.progerr:
        pop hl
.writeerr:
        xor a
        out (PORT_HSR),a
        ld a,(tries)
        dec a
        ld (tries),a
        jp nz,.again                    ; erase again and start over
        ld a,X_WRITE
        jp fail
.xfererr:
        ld a,X_XFER
        jp fail
.eraseerr:
        xor a
        out (PORT_HSR),a
        ld a,(touched)
        or a
        ld a,X_BLOCKED                  ; the first erase didn't take: nothing changed
        jr z,.blocked
        ld a,X_WRITE
.blocked:
        jp fail

; ---- flash: erase the 4K sector at HL (HSR mapped) --------------------------
; Carry set = it reads FFh now. A sector that read FFh before and still does
; proves nothing, but then programming it fails straight away, still having
; changed nothing. Keeps BC, DE, HL.
erase:
        push de
        ld a,(hl)
        cp 0FFh
        jr z,.cmd
        ld a,1                          ; it held data: if it reads FFh after, we changed it
        ld (was_data),a
.cmd:   ld a,0AAh
        ld (5555h),a
        ld a,055h
        ld (2AAAh),a
        ld a,080h
        ld (5555h),a
        ld a,0AAh
        ld (5555h),a
        ld a,055h
        ld (2AAAh),a
        ld (hl),30h                     ; sector erase
        ld de,0                         ; DQ7 polling: 0 while erasing, ~0.6 s at most
.poll:  ld a,(hl)
        rla
        jr c,.done
        dec de
        ld a,d
        or e
        jr nz,.poll
.done:  ld a,(hl)
        pop de
        cp 0FFh
        jr nz,.bad
        ld a,(was_data)
        or a
        jr z,.ok
        ld a,1
        ld (touched),a
.ok:    scf
        ret
.bad:   or a                            ; carry clear
        ret

; ---- flash: program A at HL (HSR mapped). Carry set = it reads back. --------
; Keeps BC, DE, HL.
program:
        push bc
        ld c,a
        ld a,0AAh
        ld (5555h),a
        ld a,055h
        ld (2AAAh),a
        ld a,0A0h
        ld (5555h),a
        ld (hl),c
        ld b,0                          ; DQ7 polling, 256 reads (~20 us is typical)
.poll:  ld a,(hl)
        xor c
        and 80h
        jr z,.done
        djnz .poll
.done:  ld a,(hl)
        cp c
        pop bc
        scf
        ret z
        or a
        ret

; ---- the Pico -------------------------------------------------------------------
; request: OUT (0Fh),A, then wait for READY. Carry set = ready.
request:
        out (PORT_STAT),a
; wait_ready: poll 0Fh bit 6, ~4 s. Carry set = READY. Keeps DE, HL.
wait_ready:
        push de
        ld b,4
.outer: ld de,0
.poll:  in a,(PORT_STAT)
        and 40h
        jr nz,.ready
        dec de
        ld a,d
        or e
        jr nz,.poll
        djnz .outer
        pop de
        ret                             ; carry clear (from OR)
.ready: pop de
        scf
        ret

; send: OUT (0Eh),A then ~50 us, for the Pico's 4-deep RX FIFO. Keeps BC.
send:   out (PORT_DATA),a
        push bc
        ld b,11
.d:     djnz .d
        pop bc
        ret

; recv: DE bytes to (HL), ~44 us apart (LOAD's cadence).
recv:   ld b,8
.d:     djnz .d
        in a,(PORT_DATA)
        ld (hl),a
        inc hl
        dec de
        ld a,d
        or e
        jr nz,recv
        ret

; status: tell the Pico code A, argument C. Keeps DE, HL.
status:
        push hl
        push de
        push af
        ld a,'S'
        out (PORT_STAT),a
        pop af
        call send                       ; the code
        ld a,c
        call send                       ; the argument
        call wait_ready
        jr nc,.done
        ld hl,ack                       ; the 1-byte answer
        ld de,1
        call recv
        scf
.done:  pop de
        pop hl
        ret

; fetch: BUF = block (blk) of image (img), XOR-checked, 5 tries. Carry set = ok.
fetch:
        ld a,5
        ld (xtries),a
.try:   ld a,'R'
        out (PORT_STAT),a
        ld a,(img)
        call send
        ld a,(blk)
        call send
        call wait_ready
        jr nc,.retry
        ld hl,BUF
        ld de,257
        call recv
        ld hl,BUF                       ; XOR of all 257 = 0
        ld b,0
        xor a
.x:     xor (hl)
        inc hl
        djnz .x
        xor (hl)
        jr nz,.retry
        scf
        ret
.retry: ld a,(xtries)
        dec a
        ld (xtries),a
        jr nz,.try
        or a
        ret

; ---- giving up ---------------------------------------------------------------
; A = reason. Before slot 0 is erased the Spectrum ROM is intact: back to
; BASIC (the Pico rewinds its tape; LOAD "" tries again). After, stop here.
fail:
        ld (reason),a
        xor a
        out (PORT_HSR),a
        ld a,(reason)
        ld c,a
        ld a,'X'
        call status
        ld a,(reason)
        add a,a
        ld e,a
        ld d,0
        ld hl,m_fail
        add hl,de
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        call print_msgs
        ld a,(img)                      ; slot 0 touched: its ROM is gone
        or a
        jr nz,.basic
        ld a,(zx_touched)
        or a
        jr z,.basic
        ld hl,m_stuck
        call print_msgs
        di
.stop:  halt
        jr .stop
.basic: ld a,03h                        ; the Spectrum ROM, as before
        out (PORT_HSR),a
        ld sp,(saved_sp)
        ei
        ret

; ---- screen --------------------------------------------------------------------
cls:    ld hl,SCREEN
        ld de,SCREEN+1
        ld bc,6143
        ld (hl),0
        ldir
        ld hl,ATTRS
        ld de,ATTRS+1
        ld bc,767
        ld (hl),38h                     ; black on white
        ldir
        ret

; print_msgs: HL -> a list of (row, text..., 0), ended by row FFh
print_msgs:
        ld a,(hl)
        cp 0FFh
        ret z
        inc hl
        ld b,a
        ld c,0
        call print_at
        jr print_msgs

; print_at: the 0-ended text at HL at row B, column C; HL after its 0
print_at:
        ld a,(hl)
        inc hl
        or a
        ret z
        call char_at
        inc c
        jr print_at

; char_at: character A at row B, column C. Keeps BC, HL.
char_at:
        push bc
        push hl
        sub 20h
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,FONT
        add hl,de                       ; HL = the glyph
        ld a,b                          ; DE = 4000h + (B & 18h) << 8 + (B & 7) << 5 + C
        and 18h
        or 40h
        ld d,a
        ld a,b
        and 07h
        rrca
        rrca
        rrca
        or c
        ld e,a
        ld b,8
.row:   ld a,(hl)
        ld (de),a
        inc hl
        inc d
        djnz .row
        pop hl
        pop bc
        ret

; tick: one filled cell per block; slot 1's 128 on rows 6-9, slot 0's 64 on 12-13
tick:   ld a,(blk)
        ld c,a
        and 1Fh
        ld e,a                          ; column
        ld a,c
        rlca
        rlca
        rlca
        and 07h                         ; row within the bar: blk / 32
        ld c,a
        ld a,(img)
        or a
        ld a,6
        jr nz,.row
        ld a,12
.row:   add a,c
        ld b,a
        ld c,e
        ld a,7Fh
        jp char_at

; ---- text ------------------------------------------------------------------------
m_title:
        db 0, "TS-Pico ROM update", 0
        db 2, "Don't turn off the 2068 or the", 0
        db 3, "Pico until this says DONE.", 0
        db 5, "TS-2068 ROM (slot 1):", 0
        db 11, "ZX Spectrum ROM (slot 0):", 0
        db 0FFh
m_done:
        db 16, "DONE. Finish on the web page,", 0
        db 17, "then turn the 2068 off and on.", 0
        db 0FFh
m_stuck:
        db 20, "The ZX ROM is incomplete, but", 0
        db 21, "the 2068 ROM is new: finish on", 0
        db 22, "the web page.", 0
        db 0FFh
m_fail: dw 0, f_pico, f_blocked, f_xfer, f_write
f_pico: db 16, "No answer from the TS-Pico.", 0
        db 17, "Is the upgrade firmware on it?", 0
        db 0FFh
f_blocked:
        db 16, "The flash can't be written:", 0
        db 17, "fit the P10 jumper, then", 0
        db 18, "LOAD \"\" again.", 0
        db 0FFh
f_xfer: db 16, "The TS-Pico's data keeps coming", 0
        db 17, "in wrong. LOAD \"\" to try again.", 0
        db 0FFh
f_write:
        db 16, "A write didn't take.", 0
        db 17, "LOAD \"\" to try again.", 0
        db 0FFh

; ---- variables (in the code's own space: the loader cleared to 5FFFh) --------
saved_sp:       dw 0
img:            db 0
blk:            db 0
nblocks:        db 0
hsr:            db 0
base:           dw 0
tries:          db 0
xtries:         db 0
reason:         db 0
touched:        db 0
was_data:       db 0
zx_touched:     db 0
ack:            db 0

code_end:
        ASSERT code_end <= FONT
