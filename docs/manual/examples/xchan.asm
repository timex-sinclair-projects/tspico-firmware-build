; A memory channel for the TS 2068: PRINT #4 fills a buffer, INPUT #4 reads it back.

MAKE_ROOM EQU 12BBh     ; HOME: make BC bytes of room after HL
STRMS     EQU 5C10h     ; the stream table, streams -3 to 15
CHANS     EQU 5C4Fh     ; the channel area
PROG      EQU 5C53h     ; the BASIC program, right after the channel area
BUF       EQU 50176     ; 1K of text
BUFEND    EQU BUF+1024

        ORG 50000

; RANDOMIZE USR 50000: a new record at the end of CHANS, and stream 4 on it.
INSTALL: LD HL,(PROG)
        DEC HL
        LD A,(HL)
        CP 80h          ; the end marker, at PROG-1 or PROG-2
        JR Z,FOUND
        DEC HL
FOUND:  PUSH HL         ; the record goes where the 80h is now
        DEC HL
        LD BC,5
        CALL MAKE_ROOM  ; the 80h moves up five bytes, and so does PROG
        POP DE
        PUSH DE
        LD HL,RECORD
        LD BC,5
        LDIR
        POP HL          ; the stream's offset: record - CHANS + 1
        LD DE,(CHANS)
        AND A
        SBC HL,DE
        INC HL
        LD (STRMS+2*(4+3)),HL
        LD HL,BUF
        LD (WPTR),HL
        LD (RPTR),HL
        RET

RECORD: DEFW XOUT       ; the output routine
        DEFW XIN        ; the input routine
        DEFB 'X'        ; the channel's letter

WPTR:   DEFW BUF        ; where the next character goes
RPTR:   DEFW BUF        ; the next character to hand out

; Output: the character is in A.
XOUT:   LD HL,(WPTR)
        LD B,A
        LD A,H
        CP BUFEND/256   ; full: drop the character
        RET Z
        LD (HL),B
        INC HL
        LD (WPTR),HL
        RET

; Input: carry set and A = the character, or carry and zero clear at the end.
XIN:    LD HL,(RPTR)
        LD DE,(WPTR)
        AND A
        SBC HL,DE
        JR Z,ATEND      ; everything written has been read
        ADD HL,DE
        LD A,(HL)
        INC HL
        LD (RPTR),HL
        SCF
        RET
ATEND:  LD A,1
        AND A           ; NC NZ: the ROM gives "8 End of file"
        RET
