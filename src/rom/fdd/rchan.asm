;==============================================================================
; rchan.asm -- "r:" channels: OPEN #n,"r:name"[,"mode"[,reclen]], PRINT #,
; INPUT #, INKEY$ #, CLOSE # on the Megabank's RAM disk (phase 9 of the
; Megabank's specification, TS-2068-Megabank docs/spec.md, "Channels").
;
; Part of the Megabank build only: fddcmd.asm INCLUDEs it, under IFDEF
; MEGABANK, at EXROM RCH_BASE (2400h, free in the base ROM), and build-rom.py
; splices it there. One assembly with the module, so every label is shared.
;
; The firmware keeps the file system (names, allocation, the directory); the
; ROM keeps an open file's bytes. OPEN asks the firmware (tpi:rchopen), which
; finds or makes the file, gives it an extent on the board and writes the
; stream's slot in the RAM disk's top page; the mover copies the slot's
; 15-byte block into 2068 memory, and the record in CHANS is built from it.
; From then on every character is read or written by the ROM itself, straight
; to the board through a window chunk (the mover's MV_WIN/MV_MAP/MV_UNMAP):
; no exchange with the TS-Pico. Past the extent PRINT # asks for more
; (tpi:rchgrow); CLOSE # tells the firmware (tpi:rchclose), which writes the
; length into the directory.
;
; The record is an ordinary channel record, letter 'R', with the same HOME
; stubs as an 'F' record (14A0h, 14A9h): G_OUT and G_IN (through MB_OUT and
; MB_IN) send it here by its letter. So r: needs no HOME bytes. A record takes
; R_ALLOC (256) bytes in CHANS, padded as an 'F' record is so both bytes of
; the stream's offset stay below 80h.
;
; The open-stream mask: every r: command tells the firmware which streams
; 0-15 point at an 'R' record (bit n: stream n), so it closes the slots of
; streams that NEW, a reset or a POKE took away. The channel commands carry
; it in their payload; tpi:rmask carries it before the commands that have
; none (from TPI_SEND, for ERASE/MOVE/COPY/FORMAT/CAT "r:...", and from
; SET_MODE, for SAVE/LOAD/VERIFY/MERGE "r:...").
;==============================================================================

R_ALLOC         EQU $100           ; an 'R' record's allocation in CHANS
RR_FL           EQU 7              ; flags (F_*)
RR_REC          EQU 8              ; the record length (0: a stream file)
RR_OST          EQU 9              ; output state: 0; 1 after 23 (TAB), 2 after its
                                   ;   low byte; 80h+n: n parameters to drop (text)
RR_TLO          EQU 10             ; TAB's low byte
RR_BUF          EQU 11             ; = R_OUTBUF: a channel command's payload, and
                                   ;   TAB 0's count as digits and a CR
RR_SPG          EQU 19             ; the block from the firmware (the slot's bytes
RR_SOF          EQU 21             ;   16-30): the extent's start page, its offset,
RR_EXT          EQU 23             ;   its bytes; the length; the position; the
RR_LEN          EQU 25             ;   slot's page; record length, flags, mode
RR_POS          EQU 27
RR_MPG          EQU 29
RR_BREC         EQU 31
RR_BFL          EQU 32
RR_BMODE        EQU 33
RR_COL          EQU 34             ; writing: the column (a stream), or the bytes
                                   ;   in the open record (a record file)
RR_RCOL         EQU 35             ; reading a record file: its bytes given so far
RR_DIG          EQU 36             ; reading TAB 0's count: offset of the next digit
RR_SIZE         EQU 37
        ASSERT  RR_BUF == R_OUTBUF
        ASSERT  RR_SIZE + 128 <= R_ALLOC

F_REC           EQU 0              ; a record file
F_BIN           EQU 1              ; binary: no text translation
F_RD            EQU 2              ; may be read (r, u)
F_WR            EQU 3              ; may be written (w, a, u)
F_QRY           EQU 4              ; TAB 0 came: the next read is the count
F_NCR           EQU 5              ; a text line is open: the end gives a CR
F_LCR           EQU 6              ; the last byte read was a CR: drop an LF

BLOCK_LEN       EQU 15             ; the slot's block
SLOT_OFF        EQU $0200          ; the slots in the RAM disk's top page,
SLOT_LEN        EQU 32             ;   one per stream; the block at +16, so the
SLOT_LP         EQU 16+6           ;   length and position at +22

;------------------------------------------------------------------------------
; The entries from the module. Each replaces one instruction of ROM 2.4's
; code, at the same size (fddcmd.asm, IFDEF MEGABANK).
;------------------------------------------------------------------------------

; MB_OUT, MB_IN -- G_OUT and G_IN: the current channel's record by its letter
; (one compare a character). A, the character, is kept for CH_OUT.
MB_OUT: push    af
        call    RCH_LETTER
        jr      z,.r
        pop     af
        jp      CH_OUT
.r:     pop     af
        jp      RCH_OUT

MB_IN:  call    RCH_LETTER
        jp      nz,CH_IN
        jp      RCH_IN

RCH_LETTER:
        ld      hl,(CURCHL)
        ld      de,R_LETTER
        add     hl,de
        ld      a,(hl)
        cp      'R'
        ret

; BEEP_LT -- G_BEEP's test, for 'F' and 'R' records: replaces its POP HL /
; CP 'F' (the saved HL is under the return address). Z: no click.
BEEP_LT:
        ex      (sp),hl            ; HL = our return, (SP) = the letter's address
        inc     sp
        inc     sp                 ; drop it: the saved HL is at (SP)
        ex      (sp),hl            ; HL = the saved HL, our return at (SP)
        cp      'F'
        ret     z
        cp      'R'
        ret

; RCH_KIND -- CH_OPEN_HOOK's CALL SPEC_KIND: "r:..." is answered here, in
; full (DE = the spec, BC = its length); anything else goes on to SPEC_KIND.
RCH_KIND:
        ld      a,(de)
        and     $DF
        cp      'R'
        jp      nz,SPEC_KIND
        pop     hl                 ; not back to CH_OPEN_HOOK
        jp      RCH_OPEN

; RCH_CLTEST -- CH_CLOSE_HOOK's LD A,(IX+R_LETTER) / CP 'F'. An 'R' record is
; closed here, in full; otherwise A = the letter compared with 'F'.
RCH_CLTEST:
        ld      a,(ix+R_LETTER)
        cp      'R'
        jr      z,.r
        cp      'F'
        ret
.r:     pop     hl                 ; not back to CH_CLOSE_HOOK
        jp      RCH_CLOSE

; MB_TPRE -- TPI_SEND's opening (PUSH HL / PUSH DE / LD HL,(FRAMES)), done
; after a tpi:rmask when the command names "r:" (its descriptor is on top
; of the calculator stack).
MB_TPRE:
        push    hl
        push    de
        ld      hl,(STKEND)
        dec     hl
        ld      b,(hl)
        dec     hl
        ld      c,(hl)
        dec     hl
        ld      d,(hl)
        dec     hl
        ld      e,(hl)
        ex      de,hl              ; HL = the text, BC = its length
.f:     ld      a,b
        or      c
        jr      z,.no
        ld      a,(hl)
        inc     hl
        dec     bc
        and     $DF
        cp      'R'
        jr      nz,.f
        ld      a,b
        or      c
        jr      z,.no
        ld      a,(hl)
        cp      ':'
        jr      nz,.f
        call    RMASK_SEND
.no:    pop     de
        pop     hl
        pop     bc                 ; our return, in TPI_SEND
        push    hl
        push    de
        ld      hl,(FRAMES)
        push    bc
        ret

; SET_MODE_R -- the end of SET_MODE: TPMODE := A; an "r:" statement (bit 5)
; sends the mask first.
SET_MODE_R:
        ld      (MODE_SV),a
        bit     R_BIT,a
        ret     z
        ; on into RMASK_SEND

;------------------------------------------------------------------------------
; RMASK_SEND -- tpi:rmask with the mask (2 bytes), PMR1 0; its status, then
; a wait for IDLE. IX is kept.
;------------------------------------------------------------------------------
RMASK_SEND:
        push    ix
        call    RCH_MASK
        push    de                 ; the payload, at SP
        ld      hl,-R_OUTBUF
        add     hl,sp
        push    hl
        pop     ix                 ; IX + R_OUTBUF = the payload
        ld      bc,$0200           ; two bytes, PMR2 0
        xor     a
        ld      hl,CMD_RMASK
        call    CH_SEND
        call    CH_STATUS
        ld      bc,0               ; then IDLE (~1 s at most): the status comes
.idle:  in      a,($0F)            ;   at READY, and TPI_SEND's stock session
        and     $48                ;   code (unlike CH_SEND) sends its SYNC
        cp      $48                ;   without waiting, which the Pico would
        jr      z,.done            ;   lose with the pre-header behind it
        dec     bc
        ld      a,b
        or      c
        jr      nz,.idle
.done:  pop     de
        pop     ix
        ret

; RCH_MASK -- DE = the open-stream mask: bit n set if stream n (0-15) points
; at an 'R' record.
RCH_MASK:
        ld      de,0
        ld      hl,STRMS+6+31      ; stream 15's offset, its high byte
        ld      b,16
.s:     ex      de,hl
        add     hl,hl
        ex      de,hl
        ld      a,(hl)
        dec     hl
        ld      c,(hl)
        dec     hl                 ; A, C = the offset; HL -> the next one down
        push    hl
        ld      h,a
        ld      l,c
        or      c
        jr      z,.n               ; closed
        bit     7,h
        jr      nz,.n              ; SYSCON
        push    de
        ld      de,(CHANS)
        add     hl,de
        ld      de,R_LETTER-1
        add     hl,de              ; CHANS + offset - 1 + 4: the letter
        pop     de
        ld      a,(hl)
        cp      'R'
        jr      nz,.n
        inc     e
.n:     pop     hl
        djnz    .s
        ret

;------------------------------------------------------------------------------
; RCH_OPEN -- OPEN #n,"r:name"[,"mode"[,reclen]], from CH_OPEN_HOOK (through
; RCH_KIND), with the stream in (5CCBh), the spec on top of the calculator
; stack (DE, BC) and CH_ADD on a ',' if a mode follows. Parses as f: does;
; sends tpi:rchopen (PMR1 the stream, PMR2 the record length, FFh for 255 or
; more) with the payload: mask, the address the block goes to (16 bytes made
; on the stack), the mode, a space, the name. "r:" alone or a name with * or
; ? is a listing. Then the record: R_ALLOC bytes at CHANS' end, filled from
; the block. Out: C, DE = the offset, HL = the STRMS entry, as CH_OPEN_HOOK.
;------------------------------------------------------------------------------
RCH_OPEN:
        ld      a,c
        cp      MAX_ARG+3
        jp      nc,TOO_LONG
        ld      bc,R_ALLOC+ROOM    ; the record and the payload, or Report 4
        call    HC_TEST_ROOM
        ld      bc,0               ; no record length
        call    AT_END
        jr      z,.dflt0
        cp      ','
        jp      nz,NONSENSE
        call    NEXT_CHAR
        call    HC_EXPT_STR        ; the mode
        call    SKIP_SPACES
        ld      bc,0
        cp      ','
        jr      nz,.nolen
        call    NEXT_CHAR
        call    HC_EXPT_1NUM       ; ,reclen
        call    HC_FIND_INT2
.nolen: push    bc                 ; [reclen]
        call    AT_END
        jp      nz,NONSENSE
        call    POP_STR            ; DE = the mode, BC = its length
        ld      a,c
        and     a
        jr      z,.dflt
        cp      4
        jr      c,.mode
        rst     8
        db      $19                ; Q Parameter error
.dflt0: push    bc                 ; [reclen = 0]
.dflt:  ld      de,MODE_R
        ld      bc,1
.mode:  push    de
        push    bc                 ; [mode text, length]
        call    RCH_MASK
        ld      hl,(STKEND)        ; the payload, built in the workspace
        ld      (hl),e
        inc     hl
        ld      (hl),d
        inc     hl
        inc     hl
        inc     hl                 ; the block's address goes here, below
        ex      de,hl
        pop     bc
        pop     hl
        ldir                       ; the mode
        ld      a,' '
        ld      (de),a
        inc     de
        push    de
        call    PEEK_NAME
        inc     de
        inc     de                 ; past "r:"
        dec     bc
        dec     bc
        ex      de,hl
        pop     de
        ld      a,b
        or      c
        jr      z,.none            ; "r:": LDIR with BC = 0 would copy 64K
        ldir
.none:  ld      hl,(STKEND)
        ex      de,hl
        and     a
        sbc     hl,de
        ld      b,l                ; B = the payload's length
        pop     hl                 ; the record length
        push    hl
        ld      c,l
        ld      a,h
        and     a
        jr      nz,.big
        ld      a,l
        inc     a
        jr      nz,.len
.big:   ld      c,$FF              ; 255 or more: the firmware says Q
.len:   ld      hl,-16
        add     hl,sp
        ld      sp,hl              ; 16 bytes for the block, at SP
        ex      de,hl              ; DE = SP
        ld      hl,(STKEND)
        inc     hl
        inc     hl
        ld      (hl),e
        inc     hl
        ld      (hl),d             ; the block's address, in the payload
        push    ix
        ld      ix,(STKEND)
        ld      de,-R_OUTBUF
        add     ix,de              ; IX + R_OUTBUF = the payload
        ld      hl,CMD_RCHOPEN
        ld      a,(STREAM_N)
        call    CH_SEND
        call    CH_STATUS          ; F, Q, J ... raise their reports
        pop     ix
        ld      hl,(STKEND)        ; drop the spec, as $1465's STK_FETCH would
        ld      de,-5
        add     hl,de
        ld      (STKEND),hl
        ; the allocation, as CH_OPEN_HOOK's: where CHANS' $80 is, the record
        ; padded in so both bytes of its offset stay below $80
        ld      hl,(PROG)
        dec     hl
        ld      a,(hl)
        cp      $80
        jr      z,.end
        dec     hl
.end:   push    hl                 ; [start]
        ld      de,(CHANS)
        and     a
        sbc     hl,de
        inc     hl
        xor     a
        bit     7,l
        jr      z,.pad
        sub     l                  ; 256 - L
.pad:   pop     hl
        push    af                 ; [pad]
        push    hl                 ; [start]
        dec     hl
        ld      bc,R_ALLOC
        call    HC_MAKE_ROOM
        pop     hl
        push    hl
        ld      d,h
        ld      e,l
        inc     de
        ld      (hl),0
        ld      bc,R_ALLOC-1
        ldir                       ; a clean allocation
        pop     hl
        pop     af
        ld      e,a
        ld      d,0
        add     hl,de              ; HL = the record
        push    hl
        pop     ix
        ld      (ix+R_OUT),low H_OUT_STUB
        ld      (ix+R_OUT+1),high H_OUT_STUB
        ld      (ix+R_IN),low H_IN_STUB
        ld      (ix+R_IN+1),high H_IN_STUB
        ld      (ix+R_LETTER),'R'
        ld      (ix+R_PAD),a
        ld      a,(STREAM_N)
        ld      (ix+R_STRM),a
        ld      de,RR_SPG
        add     hl,de
        ex      de,hl              ; DE = the record's block
        ld      hl,0
        add     hl,sp              ; HL = the block, on the stack
        ld      bc,BLOCK_LEN
        ldir
        ld      hl,16
        add     hl,sp
        ld      sp,hl              ; drop it
        pop     bc                 ; and the record length (the block has it)
        ; the flags from the block's record length, flags and mode
        ld      a,(ix+RR_BREC)
        ld      (ix+RR_REC),a
        ld      c,0
        and     a
        jr      z,.s
        set     F_REC,c
.s:     bit     0,(ix+RR_BFL)
        jr      z,.t
        set     F_BIN,c
.t:     ld      a,(ix+RR_BMODE)
        cp      'r'
        jr      nz,.w
        set     F_RD,c
        jr      .fl
.w:     set     F_WR,c
        cp      'u'
        jr      nz,.fl
        set     F_RD,c
.fl:    ld      (ix+RR_FL),c
        push    ix
        pop     hl
        ld      de,(CHANS)
        and     a
        sbc     hl,de
        inc     hl
        ex      de,hl              ; DE = the offset
        call    STRMS_HL
        scf
        ret

;------------------------------------------------------------------------------
; RCH_CLOSE -- CLOSE # of an 'R' record (from CH_CLOSE_HOOK, through
; RCH_CLTEST): IX = the record, BC = the stream's offset. An open record is
; padded, the length and position written back, tpi:rchclose (its mask)
; sent; a refusal raises its report and leaves the stream open. Then the
; allocation goes as an 'F' record's does, every later offset moved down
; R_ALLOC. Out: C, HL = the STRMS entry, which HOME $13A8 clears.
;------------------------------------------------------------------------------
RCH_CLOSE:
        push    bc                 ; [offset]
        bit     F_WR,(ix+RR_FL)
        jr      z,.s
        bit     F_REC,(ix+RR_FL)
        jr      z,.wb
        ld      a,(ix+RR_COL)
        and     a
        call    nz,RCH_ENDREC      ; a record left open by ';'
.wb:    call    RCH_WB
.s:     call    RCH_MASK
        push    de                 ; the payload, at SP
        ld      a,(ix+R_STRM)
        push    ix
        ld      hl,2-R_OUTBUF
        add     hl,sp
        push    hl
        pop     ix                 ; IX + R_OUTBUF = the payload
        ld      bc,$0200
        ld      hl,CMD_RCHCLOSE
        call    CH_SEND
        call    CH_STATUS
        pop     ix
        pop     de
        pop     bc                 ; the offset
        ld      e,(ix+R_PAD)
        ld      d,0
        push    ix
        pop     hl
        and     a
        sbc     hl,de
        push    hl                 ; [start]
        ld      hl,STRMS           ; every offset above ours moves down R_ALLOC
        ld      a,19
.fix:   ld      e,(hl)
        inc     hl
        ld      d,(hl)             ; DE = the entry, HL -> its high byte
        bit     7,d
        jr      nz,.next           ; SYSCON
        push    hl
        ld      h,b
        ld      l,c
        and     a
        sbc     hl,de              ; C: the entry is above ours
        pop     hl
        jr      nc,.next
        dec     (hl)
.next:  inc     hl
        dec     a
        jr      nz,.fix
        pop     hl                 ; the current channel: is it this one?
        push    hl
        ld      de,(CURCHL)
        ex      de,hl
        and     a
        sbc     hl,de              ; CURCHL - start
        ld      a,0
        jr      c,.keep
        ld      a,h
        cp      high R_ALLOC
        ld      a,0
        jr      nc,.keep
        inc     a
.keep:  pop     hl
        push    af
        ld      bc,R_ALLOC
        call    HC_RECLAIM
        pop     af
        and     a
        ld      a,2
        call    nz,HC_CHAN_OPEN    ; it was: S
        call    STRMS_HL
        scf
        ret

;------------------------------------------------------------------------------
; RCH_OUT -- an 'R' record's output routine (HOME 14A0h -> G_OUT -> MB_OUT),
; A = the character. As f: does: TAB arrives as 23, low, high and is the
; position (a record file: record n); mode r drops what is printed (INPUT #'s
; prompt); TAB 0 then anything but a read is Q. Text (no 'b'): 16-21 and their
; parameter, 22 and its two, and other controls but CR and comma are dropped;
; the comma control is spaces to the next 16-column stop; keywords stay as
; their one byte. A record file: a CR ends the record and pads it (spaces,
; or 0 in binary) and isn't stored; more than the record holds is Q, the
; position back at the record's start. The length and position go back to the
; slot at each CR and each 256-byte boundary.
;------------------------------------------------------------------------------
RCH_OUT:
        ld      iy,IY_SYSVARS
        push    ix
        ld      ix,(CURCHL)
        call    RCH_PUTC
        pop     ix
        ret

RCH_PUTC:
        ld      c,a
        ld      a,(ix+RR_OST)
        and     a
        jr      nz,.st
        ld      a,c
        cp      23
        jr      z,.tab1
        bit     F_WR,(ix+RR_FL)
        ret     z                  ; mode r: dropped
        bit     F_QRY,(ix+RR_FL)
        jr      nz,.q              ; TAB 0 is only for reading
        bit     F_BIN,(ix+RR_FL)
        jr      nz,RCH_DATA
        cp      13
        jr      z,.cr
        cp      6
        jr      z,.comma
        cp      32
        jr      nc,RCH_DATA
        cp      16
        ret     c                  ; controls: dropped
        ld      b,$81
        cp      22
        jr      c,.skip            ; 16-21: one parameter
        ret     nz                 ; 24-31: dropped
        inc     b                  ; 22, AT: two
.skip:  ld      (ix+RR_OST),b
        ret
.tab1:  ld      (ix+RR_OST),1
        ret
.st:    bit     7,a
        jr      z,.tb
        dec     a                  ; a parameter dropped
        cp      $80
        jr      nz,.st2
        xor     a
.st2:   ld      (ix+RR_OST),a
        ret
.tb:    dec     a
        jr      nz,.thi
        ld      (ix+RR_TLO),c
        ld      (ix+RR_OST),2
        ret
.thi:   ld      (ix+RR_OST),0
        ld      h,c
        ld      l,(ix+RR_TLO)
        jp      RCH_TAB
.q:     rst     8
        db      $19                ; Q
.comma: ld      a,(ix+RR_COL)
        or      $F0
        neg                        ; 16 - column MOD 16
        ld      b,a
.sp:    push    bc
        ld      c,' '
        call    RCH_DATA
        pop     bc
        djnz    .sp
        ret
.cr:    bit     F_REC,(ix+RR_FL)
        jr      nz,.endr
        call    RCH_DATA           ; a stream file keeps its CR
        ld      (ix+RR_COL),0
        jp      RCH_WB
.endr:  call    RCH_ENDREC
        jp      RCH_WB

; RCH_DATA -- C, a byte to store: at the position, the column on.
RCH_DATA:
        bit     F_REC,(ix+RR_FL)
        jr      z,.put
        ld      a,(ix+RR_COL)
        cp      (ix+RR_REC)
        jr      c,.put
        ld      e,a                ; longer than the record: back to its start
        ld      d,0
        ld      l,(ix+RR_POS)
        ld      h,(ix+RR_POS+1)
        and     a
        sbc     hl,de
        ld      (ix+RR_POS),l
        ld      (ix+RR_POS+1),h
        ld      (ix+RR_COL),0
        rst     8
        db      $19                ; Q
.put:   inc     (ix+RR_COL)
        jr      RCH_PUT

; RCH_ENDREC -- the open record padded to its length; the column 0.
RCH_ENDREC:
        ld      a,(ix+RR_REC)
        sub     (ix+RR_COL)
        jr      z,.e
        ld      b,a
.p:     push    bc
        call    RCH_PADC
        call    RCH_PUT
        pop     bc
        djnz    .p
.e:     ld      (ix+RR_COL),0
        ret

; RCH_PADC -- C = the pad: a space, or 0 in binary.
RCH_PADC:
        ld      c,' '
        bit     F_BIN,(ix+RR_FL)
        ret     z
        ld      c,0
        ret

; RCH_PUT -- write C at the position and step it on; a gap from the length up
; to the position (a TAB past the end) is padded first. The length follows;
; a step onto a 256-byte boundary writes it back.
RCH_PUT:
        push    bc
.gap:   ld      l,(ix+RR_LEN)
        ld      h,(ix+RR_LEN+1)
        ld      e,(ix+RR_POS)
        ld      d,(ix+RR_POS+1)
        and     a
        sbc     hl,de
        jr      nc,.at             ; length >= position
        add     hl,de              ; HL = the length
        call    RCH_PADC
        call    RCH_WAT
        inc     hl
        ld      (ix+RR_LEN),l
        ld      (ix+RR_LEN+1),h
        jr      .gap
.at:    pop     bc
        ld      l,(ix+RR_POS)
        ld      h,(ix+RR_POS+1)
        call    RCH_WAT
        inc     hl
        ld      (ix+RR_POS),l
        ld      (ix+RR_POS+1),h
        ex      de,hl              ; DE = the position
        ld      l,(ix+RR_LEN)
        ld      h,(ix+RR_LEN+1)
        and     a
        sbc     hl,de
        jr      nc,.nl
        ld      (ix+RR_LEN),e
        ld      (ix+RR_LEN+1),d
.nl:    ld      a,e
        and     a
        ret     nz
        jp      RCH_WB             ; a 256-byte boundary

; RCH_WAT -- write C at file position HL (kept); past the extent, grow first.
RCH_WAT:
        push    hl
        ld      e,(ix+RR_EXT)
        ld      d,(ix+RR_EXT+1)
        and     a
        sbc     hl,de
        pop     hl
        call    nc,RCH_GROW
        ld      b,1
        jr      RCH_IO

; RCH_GROW -- the stream must write at HL (kept): tpi:rchgrow with the mask,
; the address for the block (16 bytes on the stack) and the length needed;
; the new extent from the block. 65535 bytes is the most: Q. BC kept.
RCH_GROW:
        push    bc
        push    hl
        inc     hl
        ld      a,h
        or      l
        jr      nz,.ok
        rst     8
        db      $19                ; Q: a channel file holds 65535 bytes
.ok:    ld      (ix+RR_BUF+4),l
        ld      (ix+RR_BUF+5),h
        call    RCH_WB             ; the firmware reads the length from the slot
        call    RCH_MASK
        ld      (ix+RR_BUF),e
        ld      (ix+RR_BUF+1),d
        ld      hl,-16
        add     hl,sp
        ld      sp,hl
        ld      (ix+RR_BUF+2),l
        ld      (ix+RR_BUF+3),h
        ld      a,(ix+R_STRM)
        ld      bc,$0600
        ld      hl,CMD_RCHGROW
        call    CH_SEND
        call    CH_STATUS          ; Q: the RAM disk is full
        push    ix
        pop     hl
        ld      de,RR_SPG
        add     hl,de
        ex      de,hl
        ld      hl,0
        add     hl,sp
        ld      bc,6               ; the start page, its offset, the extent
        ldir
        ld      hl,16
        add     hl,sp
        ld      sp,hl
        pop     hl
        pop     bc
        ret

; RCH_IO -- file position HL (kept): B = 1 write C there, 0 read it into A.
RCH_IO: push    hl
        push    de
        push    bc
        ld      e,(ix+RR_SOF)
        ld      d,(ix+RR_SOF+1)
        add     hl,de              ; the offset in the start page: 17 bits
        ld      a,0
        adc     a,a
        add     a,a
        add     a,a
        add     a,a                ; bit 16: 8 pages
        ld      e,a
        ld      a,h
        rlca
        rlca
        rlca
        and     7
        add     a,e
        ld      e,a
        ld      d,0                ; DE = pages past the start page
        ld      a,h
        and     $1F
        ld      h,a                ; HL = the offset in that page
        push    hl
        ld      l,(ix+RR_SPG)
        ld      h,(ix+RR_SPG+1)
        add     hl,de              ; HL = the page
        pop     de                 ; DE = the offset
        pop     bc
        push    bc
        call    BOARD_IO
        pop     bc
        pop     de
        pop     hl
        ret

; BOARD_IO -- board page HL, offset DE (below 2000h): B = 1 write C, 0 read
; into A. Through a window: a chunk of 4-7 that holds neither the record (IX)
; nor the stack, mapped and put back by the mover's routines (MV_MAP reads
; BASE at (IX+0): IX points at MB_MBBASE for it). IX kept.
BOARD_IO:
        push    ix
        push    bc                 ; [B, C]
        push    de                 ; [offset]
        push    hl                 ; [page]
        push    ix
        pop     hl
        ld      a,h
        call    CHUNK_BIT
        ld      b,a                ; the record's chunk
        call    MV_WIN             ; A = the window
        pop     hl                 ; the page
        push    af
        push    af                 ; MV_MAP's save area, 4 bytes at SP
        ex      de,hl
        ld      hl,0
        add     hl,sp
        ex      de,hl              ; DE = the save area, HL = the page
        ld      ix,MB_MBBASE
        call    MV_MAP             ; HL = the window
        push    hl
        ld      hl,6               ; past HL and the save area
        add     hl,sp
        ld      e,(hl)
        inc     hl
        ld      d,(hl)             ; DE = the offset
        inc     hl
        ld      c,(hl)
        inc     hl
        ld      b,(hl)             ; B, C as given
        pop     hl
        add     hl,de
        ld      a,b
        and     a
        jr      z,.rd
        ld      (hl),c
        jr      .un
.rd:    ld      c,(hl)
.un:    ld      hl,0
        add     hl,sp              ; the save area
        push    bc
        call    MV_UNMAP
        pop     bc
        pop     af
        pop     af                 ; the save area
        pop     de
        pop     de                 ; the offset, B and C
        pop     ix
        ld      a,c
        ret

; RCH_WB -- a writable stream's length and position back to its slot (4
; bytes, page RR_MPG). The write-protect switch on: J.
RCH_WB: bit     F_WR,(ix+RR_FL)
        ret     z
        ld      a,MB_STATUS
        call    MB_RD
        rra
        jr      nc,.ok
        rst     8
        db      $12                ; J: the board is write-protected
.ok:    ld      l,(ix+R_STRM)
        ld      h,0
        add     hl,hl
        add     hl,hl
        add     hl,hl
        add     hl,hl
        add     hl,hl              ; 32 x the stream
        ld      de,SLOT_OFF+SLOT_LP
        add     hl,de
        ex      de,hl              ; DE = the offset in the slot's page
        push    ix
        pop     hl
        ld      bc,RR_LEN
        add     hl,bc              ; HL = the length, then the position
        ld      b,4
.w:     push    bc
        push    hl
        push    de
        ld      c,(hl)
        ld      l,(ix+RR_MPG)
        ld      h,(ix+RR_MPG+1)
        ld      b,1
        call    BOARD_IO
        pop     de
        pop     hl
        pop     bc
        inc     hl
        inc     de
        djnz    .w
        ret

; RCH_TAB -- TAB HL: an open record (writing) is padded; TAB 0 asks for the
; count (the next read); otherwise the position is byte HL - 1, or record
; HL's start in a record file. A gap past the end is padded by the next write.
RCH_TAB:
        push    hl
        bit     F_REC,(ix+RR_FL)
        jr      z,.nr
        bit     F_WR,(ix+RR_FL)
        jr      z,.nr
        ld      a,(ix+RR_COL)
        and     a
        call    nz,RCH_ENDREC
.nr:    pop     hl
        ld      (ix+RR_COL),0
        ld      (ix+RR_RCOL),0
        ld      (ix+RR_DIG),0
        ld      a,(ix+RR_FL)
        and     $FF-(1<<F_QRY)-(1<<F_NCR)-(1<<F_LCR)
        ld      (ix+RR_FL),a
        ld      a,h
        or      l
        jr      nz,.n
        set     F_QRY,(ix+RR_FL)
        ret
.n:     dec     hl
        bit     F_REC,(ix+RR_FL)
        jr      z,.set
        ld      e,(ix+RR_REC)
        call    MUL16X8
        jr      nc,.set
        rst     8
        db      $19                ; Q: past the longest file
.set:   ld      (ix+RR_POS),l
        ld      (ix+RR_POS+1),h
        ret

; MUL16X8 -- HL = HL x E; C if it overflows 16 bits.
MUL16X8:
        ld      b,8
        ld      a,e
        ex      de,hl              ; DE = the multiplicand
        ld      hl,0
.m:     add     hl,hl
        ret     c
        rla
        jr      nc,.n
        add     hl,de
        ret     c
.n:     djnz    .m
        and     a
        ret

; DIV16X8 -- HL = HL / E, A = the remainder (E not 0). B lost.
DIV16X8:
        xor     a
        ld      b,16
.d:     add     hl,hl
        rla
        jr      c,.s
        cp      e
        jr      c,.n
.s:     sub     e
        inc     l
.n:     djnz    .d
        ret

;------------------------------------------------------------------------------
; RCH_IN -- an 'R' record's input routine (HOME 14A9h -> G_IN -> MB_IN): C with
; A = the next byte, or NC NZ at the end of the file (WAIT-KEY: Report 8). As
; f: does: a stream opened w or a is Q; TAB 0 makes the next read the count
; (records, or bytes) and a CR; a record file gives one record (padded past
; the end) and a CR. Text: LF and CRLF read as CR, other controls dropped, and
; a last line with no newline ends with a CR. Binary: every byte as it is.
;------------------------------------------------------------------------------
RCH_IN: ld      iy,IY_SYSVARS
        push    ix
        ld      ix,(CURCHL)
        call    RCH_GETC
        pop     ix
        ret

RCH_GETC:
        bit     F_RD,(ix+RR_FL)
        jr      nz,.r
        rst     8
        db      $19                ; Q: opened for writing
.r:     ld      a,(ix+RR_DIG)
        and     a
        jr      nz,.dig
        bit     F_QRY,(ix+RR_FL)
        jr      nz,.count
        bit     F_REC,(ix+RR_FL)
        jr      nz,.rec
.str:   call    RCH_RAW            ; C with A, NC at the end
        jr      nc,.end
        bit     F_BIN,(ix+RR_FL)
        ret     nz
        bit     F_LCR,(ix+RR_FL)
        res     F_LCR,(ix+RR_FL)
        jr      z,.t1
        cp      10
        jr      z,.str             ; CRLF: the LF
.t1:    cp      13
        jr      z,.cr
        cp      10
        jr      z,.lf
        cp      32
        jr      c,.str             ; controls: dropped
        set     F_NCR,(ix+RR_FL)
        scf
        ret
.cr:    set     F_LCR,(ix+RR_FL)
.lf:    res     F_NCR,(ix+RR_FL)
        ld      a,13
        scf
        ret
.end:   bit     F_NCR,(ix+RR_FL)
        jr      z,.eof
        res     F_NCR,(ix+RR_FL)
        ld      a,13               ; a last line with no newline
        scf
        ret
.eof:   xor     a
        inc     a                  ; NC NZ: Report 8
        ret
.count: res     F_QRY,(ix+RR_FL)
        ld      l,(ix+RR_LEN)
        ld      h,(ix+RR_LEN+1)
        bit     F_REC,(ix+RR_FL)
        jr      z,.num
        ld      e,(ix+RR_REC)
        call    DIV16X8
        and     a
        jr      z,.num
        inc     hl                 ; a part record counts
.num:   call    RCH_NUM
        ld      a,(ix+RR_DIG)
.dig:   ld      e,a
        ld      d,0
        push    ix
        pop     hl
        add     hl,de
        ld      a,(hl)
        inc     (ix+RR_DIG)
        cp      13
        jr      nz,.d1
        ld      (ix+RR_DIG),0
.d1:    scf
        ret
.rec:   ld      a,(ix+RR_RCOL)
        and     a
        jr      nz,.rin
        bit     F_WR,(ix+RR_FL)    ; a record being written is closed first
        jr      z,.r0
        ld      a,(ix+RR_COL)
        and     a
        call    nz,RCH_ENDREC
.r0:    ld      l,(ix+RR_POS)
        ld      h,(ix+RR_POS+1)
        ld      e,(ix+RR_LEN)
        ld      d,(ix+RR_LEN+1)
        and     a
        sbc     hl,de
        jr      nc,.eof            ; no record here
        xor     a
.rin:   cp      (ix+RR_REC)
        jr      nz,.rb
        ld      (ix+RR_RCOL),0     ; the record's end
        ld      a,13
        scf
        ret
.rb:    inc     (ix+RR_RCOL)
        call    RCH_RAW
        jr      c,.got
        call    RCH_PADC           ; past the end: the pad
        ld      l,(ix+RR_POS)
        ld      h,(ix+RR_POS+1)
        inc     hl
        ld      (ix+RR_POS),l
        ld      (ix+RR_POS+1),h
        ld      a,c
.got:   bit     F_BIN,(ix+RR_FL)
        jr      nz,.c
        cp      32
        jr      c,.rec             ; a control: dropped
.c:     scf
        ret

; RCH_RAW -- the byte at the position, the position on: C with A; NC at the
; length.
RCH_RAW:
        ld      l,(ix+RR_POS)
        ld      h,(ix+RR_POS+1)
        ld      e,(ix+RR_LEN)
        ld      d,(ix+RR_LEN+1)
        and     a
        sbc     hl,de
        ret     nc
        add     hl,de
        ld      b,0
        call    RCH_IO
        inc     hl
        ld      (ix+RR_POS),l
        ld      (ix+RR_POS+1),h
        scf
        ret

; RCH_NUM -- HL in decimal at RR_BUF, then a CR; RR_DIG points at it.
RCH_NUM:
        ld      c,0
.dv:    push    bc
        ld      e,10
        call    DIV16X8
        pop     bc
        push    af                 ; a digit
        inc     c
        ld      a,h
        or      l
        jr      nz,.dv
        push    ix
        pop     hl
        ld      de,RR_BUF
        add     hl,de
.o:     pop     af
        add     a,'0'
        ld      (hl),a
        inc     hl
        dec     c
        jr      nz,.o
        ld      (hl),13
        ld      (ix+RR_DIG),RR_BUF
        ret

CMD_RCHOPEN:    db "tpi:rchopen ",0
CMD_RCHGROW:    db "tpi:rchgrow ",0
CMD_RCHCLOSE:   db "tpi:rchclose ",0
CMD_RMASK:      db "tpi:rmask ",0
