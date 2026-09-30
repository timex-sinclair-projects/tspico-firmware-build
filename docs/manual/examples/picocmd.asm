; picocmd.asm -- send any tpi: command from BASIC and get the report back.
;
;   LET r=USR 60000       r = 0 for OK, else the report code (see below)
;   RANDOMIZE USR 60003   stops the program with the report, as SAVE would
;
; Before the call, POKE the command's CODE numbers, its length and its text:
;   60006/60007  first CODE number        60008/60009  second CODE number
;   60010/60011  length of the text       60012...     the text (128 max)
; r+1 is the report's place in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ".

        org 60000
        jp RUN_CODE             ; 60000
        jp RUN_RAISE            ; 60003
PMR1:   dw 0                    ; 60006
PMR2:   dw 0                    ; 60008
CMDLEN: dw 0                    ; 60010
CMDBUF: ds 128                  ; 60012

RUN:    ld a,2
        call CHAN_OPEN          ; anything the Pico prints goes to the screen
        ld hl,CMDBUF
        ld bc,(CMDLEN)
        call SEND_CMD
        ret c
        jp GET_REPLY

RUN_CODE:
        call RUN
        ld bc,0
        ret nc                  ; OK: 0
        inc a                   ; ERR_NR + 1
        ld c,a
        ret

RUN_RAISE:
        call RUN
        ret nc
        jp RAISE

        include "picolib.asm"
