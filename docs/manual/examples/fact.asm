; fact.asm -- the machine-code side of the tpi:.fact example command
; (Part 2 of the programmer's manual). The Pico works out n! and sends the
; digits back as a data answer: status 1, count, digits, XOR -- the same
; shape as tpi:chrd, so GET_DATA reads it.
;
;   POKE 60003,n: RANDOMIZE USR 60000     prints n! (n = 0 to 32)

        org 60000
        jp FACT
N:      db 0                    ; 60003

PMR1:   dw 0
PMR2:   dw 0
DIGITS: ds 64

CMD_T:  db "tpi:.fact"
CMD_L   equ $-CMD_T

FACT:   ld a,(N)
        ld (PMR1),a             ; SAVE "tpi:.fact" CODE n,0
        ld a,2
        call CHAN_OPEN
        ld hl,CMD_T
        ld bc,CMD_L
        call SEND_CMD
        jp c,RAISE
        ld hl,DIGITS
        call GET_DATA
        jp c,RAISE              ; n too big: Report 6
        ld hl,DIGITS
        ld b,e
.pr:    ld a,(hl)
        inc hl
        rst 10h
        djnz .pr
        ld a,0Dh
        rst 10h
        ret

        include "picolib.asm"
