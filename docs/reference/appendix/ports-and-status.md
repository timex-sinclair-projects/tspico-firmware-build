# Ports, status bits and codes

The numbers of the protocol on two pages, each with a pointer to the chapter
that explains the code behind it. The byte-level narrative is
[PROTOCOL.md](../../PROTOCOL.md); the Z80 side of every number is in the
[ROM chapters](../rom/overview.md) and the Pico side in the
[firmware chapters](../firmware/tspico_io.md).

## The two ports

| Port | Z80 `IN` returns | Z80 `OUT` does | Where |
|---|---|---|---|
| 0Eh (14) | the next byte of the Pico's TX FIFO, or 00h when it is empty | puts the byte in the RX FIFO as a 9-bit word with bit 8 = 0 | [pio.md](../firmware/pio.md) `TS_IO_DUAL` |
| 0Fh (15) | the status byte: the PIO's Y register, which no read consumes | puts `0x100 | value` in the RX FIFO; the firmware treats any such write as SYNC / abort | [pio.md](../firmware/pio.md), [tspico_io.md](../firmware/tspico_io.md) `RX_CAPTURE`, `PORT_0F` |

Both FIFOs are four entries deep and not joined (`TX_DEPTH`). The Pico cannot
hold the Z80 up: there is no /WAIT. A read of an empty TX returns 00h, which
the ROM reads as "no answer" (Report J); a write into a full RX is dropped.

Data goes through two accessors, 2298h (`IN A,(0Eh)`) and 229Dh
(`OUT (0Eh),A`), and status through READ_STATUS (0655h, the `IN A,(0Fh)` at
065Bh); the SYNC/BREAK layer adds the SYNC and BREAK writes and its own status reads at
2304h–23C0h, and the disk module one IDLE poll at 3662h. Every site is listed in
[rom/overview.md](../rom/overview.md#where-the-rom-touches-ports-0eh-and-0fh).

## The status byte

| Bit | Name | Meaning |
|---|---|---|
| 6 | READY | 1 = the answer is queued, or the Pico is ready for the next phase. The only bit ROM 1.1 tests. |
| 3 | IDLE | 1 = no transaction is open |
| 2 | RECOVERED | 0 = the Pico gave up on a transaction by itself (active low); the next SYNC clears it |
| 7, 5, 4, 1, 0 | — | unused; read as 1 |

The firmware writes four values ([tspico_io.md](../firmware/tspico_io.md)
`MQ_STATUS`, [tspico-bus.md](../firmware/tspico-bus.md) `MQ_READY`,
`MQ_BUSY`, `CH_READY`):

| Value | Name | Meaning |
|---|---|---|
| FFh | idle | READY + IDLE: between transactions; what `MQ_READY()` sets; what old firmware always showed |
| F7h | mid | READY, transaction still open: before a command body is captured; `CH_READY()`'s answer |
| FBh | recovered | READY + IDLE with bit 2 low |
| 00h | busy | the PIO writes it after every Z80 OUT (auto-busy); `MQ_BUSY()` writes it too |

Old firmware returned FFh always, so the IDLE and RECOVERED tests of the ROM
never misfire on it. Test RECOVERED only once READY is set: busy has bit 2
clear as well.

## Timing

| What | Pace | Where |
|---|---|---|
| Z80 OUTs inside a block (pre-header, body, SAVE data) | one every ~30 µs (~43 µs in SAVE data), no handshake | [exrom-driver.md](../rom/exrom-driver.md), [exrom-chunk1.md](../rom/exrom-chunk1.md) |
| Z80 reads inside a LOAD block | one every ~44–50 µs, no handshake | [tspico_io.md](../firmware/tspico_io.md) `LOAD_TS`, `STREAM_DMA` |
| `tpi:chrd` data phase | one read every ~75 µs | [exrom-fdd.md](../rom/exrom-fdd.md) `CH_FETCH` |
| Pico gives up on a half-received pre-header or body | 1 s of silence | `RX_CAPTURE`, `RX_BLOCK` |
| Pico gives up on command output nobody reads | 10 min (`CMD_STALL_MS`); a key wait: a day (`KEY_WAIT_MS`) | [tspico-state.md](../firmware/tspico-state.md) |
| The ROM's ready wait | 226 polls, each through the debounced BREAK scan: ~19.9 s, at least 88 ms per call | [exrom-driver.md](../rom/exrom-driver.md) `WAIT_PICO_READY` |
| SYNC wait | 65536 polls, ~1.05 s | [exrom-sync.md](../rom/exrom-sync.md) `SYNC_WAIT` |
| ZX48 `WAIT_RDY` | 4 × 65536 polls, ~3.8 s | [zx48.md](../rom/zx48.md) |

## The pre-header

Ten bytes open every transaction. Byte 0 picks the kind
([tspico-dispatch.md](../firmware/tspico-dispatch.md) `TS2068_IO`):

| pre[0] | pre[1] (TADDR) | Kind | Pico handler |
|---|---|---|---|
| 00h | 0 | SAVE header block | `SAVE_TS` |
| 00h / FFh | 1–3 | LOAD / VERIFY / MERGE block | `LOAD_SERVE` → `LOAD_TS` |
| 00h / FFh | ≥ 10 | headerless LOAD | `LOAD_SERVE` |
| 42h `'B'` | 4, 5, 6 | printer: COPY (4, 6), one LPRINT character (5) | `PRINT_IO` |
| 42h `'B'` | 0 | `SAVE "tpi:…"`: a command | `PROCESS_CMD` → `SA_funct` / `EXT_SA_FUNCT` |
| 42h `'B'` | 1–3 | `LOAD "tpi:name"`: mount | `PROCESS_CMD` → `LOAD_TPI` |
| anything else | — | unrecognised: FIFOs emptied, one 01h staged, status FBh | `MQ_TO_IDLE(recovered=True)` |

| Byte | Command (`'B'`) | Block (00h / FFh) |
|---|---|---|
| 0 | `'B'` | flag: 00h header, FFh data |
| 1 | TADDR (0 SAVE, 1 LOAD, 2 VERIFY, 3 MERGE) | TADDR |
| 2 | 23h, the ROM's version (the firmware's `rom_id`; FFh before ROM 2.3) | bank |
| 3–4 | PMR1: the first `CODE` number, little-endian | session id |
| 5–6 | PMR2: the second `CODE` number | address (IX) |
| 7–8 | length of the command text | block length (DE) |
| 9 | XOR of bytes 0–8, not checked for commands | XOR of bytes 0–8 |

The firmware names byte 0's values `PRE_HEADER` (00h), `PRE_DATA` (FFh) and
`PRE_CMD` (42h); `PARAMS(pre)` returns (PMR1, PMR2). The ROM builds the
command pre-header in `BUILD_PREHEADER_B` (1BA0h) and the block pre-headers
in the patched tape routines ([exrom-driver.md](../rom/exrom-driver.md),
[exrom-chunk1.md](../rom/exrom-chunk1.md)).

## The command body

```
'D' (44h), LEN lo, LEN hi, text[0..LEN-1], XOR
```

The XOR covers `'D'` through the last text byte and the Pico checks it
(status 2, Report R, on a mismatch). The text starts with `tpi:` in any
case; the command word is the text up to the first space, upper-cased
(`"TPI:DIR"`); `getArgs(cmd)` gives the rest. From BASIC the ROM sends only
names of 6–31 characters; the disk module enters past that gate
(`SESSION_NAMED`, 1AACh); a machine-code client has a 16-bit LEN.

`tpi:tape`, `tpi:sdcard`, `tpi:picopt` and `tpi:ts2040` never reach the Pico:
the ROM sets TPMODE (5DDBh) itself (bit 1: LOAD/SAVE go to the Pico; bit 0:
printing goes to the Pico) — [sysvars.md](../rom/sysvars.md).

## Status codes and reports

The ROM reads one byte after READY. 0 is "no answer" (Report J). 1 is OK.
Anything ≥ 80h is a response function (next table). Everything else goes to
`STATUS_TO_REPORT` (1BF3h) with A = status − 1
([exrom-driver.md](../rom/exrom-driver.md)):

| Status | A at 1BF3h | Report | ERR_NR | Firmware name | ROM target |
|---|---|---|---|---|---|
| 0 | internal 9 | J Invalid I/O device | 12h | — (an empty FIFO) | 1C21h |
| 1 | 0 | OK | — | `_1_OK` | 1C23h `STATUS_OK` |
| 2 | 1 | R Tape loading error | 1Ah | `_2_R_Tape_load` | 1C3Eh |
| 3 | 2 | F Invalid file name | 0Eh | `_3_F_Invalid_file` | 1C39h |
| 4 | 3 | Q Parameter error | 19h | `_4_Q_Parameter` | 1C3Ch |
| 5 | 4 | C Nonsense in BASIC | 0Bh | `_5_C_Nonsense` | 1C35h |
| 6 | 5 | 6 Number too big | 05h | `_6_6_Num2Big` | 1C16h |
| 7 | 6 | 8 End of file | 07h | `_7_8_EOF` | 1C18h |
| 8 | 7 | A Invalid argument | 09h | `_8_A_Invalid_arg` | 1C1Ch |
| 9 | 8 | 9 STOP statement | 08h | `_9_9_STOP` | 1C1Ah |
| 10 | 9 | J Invalid I/O device | 12h | `_10_J_Invalid_IO` | 1C21h |
| 11–127 | ≥ 10 | D BREAK - CONT repeats | 0Ch | `_11_D_Break` | 00F8h |
| READY with bit 2 low | — | T TS-Pico reset, try again | 1Ch | — | `RD_STATUS` |

The ROM's BIOS `C_END` returns these on failure with carry set: A = status − 1
for an error status, 09h for a timeout, 0Ch for
BREAK, 1Ch for a Pico reset ([exrom-fdd.md](../rom/exrom-fdd.md) `C_END2`).

## Response functions

A first byte ≥ 80h asks the 2068 to do something. Each function first reads
one more byte, its own status, which becomes the command's result. The
dispatch compares A = code − 1 ([exrom-chunk1.md](../rom/exrom-chunk1.md)).

| Code | Firmware name | Bytes after the code | The 2068 | Sent by |
|---|---|---|---|---|
| 81h | `FN_PRINT_STRING` | status, text, 00h | prints the text on the main screen | `SEND_MSG` |
| 82h | `FN_PRINT_STRING_KEY` | status, text, 00h; then a key comes back | prints, waits for a key, sends it | unused |
| 83h | `FN_PRINT_CHAR` | status, one character | prints it | unused |
| 84h | `FN_RETURN_KEY` | status | waits for a key, sends it | unused |
| 85h | `FN_GET_STATUS` | status | sends a 2-bit mask, with no ready wait: b0 = 1 when no key is down, b1 (aux) always 0 | unused |
| 86h | `FN_PRINT_LOOP` | status, then pages: text, 00h → a key comes back (every key, `N` included, goes round the loop, #227; a digit at a Scroll? prompt sets the page length); 03h ends the loop | the paged display | `SEND_MSG2`, `ListMenu`, `PROMPT_EACH`, `SEND_MSG_PROMPT_YN` |
| 87h | — | status | HOME 08A6h: clears the screen | unused |
| 88h | `FN_PRINT_LOOP_LOWER` | as 86h | 86h on the lower screen (`LOWER_LOOP`, 334Fh) | `SEND_MSG_PROMPT_YN(..., lower=True)`, after `tpi:fopen` |
| 80h, 89h–FFh | — | — | fall through the chain: Report D | — |

Text rules: the ROM reads characters without a ready wait; 00h ends a string
and 03h a loop, and nothing else does; control codes 16–23 (INK … TAB)
consume the bytes after them, which `PS_READ` passes through whatever they
are (#228; ROM 2.2 also stopped on any byte ≥ 80h, and on a 00h or 03h
value). `STR_END` is 00h and `LOOP_END` is 03h in the firmware. Keys come
back as typed after a ready wait (`SEND_KEY`, 1C40h; #227).

## The BIOS table (EXROM 1840h)

| Entry | Name | Contract |
|---|---|---|
| 1840h | G_MODE | BC = TPMODE (low nibble); AF kept |
| 1842h | S_MODE | TPMODE := A AND 0Fh; AF kept |
| 1844h | G_VERS | BC = the version: 0022h on ROM 2.2 (0015h on ROM 1.1) |
| 1846h | TX_A | `OUT (0Eh),A`; no wait |
| 1848h | RX_A | `IN A,(0Eh)`; Z if 0; no wait |
| 184Ah | C_END | wait READY, read the answer, run the response functions; NC = status 1 |
| 184Ch | WF_NPH | wait READY (~19.9 s); NC = ready; C with A = 02h timeout, 0Ch BREAK, 1Ch RECOVERED |

Full contracts: [exrom-driver.md](../rom/exrom-driver.md).

## LOAD and SAVE blocks

```
LOAD   OUT flag, TADDR, BANK, SESSION lo/hi, IX lo/hi, DE lo/hi, XOR
       IN  01 (pre-load)              wait READY
       OUT flag (echo 1)
       IN  flag, DE bytes, XOR         ~47 µs a byte, no handshake
       OUT computed XOR (echo 2)       wait READY
       IN  final status                01, then the next pre-load 01

SAVE   OUT 00, 0, BANK, SESSION, IX, DE, XOR      IN 01   wait READY
       OUT 00, SESSION lo/hi, 17 header bytes, XOR
       wait READY; IN mid status       01, or 03 (F) / 08 (A): refused
       ~1 s pause
       OUT FF, SESSION lo/hi, DE bytes, XOR       no pre-header
       wait READY; IN final status     the SD write, then 01 (0A, J, if it failed) + the pre-load
```

The block XOR covers the flag and the content, not the session bytes, so a
TPI block is a TAP block. A SAVE is refused at the mid status or not at all.
Firmware: [tspico_io.md](../firmware/tspico_io.md) `LOAD_TS`, `SAVE_TS`;
ROM: [exrom-driver.md](../rom/exrom-driver.md) (1879h, 196Dh).

## The channel commands

| Text | PMR1 | PMR2 | Answer |
|---|---|---|---|
| `tpi:chopen <mode> <path>` | stream | record length (0 = a stream, 1–254) | a bare status, `CH_REPLY` |
| `tpi:chopen r d:<pattern>` | stream | 0 | a bare status; the channel reads a listing |
| `tpi:chwr <hex>` | stream | 0 | a bare status |
| `tpi:chrd` | stream | bytes wanted (1–255; 0 = 255) | the data phase: status (1 data, 7 end of file), n, n bytes, XOR |
| `tpi:chclose` | stream | 0 | a bare status |

Modes `r`, `w`, `a`, `u`, each with an optional `b`. Byte 17h in a write is
always the TAB escape `17h, n lo, n hi`. Firmware:
[tspico-disk.md](../firmware/tspico-disk.md), [channels.md](../firmware/channels.md);
ROM: [exrom-fdd.md](../rom/exrom-fdd.md).

## The printer

TADDR 5 carries one LPRINT/LLIST character in PMR1's low byte and no body.
TADDR 4 and 6 are COPY with a body (`'D'`, length, screen data, XOR) and a
final status. Every character is its own transaction, SYNC included.
[tspico-dispatch.md](../firmware/tspico-dispatch.md) `PRINT_IO`,
[printer.md](../firmware/printer.md).

## ZX48 mode

No status handshake beyond READY, no pre-header, no echo. `'L'` (4Ch) is the
Spectrum ROM's LD-BYTES asking for the next block: the Pico streams flag,
content and XOR. `'S'` (53h) precedes a saved block. `'T'` (54h) is the ZX
ROM's `LOAD "tpi:name"`: op, length, name; then READY; then a status (FFh =
OK, else an ERR_NR) and a message. ZX v4 sets bit 7 of the op for
`SAVE "tpi:dir"` and reads the reply in pieces (length 1–255, bytes, … 0).
[zx48.md](../rom/zx48.md), [tspico-dispatch.md](../firmware/tspico-dispatch.md)
`ZX48_IO`, `ZX_TPI`; [upgrade.md](../firmware/upgrade.md) uses the same `'L'`
stream to serve the updater tape. The 2068 leaves ZX48 mode with
`OUT 244,0` then `OUT 14,14`.

## The upgrade protocol

Over the same ports, from the Z80 updater program: `'I'` → `'T'`, `'P'`,
version, 0; `'R'` image, block → 256 bytes + XOR; `'S'` code, arg → 0. Each
request is a port-0Fh write followed by its arguments on 0Eh.
[upgrade.md](../firmware/upgrade.md).

## TPMODE (5DDBh, `PEEK 24027`)

| Bit | Set by | Meaning |
|---|---|---|
| 0 | `tpi:picopt` (set), `tpi:ts2040` (clear) | printing (LPRINT, LLIST, COPY) goes to the Pico |
| 1 | `tpi:sdcard` (set), `tpi:tape` (clears bits 0 **and** 1: TPMODE = 0) | LOAD and SAVE go to the Pico; 1 at power-on (TPMODE = 2) |

The ROM handles these four names itself; the BIOS's G_MODE/S_MODE read and
write the low nibble. [sysvars.md](../rom/sysvars.md).
