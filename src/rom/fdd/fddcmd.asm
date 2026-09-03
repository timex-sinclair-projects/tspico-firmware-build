;******************************************************************************
;  fddcmd.asm — native disk-command extension for the TS-PICO EXROM
;
;  Assembled at $3000, spliced into the EXROM (file $7000) by build-rom.py.
;  See docs/FDD_COMMANDS_DESIGN.md.
;
;  Entered from the HOME-ROM disk-token hook ($25D6, applied by the build
;  manifest) via the returning HOME->EXROM thunk at HOME $03FC: HL held the
;  entry ($3000), so control lands here with the EXROM paged in and returns to
;  the BASIC interpreter when we RET. Only the RUNTIME pass reaches here (the
;  hook makes the syntax pass accept and return); B carries the BASIC token
;  that was dispatched.
;******************************************************************************

        DEVICE  NOSLOT64K

FDD_BASE        EQU $3000          ; keep in sync with FDD_ORG in build-rom.py

; --- HOME/EXROM entry points we call (see rom-analysis/) ----------------------
TADDR           EQU $5C74          ; T-ADDR: low byte becomes the TPI TADDR field
STKEND          EQU $5C65          ; calculator stack end pointer
SAVE_EXEC_TPI   EQU $1A73          ; EXROM: parse TPI: prefix off the calc stack
                                   ; and send the 'B' command block (+ display)

; --- BASIC tokens -------------------------------------------------------------
TOK_CAT         EQU $CF

        ORG     FDD_BASE

;------------------------------------------------------------------------------
; FDD_DISPATCH — runtime entry. B = dispatched token.
;------------------------------------------------------------------------------
FDD_DISPATCH:
        ld      a,b
        cp      TOK_CAT
        jr      z,FDD_CAT
        ; FORMAT/MOVE/ERASE not yet implemented — return cleanly (no-op) so an
        ; unhandled disk keyword does nothing rather than erroring or hanging.
        ret

        db      "FDDCMD",0         ; signature — build.py verifies this
FDD_VERSION:
        db      1

;------------------------------------------------------------------------------
; FDD_CAT — "CAT" -> issue the equivalent of SAVE "tpi:dir".
;
; Reuses the shipping TPI command path: push a string descriptor for "tpi:dir"
; onto the calculator stack, set T-ADDR to the SAVE op (0), then jump to
; SAVE_EXEC_TPI, which reads the descriptor, recognises the "tpi:" prefix, sends
; the 'B' command block, and handles the Pico's directory response (scrolling
; display) exactly as SAVE "tpi:dir" does. It returns to BASIC on its own, so we
; JP (not CALL).
;
; Verified in ZEsarUX: runtime CAT reaches here, the "tpi:dir" prefix parses as
; a TPI command (device flag bit7 set), and the 10-byte 'B' pre-header goes out
; port $0E. A live directory listing needs a responding Pico (the issue-#35
; bridge or real hardware); the bare emulator has nothing to answer.
;------------------------------------------------------------------------------
FDD_CAT:
        ; T-ADDR := 0  (TADDR field = SAVE)
        xor     a
        ld      (TADDR),a
        ld      (TADDR+1),a

        ; push a 5-byte string descriptor {00, addr, len} onto the calc stack:
        ;   the sent string lives in EXROM (read during the send, EXROM paged).
        ld      hl,(STKEND)
        ld      (hl),0             ; string marker
        inc     hl
        ld      de,CAT_CMD
        ld      (hl),e             ; addr low
        inc     hl
        ld      (hl),d             ; addr high
        inc     hl
        ld      (hl),CAT_CMD_LEN   ; len low
        inc     hl
        ld      (hl),0             ; len high
        inc     hl
        ld      (STKEND),hl        ; STKEND += 5

        jp      SAVE_EXEC_TPI

CAT_CMD:
        db      "tpi:dir"
CAT_CMD_LEN     EQU $-CAT_CMD

FDD_END:
        SAVEBIN "fddcmd.bin", FDD_BASE, FDD_END-FDD_BASE
