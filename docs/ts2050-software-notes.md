# TS2050 / 8251 software notes, for writing a new TS2068 terminal program

These notes are a developer reference for a new TS2068 modem and terminal program. The program talks to the TS-Pico v3 card's emulated Intel 8251 at ports $73 and $77. Behind the emulated 8251, the card bridges to Zimodem running on an ESP32-C3.

The notes come from three kinds of source:

- **Disassembly** of the two MTERM programs from the archive.org Timex Sinclair software archive. I disassembled them with z80dasm 1.2.0. Every address below is the run-time address.
- **The Intel 8251A datasheet.**
- **Zimodem source** (bozimmerman/Zimodem, master branch, 2026-10). The card pins 4.0.3 (commit a24225c) in `tspico-hardware/firmware/zimodem/build.sh`.

Statements marked **(inferred)** are my reading of the code. Nothing documents them.

All T-state timings assume:

- The TS2068's 3.528 MHz clock.
- Code running above 8000h, so no memory contention.
- Interrupts off. MTERM switches the timer interrupt off with `OUT (FFh),40h`, which sets SCLD bit 6 ("interrupt disable").

## 1. Port map and 8251 registers

| Port | Read | Write |
|---|---|---|
| $73 (115) | received data | transmit data |
| $77 (119) | status | mode byte, then command bytes |

- MTERM, MTERM II and the 2068 BBS use only these two ports. The BBS write-up names them: https://timexsinclair.com/computer_media/2068-bbs-program.md
- MTERM does not set the high address byte. A before `IN A,(77h)` holds whatever the code left there. **A decoder must ignore A8–A15.**
- The 2050 has no other modem-control port. It controls the modem with the 8251's own pins **(inferred from the MTERM code, section 2)**:
  - **DTR = off-hook relay.** The command byte's DTR bit is set to 1 (pin low) when off-hook. Pulse dialing toggles DTR.
  - **DSR (status bit 7) = carrier detect** while off-hook.
  - **DSR also shows ringing while on-hook.** MTERM counts DSR edges as rings.
  - **RTS = modem transmit-carrier enable (inferred).** Originate mode raises RTS only after the remote carrier is seen. Answer mode raises it before the carrier wait. That is the Bell 103 handshake order.
- **Baud rate:** fixed at 300 baud. The program selects ×64 in the mode byte, so the 2050 presumably clocks TxC/RxC at 19.2 kHz. The datasheet's own example gives "RxC equals 19.2 kHz in the 64x mode" for 300 baud. The actual clock source is unverified.
- **Schematic:** there are schematic articles, but the site has no content for them: https://timexsinclair.com/article/timex-2050-modem-schematic.md and https://timexsinclair.com/article/2050-modem-schematic.md

Source for the register tables below: Intel 8251A datasheet 205222-002, https://mark-ogden.uk/files/intel/publications/205222-002%208251A%20Programmable%20Communication%20Interface-Nov86.pdf

### Mode byte
This is the first control write after any reset.

| Bits | Field | Values |
|---|---|---|
| 1:0 | Baud factor | 00 sync mode, 01 ×1, 10 ×16, 11 ×64 |
| 3:2 | Character length | 00 = 5, 01 = 6, 10 = 7, 11 = 8 bits |
| 4 | PEN | 1 = parity enabled |
| 5 | EP | 1 = even parity, 0 = odd |
| 7:6 | Stop bits | 00 invalid, 01 = 1, 10 = 1.5, 11 = 2 |

MTERM's default mode byte is **7Bh: ×64, 7 bits, even parity, 1 stop bit.** The BBS writes the same value (123).

### Command byte
Every control write after the mode byte is a command.

| Bit | Name | Meaning when 1 |
|---|---|---|
| 0 | TxEN | Transmitter enabled |
| 1 | DTR | /DTR pin driven low (off-hook on the 2050) |
| 2 | RxE | Receiver enabled |
| 3 | SBRK | TxD held low (send break) |
| 4 | ER | Clear PE, OE and FE |
| 5 | RTS | /RTS pin driven low |
| 6 | IR | Internal reset: the next control write is a mode byte |
| 7 | EH | Enter hunt (sync mode only) |

### Status byte (read from $77)

| Bit | Name | Set when | Cleared when |
|---|---|---|---|
| 0 | TxRDY | Transmit data buffer is empty | A data write starts |
| 1 | RxRDY | A whole character reaches the output register | The data port is read. Held clear while RxE = 0 |
| 2 | TxEMPTY | Nothing is left to send | A character is written while TxEN = 1. Stays set while the transmitter is disabled |
| 3 | PE | Parity error | ER |
| 4 | OE | A new character arrived before the old one was read; the old one is lost | ER |
| 5 | FE | No valid stop bit | ER |
| 6 | SYNDET/BRKDET | Async mode: RxD low for two whole frames | RxD returns high, or a reset |
| 7 | DSR | The /DSR pin is low | The pin goes high |

**Datasheet behaviour a driver relies on:**

- **The TxRDY status bit is not masked by CTS or TxEN.** It only means "buffer empty". The TxRDY *pin* is masked by both. Every program here polls the status bit.
- **Short characters read back with zeros.** With 5, 6 or 7 data bits, the unused high bits of a received byte are 0, and on transmit they are "don't care". So in 7E1 a received byte always has bit 7 = 0.
- **Status can lag.** A status update may lag its event by up to 28 CLK cycles.
- **Recovery time.** Back-to-back control writes during mode setup need 6 tCY between them. Data writes are allowed only when TxRDY = 1.
- **Power-up and reset.** At power-up the chip may be expecting a mode byte, a sync character or a command. The recommended reset is three 00h writes to the control port, then 40h. A hardware or internal reset returns the chip to "expecting a mode byte".

## 2. MTERM and MTERM II

### 2.1 Which files these are

**MTERM/T (tape).** Its banner reads "MTERM/T - Tiny Terminal program, Version 1.00 (c) 1983 Micro-Systems Software Inc., Anchor Automation Inc."

- Download: https://archive.org/download/timex-sinclair-software-archive/MTERM%20%281984%29%28Westridge%20Communications%29%28US%29%28TS2068%29%28Program%29.zip
- Archive page: https://timexsinclair.com/computer_media/mterm.md
- The `.tap` holds a BASIC loader `aai` (493 bytes, autostarts at line 10) and a CODE block `aterm`: 8000 bytes at **54016 (D300h)**, running from D300h to F23Fh.
- Entry point is D300h. The BASIC calls `PRINT USR 54016`.
- Menus:
  - Main menu: A auto-dial, B/I/P colours, S setup.
  - Setup menu: D duplex, P parity, S stop bits, W word length.
  - A "Modem CMD" prompt: H hang up, M answer, D dial, P off-hook with no carrier monitoring.
- Messages: "Ring-In", "Connect", "Connection lost", "No answer or busy", "Manual disconnect".
- The display is 32 columns.

**MTERM II (cartridge).** The archive lists it as "MTERM II (1986)(Zebra Systems)". Its banner reads "MTERM - Smart Terminal program, Version 1.00 (c) 1983 Micro-Systems Software Inc., Licensed to Westridge Comm. Inc."

- Download (`mterm-II.dck`, 8201 bytes): https://archive.org/download/timex-sinclair-software-archive/MTERM%20II%20%281986%29%28Zebra%20Systems%29%28US%29%28TS2068%29%28Cartridge%29.zip
- Archive page: https://timexsinclair.com/computer_media/mterm-ii.md
- **Layout:** a DCK with bank 00 (DOCK) and a single ROM chunk, chunk 4 (8000h–9FFFh).
  - The cartridge header at 8000h is `01 02 08 80 …` and contains a tokenised BASIC line, `PRINT USR 32816`.
  - At 8030h the code runs `LD HL,80FCh / LD DE,D2FCh / LD BC,1E30h / LDIR / JP D2FDh`. So the program runs from RAM at **D2FCh–F12Bh**.
- Features beyond MTERM/T:
  - A phonebook in which each entry has its own serial parameters (its own mode byte).
  - A data buffer: toggle, erase, transmit, view, conversion.
  - LF and CR suppression, MacroKeys, Xlate tables, video width, and settings saved to tape.
- The 8251 code is byte-for-byte the same as MTERM/T, relocated. Only the timeouts differ, as noted below.

### 2.2 The settings bytes and the XOR-22h trick

| | MTERM/T | MTERM II | Default | Meaning |
|---|---|---|---|---|
| Stored command | E10Bh | F103h | **37h** | The command byte XOR 22h |
| Mode byte | E10Ch | F104h | **7Bh** | 7E1, ×64 |

- The stored command is always the real command XOR 22h, so the DTR and RTS bits are kept inverted. Stored 37h means a written command of **15h: TxEN, RxE, ER, with DTR and RTS off.** That is on-hook, idle.
- Store bit 1 = 1 means DTR is off, i.e. on-hook. **Both TX and RX are skipped while on-hook.**
- **ER (bit 4) is always set in the stored value**, so rewriting the command also clears errors.
- `LD BC,(store)` loads C = stored command and B = mode, which is what the init routine takes.

### 2.3 Initialise / write command (MTERM/T DD32h; MTERM II E737h)

Inputs: B = mode byte, or 0 for "command only". C = stored command.

```
DD32  XOR A
      CP B
      JR Z,DD46        ; B=0: skip the reset, write the command only
      OUT (77h),A      ; 00h  \
      OUT (77h),A      ; 00h   } datasheet worst-case reset
      OUT (77h),A      ; 00h  /
      LD A,40h
      OUT (77h),A      ; internal reset
      LD A,B
      LD (E10C),A
      OUT (77h),A      ; mode byte
DD46  LD A,C
      LD (E10B),A
DD4A  XOR 22h          ; entry point used for "rewrite command + error reset"
      OUT (77h),A      ; command
      RET
```

- At start-up (D300h) the program runs `LD SP,E7FD / OUT (FFh),40h` (timer interrupt off), then `LD BC,(E10B) / CALL DD32`. So the full reset runs with mode 7Bh and command 15h.
- Changing parity, word length or stop bits rebuilds the mode byte and calls DD32 with B ≠ 0, which does a full reset every time.
- The four control writes go out back-to-back: `OUT (n),A` takes 11 T-states, about 3.1 µs apart.

### 2.4 Transmit (MTERM/T DD04h; MTERM II E709h)

```
DD04  PUSH AF
      LD A,(E10B)
      AND 02h
      JR NZ,DD15       ; on-hook: drop the byte silently
DD0C  IN A,(77h)
      RRCA             ; TxRDY -> carry
      JR NC,DD0C       ; busy-wait, no timeout
      POP AF
      PUSH AF
      OUT (73h),A
DD15  POP AF
      RET
```

- There is no timeout. If TxRDY never comes back, MTERM hangs here.

### 2.5 Receive (MTERM/T DD17h; MTERM II E71Ch)

Returns Z if no character is waiting. Otherwise returns NZ with the character in A.

```
DD17  LD A,(E10B)
      CPL
      AND 02h
      RET Z            ; on-hook: no receive
      IN A,(77h)
      BIT 1,A          ; RxRDY
      RET Z
      AND 38h          ; FE|OE|PE
      JR Z,DD2D
      LD A,(E10B)
      CALL DD4A        ; rewrite command (ER is set in it) = error reset
DD2D  OR 0FFh          ; force NZ
      IN A,(73h)       ; read the char even after an error
      RET
```

- The wrapper at D777h (MTERM II DD7Eh) calls DD17. If there is a character, it is stored raw in a ring buffer:
  - MTERM/T: E199h–E498h, 767 bytes, pointers at DFEEh, DFF0h and DFF2h.
  - MTERM II's buffer wraps at FA00h.
- **Every delay loop calls this wrapper.** The keyboard debounce, the dial pulses and the inter-digit pauses all keep draining RxRDY. The main loop takes **at most one character** from the ring buffer per pass and prints it.
- Main loop (MTERM/T D325h), each pass:
  1. Run the carrier/ring monitor (D555h).
  2. Scan the keyboard (DA0Bh).
  3. Handle special keys: FEh = help menu, FCh = Modem CMD prompt, FDh = send break.
  4. Send any typed character (DD04h). Echo it locally if half duplex (E108h bit 1).
  5. Pop one character from the ring buffer and display it (D64Ch).
- The display routine D64Ch handles ESC sequences, including VT52-style `ESC Y row col`, from a table at D6DDh, plus some CR/LF handling **(inferred; not traced in detail)**.
- **Display speed was not measured.** Software glyph drawing at 32 columns should keep up easily with 300 baud's 30 characters per second **(inferred)**. The 767-byte ring buffer absorbs bursts while the program is busy.

### 2.6 Delay unit (MTERM/T D8DDh; MTERM II E0E7h)

```
D8DD  PUSH BC
D8DE  CALL D777        ; poll receive (see above)
      DEC BC
      LD A,B
      OR C
      JR NZ,D8DE
      POP BC
      RET
```

One iteration takes **106 T-states while on-hook** (DD17 returns early) and **130 T-states while off-hook with no character waiting**. At 3.528 MHz that is 30.0 µs and 36.8 µs.

### 2.7 Off-hook, hang-up and break

- **Off-hook** (D48Dh): `RES 1,C` (DTR on), `SET 5,C` (RTS off), B = 0, then `JP DD32`.
- **Hang-up** (D47Bh): `SET 1,C` (DTR off), `SET 5,C` (RTS off), then `JP DD32`. It also clears E109h bit 2.
- **Break key** (FDh, D6FFh): `SET 3,C` (SBRK), wait using the count at E112h (1D00h, i.e. 7424 × 130 T ≈ **274 ms**), then restore the command.

### 2.8 Pulse dialer (MTERM/T D49Ah, D50Bh, D53Ch; MTERM II D5C1h, D61Eh, D64Fh)

1. Go off-hook.
2. Wait FC04h × 130 T ≈ **2.38 s** for dial tone.
3. Walk up to 30 characters of the number string:
   - Digits are dialled.
   - `P` pauses 65536 × 130 T ≈ **2.42 s**.
   - Anything else is skipped.
4. After the last digit, wait another 2.38 s.
5. Go to the carrier wait (2.9).

Each digit gives n pulses, and "0" gives 10:

```
D519  PUSH BC
      SET 1,C          ; DTR off = break (on-hook)
      CALL DD32
      LD BC,078Fh
      CALL D8DD        ; 1935 x 106 T = 205,110 T = 58.1 ms break
      POP BC
      PUSH BC
      CALL DD32        ; DTR on = make
      LD BC,050Ah
      CALL D8DD        ; 1290 x 130 T = 167,700 T = 47.5 ms make
      POP BC
      DEC D
      JR NZ,D519
      LD BC,5834h
      CALL D8DD        ; 22580 x 130 T = 832 ms inter-digit gap
```

That is about 9.5 pulses per second, with 55 % break.

Zimodem's own pulse decoder, if it is ever wired, accepts:

- each pulse edge 15–60 ms apart;
- a gap of 225–350 ms between digits;
- a digit complete after more than 350 ms of quiet.

MTERM's 832 ms gap fits the last rule. Source: `ZCommand::checkPulseDial` in https://github.com/bozimmerman/Zimodem/blob/master/zimodem/zcommand.ino

### 2.9 Carrier wait (MTERM/T D4B3h; MTERM II D5DAh)

```
D4B3  LD HL,0000h      ; 65536 outer tries
D4B6  LD BC,7C7Ch      ; DSR must stay 1 for 31868 consecutive polls
D4B9  IN A,(77h)
      AND 80h
      JR Z,D4C6        ; DSR=0: go scan keys, count down HL
      DEC BC
      LD A,B
      OR C
      JR NZ,D4B9       ; 51 T/poll -> 31868 x 51 = 1,625,268 T = 0.46 s
      JR D4DC          ; carrier qualified
D4C6  CALL DA0B        ; keyboard; BREAK (FDh) aborts
      CP 0FDh
      JR Z,D4D2
      DEC HL
      LD A,H
      OR L
      JR NZ,D4B6
D4D2  ...              ; "No answer or busy", hang up, return carry
```

- **DSR has to stay high continuously for about 0.46 s.** Any low reading restarts the count.
- The overall timeout is 65536 keyboard scans. I estimate roughly 10–20 s **(inferred; not timed)**.
- **What happens after qualification differs between the two programs:**
  - **MTERM/T (D4DCh):** if RTS was off, it sets RTS (`RES 5,C`, command only). It then requires DSR to stay high for 3 × 7C7Ch polls, about 1.38 s more. If DSR drops during that time, it goes back to D4B3h. Then it shows "Connect".
  - **MTERM II:** it shows "Connect" first, then sets RTS. It does no second check.

### 2.10 Monitor while connected, and ring detection (MTERM/T D555h; MTERM II D668h)

This routine is called from every main-loop pass and every key-wait.

**Off-hook** (DTR on), when E109h bit 2 is clear:

- If DSR reads 1, the routine returns at once.
- If DSR stays 0 for 7C7Ch polls (51 T each), the program shows "Connection lost" and hangs up.
  - MTERM/T waits 1 × 7C7Ch polls, about **0.46 s**.
  - MTERM II waits 3 × 7C7Ch polls, about **1.38 s**.
- Bit 2 is set by the Modem CMD "P" command. It suppresses carrier monitoring, which is direct-connect use **(inferred)**.

**On-hook** (DTR off):

1. Compare DSR with its last value (stored at E11Ah, or F112h in MTERM II).
2. On a change, keep polling (69 T per poll) until DSR has been quiet for:
   - 5834h polls in MTERM/T, about 0.44 s;
   - 7C7Ch polls in MTERM II, about 0.62 s.
3. Then show "Ring-In" and decrement the ring counter (E11Bh, default 4).
4. When the counter reaches zero it is reset to 4 and the program **auto-answers** (D5ABh):
   - go off-hook, wait 2.38 s;
   - set RTS;
   - run the carrier wait.

**So an emulator that toggles DSR while on-hook makes MTERM answer the "call" after four "rings".** Keep DSR steady while DTR is off, unless you mean to ring.

## 3. BASIC dialers and the 2068 BBS

### 3.1 Modem
Source: https://timexsinclair.com/computer_media/modem.md. Download: https://archive.org/download/timex-sinclair-software-archive/Modem%20%28198x%29%28TS2068%29%28US%29%28Program%29.zip

```
  15 OUT 119,31
  18 PAUSE 50
  60 FOR d=1 TO a
  70 FOR e=3 TO 4
  80 OUT 119,e
  90 PAUSE 2.5
 100 NEXT e
 110 OUT 119,1
 120 OUT 119,2
 130 NEXT d
 160 FOR i=1 TO 2000
 165 IF IN 119=133 THEN CLS : PRINT FLASH 1;"C O N N E C T E D ! !": GO TO 200
 168 NEXT i
 170 OUT 119,0
 280 OUT 119,34: PRINT USR 54016
```

- The program writes no mode byte and no reset.
- If the 8251 is already in command mode, the writes mean:

| Value | Meaning |
|---|---|
| 31 = 1Fh | DTR on (off-hook) + TxEN + RxE + SBRK + ER |
| 3 | DTR on |
| 4 | DTR off |
| 1 | DTR off |
| 2 | DTR on |
| 0 | everything off (hang up) |
| 34 = 22h | DTR + RTS |

  So each pulse is make, break, break, make.
- **If the chip is fresh from reset, the first write (31) is taken as a mode byte instead**, with an invalid stop-bit field. An emulator must follow the real state machine.
- **The connect test compares the whole status byte: `IN 119=133`, i.e. 85h** = DSR + TxEMPTY + TxRDY. RxRDY, every error bit and BRKDET must all be 0, or the program redials. If the bridge passes Zimodem's "CONNECT" text in as received data, RxRDY = 1 and this test never matches.
- After the connect it starts MTERM with `PRINT USR 54016`, after POKE patches.

### 3.2 Loader V (K. A. Casby, 1985)
Source: https://timexsinclair.com/computer_media/loader-v.md. Download: https://archive.org/download/timex-sinclair-software-archive/Loader%20V%20%281985%29%28Kurt%20A.%20Casby%29%28TS2068%29%28US%29%28Program%29.zip

`m` = 119, `o` = 0, `i` = 1, `b` = 2, `f` = 20.

```
   1 ... OUT m,o ...
  47 OUT m,VAL "31": PAUSE VAL "60": FOR x=i TO LEN z$: LET z=VAL z$(x): IF z=o THEN LET z=f/b
  48 PAUSE VAL "25": FOR d=i TO z: FOR e=INT PI TO VAL "4": OUT m,e: NEXT e: OUT m,i: OUT m,b: NEXT d: NEXT x
  49 FOR x=i TO VAL "1e3": IF IN m=VAL "133" THEN OUT m,VAL "34": POKE p+i,i: BEEP i,f: GO TO f
  50 NEXT x: OUT m,o: PAUSE VAL "99": LET t=t+i: GO TO VAL "46"
```

- It uses the same byte sequence as Modem, but there is no PAUSE inside a pulse, so pulse timing is just BASIC's speed.
- It uses the same `=133` test.
- After the carrier it writes 34 (DTR + RTS), so RTS goes on after the carrier, as in originate mode.

### 3.3 2068 BBS Program (Lucy Gordon / Phillip Basford)
Source: https://timexsinclair.com/computer_media/2068-bbs-program.md. Download: https://archive.org/download/timex-sinclair-software-archive/2068%20BBS%20Program.zip

```
1000 OUT 119,34: OUT 119,0
1002 LET x=IN 119
1004 IF x=5 THEN GO TO VAL "1002"
1010 OUT 119,2: OUT 119,34: PAUSE 300: OUT 119,64: OUT 119,123: OUT 119,55
1016 FOR x=1 TO 30: RANDOMIZE USR o: OUT 115,0: NEXT X
1018 LET a=IN 119: IF a<128 THEN GO TO 1020
1020 RANDOMIZE USR o: OUT 115,28: RANDOMIZE USR o: OUT 115,31: RANDOMIZE USR o: OUT 115,28
1021 LET x=IN 115
2562 LET a=USR 65480
2592 IF xmit THEN LET l$=INKEY$: PRINT l$;: OUT 115,CODE l$: FOR x=1 TO 5: NEXT x: ...
9100 FOR x=1 TO LEN P$: RANDOMIZE USR o: OUT 115,CODE p$(x): NEXT x: ...
9201 ... OUT 119,64: OUT 119,0: OUT 119,0
```

**Answer sequence:**

1. Wait while status = 5, i.e. TxRDY + TxEMPTY with DSR = 0. Any DSR = 1 (ring or carrier) ends the wait.
2. Off-hook with DTR, then DTR + RTS.
3. Wait 6 s.
4. Reset (64), mode 7Bh (123), command 37h (55) = TxEN, DTR, RxE, ER, RTS.

Line 1018 is a no-op: both branches go to 1020.

**Hang-up (line 9201):** reset, then 0 as the mode byte, then command 0 (DTR off).

**Machine code**, 56 bytes POKEd at 65480 (FFC8h) from the decimal string in line 14. Disassembly:

```
FFC8  XOR A / IN A,(77h) / AND 03h / LD C,A / LD B,0 / RET  ; USR 65480 = TxRDY|RxRDY bits
FFD1  IN A,(77h) / AND 80h / RET Z                         ; "i" = 65489: give up if DSR=0
      XOR A / IN A,(77h) / AND 02h / JR Z,FFD1             ; wait RxRDY
      IN A,(74h)                                           ; <-- 116, see below
      LD (FFC7h),A / LD C,A
FFE3  IN A,(77h) / AND 80h / RET Z                         ; DSR check
      XOR A / IN A,(77h) / AND 01h / JR Z,FFE3             ; wait TxRDY
FFEF  LD A,C / OUT (73h),A / RET                           ; echo the received char
FFF3  IN A,(77h) / AND 80h / RET Z                         ; "o" = 65523: wait-for-TxRDY
      XOR A / IN A,(77h) / AND 01h / JR Z,FFEF             ; (target as transcribed)
      RET
```

- **Every routine returns at once if DSR = 0.** With DSR low, nothing is sent or received.
- **The `IN A,(116)` oddity.** It reads 74h where the data port is 73h, and a read of $74 would fall on the status/command side of the C/D line. The `JR Z` at FFFCh lands on FFEFh, so with TxRDY = 0 it would write C instead of waiting. Both look like transcription errors in the listing **(inferred)**:
  - 116 should probably be 115;
  - the jump byte 240 should probably be 245, looping back to FFF3h.
  
  Treat this program as a behavioural reference, not as working code.
- The `XOR A` before each `IN A,(n)` puts 00h on A8–A15. MTERM does not do this, so the high byte doesn't matter.

### 3.4 Other programs (not disassembled)
The list is at https://timexsinclair.com/type/terminal/:

- **Specterm-64 v4 (2068):** https://archive.org/download/timex-sinclair-software-archive/Specterm-64%20v4%20%281986%29%28G%20%26%20C%20Computer%20Prod%29%28US%29%28TS2068%29%28Program%29.zip
- **ZX-Term*80 (TS1000, Westridge/Byte-Back):** https://archive.org/download/timex-sinclair-software-archive/ZX%20Term%2080%20v2.5%20%281987%29%28Nachbaur%2C%20Fred%29%28US%29%28TS1000%29%28Program%29.zip
- **AercoPatch (an MTERM patch).**

## 4. Zimodem facts a 2068 program needs

Sources: README https://github.com/bozimmerman/Zimodem, plus `zimodem/zimodem.ino`, `zcommand.ino` and `zstream.ino` on master.

**Factory defaults:**

- 1200 baud, `SERIAL_8N1`.
- Flow control off (`FCT_DISABLED`).
- Echo on (`ATE1`).
- Verbose result codes (`ATV1`).
- Long responses (`ATX1`).
- Line ending CR LF (`ATR1`).
- Telnet off (`S62=0`).
- PETSCII off.

On the card, the RP2350 decides what baud rate the UART to the ESP32 actually runs at. The 2068 never sees that rate. The program should not depend on it.

**Result codes:**

| Verbose (ATV1) | Numeric (ATV0) | When |
|---|---|---|
| `OK` | `0` | Command accepted |
| `CONNECT` or `CONNECT <id>` (ATX1) | `1` with ATX0; with ATX1, a code by baud rate (1, 5, 10, 11, 24, 12, 25, 13, 28) | Connection opened |
| `RING` | `2` | Incoming connection on an `ATA` listener |
| `NO CARRIER` | `3` | Remote closed the connection |
| `ERROR` | `4` | Bad command |
| `NO ANSWER` | `8` | Connect failed |

Each code is preceded by and followed by the end-of-line string. **With ATX1, `CONNECT` is followed by the connection id, not the baud rate.**

**Commands:**

| Command | Effect |
|---|---|
| `ATE0` / `ATE1` | Command-mode echo off / on |
| `ATV0` / `ATV1` | Numeric / verbose results |
| `ATQ1` | No result codes at all |
| `ATX0` | Short codes |
| `ATR0` | CR only at end of line |
| `ATR1` | CR LF |
| `ATF0` | RTS/CTS flow control |
| `ATF1` | XON/XOFF |
| `ATF4` | No flow control in command mode |
| `AT&Kn` | Hayes-style flow control: 0–2 off, 3 and 6 RTS/CTS, 4 and 5 XON/XOFF |
| `ATB"n,xYz"` | Baud, bits, parity (E, O, M, N), stop bits |
| `AT&W` | Save the current settings |
| `ATZ` | Reload saved settings |
| `ATW"ssid,password"` | Join WiFi |
| `ATI` | Show status |
| `ATD"host:port"` | Connect and enter stream mode |
| `ATDT"host:port"` | Connect with telnet negotiation for this session (or set `S62=1`) |
| `ATDX"host:port"` | Enable XON/XOFF for this session |
| `ATP"5551212=host:port,notes"` | Add a phonebook entry |
| `ATD5551212` | Dial a phonebook entry by number |
| `ATH` | Hang up all connections |
| `ATO` | Resume the stream |

**Escape (`+++`).** The guard time is **more than 900 ms** of silence before the first `+`. The three `+` characters must each follow within 900 ms, and then more than 900 ms of silence must follow. Zimodem replies `OK`. It marks the connection for disconnect unless the hang-up type is "none". (Source: `processPlusPlusPlus` and `checkPlusPlusPlusEscape` in zimodem.ino, and `switchBackToCommandMode` in zstream.ino.) The README describes `+++` as "disconnect the current opened connection".

**ESP32-C3 pins in Zimodem:** DCD IO8, CTS IO3, RTS IO2, RI IO1, DSR IO4, DTR IO5, OTH/pulse IO7.

- On the TS-Pico v3 card **only TX and RX are wired**. `build.sh` adds pull-ups on DTR (IO5) and OTH (IO7).
- So DCD, RI, RTS and CTS never reach the RP2350. **Whatever the 2068 sees as DSR is made up by the card firmware** (for example from "CONNECT" and "NO CARRIER" seen on the UART) **(inferred design point)**.
- XON/XOFF is the only flow control available on the UART.

## 5. What a new program should do

Everything in this section is a recommendation. It is written to work against a real 8251 as well as against the emulation.

**Initialise**

```
OUT (77h),00h ; OUT (77h),00h ; OUT (77h),00h   ; worst-case reset (datasheet)
OUT (77h),40h                                    ; internal reset
OUT (77h),4Fh   ; mode: 8N1 x64 (or 7Bh = 7E1 x64, MTERM's default)
OUT (77h),37h   ; command: TxEN|DTR|RxE|ER|RTS  (off-hook, transmitter carrier on)
```

- A real 2050 needs ×64 (11b in bits 1:0) at its fixed clock **(inferred)**.
- Use **4Fh (8N1)** for a Zimodem session, because Zimodem's link is 8N1 and 8-bit data is useful. Use **7Bh (7E1)** if you need to match MTERM exactly. On the emulated card, the bridge should accept either.
- Don't write anything else to $77 between the reset and the mode byte.
- After the mode byte, every write to $77 is a command.

**Polling loop**

Interrupts can stay on: there is no timing dependence below 20 ms. MTERM switches them off only so its delay loops are exact.

```
loop: IN A,(77h)
      BIT 1,A ; JR Z,notx       ; RxRDY?
      AND 38h ; JR Z,ok
      LD A,37h ; OUT (77h),A    ; error reset (ER set), keep DTR/RTS
ok:   IN A,(73h) ; store in ring buffer (do NOT print inline at speed)
notx: if a key is waiting:
        wait: IN A,(77h) ; RRCA ; JR NC,wait   ; TxRDY status bit
        OUT (73h),A
      pop one char from the ring buffer, display it
      JR loop
```

- **Status bits to trust:**
  - **TxRDY (bit 0) before every data write.** It is the status bit, so it is independent of CTS and TxEN.
  - **RxRDY (bit 1) before every data read.**
  - **PE, OE and FE (bits 3–5):** clear them with a command that has ER set, and still read the byte.
  - **DSR (bit 7) as "connected", if the bridge provides it** **(inferred)**. Don't make it a hard requirement: a direct Zimodem session is in command mode with DSR possibly low. MTERM's habit of skipping TX and RX when on-hook is a policy, not a hardware rule.
- **Bits not to rely on:**
  - TxEMPTY (bit 2), except to wait before dropping DTR or RTS.
  - SYNDET/BRKDET (bit 6).
  - Exact-value comparisons like `=133`. Mask the bits you mean.
- **Throughput.** Drain RxRDY at least once per character time:
  - 33 ms at a real 300 baud;
  - possibly much faster on the card, if the bridge doesn't pace bytes **(inferred)**.
  
  So poll the receiver inside every wait, the way MTERM's delay loop does, and keep the display out of the receive path.
  - If the 2068 can't keep up, send XOFF (13h) and XON (11h) to Zimodem after `ATF1` / `AT&K4`, or use `ATDX`.
  - A real 8251 sets OE and loses the old byte if you're late.
- **Talking to Zimodem:**
  1. Send `ATE0V1X0R1` then CR. The modem's default EOL is CR LF; drop the LF on screen if needed.
  2. Join WiFi with `ATW"ssid,pass"`.
  3. Connect with `ATDT"host:port"` and wait for a line starting `CONNECT`, or `NO ANSWER` / `ERROR`.
  4. In the stream, treat a line `NO CARRIER` as a hang-up.
  5. To hang up: wait more than 1 s with no TX, send `+++`, wait more than 1 s for `OK`, then `ATH`.
- **Hang-up for a real 2050:** write the command with DTR and RTS clear, e.g. `15h` as MTERM does. On the card, the bridge may map DTR falling to Zimodem `ATH` **(design suggestion)**.
- **Pulse dialing is only for real 2050 hardware.** If you implement it, use MTERM's values:
  - break: DTR off for 58 ms;
  - make: DTR on for 48 ms;
  - inter-digit gap: 830 ms;
  - "0" = 10 pulses.
  
  On the card, prefer sending `ATDT"host:port"` or `ATD<phonebook number>` as text.

## 6. What the TS-Pico v3 card will do (planned, not built yet)

The card's side is designed in [v3-modem-proposal.md](v3-modem-proposal.md)
(PR #264). As of 2026-10-12 only the groundwork is built; check that
document for the current state before relying on any of this.

- **Two modes, switched with `SAVE "tpi:modem 2050"` / `"tpi:modem hayes"`:**
  - **2050 mode** (the default) imitates a real 2050 for unmodified
    software. DTR pulses are decoded into a number and sent to Zimodem as
    `ATDT<number>`, to be looked up in Zimodem's phonebook. Zimodem's result
    codes are kept off the data stream. DSR is driven from CONNECT and
    NO CARRIER. Clearing DTR hangs up.
  - **Hayes mode** passes every byte both ways with **DSR held at 1**. The
    program talks to Zimodem directly: `ATW`, `ATP`, `ATDT"host:port"`,
    `+++`/`ATH`, and sees its result codes.
- **For a new program written for the card, Hayes mode is the natural
  choice:** no pulse dialing, and it can show Zimodem's own messages. Set it
  once with `SAVE "tpi:modem hayes"` (or the planned `MODEM_MODE` key in
  `config.ini`). Such a program shouldn't depend on DSR going low between
  calls, since in Hayes mode it never does.
- **Received data is paced** to `MODEM_BAUD` (300 baud by default, about 30
  characters a second), as a 2050 would deliver it. A program that keeps up
  can ask for more by raising `MODEM_BAUD`. Transmit isn't paced.
- **The ESP32 is powered on demand**, when a program first resets the 8251
  (the 00h/00h/00h/40h sequence) or on `SAVE "tpi:modem on"`. Zimodem takes
  about a second to start; TxRDY stays 0 until it's ready.
- **The link to Zimodem is 8N1**, so the mode byte only sets the character
  length the 2068 sees (7 bits: bit 7 reads 0). Parity and stop bits aren't
  generated. 4Fh (8N1) gives the full 8 bits.
- **Ports:** the card decodes $73/$77 from A0–A7 only, which matches MTERM
  leaving A8–A15 undefined.
