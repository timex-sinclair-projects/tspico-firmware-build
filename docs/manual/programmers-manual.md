# TS-Pico Programmer's Manual

### Machine code for the TS-2068, and new commands for the Pico — version 2.2

> **About this manual.** This manual describes **TS-Pico 2.2** (firmware 2.2.1 and ROM 2.2, October
> 2026). It was written from the source code at the `v2.1` tag: the firmware, the ROM patches and
> the test harnesses. Nothing it covers changed in 2.2 except the version numbers. Appendix D lists the repository documents that go with it.
>
> **Every example is in the `examples` folder next to this manual.** Each machine-code example
> was assembled with sjasmplus. It was then run in the firmware repository's Z80 interpreter
> against a simulated TS-Pico: that's `test_examples.py`, with 71 checks, all passing. The
> Pico-side examples were run through the firmware's real command dispatcher by
> `test_extcmd_host.py`. **None of them has yet run on a real 2068.** `picoex.tap` holds all the
> machine-code examples, ready to try. The BIOS example (`bios.asm`) and the error trap in
> section 8.4 go through the ROM's bank switching, which the simulation can't model. Treat
> them as the least certain code in this book.

---

## Contents

**Part 1: Talking to the TS-Pico from the 2068**

1. Before You Start
2. The Hardware: Two Ports and a Status Byte
3. The Conversation: How a Command Travels
4. A Machine-Code Toolkit: `picolib.asm`
5. Worked Examples
6. Files as Streams: the Channel Commands
7. Other Commands, and What Not to Send
8. Using the ROM's Pico BIOS
9. Rules of the Road for Z80 Programs

**Part 2: Programming the TS-Pico**

10. Inside the Firmware
11. Your First Pico Command
12. A Cookbook of Answers
13. Adding a Built-in Command
14. Timing Rules on the Pico
15. Testing and Debugging
16. Rules of the Road for Pico Code

**Appendices**

- A. Protocol Quick Reference
- B. The Pico BIOS and Useful ROM Addresses
- C. Firmware Helper Reference
- D. Further Reading in the Repository
- E. The Example Files

---

# Part 1: Talking to the TS-Pico from the 2068

# Chapter 1: Before You Start

> **Chapter Preview.** Who this book is for, what you need, the three ways a 2068 program can
> reach the TS-Pico, and how to tell which ROM you're running.

## 1.1 Who this book is for

The *TS-Pico User Manual* shows you every command from BASIC. This book is for when BASIC isn't
enough. Maybe you want a game to keep a high-score table on the SD card. Maybe you want to load a
file of any size straight into memory, or add a command of your own to the Pico. We assume you
know Z80 assembly language and TS-2068 BASIC. For Part 2, you'll also want some MicroPython.

The book has two halves, one for each end of the cable:

- **Part 1** is the 2068 side: the ports, the bytes that make up a command, and a small library
  of machine-code routines that does the work for you.
- **Part 2** is the Pico side: how the firmware is put together, and how to add a command, from
  a five-line experiment to a built-in feature.

## 1.2 What you need

- A TS-Pico with the **2.2 release**: its firmware, and ROM 2.2 in the 2068. The ROM opens
  every exchange with a "SYNC" that the 1.1 firmware doesn't understand. Our
  machine-code routines do the same, so they need firmware 2.0 or later as well.
- An assembler for your computer. The examples use **sjasmplus** syntax (local labels start with
  a dot, `equ` and `db` as usual).
- For Part 2: a USB cable and either Thonny or the repository's `tools/pico-serial.py`.

## 1.3 Three ways in

There are three ways for a 2068 program to use the TS-Pico. Pick the simplest one that does the
job.

1. **From BASIC**, with `SAVE "tpi:..."`. Every command in the User Manual works this way, and
   `SAVE t$ CODE a,b` works with a string variable, so a program can build its commands as it
   goes. For a command that sends data back, BASIC can read the data with `IN 14`
   (section 5.6).
2. **From machine code, straight through the ports.** This is the main subject of this book. It
   is plain `IN` and `OUT` on ports 14 and 15. You don't need the ROM, so it works from any
   memory bank, and you decide what happens when something goes wrong.
3. **From machine code, through the ROM's "Pico BIOS"**: a small table of routines in the
   EXROM. It saves a few bytes, but a program running in RAM has to switch ROM banks to reach
   it, and that has traps of its own (Chapter 8).

We recommend the second way, and the library in Chapter 4 makes it easy.

## 1.4 Which ROM am I running?

The byte at address 101 (0065h) of the HOME ROM tells you:

```basic
PRINT PEEK 101
```

| `PEEK 101` | ROM |
|---|---|
| 21 (15h) | 1.1 |
| 33 (21h) | 2.1 |
| 34 (22h) | 2.2 |

## 1.5 Summary

1. Part 1 is the 2068 side; Part 2 is the Pico side.
2. You need the 2.2 release: its firmware and ROM 2.2.
3. BASIC, raw ports, or the ROM's BIOS: raw ports are the most flexible, and this book's library
   does the hard parts.
4. `PEEK 101` tells you the ROM version: 34 for 2.2.

---

# Chapter 2: The Hardware: Two Ports and a Status Byte

> **Chapter Preview.** The two I/O ports, what each bit of the status byte means, the
> "auto-busy" rule, and how fast you can send and receive.

## 2.1 The ports

The TS-Pico answers on two Z80 I/O ports:

| Port | Decimal | `IN` gives you | `OUT` does |
|---|---|---|---|
| 0Eh | 14 | the next byte from the Pico's transmit FIFO, or **00h if it's empty** | puts a byte in the Pico's receive FIFO |
| 0Fh | 15 | the **status byte**. Reading it takes nothing from the FIFO. | **SYNC / abort**: the firmware treats any write here as "stop whatever you're doing and start fresh" |

Each FIFO holds only **four bytes**. There's no wait line: the Z80 is never held up. This has
two consequences you'll meet again and again:

- A read from port 14 when the Pico hasn't queued anything yet quietly gives you **00h**.
  Nothing tells you it happened, except a checksum that doesn't match later.
- A byte sent while the Pico's receive FIFO is full is quietly **lost**.

So everything in this book is paced: we either wait for the status byte to say "ready", or we
leave a short gap between bytes that the Pico is known to keep up with.

## 2.2 The status byte

Port 15 reads a status byte. Three bits matter:

| Bit | Name | Meaning |
|---|---|---|
| 6 | READY | 1 = the Pico has its answer (or is ready for your next bytes) |
| 3 | IDLE | 1 = no transaction is open |
| 2 | RECOVERED | **0** = the Pico gave up on a transaction by itself (active low) |

The other bits are reserved. In practice you'll see four values:

| Value | Meaning |
|---|---|
| FFh | ready and idle: the Pico is waiting for a new command |
| F7h | ready, but the command isn't finished yet (IDLE is clear) |
| FBh | ready and idle, but RECOVERED: the Pico abandoned the last transaction. The ROM reports this as **T TS-Pico reset, try again** |
| 00h | busy |

Test RECOVERED only when READY is set: the busy value, 00h, has bit 2 clear too.

## 2.3 Auto-busy

**Every `OUT` to either port makes the status byte read 00h (busy).** The Pico's interface does
this by itself, in hardware, the moment your byte arrives. The status stays busy until the
firmware has dealt with the byte and says READY again.

This is the most useful rule in the whole protocol. After you send anything, wait for READY
before you read the answer, and you can't read too early.

## 2.4 How fast?

| Direction | Safe pace | Notes |
|---|---|---|
| Z80 → Pico, inside a command | a byte every 30–50 µs | the ROM sends every ~30 µs. Our library uses ~50 µs. Never use `OTIR`. |
| Pico → Z80, data answers | a byte every ~75 µs | the ROM's own channel driver reads every ~75 µs. Our library does the same. Never use `INIR`. |
| Gaps | up to 1 second | the Pico gives up on a half-received command after **1 s** of silence |

Slower is always safe, up to that one-second limit. At 3.5 MHz, 50 µs is about 176 T-states. A
`DJNZ` loop of 11 does it, and a loop of 16 gives about 75 µs.

## 2.5 Summary

1. Port 14 carries data both ways; port 15 is the status (IN) and SYNC/abort (OUT).
2. Four-byte FIFOs, no wait line: an empty read gives 00h and an overflow is lost.
3. READY (bit 6), IDLE (bit 3), RECOVERED (bit 2, active low).
4. Every OUT makes the Pico busy until it says READY again.
5. Pace your bytes: about 50 µs out, 75 µs in, and never a gap of a second in the middle of a
   command.

---

# Chapter 3: The Conversation: How a Command Travels

> **Chapter Preview.** What happens, byte by byte, when the 2068 sends `SAVE "tpi:path"`: the
> SYNC, the pre-load byte, the pre-header, the body, and the answer. Then the status codes and
> the "response functions" that let the Pico print on your screen.

## 3.1 The shape of a transaction

Every command is one **transaction**, and every transaction has the same shape:

```
2068                                             Pico
(wait for IDLE)
OUT (0Fh),03h        SYNC ------------------>    empties both FIFOs, queues one 01h, says idle
(wait for READY+IDLE)
OUT the 10-byte pre-header ------------------>   (busy after each byte)
IN (0Eh) = 01h  <---- the "pre-load" byte
(wait for READY)                                 "I'm listening" (status F7h)
OUT the body: 'D', length, text, XOR -------->   checks the XOR, runs the command
(wait for READY)                                 queues its answer, then says READY
IN (0Eh) = the answer
[more bytes, if the answer has any]
                                                 finishes, queues the next 01h, says idle (FFh)
```

Let's take each part in turn.

## 3.2 SYNC

`OUT (0Fh),03h` starts every transaction. The Pico drops anything half-done, empties both
FIFOs, puts a single 01h in its transmit FIFO, and goes ready-and-idle. So whatever happened
before, even an earlier program that crashed halfway through a command, a SYNC puts the link
back into a known state.

Two things to watch:

- **Wait for IDLE before you SYNC.** Some answers, notably the channel commands in Chapter 6,
  say READY without IDLE. The Pico is still tidying up behind them. A SYNC sent in that
  moment can be lost along with the pre-header behind it, and you get **T**. Wait for IDLE first,
  and wait up to a second.
- **Wait for READY and IDLE after the SYNC**, as the ROM does, before the first pre-header
  byte.

BREAK uses the same byte. If the user presses BREAK while your program is waiting, send
`OUT (0Fh),03h`, wait for idle, and stop. The Pico abandons the command cleanly. It is listening
for that write even while it's in the middle of sending you a long listing.

## 3.3 The pre-load byte

Between transactions, the Pico's transmit FIFO always holds exactly **one 01h**. The ROM reads
it straight after the tenth pre-header byte, without waiting. If it reads 00h instead, nothing
was there, and that's **Report J**.

Because every SYNC puts a fresh 01h in place, a program that SYNCs first always finds it.

## 3.4 The pre-header

Ten bytes, sent one at a time:

| Byte | Contents | Notes |
|---|---|---|
| 0 | `'B'` (42h) | a command |
| 1 | 0 | 0 = a `SAVE "tpi:..."` command. 1, 2 or 3 = `LOAD`/`VERIFY`/`MERGE "tpi:name"`, which mounts a file. **4, 5 and 6 are printer traffic: never send them.** |
| 2 | FFh | the bank. The Pico ignores it for commands. |
| 3, 4 | first CODE number, low byte first | `SAVE "tpi:..." CODE a,b` sends *a* here; 0 without CODE |
| 5, 6 | second CODE number, low byte first | *b* |
| 7, 8 | length of the command text, low byte first | |
| 9 | XOR of bytes 0–8 | the Pico doesn't check this one, but send it right |

## 3.5 The body

After the pre-load byte, wait for READY, then send:

```
'D' (44h), length low, length high, the text..., XOR
```

The XOR covers everything from the `'D'` to the last character of the text. **The Pico does
check this one:** a wrong XOR gives **Report R**, and the command isn't run.

The text must start with the four characters `tpi:` (in any case). The command word runs up to
the first space, and anything after the space is the argument, with its case kept. The text
must be plain ASCII. Anything that isn't valid text gives Report C.

> **By the way:** from BASIC, the ROM only sends names of 6 to 31 characters as commands. From
> machine code there's no such limit (the length is 16 bits), but keep commands under 256
> bytes and you'll be in the same territory the ROM's own code has been tested in.

## 3.6 The answer: a status byte

After the body, wait for READY and read one byte. For most commands, that byte is a
**status**:

| Status | Report | Error code (for `RST 8`) |
|---|---|---|
| 00h | J Invalid I/O device (nothing there) | 12h |
| 1 | OK | — |
| 2 | R Tape loading error | 1Ah |
| 3 | F Invalid file name | 0Eh |
| 4 | Q Parameter error | 19h |
| 5 | C Nonsense in BASIC | 0Bh |
| 6 | 6 Number too big | 05h |
| 7 | 8 End of file | 07h |
| 8 | A Invalid argument | 09h |
| 9 | 9 STOP statement | 08h |
| 10 | J Invalid I/O device | 12h |
| 11–127 | D BREAK - CONT repeats | 0Ch |
| (RECOVERED bit) | T TS-Pico reset, try again | 1Ch |

The "error code" column is the byte that follows `RST 8` in the ROM. Put it there and BASIC
stops with that report, exactly as if a BASIC command had failed.

## 3.7 The answer: a response function

A first byte of 80h or more isn't a status. It's a **response function**: a request for the 2068
to do something, usually print. Each function carries its own status byte, which becomes the
command's result. The firmware uses these:

| Code | What follows | What the 2068 does |
|---|---|---|
| 81h | status, text, 00h | prints the text (it usually starts with a carriage return) |
| 86h | status, then pages of text. Each page ends in 00h, and the whole thing ends in 03h. | prints each page. At each 00h it waits for a key, waits for READY, and sends the key. `N` ends it. |
| 88h | as 86h, on the lower screen | only for `tpi:fopen` (the "Replace?" question of `SAVE "f:..."`) |

Text inside these is bytes below 80h. A byte of 80h or more ends a string, as 00h does. Keys
go back **in upper case**: the Pico ends a listing only on `N` (78), never on `n`. The ROM also
understands 82h–85h and 87h, but the firmware never sends them. Any other code gives
**Report D**, with the rest of the answer left unread.

At an 86h "Scroll?" prompt, the key does more than yes or no. `N` stops, a digit 1–9 shows that
many lines before the next prompt, `0` shows ten, and anything else shows a full page.

## 3.8 The tail

When the command has finished, the Pico waits until you've read everything it sent. It then
empties its receive FIFO, queues the next 01h pre-load, and says ready-and-idle (FFh). That's
the end of the transaction.

## 3.9 Summary

1. SYNC (`OUT (0Fh),03h`), pre-header, pre-load, body, answer: every command, every time.
2. Wait for IDLE before a SYNC, and for READY before every read.
3. Pre-header byte 1 is 0 for a command. The CODE numbers go in bytes 3–6.
4. The body's XOR is checked: a mistake is Report R.
5. The answer is a status (1 = OK), or a response function (81h/86h) that prints.

---

# Chapter 4: A Machine-Code Toolkit: `picolib.asm`

> **Chapter Preview.** A tour of `picolib.asm`, the small library every example in this book is
> built on: waiting, sending a command, reading an answer, and turning a failure into a BASIC
> report.

## 4.1 Using the library

`picolib.asm` is about 350 bytes of code. `include` it at the end of your program, and define
two words that hold the command's CODE numbers:

```asm
PMR1:   dw 0            ; SAVE "tpi:..." CODE PMR1,PMR2
PMR2:   dw 0
        ...
        include "picolib.asm"
```

It's written for a program that BASIC calls with `USR`, with the HOME ROM paged in and
interrupts on. It doesn't use IX or IY, and it only calls the ROM to print (`RST 10h`).

Every routine that can fail returns with **carry set and an error code in A**. The code is the
byte BASIC's `RST 8` takes: 12h for J, 0Ch for D, 1Ah for R, and so on. When you want to give
up, `JP RAISE` stops the BASIC program with that report.

Here are the routines, with the code. The full file, with its constants, is in `examples`.

## 4.2 Waiting: WAIT_IDLE and WAIT_READY

`WAIT_IDLE` polls for READY and IDLE together, for up to about a second:

```asm
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
```

`WAIT_READY` is the one you'll call most. It waits up to about 20 seconds for READY, the same
patience as the ROM, and watches for BREAK while it waits:

```asm
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
```

Notice what happens on BREAK. We don't just walk away: we tell the Pico with a SYNC, so it
stops too, and the link is ready for the next command.

## 4.3 Sending: TXX and SEND_CMD

`TXX` sends one byte, adds it to a running XOR in D, and pauses about 50 µs. `RXP` is its
mirror: a 75 µs pause, then a read.

```asm
TXX:    out (PORT_DATA),a
        xor d
        ld d,a
        push bc
        ld b,11
.d:     djnz .d
        pop bc
        ret

RXP:    push bc
        ld b,16
.d:     djnz .d
        pop bc
        in a,(PORT_DATA)
        ret
```

`SEND_CMD` sends a whole command: HL points at the text and BC holds its length. It does the
SYNC, the pre-header, the pre-load check, and the body:

```asm
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
```

where `PICO_SYNC` is:

```asm
PICO_SYNC:
        call WAIT_IDLE
        ld a,03h
        out (PORT_STAT),a
        jp WAIT_IDLE
```

When `SEND_CMD` returns with no carry, the command is on its way. Now read the answer with
`GET_REPLY` or `GET_DATA`.

## 4.4 Reading an answer: GET_REPLY

`GET_REPLY` handles the answers the ROM handles: a status, an 81h message or an 86h/88h
listing. Messages are printed with `RST 10h`, so select a channel first. The main screen is
stream 2:

```asm
        ld a,2
        call CHAN_OPEN          ; 1230h in the HOME ROM
```

The routine:

```asm
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
.m1:    call RXP
        and a
        jr z,.done              ; 00h ends the text
        cp 80h
        jr nc,.done             ; so does any byte 80h or over
        rst 10h
        jr .m1
.done:  pop af
        jp MAP_STATUS

.loop:  call RXP                ; 86h: status, then pages of text
        push af
.page:  call RXP
        and a
        jr z,.key               ; 00h: end of a page, the Pico waits for a key
        cp 03h
        jr z,.done              ; 03h: the end
        cp 80h
        jr nc,.done
        rst 10h
        jr .page
.key:   call GETKEY             ; upper case: the Pico stops only on 'N' (78)
        push af
        call WAIT_READY         ; the ROM waits for READY before it sends a key
        jr c,.kfail
        pop af
        out (PORT_DATA),a
        cp 'N'
        jr z,.done              ; N: nothing more comes
        call WAIT_READY         ; the next page is on its way
        jr nc,.page
        pop hl                  ; drop the saved status, keep A
        scf
        ret
.kfail: pop hl
        pop hl
        scf
        ret
```

Two things make this work without a handshake on every character. The Pico queues the first
few bytes of a message *before* it says READY. After that, `RST 10h` is slow enough that the
Pico keeps ahead of it.

An unknown function gets the same treatment as BREAK: a SYNC, so the Pico doesn't sit waiting
for us to read an answer we don't understand.

`GETKEY` waits for a key using the ROM's own keyboard scan, which runs on every interrupt. It
clears bit 5 of FLAGS, then HALTs until the interrupt routine sets it again with a new key in
LAST_K:

```asm
GETKEY: push hl
        ei
        ld hl,FLAGS             ; 5C3Bh
        res 5,(hl)
.w:     halt
        bit 5,(hl)
        jr z,.w
        pop hl
        ld a,(LAST_K)           ; 5C08h
        cp 'a'
        ret c
        cp 'z'+1
        ret nc
        and 0DFh                ; upper case
        ret
```

## 4.5 Reading data: GET_DATA

Some answers aren't for printing: they're data for your program. The channel read command in
Chapter 6 uses this format, and so does the example Pico command in Part 2:

```
status 1, count n (1-255), n bytes, XOR of the n bytes
```

Status 7 means "end of file"; any other status is an error. `GET_DATA` stores the bytes at HL:

```asm
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
```

It returns three ways: **NC and Z** means E bytes arrived; **NC and NZ** means end of file;
**carry** means an error, with its code in A. The XOR is your safety net. Remember that a read
from an empty FIFO gives 00h without complaint, and the checksum is the only thing that
catches it.

## 4.6 From status to report: MAP_STATUS and RAISE

`MAP_STATUS` turns a status byte into our error codes, using the same table the ROM uses:

```asm
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
```

and `RAISE` hands a code to BASIC:

```asm
RAISE:  ld (.code),a
        rst 8
.code:  db 0
```

`RST 8` reads the byte after itself as the report, so we store the code there first. BASIC
then stops with, say, "F Invalid file name", just as if one of its own commands had failed.

## 4.7 Summary

1. `include "picolib.asm"` and define `PMR1` and `PMR2`.
2. `SEND_CMD` (HL = text, BC = length), then `GET_REPLY` for ordinary commands or `GET_DATA`
   for data.
3. Carry means failure, with a BASIC error code in A. `JP RAISE` reports it.
4. BREAK and unknown answers are handled with a SYNC, so the link is always left clean.

---

# Chapter 5: Worked Examples

> **Chapter Preview.** Six small programs: a general command sender, a file loader, a log
> writer, a file counter, a program that reads a data answer, and reading data from BASIC.
> Each one has a BASIC program to drive it. All of them are on `picoex.tap`.

All the examples load at 60000, so start with `CLEAR 59999`. Each one begins with a few
`JP`s and data fields at fixed addresses, so BASIC can `POKE` its inputs and call the right
entry.

To get them onto the 2068, copy `picoex.tap` to the `/TAP` folder of your SD card, then:

```basic
LOAD "tpi:picoex.tap"
LOAD "picocmd" CODE
```

The TS-Pico reads a mounted TAP forward, like a tape. If a `LOAD` can't find an example you've
already passed, `SAVE "tpi:rew"` winds back to the start.

## 5.1 Any command from machine code: `picocmd`

The simplest useful program: it sends the command you give it and reports the result. Its
layout:

| Address | Contents |
|---|---|
| 60000 | `LET r=USR 60000`: run the command; r = 0 for OK, else the report's code |
| 60003 | `RANDOMIZE USR 60003`: run the command; stop with its report if it fails |
| 60006/7 | first CODE number |
| 60008/9 | second CODE number |
| 60010/11 | length of the command |
| 60012… | the command text (up to 128 characters) |

The whole program, apart from the library:

```asm
        org 60000
        jp RUN_CODE             ; 60000
        jp RUN_RAISE            ; 60003
PMR1:   dw 0                    ; 60006
PMR2:   dw 0                    ; 60008
CMDLEN: dw 0                    ; 60010
CMDBUF: ds 128                  ; 60012

RUN:    ld a,2
        call CHAN_OPEN          ; anything the Pico prints goes to the screen
        ld hl,CMDBUF
        ld bc,(CMDLEN)
        call SEND_CMD
        ret c
        jp GET_REPLY

RUN_CODE:
        call RUN
        ld bc,0
        ret nc                  ; OK: 0
        inc a                   ; ERR_NR + 1
        ld c,a
        ret

RUN_RAISE:
        call RUN
        ret nc
        jp RAISE

        include "picolib.asm"
```

`RUN_CODE` returns the error code plus one. That number is the report's position in the list
`0123456789ABCD...`, so BASIC can show the letter. Here's a driver:

```basic
10 CLEAR 59999: LOAD "picocmd" CODE
20 LET a=0: LET b=0
30 LET c$="tpi:path": GO SUB 1000
40 LET c$="tpi:dir": GO SUB 1000
50 LET c$="tpi:nosuch": GO SUB 1000
60 STOP
1000 REM send c$ with CODE a,b
1010 POKE 60006,a-256*INT (a/256): POKE 60007,INT (a/256)
1020 POKE 60008,b-256*INT (b/256): POKE 60009,INT (b/256)
1030 POKE 60010,LEN c$: POKE 60011,0
1040 FOR i=1 TO LEN c$: POKE 60011+i,CODE c$(i): NEXT i
1050 LET r=USR 60000
1060 IF r THEN PRINT "Report ";"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"(r+1)
1070 RETURN
```

What you should see: the current folder (`tpi:path` always prints), then the folder listing.
A long listing stops at "Scroll?". Then comes `Report C` for the command that doesn't exist.
Change line 1050 to `RANDOMIZE USR 60003` and the program stops with `C Nonsense in BASIC`
instead.

> **Remember:** BREAK works while the program is waiting for the Pico (in `WAIT_READY`): you
> get Report D, and the next command works normally. At a "Scroll?" prompt the program is
> waiting for *you*, and `GETKEY` doesn't watch for BREAK, so press **N** to stop a listing.

## 5.2 Loading any file into memory: `loadfile`

`LOAD "" CODE` needs a tape header. With the channel commands (Chapter 6) you can read any
file, byte for byte: a screen dump, a data file made on a PC, a font. `loadfile` opens the file
as a binary stream, reads it 255 bytes at a time, and closes it.

| Address | Contents |
|---|---|
| 60000 | `LET n=USR 60000`: n = bytes read |
| 60003/4 | where to put the file (default 32768) |
| 60005/6 | the most to read (default 16384) |
| 60007 | length of the file name |
| 60008… | the name (up to 64 characters), relative to the current folder or starting with `/` |

The heart of it:

```asm
STREAM  equ 200                 ; the Pico's key for this channel: any 0-255
                                ; that BASIC isn't using for OPEN #
OPEN_T: db "tpi:chopen rb "     ; rb = read, binary (no text translation)
OPEN_L  equ $-OPEN_T
RD_T:   db "tpi:chrd"
RD_L    equ $-RD_T
CL_T:   db "tpi:chclose"
CL_L    equ $-CL_T

LOAD:   ld hl,OPEN_T            ; build "tpi:chopen rb <name>"
        ld de,CMDBUF
        ld bc,OPEN_L
        ldir
        ld a,(NAMELEN)
        ld c,a
        ld b,0
        or a
        jr z,.named             ; no name: the Pico answers F
        ld hl,NAME
        ldir
.named: ld a,(NAMELEN)
        add a,OPEN_L
        ld c,a                  ; BC = length of the command
        ld b,0
        ld hl,STREAM
        ld (PMR1),hl            ; CODE stream, 0: a plain stream, not records
        ld hl,0
        ld (PMR2),hl
        ld (TOTAL),hl
        ld hl,CMDBUF
        call SEND_CMD
        call nc,GET_REPLY
        jp c,RAISE

.next:  ld hl,(MAXLEN)          ; room left
        ld de,(TOTAL)
        and a
        sbc hl,de
        jr z,.full
        ld a,h
        or a
        ld a,l
        jr z,.ask
        ld a,255                ; at most 255 bytes a read
.ask:   ld l,a
        ld h,0
        ld (PMR2),hl            ; CODE stream, how many bytes
        ld hl,RD_T
        ld bc,RD_L
        call SEND_CMD
        jr c,.fail
        ld hl,(DEST)
        ld de,(TOTAL)
        add hl,de
        call GET_DATA           ; NC Z: E bytes arrived
        jr c,.fail
        jr nz,.full             ; end of the file
        ld hl,(TOTAL)
        ld d,0
        add hl,de
        ld (TOTAL),hl
        jr .next

.full:  call CLOSE
        jp c,RAISE
        ld bc,(TOTAL)
        ret

.fail:  push af                 ; close the channel, then report the error
        call CLOSE
        pop af
        jp RAISE
```

Notice `.fail`: whatever goes wrong, we close the channel before we report it. An open
channel doesn't hurt the Pico, but a tidy program leaves nothing behind.

A driver that loads a screen dump made on a PC (a 6912-byte `.scr` file) straight onto the
screen:

```basic
10 CLEAR 59999: LOAD "loadfile" CODE
20 LET f$="/SCREENS/castle.scr"
30 POKE 60003,0: POKE 60004,64: REM to 16384
40 POKE 60005,0: POKE 60006,27: REM at most 6912 bytes
50 POKE 60007,LEN f$
60 FOR i=1 TO LEN f$: POKE 60007+i,CODE f$(i): NEXT i
70 LET n=USR 60000
80 PAUSE 0: PRINT n;" bytes"
```

A file that isn't there stops the program with **F Invalid file name**. A byte lost on the way
gives **R Tape loading error**.

## 5.3 Adding to a log file: `logline`

A game that remembers its high scores, or a program that keeps a diary, needs to add a line to a
text file. `logline` opens the file for appending in text mode, sends the line with
`tpi:chwr`, adds a carriage return (which text mode turns into a newline on the card), and
closes it. If the file isn't there, it's made.

| Address | Contents |
|---|---|
| 60000 | `RANDOMIZE USR 60000` |
| 60003 | length of the file name |
| 60004… | the name (up to 32 characters) |
| 60036 | length of the line |
| 60037… | the line (up to 200 characters) |

`tpi:chwr` sends its bytes as hexadecimal, two digits a byte, because the command text must be
plain text. The library's `HEX` routine does the conversion. Here's the routine that sends B
bytes from HL:

```asm
WR_T:   db "tpi:chwr "
WR_L    equ $-WR_T

WRITE:  push hl
        ld hl,WR_T
        ld de,CMDBUF
        ld c,WR_L
        push bc
        ld b,0
        ldir                    ; "tpi:chwr "
        pop bc
        pop hl
        push bc
.hex:   ld a,(hl)
        inc hl
        call HEX                ; two hex digits at DE
        djnz .hex
        pop bc
        push hl
        ld a,b
        add a,a                 ; 2 digits a byte
        add a,WR_L
        ld c,a
        ld b,0
        call SEND_REPLY         ; send CMDBUF, read the status
        pop hl
        ret
```

The main routine sends the line 64 bytes at a time, then a single 0Dh. A driver:

```basic
10 CLEAR 59999: LOAD "logline" CODE
20 LET f$="scores.txt"
30 INPUT "Name? ";n$: INPUT "Score? ";s
40 LET l$=n$+" "+STR$ s
50 POKE 60003,LEN f$
60 FOR i=1 TO LEN f$: POKE 60003+i,CODE f$(i): NEXT i
70 POKE 60036,LEN l$
80 FOR i=1 TO LEN l$: POKE 60036+i,CODE l$(i): NEXT i
90 RANDOMIZE USR 60000
100 GO TO 30
```

Put the file on a PC and you'll find one line per score. You can read it back with
`OPEN #4,"f:scores.txt"` and `INPUT #4`.

> **Note:** in a channel, the byte 23 (17h) is always the start of a TAB (a seek), even in
> binary mode. Text doesn't contain it, but a block of machine code or a screen might. **To
> write binary data, use an ordinary `SAVE ... CODE`**, or `SAVE "f:..." CODE`, not
> `tpi:chwr`.

## 5.4 Counting files: `countdir`

The channel commands can open a folder listing as if it were a file (the `d:` device, as in
`OPEN #4,"d:*.tap"`). A TAB 0 on that channel asks for the number of names, and the next read
returns it as digits and a carriage return. `countdir` uses that trick to count the files that
match a pattern, without reading the whole listing:

```asm
OPEN_T: db "tpi:chopen r d:"
TAB0_T: db "tpi:chwr 170000"    ; 23, 0, 0: TAB 0
```

After the TAB, one `tpi:chrd` returns something like `12` and a CR, which the program turns
into a number for USR:

```basic
10 CLEAR 59999: LOAD "countdir" CODE
20 LET p$="*.tap"
30 POKE 60003,LEN p$
40 FOR i=1 TO LEN p$: POKE 60003+i,CODE p$(i): NEXT i
50 PRINT USR 60000;" TAP files here"
```

An empty pattern counts everything in the current folder. `GAMES/*.tap` counts in a
subfolder, and a folder that isn't there gives **F**.

## 5.5 Reading a data answer: `fact`

Part 2 builds a new Pico command, `tpi:.fact`, that works out *n*! (n factorial) and sends the
digits back as data, in the same format as `tpi:chrd`. The 2068 side is short, because
`GET_DATA` does the work:

```asm
FACT:   ld a,(N)
        ld (PMR1),a             ; SAVE "tpi:.fact" CODE n,0
        ld a,2
        call CHAN_OPEN
        ld hl,CMD_T
        ld bc,CMD_L
        call SEND_CMD
        jp c,RAISE
        ld hl,DIGITS
        call GET_DATA
        jp c,RAISE              ; n too big: Report 6
        ld hl,DIGITS
        ld b,e
.pr:    ld a,(hl)
        inc hl
        rst 10h
        djnz .pr
        ld a,0Dh
        rst 10h
        ret
```

```basic
10 CLEAR 59999: LOAD "fact" CODE
20 FOR n=0 TO 33
30 PRINT n;"! = ";: POKE 60003,n: RANDOMIZE USR 60000
40 NEXT n
```

Numbers up to 32! (36 digits) print in full, far beyond what BASIC's arithmetic can hold. At
33 the Pico answers with status 6, and the program stops with **6 Number too big**. (You'll
need the Pico side from Chapter 11 installed first.)

## 5.6 Reading a data answer from BASIC

You don't need machine code to read data from the Pico. When BASIC sends `SAVE "tpi:.fact"`,
the ROM reads the status byte, sees 1 (OK), and carries on with the next statement. The rest
of the answer is still waiting in the Pico, and `IN 14` reads it:

```basic
10 INPUT "n? ";n
20 SAVE "tpi:.fact" CODE n,0
30 LET c=IN 14
40 FOR i=1 TO c: PRINT CHR$ IN 14;: NEXT i
50 LET x=IN 14: PRINT
60 GO TO 10
```

BASIC is slow enough that the Pico always keeps up. If the program leaves bytes unread, no
harm is done: the next command's SYNC clears them.

## 5.7 Summary

1. Fixed data fields at known addresses make machine code easy to drive from BASIC.
2. `picocmd` sends anything. `loadfile` reads any file. `logline` appends text. `countdir`
   counts. `fact` reads data.
3. Close channels on the way out, even after an error.
4. BASIC can read a data answer with `IN 14` after the `SAVE "tpi:..."`.

---

# Chapter 6: Files as Streams: the Channel Commands

> **Chapter Preview.** The four commands behind `OPEN #`, `PRINT #`, `INPUT #` and `CLOSE #`,
> and how your machine code can use them directly.

## 6.1 The four commands

| Command text | First CODE | Second CODE | Answer |
|---|---|---|---|
| `tpi:chopen <mode> <path>` | stream (0–255) | record length (0 = a plain stream, 1–254) | a status |
| `tpi:chopen r d:<pattern>` | stream | 0 | a status; the channel reads a folder listing |
| `tpi:chwr <hex>` | stream | 0 | a status |
| `tpi:chrd` | stream | the most bytes you want (1–255; 0 means 255) | a **data answer**: `1, n, bytes, XOR`, or 7 at the end of the file |
| `tpi:chclose` | stream | 0 | a status (closing a stream that isn't open is fine) |

**The stream number is just a label** the Pico files the channel under. Any number from 0 to
255 will do. If your program runs alongside BASIC programs that use `OPEN #`,
use numbers above 15 so you don't close one of theirs by accident. The examples use 200–202.

All four answer "READY but not IDLE" (F7h), because the ROM's channel driver sends its next
command at once. That's why `PICO_SYNC` waits for IDLE first.

## 6.2 Modes

| Mode | Meaning |
|---|---|
| `r` | read; the file must exist (**F** if not) |
| `w` | write; makes the file, or empties it |
| `a` | append; makes the file if needed, then writes at its end |
| `u` | update: read and write |

Add `b` for **binary** (`rb`, `wb`, `ab`, `ub`). Without it, a channel is in **text** mode:

- **writing**, a carriage return (13) becomes a newline in the file, and the 2068's keyword
  tokens are spelled out as text;
- **reading**, newlines become carriage returns, so `INPUT #` sees lines.

Binary mode passes the bytes through unchanged, with one exception: in a write, **byte 23 is
always the start of a TAB**, in either mode (next section). Paths work as they do everywhere
else: relative to the current folder, or from the card's `/TAP` folder if they start with `/`.

## 6.3 TAB: seeking

A write of the three bytes `23, n low, n high` moves the channel to byte *n* of the file (1 is
the first byte). This is how `PRINT #s;TAB n;` works, and it's how your machine code
seeks: `tpi:chwr 17` followed by the two bytes in hex.

**TAB 0** (`tpi:chwr 170000`) is a question. The next `tpi:chrd` answers it with a count, as
text ending in a carriage return:

- for a folder listing, the number of names (as `countdir` uses);
- for a record file, the number of records;
- for any other file, its length in bytes.

## 6.4 Record files

Open a file with a record length in the second CODE number (1 to 254), and it's divided into
records of that size. TAB *n* moves to record *n*. Each `tpi:chrd` returns one record plus a
carriage return, padded with spaces in text mode or zeros in binary mode. The User Manual's
address-book example in Chapter 6 shows record files from BASIC. The commands underneath are
the same.

## 6.5 Folder listings: `d:`

`tpi:chopen r d:<pattern>` opens a read-only channel over the names that `CAT "<pattern>"`
would list, one per line, with a `/` after each folder name. It's read in text mode, so each
`tpi:chrd` gives you lines ending in carriage returns. It must be opened `r` with no record
length (**Q** otherwise). A folder that isn't there gives **F**.

## 6.6 Summary

1. `chopen`, `chwr` (hex), `chrd` (data answer), `chclose`: the stream number is just a label.
2. Modes `r w a u`, plus `b` for binary. Text mode translates line ends and keywords.
3. Byte 23 in a write is always a TAB: don't write raw binary containing it.
4. TAB 0 then a read gives you a count; `d:` lists a folder.

---

# Chapter 7: Other Commands, and What Not to Send

> **Chapter Preview.** Which of the User Manual's commands make sense from machine code, a few
> that only exist inside the ROM, and the pre-header values to stay away from.

## 7.1 Everything in the User Manual

Every `SAVE "tpi:..."` command in the User Manual can be sent with `SEND_CMD` and
`GET_REPLY`. Put the CODE numbers in `PMR1` and `PMR2`, exactly as you'd write them after
`CODE`. The ones a program is most likely to want:

| Command | Useful for |
|---|---|
| `tpi:cd <folder>`, `tpi:cd -` | moving around (see the User Manual) |
| `tpi:path` | prints the current folder |
| `tpi:dir [pattern]` | prints a listing (86h, with "Scroll?") |
| `tpi:copy a b`, `tpi:ren a b`, `tpi:erase x` | file handling, as MOVE, ERASE and FORMAT use |
| `tpi:verbose` | turns the Pico's messages on or off |

Remember that most commands only print a message when VERBOSE is on. With it off, you get a
bare status. `GET_REPLY` handles both.

## 7.2 Mounting a file from machine code

`LOAD "tpi:game.tap"` mounts a file. On the wire it's an ordinary command, except that
pre-header **byte 1 is 1** (LOAD) instead of 0, and the text is `tpi:` followed by the file
name. To do this from machine code, copy `SEND_CMD` and change the second `TXX` to send 1.
The answer is a message or status, as for any command. (We haven't tested this one from
machine code; it follows the firmware's dispatcher.)

## 7.3 Commands that never reach the Pico

`tpi:tape`, `tpi:sdcard`, `tpi:picopt` and `tpi:ts2040` look like commands, but the **ROM**
handles them: they just set bits in the TPMODE system variable at 24027 (5DDBh). Sent to the
Pico, they're "Unrecognized command" (**C**). From machine code, set the bits yourself:

| Bit | Meaning | Set by |
|---|---|---|
| 1 | LOAD and SAVE go to the TS-Pico | `tpi:sdcard` (bit set), `tpi:tape` (bit clear) |
| 0 | LPRINT/LLIST/COPY go to the TS-Pico | `tpi:picopt` (bit set), `tpi:ts2040` (bit clear) |

```asm
        ld hl,5DDBh
        set 1,(hl)              ; the same as SAVE "tpi:sdcard"
```

## 7.4 What not to send

- **Pre-header byte 1 of 4, 5 or 6.** Those are the printer (COPY and LPRINT) and aren't
  commands.
- **A first byte other than `'B'`.** 00h and FFh are the ROM's LOAD and SAVE blocks, `'A'` is
  an old leftover, and anything else is thrown away *without* the pre-load byte being put back.
  If you then send a command without a SYNC, you get J.
- **ZX48 mode.** After `tpi:zx48` the Pico speaks a different, Spectrum-style protocol with no
  status port. The only way back from the 2068 is `OUT 14,14`. Don't send commands while it's
  in that mode.

## 7.5 Summary

1. Any User Manual command works through `SEND_CMD` and `GET_REPLY`.
2. Mounting is byte 1 = 1 with the file name as the text.
3. `tpi:tape` and friends are ROM-only: set TPMODE (24027) yourself.
4. Stick to `'B'` blocks with byte 1 = 0 (or 1 to mount).

---

# Chapter 8: Using the ROM's Pico BIOS

> **Chapter Preview.** The small table of routines the ROM provides for the TS-Pico, how a RAM
> program reaches them across the HOME/EXROM bank switch, and the two dangers that come with
> it: interrupts and errors.

## 8.1 The table

The EXROM holds a jump table at 1840h, the same in every ROM from 1.1 to 2.2:

| Address | Name | What it does |
|---|---|---|
| 1840h | G_MODE | BC = TPMODE (its low four bits). AF kept. |
| 1842h | S_MODE | TPMODE := A AND 0Fh. AF kept. |
| 1844h | G_VERS | BC = the interface version: 0015h on 1.1, 0021h on 2.1, **0022h on 2.2** |
| 1846h | TX_A | `OUT (0Eh),A`. No wait, no BREAK check. |
| 1848h | RX_A | `IN A,(0Eh)`: Z if the byte is 0. No wait. |
| 184Ah | C_END | waits for READY, reads the answer and runs the response functions (printing, "Scroll?"). NC = OK; C = failed: A = status−1, or 0Ch (BREAK), 1Ch (the Pico reset the transaction), or 09h on a timeout. See 8.4. |
| 184Ch | WF_NPH | waits for READY, up to ~20 s. NC = ready. C with A = 02h (timeout), 0Ch (BREAK: the Pico has been told) or 1Ch (the Pico reset the transaction). Never raises a report. |

Other EXROM addresses that are fixed and useful: `SYNC_WRITE` at 2300h (SYNC, wait,
then `OUT (0Eh),A` with the first byte), `SYNC_WAIT` at 230Eh, and 1BF3h, which takes A =
status−1 and raises the matching report. **Don't call 2003h, 2006h or 2027h–203Ch**: they're
padding that jumps to itself, and the machine hangs.

## 8.2 Getting there from RAM

A USR program runs with the HOME ROM paged in. The BIOS is in the EXROM at the same addresses,
so you have to switch banks to call it. HOME has a routine for that at **03FCh**. Put the EXROM
address in HL and call it: A, F, BC and DE reach the routine, and its A, F, BC, DE and HL come
back to you. **IX is not kept.** If the routine needs an HL argument, store it at 5DCDh first.

**Interrupts must be off.** The 2068 switches banks in two steps, and an interrupt between them
can land in an empty memory bank and wipe memory. Put `DI` before the call and `EI` after it.

Here's `bios.asm`, which reads the version and mode and sets the mode:

```asm
THUNK   equ 03FCh
G_MODE  equ 1840h               ; BC = the mode bits
S_MODE  equ 1842h               ; mode bits := A AND 0Fh
G_VERS  equ 1844h               ; BC = the interface version

        org 60000
        jp VERS                 ; 60000
        jp MODE                 ; 60003
        jp SETM                 ; 60006
M:      db 0                    ; 60009

VERS:   ld hl,G_VERS
        jr BIOS
MODE:   ld hl,G_MODE
        jr BIOS
SETM:   ld a,(M)
        ld hl,S_MODE
BIOS:   di                      ; the bank switch is not interrupt-safe
        call THUNK
        ei
        ret                     ; BC comes back to USR
```

```basic
10 CLEAR 59999: LOAD "bios" CODE
20 PRINT "Interface version ";USR 60000
30 PRINT "Mode bits ";USR 60003
40 POKE 60009,2: RANDOMIZE USR 60006: REM the same as SAVE "tpi:sdcard"
```

You should see version 33.

## 8.3 The danger: errors inside the EXROM

The bank-switching routine keeps its own small stack at (65CEh), four bytes per call. If a
report is raised while you're inside the EXROM, BASIC unwinds the Z80 stack but not that one,
so each error leaves it four bytes short. After about sixteen errors it overwrites the
bank-switching code itself, and the machine crashes.

G_VERS, G_MODE, S_MODE, TX_A, RX_A and WF_NPH never raise a report, so they're safe to call as
above. **C_END is not safe on its own**: it runs the response functions, which can raise D
(BREAK at "Scroll?") or T from inside.

## 8.4 C_END, and a trap for errors

C_END's failure codes are ready for `STATUS_TO_REPORT` (1BF3h): A = status−1 for an error
status, 09h if the Pico never answered (reported as J, as the ROM's own commands do), 0Ch for
BREAK and 1Ch if the Pico reset the transaction. (ROM 1.1 returned 02h for a timeout,
the same as status 3, Report F; there, call WF_NPH first.)

To call C_END safely, catch any report on the way out. BASIC finds its error handler through
ERR_SP (5C3Dh). Point ERR_SP at a trap of your own for the length of the call, and the trap
can put the bank stack right before passing the error on. The ROM's disk commands do exactly
this. Here's the same idea for a RAM program. It's modelled on the ROM's code, but it is
**untested**, so try it carefully:

```asm
BANK_SP equ 65CEh
ERR_SP  equ 5C3Dh

; XCALL -- call the EXROM routine at HL, catching any report it raises.
XCALL:  push hl
        ld hl,(ERR_SP)
        ex (sp),hl              ; stack: old ERR_SP
        push hl
        ld hl,(BANK_SP)
        ex (sp),hl              ; stack: the bank stack pointer, as it is now
        push hl
        ld hl,XTRAP
        ex (sp),hl              ; stack: the trap          HL = target again
        ld (ERR_SP),sp
        di
        call 03FCh
        ei
        inc sp                  ; no error: drop the trap and the bank value
        inc sp
        inc sp
        inc sp
        ex (sp),hl              ; HL = old ERR_SP; the result's HL on the stack
        ld (ERR_SP),hl
        pop hl
        ret

XTRAP:  pop hl                  ; a report: RST 8 has returned here
        ld (BANK_SP),hl         ; put the bank stack back
        pop hl
        ld (ERR_SP),hl
        ld sp,hl
        ei
        ret                     ; on to BASIC's own error handling
```

Honestly, it's simpler not to need this. `GET_REPLY` in Chapter 4 does everything C_END does,
in RAM, with no bank switching at all.

## 8.5 Summary

1. The BIOS table at EXROM 1840h: mode, version, raw byte I/O, wait, and C_END.
2. Reach it from RAM through HOME 03FCh, with HL = the address, between `DI` and `EI`.
3. IX isn't kept across the call.
4. A report raised inside the EXROM leaks bank stack. C_END can raise one, so trap ERR_SP
   around it, or use `GET_REPLY` instead.

---

# Chapter 9: Rules of the Road for Z80 Programs

> **Chapter Preview.** A checklist to keep beside you.

1. **Firmware 2.0 or later.** The 1.1 firmware doesn't know SYNC, and a SYNC makes
   it lose track of the command.
2. **SYNC first, every time**, and wait for IDLE before the SYNC.
3. **Wait for READY after every OUT**, before you read. Every OUT makes the Pico busy.
4. **Never `OTIR` or `INIR`.** About 50 µs a byte out, 75 µs a byte in, and no gap longer than
   a second in the middle of a command.
5. **Check the XOR** on data answers. An empty FIFO reads 00h silently.
6. **Keys go back in upper case.** The Pico ends a listing only on `N`.
7. **Handle BREAK with a SYNC** so the Pico stops too.
8. **Close your channels**, even when something fails.
9. **Don't write byte 23 through a channel** unless you mean a TAB.
10. **`DI` around every bank switch**, and don't let a report escape from the EXROM without a
    trap.
11. **Stay out of ZX48 mode** with this protocol; `OUT 14,14` leaves it.
12. **If the Pico says T** (RECOVERED), it has already reset the transaction: just try again.

---

# Part 2: Programming the TS-Pico

# Chapter 10: Inside the Firmware

> **Chapter Preview.** How the firmware is organised, what happens between the 2068's last
> byte and the Pico's answer, and the one rule every command must follow.

## 10.1 The pieces

The TS-Pico runs **MicroPython** on its RP2040. The firmware is Python, "frozen" into the UF2
file you flash, plus two PIO state machines that watch the 2068's bus:

| File (in `src/`) | What it does |
|---|---|
| `main.py` | starts everything; chooses the development override if there is one (10.4) |
| `TS/tspico.py` | the main loop, the command dispatcher, every `tpi:` command, the helpers |
| `TS/tspico_io.py` | the PIO program for the two ports, and the low-level FIFO routines |
| `TS/channels.py`, `TS/catalog.py`, `TS/native.py` | the channel, listing and `f:` file logic: plain Python you can test on a PC |
| `TS/extcmd.py` | external commands: the easy place to add your own |
| `test/` | host tests, which run on a PC with no hardware, and on-hardware harnesses |

The port interface is a PIO program called `TS_IO_DUAL`. It passes bytes between the 2068 and
two four-byte FIFOs, and it keeps the status byte in a PIO register. That register is how
Python says READY: `MQ_READY()` sets it. The PIO clears it on every OUT from the 2068 (the
auto-busy of section 2.3).

## 10.2 From pre-header to answer

The main loop captures the ten pre-header bytes. For a `'B'` block that isn't printer
traffic, it calls `PROCESS_CMD`, which:

1. says "mid" (F7h) and captures the body, giving up after a second of silence;
2. checks the body's XOR (Report R if it's wrong) and decodes the text (Report C if it isn't
   text);
3. for byte 1 = 0, looks up the command word, up to the first space and in upper case, in
   **`SA_funct`**, the built-in table, and then in **`EXT_SA_FUNCT`**, the external table. It
   calls the handler it finds, or answers "Unrecognized command" (C);
4. **runs the tail**, whatever happened: it waits for the 2068 to read everything, empties the
   receive FIFO, queues the next 01h pre-load, and says idle.

A handler that raises an exception gets Report J, sent by the dispatcher, and the tail still
runs. A BREAK (the 2068's SYNC) while the handler is sending raises `CmdAbort`, which empties
both FIFOs. Again the tail runs.

## 10.3 The one rule

> **A handler gives exactly one answer, and never writes the 01h pre-load.**

One answer means one status byte, or one response function with its data, or one data answer
in a format your 2068 code expects. **Not zero:** the 2068 waits, then gives J. **Not two:**
the second answer's bytes sit in the FIFO and are read as part of the next command, which
usually shows up as Report R one command later. **And no pre-load:** the tail writes it. A
second 01h is an orphan byte with the same effect.

Because a mistake shows up one command *later*, these bugs are confusing to chase. Test for
them (Chapter 15).

## 10.4 Two development overrides

You don't have to rebuild the UF2 to try things:

- **`/dev_extcmd.py`** on the Pico's flash replaces the built-in `TS/extcmd.py`. This is where
  new commands start (Chapter 11).
- **`/dev_tspico.py`** (or `.mpy`) replaces the whole of `TS/tspico.py`. Delete it to go back.

> **Note:** the repository keeps `src/dev_tspico.py` and `src/dev_extcmd.py` identical to
> `src/TS/tspico.py` and `src/TS/extcmd.py`. A CI test (`dev_sync_hosttest.py`) fails when
> they drift, so the copy you deploy is always the current firmware. CI also builds
> `dev_tspico.mpy`, which loads faster than the `.py`.

## 10.5 Summary

1. MicroPython, frozen into the UF2; a PIO program runs the ports.
2. `PROCESS_CMD` captures, checks, dispatches (built-in table first), and always runs the tail.
3. Exactly one answer; never the pre-load.
4. `/dev_extcmd.py` and `/dev_tspico.py` let you experiment without a rebuild.

---

# Chapter 11: Your First Pico Command

> **Chapter Preview.** Three external commands, from "hello" to reading the SD card, installed
> without rebuilding the firmware.

## 11.1 The external-command file

External commands live in a file with a dictionary called `EXT_SA_FUNCT`. The dictionary maps
each command word, **in upper case with its `TPI:`**, to a handler:

```python
EXT_SA_FUNCT = {
    "TPI:.HELLO": HELLO,
    "TPI:.FACT": FACT,
    "TPI:.LINES": LINES,
}
```

By convention, external commands start with a dot, which keeps them clear of the built-in
names. Each handler is called as:

```python
def HANDLER(MQ, TSP, pre, cmd):
```

| Argument | What it is |
|---|---|
| `MQ` | the port state machine *at the time of the call*. Prefer the helpers (below): after SD card work this one is stale. |
| `TSP` | the firmware's settings object: `TSP.cur_path` (the current folder, as a real path such as `/sd/TAP/GAMES`), `TSP.VERBOSE`, `TSP.f_name` (the mounted file), and so on |
| `pre` | the ten pre-header bytes |
| `cmd` | `"D.."` + the command text. `cmd[7:]` is everything after `tpi:`. |

## 11.2 The helpers

Your handler talks to the 2068 through the firmware's own helpers. Import the *module*, so you
always use the live copy, and prefer `dev_tspico` when there is one, because that's the module
running:

```python
try:
    import dev_tspico as tp
except ImportError:
    import TS.tspico as tp
```

Define the status codes you use yourself, too:

```python
OK = 1                  # 0 OK
F_BAD_NAME = 3          # F Invalid file name
NUM_TOO_BIG = 6         # 6 Number too big
```

`tspico.py` has names for them (`_1_OK`, `_3_F_Invalid_file`, …), but they're `const()`s
whose names start with an underscore. MicroPython builds those into `tspico` itself and never
stores them on the module, so `tp._1_OK` works on a PC and fails on the Pico. (That's how the
first version of `.fact` came to answer J instead of 6.)

| Helper | Use |
|---|---|
| `tp.PARAMS(pre)` | `(a, b)`: the two CODE numbers |
| `tp.getArgs(cmd)` | the text after the command word, case kept |
| `tp.SEND_MSG(msg, msg1, st, force)` | one answer: a message (81h) when VERBOSE is on or `force` is True, otherwise the bare status `st` |
| `tp.SEND_MSG2(text, st)` | one answer: scrolling text (86h) with "Scroll?" prompts for long text |
| `tp.CMD_PUT(b)` | queue one byte of your own answer. It waits while the FIFO is full, and turns a BREAK into `CmdAbort`. |
| `tp.MQ_READY()` | say READY and IDLE (FFh) |
| `tp.CH_READY()` | say READY but not IDLE (F7h), for answers the 2068 follows up at once |
| `tp.SD_CALL(fn, *args)` | run `fn` with the SD card active, and give the bus back afterwards |
| (your own constants) | the status codes: define `OK = 1`, `F_BAD_NAME = 3` and so on in your file (see below) |

## 11.3 Hello

```python
def HELLO(MQ, TSP, pre, cmd):
    """A message answer: function 81h, printed by the ROM."""
    tp.SEND_MSG("Hello from the TS-Pico!", "", OK, True)
```

That's the whole command: `SEND_MSG` with `force=True` is one complete answer. From the 2068:

```basic
SAVE "tpi:.hello"
```

and you'll see:

```
Hello from the TS-Pico!
```

## 11.4 A data answer: `.fact`

```python
def FACT(MQ, TSP, pre, cmd):
    """A data answer the Z80 reads itself: 1, n, n bytes, XOR of the bytes."""
    n, _ = tp.PARAMS(pre)
    if n > 32:                                  # 33! has 37 digits: keep it short
        tp.CMD_PUT(NUM_TOO_BIG)                 # Report 6 Number too big
        tp.MQ_READY()
        return
    digits = str(math.factorial(n)).encode()
    x = 0
    for b in digits:
        x ^= b
    tp.CMD_PUT(1)                               # status: data follows
    tp.CMD_PUT(len(digits))                     # the count
    tp.MQ_READY()                               # data in TX first, then READY
    for b in digits:
        tp.CMD_PUT(b)                           # waits while TX is full
    tp.CMD_PUT(x)
```

Three things to notice:

1. **The error is a plain status.** Status 6 makes the ROM (or `GET_DATA`) report "6 Number too
   big". There's no need to invent codes of your own.
2. **Data first, then READY.** We queue the status and the count, *then* say READY, then send
   the digits. If we said READY first, the 2068 could read an empty FIFO and get 00h.
3. **The format matches `tpi:chrd`**, so the 2068's `GET_DATA` reads it, and so does BASIC
   (section 5.6). Choosing a format your client already knows saves writing new 2068 code.

## 11.5 Reading the SD card: `.lines`

```python
def LINES(MQ, TSP, pre, cmd):
    """SD card work, then a message: how many lines a text file has."""
    name = tp.getArgs(cmd).strip()
    real = catalog.resolve(TSP.cur_path, name) if name else None
    if real is None:
        tp.SEND_MSG("Usage: tpi:.lines <file>", "", F_BAD_NAME)
        return

    def count():                                # runs with the SD card active
        n = 0
        with open(real, "rb") as f:
            while True:
                block = f.read(512)
                if not block:
                    break
                n += block.count(b"\n")
        return n

    n = tp.SD_CALL(count)                       # gives the bus back afterwards
    if isinstance(n, tuple):                    # SD_CALL's (message, status)
        tp.SEND_MSG("Can't read " + name, "", n[1])
        return
    tp.SEND_MSG("%s: %d lines" % (name, n), "", OK, True)
```

The SD card shares pins with the 2068's data bus, so the card and the ports can't be active at
the same time. **Always use `SD_CALL`** for SD work. It switches the pins to the card, runs
your function, and switches them back, even if the function fails. An `OSError` comes back as
`("SD card error", 3)`. Do all your SD work first, and only then queue the answer and say
READY.

`catalog.resolve` turns what the user typed into a real path. It follows the same rules as
every other command: relative to the current folder, `/` for the top of `/TAP`, and no
climbing above it.

## 11.6 Installing it

The complete file is `examples/dev_extcmd.py`. To install it:

1. **Switch the TS-2068 off.** The Pico runs from USB power alone.
2. Connect the Pico to your computer with a USB cable.
3. Copy the file to the root of the Pico's flash as `/dev_extcmd.py`, with Thonny, or from the
   firmware repository:

   ```bash
   python3 tools/pico-serial.py break
   ```

   ```bash
   python3 tools/pico-serial.py put docs/manual/examples/dev_extcmd.py /dev_extcmd.py
   ```

   ```bash
   python3 tools/pico-serial.py softreset
   ```

4. Unplug USB, reseat the SD card, and switch the 2068 on.

Check it's loaded with `SAVE "tpi:help"`: the end of the help lists "External commands loaded
are:" with your three names. To go back to the built-in commands, delete `/dev_extcmd.py` from
the flash.

## 11.7 Summary

1. `EXT_SA_FUNCT` maps `"TPI:.NAME"` to `handler(MQ, TSP, pre, cmd)`.
2. Import the helpers module (`dev_tspico` or `TS.tspico`) and use `CMD_PUT`, `SEND_MSG`,
   `MQ_READY` and `SD_CALL`.
3. One answer: a message, a status, or data (data first, then READY).
4. SD card work goes inside `SD_CALL`, before the answer.
5. Install as `/dev_extcmd.py` with the 2068 switched off.

---

# Chapter 12: A Cookbook of Answers

> **Chapter Preview.** Every kind of answer a command can give, the firmware call that makes
> it, and what the 2068 does with it.

## 12.1 A bare status

```python
tp.SEND_MSG("Why it failed", "", F_BAD_NAME)    # a message only if VERBOSE
```

or, when the message would never be shown:

```python
tp.CMD_PUT(OK)
tp.MQ_READY()
```

The ROM reports the status (Appendix A). For a command that runs in the middle of a BASIC
statement, as the channel commands do, use `tp.CH_REPLY(st)`. It never prints (printing
would move the ROM's current channel to the screen), and it says READY without IDLE.

## 12.2 A one-line message (81h)

```python
tp.SEND_MSG("First line", "Second line", OK, True)
```

The ROM prints a carriage return, the first line, a carriage return, then the second. Keep
the text to plain ASCII below 128. A byte of 128 or more ends the message early. The control
codes 16–23 (INK, PAPER, AT, TAB…) eat the bytes that follow them.

## 12.3 Scrolling text (86h)

```python
tp.SEND_MSG2("\r".join(lines), OK)
```

Text under 500 characters goes out in one piece. Longer text stops every screenful at
"Scroll? (Y/n)" and waits for a key: `N` ends it, a digit sets the page length, and anything
else continues. `SEND_MSG2` handles the prompt, the key, BREAK, and the closing 03h. `\*`
in the text prints as ©.

## 12.4 A yes/no question

```python
key = tp.SEND_MSG_PROMPT_YN("Erase everything? (y/N) ")
if key == ord("Y"):
    ...
```

This prints the prompt, waits for one key, and returns it (already in upper case). **It is
the answer**: once it returns, send nothing more. Do the work quietly and record any failure
in the log (`tp.LOG(msg, 2)`), because the 2068 has already moved on.

## 12.5 Data

Queue your own bytes with `tp.CMD_PUT`, and call `tp.MQ_READY()` (or `tp.CH_READY()`) **after
the first bytes are in the FIFO**. The 2068 must know exactly how many bytes to read, so start
with a count, as `.fact` does, and end with a checksum. Reusing the `1, n, bytes, XOR` format
means `GET_DATA` and BASIC's `IN 14` loop both work unchanged. For more than 255 bytes, let the
client ask again, as `tpi:chrd` does, rather than inventing a longer format.

**Don't make the first byte 80h or more.** The ROM would take it for a response function and
report D. The only exception is if your 2068 code is the only client, and never the ROM.

## 12.6 What not to do: two answers

Here's a handler that looks reasonable but breaks the link:

```python
def BROKEN(MQ, TSP, pre, cmd):
    MQ.put(0x01)                  # "OK" -- that's one answer...
    for c in b"hello":
        MQ.put(c)                 # ...and five bytes nobody asked for
```

From BASIC, the ROM reads the 01h and carries on. The five letters stay in the FIFO, and the
next command may read them where it expected its pre-load byte. (The next command's SYNC clears
them, which is why today's ROM copes better than older ones.) `MQ.put` also blocks for good once the four-byte
FIFO is full, and no one is reading. That's why `CMD_PUT` exists. The right versions are
`SEND_MSG(..., True)` for text, or a counted data answer.

> **By the way:** the two example commands built into the firmware's `TS/extcmd.py` used to
> be written this way. They've been rewritten: `.fact` now gives the counted data answer of
> section 11.4, and `.rndw` a single 81h message.

## 12.7 Summary

| You want | Call | The 2068 sees |
|---|---|---|
| success or failure | `SEND_MSG(msg, "", st)`, or `CMD_PUT(st)` + `MQ_READY()` | a report |
| mid-statement status | `CH_REPLY(st)` | a report, nothing printed |
| a line of text | `SEND_MSG(msg, msg1, st, True)` | printed text |
| a long listing | `SEND_MSG2(text, st)` | pages with "Scroll?" |
| a yes/no | `SEND_MSG_PROMPT_YN(prompt)` | a prompt; its key comes back to you |
| data | `CMD_PUT`… then `MQ_READY()`, then more `CMD_PUT` | whatever your client reads |

---

# Chapter 13: Adding a Built-in Command

> **Chapter Preview.** When a command is ready to ship, it moves from `dev_extcmd.py` into the
> firmware proper.

## 13.1 Where it goes

1. Write the handler in `src/TS/tspico.py`. Built-in handlers take `(pre, cmd)`. They use the
   module globals `MQ` and `TSP` directly (declare `global MQ` if you assign to it), and call
   the helpers without the `tp.` prefix.
2. Add it to the `SA_funct` dictionary inside `TS2068_IO()`:

   ```python
   "TPI:MYCMD": MYCMD,
   ```

   The key is the upper-case command word with its `TPI:`.
3. If the command needs help text, add `mycmd.txt` (lower case) to the SD card's `/help`
   folder, and `SAVE "tpi:help mycmd"` shows it.
4. Build: the repository's CI builds the UF2 (MicroPython with the `src/` modules frozen in)
   on every push, and `tools/pico-serial.py flash --branch <your-branch>` installs that build.
   **Flash only with the 2068 switched off**, and reseat the SD card afterwards.

## 13.2 Built-in rules

Everything in Chapter 11 applies, plus:

- Never put a pre-load back yourself. The one place the firmware does (when a command body
  never arrives) runs outside the dispatcher's `try` for exactly that reason: inside it, the
  tail would add a second one.
- Don't catch `CmdAbort`. It's a `BaseException` on purpose, so a handler's
  `except Exception:` can't swallow a BREAK.
- Catch the errors you expect (a missing file, a bad argument) and answer them with a proper
  status. Anything else becomes Report J, which tells the user nothing.

## 13.3 Summary

1. The handler goes in `tspico.py`, and its entry in `SA_funct`.
2. CI builds the UF2; flash it with the 2068 off.
3. Same rules as external commands, and never catch `CmdAbort`.

---

# Chapter 14: Timing Rules on the Pico

> **Chapter Preview.** The Pico is fast, but MicroPython isn't always. These rules come from
> bugs found the hard way.

1. **Capture first, think later.** While the 2068 is sending, don't do per-byte Python work.
   Receive the whole block into a buffer (`RX_CAPTURE`), then decode it. The 2068 sends a byte
   every 30 µs, and the FIFO holds four.
2. **No allocation in per-byte loops.** A garbage collection takes 6–25 ms, long enough for the
   2068 to overrun the FIFO. Call `gc.collect()` *before* a data answer, as `CH_READ` does.
3. **No `print()`, `LOG` or `TLM` in fast paths.** A USB print takes 5–10 ms. `MQ_READY` and
   `MQ_STATUS` deliberately log nothing.
4. **Data in the FIFO first, then READY.** The 2068 reads the moment it sees READY.
5. **Do slow work while the 2068 is waiting** for READY: SD access, calculations, building the
   text. Never after you've said READY.
6. **Use `MQX(MQ, instr)`**, not `MQ.exec()`, for PIO instructions. It takes 18 µs instead of
   9.6 ms on MicroPython 1.20.
7. **Any idle loop you add must call `DRAIN_STDIN(MQ)`**, so Ctrl-C from the USB console can
   still reach the firmware.
8. **Don't start threads on core 1** unguarded: set `busy` first, wrap the spawn in
   `try/except OSError` and clear `busy` yourself if it fails, the way the idle loop
   spawns `SAVE_LOG`. An uncaught "core1 in use" reaches `main.py` and drops the Pico
   to a REPL.

---

# Chapter 15: Testing and Debugging

> **Chapter Preview.** How to find out whether a command works before, and after, it meets a
> real 2068.

## 15.1 Host tests

The repository's `src/test/*_hosttest.py` files run on an ordinary computer with CPython, and
CI runs them on every push. `process_cmd_hosttest.py` is the one to copy for commands. It
replaces the hardware modules with fakes, gives `PROCESS_CMD` a `FakeMQ` holding a command
body, and records every byte the firmware sends back. This book's
`examples/test_extcmd_host.py` does exactly that for the three example commands. For
`.hello` it checks:

```python
log = send("tpi:.hello")
h.check(msg(log) == b"\x81\x01\rHello from the TS-Pico!\x00\x01",
        "81h message, then one pre-load")
```

That final `\x01` is the tail's pre-load. Checking for exactly one is how you catch the
two-answer bug from section 12.6.

For the 2068 side, `examples/test_examples.py` runs the assembled examples in the repository's
Z80 interpreter (`src/test/z80core.py`) against a model of the Pico. It checks the results, and
that the link is left idle with exactly one pre-load after every command.

## 15.2 Watching the Pico

- `python3 tools/pico-serial.py watch` shows the Pico's USB console with timestamps, without
  disturbing it. With telemetry on (it is, in `main.py`), each command step prints a `[TLM ...]`
  line showing the time and the FIFO levels.
- `SAVE "tpi:log"` on the 2068 shows the log (`/activity.log` on the flash), and
  `tp.LOG(msg, level)` writes to it (0 = info, 3 = critical).
- **Thonny stops the firmware when it connects.** The 2068 then sees a long pause and Report J.
  Close Thonny, or use `pico-serial.py`, which refuses to share the port.

## 15.3 On the hardware

`src/test/_harness_template.py` is a starting point for on-hardware experiments. It sets up
the pins and state machines, and captures bytes without the rest of the firmware in the way.
For your own commands, the simplest test is a BASIC loop that runs the command a few hundred
times and then runs another command. A broken pre-load chain shows up on the *second* command.

## 15.4 Summary

1. Test commands on the host with `PROCESS_CMD` and a `FakeMQ`: check the bytes and the single
   01h.
2. `pico-serial.py watch` and the `[TLM]` lines show what the firmware is doing.
3. Thonny interrupts the firmware; `pico-serial.py` doesn't.
4. On hardware, repeat the command many times and always follow it with another.

---

# Chapter 16: Rules of the Road for Pico Code

> **Chapter Preview.** The Part 2 checklist.

1. **Exactly one answer. Never the pre-load.**
2. **Data first, then READY.**
3. **`CMD_PUT`, not `MQ.put`**, for anything the 2068 reads.
4. **SD work inside `SD_CALL`**, and before the answer.
5. **Plain status codes for errors**: the ROM already knows how to report them.
6. **Text below 128**, and no 03h inside an 86h listing.
7. **No response-function codes** (80h and up) as the first byte of a data answer.
8. **Never catch `CmdAbort`.**
9. **Don't decode 2068 bytes outside a `try`.** Names can contain bytes of 128 or more.
10. **Mask receive-FIFO words with `& 0xFF`.** Bit 8 marks a write to port 15.
11. **Bound every wait.** `while MQ.tx_fifo(): pass` can hang for ever.
12. **Flash and reset with the 2068 switched off**, and reseat the SD card afterwards.

---

# Appendix A: Protocol Quick Reference

**Ports:** 0Eh data (IN: next byte, 00h if empty; OUT: a byte to the Pico). 0Fh status (IN)
and SYNC/abort (OUT any value; the ROM sends 03h).

**Status byte:** bit 6 READY, bit 3 IDLE, bit 2 RECOVERED (active low). FFh idle, F7h mid,
FBh recovered, 00h busy (after every OUT).

**A command:**

```
wait IDLE; OUT (0Fh),03h; wait READY+IDLE
OUT 42h, 0, FFh, a lo, a hi, b lo, b hi, len lo, len hi, XOR(bytes 0-8)
IN (0Eh) -> 01h
wait READY
OUT 44h, len lo, len hi, text..., XOR(44h..last text byte)
wait READY
IN (0Eh) -> answer
```

**Statuses:**

| Byte | Report | ERR_NR |
|---|---|---|
| 00h | J | 12h |
| 1 | OK | — |
| 2 | R | 1Ah |
| 3 | F | 0Eh |
| 4 | Q | 19h |
| 5 | C | 0Bh |
| 6 | 6 | 05h |
| 7 | 8 | 07h |
| 8 | A | 09h |
| 9 | 9 | 08h |
| 10 | J | 12h |
| 11–127 | D | 0Ch |
| RECOVERED | T | 1Ch |

**Response functions:** 81h (status, text, 00h), 86h (status, pages ending 00h each, key
exchange, 03h at the end), 88h (86h on the lower screen). Other codes are Report D.

**Data answer (`tpi:chrd`, `.fact`):** status 1, n (1–255), n bytes, XOR of the n bytes; or
7 at end of file.

**Firmware status constants:** `_1_OK`, `_2_R_Tape_load`, `_3_F_Invalid_file`,
`_4_Q_Parameter`, `_5_C_Nonsense`, `_6_6_Num2Big`, `_7_8_EOF`, `_8_A_Invalid_arg`,
`_9_9_STOP`, `_10_J_Invalid_IO`, `_11_D_Break`.

# Appendix B: The Pico BIOS and Useful ROM Addresses

| Where | Address | What |
|---|---|---|
| EXROM | 1840h | G_MODE: BC = TPMODE |
| EXROM | 1842h | S_MODE: TPMODE := A AND 0Fh |
| EXROM | 1844h | G_VERS: BC = 0022h on ROM 2.2 (0021h on 2.1) |
| EXROM | 1846h | TX_A: OUT (0Eh),A |
| EXROM | 1848h | RX_A: IN A,(0Eh) |
| EXROM | 184Ah | C_END: wait, read the answer, run response functions |
| EXROM | 184Ch | WF_NPH: wait for READY (02h timeout, 0Ch BREAK, 1Ch T) |
| EXROM | 1BF3h | A = status−1: raise the matching report (never returns) |
| EXROM | 2300h | SYNC_WRITE: SYNC, wait, OUT (0Eh),A |
| EXROM | 230Eh | SYNC_WAIT: wait ~1 s for READY+IDLE |
| HOME | 03FCh | call EXROM: HL = address; DI around it |
| HOME | 1230h | CHAN_OPEN: select stream A for RST 10h |
| HOME | 0065h | ROM version byte (`PEEK 101`) |
| RAM | 5C08h | LAST_K |
| RAM | 5C3Bh | FLAGS (bit 5: new key) |
| RAM | 5C3Dh | ERR_SP |
| RAM | 5DDBh (24027) | TPMODE: bit 1 LOAD/SAVE to the Pico, bit 0 printer to the Pico |
| RAM | 65CEh | the bank-switch stack pointer |

Never call EXROM 2003h, 2006h or 2027h–203Ch: they loop for ever.

# Appendix C: Firmware Helper Reference

| Name | Module | Purpose |
|---|---|---|
| `PARAMS(pre)` | tspico | the two CODE numbers |
| `getArgs(cmd)` | tspico | text after the command word |
| `SEND_MSG(msg, msg1, st, force=False)` | tspico | status, or 81h message |
| `SEND_MSG2(text, st)` | tspico | 86h scrolling text |
| `SEND_MSG_PROMPT_YN(prompt)` | tspico | 86h prompt; returns the key |
| `CMD_PUT(b)` / `CMD_KEY()` / `CMD_DRAIN()` | tspico | answer bytes, a key, wait until read; BREAK raises `CmdAbort` |
| `MQ_READY()` | tspico | status FFh |
| `CH_READY()` / `CH_REPLY(st)` | tspico | status F7h / a bare status with F7h |
| `SD_CALL(fn, *args)` | tspico | run `fn` with the SD card active |
| `LOG(msg, level)` | tspico | write to `/activity.log` |
| `TLM(action, detail)` | tspico | a telemetry line on the USB console |
| `catalog.resolve(cur, arg)` | catalog | the real path for a user's path |
| `catalog.public(real)` | catalog | the path as the user sees it |
| `MQX(MQ, instr)` | tspico_io | run one PIO instruction, fast |
| `RX_CAPTURE(MQ, buf, n, ms)` | tspico_io | capture n bytes; negative on a SYNC |
| `DRAIN_STDIN(MQ)` | tspico_io | keep Ctrl-C reachable in idle loops |

# Appendix D: Further Reading in the Repository

These documents in the firmware repository match the code this book describes:

| Document | What it covers |
|---|---|
| `docs/PROTOCOL_GUIDE.md` | the protocol in plain language: a good first read before Chapter 3 |
| `docs/PROTOCOL.md` | the byte-level reference: ports, status values, every transaction, response functions 81h–88h, the BIOS, and a long list of pitfalls |
| `docs/EXTCMD_PROTOCOL.md` | external commands: the contract of Chapter 11 and the examples |
| `docs/DISK_COMMANDS_SPEC.md` | the disk commands and channels, from the BASIC side |
| `src/CLAUDE.md` | working on the firmware: harnesses, the two-phase capture rule, talking to the Pico over USB |

`docs/GUSTAVO_PROTOCOL.md` is the original design, kept as history. A note at its top lists
where today's protocol differs.

# Appendix E: The Example Files

In the `examples` folder next to this manual:

| File | What |
|---|---|
| `picolib.asm` | the library (Chapter 4) |
| `picocmd.asm` | send any command (5.1) |
| `loadfile.asm` | load any file into memory (5.2) |
| `logline.asm` | append a line to a text file (5.3) |
| `countdir.asm` | count matching files (5.4) |
| `fact.asm` | read the `.fact` data answer (5.5) |
| `bios.asm` | call the Pico BIOS (8.2) |
| `*.bin`, `picoex.tap` | the assembled examples; the TAP has them all as CODE blocks at 60000 |
| `make_tap.py` | assembles everything and rebuilds `picoex.tap` (needs sjasmplus) |
| `dev_extcmd.py` | the Pico commands `.hello`, `.fact` and `.lines` (Chapter 11) |
| `test_examples.py` | runs the Z80 examples against a simulated Pico |
| `test_extcmd_host.py` | runs the Pico commands through the firmware's real dispatcher |

The folder is `docs/manual/examples/` in the firmware repository, and CI runs both tests on
every change. To run them yourself, from the repository's top folder:

```bash
python3 docs/manual/examples/test_examples.py
```

```bash
python3 docs/manual/examples/test_extcmd_host.py
```

`test_examples.py` and `make_tap.py` need sjasmplus.
