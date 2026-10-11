; bustest: does every read come from the right bank, under the load that
; crashes Sinistar on the v3 card? The 2068 half of src/test/bustest/.
;
; Needs bustest.dck in the dock (make_dck.py): every dock byte is
; f(addr) = lo ^ hi ^ 5Ah, and chunk c has LD A,D0h+c / RET at c*2000h+1000h.
; This fills RAM in chunks 4, 6 and 7 with ~f, with LD A,50h+c / RET at the
; same places, so a byte says which bank answered. It lives in chunk 5 (code,
; IM2 table, variables, stack: B000h-BFFFh), the one chunk it never switches,
; as Sinistar keeps its stack there whenever it maps dock chunk 3.
;
; Each iteration (keyboard INs included: see `load`) picks a random HSR over chunks 0-4, 6, 7 -- 2 (the display
; file) and 3 included, which Sinistar maps at run time -- then straight
; after the OUT (F4h) either:
;   - JP (HL) into a chunk's stub: an opcode fetch ~4 T-states after the
;     OUT, the tightest case (error type 2 if A isn't the expected bank's), or
;   - LD A,(HL) from a chunk: a data read ~7 T-states after (type 1).
;     For chunks 0-1 mapped HOME the expected byte is the ROM's, captured at
;     the start at the same 64 offsets. Chunks 2-3 mapped HOME are the screen
;     and BASIC, unknown: not checked (the screen writes then land in the
;     dock when chunk 2 is mapped, as Sinistar's can).
; then writes a byte of the screen and AY register 14 (an I/O port: silent).
; An IM2 interrupt every frame does what Sinistar's does: HSR 10h, reads a
; dock byte in chunk 4 (type 3) and a RAM byte in chunk 7 (type 4), AY
; writes, then the HSR back.
;
; BASIC sets the DECR mode (POKE 48142: 0 normal, 2 the ECM mode Sinistar
; uses) and the length (POKE 48143: n x 65536 iterations), then USR 45568.
; It returns the error count; the counts by type and the first 32 errors
; (type, HSR, address, expected, got, iteration) are at VARS and ERRLOG.
;
;   sjasmplus bustest.asm   ->   bustest.bin, loaded at 45568 (B200h)
;
; DOCKRUN (sjasmplus -DDOCKRUN): the same test, run from the cartridge as
; Sinistar runs, so nearly every opcode fetch comes from the card too. The
; test code goes into dock chunk 4 at 9100h (bustestd_dock.bin, which
; make_dck.py puts into the image) and chunk 4 stays DOCK throughout (HSR
; bit 4 always set, Sinistar's baseline 10h); bustestd.bin, at B200h, is the
; stub that maps it, jumps in, and takes the way back to BASIC.
;
; Both: every 64 iterations an LDIR copies 256 bytes of a chunk to RAM and
; checks them all (type 5), Sinistar's bulk copies. And RAM integrity, the
; 2068's own RAM written and read by code running from the dock (the crash
; that started this was a stack byte in RAM read back with D1 low):
;   type 6, the stack: a random word pushed and popped straight back, and a
;     CALL whose routine checks its own return address on the stack;
;   type 7, RAM: a 256-byte pattern at RAMBUF, one byte checked and rewritten
;     each iteration and all of it every 64th; a random byte written to
;     RAMSCR and read straight back.
; An error's expected and got bytes say which data bits were wrong.

        DEVICE NOSLOT64K
        org 0B200h

PORT_HSR    equ 0F4h
PORT_DECR   equ 0FFh
AY_SEL      equ 0F5h
AY_DAT      equ 0F6h

VARS        equ 0BC00h
v_sp        equ VARS+0      ; 2  BASIC's SP
v_iter      equ VARS+2      ; 4  iterations done
v_errs      equ VARS+6      ; 2  errors
v_cur       equ VARS+8      ; 1  the HSR the main loop wants (the ISR restores it)
v_i         equ VARS+9      ; 1  BASIC's I register
v_lfsr      equ VARS+10     ; 2
v_isrn      equ VARS+12     ; 2  interrupts taken
v_mode      equ VARS+14     ; 1  DECR value (48142)
v_count     equ VARS+15     ; 1  65536-iteration blocks (48143)
v_nlog      equ VARS+16     ; 1  entries in ERRLOG
v_type      equ VARS+18     ; 2 x 7  errors by type 1-7 (48146..)
v_exp       equ VARS+40     ; 1  scratch: the expected byte
v_hsr       equ VARS+41     ; 1  scratch: the HSR under test
v_addr      equ VARS+42     ; 2  scratch: the address under test
v_tmp       equ VARS+44     ; 2  scratch
ROMPRB      equ 0BD00h      ; 128: ROM bytes at the 64 offsets, chunk 0 then 1
ERRLOG      equ 0BE00h      ; 32 x 8: type, HSR, addr lo, hi, expected, got, iter lo, mid
STACKTOP    equ 0C000h      ; BF00h-BFFFh
IM2TAB      equ 0B000h      ; B000h-B100h, all B1h: the jump at B1B1h
IM2JP       equ 0B1B1h
BULKBUF     equ 0BA00h      ; 256: the LDIR test's copy
RAMBUF      equ 0BB00h      ; 256: the RAM test's pattern, ramp(i) = i ^ A5h
RAMSCR      equ 0BC80h      ; 1: the RAM test's scratch byte

        IFDEF DOCKRUN
; The RAM stub: map dock chunk 4, run the test there, come back here.
stub:
        di
        ld (v_sp),sp
        ld sp,STACKTOP
        ld a,10h
        out (PORT_HSR),a
        jp entry
finish:
        di
        xor a
        out (PORT_HSR),a
        out (PORT_DECR),a
        ld a,(v_i)
        ld i,a
        im 1
        ld sp,(v_sp)
        ei
        ld bc,(v_errs)
        ret
        SAVEBIN "bustestd.bin", stub, $ - stub
        org 9100h
HSR_BASE    equ 10h         ; chunk 4: the test's own code
        ELSE
HSR_BASE    equ 00h
        ENDIF

entry:
        IFNDEF DOCKRUN
        di
        ld (v_sp),sp
        ld sp,STACKTOP
        ENDIF
        ld a,(v_mode)                   ; BASIC's settings survive the clear
        ld e,a
        ld a,(v_count)
        ld d,a
        xor a
        ld hl,v_iter
        ld b,v_exp - v_iter
.clr:   ld (hl),a
        inc hl
        djnz .clr
        ld a,e
        ld (v_mode),a
        ld a,d
        ld (v_count),a
        ld a,i
        ld (v_i),a
        ld hl,0ACE1h
        ld (v_lfsr),hl
        ld a,HSR_BASE
        ld (v_cur),a
        out (PORT_HSR),a                ; everything HOME (but the test's own chunk)

        ; The ROM's bytes at the probe offsets, chunks 0 and 1.
        ld de,ROMPRB
        ld b,0
.cap:   ld a,b
        call probe_off                  ; HL = offset
        ld a,(hl)
        ld (de),a
        ld a,h
        add a,20h                       ; chunk 1
        ld h,a
        ld a,(hl)
        push de
        ld hl,64
        add hl,de
        ld (hl),a
        pop de
        inc de
        inc b
        ld a,b
        cp 64
        jr nz,.cap

        ; The RAM test's pattern.
        ld hl,RAMBUF
.rb:    ld a,l
        xor 0A5h
        ld (hl),a
        inc l
        jr nz,.rb

        ; RAM in chunks 4, 6, 7: ~f, and the RAM stubs.
        ld hl,8000h
.fill:  ld a,h
        and 0E0h
        cp 0A0h                         ; chunk 5: ours
        jr z,.skip
        IFDEF DOCKRUN
        cp 80h                          ; chunk 4: DOCK throughout
        jr z,.skip
        ENDIF
        ld a,l
        xor h
        xor 5Ah
        cpl
        ld (hl),a
.skip:  inc hl
        ld a,h
        or l
        jr nz,.fill
        ld b,4
.stubs: ld a,b
        cp 5
        jr z,.snext
        IFDEF DOCKRUN
        cp 4
        jr z,.snext
        ENDIF
        rrca
        rrca
        rrca
        or 10h
        ld h,a
        ld l,0
        ld (hl),3Eh
        inc hl
        ld a,50h
        add a,b
        ld (hl),a
        inc hl
        ld (hl),0C9h
.snext: inc b
        ld a,b
        cp 8
        jr nz,.stubs

        ; IM2: the table at B000h-B100h, the jump at B1B1h (chunk 5).
        ld hl,IM2TAB
        ld b,0
.tab:   ld (hl),IM2JP & 0FFh
        inc hl
        djnz .tab
        ld (hl),IM2JP & 0FFh
        ld a,0C3h
        ld (IM2JP),a
        ld hl,isr
        ld (IM2JP+1),hl
        ld a,IM2TAB >> 8
        ld i,a
        im 2
        ld a,(v_mode)
        out (PORT_DECR),a
        ei

        ld a,(v_count)
        ld c,a                          ; C: blocks left
        ld de,0                         ; DE: iterations left in this block
main:
        push bc
        push de
        call iter
        pop de
        pop bc
        ld hl,(v_iter)
        inc hl
        ld (v_iter),hl
        ld a,h
        or l
        jr nz,.noc
        ld hl,(v_iter+2)
        inc hl
        ld (v_iter+2),hl
.noc:   dec de
        ld a,d
        or e
        jr nz,main
        dec c
        jr nz,main

        IFDEF DOCKRUN
        jp finish
        ENDIF
        di
        xor a
        out (PORT_HSR),a
        out (PORT_DECR),a
        ld a,(v_i)
        ld i,a
        im 1
        ld sp,(v_sp)
        ei
        ld bc,(v_errs)
        ret

; One iteration.
iter:
        call lfsr                       ; HL = random
        ld a,h
        and 0DFh                        ; every chunk but 5
        or HSR_BASE
        ld (v_hsr),a
        ld a,l
        and 7
        cp 5
        jr nz,.cok
        dec a                           ; 5 -> 4
.cok:   ld b,a                          ; B = chunk
        ld a,b
        call chunk_bit                  ; A = the chunk's HSR bit
        ld c,a
        ld a,(v_hsr)
        and c
        ld c,a                          ; C != 0: the chunk is DOCK under the new HSR
        bit 7,l
        jr z,read_test
        ; JP test, unless the chunk would be HOME ROM (0-1 not mapped)
        ld a,c
        or a
        jr nz,.jdock
        ld a,b
        cp 4
        jr c,read_test                  ; HOME ROM, screen or BASIC: not a stub
        ld a,50h
        jr .jexp
.jdock: ld a,0D0h
.jexp:  add a,b
        ld (v_exp),a
        ld a,b
        rrca
        rrca
        rrca
        or 10h
        ld h,a
        ld l,0                          ; HL = the stub
        ld (v_addr),hl
        ld de,.jret
        push de
        ld a,(v_hsr)
        ld (v_cur),a
        out (PORT_HSR),a
        jp (hl)                         ; the next opcode fetch is from the new mapping
.jret:  ld e,a
        ld a,(v_exp)
        cp e
        ld d,2
        call nz,err_main
        jr load

read_test:
        ld a,l
        rrca
        rrca
        rrca
        and 63                          ; k
        push af
        call probe_off                  ; HL = offset
        ld a,b
        rrca
        rrca
        rrca                            ; chunk << 5
        or h
        ld h,a                          ; HL = address
        ld (v_addr),hl
        pop de                          ; D = k
        ld a,c
        or a
        jr nz,.rdock
        ld a,b
        cp 4
        jr nc,.rram
        cp 2
        jr nc,load                      ; chunk 2-3 HOME: the screen, BASIC
        jr .rrom
.rram:
        ld a,l                          ; RAM: ~f
        xor h
        xor 5Ah
        cpl
        jr .rexp
.rrom:  push hl                         ; HOME ROM: the captured byte
        ld hl,ROMPRB
        ld a,b
        or a
        jr z,.r0
        ld a,64
.r0:    add a,d
        ld e,a
        ld d,0
        add hl,de
        ld a,(hl)
        pop hl
        jr .rexp
.rdock: ld a,l                          ; DOCK: f
        xor h
        xor 5Ah
.rexp:  ld (v_exp),a
        ld a,(v_hsr)
        ld (v_cur),a
        out (PORT_HSR),a
        ld a,(hl)                       ; read straight after the switch
        ld e,a
        ld a,(v_exp)
        cp e
        ld d,1
        call nz,err_main

load:   ; every 64th: the LDIR test. Then a keyboard scan (8 INs from port
        ; FEh, as a game reads its controls: every IN interrupts the v3 card's
        ; core 1), a byte of the screen and AY register 14.
        ld a,(v_iter)
        and 63
        call z,bulk
        call ramtest
        ld b,0FEh
.kbd:   ld c,0FEh
        in a,(c)
        rlc b
        jr c,.kbd
        call lfsr
        ld a,h
        and 17h
        or 40h
        ld h,a
        ld (hl),l
        ld a,14
        out (AY_SEL),a
        ld a,l
        out (AY_DAT),a
        ret

; RAM integrity (types 6, 7): see the header.
ramtest:
        call lfsr                       ; HL = random
        ; type 6: push and pop straight back
        ld (v_tmp),hl
        push hl
        pop bc
        ld a,c
        cp l
        jr nz,.st_bad
        ld a,b
        cp h
        jr nz,.st_bad
        ; type 6: a CALL that checks its own return address
        ld de,.st_ret
        call .st_chk
.st_ret:
        jr nz,.st_bad2
        ; type 7: the pattern byte at RAMBUF + L, then rewrite it
        ld hl,(v_tmp)
        ld h,RAMBUF >> 8
        ld a,l
        xor 0A5h
        ld c,a                          ; C = expected
        ld a,(hl)
        cp c
        jr nz,.rb_bad
        ld (hl),c
        ; type 7: a random byte written and read straight back
        ld a,(v_tmp+1)
        ld (RAMSCR),a
        ld c,a
        ld a,(RAMSCR)
        cp c
        jr nz,.sc_bad
        ; every 64th iteration: all of RAMBUF
        ld a,(v_iter)
        and 63
        ret nz
        ld hl,RAMBUF
.rball: ld a,l
        xor 0A5h
        cp (hl)
        jr nz,.rb_bad2
        inc l
        jr nz,.rball
        ret
.st_chk:                                ; Z if the return address on the stack is DE
        pop hl
        push hl
        or a
        sbc hl,de
        ret
.st_bad:                                ; pushed HL, popped BC: log the first byte that differs
        ld a,c
        cp l
        ld e,c
        ld a,l
        jr nz,.st_log
        ld e,b
        ld a,h
.st_log:
        ld (v_exp),a
        ld hl,0
        add hl,sp
        ld (v_addr),hl
        ld a,(v_cur)
        ld (v_hsr),a
        ld d,6
        jp err_main
.st_bad2:                               ; the return address read back wrong
        ld hl,0
        add hl,sp
        dec hl
        dec hl
        ld (v_addr),hl                  ; where it was
        ld a,(hl)                       ; its low byte now
        ld e,a
        ld a,.st_ret & 0FFh
        ld (v_exp),a
        ld a,(v_cur)
        ld (v_hsr),a
        ld d,6
        jp err_main
.rb_bad2:
        ld c,a
        ld a,(hl)
        jr .rb_log2
.rb_bad:                                ; HL = where, C = expected, A = got
.rb_log2:
        ld e,a
        ld a,c
        ld (v_exp),a
        ld (v_addr),hl
        ld (hl),c                       ; put it right, so one flip is one error
        ld a,(v_cur)
        ld (v_hsr),a
        ld d,7
        jp err_main
.sc_bad:
        ld e,a
        ld a,c
        ld (v_exp),a
        ld hl,RAMSCR
        ld (v_addr),hl
        ld a,(v_cur)
        ld (v_hsr),a
        ld d,7
        jp err_main

; The LDIR test: 256 bytes from a random chunk (under the HSR in force) into
; BULKBUF, then each checked. Chunks whose content isn't known (HOME 0-3, our
; chunk 5) are skipped. One error (type 5) per copy, at the first bad byte.
bulk:
        call lfsr
        ld a,h
        and 7
        cp 5
        ret z
        ld b,a                          ; B = chunk
        call chunk_bit
        ld c,a
        ld a,(v_cur)
        and c
        ld c,0                          ; C = 0: expect f (DOCK)
        jr nz,.bmap
        ld a,b
        cp 6
        ret c                           ; HOME 0-4: unknown here
        ld c,0FFh                       ; RAM: expect ~f
.bmap:  ld a,b
        rrca
        rrca
        rrca
        ld h,a
        ld a,l
        and 0Eh
        or h
        ld h,a
        ld l,1                          ; HL = source, inside the chunk's first 4K
        push hl
        ld de,BULKBUF
        push bc
        ld bc,256
        ldir
        pop bc
        pop hl
        ld de,BULKBUF
        ld b,0
.bchk:  ld a,l
        xor h
        xor 5Ah
        xor c
        ex de,hl
        cp (hl)
        ex de,hl
        jr nz,.bbad
        inc hl
        inc de
        djnz .bchk
        ret
.bbad:  ld (v_exp),a
        ld (v_addr),hl
        ld a,(v_cur)
        ld (v_hsr),a
        ld a,(de)
        ld e,a
        ld d,5
        jp err_main

; error, from the main loop: with the interrupt off, so the ISR's own errors
; can't interleave with the log entry.
err_main:
        di
        call error
        ei
        ret

; Error type D: expected (v_exp), got E, at (v_addr) under (v_hsr). Counts it
; and logs the first 32. Keeps nothing.
error:
        push hl
        ld hl,(v_errs)
        inc hl
        ld (v_errs),hl
        ld a,d
        dec a
        add a,a
        ld c,a
        ld b,0
        ld hl,v_type
        add hl,bc
        inc (hl)
        jr nz,.t1
        inc hl
        inc (hl)
.t1:    ld a,(v_nlog)
        cp 32
        jr nc,.done
        inc a
        ld (v_nlog),a
        dec a
        add a,a
        add a,a
        add a,a
        ld l,a
        ld h,ERRLOG >> 8
        ld (hl),d
        inc hl
        ld a,(v_hsr)
        ld (hl),a
        inc hl
        ld bc,(v_addr)
        ld (hl),c
        inc hl
        ld (hl),b
        inc hl
        ld a,(v_exp)
        ld (hl),a
        inc hl
        ld (hl),e
        inc hl
        ld bc,(v_iter)
        ld (hl),c
        inc hl
        ld (hl),b
.done:  pop hl
        ret

; The interrupt: as Sinistar's, HSR 10h (chunk 4 DOCK) and back, with reads
; checked and AY writes.
isr:
        push af
        push bc
        push de
        push hl
        ld hl,(v_exp)                   ; v_exp and v_hsr
        push hl
        ld hl,(v_addr)
        push hl
        ld hl,(v_isrn)
        inc hl
        ld (v_isrn),hl
        ld a,10h
        ld (v_hsr),a
        out (PORT_HSR),a
        ld a,l
        and 63
        call probe_off
        ld a,h
        or 80h                          ; chunk 4: DOCK
        ld h,a
        ld (v_addr),hl
        ld a,l
        xor h
        xor 5Ah
        ld (v_exp),a
        ld e,(hl)
        cp e
        ld d,3
        call nz,error
        ld a,h
        or 0E0h                         ; chunk 7: RAM
        ld h,a
        ld (v_addr),hl
        ld a,l
        xor h
        xor 5Ah
        cpl
        ld (v_exp),a
        ld e,(hl)
        cp e
        ld d,4
        call nz,error
        ld a,7Fh
        in a,(0FEh)                     ; a keyboard row, as an ISR reads
        ld a,7
        out (AY_SEL),a
        ld a,0FFh
        out (AY_DAT),a                  ; mixer: all off (silent)
        ld a,(v_cur)
        out (PORT_HSR),a
        pop hl
        ld (v_addr),hl
        pop hl
        ld (v_exp),hl
        pop hl
        pop de
        pop bc
        pop af
        ei
        reti

; HL = probe offset k (A, 0-63): k*63 + 1, 1-3970, inside a chunk's first
; 4K (clear of the stub at 1000h and of the 00h at 0000h).
probe_off:
        push de
        ld l,a
        ld h,0
        ld e,a
        ld d,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl                       ; k * 64
        or a
        sbc hl,de                       ; k * 63
        inc hl
        pop de
        ret

; A = 1 << A (A 0-7). Keeps BC, DE, HL.
chunk_bit:
        push bc
        ld b,a
        ld a,1
        inc b
.cb:    dec b
        jr z,.cbd
        add a,a
        jr .cb
.cbd:   pop bc
        ret

; HL = the next 16-bit Galois LFSR value (taps B400h).
lfsr:
        ld hl,(v_lfsr)
        srl h
        rr l
        jr nc,.ln
        ld a,h
        xor 0B4h
        ld h,a
.ln:    ld (v_lfsr),hl
        ret

        IFDEF DOCKRUN
        SAVEBIN "bustestd_dock.bin", entry, $ - entry
        ASSERT $ <= 0A000h
        ELSE
        SAVEBIN "bustest.bin", entry, $ - entry
        ASSERT $ <= BULKBUF
        ENDIF
