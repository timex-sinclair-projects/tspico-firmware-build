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
;  COPY reaches the same hook ($25E0); a bare COPY comes back with carry set
;  and the hook goes on to HOME's own COPY, the printer (FDD_ENTRY). LIST and
;  RESTORE come straight to $25D6, and T-ADDR says which; their other forms go
;  back to HOME the same way.
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
;    MOVE TO x          -> tpi:cd x              (§3; "-" is the previous dir)
;    MOVE TO ""         -> tpi:cd                (the list of directories to pick from)
;    MOVE a TO b        -> tpi:ren a|b           ('|' can't occur in a FAT name)
;    COPY a TO b        -> tpi:copy a|b
;    COPY               -> HOME's COPY: the screen to the printer
;    ERASE x            -> tpi:erase x
;    FORMAT x           -> tpi:format x
;    LIST x             -> tpi:list x            (a string; LIST, LIST n, LIST #n: HOME's)
;    RESTORE #n         -> back to the start of the file on #n (RESTORE [n]: HOME's)
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
BANK_SV         EQU $5DCF          ; pre-header byte 2 on ROM 2.2 and earlier (always FFh)
    IFDEF MEGABANK
ROM_ID          EQU $25            ; the Megabank test ROM (build-rom.py --megabank): 2.5
    ELSE
ROM_ID          EQU $24            ; ROM 2.4: a command pre-header's byte 2 (#227, #228),
    ENDIF
                                   ;   the version marker at HOME $0065; build-rom.py
                                   ;   patches $1BB5 to send the same
TSPICO_READ_DATA EQU $2298         ; EXROM: IN A,(0Eh) / AND A / RET -- no ready-wait
PRINT_A         EQU $05FA          ; EXROM: SCR_CT = FFh, then RST 10h through CALL_HOME
MODE_SV         EQU $5DDB          ; SESSION_SETUP clears bits 7-4 for a plain name
MODE_SET_OK     EQU $2105          ; EXROM: CALL S_MODE ($1862) with A, then "0 OK" --
                                   ;   where tpi:sdcard and tpi:picopt end
READ_STATUS_BYTE EQU $02B9          ; EXROM: the response's status byte -> AF ($01C3's first half)
OPEN_STREAM     EQU $0426          ; EXROM: open stream A ($04F1 opens $FE, the main screen)
LOOP_BODY       EQU $21E6          ; EXROM: function $86's loop after $01C3 (PUSH AF; print/key...)
STREAM_LOWER    EQU $FD            ; stream -3: K, the lower screen
CURCHL          EQU $5C51          ; the current channel's record
THUNK_HX        EQU $03FC          ; HOME: LD (5DCD),HL / LD HL,t / JP here = call EXROM t
H_COPY          EQU $0A02          ; HOME: COPY (EXX / LD HL,1630h / JP 3CE3h), the
                                   ;   printer; the $25D6 hook jumps there on carry
H_LIST          EQU $1545          ; HOME: LIST, class 05h: it parses its own #n and n
H_RESTORE       EQU $1E9D          ; HOME: RESTORE, with the line number class 03h stacked
H_USE_ZERO      EQU $1C51          ; HOME: USE-ZERO, 0 on the calculator stack at run time
T_LIST          EQU $19B0          ; T-ADDR in a LIST statement: its parameter list
                                   ;   (19AFh) + 1, where class 05h leaves it
T_RESTORE       EQU $19D1          ; T-ADDR in a RESTORE statement (list 19D0h + 1)

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
R_FLAGS         EQU 10             ; bit 0: a record file (OPEN # gave a length);
                                   ;   bit 1: sent at each CR too (speech "v:",
                                   ;   commands "x:"); bit 2: commands ("x:"),
                                   ;   what was read ahead goes at each write
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
TOK_INKEY       EQU $A6
TOK_FN          EQU $A8
TOK_SCREEN      EQU $AA
TOK_VALS        EQU $AE
TOK_STRS        EQU $C1
TOK_CHRS        EQU $C2
TOK_CODE        EQU $AF
TOK_LINE        EQU $CA
TOK_DATA        EQU $E4

MAX_ARG         EQU 64             ; longest argument (per string); longer is F
ROOM            EQU 2*MAX_ARG+32   ; workspace a command can need

CR              EQU $0D            ; BASIC end-of-line
SEP             EQU '|'            ; COPY's and MOVE's source/destination separator

; --- BASIC tokens -------------------------------------------------------------
TOK_TO          EQU $CC
TOK_CAT         EQU $CF
TOK_FORMAT      EQU $D0
TOK_MOVE        EQU $D1
TOK_ERASE       EQU $D2
TOK_COPY        EQU $FF

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
TAPE_VEC:
        jp      TAPE_MODE          ; $301E: SAVE "tpi:tape" from $20BE (build-rom.py)

;------------------------------------------------------------------------------
; TAPE_MODE -- SAVE "tpi:tape": LOAD and SAVE back to the cassette (TPMODE bit
; 1 clear), the printer switch (bit 0) left as it is. ROM 2.0 did XOR A /
; S_MODE ($1861) here, clearing the printer switch too, and tpi:sdcard sets
; only bit 1: so tpi:picopt, tpi:tape, tpi:sdcard quietly sent printing back
; to the 2068 (#176). $20BE jumps here once the name and its length have
; matched and bits 7-6 are cleared in MODE_SV; A was used for the length test.
;------------------------------------------------------------------------------
TAPE_MODE:
        ld      a,(MODE_SV)
        res     1,a                ; cassette; bit 0 (the printer) untouched
        jp      MODE_SET_OK

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
    IFDEF MEGABANK
        call    BEEP_LT            ; POP HL, and Z for 'F' or 'R' (same size)
    ELSE
        pop     hl
        cp      'F'
    ENDIF
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
G_MAIN: ld      hl,FDD_ENTRY
        jr      GUARDED
    IFDEF MEGABANK
G_OUT:  ld      hl,MB_OUT          ; 'R' records too (rchan.asm), by the letter
        jr      GUARDED
G_IN:   ld      hl,MB_IN
        jr      GUARDED
    ELSE
G_OUT:  ld      hl,CH_OUT
        jr      GUARDED
G_IN:   ld      hl,CH_IN
        jr      GUARDED
    ENDIF
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
.bs:    ex      (sp),hl            ; [the bank stack before the thunk]
        push    hl                 ;   (GUARD0, rchan.asm, joins here)
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

        db      "FDDCMD",0         ; signature (nothing checks it; build-rom.py checks FDD_DISPATCH is at $3000)
FDD_VERSION:
        db      9

;------------------------------------------------------------------------------
; FDD_CAT -- CAT [string]; CAT #n[;string] goes to CAT_HASH (#404)
;------------------------------------------------------------------------------
FDD_CAT:
        call    CAT_HASH           ; AT_END's answer, or the whole of CAT #n
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
; FDD_MOVE -- MOVE TO string          change directory ("-" = the previous one,
;                                     "" = the list to pick from)
;             MOVE string TO string   rename (IX = CMD_REN, from FDD_ENTRY)
; TWO_NAMES is the two-name form on its own: COPY comes in there with IX =
; CMD_COPY. IX survives the HOME calls (CALL_HOME pops the caller's IX).
;------------------------------------------------------------------------------
FDD_MOVE:
        call    SKIP_SPACES
        cp      TOK_TO
        jr      z,MOVE_TO
TWO_NAMES:
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
        push    ix
        pop     hl                 ; the prefix: tpi:ren or tpi:copy
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
MOVE_TO:
        call    NEXT_CHAR
        call    EXPT_STR_END
        ret     z
        call    POP_STR
        ld      a,b
        or      c
        ld      hl,CMD_CD_MENU
        jp      z,SEND_PREFIX      ; MOVE TO "" -> tpi:cd, the list of directories
        ld      hl,CMD_CD
        jp      SEND_ONE           ; MOVE TO "-" -> tpi:cd -, the previous one

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
    IFDEF MEGABANK
        call    MB_TPRE            ; tpi:rmask first for an "r:" command (same size)
        nop
        nop
    ELSE
        push    hl
        push    de
        ld      hl,(FRAMES)
    ENDIF
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
    IFDEF MEGABANK
        call    FR_TEST            ; "f:" or, on the Megabank ROM, "r:" (same size:
        jr      nz,.stock          ;   nothing after this moves)
        nop
    ELSE
        and     $DF
        cp      'F'
        jr      nz,.stock
    ENDIF
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
    IFDEF MEGABANK
        call    SET_MODE           ; and TPMODE bit 5 for an "r:" name
    ELSE
        ld      (MODE_SV),a
    ENDIF
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
; pre-header 'B', 0 (a SAVE "tpi:" command), ROM_ID, PMR1 (operation, token),
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
        ld      a,ROM_ID           ; byte 2: which ROM this is (#227); was (BANK_SV), FFh
        nop                        ;   (keeps every later address where it was)
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
        call    PRELOAD            ; the preloaded status: 0 is J (#179)
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
    IFDEF MEGABANK
        call    OPEN_TXT           ; HL = "tpi:fopen " or "tpi:ropen "
    ELSE
        ld      hl,FOPEN_TXT
    ENDIF
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
; Exactly $86's handler with a different stream: $01C3 is READ_STATUS_BYTE then
; "open stream $FE"; this opens $FD instead and joins $86's loop, which prints
; through the current channel and leaves via its own POP AF / RET.
; The Pico only sends $88 to a ROM it knows has it (tpi:fopen comes only from
; this module).
;------------------------------------------------------------------------------
LOWER_LOOP:
        call    READ_STATUS_BYTE
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
    IFDEF MEGABANK
        call    RCH_KIND           ; "r:" is answered there; else SPEC_KIND
    ELSE
        call    SPEC_KIND          ; "d:", "v:", "x:", or "f:" and a character more
    ENDIF
        jp      nz,STRMS_NC
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
        call    DV_TEST
        jr      z,.keep            ; "d:...", "v:" and "x:" go as they are
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
        call    PUSH_LETTER        ; [letter]: the spec is about to go
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
        pop     af                 ; the spec's letter
        pop     bc                 ; the record length
        call    REC_FLAGS
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
    IFDEF MEGABANK
        call    RCH_CLTEST         ; an 'R' record is closed there (same size)
        nop
        nop
    ELSE
        ld      a,(ix+R_LETTER)
        cp      'F'
    ENDIF
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
        call    z,IN_DROP          ;   ahead is no longer next; on "x:" any
        bit     2,(ix+R_FLAGS)     ;   write, a new command, whose answer
        call    nz,IN_DROP         ;   replaces the last (#404). 12 bytes, as
.put:   ld      a,(ix+R_OUTN)      ;   before: nothing up to PS_READ moves
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
        jr      nz,.done           ;   on the PRINT that made it; speech
        ld      a,(ix+R_FLAGS)     ;   too, so a line is said when it is
        and     3                  ;   printed
        jr      z,.done
    IFDEF MEGABANK
.send:  call    G_FLUSH            ; under the error trap (rchan.asm, the fast entry)
    ELSE
.send:  call    CH_FLUSH
    ENDIF
.done:  pop     ix
        ret

CH_IN:
        ld      iy,IY_SYSVARS
        push    ix
        ld      ix,(CURCHL)
.again: ld      a,(ix+R_INP)
        cp      (ix+R_INN)
        jr      c,.have
    IFDEF MEGABANK
        call    G_FLUSH            ; the same, under the error trap (rchan.asm)
        call    G_FETCH
    ELSE
        call    CH_FLUSH           ; what was printed first (INPUT #4;TAB n: the seek)
        call    CH_FETCH           ; NZ: end of file
    ENDIF
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
        ld      a,ROM_ID           ; byte 2: which ROM this is (#227); was (BANK_SV), FFh
        nop                        ;   (keeps every later address where it was)
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
        call    PRELOAD            ; the preloaded status: 0 is J (#179)
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
CMD_REN:     db "tpi:ren ",0
CMD_COPY:    db "tpi:copy ",0
CMD_ERASE:   db "tpi:erase ",0
CMD_FORMAT:  db "tpi:format ",0
CMD_CHWR:    db "tpi:chwr ",0
CMD_CHRD:    db "tpi:chrd",0
CMD_CHCLOSE: db "tpi:chclose",0
CMD_CHOPEN:  db "tpi:chopen ",0
MODE_R:      db "r"

;------------------------------------------------------------------------------
; PRELOAD -- SEND_FOPEN's and CH_SEND's read of the preloaded status (#179).
; 0 means no Pico, or a link out of step: Report J at once, as the ROM's own
; exchanges give it (1A35h), instead of carrying on into a timeout. Anything
; else goes on as before. Not the ROM's whole rule ("not 1: the Pico's
; refusal"): the firmware refuses nothing here, and the one other value it
; stages is a refused header LOAD's error, for the LOAD's retry, which a
; channel command in the next 2 s (an ON ERR handler doing PRINT #) would
; otherwise report as its own. At the end of the module so nothing moves.
;------------------------------------------------------------------------------
PRELOAD:
        call    BIOS_RX_A          ; IN A,(0Eh) / AND A: Z if 0
        ret     nz
        jp      WF_FAIL            ; A = 0: J (Invalid I/O device)

; Free bytes: PS_READ stays at 377Fh, where HOME's patch jumps (build-rom.py's
; FIXED_SYMS). Code before it that shrinks leaves room here (#375: 14 bytes).
        BLOCK   $377F-$,$FF

;------------------------------------------------------------------------------
; PS_READ -- PRINT_STRING_FROM_PICO for ROM 2.3 (#228). EXROM $045F (functions
; $81, $82, $86 and, through $86's loop, $88) jumps here. Prints bytes from the
; Pico until a terminator, as the v1.1 routine at $045F did, with two changes:
;
;   - the parameter bytes after a control code (one after INK..OVER, $10-$15;
;     two after AT and TAB, $16-$17) go straight to RST 10h, so INK 0, PAPER 3,
;     AT r,0 and the rest can be sent: v1.1 tested every byte, and a 00h or
;     03h parameter ended the text;
;   - only 00h and 03h end the text. v1.1 also ended it on any byte of 80h or
;     more, so block graphics, UDGs and keyword tokens could not be sent.
;
; Reads with no ready-wait, like v1.1: the Pico keeps ahead (PROTOCOL.md 5.4).
; Exits as v1.1 did: 00h -> the caller's AF back, carry clear; 03h -> carry set
; (v1.1's $21FA: POP AF / SCF / RET), which ends an $86 loop. C carries the
; parameter count across PRINT_A, which may change any register.
;------------------------------------------------------------------------------
PS_READ:
        push    af                 ; the caller's status
.next:  call    TSPICO_READ_DATA
        jr      z,.end             ; 00h: the end of the text or the page
        cp      $03
        jr      z,.loopend         ; 03h: the end of an $86/$88 loop
        cp      $10
        jr      c,.print
        cp      $18
        jr      nc,.print          ; $18 and up, $80-$FF included: print it
        ld      c,1                ; INK, PAPER, FLASH, BRIGHT, INVERSE, OVER
        cp      $16
        jr      c,.code
        inc     c                  ; AT, TAB: two
.code:  push    bc
        call    PRINT_A            ; the code: RST 10h now waits for its parameters
        pop     bc
.param: call    TSPICO_READ_DATA   ; a parameter: never a terminator
        push    bc
        call    PRINT_A
        pop     bc
        dec     c
        jr      nz,.param
        jr      .next
.print: call    PRINT_A
        jr      .next
.loopend:
        pop     af
        scf
        ret
.end:   pop     af
        and     a
        ret

;------------------------------------------------------------------------------
; FDD_ENTRY -- G_MAIN's routine: every disk keyword and COPY, on both passes.
; COPY's parameter list (HOME 19D7h) is class 05h with routine 25E0h, LD B,FFh
; into the $25D6 hook, so the module parses COPY's arguments itself. The hook
; is CALL 03FCh / EI / RET NC / JP (HL): this returns NC, except a bare COPY at
; run time, which returns C with HL = H_COPY, and the hook goes on to HOME's
; COPY with the stack and T-ADDR as class 00h left them (1781h tells COPY from
; LPRINT by T-ADDR's low byte, D8h). The stock COPY ends with a no-return jump
; to HOME (17B3h), so the module can't call it. IX carries the two-name prefix
; into TWO_NAMES and is put back for the caller.
;------------------------------------------------------------------------------
FDD_ENTRY:
        push    ix
        call    .run
        pop     ix                 ; the flags pass through
        ret
.run:   ld      hl,(TADDR)         ; LIST and RESTORE come straight to $25D6
        ld      a,h                ;   (B is not a token then): their
        cp      high T_LIST        ;   parameter lists say which
        jr      nz,.tok
        ld      a,l
        cp      low T_LIST
        jr      z,FDD_LIST
        cp      low T_RESTORE
        jp      z,FDD_RESTORE
.tok:   ld      ix,CMD_REN         ; MOVE a TO b: rename
        ld      a,b
        cp      TOK_COPY
        jr      z,FDD_COPY
        call    FDD_MAIN
        and     a                  ; NC: the hook returns
        ret

;------------------------------------------------------------------------------
; FDD_COPY -- COPY                    the screen to the printer (HOME's COPY)
;             COPY string TO string   copy a file
;------------------------------------------------------------------------------
FDD_COPY:
        ld      iy,IY_SYSVARS
        ei                         ; as FDD_MAIN
        call    AT_END
        jr      z,.bare
        ld      ix,CMD_COPY
        call    TWO_NAMES
        and     a                  ; NC: the hook returns
        ret
.bare:  call    RUNTIME
        ret     z                  ; syntax pass: accepted (NC from RUNTIME's AND)
        ld      hl,H_COPY          ; run time: C, and the hook jumps to HOME's COPY
        scf
        ret

;------------------------------------------------------------------------------
; FDD_LIST -- LIST string            show a file (tpi:list)
;             LIST, LIST n, LIST #n  HOME's LIST (C, HL = H_LIST, on both passes:
;                                    it does its own syntax check)
; LIST's parameter list (HOME 19AFh) is class 05h with routine 25D6h. Which
; form it is goes by how the expression starts (STR_NEXT): the module can't
; scan it to find out, because a syntax-pass scan at run time inserts a
; second hidden number after each number in the line, and a run-time scan
; evaluates it twice.
;------------------------------------------------------------------------------
FDD_LIST:
        ld      iy,IY_SYSVARS
        ei                         ; as FDD_MAIN
        call    AT_END
        jr      z,.home            ; LIST
        cp      '#'
        jr      z,.home            ; LIST #n
        call    STR_NEXT
        jr      nz,.home           ; LIST n
        ld      hl,CMD_LIST
        call    FDD_ONE_ARG
        and     a                  ; NC: the hook returns
        ret
.home:  ld      hl,H_LIST
        scf
        ret

;------------------------------------------------------------------------------
; FDD_RESTORE -- RESTORE [n]   HOME's RESTORE: the module does class 03h's
;                              part (the number, or 0) and hands over at run
;                              time (C, HL = H_RESTORE)
;                RESTORE #n    the file open on stream n goes back to its
;                              start: what was printed to it is sent, what
;                              was read ahead is dropped, and TAB 1 goes to
;                              the Pico (Channels._seek: byte 0, a record
;                              file's open record closed). Report O if #n is
;                              not an OPEN # file.
; RESTORE's parameter list (HOME 19D0h) was class 03h, routine 1E9Dh; it is
; class 05h with routine 25D6h.
;------------------------------------------------------------------------------
FDD_RESTORE:
        ld      iy,IY_SYSVARS
        ei
        call    AT_END
        jr      z,.zero
        cp      '#'
        jr      z,.strm
        call    HC_EXPT_1NUM       ; RESTORE n
        call    AT_END
        jp      nz,NONSENSE
        call    RUNTIME
        ret     z                  ; syntax pass: accepted (NC)
        jr      .home
.zero:  call    RUNTIME
        ret     z
        call    HC_USE_ZERO        ; RESTORE: line 0
.home:  ld      hl,H_RESTORE
        scf
        ret
.strm:  call    NEXT_CHAR
        call    HC_EXPT_1NUM       ; the stream
        call    AT_END
        jp      nz,NONSENSE
        call    RUNTIME
        ret     z
        call    STRM_REC           ; IX = the record, what was printed sent
        xor     a
        ld      (ix+R_INN),a       ; what was read ahead goes
        ld      (ix+R_INP),a
        ld      (ix+R_OUTBUF),23   ; TAB 1: the file's first byte
        ld      (ix+R_OUTBUF+1),1
        ld      (ix+R_OUTBUF+2),a
        ld      (ix+R_OUTN),3
        call    CH_FLUSH
        and     a
        ret

; STRM_REC -- the number on the calculator stack is a stream open to an OPEN #
; channel (an 'F' record): IX = its record, and what was printed to it is sent
; first (CH_FLUSH). Report O if it isn't: over 15, not open, a system stream,
; or another channel. RESTORE #n and CAT #n.
STRM_REC:
        call    HC_FIND_INT2       ; BC
        ld      a,b
        and     a
        jr      nz,.bad
        ld      a,c
        cp      16
        jr      nc,.bad
        add     a,a
        add     a,low (STRMS+6)    ; stream n's STRMS entry
        ld      l,a
        ld      h,high STRMS
        ld      e,(hl)
        inc     hl
        ld      d,(hl)
        ld      a,d
        or      e
        jr      z,.bad             ; not open
        bit     7,d
        jr      nz,.bad            ; SYSCON
        ld      hl,(CHANS)
        add     hl,de
        dec     hl
        push    hl
        pop     ix                 ; the record
        ld      a,(ix+R_LETTER)
        cp      'F'
        jp      z,CH_FLUSH         ; what was printed first
.bad:   rst     8
        db      $17                ; O Invalid stream

; STR_NEXT -- Z if the expression at CH_ADD starts as a string does: a quote,
; a string variable (a letter, then '$'), FN a$, STR$, CHR$, INKEY$, SCREEN$
; or VAL$. It only looks; CH_ADD stays on the expression. Anything else
; (a parenthesis among them) counts as a number.
STR_NEXT:
        call    SKIP_SPACES        ; A = the character, HL = CH_ADD
        cp      '"'
        ret     z
        cp      TOK_INKEY
        ret     z
        cp      TOK_SCREEN
        ret     z
        cp      TOK_VALS
        ret     z
        cp      TOK_STRS
        ret     z
        cp      TOK_CHRS
        ret     z
        cp      TOK_FN
        call    z,.next            ; FN a$(...): the letter
        or      $20
        cp      'a'
        jr      c,.no
        cp      'z'+1
        jr      nc,.no
        call    .next              ; then '$', perhaps after spaces
        cp      '$'
        ret
.no:    or      1                  ; NZ
        ret
.next:  inc     hl
        ld      a,(hl)
        cp      ' '
        jr      z,.next
        ret

HC_USE_ZERO:
        push    ix
        exx
        ld      hl,H_USE_ZERO
        jp      CALL_HOME

CMD_LIST:    db "tpi:list ",0
CMD_CD_MENU: db "tpi:cd",0

;------------------------------------------------------------------------------
; OPEN #n,"v:" -- the v3 card's speech (#375). CH_OPEN_HOOK takes it as it takes
; "d:": the spec goes to the Pico whole (tpi:chopen r v:), which speaks what is
; printed to the stream. The record is an 'F' record like any other (CLOSE #,
; the quiet key click and the rest need no change); R_FLAGS bit 1 makes CH_OUT
; send at each CR, so PRINT #4;"HELLO" is said at once, not when 64 bytes have
; gathered or at CLOSE #. Here, past PS_READ, so nothing before it moves.
;
; OPEN #n,"x:" -- commands (#404), the same way: the spec goes whole, and
; R_FLAGS bit 1 sends each line at its CR, so PRINT #4;"dir" reaches the Pico
; as a command and the next INPUT #4 reads its answer. Bit 2 makes CH_OUT drop
; what CH_IN read ahead from the last answer whenever the stream is written.
;------------------------------------------------------------------------------

; SPEC_KIND -- DE = the spec ("x:..."), C = its length: Z if it is ours ("d:",
; "v:", "x:", or "f:" with at least one character more), else NZ. A is lost.
SPEC_KIND:
        call    DV_TEST
        ret     z
        cp      'F'
        ret     nz
        ld      a,c
        cp      3                  ; C: "f:" alone
        sbc     a,a                ; FFh if so, else 0
        and     a                  ; Z: ours
        ret

; DV_TEST -- Z if the spec at DE starts with d, v or x (any case): it goes to
; the Pico whole. A = the letter in upper case.
DV_TEST:
        ld      a,(de)
        and     $DF
        cp      'D'
        ret     z
        cp      'V'
        ret     z
        cp      'X'
        ret

; PUSH_LETTER -- push the spec's first letter (upper case) in AF under the
; return address: CH_OPEN_HOOK drops the spec before it builds the record.
; HL is lost.
PUSH_LETTER:
        call    PEEK_NAME
        ld      a,(de)
        and     $DF
        pop     hl                 ; the return address
        push    af
        jp      (hl)

; REC_FLAGS -- the new record's R_FLAGS (IX = the record, A = the spec's
; letter, BC = the record length): bit 0 for a record file, bit 1 (send at
; each CR) for speech and commands, bit 2 for commands. HL is kept.
REC_FLAGS:
        cp      'X'
        jr      nz,.v
        set     2,(ix+R_FLAGS)
        jr      .cr
.v:     cp      'V'
        jr      nz,.file
.cr:    set     1,(ix+R_FLAGS)
.file:  ld      a,b
        or      c
        ret     z
        set     0,(ix+R_FLAGS)
        ret

; IN_DROP -- forget what CH_IN read ahead (IX = the record): CH_OUT, for a TAB
; (a seek) and for any write to an "x:" stream (a new command).
IN_DROP:
        ld      (ix+R_INN),0
        ld      (ix+R_INP),0
        ret

;------------------------------------------------------------------------------
; CAT_HASH -- FDD_CAT's first call, in AT_END's place (#404). For CAT and
; CAT "x" it is AT_END: Z at the end of the statement, NZ and A = the
; character. For CAT #n and CAT #n;"x" (or ,"x") it does the whole statement
; and returns from FDD_CAT itself, NC as FDD_CAT does: the listing goes into
; the file open on stream n. The Pico writes it (tpi:chcat, PMR1 = the
; stream, PMR2 = 1 when a string came: "" is the mounted TAP); the ROM can't
; print a reply into a Pico-backed stream mid-transaction. What was printed
; to the stream is sent first and what was read ahead dropped, so the
; listing lands where the file's position is.
;------------------------------------------------------------------------------
CAT_HASH:
        call    AT_END
        ret     z
        cp      '#'
        ret     nz                 ; CAT "x"
        pop     hl                 ; FDD_CAT's: this ends the statement
        call    NEXT_CHAR
        call    HC_EXPT_1NUM       ; the stream
        call    AT_END
        jr      z,.bare
        cp      ';'
        jr      z,.str
        cp      ','
        jp      nz,NONSENSE
.str:   call    NEXT_CHAR
        call    EXPT_STR_END
        ret     z                  ; syntax pass: accepted (NC)
        call    POP_STR            ; DE = text, BC = length
        ld      a,1                ; PMR2: a string came
        jr      .run
.bare:  call    RUNTIME
        ret     z
        ld      bc,0
        xor     a                  ; PMR2: none
.run:   push    af                 ; [PMR2]
        push    de                 ; [text]
        push    bc                 ; [length]
        call    STRM_REC           ; IX = the record (Report O), flushed
        call    IN_DROP
        ld      hl,CMD_CHCAT
        call    BUILD_START        ; HL = start, DE = next
        pop     bc
        ex      (sp),hl            ; HL = text; [start]
        ld      a,b
        or      c
        jr      z,.none
        ldir
.none:  xor     a
        ld      (de),a
        pop     hl                 ; the command
        pop     af
        ld      c,a                ; PMR2
        ld      b,0                ; no payload
        ld      a,(ix+R_STRM)
        call    CH_SEND
        call    CH_STATUS          ; Q, F, J raise their reports
        and     a
        ret

CMD_CHCAT:   db "tpi:chcat ",0

    IFDEF MEGABANK
;==============================================================================
; THE TS-2068 MEGABANK -- the Megabank test ROM (build-rom.py --megabank),
; phase 4 of the Megabank's specification (TS-2068-Megabank, docs/spec.md):
; the boot reset, SAVE/LOAD/VERIFY/MERGE "r:name" and the mover.
;
; The board is 4 MB of battery-backed RAM: up to 512 pages of 8K, numbered
; from 0, which make 64 banks of 64K (BASE, BASE+1 ...). Two ports: OUT (FDh)
; selects a register, IN/OUT (FCh) reads or writes it. OWN0-OWN7 name the bank
; that owns each 8K chunk of the 2068's memory (0 = none, and writing one sets
; that chunk's SUBn = n); SUB0-SUB7 say which 8K of the bank appears there.
; An owned chunk's reads and writes go to the board, which pulls /BE.
;
; The rule from the hardware (2026-11-18): /BE stops the 2068's own memory
; answering a read, but not HOME RAM taking a write. So a chunk is mapped
; OWNn first, then its bit in the HSR (port F4h), which sends the chunk to
; EXROM/DOCK and keeps the RAM underneath; and unmapped in the reverse order.
;
; Everything here is appended after the 2.4 module, so no 2.4 entry point
; moves; F_HOOK and SEND_FOPEN change in place, at the same size, under
; IFDEF MEGABANK. build-rom.py's FIXED_SYMS holds the addresses its patches
; jump to (MB_BOOT, R_SA, R_LD, FN_EXT).
;==============================================================================

MB_SEL          EQU $FD            ; OUT: select a board register
MB_DATA         EQU $FC            ; IN/OUT: the selected register
MB_OWN          EQU $00            ; OWN0-OWN7
MB_SUB          EQU $08            ; SUB0-SUB7
MB_WPROT        EQU $10            ; bit n: writes to chunk n dropped
MB_STATUS       EQU $11            ; bit 0 write-protect switch, bit 1 battery low
MB_ID           EQU $12            ; A5h
MB_IDCOMP       EQU $13            ; 5Ah
MB_BASE         EQU $14            ; the first bank: 1, 65, 129 or 193
MB_SIZE         EQU $15            ; banks fitted: 8, 16, 32 or 64
MB_VERSION      EQU $16
HSR             EQU $F4            ; the 2068's chunk select: bit n set = chunk n off HOME
SYSCON          EQU $5CBC          ; -> the SYSCON table (5EEAh)
SYSCON_END      EQU $2082          ; EXROM: DEC HL / LD (HL),80h, then HOME's CLEAR-PRB
SA_RET          EQU $00E5          ; EXROM: the tape routines' exit: border, BREAK, EI
PICO_SA         EQU $1879          ; EXROM: SA-BYTES's TPMODE bit-1 gate ($0068 went here)
PICO_LD         EQU $196D          ; EXROM: LD-BYTES's ($00FC went here)
R_BIT           EQU 5              ; TPMODE bit 5: this statement's blocks go to "r:"

;------------------------------------------------------------------------------
; MB_BOOT -- the boot's bank search, replaced. EXROM $0A3E (patched to JP here)
; is reached by the fall-through from $09F4 (the DOCK header read, on the
; normal path) and by CALL $0A3E at $1CA8 (D held at power-on). Timex's search
; probed for banks through the memory-mapped, IOA5-gated registers; this board
; answers ports only, so the search is dropped; MB_DETECT, at the end, reads
; the board's ID, BASE and SIZE instead and sets the bank count (MAXBNK,
; 5CBEh, and 6315h) that the rewritten bank code (bankapi.asm) works from.
;
; Every OWNn and WPROT is written 0 although the board clears them on /RESET:
; PicoVideo can't see /RESET, and the v3 card keeps its shadows through a plain
; reset, so these writes put every device that watches FDh/FCh back in step.
; With no board fitted they reach nobody, which is harmless. Nothing is read
; here and nothing is told to the TS-Pico: the firmware asks the mover (op 7)
; when it needs the board's state (PROTOCOL.md 6.3).
;
; Ends as the old code did: HL = SYSCON + 0Dh, then (through MB_DETECT) $2082, which
; writes SYSCON's 80h end marker after the LROS header and clears the printer
; buffer. The old code then called the renumbering at $0CFB: dropped.
;------------------------------------------------------------------------------
MB_BOOT:
        ld      e,0
        ld      a,MB_OWN+7
.own:   push    af
        call    MB_WR              ; OWNn = 0: no owner (and SUBn = n)
        pop     af
        dec     a
        jp      p,.own
        ld      a,MB_WPROT
        call    MB_WR
        ld      hl,(SYSCON)
        ld      de,$000D
        add     hl,de
        jp      MB_DETECT          ; and on to SYSCON_END: the boot

;------------------------------------------------------------------------------
; The "r:" prefix, through F_HOOK. SAVE/LOAD/VERIFY/MERGE "r:name" goes
; exactly as "f:path" does -- the Pico gets the name in a command, the name on
; the calculator stack is shortened, and the stock SAVE-ETC body runs -- with
; two differences: the command is tpi:ropen, not tpi:fopen, and TPMODE bit 5
; is set, so the body's tape blocks go to R_SA / R_LD instead of the Pico's
; block transfer. The RAM disk's file system is the firmware's (spec: "The RAM
; disk"); the ROM only moves the bytes, when the firmware says so.
;------------------------------------------------------------------------------

; FR_TEST -- F_HOOK's prefix letter (A, as typed): Z for F or R.
FR_TEST:
        and     $DF
        cp      'F'
        ret     z
        cp      'R'
        ret

; SET_MODE -- F_HOOK's .go: TPMODE := A (TPMODE AND 0Fh, the prefix flags
; cleared), plus bit 5 if the name began "r:". The name is on the calculator
; stack, already shortened: a SAVE's moved past its two-character prefix, a
; LOAD's not moved (its length is 0).
SET_MODE:
        push    af
        call    PEEK_NAME          ; DE = the name
        ld      a,(TADDR)
        and     a
        jr      nz,.load
        dec     de
        dec     de                 ; SAVE: back to the prefix
.load:  ld      a,(de)
        and     $DF
        cp      'R'
        pop     bc                 ; B = TPMODE AND 0Fh
        ld      a,b
        jr      nz,.st
        set     R_BIT,a
.st:    jp      SET_MODE_R         ; and the mask, for an "r:" statement (rchan.asm)
        db      $FF                ; (R_SA stays at 39F5h)

; OPEN_TXT -- SEND_FOPEN's command word: HL = "tpi:fopen " or "tpi:ropen " by
; the name's first letter. BC and DE (D: the running XOR) are kept.
OPEN_TXT:
        push    de
        push    bc
        call    PEEK_NAME          ; DE = the name, not yet shortened
        ld      a,(de)
        pop     bc
        pop     de
        and     $DF
        ld      hl,FOPEN_TXT
        cp      'R'
        ret     nz
        ld      hl,ROPEN_TXT
        ret

ROPEN_TXT:   db "tpi:ropen "
        ASSERT  $-ROPEN_TXT == FOPEN_LEN

;------------------------------------------------------------------------------
; R_SA, R_LD -- the tape block routines' gates. EXROM $0068 (SA-BYTES) and
; $00FC (LD-BYTES) were JP $1879 / JP $196D, which test TPMODE bit 1 (the
; Pico or the cassette); build-rom.py points them here. With TPMODE bit 5 set
; (an "r:" statement) the block goes to the RAM disk; otherwise on as before.
;
; In: A = the flag (00h a header, FFh data), IX = the address, DE = the length;
; for R_LD, carry set = LOAD (and MERGE), clear = VERIFY.
;------------------------------------------------------------------------------
R_SA:   push    af
        ld      a,(MODE_SV)
        bit     R_BIT,a
        jr      nz,.r
        pop     af
        jp      PICO_SA
.r:     pop     af
        ld      c,0                ; PMR1: SAVE
        jr      R_BLOCK

R_LD:   push    af
        ld      a,(MODE_SV)
        bit     R_BIT,a
        jr      nz,.r
        pop     af
        jp      PICO_LD
.r:     pop     af
        ld      c,1                ; PMR1: LOAD
        jr      c,R_BLOCK
        inc     c                  ; 2: VERIFY

; R_BLOCK -- one block to or from the RAM disk: the command
;   tpi:rblk <hex: address lo, hi, length lo, hi>   PMR1 = C (0 SAVE, 1 LOAD,
;   2 VERIFY), PMR2 = the flag
; through CH_SEND, then C_END. The firmware answers with response function 89h
; (MOVER): its operations copy the block between the 2068's memory and the
; board, then its status ends the command. Leaves as the Pico's block routines
; do, through SA_RET with carry set: done. A failed status raises its report
; (VERIFY's mismatch is R, as on tape). TPMODE bit 5 is cleared after any
; block but a header (flag 00h: the data block follows) and on any failure.
R_BLOCK:
        ld      hl,SA_RET
        push    hl                 ; leave through the tape routines' exit
        di
        push    ix
        push    af                 ; [the flag]
        push    de
        push    ix                 ; the payload, at SP: address, length (LE)
        ld      b,a
        ld      hl,-R_OUTBUF
        add     hl,sp
        push    hl
        pop     ix                 ; IX + R_OUTBUF = the payload, where CH_SEND reads it
        ld      a,c                ; PMR1: the direction
        ld      c,b                ; PMR2: the flag
        ld      b,4                ; four payload bytes, sent as hex
        ld      hl,CMD_RBLK
        call    CH_SEND
        call    BIOS_C_END         ; the answer: 89h, the operations, the status
        pop     hl
        pop     hl                 ; the payload
        pop     hl                 ; H = the flag
        pop     ix
        jr      c,.fail
        ld      a,h
        and     a
        call    nz,R_OFF           ; data: the statement's last block
        scf                        ; C: the block is done
        ret                        ; -> SA_RET
.fail:  call    R_OFF
        jp      C_FAIL             ; A = status-1, 0Ch BREAK, 1Ch reset

; R_OFF -- clear TPMODE bit 5: the next blocks go where bit 1 says. AF kept.
R_OFF:  push    af
        ld      a,(MODE_SV)
        res     R_BIT,a
        ld      (MODE_SV),a
        pop     af
        ret

CMD_RBLK:    db "tpi:rblk ",0

;------------------------------------------------------------------------------
; FN_EXT -- the response functions past 87h. The dispatch chain's last test,
; $2213, was CP 87h / JP Z,$3006 / RET (function 88h, LOWER_LOOP); it is now
; JP FN_EXT. A = the code - 1.
;------------------------------------------------------------------------------
FN_EXT: cp      $87
        jp      z,LOWER_LOOP       ; 88h: $86's loop on the lower screen
        cp      $88
        jr      z,MOVER            ; 89h: the mover
        ret                        ; anything else: as before (Report D)

;------------------------------------------------------------------------------
; MOVER -- response function 89h: the firmware's hands on the board
; (PROTOCOL.md 6.3; the spec's "The mover's operations"). The TS-Pico can't
; reach the board, which answers only the Z80's bus cycles; so the firmware
; keeps the RAM disk's file system and tells the Z80, one operation at a time,
; what to copy. After 89h comes the first operation, with no wait; after each
; operation the Z80 replies and waits for READY before reading the next.
;
;   op  parameters (16-bit, LE)        does                         reply
;   1   addr, len, page, off           2068 memory -> the board     status
;   2   addr, len, page, off           the board -> 2068 memory     status
;   3   addr, len, page, off           compare them                 status: 1 same, 2 not
;   4   len, page, off                 the board -> the Pico        len bytes, XOR, status
;   5   len, page, off, then len       the Pico -> the board        status (5: XOR wrong)
;       bytes and their XOR
;   6   len, page, off, page2, off2    page:off -> page2:off2       status
;   7   -                              describe the board           found, BASE, SIZE,
;                                                                   STATUS, VERSION
;   0   -                              done: the next byte is the command's answer, read
;                                      as after any command (a status, or a function)
;
; page:off is a page of the board (0 to SIZE*8-1, relative to BASE) and an
; offset into it (0-1FFFh); a transfer may run over into the following pages.
; Status: 1 done, 2 compare: they differ, 3 no board, 4 page or offset out of
; range (nothing done), 5 op 5's XOR didn't match (a byte went missing).
; Refused or not, ops 4 and 5 always pass len bytes and the XOR.
; Bytes to and from the Pico are paced like CH_FETCH's (~75 us).
;
; For each piece of a transfer that lies in one 8K chunk on both sides, the
; page is mapped into a window: a chunk of 4-7 that holds neither the 2068
; memory being copied nor the stack (nor the frame above it). Four
; candidates, at most three excluded, so one is always free; op 6 maps two.
; The window's OWN, SUB and HSR bit are saved, set (OWN, then the HSR bit),
; and put back (spec: "map = OWNn, then F4h bit n; unmap = F4h bit n clear,
; then OWNn = 0"). The mover runs from the EXROM, chunks 0-1, and never maps
; a window there. The whole function runs with interrupts off, and puts back
; the interrupt state it found.
;
; Out: as a response function, to C_END: op 0 goes on to C_END_TAIL ($227F),
; which reads the answer; a failed wait for READY returns C with A = 09h
; (timeout: J), 0Ch (BREAK) or 1Ch (Pico reset); an unknown operation as a
; timeout.
;------------------------------------------------------------------------------
MV_BASE         EQU 0              ; the frame, at IX: BASE
MV_LIM          EQU 1              ;   pages on the board (2)
MV_OK           EQU 3              ;   1: the board answered A5h, 5Ah
MV_ADDR         EQU 4              ;   the operation's parameters: address
MV_LEN          EQU 6              ;   length
MV_PAGE         EQU 8              ;   page
MV_OFF          EQU 10             ;   offset
MV_PAGE2        EQU 12             ;   op 6's destination page
MV_OFF2         EQU 14             ;   and offset
MV_OP           EQU 16             ;   the operation
MV_RES          EQU 17             ;   its reply
MV_XOR          EQU 18             ;   ops 4 and 5: the XOR of the bytes so far
MV_N            EQU 19             ;   this piece's length (2)
MV_W1           EQU 21             ;   window 1: chunk, OWN, SUB, HSR as found (4)
MV_W2           EQU 25             ;   window 2, op 6 (4)
MV_FRAME        EQU 29

MOVER:  push    ix
        ld      a,i                ; P/V = IFF2: were interrupts on?
        push    af
        di
        ld      hl,-MV_FRAME
        add     hl,sp
        ld      sp,hl
        push    hl
        pop     ix                 ; IX = the frame, at SP
        call    MB_PROBE
        jr      .op                ; the first operation follows 89h at once
.next:  call    BIOS_WF_NPH        ; each later one after READY
        jr      c,.fail            ; 02h timeout, 0Ch BREAK, 1Ch reset
.op:    call    MV_RX
        and     a
        jr      z,.end
        cp      7
        jr      z,.info
        jr      nc,.bad
        ld      (ix+MV_OP),a
        call    MV_PARAMS
        call    MV_RUN             ; A = the reply
.rep:   call    MV_TX
        jr      .next
.info:  call    MV_INFO
        jr      .rep
.end:   ld      b,0
        jr      .out
.bad:   ld      a,$02              ; an unknown operation: the stream is lost
.fail:  cp      $02
        jr      nz,.f2
        ld      a,$09              ; a timeout is J, as in C_END2
.f2:    ld      b,1
.out:   ld      c,a
        ld      hl,MV_FRAME
        add     hl,sp
        ld      sp,hl
        pop     af
        jp      po,.di             ; interrupts were off
        ei
.di:    pop     ix
        ld      a,b
        and     a
        jp      z,C_END_TAIL       ; op 0: the answer follows
        ld      a,c
        and     a
        scf
        ret

; MB_PROBE -- the frame's board fields: MV_OK = 1 if ID and IDCOMP read A5h and
; 5Ah (a bus with no board floats: never that pair), BASE, and the page count.
MB_PROBE:
        ld      (ix+MV_OK),0
        ld      a,MB_ID
        call    MB_RD
        cp      $A5
        ret     nz
        ld      a,MB_IDCOMP
        call    MB_RD
        cp      $5A
        ret     nz
        ld      a,MB_BASE
        call    MB_RD
        ld      (ix+MV_BASE),a
        ld      a,MB_SIZE
        call    MB_RD
        ld      l,a
        ld      h,0
        add     hl,hl
        add     hl,hl
        add     hl,hl              ; 8 pages a bank
        ld      (ix+MV_LIM),l
        ld      (ix+MV_LIM+1),h
        ld      (ix+MV_OK),1
        ret

; MB_RD -- A = board register A. MB_WR -- board register A := E.
MB_RD:  out     (MB_SEL),a
        in      a,(MB_DATA)
        ret
MB_WR:  out     (MB_SEL),a
        ld      a,e
        out     (MB_DATA),a
        ret

; MV_PARAMS -- operation A (1-6): its parameters into the frame. The frame's
; fields are in wire order: 1-3 from MV_ADDR (8 bytes), 4-5 from MV_LEN (6),
; 6 from MV_LEN (10).
MV_PARAMS:
        ld      e,MV_ADDR
        ld      b,8
        cp      4
        jr      c,.rx
        ld      e,MV_LEN
        ld      b,6
        cp      6
        jr      c,.rx
        ld      b,10
.rx:    call    FRAME
.b:     call    MV_RX
        ld      (hl),a
        inc     hl
        djnz    .b
        ret

; FRAME -- HL = IX + E.
FRAME:  push    ix
        pop     hl
        ld      d,0
        add     hl,de
        ret

; MV_INFO -- op 7: found (1/0), BASE, SIZE, STATUS sent; A = VERSION, the
; reply. Read fresh, so STATUS (the switch, the battery) is current.
MV_INFO:
        ld      a,(ix+MV_OK)
        call    MV_TX
        ld      a,MB_BASE
        call    MB_RD
        call    MV_TX
        ld      a,MB_SIZE
        call    MB_RD
        call    MV_TX
        ld      a,MB_STATUS
        call    MB_RD
        call    MV_TX
        ld      a,MB_VERSION
        jp      MB_RD

; MV_RX / MV_TX -- a byte from / to the Pico, paced as CH_FETCH paces its
; reads (the Pico feeds and drains 4-deep FIFOs). MV_TX keeps A.
MV_RX:  call    MV_PACE
        in      a,($0E)
        ret
MV_TX:  call    MV_PACE
        out     ($0E),a
        ret
MV_PACE:
        push    bc
        ld      b,READ_DELAY+4
.d:     djnz    .d
        pop     bc
        ret

; MV_RUN -- operations 1-6, whose parameters are in the frame: A = the reply.
MV_RUN: ld      (ix+MV_RES),1
        ld      (ix+MV_XOR),0
        ld      a,(ix+MV_OK)
        and     a
        ld      a,3                ; no board
        jp      z,MV_REFUSE
        ld      e,MV_PAGE
        call    MV_RANGE
        ld      a,4                ; out of range: nothing done
        jp      c,MV_REFUSE
        ld      a,(ix+MV_OP)
        cp      6
        jr      nz,.piece
        ld      e,MV_PAGE2
        call    MV_RANGE
        ld      a,4
        jp      c,MV_REFUSE
.piece: ld      l,(ix+MV_LEN)      ; the next piece: as much as fits in
        ld      h,(ix+MV_LEN+1)    ;   one 8K chunk on every side
        ld      a,h
        or      l
        jp      z,.done
        ld      e,(ix+MV_OFF)
        ld      d,(ix+MV_OFF+1)
        call    MV_ROOM
        ld      a,(ix+MV_OP)
        cp      4
        jr      nc,.n2
        ld      a,(ix+MV_ADDR+1)
        and     $1F
        ld      d,a
        ld      e,(ix+MV_ADDR)
        call    MV_ROOM
.n2:    ld      a,(ix+MV_OP)
        cp      6
        jr      nz,.n3
        ld      e,(ix+MV_OFF2)
        ld      d,(ix+MV_OFF2+1)
        call    MV_ROOM
.n3:    ld      (ix+MV_N),l
        ld      (ix+MV_N+1),h
        ld      b,0                ; chunks the window must not be
        ld      a,(ix+MV_OP)
        cp      4
        jr      nc,.w1
        ld      a,(ix+MV_ADDR+1)
        call    CHUNK_BIT
        ld      b,a                ; not the 2068 memory's own
.w1:    call    MV_WIN             ; A = the window; B += the stack's
        push    bc
        ld      e,MV_W1
        call    FRAME
        ex      de,hl
        ld      l,(ix+MV_PAGE)
        ld      h,(ix+MV_PAGE+1)
        call    MV_MAP
        ld      e,(ix+MV_OFF)
        ld      d,(ix+MV_OFF+1)
        add     hl,de              ; HL = page:offset, as the Z80 sees it
        pop     bc
        ld      a,(ix+MV_OP)
        cp      6
        jr      nz,.go
        push    hl
        ld      a,(ix+MV_W1)
        call    CHUNK_MASK
        or      b
        ld      b,a                ; nor window 1
        call    MV_WIN
        ld      e,MV_W2
        call    FRAME
        ex      de,hl
        ld      l,(ix+MV_PAGE2)
        ld      h,(ix+MV_PAGE2+1)
        call    MV_MAP
        ld      e,(ix+MV_OFF2)
        ld      d,(ix+MV_OFF2+1)
        add     hl,de
        ex      de,hl              ; DE = page2:offset2
        pop     hl                 ; HL = page:offset
.go:    ld      c,(ix+MV_N)
        ld      b,(ix+MV_N+1)
        call    MV_DO
        ld      a,(ix+MV_OP)
        cp      6
        jr      nz,.u1
        ld      e,MV_W2
        call    FRAME
        call    MV_UNMAP
.u1:    ld      e,MV_W1
        call    FRAME
        call    MV_UNMAP
        ld      c,(ix+MV_N)        ; on by the piece's length
        ld      b,(ix+MV_N+1)
        ld      l,(ix+MV_LEN)
        ld      h,(ix+MV_LEN+1)
        and     a
        sbc     hl,bc
        ld      (ix+MV_LEN),l
        ld      (ix+MV_LEN+1),h
        ld      l,(ix+MV_ADDR)
        ld      h,(ix+MV_ADDR+1)
        add     hl,bc
        ld      (ix+MV_ADDR),l
        ld      (ix+MV_ADDR+1),h
        ld      e,MV_PAGE
        call    MV_ADV
        ld      a,(ix+MV_OP)
        cp      6
        jp      nz,.piece
        ld      e,MV_PAGE2
        call    MV_ADV
        jp      .piece
.done:  ld      a,(ix+MV_OP)
        cp      4
        jr      z,.sx
        cp      5
        jr      nz,.res
        call    MV_RX              ; op 5: the Pico's XOR of what it sent
        cp      (ix+MV_XOR)
        jr      z,.res
        ld      (ix+MV_RES),5
        jr      .res
.sx:    ld      a,(ix+MV_XOR)      ; op 4: the XOR of what was sent
        call    MV_TX
.res:   ld      a,(ix+MV_RES)
        ret

; MV_REFUSE -- reply A, nothing done. Ops 4 and 5 still pass their bytes, so
; the stream stays in step: op 4 sends len zeros and their XOR (0), op 5 reads
; and drops len bytes and the XOR.
MV_REFUSE:
        ld      (ix+MV_RES),a
        ld      a,(ix+MV_OP)
        sub     4
        cp      2
        jr      nc,.r              ; not 4 or 5
        ld      e,a                ; 0: op 4, 1: op 5
        ld      c,(ix+MV_LEN)
        ld      b,(ix+MV_LEN+1)
        inc     bc                 ; the bytes and the XOR (0 here: 65536)
.l:     ld      a,e
        and     a
        jr      nz,.in
        call    MV_TX              ; op 4: a zero
        jr      .n
.in:    call    MV_RX              ; op 5: dropped
.n:     dec     bc
        ld      a,b
        or      c
        jr      nz,.l
.r:     ld      a,(ix+MV_RES)
        ret

; MV_DO -- one piece: BC (1-2000h) bytes; HL = page:offset in its window;
; DE = page2:offset2 (op 6).
MV_DO:  ld      a,(ix+MV_OP)
        cp      6
        jr      z,.ldir            ; page to page
        cp      4
        jr      nc,.port
        ld      e,(ix+MV_ADDR)
        ld      d,(ix+MV_ADDR+1)   ; DE = the 2068 memory
        cp      2
        jr      z,.ldir            ; op 2: the board -> 2068 memory
        ex      de,hl
        jr      c,.ldir            ; op 1: 2068 memory -> the board
.cmp:   ld      a,(de)             ; op 3: compare
        cp      (hl)
        jr      z,.same
        ld      (ix+MV_RES),2
.same:  inc     hl
        inc     de
        dec     bc
        ld      a,b
        or      c
        jr      nz,.cmp
        ret
.ldir:  ldir
        ret
.port:  jr      nz,.in             ; (still CP 4) op 5
.out:   ld      a,(hl)             ; op 4: to the Pico
        call    MV_TX
        xor     (ix+MV_XOR)
        ld      (ix+MV_XOR),a
        inc     hl
        dec     bc
        ld      a,b
        or      c
        jr      nz,.out
        ret
.in:    call    MV_RX              ; op 5: from the Pico
        ld      (hl),a
        xor     (ix+MV_XOR)
        ld      (ix+MV_XOR),a
        inc     hl
        dec     bc
        ld      a,b
        or      c
        jr      nz,.in
        ret

; MV_ROOM -- HL = the smaller of HL and 2000h - DE (DE an offset in a chunk).
MV_ROOM:
        push    hl
        ld      hl,$2000
        and     a
        sbc     hl,de
        ex      de,hl              ; DE = the room left
        pop     hl
        push    hl
        and     a
        sbc     hl,de
        pop     hl
        ret     c
        ex      de,hl
        ret

; MV_RANGE -- E = the frame offset of a page, its offset after it: carry if
; the offset is 2000h or more, or the transfer (MV_LEN bytes) would run past
; the board's last page.
MV_RANGE:
        call    FRAME
        ld      c,(hl)
        inc     hl
        ld      b,(hl)             ; BC = the page
        inc     hl
        ld      e,(hl)
        inc     hl
        ld      d,(hl)             ; DE = the offset
        ld      a,d
        cp      $20
        ccf
        ret     c
        ld      a,b
        cp      2
        ccf
        ret     c                  ; 512 pages at most: no overflow below
        ld      l,(ix+MV_LEN)
        ld      h,(ix+MV_LEN+1)
        ld      a,h
        or      l
        ret     z                  ; nothing to move (NC)
        dec     hl
        add     hl,de              ; the last byte's offset: 17 bits
        ld      a,h
        rla
        rla
        rla
        rla
        and     $0F                ; its pages past this one: bits 16-13
        add     a,c
        ld      c,a
        jr      nc,.p
        inc     b
.p:     ld      l,(ix+MV_LIM)      ; BC = the last page
        ld      h,(ix+MV_LIM+1)
        scf
        sbc     hl,bc              ; carry if the last page >= the page count
        ret

; MV_ADV -- E = the frame offset of a page, its offset after it: on by the
; piece (BC bytes). A piece never runs past its page, so the offset reaches
; 2000h at most, and then it is the next page's 0.
MV_ADV: call    FRAME              ; HL -> the page
        push    hl
        inc     hl
        inc     hl
        ld      e,(hl)
        inc     hl
        ld      d,(hl)             ; DE = the offset; HL -> its high byte
        ex      de,hl
        add     hl,bc
        ex      de,hl              ; DE = offset + piece
        ld      a,d
        cp      $20
        jr      c,.st
        ld      de,0
        ex      (sp),hl            ; HL -> the page
        inc     (hl)
        jr      nz,.nc
        inc     hl
        inc     (hl)
        dec     hl
.nc:    ex      (sp),hl
.st:    ld      (hl),d
        dec     hl
        ld      (hl),e
        pop     hl
        ret

; MV_WIN -- B = chunks not to use (bit n = chunk n), to which this adds the
; stack's: the chunks of SP-32 and SP+48, which take in the calls below SP and
; the frame and return addresses above it (80 bytes: two chunks at most).
; A = the window, the first of chunks 4-7 left.
MV_WIN: ld      hl,-32
        add     hl,sp
        ld      a,h
        call    CHUNK_BIT
        or      b
        ld      b,a
        ld      hl,48
        add     hl,sp
        ld      a,h
        call    CHUNK_BIT
        or      b
        ld      b,a
        ld      c,4
        rra
        rra
        rra
        rra                        ; chunk 4's bit to bit 0
.t:     rra
        jr      nc,.ok
        inc     c
        jr      .t                 ; at most three of the four are taken
.ok:    ld      a,c
        ret

; CHUNK_BIT -- A = an address's high byte: A = its chunk's bit.
; CHUNK_MASK -- A = a chunk, 0-7: A = its bit. BC kept.
CHUNK_BIT:
        rlca
        rlca
        rlca
        and     7
CHUNK_MASK:
        push    bc
        ld      b,a
        ld      a,1
        inc     b
.s:     dec     b
        jr      z,.e
        add     a,a
        jr      .s
.e:     pop     bc
        ret

; MV_MAP -- map page HL into chunk A, saving that chunk's OWN, SUB and HSR at
; (DE), after the chunk number. HL = the window's address.
MV_MAP: ld      c,a
        ld      (de),a
        inc     de
        call    MB_RD              ; OWNw as it was
        ld      (de),a
        inc     de
        ld      a,c
        add     a,MB_SUB
        call    MB_RD              ; SUBw
        ld      (de),a
        inc     de
        in      a,(HSR)
        ld      (de),a             ; the HSR
        ld      a,l
        and     7
        ld      b,a                ; B = the page's 8K in its bank
        srl     h
        rr      l
        srl     h
        rr      l
        srl     h
        rr      l                  ; L = the page / 8
        ld      a,(ix+MV_BASE)
        add     a,l
        ld      e,a                ; E = its bank
        ld      a,c
        call    MB_WR              ; OWNw = the bank (SUBw = w) ...
        ld      a,c
        add     a,MB_SUB
        ld      e,b
        call    MB_WR              ; ... SUBw = its 8K
        ld      a,c
        call    CHUNK_MASK
        ld      b,a
        in      a,(HSR)
        or      b
        out     (HSR),a            ; then the HSR bit: the RAM under it keeps its bytes
        ld      a,c
        rrca
        rrca
        rrca
        ld      h,a
        ld      l,0                ; HL = w * 2000h
        ret

; MV_UNMAP -- put back the chunk saved at (HL) by MV_MAP. An owner of 0 goes
; back after the HSR, any other before it.
MV_UNMAP:
        ld      c,(hl)             ; the window
        inc     hl
        ld      e,(hl)             ; its owner
        inc     hl
        ld      b,(hl)             ; its SUB
        inc     hl
        ld      a,e
        and     a
        jr      nz,.own
        ld      a,(hl)
        out     (HSR),a
.own:   ld      a,c
        call    MB_WR              ; OWNw (SUBw = w)
        ld      a,c
        add     a,MB_SUB
        ld      e,b
        call    MB_WR              ; SUBw
        ld      a,(hl)
        out     (HSR),a
        ret

;------------------------------------------------------------------------------
; MB_DETECT -- the end of MB_BOOT: the bank count for the Timex bank API
; (bankapi.asm). With ID and IDCOMP reading A5h and 5Ah, BASE goes to 6404h
; and the count to MAXBNK (5CBEh) and 6315h: SIZE, cut so the last bank is no
; higher than 253 (FEh and FFh are EXROM and HOME). A BASE of 0 or above 253
; is no board. Else the count stays the 0 that $09F4 and $1C8D stored. The
; boot has copied the bank code to 6200h by now; the 64-column copy is made
; later, from it, so it gets both. HL and DE kept for SYSCON_END.
;------------------------------------------------------------------------------
MB_NBANKS       EQU $6315          ; the bank code's count (bankapi.asm NBANKS)
MB_MBBASE       EQU $6404          ; and the board's BASE (MBBASE)
MAXBNK          EQU $5CBE

MB_DETECT:
        push    de
        ld      a,MB_ID
        call    MB_RD
        cp      $A5
        jr      nz,.x
        ld      a,MB_IDCOMP
        call    MB_RD
        cp      $5A
        jr      nz,.x
        ld      a,MB_SIZE
        call    MB_RD
        ld      d,a
        ld      a,MB_BASE
        call    MB_RD
        ld      e,a
        dec     a
        cp      253
        jr      nc,.x              ; BASE 0, or FEh, FFh
        ld      a,254
        sub     e                  ; banks BASE to 253
        cp      d
        jr      c,.n
        ld      a,d                ; or SIZE, if fewer
.n:     ld      (MAXBNK),a
        ld      (MB_NBANKS),a
        ld      a,e
        ld      (MB_MBBASE),a
.x:     pop     de
        jp      SYSCON_END

;------------------------------------------------------------------------------
; MB_CALL_HOME -- CALL_HOME (EXROM $03DD) with HOME in chunks 0-1 only. $03DE's
; LD HL,FF00h is patched to JP here (build-rom.py): the bank word FFFCh, then
; the two zero words. (The genuine thunk's LD H,0 made its zeros from FF00h's
; L, so FFFCh can't be patched in place: it would push a parameter count of
; FCh.) FF00h gave HOME every chunk, taking them from any board bank mapped in
; chunks 2-7. Reached from EXROM code, so chunk 1 is the EXROM.
;------------------------------------------------------------------------------
MB_CALL_HOME:
        ld      hl,$FFFC
        push    hl
        ld      hl,0
        push    hl
        push    hl
        exx
        call    $0F99              ; BANK_SWITCH
        pop     ix
        ret

    ENDIF   ; MEGABANK


FDD_END:
        SAVEBIN "fddcmd.bin", FDD_BASE, FDD_END-FDD_BASE

    IFDEF MEGABANK
;------------------------------------------------------------------------------
; The "r:" channels (phase 9) don't fit in the module's 4K: they go at EXROM
; RCH_BASE, free in the base ROM, in the same chunk (1) as the module.
; build-rom.py splices rchan.bin there.
;------------------------------------------------------------------------------
RCH_BASE        EQU $2400
        ORG     RCH_BASE
        INCLUDE "rchan.asm"
RCH_END:
        ASSERT  RCH_END <= $2C8C     ; EXROM 2C8Ch: the fast entry's JP FX_ENTRY (build-rom.py)
        SAVEBIN "rchan.bin", RCH_BASE, RCH_END-RCH_BASE
    ENDIF
