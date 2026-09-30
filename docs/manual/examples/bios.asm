; bios.asm -- calling the Pico Interface BIOS in the EXROM from RAM.
; A USR program runs with the HOME ROM paged in; the BIOS is in the EXROM at
; the same addresses, so the call goes through HOME's bank-switching thunk
; at 03FCh: HL = the EXROM address; A, F, BC and DE reach the routine and
; come back from it. IX is not kept. Interrupts must be off for the switch.
;
;   PRINT USR 60000       the interface version: 32 (20h) on ROM 2.0
;   PRINT USR 60003       the TS-Pico mode bits (TPMODE)
;   POKE 60009,m: RANDOMIZE USR 60006     set the mode bits to m

THUNK   equ 03FCh
G_MODE  equ 1840h               ; BC = the mode bits
S_MODE  equ 1842h               ; mode bits := A AND 0Fh
G_VERS  equ 1844h               ; BC = the interface version

        org 60000
        jp VERS                 ; 60000
        jp MODE                 ; 60003
        jp SETM                 ; 60006
M:      db 0                    ; 60009

VERS:   ld hl,G_VERS
        jr BIOS
MODE:   ld hl,G_MODE
        jr BIOS
SETM:   ld a,(M)
        ld hl,S_MODE
BIOS:   di                      ; the bank switch is not interrupt-safe
        call THUNK
        ei
        ret                     ; BC comes back to USR
