; countdir.asm -- how many files match a pattern, without listing them.
; Opens a directory listing as a channel (the d: device), then asks for the
; number of names the way TAB 0 does in BASIC: a seek to byte 0 (the bytes
; 23, 0, 0 sent with tpi:chwr) makes the next read return the count as text.
;
;   LET n=USR 60000       n = the number of names
;
;   60003        length of the pattern       60004...  the pattern, "*.tap"
; An error stops the program with its report.

STREAM  equ 202

        org 60000
        jp COUNT
PATLEN: db 0                    ; 60003
PAT:    ds 40                   ; 60004

PMR1:   dw STREAM
PMR2:   dw 0
CMDBUF: ds 64
REPLY:  ds 8                    ; the count comes back as digits and a CR

OPEN_T: db "tpi:chopen r d:"
OPEN_L  equ $-OPEN_T
TAB0_T: db "tpi:chwr 170000"    ; 23, 0, 0: TAB 0
TAB0_L  equ $-TAB0_T
RD_T:   db "tpi:chrd"
RD_L    equ $-RD_T
CL_T:   db "tpi:chclose"
CL_L    equ $-CL_T

COUNT:  ld hl,OPEN_T            ; "tpi:chopen r d:<pattern>"
        ld de,CMDBUF
        ld bc,OPEN_L
        ldir
        ld a,(PATLEN)
        ld c,a
        ld b,0
        or a
        jr z,.pat               ; no pattern: everything in the folder
        ld hl,PAT
        ldir
.pat:   ld a,(PATLEN)
        add a,OPEN_L
        ld c,a
        ld b,0
        ld hl,CMDBUF
        call SEND_CMD
        call nc,GET_REPLY
        jp c,RAISE

        ld hl,TAB0_T
        ld bc,TAB0_L
        call SEND_CMD
        call nc,GET_REPLY
        jr c,.fail

        ld hl,8
        ld (PMR2),hl            ; up to 8 bytes
        ld hl,RD_T
        ld bc,RD_L
        call SEND_CMD
        jr c,.fail
        ld hl,REPLY
        call GET_DATA
        jr c,.fail
        ld hl,0
        ld (PMR2),hl

        ld de,REPLY             ; digits to a number in HL
.dig:   ld a,(de)
        inc de
        sub '0'
        jr c,.num               ; the CR (or anything else) ends it
        cp 10
        jr nc,.num
        push de
        ld d,h
        ld e,l
        add hl,hl
        add hl,hl
        add hl,de
        add hl,hl               ; HL * 10
        ld e,a
        ld d,0
        add hl,de
        pop de
        jr .dig
.num:   push hl
        call CLOSE
        pop bc                  ; BC = the count, for USR
        jp c,RAISE
        ret

.fail:  push af
        ld hl,0
        ld (PMR2),hl
        call CLOSE
        pop af
        jp RAISE

CLOSE:  ld hl,CL_T
        ld bc,CL_L
        call SEND_CMD
        ret c
        jp GET_REPLY

        include "picolib.asm"
