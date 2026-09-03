;******************************************************************************
;  fddcmd.asm — native disk-command extension for the TS-PICO EXROM
;
;  Assembled at $3000, spliced into the EXROM (file $7000) by build-rom.py.
;  See docs/FDD_COMMANDS_DESIGN.md.
;
;  Entered from the HOME-ROM disk-token hook ($25D6, applied by the build
;  manifest) via the returning HOME->EXROM thunk at HOME $03FC: HL held the
;  entry ($3000), so control lands in FDD_DISPATCH with the EXROM paged and
;  returns to the BASIC interpreter when we RET. B carries the BASIC token.
;
;  BASIC calls a command's routine TWICE — once to syntax-check the statement
;  (FLAGS bit 7 clear) and once to execute it (bit 7 set). Both reach here. The
;  syntax pass must consume the argument so the statement is accepted (otherwise
;  a trailing "name" is "nonsense"); the runtime pass builds and sends.
;
;  Each handler builds a "tpi:<verb> <arg>" command string in the calculator
;  stack workspace, pushes a string descriptor for it, and jumps to the shipping
;  TPI send entry ($1A73) — reusing the whole SAVE "tpi:..." machinery (send +
;  scrolling display of the Pico's response). A live response needs a Pico (the
;  issue-#35 bridge or hardware); the bare emulator has nothing to answer.
;******************************************************************************

        DEVICE  NOSLOT64K

FDD_BASE        EQU $3000          ; keep in sync with FDD_ORG in build-rom.py

; --- HOME/EXROM sysvars & entry points (see rom-analysis/) --------------------
CH_ADD          EQU $5C5D          ; address of the next char in the BASIC line
FLAGS           EQU $5C3B          ; bit 7 set = runtime, clear = syntax check
TADDR           EQU $5C74          ; T-ADDR: low byte becomes the TPI TADDR field
STKEND          EQU $5C65          ; calculator stack end pointer (our scratch top)
SAVE_EXEC_TPI   EQU $1A73          ; EXROM: parse "tpi:" off the calc stack, send

CR              EQU $0D            ; BASIC end-of-line
DQUOTE          EQU $22            ; string-literal quote

; --- BASIC tokens -------------------------------------------------------------
TOK_CAT         EQU $CF
TOK_FORMAT      EQU $D0
TOK_MOVE        EQU $D1
TOK_ERASE       EQU $D2

        ORG     FDD_BASE

;------------------------------------------------------------------------------
; FDD_DISPATCH — entry for both the syntax-check and runtime pass. B = token.
;------------------------------------------------------------------------------
FDD_DISPATCH:
        ld      a,(FLAGS)          ; read FLAGS directly (IY is clobbered by the
        bit     7,a                ; bank call). bit 7: set = runtime, clear = syntax
        jr      nz,FDD_RUN
        ; --- syntax pass: consume the (optional) quoted argument, accept ---
        ld      de,(STKEND)        ; throwaway sink above the calc stack
        call    COPY_ARG           ; advances CH_ADD past the argument
        ret

FDD_RUN:
        ld      a,b
        cp      TOK_CAT
        jr      z,FDD_CAT
        cp      TOK_FORMAT
        jr      z,FDD_FORMAT
        cp      TOK_MOVE
        jr      z,FDD_MOVE
        cp      TOK_ERASE
        jr      z,FDD_ERASE
        ret                        ; unknown token — no-op

        db      "FDDCMD",0         ; signature — build.py verifies this
FDD_VERSION:
        db      3

;------------------------------------------------------------------------------
; Command handlers.  HL -> NUL-terminated "tpi:<verb> " prefix.
;   CAT takes no argument (fixed "tpi:dir").
;   FORMAT/MOVE/ERASE append the quoted argument from the BASIC line.
;------------------------------------------------------------------------------
FDD_CAT:
        ld      hl,CMD_DIR
        jr      FDD_SEND           ; no argument
FDD_FORMAT:
        ld      hl,CMD_NEWTAP
        jr      FDD_SEND_ARG
FDD_MOVE:
        ld      hl,CMD_CD
        jr      FDD_SEND_ARG
FDD_ERASE:
        ld      hl,CMD_RM
        jr      FDD_SEND_ARG

;------------------------------------------------------------------------------
; FDD_SEND_ARG — build "<prefix><quoted arg from the line>" and send.
; FDD_SEND     — build "<prefix>" alone (no argument) and send.
;
; The command string is assembled in the calculator-stack workspace starting at
; STKEND; a 5-byte string descriptor is pushed above it and STKEND advanced, so
; SAVE_EXEC_TPI reads it exactly like a SAVE "tpi:..." filename.
;------------------------------------------------------------------------------
FDD_SEND_ARG:
        ld      de,(STKEND)        ; DE = build ptr = start of command string
        push    de                 ; [start]
        call    COPY_CSTR          ; copy the NUL-terminated prefix (HL) to (DE)
        call    COPY_ARG           ; append the quoted line argument
        jr      FDD_SEND_TAIL
FDD_SEND:
        ld      de,(STKEND)
        push    de                 ; [start]
        call    COPY_CSTR          ; prefix only

FDD_SEND_TAIL:
        ; DE -> end of the command string; [start] on stack. Build descriptor.
        pop     hl                 ; HL = start
        ld      a,e
        sub     l
        ld      c,a
        ld      a,d
        sbc     a,h
        ld      b,a                ; BC = length = end - start
        ex      de,hl              ; HL = end (descriptor position), DE = start
        ld      (hl),0             ; marker
        inc     hl
        ld      (hl),e             ; addr low
        inc     hl
        ld      (hl),d             ; addr high
        inc     hl
        ld      (hl),c             ; len low
        inc     hl
        ld      (hl),b             ; len high
        inc     hl
        ld      (STKEND),hl        ; STKEND past the descriptor

        xor     a                  ; T-ADDR := 0 (TADDR field = SAVE)
        ld      (TADDR),a
        ld      (TADDR+1),a
        jp      SAVE_EXEC_TPI

;------------------------------------------------------------------------------
; COPY_CSTR — copy the NUL-terminated string at (HL) to (DE). Stops on NUL
; (not copied). Advances HL past the NUL and DE past the last copied byte.
;------------------------------------------------------------------------------
COPY_CSTR:
        ld      a,(hl)
        inc     hl
        and     a
        ret     z
        ld      (de),a
        inc     de
        jr      COPY_CSTR

;------------------------------------------------------------------------------
; COPY_ARG — copy a "..." literal argument from the BASIC line into (DE), and
; advance CH_ADD past it so the statement parses/continues cleanly. Scans from
; CH_ADD for the opening quote (skipping the token/spaces); if there is no quote
; before end-of-statement, copies nothing. On return DE is past the copied
; characters and (CH_ADD) points just after the argument.
;
; Runs on both passes: at runtime DE is the real command buffer; on the syntax
; pass DE is throwaway scratch above the calc stack and only the CH_ADD advance
; matters.
;------------------------------------------------------------------------------
COPY_ARG:
        ld      hl,(CH_ADD)
.find:  ld      a,(hl)
        cp      CR
        jr      z,.end             ; end of statement, no argument
        cp      ':'
        jr      z,.end
        inc     hl
        cp      DQUOTE
        jr      nz,.find
.copy:  ld      a,(hl)
        cp      DQUOTE
        jr      z,.close
        cp      CR
        jr      z,.end
        inc     hl
        ld      (de),a
        inc     de
        jr      .copy
.close: inc     hl                 ; step past the closing quote
.end:   ld      (CH_ADD),hl
        ret

;------------------------------------------------------------------------------
; TPI command prefixes (NUL-terminated). Verbs map to existing Pico commands.
;------------------------------------------------------------------------------
CMD_DIR:    db "tpi:dir",0
CMD_NEWTAP: db "tpi:newtap ",0
CMD_CD:     db "tpi:cd ",0
CMD_RM:     db "tpi:rm ",0

FDD_END:
        SAVEBIN "fddcmd.bin", FDD_BASE, FDD_END-FDD_BASE
