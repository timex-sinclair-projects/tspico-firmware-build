; logline.asm -- add a line of text to the end of a text file on the SD card
; (a log, a high-score table...), with tpi:chopen / tpi:chwr / tpi:chclose.
; The file is made if it isn't there.
;
;   RANDOMIZE USR 60000
;
;   60003        length of the file name     60004...  the name (32 max)
;   60036        length of the line          60037...  the line (200 max)
; An error stops the program with its report.

STREAM  equ 201
CHUNK   equ 64                  ; bytes per tpi:chwr (128 hex digits)

        org 60000
        jp LOG
NAMELEN: db 0                   ; 60003
NAME:   ds 32                   ; 60004
LINELEN: db 0                   ; 60036
LINE:   ds 200                  ; 60037

PMR1:   dw STREAM               ; every command here is for our stream
PMR2:   dw 0
CMDBUF: ds 140

OPEN_T: db "tpi:chopen a "      ; a = append, text mode: CR becomes a newline
OPEN_L  equ $-OPEN_T
WR_T:   db "tpi:chwr "
WR_L    equ $-WR_T
CL_T:   db "tpi:chclose"
CL_L    equ $-CL_T

LOG:    ld hl,OPEN_T            ; "tpi:chopen a <name>"
        ld de,CMDBUF
        ld bc,OPEN_L
        ldir
        ld a,(NAMELEN)
        ld c,a
        ld b,0
        or a
        jr z,.named
        ld hl,NAME
        ldir
.named: ld a,(NAMELEN)
        add a,OPEN_L
        ld c,a
        ld b,0
        call SEND_REPLY
        jp c,RAISE

        ld hl,LINE              ; the line, CHUNK bytes at a time
        ld a,(LINELEN)
        ld c,a
.chunk: ld a,c
        or a
        jr z,.eol
        cp CHUNK+1
        jr c,.last
        ld a,CHUNK
.last:  ld b,a                  ; B = bytes in this write
        sub c
        neg
        ld c,a                  ; C = bytes left after it
        push bc
        call WRITE              ; B bytes from HL, HL advanced
        pop bc
        jr c,.fail
        jr .chunk

.eol:   ld hl,CR
        ld b,1
        call WRITE              ; end the line
        jr c,.fail
        call CLOSE
        jp c,RAISE
        ret

.fail:  push af
        call CLOSE
        pop af
        jp RAISE

CR:     db 0Dh

; WRITE -- tpi:chwr with B bytes from HL (HL advanced). NC ok, C: A = error.
WRITE:  push hl
        ld hl,WR_T
        ld de,CMDBUF
        ld c,WR_L
        push bc
        ld b,0
        ldir
        pop bc
        pop hl
        push bc
.hex:   ld a,(hl)
        inc hl
        call HEX                ; two hex digits at DE
        djnz .hex
        pop bc
        push hl
        ld a,b
        add a,a                 ; 2 digits a byte
        add a,WR_L
        ld c,a
        ld b,0
        call SEND_REPLY
        pop hl
        ret

CLOSE:  ld hl,CL_T
        ld bc,CL_L
        jr SEND_TEXT

; SEND_REPLY -- send the command in CMDBUF, BC long, and read the status.
; SEND_TEXT does the same for a command at HL.
SEND_REPLY:
        ld hl,CMDBUF
SEND_TEXT:
        call SEND_CMD
        ret c
        jp GET_REPLY

        include "picolib.asm"
