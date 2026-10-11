; st254: the 2068 half of the issue-#254 stress test.
;
; Reads the TS-Pico status port (0Fh) as fast as it can, OUTER x 65536 times
; (about 0.7 s per 65536 at 3.5 MHz), while src/test/st254/stress.py holds the
; status at 00h and puts the Pico through flash, SD and GC phases. Every read
; that isn't 00h is sent back with OUT (0Eh),A: tsbus queues it, so the Pico
; counts it under the phase it was in. Every 65536 reads, OUT (0Fh),0 is a
; heartbeat, so the Pico knows how many reads each phase saw. (An OUT sets
; the status to 00h, which it already is.)
;
; USR 60000 returns the number of bad reads (mod 65536).
;
;   sjasmplus st254.asm   ->   st254.bin, loaded at 60000

        DEVICE NOSLOT64K
        org 60000

PORT_DATA   equ 0Eh
PORT_STATUS equ 0Fh

start:  ld hl,0
        ld (bad),hl
        ld a,(outer)
        ld b,a
        ld de,0
loop:   in a,(PORT_STATUS)
        or a
        jr nz,isbad
next:   dec e
        jr nz,loop
        dec d
        jr nz,loop
        xor a
        out (PORT_STATUS),a     ; heartbeat: 65536 more reads
        djnz loop
        ld bc,(bad)
        ret

isbad:  out (PORT_DATA),a       ; the bad value, for the Pico to count
        ld hl,(bad)
        inc hl
        ld (bad),hl
        jr next

bad:    dw 0
outer:  db 255                  ; POKE 60000+(outer-start) to change

        SAVEBIN "st254.bin", start, $ - start
