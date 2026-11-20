;==============================================================================
; bankapi.asm -- the Timex bank API on the TS-2068 Megabank (Megabank spec,
; "The Timex bank API on the board", phase 8). Megabank test ROM (2.5) only:
; tools/build-rom.py --megabank assembles it and splices it over the bank
; code that the boot copies from EXROM 1000h-162Fh to RAM 6200h.
;
; It replaces RAM 6316h-6571h, GET_WORD to the end of RESTORE_STATUS, with
; every entry point where it was:
;
;   6316h GET_WORD        genuine
;   633Bh PUT_WORD        genuine, with the Technical Manual's fix (6.5.3):
;                         the word in DE is kept, not overwritten by LD D,B
;   635Ch                 (WRITE_BS_REG and READ_BS_REG, Timex's nibble-wide
;                         expansion-bus interface: gone, the space reused)
;   6405h GET_STATUS      C = a bank's chunks, low active, for every bank (6.5.2)
;   644Dh GET_CHUNK       genuine
;   645Eh GET_NUMBER      the board's OWNn first; EXROM no longer unreachable
;   6499h BANK_ENABLE     Timex's semantics plus the board, with the HSR rule
;   651Eh SAVE_STATUS     FFh, F4h, the board's 16 registers and its select
;   654Ah RESTORE_STATUS  the same, in the order the HSR rule needs (6.5.4,
;                         6.5.5: only FFh bit 7 comes back)
;
; DOCK and EXROM get exactly the chunks asked for (TIMEX_HSR): the EXROM is no
; longer tied to chunks 0-1.
;
; The code runs at RAM 6200h up, and in 64-column mode 97C0h higher: the
; boot's video-mode service copies 6000h-683Fh to F7C0h and adds 97C0h to
; every word that X1D00's table lists. RB is that offset: the build
; assembles this file twice, with RB = 0 and RB = 97C0h, and every word that
; differs by 97C0h is an address the table must list. So every address in
; the copied block is written RB + it (a label in this file is already).
;
; Bank numbers, as Timex's: 0 DOCK, FEh EXROM, FFh HOME, 1-253 expansion
; banks. A chunk mask (C) is low active: bit n clear = chunk n.
;
; The HSR rule (measured on the board, 2026-11-18): /BE keeps the 2068's
; memory off a read of a board-owned chunk, but not HOME RAM off a write, so
; an owned chunk must have its HSR (F4h) bit set. Map: OWNn, then the bit.
; Unmap: the bit, then OWNn = 0. BANK_ENABLE and RESTORE_STATUS keep that
; order, with interrupts off (and back as they were: LD A,I, read twice for
; the NMOS Z80's IFF2 slip).
;==============================================================================

        DEVICE  NOSLOT64K

        IFNDEF  RB
RB      EQU     0
        ENDIF

PORT_SEL        EQU $FD            ; the board's register select
PORT_DAT        EQU $FC            ; the selected register
HSR             EQU $F4            ; bit n set: chunk n to DOCK/EXROM
DEC             EQU $FF            ; bit 7: EXROM, not DOCK

NBANKS          EQU RB+$6315       ; the bank count: the board's (SIZE), 0 none

        ; The interrupt state: P/V = IFF2 on the stack, interrupts off.
        MACRO   DI_SAVE
        ld      a,i
        jp      pe,1F
        ld      a,i                ; an interrupt taken during LD A,I reads 0
1:      di
        push    af
        ENDM

        MACRO   EI_RESTORE
        pop     af
        jp      po,1F
        ei
1:
        ENDM

        ORG     RB+$6316

;------------------------------------------------------------------------------
; GET_WORD (6316h): HL = the word at HL in bank B. Genuine.
;------------------------------------------------------------------------------
GET_WORD:
        push    af
        push    bc
        push    de
        call    GET_NUMBER         ; the bank in control of HL's chunk now
        push    af
        ld      d,b
        ld      b,a
        call    GET_STATUS         ; its chunks
        push    bc
        call    GET_CHUNK
        cpl
        ld      b,d
        ld      c,a
        call    BANK_ENABLE        ; bank B in HL's chunk
        ld      e,(hl)
        inc     hl
        ld      d,(hl)
        dec     hl
        ex      de,hl
        pop     bc
        pop     af
        ld      b,a
        call    BANK_ENABLE        ; and back
        pop     de
        pop     bc
        pop     af
        ret
        ASSERT  $ == RB+$633B

;------------------------------------------------------------------------------
; PUT_WORD (633Bh): the word in DE to HL in bank B. The Technical Manual's
; fix (6.5.3): PUSH DE where the genuine code had PUSH AF, so LD D,B no longer
; loses the word. Needs GET_STATUS keeping B (6.5.2), which it does.
;------------------------------------------------------------------------------
PUT_WORD:
        push    af
        push    bc
        call    GET_NUMBER
        push    de
        ld      d,b
        ld      b,a
        call    GET_STATUS         ; B kept: the owner, C its chunks
        push    bc
        call    GET_CHUNK
        cpl
        ld      b,d
        ld      c,a
        call    BANK_ENABLE
        pop     bc
        pop     de
        ld      (hl),e
        inc     hl
        ld      (hl),d
        dec     hl
        call    BANK_ENABLE        ; the owner back
        pop     bc
        pop     af
        ret
        ASSERT  $ == RB+$635C

;------------------------------------------------------------------------------
; 635Ch-6404h held WRITE_BS_REG and READ_BS_REG, Timex's register-by-nibble
; interface to its expansion bus. Nothing uses it any more (the boot's bank
; search that did is gone, and there is no Timex bank hardware to talk to), so
; the space holds this file's helpers. No entry point is kept there.
;------------------------------------------------------------------------------

; ISBOARD -- B: a bank number. Out: B as it was if it is one of the board's
; banks (BASE to BASE + count - 1), else 0. A, F changed.
ISBOARD:
        ld      a,(NBANKS)
        and     a
        jr      z,.no
        push    hl
        ld      a,b
        ld      hl,MBBASE
        sub     (hl)
        ld      hl,NBANKS
        cp      (hl)
        pop     hl
        ret     c
.no:    ld      b,0
        ret

; OWNMAP -- A: a bank (0: any bank). Out: A = the chunks it owns, bit n for
; chunk n; 0 with no board. BC, DE, HL kept. OWNn of FEh or FFh is no owner.
OWNMAP:
        push    bc
        push    de
        ld      e,a
        ld      d,0
        ld      a,(NBANKS)
        and     a
        jr      z,.out
        ld      b,8                ; chunk 7 first: it ends in bit 7
.lp:    ld      a,b
        dec     a
        out     (PORT_SEL),a
        in      a,(PORT_DAT)
        cp      $FE
        jr      c,.n
        xor     a
.n:     inc     e
        dec     e
        jr      nz,.cmp
        cp      1                  ; any bank: carry if none
        ccf
        jr      .sh
.cmp:   xor     e                  ; this bank: carry if it is
        cp      1
.sh:    rl      d
        djnz    .lp
.out:   ld      a,d
        pop     de
        pop     bc
        ret

; NEWOWN -- BANK_ENABLE's rule for one chunk. A = its OWNn as read, B = the
; board bank asked for (0: the bank is not one of the board's), D = the
; chunk's bit, E = the chunks asked for. Out: A = what OWNn must be: the bank
; for a chunk asked for (0 if not a board bank); 0 for one the bank owns and
; is not asked for (a bank holds exactly what it is given); else as it was.
; Only A and F change.
NEWOWN:
        cp      $FE
        jr      c,.n
        xor     a                  ; FEh, FFh: no owner
.n:     push    af
        ld      a,d
        and     e
        jr      z,.not
        pop     af
        ld      a,b
        ret
.not:   pop     af
        cp      b
        ret     nz
        xor     a
        ret

; SAVE_BOARD -- SAVE_STATUS's second half: the board's registers 00h-0Fh and
; its select, to IX+1 on. Reads only, but for the select (FDh), which the
; boot's MB_DETECT writes on any 2068, so it needs no board check: with no
; board the bytes are whatever the bus gives and RESTORE_STATUS ignores them.
SAVE_BOARD:
        in      a,(PORT_SEL)
        ld      c,a
        ld      b,0
.lp:    inc     ix
        ld      a,b
        out     (PORT_SEL),a
        in      a,(PORT_DAT)
        ld      (ix+0),a
        inc     b
        bit     4,b
        jr      z,.lp
        inc     ix
        ld      (ix+0),c
        ld      a,c
        out     (PORT_SEL),a       ; the select as it was
        pop     bc
        pop     af
        ret

; RESTORE_BOARD -- RESTORE_STATUS's second half. D = the saved FFh, E = the
; saved HSR (already ANDed in), IX at the saved HSR.
RESTORE_BOARD:
        in      a,(DEC)
        xor     d
        and     $7F
        xor     d
        out     (DEC),a            ; bit 7 from the frame, the rest as now
        ld      c,PORT_DAT
        ld      a,(NBANKS)
        and     a
        jr      nz,.b
        inc     c                  ; no board: the bytes go to the select,
.b:     ld      b,0                ; which MB_DETECT writes on any 2068
.lp:    inc     ix
        ld      a,b
        out     (PORT_SEL),a
        ld      a,(ix+0)
        out     (c),a              ; OWN0-7 (each sets its SUB), then SUB0-7
        inc     b
        bit     4,b
        jr      z,.lp
        inc     ix
        ld      a,(ix+0)
        out     (PORT_SEL),a       ; the select as it was
        ld      a,e
        out     (HSR),a            ; bits that come, after their owners
        EI_RESTORE
        pop     de
        pop     bc
        pop     af
        ret

        ASSERT  $ <= RB+$6404

; MBBASE -- the board's BASE, set by the boot's MB_DETECT (fddcmd.asm
; MB_MBBASE): a fixed address, the last byte before GET_STATUS. (658Eh-65CDh
; look free, FFh, but are the bank stack: 65CEh's pointer starts at 65CEh and
; CALL_BANK pushes 4 bytes a call below it.)
        ORG     RB+$6404
MBBASE: db      0
        ASSERT  $ == RB+$6405

        ORG     RB+$6405
;------------------------------------------------------------------------------
; GET_STATUS (6405h): B = a bank. Out: C = its chunks, low active (bit n
; clear: it has chunk n). A, B, DE, HL kept: B is kept for every bank, which
; the Technical Manual's fix (6.5.2) does for HOME, EXROM and DOCK, and its
; PUT_WORD needs. HOME: the chunks whose HSR bit is clear. DOCK (FFh bit 7
; clear) and EXROM (set): the chunks whose bit is set and that the board
; doesn't own, none if the other is selected. A board bank: what OWNMAP says;
; any other bank: none.
;------------------------------------------------------------------------------
GET_STATUS:
        push    af
        ld      a,b
        inc     a
        jr      z,.home            ; FFh
        inc     a
        jr      z,.ext             ; FEh
        dec     a
        dec     a
        jr      z,.dock            ; 0
        push    bc
        call    ISBOARD
        ld      a,b
        pop     bc
        and     a
        jr      z,.none
        call    OWNMAP
        cpl
        jr      .c
.home:  in      a,(HSR)
        jr      .c
.ext:   in      a,(DEC)
        rla
        jr      nc,.none
        jr      .sel
.dock:  in      a,(DEC)
        rla
        jr      c,.none
.sel:   xor     a
        call    OWNMAP             ; the board's chunks
        ld      c,a
        in      a,(HSR)
        cpl
        or      c
        jr      .c
.none:  ld      a,$FF
.c:     ld      c,a
        pop     af
        ret
        ASSERT  $ <= RB+$644D

        ORG     RB+$644D
;------------------------------------------------------------------------------
; GET_CHUNK (644Dh): A = the bit of HL's chunk. Genuine.
;------------------------------------------------------------------------------
GET_CHUNK:
        push    bc
        ld      a,h
        ld      b,5
.s:     srl     a
        djnz    .s
        inc     a
        ld      b,a
        xor     a
        scf
.r:     rla
        djnz    .r
        pop     bc
        ret
        ASSERT  $ == RB+$645E

;------------------------------------------------------------------------------
; GET_NUMBER (645Eh): A = the bank in control of HL's chunk: the board bank
; that owns it, else FFh HOME (its HSR bit clear), FEh EXROM (set, FFh bit 7
; set) or 0 DOCK. BC, DE, HL kept. (The genuine code looped over GET_STATUS,
; whose B overwrote its count, and tested for the EXROM where the chunk was
; HOME: the Technical Manual's 6.5.7.)
;------------------------------------------------------------------------------
GET_NUMBER:
        push    bc
        call    GET_CHUNK
        ld      c,a
        ld      a,(NBANKS)
        and     a
        jr      z,.nob
        ld      a,h
        rlca
        rlca
        rlca
        and     7
        out     (PORT_SEL),a
        in      a,(PORT_DAT)       ; OWNn
        and     a
        jr      z,.nob
        cp      $FE
        jr      c,.x
.nob:   in      a,(HSR)
        and     c
        ld      a,$FF
        jr      z,.x               ; HOME
        in      a,(DEC)
        rla
        ld      a,$FE
        jr      c,.x               ; EXROM
        xor     a                  ; DOCK
.x:     pop     bc
        ret

        ASSERT  $ <= RB+$648B      ; RAM 648Bh-6496h is EXROM 128Bh-1296h: the fast
                                   ;   entry's switch loops and landing (build-rom.py)
        ASSERT  $ <= RB+$6499

        ORG     RB+$6499
;------------------------------------------------------------------------------
; BANK_ENABLE (6499h): B = the bank, C = the chunks it gets, low active. All
; registers kept; interrupts off throughout and then as they were (6.5.4,
; with Brzozowski's caution: the state is restored, not an unconditional EI).
;
; First the HSR and FFh as Timex's code sets them (TIMEX_HSR). Then, with a
; board: a chunk asked for goes to the bank if it is one of the board's
; (else to no board bank), and a board bank's chunks not asked for go back
; (NEWOWN) to HOME: their HSR bits, kept by TIMEX_HSR, are cleared. The HSR rule: every chunk the board owns afterwards keeps its HSR
; bit; bits are cleared before the owners change and set after.
;------------------------------------------------------------------------------
BANK_ENABLE:
        push    af
        push    bc
        push    de
        push    hl
        DI_SAVE
        ld      a,c
        cpl
        ld      e,a                ; E = the chunks, high active
        call    TIMEX_HSR          ; H = the HSR Timex's code would set
        ld      a,(NBANKS)
        and     a
        jr      z,.f4
        call    ISBOARD            ; B: the board's bank, or 0
        ld      l,0                ; L = the chunks the board will own
        ld      c,0
        ld      d,1
.pa:    ld      a,c
        out     (PORT_SEL),a
        in      a,(PORT_DAT)
        call    NEWOWN
        and     a
        jr      z,.pa0
        ld      a,l
        or      d
        ld      l,a                ; owned after
        jr      .pa1
.pa0:   ld      a,d
        and     e
        jr      nz,.pa1            ; asked for: TIMEX_HSR's bit stands
        in      a,(PORT_DAT)
        and     a
        jr      z,.pa1             ; no owner before
        cp      b
        jr      nz,.pa1
        ld      a,d                ; the bank's, given up: back to HOME
        cpl
        and     h
        ld      h,a
.pa1:   inc     c
        sla     d
        jr      nc,.pa
        ld      a,h
        or      l
        ld      h,a                ; owned chunks keep their HSR bit
        in      a,(HSR)
        and     h
        out     (HSR),a            ; bits that go, before their owners do
        ld      c,0
        ld      d,1
.pb:    ld      a,c
        out     (PORT_SEL),a
        in      a,(PORT_DAT)
        ld      l,a
        call    NEWOWN
        cp      l
        jr      nz,.w              ; changed
        and     a
        jr      z,.pb1             ; no owner before or after
        ld      l,a
        ld      a,d
        and     e
        ld      a,l
        jr      z,.pb1             ; another chunk's owner, untouched
.w:     out     (PORT_DAT),a       ; OWNn (and SUBn = n, Timex's model)
.pb1:   inc     c
        sla     d
        jr      nc,.pb
.f4:    ld      a,h
        out     (HSR),a            ; bits that come, after their owners
        EI_RESTORE
        pop     hl
        pop     de
        pop     bc
        pop     af
        ret
        ASSERT  $ <= RB+$651E

        ORG     RB+$651E
;------------------------------------------------------------------------------
; SAVE_STATUS (651Eh): IX = 19 bytes: FFh, F4h, the board's registers 00h-
; 0Fh (OWN0-7, SUB0-7) and its register select (FDh). Out: IX = the last.
; AF, BC, DE kept. CALL_BANK, XFER_BYTES and the interrupt handler at 62AEh
; make room for 19 (patched in build-rom.py: they made the bank count + 2).
; With no board the 17 are written all the same (what the bus gives).
;------------------------------------------------------------------------------
SAVE_STATUS:
        push    af
        push    bc
        in      a,(DEC)
        ld      (ix+0),a
        inc     ix
        in      a,(HSR)
        ld      (ix+0),a
        jp      SAVE_BOARD

;------------------------------------------------------------------------------
; TIMEX_HSR -- BANK_ENABLE's first half: FFh bit 7 and H = the HSR before the
; board is considered. B = the bank, C = its chunks low active, E = high
; active. Changes A, F, H.
;
; HOME or an expansion bank: its chunks' HSR bits cleared, the rest as they
; are. DOCK and EXROM: exactly the chunks asked for (the others to HOME), and
; FFh bit 7 selects which of the two, unless no chunk is asked for. Timex's
; code tied the EXROM to chunks 0-1 (chunk 0 asked for meant both, and HOME
; taking chunk 0 back also selected the DOCK); this doesn't, so a ROM that
; puts the EXROM elsewhere, as Charlie Day's LEAP ROMs do in chunk 6, can.
; DOCK and EXROM still share FFh bit 7: one of them at a time.
;------------------------------------------------------------------------------
TIMEX_HSR:
        in      a,(HSR)
        and     c
        ld      h,a                ; the chunks asked for to HOME
        ld      a,b
        cp      $FE
        jr      z,.dx              ; EXROM
        and     a
        ret     nz                 ; HOME or an expansion bank
.dx:    ld      h,e                ; DOCK, EXROM: exactly these
        ld      a,c
        inc     a
        ret     z                  ; none: the select as it is
        in      a,(DEC)
        xor     b
        and     $7F
        xor     b
        out     (DEC),a            ; bit 7 = B's: EXROM (FEh) or DOCK (0)
        ret
        ASSERT  $ <= RB+$654A

        ORG     RB+$654A
;------------------------------------------------------------------------------
; RESTORE_STATUS (654Ah): the 19 bytes at IX back. Out: IX = the last.
; AF, BC, DE kept. Interrupts off and back (6.5.4). FFh: only bit 7, the
; EXROM/DOCK select, comes back (6.5.5: a mode change made in between, video
; or the interrupt inhibit, is no longer undone). The HSR rule: F4h's bits
; that go first, then the owners and pages, then F4h whole.
;------------------------------------------------------------------------------
RESTORE_STATUS:
        push    af
        push    bc
        push    de
        DI_SAVE
        ld      d,(ix+0)           ; FFh
        inc     ix
        ld      e,(ix+0)           ; F4h
        in      a,(HSR)
        and     e
        out     (HSR),a
        jp      RESTORE_BOARD
        ASSERT  $ <= RB+$6572


        SAVEBIN "bankapi.bin", RB+$6316, $6572-$6316
