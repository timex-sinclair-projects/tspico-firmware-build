# EXROM chunk 1 and the function chain

Source: [`tspico-21-exrom.labelled.asm`](../../rom-analysis/disasm/tspico-21-exrom.labelled.asm):
EXROM 2000h–22FDh (chunk 1 up to ROM 2.0's code), the chunk-0 helpers the
function chain uses (01C3h, 025Eh–02C6h, 045Fh–0480h, 04F1h, 05FAh,
068Eh, 06F2h, 0810h–0815h), and the printer path at 1630h–183Bh. Names
from [`docs/rom-analysis/tspico-exrom-symbols.sym`](../../rom-analysis/tspico-exrom-symbols.sym).
ROM 2.1.

When a `tpi:` command, a LOAD or a SAVE ends, the Pico's answer is one
byte. Status 1 is OK and 2–127 a report ([exrom-driver.md](exrom-driver.md#status_to_report-1bf3h));
80h and above asks the 2068 to do something first: print a message, show
pages of text and send back keys, ask a question. That is the **function
chain**, and this chapter is its code, with the two port accessors every
byte goes through, the routine that sends a command's text, the
v1.5w/v1.7 fixes that live in chunk 1, and the printer path that sends
LPRINT and COPY to the Pico. The firmware side of each function is
[../firmware/tspico-messages.md](../firmware/tspico-messages.md); the
table of codes is [PROTOCOL.md §5.4](../../PROTOCOL.md#54-the-answer-a-response-function-status--80).

**Status − 1.** C_END_TAIL (227Fh) reads the status, `AND A` (0 → no
answer, J), `DEC A`, returns on 0 (OK), and otherwise calls the chain with
A = status − 1. So every `CP nn` in the chain matches status **nn + 1**:
`CP 80h` is function 81h, `CP 85h` is 86h. This is the most common
misreading of this code, and the reason the second `CP 86h` below looked
like a bug for so long.

## Map

| EXROM | Symbol / what | Since |
|---|---|---|
| 01C3h | `READ_STATUS_AND_OPEN` | 1.1 |
| 025Eh, 026Ah | `GET_STATUS_BIT_0`, `GET_STATUS_BIT_1` | 1.1 |
| 026Fh | `FN_CHAIN_HEAD`; 0274h `FN_81_PRINT_STRING` | 1.1 |
| 02B9h | `READ_STATUS_BYTE` | 1.1 |
| 045Fh | `PRINT_STRING_FROM_PICO` (with 068Eh, 05FAh, 06F2h) | 1.1 |
| 0471h | `GET_KEY_AND_SEND` | 1.1; 2.0 (0479h) |
| 04F1h | `OPEN_MAIN_SCREEN` | 1.1 |
| 0810h, 0813h | `LOOP_EXIT_OK`, `LOOP_EXIT_ERR` | 1.1 |
| 0886h | the SAVE prompt's call to 22AEh | 1.7 |
| 1630h | `PRINTER_TABLE` and the printer path to 183Bh | 1.1 |
| 2000h | `ENTRY_TABLE`, the landing pad: `BREAK_KEY` (2009h), the `HALT_STUB_*`s | 1.1 |
| 203Fh | `BEEPER`, moved from HOME | 1.1 |
| 2082h | the printer-line helper | 1.1 |
| 208Eh–2193h | the four switch words | 1.1 ([sysvars.md](sysvars.md#5ddbh-tpmode-peek-24027)) |
| 2194h | `FN_CHAIN_C1` and functions 82h–88h | 1.1; 2.1 (2213h) |
| 2219h–223Dh | the dead beep handler; EXTINIT's helper; unreferenced stubs | 1.1 |
| 223Eh | `SEND_DATA_BLOCK_D` | 1.1 |
| 2274h | `PICO_TRANSACT` (C_END_TAIL at 227Fh) | 1.1 |
| 2294h | `ERR_9` | 1.1 |
| 2298h, 229Dh | `TSPICO_READ_DATA`, `TSPICO_WRITE_DATA` | 1.1 |
| 22A1h | `YN_LOOP_GUARD` | 1.5w |
| 22AEh–22FDh | the SAVE-prompt BREAK routine | 1.7 |

## The accessors

### `TSPICO_READ_DATA` (2298h)

`IN A,(0Eh) / AND A / RET`, then a stray `RET` at 229Ch. Every byte from
the Pico comes through here (the only other port-0Eh read in the ROM is
ROM 2.1's channel data phase, [exrom-fdd.md](exrom-fdd.md)). The `AND A`
clears carry and sets Z for a 00h, which is how the callers spot "no
answer": an empty TX FIFO reads as 00h, so a status of 0 is never a real
status.

Carry is always clear on return, so every `JR C`/`JP C` after a call to it
— there are dozens, written as if a read could fail — is never taken *(the
code cannot set it; inferred that the accessor once could, or was meant
to)*.

### `TSPICO_WRITE_DATA` (229Dh)

`OUT (0Eh),A / AND A / RET`. Every byte to the Pico. The Z80's `OUT` drops
the Pico's READY at once (the PIO's auto-busy,
[../firmware/pio.md](../firmware/pio.md#ts_io_dual)), which is why every
write that expects an answer is followed by a ready-wait. Carry always
clear, as above. ROM 2.0's tspico-sync.asm calls it TSPICO_WRITE.

## Sending a command's text

### `SEND_DATA_BLOCK_D` (223Eh)

The second half of a `'B'` transaction: entered from `BUILD_PREHEADER_B`
(and the printer path) with HL = the text and its length in 5DCDh.

1. The pre-load: `TSPICO_READ_DATA`; carry or 0 → `ERR_9`. `DEC A`;
   `WAIT_PICO_READY` (carry → `ERR_9`); `RET NZ` with A = status − 1 if the
   pre-load was not 1 — the Pico refused before the body.
2. `'D'` (44h), with D = 44h as the XOR's seed.
3. The length from 5DCDh, low then high, through `SEND_BYTE_CRC`.
4. The text from HL, each byte through `SEND_BYTE_CRC`, counting 5DCDh down
   to 0 ([sysvars.md](sysvars.md#5dcdh-a-byte-counter-and-the-thunks-hl)).
5. A = D, the XOR, and on into `PICO_TRANSACT`.

The bytes go out with no ready-wait between them: the Pico's capture
(`RX_CAPTURE`/`RxDMA`, [../firmware/tspico_io.md](../firmware/tspico_io.md))
keeps up. This is [PROTOCOL.md §5.2](../../PROTOCOL.md#52-the-body)'s
body; unlike the pre-header's, this XOR is checked by the firmware
(a mismatch is status 2, Report R).

### `PICO_TRANSACT` (2274h)

`CALL TSPICO_WRITE_DATA` (the last byte) / `JR C,ERR_9` /
`CALL WAIT_PICO_READY` (2279h) / `JP C,ERR_9`, then C_END_TAIL (227Fh):

```text
227Fh   LD C,0Eh
        CALL TSPICO_READ_DATA / JR C,ERR_9
        AND A / JP Z,ERR_9       ; 00h: no answer
        DEC A / RET Z            ; status 1: OK, A = 0, carry clear
        CALL FN_CHAIN_HEAD       ; A = status - 1
        AND A / JR NZ,2296h      ; still not OK: carry set, A = status - 1
        AND A / RET              ; a function ran and ended OK
```

So: A = 0 and carry clear for OK; carry set with A = status − 1 for a
report, or A = 09h (`ERR_9`) for no answer. 2279h was the 1.x BIOS C_END
target; ROM 2.0's BIOS_C_END and 2.1's C_END2 enter at 227Fh, after their
own waits ([exrom-sync.md](exrom-sync.md#bios_c_end-23cdh),
[exrom-fdd.md](exrom-fdd.md)). The `LD C,0Eh` is never used: C is not read
after it *(inferred: the port number, from a version that read with `IN
A,(C)`)*.

### `ERR_9` (2294h)

`LD A,09h`, then 2296h `SCF / RET`. "Internal error 9": the ROM's own
code for "the Pico did not answer", which `STATUS_TO_REPORT` turns into
Report J, not 9 STOP, because A = 9 is status − 1 for status 10
([exrom-driver.md](exrom-driver.md#status_to_report-1bf3h)).

## The function chain

### `FN_CHAIN_HEAD` (026Fh)

`CP 80h / JP NZ,FN_CHAIN_C1` — with A = status − 1, `CP 80h` is status
81h. Falls into `FN_81_PRINT_STRING`. The chain is split: the head in
chunk 0, the rest at 2194h in chunk 1.

| Status | Test (A = status − 1) | Handler | What the 2068 does |
|---|---|---|---|
| 81h | 026Fh `CP 80h` | `FN_81_PRINT_STRING` | reads its status, prints the text on the main screen |
| 82h | 2194h `CP 81h` | `FN_82_PRINT_STR_KEY` | prints, then waits for a key and sends it |
| 83h | 21A4h `CP 82h` | `FN_83_PRINT_CHAR` | prints one character |
| 84h | 21BAh `CP 83h` | `FN_84_RETURN_KEY` | waits for a key and sends it |
| 85h | 21C7h `CP 84h` | `FN_85_GET_STATUS` | sends a 2-bit keyboard/aux mask |
| 86h | 21DFh `CP 85h` | `FN_86_YN_PROMPT` | pages of text with a key between them |
| 87h | 21FDh `CP 86h` | `FN_87_PRINT_N_CHARS` | clears the screen (HOME 08A6h) |
| 88h | 2213h `CP 87h` (2.1) | LOWER_LOOP (3006h) | 86h on the lower screen |
| anything else | 2218h `RET` | — | back with A unchanged: STATUS_TO_REPORT gives D |

Every handler first reads **one more byte, its own status**
(`READ_STATUS_BYTE`), which becomes the result of the whole command when
the function ends. The firmware uses 81h, 86h and 88h; 82h–85h and 87h are
in the ROM and unused ([../firmware/tspico-state.md](../firmware/tspico-state.md#the-protocol-bytes)).
A code of 80h or 89h–FFh falls off the end: Report D, with whatever the
Pico queued behind it left unread.

### `FN_81_PRINT_STRING` (0274h)

`CALL READ_STATUS_BYTE / CALL OPEN_MAIN_SCREEN / JP PRINT_STRING_FROM_PICO`,
then three `NOP`s. The text goes to the main screen (stream FEh), starting
wherever the print position is; the firmware starts its messages with a CR
([../firmware/tspico-messages.md](../firmware/tspico-messages.md#send_msgmsg-msg1-st-forcedisplayfalse)).

### `READ_STATUS_BYTE` (02B9h)

`CALL TSPICO_READ_DATA` / carry → 192Fh / `AND A` / 0 → 192Fh / `DEC A /
RET Z` / `SCF / RET`. Returns Z (and A = 0) for status 1; carry set with A =
status − 1 otherwise. 192Fh drops two stack levels and then
(1931h) `AND A / RET Z / JP STATUS_TO_REPORT`: A is 0 there (it came from
the 00h), so it returns two levels up without a report — a function code
with no status byte behind it ends quietly *(inferred from the code; the
firmware always sends one)*. The handlers push AF after
this call and pop it last, so the flags and A they return are this status's.
`fddcmd.asm`'s `READ_STATUS` EQU names this address
([exrom-driver.md](exrom-driver.md#read_status-0655h)).

### `READ_STATUS_AND_OPEN` (01C3h)

`CALL READ_STATUS_BYTE / JP OPEN_MAIN_SCREEN`: function 86h's opening, and
the first half of what ROM 2.1's LOWER_LOOP reuses (anchored by
`build-rom.py`).

### `OPEN_MAIN_SCREEN` (04F1h)

`PUSH AF / LD A,FEh / CALL 0426h / POP AF / RET`: open stream FEh (−2, the
main screen, "S") through HOME's CHAN-OPEN (0426h is the CALL_HOME
preamble for HOME 1230h). AF is kept, so the status survives. Printing
through RST 10 then goes to the screen whatever stream the statement was
using — which is why ROM 2.1's channel commands must never get a printed
answer ([../firmware/tspico-bus.md](../firmware/tspico-bus.md#ch_replyst)).

### `PRINT_STRING_FROM_PICO` (045Fh)

Prints bytes from the Pico until a terminator.

```text
045Fh   PUSH AF                  ; the caller's status
        JR 0465h
0462h   CALL 05FAh               ; print A
0465h   CALL 068Eh               ; read a byte and classify it
        JR C,046Dh               ; 80h or more: the end
        JP 06F2h
06F2h   JP Z,046Dh               ; 00h: the end
        CP 03h
        JP Z,21FAh               ; 03h: the end of an 86h loop
        JP 0462h                 ; anything else: print it
046Dh   POP AF / AND A / RET     ; carry clear
```

- **068Eh**: `CALL TSPICO_READ_DATA / AND A / RET Z / CP 80h / CCF /
  RET`: Z for 00h, carry for 80h and above.
- **05FAh**: `LD (IY+52h),FFh` — SCR_CT, so the 2068 never stops with its
  own "scroll?" prompt — then `JP 030Ch`, HOME's `RST 10h` through
  CALL_HOME.
- **21FAh**: `POP AF / SCF / RET` — pops this routine's saved AF and
  returns to the caller with carry set. In function 86h that ends the loop
  (below); in 81h or 82h it ends the text the same way as 00h, as far as
  the caller can tell.

So the text rules the firmware keeps ([../firmware/tspico-messages.md](../firmware/tspico-messages.md#the-answer-on-the-wire)):
each byte is read **with no ready-wait** — `RST 10h` is slow enough that a
Pico with the bytes queued keeps ahead; 00h ends a string; **any byte of
80h or more ends it too**, so keyword tokens and UDGs cannot be sent; 03h
ends an 86h loop. Control codes pass to `RST 10h`, which takes their
parameters from the following bytes. An empty TX reads 00h and silently
ends the text — the bug the firmware's "data before READY" rule exists to
prevent.

### `GET_KEY_AND_SEND` (0471h)

```text
0471h   CALL 03C1h               ; HOME KEY-SCAN: DE = FFFFh when no key
        INC DE / LD A,D / OR E
        JR NZ,0471h              ; wait until every key is released
0479h   CALL KEYWAIT             ; 2.0: BREAK test, then POLL_KEYPRESS
        JR Z,0479h               ; wait for a key
        JP SEND_KEY              ; wait for READY, OUT (0Eh) the key
```

Waits for the keyboard to be clear (so the key that answered the last
prompt is not taken again), then for a key, then sends it — after a
ready-wait, so the Pico has finished sending the page
([exrom-driver.md](exrom-driver.md#send_key-1c40h)). Returns A = the key:
LAST_K as the 2068's keyboard routine leaves it, upper case for letters
*(per [PROTOCOL.md §5.4](../../PROTOCOL.md#54-the-answer-a-response-function-status--80);
the firmware compares only upper case)*. In 1.x 0479h was `CALL
POLL_KEYPRESS` directly and BREAK could not end a prompt; ROM 2.0's
KEYWAIT adds the test and the abort ([exrom-sync.md](exrom-sync.md#keywait-2346h)).

### `LOOP_EXIT_OK` (0810h) and `LOOP_EXIT_ERR` (0813h)

`LOOP_EXIT_OK`: `CALL 05FAh` (print A — the `N` the user typed), then
falls into `LOOP_EXIT_ERR`: `POP AF / RET`, the function's status back.
Both are function 86h's exits; "ERR" is a misnomer — 0813h is also the
normal end of the loop on 03h.

### `FN_CHAIN_C1` (2194h)

`CP 81h / JR NZ,21A4h`: the chain's second link, in chunk 1. Each
following link is the same shape (`CP n / JR NZ,next`) at 21A4h, 21BAh,
21C7h, 21DFh, 21FDh, 2213h.

### `FN_82_PRINT_STR_KEY` (2198h)

`READ_STATUS_BYTE`, `OPEN_MAIN_SCREEN`, `PRINT_STRING_FROM_PICO`, then
21C1h: `PUSH AF / CALL GET_KEY_AND_SEND / POP AF / RET`. One string, one
key back. Unused by the firmware.

### `FN_83_PRINT_CHAR` (21A8h)

`READ_STATUS_BYTE / PUSH AF`, then 21B1h: `OPEN_MAIN_SCREEN /
TSPICO_READ_DATA / JP 05FAh` (print it), `POP AF / RET`. One character,
read without a wait. Unused.

### `FN_84_RETURN_KEY` (21BEh)

`READ_STATUS_BYTE`, then 21C1h (above): a key, sent. Unused.

### `FN_85_GET_STATUS` (21CBh)

`READ_STATUS_BYTE / PUSH AF / PUSH HL`; L = `GET_STATUS_BIT_0`; A =
`GET_STATUS_BIT_1` × 2 OR L; `TSPICO_WRITE_DATA` — **with no ready-wait**
before it; `POP HL / POP AF / RET`. Unused by the firmware.

#### `GET_STATUS_BIT_0` (025Eh)

HOME's KEY-SCAN (through 03C1h): A = 1 when **no** key is down (DE =
FFFFh), 0 when one is. So bit 0 of the mask is "keyboard idle", not "a key
is pressed" *(the meaning of the bit is the code's; no document defines
it)*.

#### `GET_STATUS_BIT_1` (026Ah)

Three `NOP`s, `XOR A / RET`: always 0. The "aux" bit was never
implemented.

### `FN_86_YN_PROMPT` (21E3h)

The function the firmware uses for everything longer than a line: listings
in pages, menus, Y/N questions
([../firmware/tspico-messages.md](../firmware/tspico-messages.md)).

```text
21E3h   CALL READ_STATUS_AND_OPEN   ; its status; the main screen
21E6h   PUSH AF                     ; (LOOP_BODY, which LOWER_LOOP reuses)
21E7h   CALL PRINT_STRING_FROM_PICO ; a page, up to 00h or 03h
        JP C,LOOP_EXIT_ERR          ; 03h: the end, no key
        CALL GET_KEY_AND_SEND       ; a key, after a ready-wait
        AND 5Fh / CP 'N'
        JP NZ,YN_LOOP_GUARD         ; not N: the next page
        JP LOOP_EXIT_OK             ; N: print it, end
```

Returns the function's own status (from the `PUSH AF`). The firmware's side
of every step — the page in TX before READY, the key, READY again after the
next page's first bytes — is [../firmware/tspico-messages.md](../firmware/tspico-messages.md#the-answer-on-the-wire).
On `N` the ROM leaves the loop without waiting for READY and reads nothing
more, so the firmware sends nothing after an `N`. Letters are compared after
`AND 5Fh`, so `n` would do as well as `N`.

#### `YN_LOOP` (21E7h)

The loop's head, the target of the guard's `JP`.

#### `YN_LOOP_GUARD` (22A1h)

`CALL WAIT_PICO_READY / JR C,22A9h / JP YN_LOOP`; 22A9h: `POP AF / LD
A,09h / SCF / RET` — a timeout is J. This is v1.5w's whole change (15
bytes, two hunks, [DIFF_V11_vs_V15W.md](../../rom-analysis/DIFF_V11_vs_V15W.md)):
in v1.1, 21F4h was `JP NZ,YN_LOOP`, so the Z80 sent the key and then read
the next page at once, before the Pico had had time to put it in TX — an
empty FIFO read as 00h, an empty page, a broken listing. The guard makes it
wait for READY. With the dual-port firmware this is also what the
firmware's "data in TX first, then READY" relies on.

### `FN_87_PRINT_N_CHARS` (2201h)

`READ_STATUS_BYTE / PUSH AF / CALL 220Ah / POP AF / RET`, and 220Ah is
`CALL_HOME` to HOME 08A6h. The name is the original specification's
("print n characters"); what the code does is call HOME 08A6h, which clears
the screen as CLS does ([PROTOCOL.md §5.4](../../PROTOCOL.md#54-the-answer-a-response-function-status--80)).
Unused.

### `FN_DEAD_BEEP` (2216h)

In v1.1–2.0, 2213h was a second `CP 86h / RET NZ` and 2216h `CALL 02B9h`
then a beep: unreachable, because 21FDh's `JR NZ` had already taken every
A that was not 86h, so A could never be 86h at 2213h — the "duplicate
`CP 86h`" of [PROTOCOL_FROM_ROM.md](../../rom-analysis/PROTOCOL_FROM_ROM.md#bug-the-second-cp-86h-is-unreachable).
ROM 2.1 rewrote 2213h–2218h as `CP 87h / JP Z,3006h / RET`: status 88h now
goes to LOWER_LOOP, function 86h on the lower screen
([exrom-fdd.md](exrom-fdd.md)). 2216h is now inside that `JP Z`; the old
handler's tail, 2219h–221Eh (`PUSH AF / CALL BEEPER / POP AF / RET`), is
still there and unreferenced.

## The landing pad at 2000h

### `ENTRY_TABLE` (2000h)

Not an API table, despite its look:

| EXROM | Bytes | What |
|---|---|---|
| 2000h | `JP 203Fh` | BEEPER's entry: HOME's BEEPER thunk calls 2000h (in 1.x directly; in 2.1 the module's G_BEEP does) |
| 2003h, 2006h | `HALT_STUB_2003`, `HALT_STUB_2006` | `JP` to itself |
| 2009h | `BREAK_KEY` | address-pinned (below) |
| 201Eh–2026h | dead | `LD A,20h / OUT (0Fh),A / XOR A / OUT (0Fh),A / POP AF / RET`, after `BREAK_KEY`'s `RET`, reached by nothing |
| 2027h–203Ch | `HALT_STUB_2027` … `HALT_STUB_203C` | `JP` to itself |

| Symbol | EXROM |
|---|---|
| `HALT_STUB_2003` | 2003h |
| `HALT_STUB_2006` | 2006h |
| `HALT_STUB_2027` | 2027h |
| `HALT_STUB_202A` | 202Ah |
| `HALT_STUB_202D` | 202Dh |
| `HALT_STUB_2030` | 2030h |
| `HALT_STUB_2033` | 2033h |
| `HALT_STUB_2036` | 2036h |
| `HALT_STUB_2039` | 2039h |
| `HALT_STUB_203C` | 203Ch |

The ten stubs are padding that keeps 2009h where it must be, written to
hang (a `JP` to itself) rather than run into garbage if anything ever
jumps there. The dead `OUT (0Fh)` pair would, if it ran, be read by
firmware 2.0 and later as SYNC/BREAK
([overview.md](overview.md#where-the-rom-touches-ports-0eh-and-0fh)).

### `BREAK_KEY` (2009h)

A copy of HOME's BREAK-KEY at the same address: `LD A,7Fh / IN A,(FEh) /
RRA / RET C` (SPACE not down), then `BIT 6,(IY+7Dh)` — carry set (no
break) when that flag is set — then the CAPS SHIFT row: carry clear = BREAK.
It has to be at 2009h because the stock printer code that moved into the
EXROM (17DCh onwards, below) still contains `CALL 2009h`, copied verbatim
from HOME, where 2009h is BREAK-KEY. Called only from 17E5h in the EXROM;
HOME's own 1AB9h reference is to HOME's copy. Not to be confused with the BREAK_KEY of
`tspico-zx48-v3.asm`, the Spectrum ROM's routine at 1F54h
([zx48.md](zx48.md)), nor with `fddcmd.asm`'s BEEPER, which is 2000h, the
`JP` in front of this one.

The flag at 5CB7h bit 6: [ERROR_TRAPPING.md](../../rom-analysis/ERROR_TRAPPING.md)
reads it as "an `ON ERR` trap was taken", the v1.7 review as a break
inhibit; whichever it is, while it is set BREAK is not seen here or by
v1.7's prompt test (22F0h).

### `BEEPER` (203Fh)

The genuine HOME BEEPER, moved here by v1.1 to make room for the returning
thunk in HOME; identical but for its two `IX` operands, rebased to 205Bh
and 2060h ([home.md](home.md#03f3h0420h-beeper-moved-out)). Entered with HL
= the pitch and DE = the duration, as on a stock 2068; reads BORDCR to keep
the border colour; ends `EI / RET`. Callers: 2000h, and 221Ah in the dead
handler.

## Smaller pieces of chunk 1

- **2082h**: `DEC HL / LD (HL),80h`, then HOME 0A35h through CALL_HOME
  (clear the printer buffer). Called from 0AD4h in chunk 0.
- **208Eh–2193h**: `tpi:tape`, `tpi:sdcard`, `tpi:picopt`, `tpi:ts2040`,
  reached from SESSION_SETUP ([sysvars.md](sysvars.md#5ddbh-tpmode-peek-24027),
  [exrom-driver.md](exrom-driver.md#session_setup-1a73h-is-this-name-a-command)).
- **221Fh**: EXTINIT's helper: TPMODE = 2 (081Dh), `CALL 096Ch`, clear
  5CBEh and 6315h ([sysvars.md](sysvars.md#the-2068s-ram-code)).
- **222Dh–223Dh**: three fragments with no reference to them in either ROM:
  `LD A,80h / LD (5EF6h),A / RET`; `XOR A / OUT (0Fh),A / RET`; `LD A,01h /
  JP 192Fh`. Each is preceded by a stray `RRCA` byte *(likely leftovers of
  removed code; inferred)*.

## The SAVE prompt and BREAK (v1.7, 22AEh–22FDh)

Stock SAVE prints "Start tape, then press any key" and waits; on the
TS-Pico the "tape" is the Pico, and v1.1–v1.5w noticed a BREAK there only
after the 17-byte header had gone to the Pico, which then had to time out
of a half-finished transaction. v1.7 tests for BREAK **before** anything
is sent. The call site, 0886h:

```text
0886h   CALL 22AEh
        JR C,088Dh               ; no BREAK: on with the SAVE (0893h: SA-BYTES)
        RST 8 / DEFB 0Ch         ; Report D
```

22AEh: `SET 5,(IY+2)` (TV_FLAG: clear the lower screen at the next key);
`SCF`; save AF, BC, DE; a delay loop of 40 000 passes; wait until any key
is down (all rows, `IN A,(FEh)` with A = 0); 12 `HALT`s (about a quarter
of a second); then `CALL 22F0h`:

```text
22F0h   BIT 6,(IY+7Dh) / JR Z,22F8h
        SCF / RET                ; the flag set: never a BREAK
22F8h   LD A,7Fh / IN A,(FEh) / RRA / RET   ; carry clear = SPACE down
```

No BREAK → `JP C,08BEh`, the stock code's continuation. BREAK → `CALL
22E7h` (HOME 08A9h), restore DE, BC, AF, `POP HL` (the return address) /
`EX (SP),HL` (drop the data pointer and put the return address back),
restore the border from BORDCR, `AND A` (carry clear), `EI / RET` →
0889h's `JR C` not taken → Report D. SPACE alone is the BREAK, as it is
everywhere else on the tape path; the first v1.7 build required CAPS
SHIFT as well and broke the stack, which the shipped build fixed
([REVIEW_ROM_V17_SAVE_BREAK.md](../../rom-analysis/REVIEW_ROM_V17_SAVE_BREAK.md) §10).
ROM 2.0 adds a SYNC at the start of every transaction, so even a BREAK
that slips past this leaves the Pico able to recover.

## The printer path (1630h–183Bh)

### `PRINTER_TABLE` (1630h)

Five `JP`s at a fixed address, the EXROM ends of HOME's printer hooks
([home.md](home.md#0a02h0a2fh-copy-the-character-router-copy-buff)):

| EXROM | Jumps to | From HOME | What |
|---|---|---|---|
| 1630h | 1781h | 0A02h | COPY |
| 1633h | 17C3h | 0A4Ah | COPY-LINE |
| 1636h | 17CDh | 04F8h ← 0A23h | COPY-BUFF |
| 1639h | 1668h | 04F2h ← 0A1Dh | one LPRINT/LLIST character to the Pico |
| 163Ch | 180Fh | 0A26h | a UDG to the Pico |

The genuine 8K EXROM had zeros here.

**COPY (1781h).** TPMODE bit 0 set (`tpi:picopt`): 16F3h, a COPY to the
Pico; a carry back is Report J, a non-zero A goes to `STATUS_TO_REPORT`
(so the firmware's status 2 is Report R). Clear: the stock COPY, moved here
from HOME's K_DUMP unchanged (1794h: 176 lines through COPY-LINE to a ZX
Printer on port FBh). Both end at 17B3h → HOME 0A30h (the stock tail:
printer motor off, `EI`, clear the buffer).

**16F3h, the COPY transaction**: SYNC and `'B'`; TADDR from T_ADDR's
low byte (D8h → 4, DBh → 5, DEh → 6: the screen mode as the stock code
encodes it, [PROTOCOL.md §8](../../PROTOCOL.md#8-printer-transactions));
BANK; from port FFh the screen mode (bits 0–2) and, for the hi-res colour
modes, a colour byte from the table at 16EBh (`07 16 43 52 25 34 61 70`,
indexed by bits 3–5); the mode (6 sent as 3); PMR2; the length, 1B00h
(6912) for a normal screen or 3B00h (15104) for the larger one, also put
in 5DCDh; the XOR; then `SEND_DATA_BLOCK_D` from 4000h. The firmware turns
the body into a BMP ([../firmware/tspico-dispatch.md](../firmware/tspico-dispatch.md#print_iopre)).

**COPY-LINE (17C3h) and COPY-BUFF (17CDh)** are the stock routines moved
from HOME unchanged: they clock pixel lines into a ZX Printer on port FBh
(17DCh–180Eh, the loop with the `CALL 2009h` that pins BREAK_KEY). 17CDh
prints the printer buffer at 5B00h, 8 lines. **Nothing here goes to the
Pico**: with `tpi:picopt`, characters reach the Pico one by one through
1639h, and COPY-BUFF, still called at the end of each LPRINT line, finds
no ZX Printer (17EFh: `IN A,(FBh) / ADD A,A / RET M`) and returns *(that a
2068 with no ZX Printer reads bit 6 set on port FBh is inferred from the
stock code's test)*. A real ZX Printer on the expansion bus still works
for COPY and LPRINT with `tpi:ts2040`.

**One character (1668h).** Entered from HOME's router with A = the
character (below 80h; or 80h–8Fh with its pattern built at MEMBOT; UDGs
come through 180Fh):

1. 164Dh: SYNC_WRITE `'B'` (D = the XOR); TADDR 5 (also stored in 5DD9h);
   BANK.
2. The character (PMR1 low), then 1 (below 80h, L = 0: no body) or 2 (80h
   and above, L = 8: an 8-byte pattern follows) as PMR1 high.
3. PMR2 low: flags — 10h from TV_FLAG bit 4 (5C3Ch: AUTOLIST, a listing),
   bit 0 if FLAGS bit 4 is set, bit 1 if FLAGS2 (5C6Ah, `IY+30h`) bit 1 is
   set; PMR2 high: ATTR_P (5C8Dh). *(The firmware's `PRINT_IO` uses only
   the character and the length; what each flag bit means to the printer
   is not documented in the code.)*
4. The length L, 0, and the XOR.
5. With a pattern: `SEND_DATA_BLOCK_D` from 5DD7h (MEMBOT for block
   graphics, the UDG's 8 bytes for 180Fh). Without: 1828h — read the
   pre-load (0 → 0414h, not 1 → 0416h, the stock error exits), then
   `WAIT_PICO_READY`.
6. A report → 1BF2h. Then back to HOME 0A35h through the no-return thunk
   (08E4h), with one extra stack level dropped for TADDR 5.

**A UDG (180Fh)**: `(char − 90h) × 8 + UDG` → 5DD7h, then 1668h with
the character.

Every character is a whole transaction, SYNC included — about as slow as
it sounds, which is why the firmware buffers the text and writes it out in
blocks ([../firmware/printer.md](../firmware/printer.md),
[../flows/printer.md](../flows/printer.md)).

## Where comments, documents and the code disagree

Logged in [REFERENCE-FOLLOWUPS.md](../../../REFERENCE-FOLLOWUPS.md).

- [rom/home.md](home.md) said, until this chapter was written, that HOME's
  COPY-BUFF hook flushes a line to the Pico; 17CDh is the stock ZX Printer
  routine (corrected there).
- `FN_87_PRINT_N_CHARS`'s name (from the original specification) does not
  describe the code, which clears the screen.
- `LOOP_EXIT_ERR` is also the normal end of an 86h loop.
- `FN_DEAD_BEEP` (2216h) names an address that in 2.1 is the middle of an
  instruction.
