; picolib.asm -- talk to the TS-Pico from machine code, through its ports.
;
; For ROM 2.0 (and 2.1) with firmware 2.0 or later. Include this file at the
; end of your program; the program must define two words, PMR1 and PMR2, which
; carry the two CODE numbers of the command (SAVE "tpi:..." CODE PMR1,PMR2).
;
; Written for a RAM program called with USR from BASIC: HOME ROM paged in,
; interrupts on. Nothing here uses IX or IY or calls the ROM, except RST 10h
; to print (GET_REPLY) and the keyboard system variables (GETKEY).
;
; Every routine that can fail returns carry set with A = an error code, which
; is the byte BASIC's RST 8 takes (ERR_NR): see RAISE at the end.

PORT_DATA   equ 0Eh             ; data, both ways
PORT_STAT   equ 0Fh             ; status (IN); SYNC/abort (OUT)

ST_READY    equ 6               ; 1 = the Pico has its answer ready
ST_IDLE     equ 3               ; 1 = no transaction open
ST_RECOV    equ 2               ; 0 = the Pico gave up on a transaction

E_R         equ 1Ah             ; R Tape loading error (checksum)
E_D         equ 0Ch             ; D BREAK - CONT repeats
E_J         equ 12h             ; J Invalid I/O device (no answer)
E_T         equ 1Ch             ; T TS-Pico reset, try again (ROM 2.0)

LAST_K      equ 5C08h           ; the last key pressed (system variable)
FLAGS       equ 5C3Bh           ; bit 5 set = a new key is in LAST_K

; ---------------------------------------------------------------------------
; WAIT_IDLE -- wait up to about 1 s for READY and IDLE together.
; Z = the Pico is idle; NZ = timed out. Uses A, F, BC.
WAIT_IDLE:
        ld bc,0
.poll:  in a,(PORT_STAT)
        and (1 << ST_READY) | (1 << ST_IDLE)
        cp (1 << ST_READY) | (1 << ST_IDLE)
        ret z
        dec bc
        ld a,b
        or c
        jr nz,.poll
        inc a                   ; A was 0: make it NZ
        ret

; ---------------------------------------------------------------------------
; PICO_SYNC -- start a new transaction: OUT (0Fh),03h. The Pico empties both
; its FIFOs, puts one 01h (the "pre-load") in its transmit FIFO and goes idle.
; Waits for IDLE first: an answer marked READY-but-not-IDLE (a channel command)
; means the Pico is still finishing the last command. Uses A, F, BC.
PICO_SYNC:
        call WAIT_IDLE
        ld a,03h
        out (PORT_STAT),a
        jp WAIT_IDLE

; ---------------------------------------------------------------------------
; WAIT_READY -- wait (about 20 s at most) for the READY bit.
; NC = ready. C = failed, A = E_J (timeout), E_D (BREAK pressed: the Pico has
; been told and is idle again) or E_T (the Pico reset the transaction).
; Keeps BC, DE, HL.
WAIT_READY:
        push bc
        push hl
        ld hl,0
        ld c,13                 ; 13 x 65536 polls of about 86 T
.poll:  in a,(PORT_STAT)
        bit ST_READY,a
        jr nz,.ready
        ld a,7Fh
        in a,(0FEh)             ; keyboard row with SPACE in bit 0
        rra
        jr c,.more
        ld a,0FEh
        in a,(0FEh)             ; keyboard row with CAPS SHIFT in bit 0
        rra
        jr nc,.brk              ; both down: BREAK
.more:  dec hl
        ld a,h
        or l
        jr nz,.poll
        dec c
        jr nz,.poll
        ld a,E_J
        jr .fail
.ready: bit ST_RECOV,a          ; active low
        ld a,E_T
        jr z,.fail
        pop hl
        pop bc
        and a                   ; NC
        ret
.brk:   ld a,03h
        out (PORT_STAT),a       ; abort: the Pico drops the command
        call WAIT_IDLE
        ld a,E_D
.fail:  pop hl
        pop bc
        scf
        ret

; ---------------------------------------------------------------------------
; TXX -- send A to the Pico, XOR it into D, then pause about 50 us.
; Uses A, F. Keeps BC, E, HL.
TXX:    out (PORT_DATA),a
        xor d
        ld d,a
        push bc
        ld b,11
.d:     djnz .d
        pop bc
        ret

; RXP -- pause about 75 us, then read a byte from the Pico into A.
; Keeps BC, DE, HL. (IN A,(n) changes no flags.)
RXP:    push bc
        ld b,16
.d:     djnz .d
        pop bc
        in a,(PORT_DATA)
        ret

; ---------------------------------------------------------------------------
; SEND_CMD -- send one command: HL = its text ("tpi:..."), BC = its length.
; PMR1 and PMR2 are sent as the CODE numbers.
; NC = sent; now read the answer with GET_REPLY or GET_DATA.
; C  = failed, A = error code.
; Uses all registers except IX, IY.
SEND_CMD:
        push hl
        push bc
        call PICO_SYNC          ; a timeout here shows up in WAIT_READY below
        pop bc
        pop hl
        ld d,0                  ; running XOR
        ld a,'B'
        call TXX                ; 0: block type 'B' (a command)
        xor a
        call TXX                ; 1: 0 = SAVE "tpi:..."
        ld a,0FFh
        call TXX                ; 2: bank (FFh = HOME)
        ld a,(PMR1)
        call TXX                ; 3-4: first CODE number
        ld a,(PMR1+1)
        call TXX
        ld a,(PMR2)
        call TXX                ; 5-6: second CODE number
        ld a,(PMR2+1)
        call TXX
        ld a,c
        call TXX                ; 7-8: length of the text
        ld a,b
        call TXX
        ld a,d
        call TXX                ; 9: XOR of bytes 0-8
        in a,(PORT_DATA)        ; the pre-load, waiting since the SYNC
        cp 1
        ld a,E_J
        scf
        ret nz                  ; anything else: the link is out of step
        call WAIT_READY         ; the Pico says READY when it's listening
        ret c
        ld d,0
        ld a,'D'
        call TXX                ; the body: 'D', length, text, XOR
        ld a,c
        call TXX
        ld a,b
        call TXX
.body:  ld a,(hl)
        inc hl
        call TXX
        dec bc
        ld a,b
        or c
        jr nz,.body
        ld a,d
        call TXX                ; the Pico checks this one: Report R if wrong
        and a
        ret

; ---------------------------------------------------------------------------
; GET_REPLY -- read the answer to an ordinary command, the way the ROM does.
; Prints text the Pico sends (functions 81h, 86h, 88h) with RST 10h, so select
; the channel first (LD A,2 / CALL CHAN_OPEN for the main screen). At a
; "Scroll?" prompt it waits for a key and sends it, then reads on whatever the
; key: the Pico decides what it means and ends the listing with 03h.
; NC = OK. C = failed, A = error code.
GET_REPLY:
        call WAIT_READY
        ret c
        in a,(PORT_DATA)
        cp 81h
        jr z,.msg
        cp 86h
        jr z,.loop
        cp 88h
        jr z,.loop
        cp 80h
        jp c,MAP_STATUS         ; a plain status byte
        ld a,03h                ; a function this code doesn't know:
        out (PORT_STAT),a       ; abort it, as BREAK would
        call WAIT_IDLE
        ld a,E_D
        scf
        ret

.msg:   call RXP                ; 81h: status, text, 00h
        push af
.m1:    call TEXT
        jr nc,.m1               ; until 00h (or 03h)
.done:  pop af
        jp MAP_STATUS

.loop:  call RXP                ; 86h: status, then pages of text
        push af
.page:  call TEXT
        jr nc,.page
        cp 03h
        jr z,.done              ; 03h: the end
        call GETKEY             ; 00h: end of a page, the Pico waits for a key
        push af
        call WAIT_READY         ; the ROM waits for READY before it sends a key
        jr c,.kfail
        pop af
        out (PORT_DATA),a       ; any key, N included: the Pico ends the loop
        call WAIT_READY         ; the next page, or the Pico's last words, are on their way
        jr nc,.page
        pop hl                  ; drop the saved status, keep A
        scf
        ret
.kfail: pop hl
        pop hl
        scf
        ret

; TEXT -- read one character of an answer and print it, as the ROM does.
; C = a terminator, with A = 00h (the end of the text or page) or 03h (the end
; of an 86h listing). NC = printed. A control code from 10h (INK) to 17h (TAB)
; is printed with its value bytes, one or two (AT and TAB), whatever they are:
; INK 0 is a colour, not the end. Keeps BC, DE, HL.
TEXT:   call RXP
        and a
        scf
        ret z                   ; 00h
        cp 03h
        scf
        ret z                   ; 03h
        push bc
        ld b,1                  ; one byte: the character
        cp 10h
        jr c,.put
        cp 18h
        jr nc,.put
        inc b                   ; a control code and one value
        cp 16h
        jr c,.put
        inc b                   ; AT, TAB: two values
.put:   push bc
        rst 10h
        pop bc
        dec b
        jr z,.out
        call RXP                ; a value byte
        jr .put
.out:   pop bc
        and a                   ; NC
        ret

; ---------------------------------------------------------------------------
; GET_DATA -- read a data answer into memory at HL. The format is the one
; tpi:chrd uses:  status 1, count n (1-255), n bytes, XOR of the n bytes.
; Status 7 means "end of file"; any other status is an error.
; NC, Z  = got it: E = n, HL = just past the data.
; NC, NZ = end of file, nothing read.
; C      = failed, A = error code.
GET_DATA:
        call WAIT_READY
        ret c
        in a,(PORT_DATA)
        cp 1
        jr z,.data
        cp 7
        jp nz,MAP_STATUS        ; an error status
        or a                    ; 7: NZ and NC
        ret
.data:  call RXP
        ld e,a                  ; n
        ld b,a
        ld c,0                  ; XOR
.byte:  call RXP
        ld (hl),a
        inc hl
        xor c
        ld c,a
        djnz .byte
        call RXP
        cp c
        ld a,E_R                ; a byte went missing or changed
        scf
        ret nz
        xor a                   ; Z, NC
        ret

; ---------------------------------------------------------------------------
; MAP_STATUS -- A = a status byte from the Pico (below 80h).
; NC if it is 1 (OK); otherwise C with A = the error code BASIC would report.
MAP_STATUS:
        and a
        jr z,.none              ; 00h: an empty FIFO, no answer at all
        dec a
        ret z                   ; 1: OK (AND A cleared the carry)
        cp 10
        jr c,.map
        ld a,10                 ; 11 and over: D
.map:   push hl
        push de
        ld hl,RPT_TAB-1
        ld e,a
        ld d,0
        add hl,de
        ld a,(hl)
        pop de
        pop hl
        scf
        ret
.none:  ld a,E_J
        scf
        ret

; status 2..11 -> R F Q C 6 8 A 9 J D  (the ROM's own table at EXROM 1BF3h)
RPT_TAB:
        db 1Ah, 0Eh, 19h, 0Bh, 05h, 07h, 09h, 08h, 12h, 0Ch

; ---------------------------------------------------------------------------
; GETKEY -- wait for a key press and return it in A, as typed (the Pico reads
; either case). Uses the keyboard scan the ROM runs on every interrupt.
; Keeps BC, DE, HL.
GETKEY: push hl
        ei
        ld hl,FLAGS
        res 5,(hl)
.w:     halt
        bit 5,(hl)
        jr z,.w
        pop hl
        ld a,(LAST_K)
        ret

; ---------------------------------------------------------------------------
; RAISE -- stop the BASIC program with the report whose code is in A,
; exactly as if BASIC had raised it. Does not return.
RAISE:  ld (.code),a
        rst 8
.code:  db 0

; ---------------------------------------------------------------------------
; HEX -- write A as two hex digits at DE, DE advanced. Uses A, F.
HEX:    push af
        rrca
        rrca
        rrca
        rrca
        call .nib
        pop af
.nib:   and 0Fh
        add a,'0'
        cp '9'+1
        jr c,.put
        add a,'a'-'9'-1
.put:   ld (de),a
        inc de
        ret

CHAN_OPEN   equ 1230h           ; HOME: select stream A for RST 10h
