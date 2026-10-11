; ramtest: is this 2068's own RAM sound? Sinistar crashed on two TS-Pico
; boards with a stack byte at 7Fxxh read back with D1 lost, while the bus
; tests (bustest.asm) found nothing; so test the RAM itself, where its stack,
; IM2 table and variables live (chunk 3) and above.
;
; March C- over 5F00h-FFFFh, with eight data backgrounds (00, FF, 55, AA,
; 33, CC, 0F, F0), then an address-in-data pass (lo ^ hi), repeated forever
; with interrupts off and the display in ECM (DECR 2), as Sinistar runs it,
; so the SCLD's fetches load the RAM as in the game. It overwrites BASIC and
; the system variables, so it never returns: the results are drawn on the
; screen with the ROM's font, updated after every pass. Reset the 2068 to
; finish.
;
;   row 0  RAMTEST  pass N   (shown in the normal display for ~1.5 s after
;          each pass, then back to ECM for the next)
;   row 2  errors NNNN  bits XX     (XX: every data bit that ever failed)
;   row 4  D7..D0 errors per bit
;   rows 7-22  the first 16 errors: address, expected, got, pass
;
; LOAD ""CODE 32768, RANDOMIZE USR 32768: a stub there copies the test down
; to 5B00h (the printer buffer and system variables, which it then owns) and
; runs it there, out of the range it tests.
;
;   sjasmplus ramtest.asm   ->   ramtest.bin

        DEVICE NOSLOT64K
        org 8000h
stub:   di
        ld hl,body
        ld de,5B00h
        ld bc,body_end - body
        ldir
        jp start
body:
        DISP 5B00h

LO          equ 5F00h       ; first byte tested
PORT_DECR   equ 0FFh
FONT        equ 3D00h       ; the ROM's character set, from the space

; variables, past the code (5B00h-5EFFh is ours: not tested)
pass        equ 5D80h       ; 2
errs        equ 5D82h       ; 2
bits        equ 5D84h       ; 1  OR of every (got ^ expected)
nlog        equ 5D85h       ; 1
bg          equ 5D86h       ; 1  the data background
perbit      equ 5D88h       ; 2 x 8  errors per bit, D0 first
elog        equ 5DA0h       ; 16 x 6: addr, exp, got, pass (2)
STACK       equ 5EFEh

start:
        di
        ld sp,STACK
        ld a,2
        out (PORT_DECR),a               ; ECM, as Sinistar
        xor a
        ld hl,pass
        ld b,elog + 96 - pass
.clr:   ld (hl),a
        inc hl
        djnz .clr
        call cls
        ld hl,5800h                     ; normal-mode attributes: black on white
        ld de,5801h
        ld bc,2FFh
        ld (hl),38h
        ldir
loop:
        ld hl,(pass)
        inc hl
        ld (pass),hl
        ld de,bglist
.bgl:   ld a,(de)
        ld (bg),a
        push de
        call march
        pop de
        inc de
        ld a,e
        cp bglist_end & 0FFh
        jr nz,.bgl
        call addrtest
        xor a
        out (PORT_DECR),a               ; normal display: the report readable
        call show
        ld bc,0                         ; ~1.5 s
        ld e,6
.w:     dec bc
        ld a,b
        or c
        jr nz,.w
        dec e
        jr nz,.w
        ld a,2
        out (PORT_DECR),a               ; ECM for the next pass
        jr loop

bglist: db 00h, 0FFh, 55h, 0AAh, 33h, 0CCh, 0Fh, 0F0h
bglist_end:

; March C- with background (bg): up w; up r,w~; up r~,w; down r,w~; down r~,w; down r.
march:
        ld a,(bg)
        ld c,a
        ; M0: up, write bg
        ld hl,LO
.m0:    ld (hl),c
        inc hl
        ld a,h
        or l
        jr nz,.m0
        ; M1: up, read bg, write ~bg
        ld hl,LO
.m1:    ld a,(hl)
        cp c
        call nz,bad
        ld a,c
        cpl
        ld (hl),a
        inc hl
        ld a,h
        or l
        jr nz,.m1
        ; M2: up, read ~bg, write bg
        ld a,c
        cpl
        ld b,a
        ld hl,LO
.m2:    ld a,(hl)
        cp b
        call nz,badb
        ld (hl),c
        inc hl
        ld a,h
        or l
        jr nz,.m2
        ; M3: down, read bg, write ~bg
        ld hl,0FFFFh
.m3:    ld a,(hl)
        cp c
        call nz,bad
        ld (hl),b
        dec hl
        ld a,h
        cp (LO >> 8) - 1
        jr nz,.m3
        ; M4: down, read ~bg, write bg
        ld hl,0FFFFh
.m4:    ld a,(hl)
        cp b
        call nz,badb
        ld (hl),c
        dec hl
        ld a,h
        cp (LO >> 8) - 1
        jr nz,.m4
        ; M5: down, read bg
        ld hl,0FFFFh
.m5:    ld a,(hl)
        cp c
        call nz,bad
        dec hl
        ld a,h
        cp (LO >> 8) - 1
        jr nz,.m5
        ret

; Address in data: every byte lo ^ hi, then read back.
addrtest:
        ld hl,LO
.a0:    ld a,l
        xor h
        ld (hl),a
        inc hl
        ld a,h
        or l
        jr nz,.a0
        ld hl,LO
.a1:    ld a,l
        xor h
        ld c,a
        ld a,(hl)
        cp c
        call nz,bad
        inc hl
        ld a,h
        or l
        jr nz,.a1
        ret

; An error at HL: got A, expected C (bad) or B (badb). Keeps BC, HL.
badb:   push bc
        ld c,b
        call bad
        pop bc
        ret
bad:    push bc
        push de
        push hl
        ld b,a                          ; B = got, C = expected
        ld hl,(errs)
        inc hl
        ld (errs),hl
        xor c                           ; the bits that differ
        ld e,a
        ld hl,bits
        or (hl)
        ld (hl),a
        ld a,e                          ; count each bit
        ld hl,perbit
        ld d,8
.pb:    rrca
        jr nc,.pbn
        inc (hl)
        jr nz,.pbn
        inc hl
        inc (hl)
        dec hl
.pbn:   inc hl
        inc hl
        dec d
        jr nz,.pb
        ld a,(nlog)                     ; log the first 16
        cp 16
        jr nc,.done
        inc a
        ld (nlog),a
        dec a
        ld e,a
        add a,a
        add a,e
        add a,a                         ; x 6
        ld e,a
        ld d,0
        ld hl,elog
        add hl,de
        pop de                          ; the address
        push de
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ld (hl),c
        inc hl
        ld (hl),b
        inc hl
        ld de,(pass)
        ld (hl),e
        inc hl
        ld (hl),d
.done:  pop hl
        pop de
        pop bc
        ret

; The report.
show:
        ld de,0000h                     ; row 0, col 0
        ld hl,t_title
        call puts
        ld hl,(pass)
        call putw
        ld de,0200h
        ld hl,t_errs
        call puts
        ld hl,(errs)
        call putw
        ld hl,t_bits
        call puts
        ld a,(bits)
        call putb
        ld de,0400h                     ; per bit, D7 first
        ld b,8
        ld hl,perbit + 14
.pbs:   push hl
        push bc
        ld a,"D"
        call putc
        ld a,b
        dec a
        add a,"0"
        call putc
        ld a,"="
        call putc
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        call putw
        ld a," "
        call putc
        pop bc
        pop hl
        dec hl
        dec hl
        ld a,b
        cp 5
        jr nz,.nl
        ld de,0500h
.nl:    djnz .pbs
        ld a,(nlog)                     ; the first errors
        or a
        ret z
        ld b,a
        ld ix,elog
        ld d,7
.el:    push bc
        ld e,0
        ld l,(ix+0)
        ld h,(ix+1)
        call putw
        ld a," "
        call putc
        ld a,(ix+2)
        call putb
        ld a," "
        call putc
        ld a,(ix+3)
        call putb
        ld a," "
        call putc
        ld l,(ix+4)
        ld h,(ix+5)
        call putw
        ld bc,6
        add ix,bc
        inc d
        pop bc
        djnz .el
        ret

t_title: db "RAMTEST 5F00-FFFF ECM pass ",0
t_errs:  db "errors ",0
t_bits:  db "  bits ",0

; Text at row D, column E (advances E). puts: the string at HL.
puts:   ld a,(hl)
        or a
        ret z
        call putc
        inc hl
        jr puts
putw:   ld a,h
        call putb
        ld a,l
putb:   push af
        rrca
        rrca
        rrca
        rrca
        call puth
        pop af
puth:   and 0Fh
        add a,"0"
        cp "9"+1
        jr c,putc
        add a,7
putc:   push bc
        push de
        push hl
        sub " "
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld bc,FONT
        add hl,bc                       ; HL = the glyph
        ld a,d                          ; screen: 010R R000 RRRC CCCC
        and 18h
        or 40h
        ld b,a
        ld a,d
        and 7
        rrca
        rrca
        rrca
        or e
        ld c,a                          ; BC = the cell's top line
        ld e,8
.pc:    ld a,(hl)
        ld (bc),a
        inc hl
        inc b
        dec e
        jr nz,.pc
        pop hl
        pop de
        pop bc
        inc e
        ret

; Clear the bitmap; attributes (ECM: 6000h-77FFh, which the test overwrites)
; are set to black on white after each pass by show's caller.
cls:    ld hl,4000h
        ld de,4001h
        ld bc,17FFh
        ld (hl),0
        ldir
        ret

        ASSERT $ <= pass
        ENT
body_end:
        SAVEBIN "ramtest.bin", stub, body_end - stub
