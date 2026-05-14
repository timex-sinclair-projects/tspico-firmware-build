# Extension Command Protocol — Design Document

**Status: UNDER DEVELOPMENT — postponed beyond the current dual-port
release. See "Decision pending" below.**

This document captures the design space and proposed contract for
user-extensible Pico-side TPI commands (the `TPI:.XXX` "extcmd"
mechanism), as it applies to the dual-port PIO firmware. Written
after testing exposed a structural incompatibility between the
current extcmd implementation and the dual-port V6 pre-load chain.

This is a working document. The contract is not yet ratified — the
team needs to discuss the open questions in §6 before any
implementation lands.

---

## 1. What extcmd is for

The TPI protocol reserves `TPI:.XXX` commands (note the leading dot)
for user-extensible handlers. A user can write Python code in
`TS/extcmd.py` (or `/dev_extcmd.py` for the dev override) that runs
on the Pico when the 2068 issues a `SAVE "tpi:.something"` command,
and that returns a result to the 2068.

Two example handlers ship in the current `TS/extcmd.py`:

- `FACTORIAL` (`TPI:.FACT`) — compute *n!* and return as a
  type-length-value response.
- `RND_WORD` (`TPI:.RNDW`) — read a random word from `/words.txt` on
  Pico flash and return it as a stream of ASCII characters.

---

## 2. What broke with the dual-port migration

The original extcmd protocol was designed against the single-port
firmware. In single-port, the Z80's `IN 14` reads consumed bytes from
the same FIFO that carried protocol status and data, and there was no
"pre-load for the next command's initial status." So a handler could
write a stream of bytes terminated by `0x00`, BASIC could `IN 14`
until it saw `0`, and everything would line up correctly.

In dual-port (the V6 pattern), `PROCESS_CMD`'s tail writes a `0x01`
into TX FIFO after every handler returns. This byte serves as the
**initial status** for the *next* command's pre-header phase — when
the Z80 sends a new `SAVE "tpi:..."`, its first `IN A,($0E)` reads
that pre-load and sees `0x01` = OK. The next command can then proceed.

This **V6 pre-load chain** is the load-bearing invariant for dual-port
command flow. Without it, every command's pre-header phase would read
`0x00` from empty TX and report J.

The current extcmd implementation breaks this invariant:

```python
# RND_WORD (current)
def RND_WORD(MQ, TSP, pre, cmd):
    MQ.put(0x01)                  # status byte (Z80 sees as "OK")
    ...
    for el in word:
        MQ.put(el)                # word characters (orphan bytes!)
    return
```

The Z80's SAVE statement reads the `0x01` status and considers the
command done. The word characters are left in TX. Now if the BASIC
program does an `IN 14` loop to read them (as Ryan's `picotest.tap`
does), it reads:

1. The word characters → prints them
2. **The V6 pre-load `0x01`** ← consumed!
3. `0x00` from empty TX → terminates the loop

The V6 pre-load is gone. The next `SAVE "tpi:..."` command's
pre-header phase reads `0x00` → Report J. BASIC's error handler may
recover, but Z80 has already aborted the command body — leaving
`PROCESS_CMD` blocked on `MQ.get()` inside its body-read loop. The
Pico effectively halts.

This is **not a regression in the dual-port migration** — it's a
structural mismatch between extcmd's single-port-era design and the
dual-port V6 chain. Both Ryan's `RND_WORD` and Ricardo's older
patterns have the same issue.

---

## 3. The dual-port protocol contract for extcmd handlers

Three constraints any new extcmd design must satisfy:

### 3a. The V6 pre-load belongs to PROCESS_CMD, not the handler

`PROCESS_CMD` writes `MQ.put(0x01)` as the last thing it does before
returning. Handlers should NOT write a V6 pre-load themselves — they
just write their response data and return.

### 3b. The handler's response must have a known length

BASIC has no out-of-band way to detect "no more bytes coming." If
BASIC reads bytes "until it sees `0x00` from empty TX," it will
consume the V6 pre-load that `PROCESS_CMD` writes after the handler
returns. The handler must therefore frame its response so BASIC knows
exactly how many bytes to read.

### 3c. The status byte (first byte the Z80 reads) determines the
       Z80-side protocol that follows

This is per Gustavo's TPI v2.4 spec. The status byte is read by the
2068's BASIC SAVE statement at the end of WAIT EXECUTION (byte 27 of
the spec's exchange table on p.5). The Z80's response depends on
which status code:

| Status | Z80 behavior | Useful for |
|---|---|---|
| `0x01` | "OK, command done" — returns to BASIC immediately. | Status-only commands (no return data) |
| `0x02–0x09` | BASIC error reports (R, F, Q, C, 6, 8, A, 9). | Signaling failure |
| `0x0A–0x7F` | Various error reports (mostly mapped to J). | Signaling failure |
| `0x81` | PRINT_STRING — Z80 reads chars until `0x00`, prints them. | Display-only output (no BASIC-side reading) |
| `0x82–0x86` | Other ROM-defined function codes. | Specialized output |
| `0x80, 0x87–0xFF` | **Behavior unverified — see §6.** Likely returns to BASIC; BASIC then does `IN 14` to read more. | Length-prefixed data return |

---

## 4. Recommended response shapes

Three response patterns cover all the use cases we've encountered:

### 4a. Status-only response (no data return)

For commands like `tpi:.nop` that just signal success/failure.

```python
def MY_CMD(MQ, TSP, pre, cmd):
    MQ.put(0x01)                  # OK (or 0x02-0x09 for an error)
    return                        # PROCESS_CMD writes V6 pre-load
```

BASIC consumer:

```basic
10 SAVE "tpi:.mycmd"
20 REM SAVE statement consumed the status byte. BASIC continues.
30 REM V6 pre-load is intact. Next command works.
```

### 4b. Print-only response (just display text)

For commands that produce human-readable output but BASIC doesn't
need to capture the bytes — e.g., a help message.

```python
def MY_CMD(MQ, TSP, pre, cmd):
    msg = "Hello from Pico"
    MQ.put(0x81)                  # PRINT_STRING function code
    MQ.put(0x01)                  # status: no error
    for c in msg:
        MQ.put(ord(c))
    MQ.put(0x00)                  # end-of-string terminator
    return                        # PROCESS_CMD writes V6 pre-load
```

BASIC consumer:

```basic
10 SAVE "tpi:.mycmd"
20 REM Word appears on screen via Z80 ROM's PRINT_STRING handler.
30 REM V6 pre-load is intact. Next command works.
```

### 4c. Length-prefixed data response (return bytes to BASIC)

For commands that return data the BASIC program needs to capture
into a variable.

```python
def MY_CMD(MQ, TSP, pre, cmd):
    payload = b"some result data"

    MQ.put(0x80)                  # custom function code (see §6)
    MQ.put(len(payload))          # 1-byte length (0-255)
    for b in payload:
        MQ.put(b)
    return                        # PROCESS_CMD writes V6 pre-load
```

BASIC consumer:

```basic
10 SAVE "tpi:.mycmd"
20 REM SAVE consumed the 0x80 status byte (if the ROM treats it
30 REM as a benign function code — see Open Questions §6).
40 LET length = IN 14
50 LET data$ = ""
60 FOR i = 1 TO length
70   LET data$ = data$ + CHR$ (IN 14)
80 NEXT i
90 PRINT data$
100 REM Read EXACTLY `length` bytes. Stop. V6 pre-load preserved.
```

**Critical**: BASIC must read **exactly** `length` bytes. Do NOT use
`IF c <> 0 THEN GO TO ...` patterns — those consume the V6 pre-load.

For payloads longer than 255 bytes, extend the protocol with a
2-byte length (LSB then MSB), or send length=0 to indicate "use the
next 2 bytes as the real length." This is design space the team
should agree on before implementing.

---

## 5. Why Ryan's picotest IN-14 loop won't work

Ryan's test program at `test-progs/picotest.tap` uses this pattern
to consume external command output:

```basic
1186 LET c = IN 14
1188 IF c < 32 THEN PRINT c
1190 IF c >= 32 THEN PRINT c, CHR$ c
1192 IF c <> 0 THEN GO TO 1186
```

This was correct for single-port firmware where there was no V6
pre-load. In dual-port, it always reads one extra byte beyond the
response — the V6 pre-load — and then sees `0` from empty TX. The
V6 pre-load is gone, the next command halts.

There's no clean handler-side fix for this pattern. The BASIC has to
be updated to read a known-length response.

---

## 6. Open questions for the team

These need to be resolved before implementation.

### Q1. What does the 2068 ROM do with status codes `0x80`, `0x87–0xFF`?

The spec (p.5) documents `0x81–0x86` as ROM-defined function codes.
The comment in current `extcmd.py` claims `128-199 = "normal" custom
response, 200 = OK, 201+ = error conditions` — but this is
Ryan/Ricardo's convention, not Gustavo's spec. The actual ROM
behavior for these codes needs to be verified empirically:

- Does the ROM dispatch them to a custom handler?
- Does it return to BASIC immediately (so BASIC can `IN 14`)?
- Does it raise an error report?

If it errors, **§4c's length-prefixed pattern won't work as written**
— we'd need to embed the data inside a `0x81 PRINT_STRING` response
and have BASIC parse the bytes back out.

### Q2. Should `PROCESS_CMD` strip the V6 pre-load for extcmd?

An alternative to the contract above: `PROCESS_CMD` could omit the
V6 pre-load for `EXT_SA_FUNCT` dispatches, and require EXT handlers
to write their own V6 pre-load as the last byte of their response.

Pros: handlers can build a response stream that ends with `0x01`,
and a BASIC `IN 14` "read until 0" loop wouldn't consume any V6
pre-load (because the handler's response stream ends with the V6
byte, not a `0x00`).

Cons: handlers that forget to write the V6 pre-load break the next
command. The contract is more error-prone.

Decision: probably keep V6 pre-load in `PROCESS_CMD` for consistency
with SA_funct handlers. Worth confirming with the team.

### Q3. Should `PROCESS_CMD` add a body-read timeout?

Independent of the extcmd protocol, `PROCESS_CMD`'s body-read loop
(`for l in rl: cmd[l] = MQ.get()`) blocks forever if the Z80 aborts
the command mid-stream (which happens when J fires at the pre-header
phase). A 1-second timeout would prevent the Pico from "halting"
when a J cascade occurs, making the firmware more robust.

This is independently useful and not specific to extcmd.

### Q4. Should we keep `RND_WORD` / `FACTORIAL` as shipped examples?

If the contract changes, both need rewriting to follow it. The team
should decide whether to:

a) Rewrite both as good examples of the new contract.
b) Remove `RND_WORD` (the simpler one) and keep `FACTORIAL` only,
   since its length-prefixed pattern more closely matches the
   recommended approach.
c) Mark extcmd as "under development" / "not for end-user use"
   until the contract is ratified.

---

## 7. Decision pending — feature postponed for current release

For the current dual-port release (PR #3), **extcmd is being shipped
as-is, with the known limitation that user-defined commands can hang
the Pico if their BASIC consumer uses the "read until 0" pattern.**

The path forward:

1. Ship the current dual-port release (with this document calling
   out the issue).
2. Team discusses Q1–Q4 above and ratifies a contract.
3. New UF2 build with refactored `TS/extcmd.py`, sample BASIC, and
   updated docs.

End users wanting to write extcmd handlers in the interim should:

- Use `0x01` status-only responses (§4a) — these work cleanly.
- Avoid commands that return data via `IN 14` loops until the
  contract is ratified.
- Or use `0x81` PRINT_STRING (§4b) for display-only output that
  doesn't need BASIC-side capture.
