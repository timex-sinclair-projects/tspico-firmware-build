; loadfile.asm -- read a whole file from the SD card into memory, byte for
; byte, with tpi:chopen / tpi:chrd / tpi:chclose. Any file, any size up to
; the limit you set: no tape header needed.
;
;   LET n=USR 60000       n = the number of bytes read
;
;   60003/60004  where to put the file       60005/60006  the most to read
;   60007        length of the file name     60008...     the name (64 max)
; An error (no such file, and so on) stops the program with its report.

STREAM  equ 200                 ; the Pico's key for this channel: any 0-255
                                ; that BASIC isn't using for OPEN #

        org 60000
        jp LOAD
DEST:   dw 32768                ; 60003
MAXLEN: dw 16384                ; 60005
NAMELEN: db 0                   ; 60007
NAME:   ds 64                   ; 60008

PMR1:   dw 0
PMR2:   dw 0
TOTAL:  dw 0
CMDBUF: ds 80

OPEN_T: db "tpi:chopen rb "     ; rb = read, binary (no text translation)
OPEN_L  equ $-OPEN_T
RD_T:   db "tpi:chrd"
RD_L    equ $-RD_T
CL_T:   db "tpi:chclose"
CL_L    equ $-CL_T

LOAD:   ld hl,OPEN_T            ; build "tpi:chopen rb <name>"
        ld de,CMDBUF
        ld bc,OPEN_L
        ldir
        ld a,(NAMELEN)
        ld c,a
        ld b,0
        or a
        jr z,.named             ; no name: the Pico answers F
        ld hl,NAME
        ldir
.named: ld a,(NAMELEN)
        add a,OPEN_L
        ld c,a                  ; BC = length of the command
        ld b,0
        ld hl,STREAM
        ld (PMR1),hl            ; CODE stream, 0: a plain stream, not records
        ld hl,0
        ld (PMR2),hl
        ld (TOTAL),hl
        ld hl,CMDBUF
        call SEND_CMD
        call nc,GET_REPLY
        jp c,RAISE

.next:  ld hl,(MAXLEN)          ; room left
        ld de,(TOTAL)
        and a
        sbc hl,de
        jr z,.full
        ld a,h
        or a
        ld a,l
        jr z,.ask
        ld a,255                ; at most 255 bytes a read
.ask:   ld l,a
        ld h,0
        ld (PMR2),hl            ; CODE stream, how many bytes
        ld hl,RD_T
        ld bc,RD_L
        call SEND_CMD
        jr c,.fail
        ld hl,(DEST)
        ld de,(TOTAL)
        add hl,de
        call GET_DATA           ; NC Z: E bytes arrived
        jr c,.fail
        jr nz,.full             ; end of the file
        ld hl,(TOTAL)
        ld d,0
        add hl,de
        ld (TOTAL),hl
        jr .next

.full:  call CLOSE
        jp c,RAISE
        ld bc,(TOTAL)
        ret

.fail:  push af                 ; close the channel, then report the error
        call CLOSE
        pop af
        jp RAISE

CLOSE:  ld hl,0
        ld (PMR2),hl
        ld hl,CL_T
        ld bc,CL_L
        call SEND_CMD
        ret c
        jp GET_REPLY

        include "picolib.asm"
