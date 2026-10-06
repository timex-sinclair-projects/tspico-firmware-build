# TS-Pico TPI Protocol — Reference

This is the byte-level reference for how a Timex Sinclair 2068 and the TS-Pico
talk: the two I/O ports, the status byte, every kind of transaction, and the
rules a firmware handler must follow. It describes **firmware 2.2.1 with ROM 2.2**
(the disk-command ROM), as the code on `main` does it. Where an older document or the original spec says otherwise, this one follows the code.

> **New to all this?** Start with [`PROTOCOL_GUIDE.md`](PROTOCOL_GUIDE.md), a
> plain-language walk through the same ground. Come back here for the details.

> **Source paths** like `TS/tspico_io.py` are Python-package paths; the files
> are under `src/` (`src/TS/tspico_io.py`). ROM addresses are written
> `EXROM $xxxx` / `HOME $xxxx`; the ROM sources are
> `src/rom/patches/tspico-sync.asm` (SYNC, BREAK abort, the BIOS wait) and
> `src/rom/fdd/fddcmd.asm` + `tools/build-rom.py` (the disk commands and channels).

> **History.** The protocol is Gustavo Pane's TPI design
> ([`GUSTAVO_PROTOCOL.md`](GUSTAVO_PROTOCOL.md) tells that story). Since then
> the Pico side moved from one shared FIFO to two ports ("dual-port",
> [`DUAL_PORT_DEVELOPMENT.md`](DUAL_PORT_DEVELOPMENT.md)), the status port
> became a real handshake (auto-busy, issue #14), and the ROM gained SYNC,
> BREAK abort and the IDLE/RECOVERED bits (issue #51).

---

## 1. The two ports

| Port  | Decimal | Z80 `IN` gives                                             | Z80 `OUT` does                                        |
|-------|---------|------------------------------------------------------------|-------------------------------------------------------|
| `$0E` | 14      | the next byte of the Pico's TX FIFO; **`$00` if it's empty** | puts the byte in the Pico's RX FIFO (9-bit word, bit 8 = 0) |
| `$0F` | 15      | the **status byte** (PIO register Y); reading it takes nothing from any FIFO | also reaches the RX FIFO, as `0x100 \| value`. The firmware treats **any** write here as SYNC / abort (§4.1) |

Both FIFOs are **4 entries deep** and not joined (`TX_DEPTH`,
`TS/tspico_io.py`). There is no `/WAIT` line: the Z80 is never held up. So:

- a read of `$0E` with nothing queued quietly returns `$00`;
- a byte the Z80 sends while RX is full is quietly lost (`push(noblock)`).

Everything below exists to keep both of those from happening.

The 1.1 firmware served both ports from one FIFO and
interleaved `0x40` "continue" bytes with the data. That is gone: `$0F` is a
register, and a `0x40` in TX today is an orphan byte (§13).

## 2. The PIO state machine (`TS_IO_DUAL`)

One PIO state machine at 30 MHz handles every Z80 I/O cycle on `$0E`/`$0F`:

1. wait for `/PICOSEL` (GPIO 14) low;
2. GPIO 11 high = the Z80 is writing: sample D0–D7 and A0, push the 9-bit word
   to RX, then **set Y = 0 (busy)** — the *auto-busy* rule of §3.2;
3. GPIO 11 low = the Z80 is reading: A0 = 0 (`$0E`) pulls a TX byte
   (`pull(noblock)`, which falls back to X = 0 when TX is empty); A0 = 1
   (`$0F`) drives Y;
4. wait for `/PICOSEL` high, and loop.

| GPIO | Role |
|------|------|
| 2–9  | D0–D7 (through the U6 buffer). **GPIO 2–4 double as the SD card's SPI pins**: while the card is active, the bus is parked. |
| 10   | A0: `$0E` or `$0F` |
| 11   | direction: 1 = Z80 OUT, 0 = Z80 IN |
| 12   | U6 buffer enable (side-set, active low) |
| 14   | `/PICOSEL` |

Why `pull(noblock)`: a blocking pull would stall the state machine, not the
Z80 (there's no `/WAIT`), and the SM would miss the next bus cycles. With
`noblock` an unprepared Pico fails loudly and at once: `$00` is "no answer".

## 3. The status byte

### 3.1 Bits and values

| Bit | Name | Meaning |
|-----|------|---------|
| 6 | READY | 1 = the Pico has its answer queued, or is ready for the next phase. The only bit the 1.1 ROM tests. |
| 3 | IDLE | 1 = no transaction is open |
| 2 | RECOVERED | **0** = the Pico gave up on a transaction by itself (active low). Cleared by the next SYNC. |
| 7, 5, 4, 1, 0 | — | reserved |

The firmware sets four values (`MQ_STATUS`, `MQ_READY`, `TS/tspico_io.py`):

| Value | Name | Meaning |
|-------|------|---------|
| `$FF` | idle | READY + IDLE. Also what `MQ_READY()` sets, and what old firmware always showed, so no bit misfires on it. |
| `$F7` | mid | READY, transaction still open. Before a command body is captured, and `CH_READY()` answers. |
| `$FB` | recovered | READY + IDLE + RECOVERED (bit 2 low) |
| `$00` | busy | set by the PIO after every Z80 OUT, or by `MQ_BUSY()` |

Test RECOVERED only once READY is set: busy (`$00`) has bit 2 clear too.

### 3.2 Auto-busy

**Every Z80 OUT, to either port, makes the status read `$00` until Python says
READY again.** The PIO does it (`mov(y, null)` at the end of its OUT path).

- *Z80 side*: after any OUT, wait for READY before reading an answer.
- *Pico side*: after the Z80's last OUT of a phase, **queue the answer first,
  then say READY** (`MQ_READY()` or `MQ_STATUS`). The Z80 reads `$0E` the
  moment it sees READY; an empty TX then reads as `$00`.

This replaced the old "ready forever" model (Y set once at boot), in which a
fast Z80 could read before the Pico had queued anything.

### 3.3 Timing

| What | Pace |
|------|------|
| Z80 OUTs inside a block (pre-header, body, SAVE data) | one every ~30 µs (43 µs in SAVE data), **no handshake** |
| Z80 reads inside a block (LOAD data) | one every ~44–50 µs, **no handshake** |
| `tpi:chrd` data phase (the ROM's channel driver) | one every ~75 µs |
| The Pico gives up on a half-received pre-header or body | after **1 s** of silence (`RX_CAPTURE(..., 1000)`, `BODY_READ_TIMEOUT_MS`) |
| The Pico gives up on command output nobody reads | 10 min (`CMD_STALL_MS`); key waits: a day (`KEY_WAIT_MS`) |
| The ROM's ready-wait | 226 polls through a debounced BREAK scan, **~19.9 s**, ≥ 88 ms per call |

A Z80 program must never use `OTIR`/`INIR` to the Pico.

## 4. Transactions

### 4.1 SYNC

The ROM opens **every** transaction with `OUT (0Fh),03h` and then waits up to
~1 s for READY + IDLE before its first byte (`SYNC_WRITE` EXROM `$2300`,
`SYNC_WAIT` `$230E`). The patched sites are the SAVE pre-header (`$189A`),
every LOAD/VERIFY/MERGE block (`$1998`), `tpi:` commands (`$1BAA`), the LPRINT
character (`$1651`) and COPY (`$16F6`).

The Pico sees the `0x103` word in `RX_CAPTURE`, calls `MQ_TO_IDLE`, which
**empties TX and RX and queues exactly one `0x01`**, and says idle. So a SYNC
always leaves the link at TX = `[01]`, RX empty, status `$FF`, whatever state
an earlier client left it in.

- **BREAK** (CAPS SHIFT + SPACE) during a transaction: the ROM writes the same
  `03h`, waits for READY + IDLE and raises Report D (`BRK_ABORT`). It checks in
  every ready-wait, every 256 bytes of the SAVE/LOAD loops, and in the key waits
  of functions `$82`, `$84`, `$86`. The Pico hears the `$0F` write in
  `RX_CAPTURE`, `RX_BLOCK`, `TX_ROOM` and `CMD_PUT`/`CMD_KEY`/`CMD_DRAIN`
  (`CmdAbort`), abandons the transaction and goes idle.
- **RECOVERED**: if the ROM sees READY with bit 2 low, it raises the new
  **Report T "TS-Pico reset, try again"** (ERR_NR `$1C`, `RD_STATUS`).
- **Wait for IDLE before a SYNC** that follows a READY-not-IDLE answer
  (§5.6): a SYNC sent while the Pico is still in `PROCESS_CMD`'s tail is lost
  with the pre-header behind it (Report T). The ROM's channel driver does.

The ROM **requires** firmware that knows SYNC: the 1.1 firmware reads the SYNC
byte as the first pre-header byte and hangs or misaligns. The 1.1 ROM never
writes `$0F`, and the current firmware still serves it.

### 4.2 The pre-load byte

Between transactions TX holds **exactly one `0x01`**. The ROM reads it straight
after the tenth pre-header byte, **without waiting** (EXROM `$223E`), then
waits for READY. It is queued at boot, by `PROCESS_CMD`'s tail after every
command, by `LOAD_TS`/`SAVE_TS` at their ends, and by every SYNC.

- None there: the Z80 reads `$00`, the ROM's internal "no answer" → **Report J**
  on that command.
- Two there: the second is read later as data → usually **Report R**.

### 4.3 The pre-header and the dispatcher

Every transaction starts with 10 bytes. Byte 0 picks the kind
(`TS2068_IO`, `TS/tspico.py`):

| pre[0] | pre[1] (TADDR) | What it is | Handler |
|--------|----------------|------------|---------|
| `$00` | 0 | SAVE header block (§6.2) | `SAVE_TS` |
| `$00` / `$FF` | 1–3 | LOAD / VERIFY / MERGE block (§6.1) | `LOAD_SERVE` → `LOAD_TS` |
| `$00` / `$FF` | ≥ 10 | headerless LOAD | `LOAD_SERVE` |
| `'B'` `$42` | 4, 5, 6 | printer: COPY (4, 6), LPRINT character (5) (§8) | `PRINT_IO` |
| `'B'` `$42` | 0 | `SAVE "tpi:..."` command (§5) | `PROCESS_CMD` → `SA_funct` / `EXT_SA_FUNCT` |
| `'B'` `$42` | 1–3 | `LOAD "tpi:name"`: mount a file | `PROCESS_CMD` → `LOAD_TPI` |
| anything else (incl. `'A'` `$41`) | — | "Unrecognized": `MQ_TO_IDLE(recovered=True)` — FIFOs emptied, **one `0x01` staged**, status RECOVERED | — |

Two layouts share the byte positions:

| Byte | Command (`'B'`) | LOAD/SAVE block (`$00`/`$FF`) |
|------|-----------------|-------------------------------|
| 0 | `'B'` | flag: `$00` header, `$FF` data |
| 1 | TADDR (0 = SAVE, 1–3 = LOAD/VERIFY/MERGE) | TADDR |
| 2 | bank (`$FF` = HOME); ignored for commands | bank |
| 3–4 | PMR1: the first `CODE` number, LE | session id, LE |
| 5–6 | PMR2: the second `CODE` number, LE | address (IX), LE |
| 7–8 | length of the command text, LE | block length (DE), LE |
| 9 | XOR of bytes 0–8 (**not checked** for commands) | XOR of bytes 0–8 |

`PARAMS(pre)` returns `(pre[3] | pre[4] << 8, pre[5] | pre[6] << 8)`.

## 5. Commands (`'B'`, TADDR 0)

### 5.1 The exchange

```
Z80                                                   Pico
[wait IDLE]                  (the channel driver)
OUT (0Fh),03h  SYNC --------------------------------> MQ_TO_IDLE: TX=[01], status FF
wait READY+IDLE (<= ~1 s)
OUT 'B', 0, FF, PMR1 lo/hi, PMR2 lo/hi, LEN lo/hi, XOR  RX_CAPTURE, 10 words
IN  (0Eh) = 01  <---- the pre-load, read at once
wait READY ........................................... PROCESS_CMD: status F7, capture body
OUT 'D', LEN lo, LEN hi, text..., XOR --------------> check XOR, decode, dispatch
wait READY ........................................... handler queues its answer, then READY
IN  (0Eh) = the answer
[function data, key exchange: §5.4]
                                                      tail: wait TX empty, drain RX,
                                                      queue 01, status FF (FB if abandoned)
```

### 5.2 The body

```
'D' ($44), LEN lo, LEN hi, text[0..LEN-1], XOR
```

The XOR covers `'D'` through the last text byte. **The Pico checks it**: a
mismatch answers status 2 (Report R) and the handler doesn't run. The text
must decode as UTF-8 (in practice ASCII; otherwise status 5, Report C) and
start with the four characters `tpi:` in any case. The command word is the
text up to the first space, upper-cased, `TPI:` included (the dictionary keys
are `"TPI:DIR"` and so on); `getArgs(cmd)` returns the rest, case kept.
Handlers receive `cmd = "D.." + text`.

From BASIC the ROM only sends names of 6–31 characters as commands (EXROM
`$1A90`/`$1AFC`); the disk-command module enters past that gate
(`SESSION_NAMED` `$1AAC`). A machine-code client has no gate: LEN is 16 bits.

The names `tpi:tape`, `tpi:sdcard`, `tpi:picopt` and `tpi:ts2040` never reach
the Pico: the ROM handles them (they set TPMODE, `$5DDB` = 24027: bit 1
LOAD/SAVE to the Pico, bit 0 printer to the Pico). Sent raw, they are
"Unrecognized command".

The ROM also recognises a second prefix, `net:`: Gustavo's provision for
networking from the 2068, meant as an extended ZX Interface 1 network. A
`net:` name goes to the Pico like a `tpi:` command (it is never a switch
word), with `net:` at the start of the text. No firmware implements it yet:
the command word `NET:…` matches nothing and is "Unrecognized command"
(Report C). A network service would need only firmware: dispatch on the
`NET:` prefix in `PROCESS_CMD`; the ROM side is in place.

### 5.3 The answer: a status

The ROM reads one byte, `AND A` (0 → its internal "no answer", Report J),
`DEC A`, returns on 0 (status 1 = OK), otherwise runs the response functions
(§5.4) and hands anything else to `STATUS_TO_REPORT` (EXROM `$1BF3`) with
A = status − 1:

| Status | A at `$1BF3` | Report | ERR_NR | Firmware constant |
|--------|--------------|--------|--------|-------------------|
| 0 | (internal 9) | J Invalid I/O device | `$12` | — (empty FIFO) |
| 1 | 0 | OK | — | `_1_OK` |
| 2 | 1 | R Tape loading error | `$1A` | `_2_R_Tape_load` |
| 3 | 2 | F Invalid file name | `$0E` | `_3_F_Invalid_file` |
| 4 | 3 | Q Parameter error | `$19` | `_4_Q_Parameter` |
| 5 | 4 | C Nonsense in BASIC | `$0B` | `_5_C_Nonsense` |
| 6 | 5 | 6 Number too big | `$05` | `_6_6_Num2Big` |
| 7 | 6 | 8 End of file | `$07` | `_7_8_EOF` |
| 8 | 7 | A Invalid argument | `$09` | `_8_A_Invalid_arg` |
| 9 | 8 | 9 STOP statement | `$08` | `_9_9_STOP` |
| 10 | 9 | J Invalid I/O device | `$12` | `_10_J_Invalid_IO` |
| 11–127 | ≥ 10 | D BREAK - CONT repeats | `$0C` | `_11_D_Break` |
| RECOVERED bit | — | T TS-Pico reset, try again | `$1C` | — |

### 5.4 The answer: a response function (status ≥ `$80`)

A first byte of `$80` or more asks the 2068 to do something. The dispatch chain
starts at EXROM `$026F` (and `$2194`) and compares A = code − 1. **Each function
first reads one more byte, its own status** (`READ_STATUS_BYTE` `$02B9`), which
becomes the command's result.

| Code | Name | Bytes after the code | The 2068 | Firmware |
|------|------|----------------------|----------|----------|
| `$81` | PRINT STRING | status, text, `$00` | prints the text on the main screen (`$0274`) | `SEND_MSG` (when VERBOSE or forced) |
| `$82` | PRINT STRING & RETURN KEY | status, text, `$00`; then the Z80 waits READY and OUTs one key | `$2198` | unused |
| `$83` | PRINT CHARACTER | status, one character | `$21A8` | unused |
| `$84` | RETURN KEY | status; the Z80 waits for a key, waits READY, OUTs it | `$21BE` | unused |
| `$85` | GET STATUS | status; the Z80 OUTs a 2-bit mask (b0 keyboard, b1 aux) | `$21CB` | unused |
| `$86` | PRINT STRING WITH LOOP | status, then pages: text, `$00` → the Z80 waits for a key, waits READY, OUTs the key; `N` ends the loop; any other key: it waits READY and prints the next page. `$03` ends the loop. | `$21E3` (loop `$21E7`, guard `$22A1`) | `SEND_MSG2`, `ListMenu`, `PROMPT_EACH`, `SEND_MSG_PROMPT_YN` |
| `$87` | (spec: "print n characters") | status | calls HOME `$08A6`, which clears the screen like CLS | unused |
| `$88` | **`$86` on the lower screen** | as `$86` (no leading CR) | `$2213` is patched to `CP 87h / JP Z,$3006 / RET`, and `$3006` is `LOWER_LOOP` in `fddcmd.asm`, which is `$86`'s handler with the lower screen (stream `$FD`) as its channel, so a prompt doesn't write over a picture that `SAVE "f:x" SCREEN$` is about to save | `SEND_MSG_PROMPT_YN(..., lower=True)`, sent only by `tpi:fopen` |
| `$80`, `$89`–`$FF` | — | — | fall through the chain: Report D, and whatever the Pico queued behind the code is left unread | — |

In the firmware (`TS/tspico.py`, issue #16) these are `FN_PRINT_STRING` (`$81`), `FN_PRINT_STRING_KEY` (`$82`), `FN_PRINT_CHAR` (`$83`), `FN_RETURN_KEY` (`$84`), `FN_GET_STATUS` (`$85`), `FN_PRINT_LOOP` (`$86`) and `FN_PRINT_LOOP_LOWER` (`$88`); the `$00` that ends a string or a page is `STR_END`, the `$03` that ends a loop `LOOP_END`, and a pre-header's first byte is `PRE_HEADER` (`$00`), `PRE_DATA` (`$FF`) or `PRE_CMD` (`$42`, `'B'`). Each use in the code also gives the number in its comment.

Text rules (the ROM's `PRINT_STRING_FROM_PICO`, `$045F`/`$068E`/`$06F2`):

- it reads each character **without a ready-wait**; `RST 10` is slow enough
  that the Pico keeps ahead, provided the first bytes were queued before READY;
- `$00` ends a string, and so does **any byte ≥ `$80`**; inside a `$86` loop,
  `$03` ends the loop. `SEND_MSG2` maps bytes ≥ `$80` to `?` and `\*` to `$7F`
  (©);
- control codes 16–23 (INK … TAB) consume the bytes after them.

Keys (`GET_KEY_AND_SEND` `$0471` → `SEND_KEY` `$1C40`): letters are sent **upper
case**, after a ready-wait. The Pico compares with `78` (`N`) only, so a
machine-code client must send upper case too. At a `SEND_MSG2` "Scroll?"
prompt a digit also sets the page length (`1`–`9` lines, `0` = 10); any other
key is a full page. The ROM puts a BREAK test in front of the key poll
(`KEYWAIT`, patched at `$0479`).

### 5.5 Mounting: `LOAD "tpi:name"` (TADDR 1–3)

The same frames with pre-header byte 1 = 1, 2 or 3 and the text `tpi:` +
name. `PROCESS_CMD` calls `LOAD_TPI(name)` instead of the command tables and
answers with `SEND_MSG` (a status, or a message when VERBOSE is on).

### 5.6 The tail, and READY vs IDLE

When the handler returns (or raises), `PROCESS_CMD`'s `finally` waits (bounded)
for TX to empty, drains RX, **queues the next `0x01`** and sets the status to
idle (`$FF`), or recovered (`$FB`) if the Z80 stopped reading. A handler never
writes that `0x01` itself.

An answer that the ROM follows *immediately* with another command must say
READY **without** IDLE: `CH_READY()` (`$F7`). Otherwise the Z80's next SYNC can
arrive while the tail is still running (see §4.1). The channel commands answer
this way; `CH_REPLY(st)` is a bare status with `CH_READY`, and never prints.

## 6. LOAD and SAVE blocks

### 6.1 LOAD / VERIFY / MERGE

EXROM `$00FC` (the Spectrum's `LD_BYTES` entry, `JP 196Dh` here) takes this
path when TPMODE bit 1 is set (`tpi:sdcard`); A = flag, carry = LOAD (clear =
VERIFY), IX = destination, DE = length.

```
Z80                                                   Pico (LOAD_TS)
SYNC
OUT flag, TADDR, BANK, SESSION lo/hi, IX lo/hi, DE lo/hi, XOR
IN  status  (the pre-load; must be 1, else Report R)
wait READY ........................................... queue the first bytes, then READY
OUT flag          (echo 1, BEFORE the data)
IN  flag, DE data bytes, CRC                          flag + content + CRC
    (~47 us a byte, no handshake; H keeps a running XOR)
OUT computed XOR  (echo 2)
wait READY
IN  final status  (1 = OK; >= $80 -> response functions) 01 (final) + 01 (next pre-load)
```

The first echo comes **before** the data loop (`$19DA: CALL 1924h`, `OUT H`),
not after it as older documents say. The block CRC is the XOR of the flag and
the content, **not** including the session bytes, so TPI blocks convert to TAP
without recalculation. `LOAD_TS` writes its own final status and the next
pre-load (two bytes); its abort path writes **one** (`MQ_TO_IDLE`).

### 6.2 SAVE

EXROM `$0068` (`SA_BYTES`, `JP 1879h`), same TPMODE gate; A = flag, IX =
source, DE = length.

```
Header (flag 00):                                     Pico (SAVE_TS)
  SYNC; OUT 00, 0, BANK, SESSION lo/hi, IX lo/hi, DE lo/hi, XOR
  IN pre-load (must be 1)
  wait READY ......................................... status "mid" right before capture
  OUT 00, SESSION lo/hi, 17 header bytes, CRC          RX_CAPTURE, 21 words
  wait READY; IN mid-phase status                      01, or a refusal: 03 (F), 08 (A)
~1 s pause (the ROM HALTs)
Data (flag FF), NO pre-header:
  OUT FF, SESSION lo/hi, DE bytes, CRC                  RX_BLOCK (length + 4)
  wait READY; IN final status                          the SD write, then 01 (0A, J, if it failed) + the pre-load
```

Refuse a SAVE at the **mid-phase** status, never after the final status: by
then the 2068 has printed `0 OK` and gone. The final status waits for the SD
write, so a failed write is reported as J (§13). `SAVE ""` and names over 10
characters are refused by the ROM before anything is sent.

## 7. The channel commands

`OPEN #`, `PRINT #`, `INPUT #` and `CLOSE #` on `f:` and `d:` streams become
ordinary commands (client: `fddcmd.asm` `CH_SEND`/`CH_FETCH`/`CH_STATUS`;
Pico: `CH_*` in `tspico.py`, logic in `TS/channels.py`). Any Z80 program can
send them.

| Text | PMR1 | PMR2 | Answer |
|------|------|------|--------|
| `tpi:chopen <mode> <path>` | stream (0–255, just a key) | record length (0 = a stream, 1–254) | bare status (`CH_REPLY`) |
| `tpi:chopen r d:<pattern>` | stream | 0 | bare status; the channel reads a listing |
| `tpi:chwr <hex>` | stream | 0 | bare status |
| `tpi:chrd` | stream | bytes wanted (1–255; 0 = 255) | **data phase**, below |
| `tpi:chclose` | stream | 0 | bare status (closing an unopened stream is fine) |

Modes: `r`, `w`, `a`, `u`, each with an optional `b` (binary). Text mode turns
2068 CR and keyword tokens into newlines and words on the card, and back.
Binary passes bytes through — **except byte 23 (`$17`) in a write, which is
always the TAB escape** `23, n lo, n hi` (seek to byte or record *n*, 1-based).
TAB 0 is a query: the next read returns a count as text + CR (names in a
listing, records in a record file, bytes otherwise). `tpi:chwr` sends its
payload as hex because the command text must be text.

The `tpi:chrd` data phase, straight after the command body (no C_END):

```
wait READY
IN status        1 = data follows, 7 = end of file (Report 8), anything else: its report
if 1:  IN n (1-255), n bytes, XOR of the n bytes (seed 0)
       -- read ~75 us apart; the Pico queues 1 and n, says CH_READY, then streams
```

## 8. Printer transactions

`'B'` with TADDR 5 carries one LPRINT/LLIST character in PMR1's low byte and
no body: the Z80 reads the pre-load and waits for READY. TADDR 4/6 is COPY
and has a body (`'D'`, length, screen data, XOR, checked) followed by a final
status (1, or 2 = Report R). Every character is its own transaction, SYNC and
all (`PRINT_IO`; output in `TS/printer.py`).

## 9. The Pico Interface BIOS (EXROM `$1840`)

A jump table for machine-code programs, stable across ROMs:

| Entry | Name | Contract |
|-------|------|----------|
| `$1840` | G_MODE | BC = TPMODE (low nibble); AF kept |
| `$1842` | S_MODE | TPMODE := A AND `0Fh`; AF kept |
| `$1844` | G_VERS | BC = the interface version: `$0015` on ROM 1.1, `$0022` on ROM 2.2 |
| `$1846` | TX_A | `OUT (0Eh),A`; no wait, no BREAK check |
| `$1848` | RX_A | `IN A,(0Eh)`; Z if 0; no wait |
| `$184A` | C_END | wait READY, read the answer, run the response functions. NC = status 1 (A = 0). C = failed, see below. |
| `$184C` | WF_NPH | wait READY (~19.9 s). NC = ready (A, BC kept). C with A = `02h` timeout, `0Ch` BREAK (abort already sent, Pico idle), `1Ch` RECOVERED. Never raises a report. |

C_END's failure codes:

| Failure | A |
|---|---|
| error status *s* | *s* − 1 |
| timeout | `09h` (J) |
| BREAK | `0Ch` |
| Pico reset (RECOVERED) | `1Ch` |

The table entry (`$184F`) goes to the module's `C_END2` (`$301B`). It calls
WF_NPH first and turns its timeout (`02h`) into `09h`, so a silent Pico is J;
read as a status, `02h` would be status 3, F. `0Ch` and `1Ch` never collide with a status: the firmware's
highest is 11. Note that C_END runs the response functions, which can raise a
report from inside (BREAK in a key wait, RECOVERED in the `$86` loop).

Other fixed EXROM addresses: `SYNC_WRITE` `$2300`, `SYNC_WAIT`
`$230E`, `STATUS_TO_REPORT` `$1BF3` (A = status − 1; never returns),
`READ_STATUS` `$0655`, `SESSION_SETUP` `$1A73`, `SESSION_NAMED` `$1AAC`.
**`$2003`, `$2006` and `$2027`–`$203C` are `JP self` padding: calling one hangs.**

A RAM program reaches the EXROM through HOME `$03FC` (HL = target; A, F, BC,
DE in and out; **IX not kept**; an HL argument goes in `$5DCD`), with
interrupts off around the call (§13, the bank-switch pitfall). A report raised inside the
EXROM leaks four bytes of the bank-switch stack at `($65CE)` each time; the
ROM's own `GUARDED` (`fddcmd.asm`) traps ERR_SP for that. See the programmer's manual for worked
examples; most programs are better off driving the ports directly.

## 10. ZX48 mode

After `tpi:zx48` the Pico serves the customised Spectrum ROM (flash slot 0) and
speaks its protocol: no status port, no pre-header, no echo. `'L'` → flag +
content + CRC; `'S'` → a block; `'T'` → `LOAD "tpi:name"`, or, on the ZX v4
ROM, `SAVE "tpi:dir"`, flagged by bit 7 of the op byte, with the reply in
pieces (status, then length 1–255 + bytes, repeated, then 0). The V6
pre-load chain does not apply (§13). The 2068 leaves ZX48 mode with
`OUT 244,0` then `OUT 14,14`.

## 11. Writing a command handler

A built-in handler is `def NAME(pre, cmd)` in `TS/tspico.py`, registered in
`SA_funct` inside `TS2068_IO()` as `"TPI:NAME": NAME`. An external one is
`def NAME(MQ, TSP, pre, cmd)` in `TS/extcmd.py` (or `/dev_extcmd.py` on the
flash), registered in its `EXT_SA_FUNCT` as `"TPI:.NAME"`. Either way:

1. **Give exactly one answer.** Pick one:
   - a status: `SEND_MSG(msg, "", st)` (a message only when VERBOSE is on), or
     `CMD_PUT(st); MQ_READY()`; mid-statement commands use `CH_REPLY(st)`;
   - a message: `SEND_MSG(msg, msg1, st, True)` (`$81`);
   - scrolling text: `SEND_MSG2(text, st)` (`$86`);
   - a yes/no: `SEND_MSG_PROMPT_YN(prompt)` returns the key, and nothing more
     may be sent after it;
   - data your client reads: `CMD_PUT` the first bytes, **then** `MQ_READY()`
     (or `CH_READY()`), then the rest. Say how long it is up front and end
     with a checksum; `1, n, n bytes, XOR` is the `tpi:chrd` format, which the
     programmer's manual's `GET_DATA` and a BASIC `IN 14` loop both read.
     Never start data with a byte ≥ `$80` if the ROM might read it.
2. **Never write the `0x01` pre-load**; the tail does.
3. **Use `CMD_PUT`/`CMD_KEY`/`CMD_DRAIN`**, not `MQ.put`/`MQ.get`: they wait
   while TX is full, listen for BREAK, and turn it into `CmdAbort` (a
   `BaseException`: don't catch it).
4. **SD work inside `SD_CALL(fn, *args)`**, before the answer: GPIO 2–4 are
   D0–D2, and `SD_CALL` gives the pins back even when `fn` fails.
5. **Errors are statuses.** Catch what you expect and answer F, Q, A…; anything
   that escapes becomes J (`FAIL_CMD`), and the tail still runs.
6. **In an external command, define the status numbers yourself.** The
   `_1_OK`-style names are underscore `const()`s, inlined by MicroPython:
   they are not attributes of `TS.tspico` on the Pico (`AttributeError`,
   Report J), though they are on a PC.

`src/test/process_cmd_hosttest.py` shows how to run a handler through the real
`PROCESS_CMD` on a PC and check its bytes; `src/test/extcmd_hosttest.py` does it
for the example external commands.

## 12. Debugging

- **Host tests** (`src/test/*_hosttest.py`, run by CI) cover the dispatcher,
  SYNC, LOAD/SAVE, the channels, the ROM patches and the Z80 updater.
- **Watch the Pico**: `tools/pico-serial.py watch` shows the `[TLM ...]`
  telemetry (`TLM_ENABLED` is on in `main.py`) without disturbing it.
- **Protocol observers** (`src/test/protocol_observer_*.py`,
  `_harness_template.py`): standalone bus harnesses that capture every byte
  with timestamps. Capture first, decide after — never per-byte Python work in
  the capture loop (`src/CLAUDE.md`, "the two-phase capture rule").

---

## 13. Pitfalls

Each of these was a real bug. Most show up one command *after* the mistake.


- **Don't `print()` during a protocol exchange.** USB serial prints
  take 5-10 ms, and the PIO RX FIFO is only 4 bytes deep. A print mid-
  pre-header drops Z80 OUTs.
- **Don't `MQ.put()` between draining pre-header and starting the data
  response.** Any byte put there ends up *before* the response in the
  FIFO and shifts the data stream by one byte. Z80's CRC will mismatch
  and you'll see "Report R - Tape Loading Error".
- **If `LOAD_TS` returns without writing its trailing two `0x01`s (final
  status + next pre-load), the next LOAD fails with Report J.** The
  pre-load chain is load-bearing. (Command handlers are different: they
  write their one answer and `PROCESS_CMD`'s tail writes the pre-load.)
- **An early return re-arms too — and with ONE `0x01`, not two.**
  `LOAD_TS`'s abort path skips the V6 chain by construction, so TX is
  left empty and Y wherever the partial Z80 OUTs dropped it. That is the
  rule above firing on an error path: the next command's status read
  finds nothing and gets Report J. So the path ends in
  `MQ_TO_IDLE(MQ, recovered=...)` — the one way back to idle (issue
  #51) — which drains both FIFOs, stages exactly one `0x01` and sets Y.
  One byte, because the pair on the normal path exists only so the Z80
  can consume the first as this transaction's final status: after an
  abort it has already reported and gone, and a second byte would be
  read as the first byte of the next response, the one-byte shift that
  surfaces as Report R. **Nothing runs after `LOAD_TS` returns**, so it
  has to re-arm itself. Found via VERIFY, which makes the Z80 abandon
  the transfer mid-block as soon as the comparison fails — the R is
  correct, the J on everything after it was not.
- **Don't pre-load `0x01` inside `ACTIVATE_MQ()`.** It's tempting (the
  pre-load chain expects a status byte ready in TX after the SM is
  re-activated), but `ACTIVATE_MQ` is called both at boot AND mid-
  command (e.g., after SD card access in `MOUNT_FILE`). Mid-command,
  the next call in the chain is usually `SEND_MSG` which writes its
  own status byte — pre-loading inside `ACTIVATE_MQ` would put TWO
  status bytes in TX, the Z80 reads ONE and considers the response
  done, and `SEND_MSG`'s drain-wait loops forever. Pre-loading
  belongs **at boot** (one explicit `MQ.put(0x01)` in `TS2068_IO()`)
  and at the **tail of each command handler** (the V6 chain).
- **Don't call `END_MSG()` after the final status + pre-load writes
  in LVM handlers.** `END_MSG` writes its own `0x01` status byte to TX
  for the non-verbose case (and a verbose directive header for verbose
  mode). If your handler already wrote `MQ.put(0x01)` × 2 (final +
  pre-load), `END_MSG` adds a THIRD `0x01`. The first two are consumed
  correctly (final status + next-iter status) but the third sits in TX
  and gets read as the FIRST byte of the next iteration's data-loop
  reads, where the Z80 expects the block_type byte. The Z80's running
  CRC accumulator drifts by one byte from the start, the final CRC
  check fails, and you get "Report R — Tape Loading Error" on the data
  block. If you want a verbose status message, write the directive
  bytes BEFORE the pre-load `0x01` so the directive IS the final
  response, not an addition.
- **Validate a SAVE before you write the final status, not after.** The
  V6 chain's `MQ.put(0x01)` final status IS the Z80 printing `0 OK` —
  once it's in TX, the transaction is decided. Any check that runs after
  it can only report into a Z80 that has already gone back to the BASIC
  prompt and stopped reading `$0E`, so the report has nowhere to go and
  the handler blocks in `MQ.put` on a full 4-deep TX FIFO. The `WATCHDOG`
  can't rescue it either: `dead = True` is set alongside the final status,
  so that thread has already exited. `SAVE "bad file"` used to do exactly
  this — a false `0 OK` followed by a wedged Pico until reset.

  The place to refuse a SAVE is the **post-header status read**, where
  `SAVE_TS` writes the mid-phase `0x01`. Write an error status there
  instead and the Z80's `STATUS_TO_REPORT` path RST-8's, shows the BASIC
  report, and aborts *before* sending the data block. Both current guards
  use this: `BLEN == 0` → `0x08` (Report A, empty program) and a
  disallowed filename → `0x03` (Report F). Follow either as a template,
  and finish with `DRAIN_REFUSED_SAVE()` so a Z80 that sends the data
  block anyway doesn't leave bytes in RX to be misread as the next
  command's pre-header.
- **Never call `bytes.decode()` on anything the Z80 sent.** A TS-2068
  filename can legitimately contain bytes >= 0x80 (graphics characters,
  BASIC tokens), and `decode()` raises on those. `SAVE_TS` and `LOAD_TS`
  run *unguarded* inside the dispatcher's main loop — there's no
  try/except around the call in `tspico.py` — so an exception doesn't
  produce an error report, it takes the whole loop down. Build the string
  byte-by-byte instead; `SAVE_NAME()` in `TS/tspico_io.py` is the pattern.
- **The two filename allowlists disagree, deliberately for now.**
  `SAVE_TS` accepts only alphanumerics, `_` and `-`. The
  `SAVE "tpi:<name>"` create path in `TS/tspico.py` is far more
  permissive — any printable character except the eight FAT-reserved
  ones — so spaces, dots and parens produce a file that way but a
  Report F via a plain `SAVE`. Worth reconciling; until then, don't
  "fix" one side in isolation and assume the other matches.
- **Never answer an error with `0x01`.** Two SAVE paths used to write
  "OK" and bail out — the header-CRC failure and the no-data timeout —
  on the theory that the Z80 would notice the problem itself. It won't:
  it validated the bytes *it* sent and is satisfied, so a CRC mismatch is
  something only the Pico can see. Answering OK makes the Z80 stream the
  entire data block at a handler that has already returned. Nothing
  drains it, so the dispatcher's next pre-header read consumes data bytes
  and dispatches on garbage, and the trailing `0x01` is read as the final
  status — "0 OK" on screen for a save that never wrote a file. Refuse at
  the post-header status read via `REFUSE_SAVE()` instead.
- **A LOAD's first status can't carry an error, and a header search
  swallows every failure.** The ROM reads it with no wait straight after
  the pre-header (EXROM 19C7), so it is the `0x01` staged before the
  command arrived; an error byte `LOAD_TS` writes lands in the *flag* slot.
  For a data block a wrong flag is Report R. For a header, the LOAD's
  search (04DD: `CALL 00FC / JR NC`) just asks again after any failure — a
  wrong flag, a bad checksum, even a final status of 2 (1A0B goes to the
  FUNCTION chain, not the report dispatcher) — so a damaged header used to
  be re-requested for ever, until a stall gave Report T. The only report a
  header search can raise is the first status of its *next* request: any
  value but 00/01 there is Report R. `LOAD_REFUSE()` does both steps (the
  failing flag, then the error staged for the retry, re-staged after the
  2.x ROM's SYNC by `FIRST_STATUS()`). It also means "End of file" (status
  7) shows as R on a header search. And never stream a block the Z80 will
  stop reading part way (wrong type, wrong length, bad checksum): the rest
  waits in TX until the next SYNC, which looks like a BREAK and rewinds the
  search. `LOAD_TS` checks all three before READY.
- **Never call `_thread.start_new_thread()` unguarded.** If core1 is
  already in use the call raises `OSError` "core1 in use", and nothing up
  the stack catches it: it leaves `TS2068_IO` and reaches `main.py`,
  which has no try/except either, so the Pico drops to a REPL and the
  user sees "locked up, LED stopped blinking". Core1 is not idle by
  default — `BLINK_LED` is spawned at boot and runs for the life of the
  board, and the idle loop spawns `SAVE_LOG`. The one spawn on a live
  path, `SAVE_LOG`, sets `busy` first and then wraps the spawn in
  `try/except OSError`, clearing `busy` itself on failure, because
  nothing else will. Don't "fix" a failed spawn by retrying with a sleep
  — a few ms of sleep with the Z80 streaming into a 4-deep RX FIFO
  trades a rare hang for routine corruption.
- **Wait for core1 before starting a transfer.** Writing to the Pico's
  flash stops *both* cores while a sector is programmed, so a `SAVE_LOG`
  on core1 must not overlap a LOAD or SAVE block, or the pre-header
  burst after a SYNC: the Z80 keeps clocking bytes out and the 4-deep
  PIO FIFO overflows. `busy` is how core0 knows a write is in progress;
  wait on it with `WAIT_CORE1(limit_ms, who)`, which is **bounded** — an
  unbounded `while busy: pass` turns any way of `busy` staying True into
  a hang that needs a power cycle. `SAVE_LOG` clears `busy` in a
  `finally` so that every path, including a failed write, ends with it
  False.
- **Don't announce READY and then go do SD work.** `ACTIVATE_SD()` grabs
  GPIO 2-4 for SPI, and GPIO 2 is D0. Any `$0E` or `$0F` cycle that lands
  after the grab reads corrupted data — this is the pin-grab race #40
  fixed inside `SAVE_TS`, and the post-SAVE dispatcher block reintroduced
  it by arming TX + `MQ_READY()` and *then* calling `MOUNT_FILE` and
  `DIR_FILES`. The 2068 prints `0 OK` and returns to the prompt while the
  Pico is still working, so the window is reachable in normal use. Arm
  exactly once, after the last SD access; leave Y at BUSY until then.
- **Guard every allocation sized by a Z80-supplied field.** `BLEN` is
  16 bits and `SAVE "x" CODE 0,65535` is legal, so there is no sane bound
  to clamp to — only an allocation that may fail. An unguarded
  `MemoryError` reaches `main.py` and drops the Pico to a REPL, and if the
  allocation sits before the mid-phase status write the 2068 *also* hangs
  to its ~19.9s `WF_NPH` timeout. Collect, retry once, then refuse.
- **A failed SD write is reported: the final status waits for it.**
  `SAVE_TS` leaves the final status in `TSP.save_final` and the dispatcher
  sends it once the card work is done and the bus is back (the pin-grab
  rule above): `01`, or `0A` (J, Invalid I/O device) if nothing was
  written. Before that change the final status went out before
  `ENA_SD()`, and a failed write could not be reported. Still wrap the
  write, or an `OSError` from a pulled card takes the dispatcher down on
  top of losing the file.
- **`END_MSG()` has no callers and should keep it that way.** It is
  retained as documented context for the trap above, not as an API.
- **`busy` is set by another core: never wait on it unbounded, and always
  clear it in a `finally`.** `tspico.py`'s `busy` means "core1 is writing
  the log to flash" (`SAVE_LOG`; `BLINK_LED` uses it during boot only).
  `tspico_io` has its own, unrelated `busy` left from the removed watchdog;
  `tspico.py` doesn't import it. Before the 2026-09-30 audit `SAVE_LOG`
  cleared the flag only when its write succeeded, so a full flash left it
  True for good and every `while busy: pass` -- `COPY_FILE` (every
  `LOAD "tpi:file"`), and the main loop's SAVE and LOAD branches -- hung
  the Pico. Wait with `WAIT_CORE1(limit_ms, who)`, which gives up and logs;
  set `busy = True` on core0 *before* `start_new_thread`, so there is no
  window in which a transfer sees core1 idle as the write begins.
- **A bare `except:` swallows BREAK.** `CmdAbort` (#51) is a
  `BaseException` so that `except Exception:` lets it through to
  `PROCESS_CMD`; a bare `except:` catches it anyway. Any handler that wraps
  `SEND_MSG2`, `ListMenu`, `CMD_KEY` or another Z80 exchange must catch
  `Exception` (or narrower), or keep the exchange outside the `try`.
  `GETLOG` had this until the audit: BREAK at its Scroll? prompt was
  answered with "Log file too large".
- **ZX48 mode is a different protocol — don't apply the V6 chain to
  it.** The customised Spectrum ROM in flash slot 0 has no status port,
  no pre-header and no echo phase: after `'L'` it reads exactly
  `flag + content + CRC` and returns, and after `'S'` it writes the
  block and returns. A status byte or pre-load `0x01` written by a ZX
  handler is an orphan that the *next* `'L'` reads as its flag byte.
  `LOAD_ZX` streamed one byte too many for exactly this reason (flag +
  `totbytes` instead of `totbytes`); the surplus was the next block's
  length-low byte, and the "TX FIFO not empty after ZX mode" cleanup in
  `ZX48_IO` was mopping it up rather than fixing it. Covered now by
  `src/test/zx48_hosttest.py`.
- **Never call `ENA_MQ()` — it rebuilds the single-port SM.** It
  creates `TS_IO` at 15 MHz, which does not decode `$0E` from `$0F`.
  `SAVE_ZX` called it after its SD write and handed the result back to
  `ZX48_IO` as the session's state machine, so every ZX transaction
  after the first save ran on the wrong bus program. Any handler that
  calls `ENA_SD()` and isn't returning to the main dispatcher must
  restore the bus with `ENA_MQ_DUAL()` (or `ACTIVATE_MQ()` in
  `tspico.py`) instead.
- **Mask RX reads to 8 bits.** The RX word is 9 bits — bit 8 carries
  A0, i.e. which port the Z80 wrote. `MQ.get()` unmasked into a
  `bytearray` raises `ValueError` on any `$0F` write and drops the Pico
  to the REPL. `SAVE_TS` masks; `SAVE_ZX` didn't until the ZX48
  migration.
- **`while MQ.tx_fifo() != 0: pass` can hang forever.** It waits for the
  Z80 to drain, which never happens if the Z80 has stopped asking (in
  ZX48 compatible mode the Pico streams the whole tape, so the tail is
  routinely unread). Bound the wait, then drain TX explicitly — leaving
  bytes behind is the orphan-byte bug above.
- **Never let an exception escape a command handler.** `PROCESS_CMD`
  writes the V6 pre-load as the last thing it does. If a handler raises,
  that write is skipped — the main loop catches the exception and
  `continue`s — so the NEXT command's pre-header phase reads `0x00`
  from an empty TX FIFO and reports J. The symptom shows up one command
  *after* the one that actually failed, which makes it maddening to
  trace. Since the issue-#42 fix the dispatch runs inside a
  `try`/`finally` whose `finally` is the tail, so this is handled
  centrally — but the underlying rule still binds anything you add
  outside that block: **every exit path from a command must leave
  exactly one `0x01` in TX.** Not zero (Report J on the next command),
  and not two (the second is an orphan byte that shifts the next data
  block — Report R). A recovery path that stages its own pre-load, as
  the body-read timeout does, must stay OUTSIDE the `try`, or the
  `finally` hands it a second one.
- **Any idle loop you add must call `DRAIN_STDIN(MQ)`.** The firmware
  never reads stdin, and MicroPython (v1.20, and v1.29) only notices Ctrl-C while
  moving USB bytes into its 512-byte stdin buffer. Once 511 bytes of
  any other text arrive (a tool writing before its Ctrl-C landed, a
  terminal echoing telemetry back), the buffer is full and no Ctrl-C
  ever gets through. The Pico runs on, but USB stays deaf until a reset.
  Reproduced on hardware with 600 bytes (2026-09-28).
  `TS2068_IO` and `ZX48_IO` drain stdin at their idle heartbeat; see
  `src/test/stdin_drain_hosttest.py`.
- **A reply the ROM answers straight away must say READY, not IDLE.**
  `MQ_READY()` sets Y to `0xFF`, which is READY *and* IDLE. A ROM that
  sends its next command as soon as it has this one's answer
  (the fdd channel driver: `CLOSE #` flushes, then sends `tpi:chclose`
  at once) waits only for IDLE after its SYNC. If IDLE is already up while
  `PROCESS_CMD`'s tail is still draining and logging, the tail's own IDLE
  lets the pre-header go before the main loop is capturing. Only the
  FIFO's 4 bytes survive: `Partial pre-header 4/10`, `RECOVERED`, Report T
  (hardware, 2026-09-29). Channel handlers answer with `CH_READY()`
  (`0xF7`, READY without IDLE), and the ROM waits for IDLE before its SYNC.
- **ROM side: the 2068's bank switch is not interrupt-safe.** Timex's
  switch routine (the RAM copy of EXROM `$12BE`/`$134A`) writes port `FFh`
  and then `F4h` with interrupts enabled. Between the two, chunk 0 can be
  the empty DOCK bank, and an interrupt there runs `RST 38` over `$FF`
  until memory is wiped (`39 00` everywhere). Anything that crosses banks
  often (the fdd channel driver crosses twice per character) must do so
  under `DI`. The TS-Pico's relocated BEEPER (`$03F3` → EXROM) was the
  other hot path: the editor clicks once per character, including every
  character `INPUT #` reads from a file. See `src/rom/fdd/fddcmd.asm`
  `GUARDED` / `G_BEEP` and `docs/DISK_COMMANDS_SPEC.md` §4.

---
- **Don't write `0x40`.** It was the single-port "continue" byte. Port
  `$0F` is a register now; a `0x40` in TX is read as data (§1).
- **One answer per command, including external commands.** The two example
  commands in `TS/extcmd.py` used to break this:
  `.rndw` answered `0x01` and then sent the word as extra bytes, `.fact` sent
  a message and then more bytes with a blocking `MQ.put`. The extra bytes are
  orphans; from BASIC they happened to be read by `IN 14`, and the next
  command's SYNC now clears what's left, but on a ROM without SYNC (1.1) they
  became the next command's status. `src/test/extcmd_hosttest.py` checks the fixed ones.
- **Send `N` in upper case to end a `$86` loop.** The Pico compares with 78;
  the ROM upper-cases letters, a machine-code client must too.
- **Byte 23 in a channel write is always a TAB**, in binary mode too (§7).
  Binary data containing `$17` can't go through `tpi:chwr`.
- **Underscore constants don't cross modules on the Pico.** `_1_OK`,
  `_6_6_Num2Big` and friends are `const()`s with a leading underscore, which
  MicroPython substitutes at compile time and never stores on the module.
  `tp._6_6_Num2Big` from `TS/extcmd.py` worked under CPython and raised
  `AttributeError` on hardware, so `SAVE "tpi:.fact" CODE 33,0` gave J instead
  of 6. Host tests that run under CPython won't see it unless they hide those
  names, as `src/test/extcmd_hosttest.py` does.
- **The development copies must match.** `src/dev_tspico.py` and
  `src/dev_extcmd.py` replace the frozen modules when copied to the Pico.
  `src/test/dev_sync_hosttest.py` fails CI when they drift from
  `src/TS/tspico.py` / `src/TS/extcmd.py`; refresh them with `cp`.

---

## 14. Where to look in the source

| File | What's in it |
|------|--------------|
| `TS/tspico_io.py` | the PIO programs (`TS_IO_DUAL`, `set_ctrl`, `sel_bank`), `MQ_STATUS`/`MQ_TO_IDLE`/`RX_CAPTURE`/`RX_BLOCK`/`TX_ROOM`/`MQX`, `LOAD_TS`, `SAVE_TS`, the ZX48 handlers |
| `TS/tspico.py` | the dispatcher (`TS2068_IO`), `PROCESS_CMD`, every built-in command (`SA_funct`), `SEND_MSG`/`SEND_MSG2`/`CMD_PUT`/`CH_READY`/`SD_CALL`, `PRINT_IO`, `PICO_STATUS` |
| `TS/channels.py`, `TS/catalog.py`, `TS/native.py` | channel, listing/path and `f:` file logic (pure Python, host-tested) |
| `TS/extcmd.py` | the external-command table and its examples |
| `rom/patches/tspico-sync.asm` | SYNC, BREAK abort, RECOVERED/Report T, the BIOS wait |
| `rom/fdd/fddcmd.asm`, `tools/build-rom.py` | disk commands, `f:`/`d:` channels, function `$88`, `C_END2` |
| `test/` | host tests and bus harnesses |
| `manifest.py` | the MicroPython freeze list: a new `TS/` module must be added here |

## 15. Further reading

- [`PROTOCOL_GUIDE.md`](PROTOCOL_GUIDE.md) — the same protocol, explained
  from the beginning.
- [`GUSTAVO_PROTOCOL.md`](GUSTAVO_PROTOCOL.md) — the original design, and why
  the ROM was modified. Historical: where it differs, this document wins.
- [`EXTCMD_PROTOCOL.md`](EXTCMD_PROTOCOL.md) — external commands.
- [`DISK_COMMANDS_SPEC.md`](DISK_COMMANDS_SPEC.md) — the ROM's disk commands and
  channels, from the BASIC side.
- [`rom-analysis/`](rom-analysis/) — the ROM disassemblies, memory map and
  error-trapping notes.
- [`reference/`](reference/README.md) — the programmer's reference: every
  function, variable and ROM routine behind this protocol, in source order.
- MicroPython rp2: https://docs.micropython.org/en/latest/library/rp2.html;
  RP2040 datasheet, chapter 3 (PIO).
