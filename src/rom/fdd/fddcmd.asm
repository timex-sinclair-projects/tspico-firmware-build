;******************************************************************************
;  fddcmd.asm — native disk-command extension for the TS-PICO EXROM
;
;  Assembled at $3000, spliced into the EXROM (file $7000) by build-rom.py.
;  See docs/FDD_COMMANDS_DESIGN.md and docs/DISK_COMMANDS_SPEC.md.
;
;  Entered from the HOME-ROM disk-token hook ($25D6, applied by the build
;  manifest) via the returning HOME->EXROM thunk at HOME $03FC: HL held the
;  entry ($3000), so control lands in FDD_DISPATCH with the EXROM paged and
;  returns to the BASIC interpreter when we RET. B carries the BASIC token.
;
;  BASIC calls a command's routine TWICE — once to syntax-check the statement
;  (FLAGS bit 7 clear) and once to execute it (bit 7 set). Both reach here.
;  Arguments are string expressions, checked and evaluated by HOME's class-$0A
;  routine through the EXROM->HOME thunk: the syntax pass only checks them, the
;  runtime pass pops them off the calculator stack and builds a TPI command:
;
;    CAT                -> tpi:dir               (§2)
;    CAT ""             -> tpi:tapdir
;    CAT x              -> tpi:dir x
;    MOVE TO x          -> tpi:cd x              (§3; "" -> tpi:cd -, the previous dir)
;    MOVE a TO b        -> tpi:copy a|b          ('|' can't occur in a FAT name)
;    ERASE x            -> tpi:erase x
;    FORMAT x           -> tpi:format x
;
;  The command is built in the calculator-stack workspace with a string
;  descriptor above it, and sent through the shipping SAVE "tpi:..." machinery
;  (send + scrolling display of the Pico's response) -- entered past its 31-
;  character name gate (TPI_SEND), so arguments may be up to MAX_ARG long.
;******************************************************************************

        DEVICE  NOSLOT64K

FDD_BASE        EQU $3000          ; keep in sync with FDD_ORG in build-rom.py

; --- HOME/EXROM sysvars & entry points (see rom-analysis/) --------------------
; build-rom.py checks the bytes at every ROM address below (ANCHORS), so a base
; ROM that moves one fails the build instead of jumping into the wrong code.
CH_ADD          EQU $5C5D          ; address of the next char in the BASIC line
FLAGS           EQU $5C3B          ; bit 7 set = runtime, clear = syntax check
TADDR           EQU $5C74          ; T-ADDR: low byte becomes the TPI TADDR field
STKEND          EQU $5C65          ; calculator stack end pointer (our scratch top)
FRAMES          EQU $5C78          ; frame counter: SESSION_SETUP's session id
SESSION_ID      EQU $5DD1          ; where SESSION_SETUP keeps it
SESSION_NAMED   EQU $1AAC          ; EXROM: SESSION_SETUP past its length gate,
                                   ;   entered with DE = name, BC = its length
CALL_HOME       EQU $03DD          ; EXROM->HOME returning thunk: PUSH IX / EXX /
                                   ;   LD HL,target / JP CALL_HOME (MEMORY_MAP.md)
H_EXPT_STR      EQU $1BEF          ; HOME: syntax class $0A -- SCANNING, then
                                   ;   Report C unless the result is a string
H_TEST_ROOM     EQU $1FBB          ; HOME: Report 4 unless BC bytes fit at STKEND
IY_SYSVARS      EQU $5C3A          ; what every HOME routine expects in IY

; --- SAVE/LOAD "f:name" (spec §4a) ---------------------------------------------
SESSION_SETUP   EQU $1A73          ; EXROM: where $01D2 went before the hook
SAVE_ETC_BODY   EQU $01D5          ; EXROM: stock SAVE-ETC after SESSION_SETUP's
                                   ;   non-command exit ($1A45: BC = $0011)
STATUS_REPORT   EQU $1BF3          ; EXROM: A = status-1 -> the matching report
SYNC_WRITE      EQU $2300          ; EXROM: OUT (0Fh),03, wait READY+IDLE, OUT (0Eh),A
BIOS_TX_A       EQU $1846          ; Pico Interface BIOS: OUT (0Eh),A
BIOS_RX_A       EQU $1848          ;   IN A,(0Eh)
BIOS_C_END      EQU $184A          ;   status: NC ok, else C with A = status-1
BIOS_WF_NPH     EQU $184C          ;   wait for the Pico: C with A = 02/0C/1C
C_END_TAIL      EQU $227F          ; EXROM: C_END after its wait: read the status,
                                   ;   run the response functions (v1.7's $2279 tail)
BANK_SV         EQU $5DCF          ; pre-header byte 2
MODE_SV         EQU $5DDB          ; SESSION_SETUP clears bits 7-4 for a plain name
READ_STATUS     EQU $02B9          ; EXROM: the response's status byte -> AF ($01C3's first half)
OPEN_STREAM     EQU $0426          ; EXROM: open stream A ($04F1 opens $FE, the main screen)
LOOP_BODY       EQU $21E6          ; EXROM: function $86's loop after $01C3 (PUSH AF; print/key...)
STREAM_LOWER    EQU $FD            ; stream -3: K, the lower screen
CURCHL          EQU $5C51          ; the current channel's record
THUNK_HX        EQU $03FC          ; HOME: LD (5DCD),HL / LD HL,t / JP here = call EXROM t

; --- a channel record in CHANS (spec §4; FDD_COMMANDS_DESIGN §6.1, §10.8) --------
; Each OPEN # takes CH_ALLOC bytes just before CHANS' closing $80, with the
; record R_PAD bytes in, so its STRMS offset has both bytes below $80 (channel
; select at $1239 tests D OR E). CH_ALLOC is a multiple of 256, so reclaiming
; one never changes the low byte of another's offset. The output and input
; routines are fixed stubs in HOME ($14A0/$14A9, build-rom.py), so a record
; holds no addresses that move with it.
R_OUT           EQU 0              ; output routine: HOME $14A0 -> CH_OUT
R_IN            EQU 2              ; input routine: HOME $14A9 -> CH_IN
R_LETTER        EQU 4              ; 'F'
R_STRM          EQU 5              ; the stream number (the Pico's key)
R_PAD           EQU 6              ; bytes before the record in its allocation
R_OUTN          EQU 7              ; bytes waiting in R_OUTBUF
R_INN           EQU 8              ; bytes in R_INBUF
R_INP           EQU 9              ; the next one to hand out
R_FLAGS         EQU 10             ; bit 0: a record file (OPEN # gave a length)
R_OUTBUF        EQU 11
OUTMAX          EQU 64             ; tpi:chwr sends them as hex: 9 + 128 < 256
R_INBUF         EQU R_OUTBUF+OUTMAX
INMAX           EQU 255
REC_LEN         EQU R_INBUF+INMAX
CH_ALLOC        EQU $200           ; REC_LEN + the largest pad (128) fits
H_OUT_STUB      EQU $14A0          ; HOME: DI / LD HL,CH_OUT_VEC / CALL 03FC / EI / RET
H_IN_STUB       EQU $14A9          ; HOME: DI / LD HL,CH_IN_VEC / CALL 03FC / EI / RET
H_MAKE_ROOM     EQU $12BB          ; HOME: BC bytes before (HL); Report 4
H_RECLAIM       EQU $1750          ; HOME: remove BC bytes at HL
H_CHAN_OPEN     EQU $1230          ; HOME: select stream A
STRMS           EQU $5C10          ; streams -3..15, two bytes each
CHANS           EQU $5C4F
PROG            EQU $5C53
STREAM_N        EQU $5CCB          ; OPEN/CLOSE #: the stream ($140F)
H_EXPT_1NUM     EQU $1BE5          ; HOME: syntax class $06 -- a numeric expression
H_FIND_INT2     EQU $1F23          ; HOME: the number on the stack -> BC, Report B
ERR_SP          EQU $5C3D
BANK_SP         EQU $65CE          ; the RAM bank-call stack pointer
H_TRAP          EQU $14B2          ; HOME: GUARDED's error trap
BEEPER          EQU $2000          ; EXROM: JP to the relocated HOME BEEPER
READ_DELAY      EQU 16             ; x 16 T-states between data-phase reads (~75 us)
TOK_SCREEN      EQU $AA
TOK_CODE        EQU $AF
TOK_LINE        EQU $CA
TOK_DATA        EQU $E4

MAX_ARG         EQU 64             ; longest argument (per string); longer is F
ROOM            EQU 2*MAX_ARG+32   ; workspace a command can need

CR              EQU $0D            ; BASIC end-of-line
SEP             EQU '|'            ; MOVE's source/destination separator

; --- BASIC tokens -------------------------------------------------------------
TOK_TO          EQU $CC
TOK_CAT         EQU $CF
TOK_FORMAT      EQU $D0
TOK_MOVE        EQU $D1
TOK_ERASE       EQU $D2

        ORG     FDD_BASE

;------------------------------------------------------------------------------
; FDD_DISPATCH — entry for both the syntax-check and runtime pass. B = token.
;------------------------------------------------------------------------------
FDD_DISPATCH:
        jp      G_MAIN             ; $3000: the $25D6 disk-keyword hook
F_HOOK_VEC:
        jp      F_HOOK             ; $3003: the $01D2 SAVE/LOAD hook (build-rom.py)
LOWER_VEC:
        jp      LOWER_LOOP         ; $3006: function $88 from the $2213 dispatch patch
CH_OUT_VEC:
        jp      G_OUT              ; $3009: HOME's output stub at $14A0
CH_IN_VEC:
        jp      G_IN               ; $300C: HOME's input stub at $14A9
CH_OPEN_VEC:
        jp      G_OPEN             ; $300F: OPEN #'s $145E, via HOME $1488
CH_CLOSE_VEC:
        jp      G_CLOSE            ; $3012: CLOSE #'s $13A5, via HOME $1494
BEEP_VEC:
        jp      G_BEEP             ; $3015: HOME's BEEPER thunk ($03F3 -> $041C)
OPEN_SYN_VEC:
        jp      G_OSYN             ; $3018: OPEN #'s syntax pass after a comma, via HOME $14BD
C_END_VEC:
        jp      C_END2             ; $301B: the BIOS C_END entry ($184A -> $184F, build-rom.py)

;------------------------------------------------------------------------------
; G_BEEP -- the key click and BEEP. The TS-Pico ROM moved BEEPER to EXROM
; ($2000 -> $203F) behind HOME's $03F3 thunk; BEEPER ends in EI, so the switch
; back to HOME ran with interrupts on (see GUARDED for why that can crash). The
; editor clicks for every character, so INPUT # from a file ran that switch
; hundreds of times a line. $03F3 now enters under DI and EIs back in HOME;
; this puts DI back after BEEPER's EI.
;
; The editor clicks (HL = $00C8, $0A97) for every character it takes, whatever
; the channel, so INPUT # from a file chattered through the speaker for every
; byte read (the Spectrum did the same with microdrives). That click is skipped
; when the current channel is an 'F' record; the keyboard, BEEP and the error
; buzz ($1A90) are untouched.
;------------------------------------------------------------------------------
G_BEEP: ld      a,h
        and     a
        jr      nz,.beep
        ld      a,l
        cp      $C8
        jr      nz,.beep           ; not the editor's key click
        push    hl
        ld      hl,(CURCHL)
        inc     hl
        inc     hl
        inc     hl
        inc     hl
        ld      a,(hl)             ; the channel letter
        pop     hl
        cp      'F'
        jr      z,.quiet           ; INPUT # from a file
.beep:  call    BEEPER
.quiet: di
        ret

;------------------------------------------------------------------------------
; GUARDED -- every entry that comes through HOME's returning thunk ($03FC) runs
; under an error trap. The thunk pushes a frame on the RAM bank stack at
; ($65CE) and pops it on the way back; an error unwinds the Z80 stack but never
; that one, so each report raised inside the module (or in HOME code it calls)
; used to leave it 4-8 bytes lower -- about 16 errors and it overwrites the
; bank-switch code below it. Both ROMs' RST 8 end in SP := (ERR_SP), HOME
; $1354, RET with HOME paged, so the trap is in HOME ($14B2, build-rom.py):
; POP HL / LD (65CE),HL / POP HL / LD (ERR_SP),HL / LD SP,HL / EI / RET -- the
; bank stack as it was before the thunk, interrupts back on (the HOME side of
; every entry runs the thunk under DI, see below), then on to the previous
; handler exactly as RST 8 would have gone.
;
; Interrupts: the 2068's bank switch (the RAM copy of EXROM $12BE/$134A) writes
; port FFh and then F4h with interrupts enabled; between the two, chunk 0 can
; be the empty DOCK bank, and an interrupt there runs RST 38 over $FF bytes
; until the machine is wiped. Stock only switches a few times per command; a
; channel does it for every character, which hit the window within a few
; hundred characters in ZEsarUX. So every HOME stub and trampoline that enters
; the module is DI / LD HL,vector / CALL 03FC / EI -- the whole round trip,
; both switches, with interrupts off, as the stock tpi: flows already run.
;
; HL = the routine; A, F, BC and DE reach it, and it returns AF, BC, DE, HL.
;------------------------------------------------------------------------------
G_MAIN: ld      hl,FDD_MAIN
        jr      GUARDED
G_OUT:  ld      hl,CH_OUT
        jr      GUARDED
G_IN:   ld      hl,CH_IN
        jr      GUARDED
G_OPEN: ld      hl,CH_OPEN_HOOK
        jr      GUARDED
G_OSYN: ld      hl,OPEN_SYNTAX
        jr      GUARDED
G_CLOSE:
        ld      hl,CH_CLOSE_HOOK
GUARDED:
        push    hl
        ld      hl,(ERR_SP)
        ex      (sp),hl            ; [old ERR_SP]
        push    hl
        ld      hl,(BANK_SP)
        inc     hl
        inc     hl
        inc     hl
        inc     hl
        ex      (sp),hl            ; [the bank stack before the thunk]
        push    hl
        ld      hl,H_TRAP
        ex      (sp),hl            ; [the trap]
        ld      (ERR_SP),sp
        call    JP_HL
        di                         ; the switch back to HOME must not be interrupted
        inc     sp
        inc     sp
        inc     sp
        inc     sp                 ; drop the trap and the bank stack value
        ex      (sp),hl
        ld      (ERR_SP),hl
        pop     hl
        ret

JP_HL:  jp      (hl)

FDD_MAIN:
        ld      iy,IY_SYSVARS      ; the bank call clobbers IY; HOME needs it
        ei                         ; the $25D6 hook entered under DI; CAT's "Scroll?"
                                   ;   and the Y/N prompts wait with HALT. GUARDED
                                   ;   DIs again before the switch back
        ld      a,b
        cp      TOK_CAT
        jp      z,FDD_CAT
        cp      TOK_MOVE
        jp      z,FDD_MOVE
        ld      hl,CMD_ERASE
        cp      TOK_ERASE
        jp      z,FDD_ONE_ARG
        ld      hl,CMD_FORMAT
        cp      TOK_FORMAT
        jp      z,FDD_ONE_ARG
        ret                        ; unknown token — no-op

        db      "FDDCMD",0         ; signature — build.py verifies this
FDD_VERSION:
        db      8

;------------------------------------------------------------------------------
; FDD_CAT -- CAT [string]
;------------------------------------------------------------------------------
FDD_CAT:
        call    AT_END
        jr      z,.bare
        call    EXPT_STR_END
        ret     z                  ; syntax pass: accepted
        call    POP_STR
        ld      a,b
        or      c
        ld      hl,CMD_TAPDIR
        jp      z,SEND_PREFIX      ; CAT "" -> the mounted TAP
        ld      hl,CMD_DIR_ARG
        jp      SEND_ONE
.bare:
        call    RUNTIME
        ret     z
        ld      hl,CMD_DIR
        jp      SEND_PREFIX

;------------------------------------------------------------------------------
; FDD_ONE_ARG -- ERASE string / FORMAT string.  HL = the command prefix.
;------------------------------------------------------------------------------
FDD_ONE_ARG:
        push    hl
        call    AT_END
        jr      z,NONSENSE         ; the argument is required
        call    EXPT_STR_END
        pop     hl
        ret     z
        push    hl
        call    POP_STR
        pop     hl
        call    NOT_EMPTY
        jp      SEND_ONE

;------------------------------------------------------------------------------
; FDD_MOVE -- MOVE TO string          change directory ("" = the previous one)
;             MOVE string TO string   copy
;------------------------------------------------------------------------------
FDD_MOVE:
        call    SKIP_SPACES
        cp      TOK_TO
        jr      z,.cd
        call    AT_END
        jr      z,NONSENSE
        call    HC_EXPT_STR        ; source
        call    SKIP_SPACES
        cp      TOK_TO
        jr      nz,NONSENSE
        call    NEXT_CHAR
        call    EXPT_STR_END       ; destination
        ret     z
        call    POP_STR            ; destination (top of the stack)
        call    NOT_EMPTY
        push    de                 ; [dst text]
        push    bc                 ; [dst len]
        call    POP_STR            ; source
        call    NOT_EMPTY
        push    de                 ; [src text]
        push    bc                 ; [src len]
        ld      hl,CMD_COPY
        call    BUILD_START        ; HL = start, DE = next free byte
        pop     bc                 ; src len
        ex      (sp),hl            ; HL = src text; [start] in its slot
        ldir                       ; + source
        ld      a,SEP
        ld      (de),a             ; + '|'
        inc     de
        pop     hl                 ; HL = start
        pop     bc                 ; dst len
        ex      (sp),hl            ; HL = dst text; [start]
        ldir                       ; + destination
        jp      SEND_TAIL
.cd:
        call    NEXT_CHAR
        call    EXPT_STR_END
        ret     z
        call    POP_STR
        ld      a,b
        or      c
        ld      hl,CMD_CD_BACK
        jp      z,SEND_PREFIX      ; MOVE TO "" -> the previous directory
        ld      hl,CMD_CD
        jp      SEND_ONE

NONSENSE:
        rst     8
        db      $0B                ; C Nonsense in BASIC
TOO_LONG:
        rst     8
        db      $0E                ; F Invalid file name

;------------------------------------------------------------------------------
; Parsing helpers
;------------------------------------------------------------------------------

; SKIP_SPACES -- A = the character at CH_ADD, stepping CH_ADD over spaces.
SKIP_SPACES:
        ld      hl,(CH_ADD)
.loop:  ld      a,(hl)
        cp      ' '
        jr      nz,.done
        inc     hl
        jr      .loop
.done:  ld      (CH_ADD),hl
        ret

; NEXT_CHAR -- step CH_ADD over one character (a token such as TO).
NEXT_CHAR:
        ld      hl,(CH_ADD)
        inc     hl
        ld      (CH_ADD),hl
        ret

; AT_END -- Z if the statement ends here (':' or end of line).
AT_END:
        call    SKIP_SPACES
        cp      CR
        ret     z
        cp      ':'
        ret

; EXPT_STR_END -- a string expression that ends the statement. Returns Z on
; the syntax pass (nothing more to do), NZ on the runtime pass (string stacked).
EXPT_STR_END:
        call    HC_EXPT_STR
        call    AT_END
        jr      nz,NONSENSE
        ; fall through
RUNTIME:                           ; NZ at run time, Z on the syntax pass
        ld      a,(FLAGS)
        and     $80
        ret

; HC_EXPT_STR -- run HOME's class-$0A routine (string expression, C if not).
HC_EXPT_STR:
        push    ix
        exx
        ld      hl,H_EXPT_STR
        jp      CALL_HOME

; POP_STR -- pop a string off the calculator stack: DE = text, BC = length.
; Report F if it is longer than MAX_ARG.
POP_STR:
        ld      hl,(STKEND)
        dec     hl
        ld      b,(hl)
        dec     hl
        ld      c,(hl)
        dec     hl
        ld      d,(hl)
        dec     hl
        ld      e,(hl)
        dec     hl
        ld      (STKEND),hl
        ld      a,b
        and     a
        jr      nz,TOO_LONG
        ld      a,c
        cp      MAX_ARG+1
        jr      nc,TOO_LONG
        ret

; NOT_EMPTY -- Report F for an empty name (BC = 0).
NOT_EMPTY:
        ld      a,b
        or      c
        ret     nz
        jr      TOO_LONG

;------------------------------------------------------------------------------
; Building and sending the command
;------------------------------------------------------------------------------

; BUILD_START -- make sure there is room (Report 4 if not), then copy the
; prefix (HL, NUL-ended) to STKEND. Returns HL = start, DE = next free byte.
BUILD_START:
        push    hl
        ld      bc,ROOM
        call    HC_TEST_ROOM
        pop     hl
        ld      de,(STKEND)
        push    de
        call    COPY_CSTR
        pop     hl
        ret

HC_TEST_ROOM:
        push    ix
        exx
        ld      hl,H_TEST_ROOM
        jp      CALL_HOME

; SEND_PREFIX -- send the prefix at HL on its own.
SEND_PREFIX:
        call    BUILD_START
        push    hl                 ; [start]
        jr      SEND_TAIL

; SEND_ONE -- send prefix HL + the string DE (text) / BC (length).
SEND_ONE:
        push    de                 ; [text]
        push    bc                 ; [len]
        call    BUILD_START
        pop     bc
        ex      (sp),hl            ; HL = text; [start]
        ldir
        ; fall through

; SEND_TAIL -- DE = end of the command, [start] on the stack.
SEND_TAIL:
        pop     hl                 ; HL = start
        ld      a,e
        sub     l
        ld      c,a
        ld      a,d
        sbc     a,h
        ld      b,a                ; BC = length
        ex      de,hl              ; HL = end (descriptor position), DE = start
        ld      (hl),0             ; string descriptor, as SAVE "..." leaves it
        inc     hl
        ld      (hl),e
        inc     hl
        ld      (hl),d
        inc     hl
        ld      (hl),c
        inc     hl
        ld      (hl),b
        inc     hl
        ld      (STKEND),hl
        xor     a                  ; T-ADDR := 0 (TADDR field = SAVE)
        ld      (TADDR),a
        ld      (TADDR+1),a
        ; fall through

; TPI_SEND -- SESSION_SETUP ($1A73) without its 5-31 character name gate: the
; same entry work ($1A73-$1A7D), then straight to the named-session code with
; DE = name, BC = length. Everything past the gate keeps the name as a pointer
; and a 16-bit length, and the Pico sizes its buffer from the pre-header.
TPI_SEND:
        push    hl
        push    de
        ld      hl,(FRAMES)
.nz:    inc     hl                 ; a session id that is never 0
        ld      a,h
        or      l
        jr      z,.nz
        ld      (SESSION_ID),hl
        ld      hl,(STKEND)
        dec     hl
        ld      b,(hl)
        dec     hl
        ld      c,(hl)
        dec     hl
        ld      d,(hl)
        dec     hl
        ld      e,(hl)
        jp      SESSION_NAMED

; COPY_CSTR — copy the NUL-terminated string at (HL) to (DE).
COPY_CSTR:
        ld      a,(hl)
        inc     hl
        and     a
        ret     z
        ld      (de),a
        inc     de
        jr      COPY_CSTR

;------------------------------------------------------------------------------
; F_HOOK -- SAVE / LOAD / VERIFY / MERGE "f:<path>"            (spec §4a)
;
; $01D2 (the runtime SAVE-ETC's only jump to SESSION_SETUP) comes here instead.
; The name is on the calculator stack, T-ADDR is 0-3, CH_ADD points past the
; name. Anything that isn't "f:..." goes on to SESSION_SETUP untouched.
;
; For "f:<path>": send tpi:fopen <path> (PMR1 = T-ADDR + 256 * the next token,
; PMR2 = this statement's session) through the Pico Interface BIOS -- it returns
; here, prints only what the Pico asks it to, and leaves CH_ADD alone -- then
; shorten the name (SAVE: <= 10 characters of the path, a stand-in the Pico
; ignores; LOAD/VERIFY/MERGE: "", any name) and carry on with the stock body
; exactly as SESSION_SETUP's non-command exit does. The Pico writes the SAVE
; to <path>, or serves <path> as a one-shot tape for the LOAD.
;------------------------------------------------------------------------------
F_HOOK:
        push    hl                 ; as SESSION_SETUP does; popped at the exit
        push    de
        call    PEEK_NAME          ; DE = text, BC = length
        ld      a,b
        and     a
        jr      nz,.stock
        ld      a,c
        cp      3
        jr      c,.stock           ; "f:" and at least one character
        ld      a,(de)
        and     $DF
        cp      'F'
        jr      nz,.stock
        inc     de
        ld      a,(de)
        cp      ':'
        jr      nz,.stock
        ld      a,c
        cp      MAX_ARG+3
        jp      nc,TOO_LONG
        ld      hl,(FRAMES)        ; the session id, as SESSION_SETUP makes it
.nz:    inc     hl
        ld      a,h
        or      l
        jr      z,.nz
        ld      (SESSION_ID),hl
        push    ix
        call    SEND_FOPEN         ; an error status raises its report
        pop     ix
        ld      hl,(STKEND)        ; shorten the name in place
        dec     hl
        dec     hl                 ; -> length low
        ld      a,(TADDR)
        and     a
        jr      nz,.anyname
        ld      a,(hl)
        sub     2                  ; the path, without "f:"
        cp      11
        jr      c,.fits
        ld      a,10
.fits:  ld      (hl),a
        dec     hl
        dec     hl                 ; -> address low
        ld      a,(hl)
        add     a,2
        ld      (hl),a
        inc     hl
        ld      a,(hl)
        adc     a,0
        ld      (hl),a
        jr      .go
.anyname:
        ld      (hl),0             ; LOAD "": the one-shot tape holds one file
.go:    ld      a,(MODE_SV)
        and     $0F
        ld      (MODE_SV),a
        pop     de
        pop     hl
        ld      bc,$0011
        jp      SAVE_ETC_BODY
.stock:
        pop     de
        pop     hl
        jp      SESSION_SETUP

; PEEK_NAME -- the string on top of the calculator stack, not popped:
; DE = text, BC = length.
PEEK_NAME:
        ld      hl,(STKEND)
        dec     hl
        ld      b,(hl)
        dec     hl
        ld      c,(hl)
        dec     hl
        ld      d,(hl)
        dec     hl
        ld      e,(hl)
        ret

; SEND_FOPEN -- the 'B' command "tpi:fopen <path>", by hand through the BIOS:
; pre-header 'B', 0 (a SAVE "tpi:" command), BANK, PMR1 (operation, token),
; PMR2 (session), LEN, XOR; the preloaded status; wait for the Pico; body 'D',
; LEN, text, XOR; the status. D = running XOR, E = token, C = command length.
SEND_FOPEN:
        ld      hl,(CH_ADD)        ; the token after the name, CH_ADD untouched
.sp:    ld      a,(hl)
        inc     hl
        cp      ' '
        jr      z,.sp
        cp      TOK_CODE
        jr      z,.tok
        cp      TOK_SCREEN
        jr      z,.tok
        cp      TOK_DATA
        jr      z,.tok
        cp      TOK_LINE
        jr      z,.tok
        xor     a
.tok:   push    af
        call    PEEK_NAME
        inc     de
        inc     de
        ex      de,hl              ; HL = path
        ld      a,c
        sub     2
        ld      b,a                ; B = path length
        add     a,FOPEN_LEN
        ld      c,a                ; C = command length (< 128)
        pop     af
        ld      e,a                ; E = token
        push    hl
        push    bc
        ld      a,'B'
        ld      d,a
        call    SYNC_WRITE
        xor     a
        call    TXX                ; T-ADDR 0: a command
        ld      a,(BANK_SV)
        call    TXX
        ld      a,(TADDR)
        call    TXX                ; PMR1 low: 0 SAVE, 1 LOAD, 2 VERIFY, 3 MERGE
        ld      a,e
        call    TXX                ; PMR1 high: CODE / SCREEN$ / DATA / LINE / 0
        ld      a,(SESSION_ID)
        call    TXX                ; PMR2: the session
        ld      a,(SESSION_ID+1)
        call    TXX
        ld      a,c
        call    TXX                ; LEN
        xor     a
        call    TXX
        ld      a,d
        call    BIOS_TX_A          ; the pre-header's XOR
        call    BIOS_RX_A          ; the preloaded status
        call    BIOS_WF_NPH
        jr      c,WF_FAIL
        pop     bc
        pop     hl
        ld      a,'D'
        ld      d,a
        call    BIOS_TX_A
        ld      a,c
        call    TXX
        xor     a
        call    TXX
        push    hl
        push    bc
        ld      hl,FOPEN_TXT
        ld      b,FOPEN_LEN
        call    TX_STR
        pop     bc
        pop     hl
        call    TX_STR             ; the path
        ld      a,d
        call    BIOS_TX_A          ; the body's XOR
        call    BIOS_C_END
        ret     nc
        jp      C_FAIL             ; A = status-1: F, Q, R ... as for tpi: commands

; TXX -- send A and fold it into the XOR in D.
TXX:    push    af
        xor     d
        ld      d,a
        pop     af
        jp      BIOS_TX_A

; TX_STR -- send B (>0) bytes from HL through TXX.
TX_STR: ld      a,(hl)
        inc     hl
        call    TXX
        djnz    TX_STR
        ret

WF_FAIL:                           ; the Pico didn't answer the pre-header
        cp      $0C
        jr      z,.brk
        cp      $1C
        jr      z,.rst
        rst     8
        db      $12                ; J Invalid I/O device (timeout)
.brk:   rst     8
        db      $0C                ; D BREAK - CONT repeats
.rst:   rst     8
        db      $1C                ; T TS-Pico reset, try again

; C_FAIL -- after a C_END failure: A = status-1 (its report), or 0Ch BREAK / 1Ch
; the Pico reset the transaction, which STATUS_REPORT would both call D.
C_FAIL: cp      $0C
        jr      z,WF_FAIL.brk
        cp      $1C
        jr      z,WF_FAIL.rst
        jp      STATUS_REPORT

;------------------------------------------------------------------------------
; C_END2 -- the Pico Interface BIOS's C_END on ROM 2.1 (the table entry at
; $184A reaches it through $184F, patched by build-rom.py).
;
; ROM 2.0's C_END ($23CD) failed with A = 02h both when the Pico never said
; READY (a timeout, BIOS_WF_NPH's code) and for status 3 (A = status-1 = 02h,
; Report F), so a caller couldn't tell a silent Pico from a bad file name --
; and this module's callers reported a timeout as F. Here every failure comes
; back ready for STATUS_REPORT or C_FAIL:
;   an error status   A = status-1 (01h R, 02h F, ... 09h J, 0Ah and up D)
;   timeout           A = 09h, J -- what the ROM's own commands report then
;   BREAK             A = 0Ch (abort byte already sent; as before)
;   Pico reset        A = 1Ch (as before)
; 0Ch and 1Ch are never status-1 values: the firmware's highest status is 11.
; Carry set on failure, clear for status 1 (A = 0), as the BIOS always did.
;------------------------------------------------------------------------------
C_END2: call    BIOS_WF_NPH
        jp      nc,C_END_TAIL
        cp      $02
        scf
        ret     nz                 ; 0Ch / 1Ch
        ld      a,$09              ; the timeout: J, never F
        ret                        ; (carry still set)

FOPEN_TXT:   db "tpi:fopen "
FOPEN_LEN    EQU $-FOPEN_TXT

;------------------------------------------------------------------------------
; LOWER_LOOP -- response function $88: function $86 ("print string with loop",
; the Y/N prompt) on the LOWER screen, so a prompt doesn't write over the
; picture -- which SAVE "f:x" SCREEN$ would then save. Reached from the
; function dispatcher's last, otherwise dead, check at $2213 (patched to
; CP 87h / JP Z,$3006 / RET) with A = function - 1.
;
; Exactly $86's handler with a different stream: $01C3 is READ_STATUS then
; "open stream $FE"; this opens $FD instead and joins $86's loop, which prints
; through the current channel and leaves via its own POP AF / RET.
; The Pico only sends $88 to a ROM it knows has it (tpi:fopen comes only from
; this module).
;------------------------------------------------------------------------------
LOWER_LOOP:
        call    READ_STATUS
        push    af
        ld      a,STREAM_LOWER
        call    OPEN_STREAM
        pop     af
        jp      LOOP_BODY

;------------------------------------------------------------------------------
; Channel driver (stage 1: sequential)                      (spec §4)
;
; OPEN #n,"f:path"[,"mode"] builds an 'F' record in CHANS and points stream n
; at it; CLOSE #n flushes it, tells the Pico and takes the record out again.
; Both come here from one-instruction HOME patches (a CALL redirected to a
; trampoline in the dead $1488-$14C6) through the returning thunk at $03FC.
;
; CH_OUT and CH_IN are a record's output and input routines: RST 10 and INCH
; call its HOME stubs, the stubs come here through the same thunk, and CURCHL
; points at the record. Output is buffered and sent as tpi:chwr <hex>; input is
; fetched 255 bytes at a time with tpi:chrd. At the end of the file CH_IN
; returns NC NZ, which the ROM's WAIT-KEY ($11CF) turns into Report 8 by itself.
;
; Every exchange keeps CURCHL: the command goes out mid-statement (inside PRINT #
; or INPUT #), and the Pico answers channel commands with a bare status that
; prints nothing, but C_END could still open the screen for a message.
;------------------------------------------------------------------------------

; CH_OPEN_HOOK -- HOME $145E's CALL $1465 goes to $1488 (LD HL,CH_OPEN_VEC /
; CALL 03FC / RET C / JP 1465). The stream is ($5CCB), the spec string is on
; top of the calculator stack, and CH_ADD is on the ',' of a mode, if any (the
; syntax pass skipped everything after it). Not "f:": NC, HL = the STRMS entry,
; the stack untouched, for the stock $1465. "f:": C, DE = the new offset, HL =
; the STRMS entry, which $1461 stores.
CH_OPEN_HOOK:
        ld      iy,IY_SYSVARS
        call    PEEK_NAME          ; DE = text, BC = length
        ld      a,b
        and     a
        jp      nz,STRMS_NC
        ld      a,c
        cp      2
        jp      c,STRMS_NC
        inc     de
        ld      a,(de)
        dec     de
        cp      ':'
        jp      nz,STRMS_NC
        ld      a,(de)
        and     $DF
        cp      'D'                ; "d:[pattern]" (stage 3): a directory listing
        jr      z,.ours
        cp      'F'
        jp      nz,STRMS_NC
        ld      a,c
        cp      3
        jp      c,STRMS_NC         ; "f:" and at least one character
.ours:  ld      a,c
        cp      MAX_ARG+3
        jp      nc,TOO_LONG
        ld      bc,CH_ALLOC+ROOM   ; the record and the command, or Report 4
        call    HC_TEST_ROOM       ;   before the Pico hears of it
        ld      bc,0               ; no record length: a stream
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
        call    HC_EXPT_1NUM       ; ,reclen (stage 2): a record file
        call    HC_FIND_INT2       ; BC
.nolen: push    bc                 ; [reclen]
        call    AT_END
        jp      nz,NONSENSE
        call    POP_STR            ; DE = mode, BC = its length
        ld      a,c
        and     a
        jr      z,.dflt            ; "": read
        cp      4
        jr      c,.mode
        rst     8
        db      $19                ; Q Parameter error
.dflt0: push    bc                 ; [reclen = 0]
.dflt:  ld      de,MODE_R
        ld      bc,1
.mode:  push    bc
        push    de
        ld      hl,CMD_CHOPEN      ; tpi:chopen <mode> <path>, built at STKEND
        ld      de,(STKEND)
        call    COPY_CSTR
        pop     hl
        pop     bc
        ldir
        ld      a,' '
        ld      (de),a
        inc     de
        push    de
        call    PEEK_NAME
        ld      a,(de)
        and     $DF
        cp      'D'
        jr      z,.keep            ; "d:..." goes as it is: the Pico lists it
        inc     de
        inc     de                 ; past "f:"
        dec     bc
        dec     bc
.keep:  ex      de,hl
        pop     de
        ld      a,b
        or      c
        jr      z,.none            ; LDIR with BC = 0 would copy 64K
        ldir
.none:
        xor     a
        ld      (de),a
        pop     bc
        push    bc                 ; the record length
        ld      a,b
        and     a
        jr      z,.len
        ld      c,$FF              ; over 255: the Pico says Q
.len:   ld      b,0                ; no payload, PMR2 = the record length
        ld      hl,(STKEND)
        ld      a,(STREAM_N)
        call    CH_SEND
        call    CH_STATUS          ; F, Q ... raise their reports
        ld      hl,(STKEND)        ; drop the spec, as $1465's STK_FETCH would
        ld      de,-5
        add     hl,de
        ld      (STKEND),hl
        ; the allocation goes where CHANS' $80 is; pad the record in so both
        ; bytes of its offset (record - CHANS + 1) are below $80. On the 2068
        ; one spare byte sits between that $80 and PROG.
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
        inc     hl                 ; the offset with no pad
        xor     a
        bit     7,l
        jr      z,.pad
        sub     l                  ; 256 - L
.pad:   pop     hl
        push    af                 ; [pad]
        push    hl                 ; [start]
        dec     hl                 ; MAKE_ROOM opens the space AFTER (HL), so
        ld      bc,CH_ALLOC        ;   the $80 moves up past the allocation
        call    HC_MAKE_ROOM
        pop     hl
        push    hl
        ld      d,h
        ld      e,l
        inc     de
        ld      (hl),0
        ld      bc,CH_ALLOC-1
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
        ld      (ix+R_LETTER),'F'
        ld      (ix+R_PAD),a
        ld      a,(STREAM_N)
        ld      (ix+R_STRM),a
        pop     bc                 ; the record length
        ld      a,b
        or      c
        jr      z,.strm
        ld      (ix+R_FLAGS),1
.strm:
        ld      de,(CHANS)
        and     a
        sbc     hl,de
        inc     hl
        ex      de,hl              ; DE = the offset
        call    STRMS_HL
        scf
        ret

; OPEN_SYNTAX -- stock OPEN #'s syntax pass skipped everything after the
; spec's comma ($1438 CALL $2569). That also skipped storing the hidden five-byte
; form of each number, so a number there (the record length) could not be
; evaluated at run time. $1438 now comes here (HOME $14BD) with CH_ADD on the
; ',': a string (the mode), then optionally ',' and a numeric expression; $143B's
; CHECK_END then wants the end of the statement. A K/S/P OPEN # with extra
; arguments is still Report C, now as a syntax error.
OPEN_SYNTAX:
        ld      iy,IY_SYSVARS
        call    NEXT_CHAR
        call    HC_EXPT_STR        ; the mode
        call    SKIP_SPACES
        cp      ','
        ret     nz
        call    NEXT_CHAR
        jp      HC_EXPT_1NUM       ; the record length

STRMS_NC:
        call    STRMS_HL
        and     a
        ret

; STRMS_HL -- HL = stream ($5CCB)'s STRMS entry, $5C16 + 2n.
STRMS_HL:
        ld      a,(STREAM_N)
        add     a,a
        add     a,low (STRMS+6)
        ld      l,a
        ld      h,high STRMS
        ret

; CH_CLOSE_HOOK -- HOME $13A5's CALL $13BE goes to $1494 (DI / LD HL,
; CH_CLOSE_VEC / CALL 03FC / EI / RET C / JP 13BE). BC = the stream's offset (not 0), the stream
; is ($5CCB). Not an 'F' record: NC with HL = the STRMS entry, BC and A = B|C,
; for the stock $13BE. 'F': flush, tpi:chclose, reclaim the allocation, move
; every later offset down; C with HL = the STRMS entry, which $13A8 resets.
CH_CLOSE_HOOK:
        ld      iy,IY_SYSVARS
        bit     7,b
        jr      nz,.stock          ; SYSCON
        ld      hl,(CHANS)
        add     hl,bc
        dec     hl
        push    hl
        pop     ix                 ; the record
        ld      a,(ix+R_LETTER)
        cp      'F'
        jr      z,.ours
.stock: call    STRMS_HL
        ld      a,b
        or      c                  ; NC
        ret
.ours:  push    bc                 ; [offset]
        call    CH_FLUSH
        ld      a,(ix+R_STRM)
        ld      hl,CMD_CHCLOSE
        ld      bc,0
        call    CH_SEND
        call    CH_STATUS
        pop     bc
        ld      e,(ix+R_PAD)
        ld      d,0
        push    ix
        pop     hl
        and     a
        sbc     hl,de
        push    hl                 ; [start]
        ; every offset above ours moves down CH_ALLOC ($200): high byte - 2
        ld      hl,STRMS
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
        dec     (hl)
.next:  inc     hl
        dec     a
        jr      nz,.fix
        ; is the current channel this one? then it goes (POINTERS would leave
        ; CURCHL CH_ALLOC below it, in someone else's bytes): select S after
        pop     hl
        push    hl
        ld      de,(CURCHL)
        ex      de,hl
        and     a
        sbc     hl,de              ; CURCHL - start
        ld      a,0
        jr      c,.keep
        ld      a,h
        cp      high CH_ALLOC
        ld      a,0
        jr      nc,.keep
        inc     a
.keep:  pop     hl
        push    af
        ld      bc,CH_ALLOC
        call    HC_RECLAIM
        pop     af
        and     a
        ld      a,2
        call    nz,HC_CHAN_OPEN
        call    STRMS_HL
        scf
        ret

HC_EXPT_1NUM:
        push    ix
        exx
        ld      hl,H_EXPT_1NUM
        jp      CALL_HOME

HC_FIND_INT2:
        push    ix
        exx
        ld      hl,H_FIND_INT2
        jp      CALL_HOME

HC_MAKE_ROOM:
        push    ix
        exx
        ld      hl,H_MAKE_ROOM
        jp      CALL_HOME

HC_RECLAIM:
        push    ix
        exx
        ld      hl,H_RECLAIM
        jp      CALL_HOME

HC_CHAN_OPEN:
        push    ix
        exx
        ld      hl,H_CHAN_OPEN
        jp      CALL_HOME

CH_OUT:
        ld      iy,IY_SYSVARS
        push    ix
        ld      ix,(CURCHL)
        ld      c,a
        cp      23                 ; TAB (stage 2): a seek, so what was read
        jr      nz,.put            ;   ahead is no longer next
        ld      (ix+R_INN),0
        ld      (ix+R_INP),0
.put:   ld      a,(ix+R_OUTN)
        push    ix
        pop     hl
        ld      de,R_OUTBUF
        add     hl,de
        ld      e,a
        ld      d,0
        add     hl,de
        ld      (hl),c             ; into the buffer
        inc     a
        ld      (ix+R_OUTN),a
        cp      OUTMAX
        jr      nc,.send
        ld      a,c                ; a record file sends at each CR, so a
        cp      13                 ;   record that is too long is Report Q
        jr      nz,.done           ;   on the PRINT that made it
        bit     0,(ix+R_FLAGS)
        jr      z,.done
.send:  call    CH_FLUSH
.done:  pop     ix
        ret

CH_IN:
        ld      iy,IY_SYSVARS
        push    ix
        ld      ix,(CURCHL)
.again: ld      a,(ix+R_INP)
        cp      (ix+R_INN)
        jr      c,.have
        call    CH_FLUSH           ; what was printed first (INPUT #4;TAB n: the seek)
        call    CH_FETCH           ; NZ: end of file
        jr      z,.again
        pop     ix
        xor     a
        inc     a                  ; NC NZ: WAIT-KEY gives Report 8
        ret
.have:  ld      e,a
        inc     a
        ld      (ix+R_INP),a
        ld      d,0
        push    ix
        pop     hl
        add     hl,de
        ld      de,R_INBUF
        add     hl,de
        ld      a,(hl)
        pop     ix
        scf
        ret

; CH_FLUSH -- send what R_OUTBUF holds (IX = the record). Keeps CURCHL. The
; count is cleared first: if the Pico refuses the bytes, they are dropped with
; the report, and CLOSE # can still close the stream.
CH_FLUSH:
        ld      a,(ix+R_OUTN)
        and     a
        ret     z
        ld      b,a                ; payload count
        ld      (ix+R_OUTN),0
        ld      c,0                ; PMR2
        ld      a,(ix+R_STRM)
        ld      hl,CMD_CHWR
        call    CH_SEND
        jp      CH_STATUS          ; C_END, reports on error

; CH_FETCH -- refill R_INBUF from the Pico (IX = the record): Z when it has
; bytes, NZ at the end of the file. The data phase: status, count, bytes, XOR.
CH_FETCH:
        ld      b,0                ; no payload
        ld      c,INMAX            ; PMR2: how many
        ld      a,(ix+R_STRM)
        ld      hl,CMD_CHRD
        call    CH_SEND
        call    BIOS_WF_NPH
        jp      c,WF_FAIL
        call    BIOS_RX_A          ; status
        cp      1
        jr      z,.data
        cp      7
        jr      nz,.err
        or      a                  ; end of file: NZ
        ret
.err:   dec     a
        jp      STATUS_REPORT
.data:  call    BIOS_RX_A          ; count, 1-255
        ld      b,a
        ld      (ix+R_INN),a
        ld      (ix+R_INP),0
        push    ix
        pop     hl
        ld      de,R_INBUF
        add     hl,de
        ld      d,0                ; running XOR
.byte:  ld      e,READ_DELAY       ; pace like LOAD: the Pico feeds a 4-deep FIFO
.dly:   dec     e
        jr      nz,.dly
        call    BIOS_RX_A
        ld      (hl),a
        inc     hl
        xor     d
        ld      d,a
        djnz    .byte
        ld      e,READ_DELAY
.dly2:  dec     e
        jr      nz,.dly2
        call    BIOS_RX_A          ; the XOR
        cp      d
        jr      nz,.bad
        xor     a                  ; Z: bytes to hand out
        ret
.bad:   rst     8
        db      $1A                ; R Tape loading error: a starved FIFO

; CH_STATUS -- C_END, keeping CURCHL; an error status raises its report.
CH_STATUS:
        ld      hl,(CURCHL)
        push    hl
        call    BIOS_C_END
        pop     hl
        ld      (CURCHL),hl
        ret     nc
        jp      C_FAIL

; CH_SEND -- the 'B' command <prefix HL>[hex of B bytes from IX+R_OUTBUF],
; PMR1 = A (the stream), PMR2 = C, through the BIOS; stops after the body (the
; caller reads the answer).
CH_SEND:
        push    af                 ; [stream]
        push    hl
        push    bc
        call    STRLEN             ; A = prefix length
        pop     bc
        add     a,b
        add     a,b                ; + 2 per payload byte
        ld      e,a                ; E = command length (< 256)
        pop     hl
        pop     af
        push    hl                 ; [prefix]
        push    bc                 ; [count, PMR2]
        push    af
        ld      bc,0               ; wait (~1 s at most) for IDLE: the Pico
.idle:  in      a,($0F)            ;   answers channel commands READY but not
        and     $48                ;   IDLE until PROCESS_CMD's tail is done,
        cp      $48                ;   and a SYNC sent before then is lost
        jr      z,.sync            ;   with the pre-header behind it (T)
        dec     bc
        ld      a,b
        or      c
        jr      nz,.idle
.sync:  pop     af
        pop     bc
        push    bc
        push    af
        ld      a,'B'
        ld      d,a                ; D = running XOR
        call    SYNC_WRITE
        xor     a
        call    TXX                ; T-ADDR 0: a command
        ld      a,(BANK_SV)
        call    TXX
        pop     af
        call    TXX                ; PMR1: the stream
        xor     a
        call    TXX
        ld      a,c
        call    TXX                ; PMR2
        xor     a
        call    TXX
        ld      a,e
        call    TXX                ; LEN
        xor     a
        call    TXX
        ld      a,d
        call    BIOS_TX_A
        call    BIOS_RX_A          ; the preloaded status
        call    BIOS_WF_NPH
        jp      c,WF_FAIL
        ld      a,'D'
        ld      d,a
        call    BIOS_TX_A
        ld      a,e
        call    TXX
        xor     a
        call    TXX
        pop     bc
        pop     hl
        push    bc
.pre:   ld      a,(hl)             ; the prefix
        inc     hl
        and     a
        jr      z,.hex
        call    TXX
        jr      .pre
.hex:   pop     bc
        ld      a,b
        and     a
        jr      z,.end
        push    de                 ; D is the running XOR
        push    ix
        pop     hl
        ld      de,R_OUTBUF
        add     hl,de
        pop     de
.hx:    ld      a,(hl)
        inc     hl
        push    af
        rrca
        rrca
        rrca
        rrca
        call    HEXDIG
        pop     af
        call    HEXDIG
        djnz    .hx
.end:   ld      a,d
        jp      BIOS_TX_A          ; the body's XOR

HEXDIG: and     $0F
        add     a,'0'
        cp      '9'+1
        jr      c,.d
        add     a,'a'-'9'-1
.d:     jp      TXX

STRLEN: ld      c,0                ; A = length of the NUL-ended string at HL
.l:     ld      a,(hl)
        inc     hl
        and     a
        jr      z,.e
        inc     c
        jr      .l
.e:     ld      a,c
        ret

;------------------------------------------------------------------------------
; TPI command prefixes (NUL-terminated).
;------------------------------------------------------------------------------
CMD_DIR:     db "tpi:dir",0
CMD_DIR_ARG: db "tpi:dir ",0
CMD_TAPDIR:  db "tpi:tapdir",0
CMD_CD:      db "tpi:cd ",0
CMD_CD_BACK: db "tpi:cd -",0
CMD_COPY:    db "tpi:copy ",0
CMD_ERASE:   db "tpi:erase ",0
CMD_FORMAT:  db "tpi:format ",0
CMD_CHWR:    db "tpi:chwr ",0
CMD_CHRD:    db "tpi:chrd",0
CMD_CHCLOSE: db "tpi:chclose",0
CMD_CHOPEN:  db "tpi:chopen ",0
MODE_R:      db "r"

FDD_END:
        SAVEBIN "fddcmd.bin", FDD_BASE, FDD_END-FDD_BASE
