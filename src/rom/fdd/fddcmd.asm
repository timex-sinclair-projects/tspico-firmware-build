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
BANK_SV         EQU $5DCF          ; pre-header byte 2
MODE_SV         EQU $5DDB          ; SESSION_SETUP clears bits 7-4 for a plain name
READ_STATUS     EQU $02B9          ; EXROM: the response's status byte -> AF ($01C3's first half)
OPEN_STREAM     EQU $0426          ; EXROM: open stream A ($04F1 opens $FE, the main screen)
LOOP_BODY       EQU $21E6          ; EXROM: function $86's loop after $01C3 (PUSH AF; print/key...)
STREAM_LOWER    EQU $FD            ; stream -3: K, the lower screen
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
        jp      FDD_MAIN           ; $3000: the $25D6 disk-keyword hook
F_HOOK_VEC:
        jp      F_HOOK             ; $3003: the $01D2 SAVE/LOAD hook (build-rom.py)
LOWER_VEC:
        jp      LOWER_LOOP         ; $3006: function $88 from the $2213 dispatch patch

FDD_MAIN:
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
        db      7

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
        jp      STATUS_REPORT      ; A = status-1: F, Q, R ... as for tpi: commands

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
