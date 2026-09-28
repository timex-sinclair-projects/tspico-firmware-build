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
        ld      iy,IY_SYSVARS      ; the bank call clobbers IY; HOME needs it
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
        db      5

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

FDD_END:
        SAVEBIN "fddcmd.bin", FDD_BASE, FDD_END-FDD_BASE
