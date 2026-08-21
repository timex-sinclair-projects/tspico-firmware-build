# TS-PICO ROM v1.1 → v1.5w: the complete delta

**Bottom line: the entire difference between the shipping ROM set (v1.1) and the
next one (v1.5w) is 15 bytes in the EXROM. It closes a half-duplex
synchronization hole in the Pico's Y/N prompt (function `0x86`): the Z80 sends the
user's keypress to the Pico and then immediately reads the Pico's next string back
without ever waiting for the Pico to become ready. v1.5w inserts that missing
wait, and gives the loop a bounded (~20 s), BREAK-abortable exit that reports
`J Invalid I/O device`.**

The HOME ROMs are byte-identical. Nothing else changed.

| Image | v1.1 md5 | v1.5w md5 | Verdict |
|---|---|---|---|
| HOME | `620d6ded106839b73dd6dac9f98f7ed9` | `620d6ded106839b73dd6dac9f98f7ed9` | **identical** |
| EXROM | `b4a1596823dfda0f9b8dc3d2dec816cb` | `639c62742fa388750a0624e1270e1583` | 15 bytes / 2 hunks |

Reproduce with `python3 tools/romdiff.py`.

## The two hunks

```
21F5-21F6 (2)   v1.1 : e7 21          v1.5w: a1 22
22A1-22AD (13)  v1.1 : ff ×13         v1.5w: cd 54 1a 38 03 c3 e7 21 f1 3e 09 37 c9
```

Hunk 1 retargets one `JP NZ` operand. Hunk 2 writes a 13-byte stub into `0xFF`
filler. In v1.1 the last non-`0xFF` byte in the EXROM is `0x22A0`; in v1.5w it is
`0x22AD`. Pure append — nothing was displaced and no existing address moved.

## Which handler this is

The patched loop is the handler for **function `0x86` — "PRINT STRING WITH LOOP
(Y/N)"**, per the function table in
[`LOW-LEVEL-PROTOCOL-V5.TXT`](../LOW-LEVEL-PROTOCOL-V5.TXT).

> **Why `CP 85h` means function `0x86`.** The Pico returns a *status byte*, and the
> ROM decrements it before dispatching. At `0x228A`, immediately before the chain
> call:
> ```asm
> 228A: 3D        DEC A          ; A = status - 1
> 228B: C8        RET Z          ; status 1 = OK -> done
> 228C: CD 6F 02  CALL 026F      ; else dispatch FUNCTION chain with A = status-1
> ```
> Every `CP nn` in the chain therefore matches status `nn+1`. `CP 85h` is status
> **`0x86`**. Four independent structural checks confirm the offset — see the chain
> table in [PROTOCOL_FROM_ROM.md](PROTOCOL_FROM_ROM.md).

## Hunk 1: the retargeted jump

```asm
21DF: FE 85        CP   85h            ; status 0x86 = PRINT STRING WITH LOOP (Y/N)?
21E1: 20 1A        JR   NZ,21FD        ; no -> try status 0x87
21E3: CD C3 01     CALL 01C3           ; read status byte + open channel 0xFE (main screen)
21E6: F5           PUSH AF             ; <-- stack depth +1 for the whole loop

21E7: CD 5F 04     CALL 045F           ; <-- LOOP HEAD: READ the prompt string from the
                                       ;     Pico and print it
21EA: DA 13 08     JP   C,0813         ; read failed -> 0813: POP AF; RET
21ED: CD 71 04     CALL 0471           ; wait for keypress, then SEND the key to the Pico
21F0: E6 5F        AND  5Fh            ; fold to uppercase
21F2: FE 4E        CP   4Eh            ; did the user answer 'N'?
21F4: C2 E7 21     JP   NZ,21E7        ; *** v1.1: not 'N' -> re-read immediately ***
21F7: C3 10 08     JP   0810           ; 'N' -> 0810: CALL 05FA; POP AF; RET
```

v1.5w changes exactly one operand:

```asm
21F4: C2 A1 22     JP   NZ,22A1        ; *** v1.5w: go via the new guard stub ***
```

## Hunk 2: the new guard stub

```asm
22A1: CD 54 1A     CALL 1A54           ; WAIT_PICO_READY - the missing handshake
22A4: 38 03        JR   C,22A9         ; carry = timed out / user pressed BREAK
22A6: C3 E7 21     JP   21E7           ; Pico ready -> resume the loop, unchanged
22A9: F1           POP AF              ; balance the PUSH AF at 21E6
22AA: 3E 09        LD   A,09h          ; error code 9
22AC: 37           SCF                 ; carry = error
22AD: C9           RET                 ; -> BASIC Report J
```

On the happy path this is transparent — `JP 21E7` resumes the identical loop. It
only diverges when the Pico fails to become ready.

Note the `POP AF` at `0x22A9`. The loop runs one `PUSH AF` deep (from `0x21E6`) and
both pre-existing exits (`0x0810`, `0x0813`) pop it. The new error exit pops it
too, so **the stack stays balanced on every path.** This is a correct patch.

## Why the missing wait matters

The ROM's rule is *wait for the Pico to be ready before you touch the data port*.
`WAIT_PICO_READY` at `0x1A54` — identical in both versions — is that primitive:

```asm
1A54: F5           PUSH AF
1A55: C5           PUSH BC
1A56: 06 E2        LD   B,0E2h         ; 226 poll attempts, then give up
1A58: CD 55 06     CALL 0655           ; read status port 0x0F (via the BREAK guard)
1A5B: CB 77        BIT  6,A            ; bit 6 = Pico READY (D6, per the spec)
1A5D: 20 0F        JR   NZ,1A6E        ; ready -> success
1A5F: 10 F7        DJNZ 1A58           ; retry
1A61: 3E 40        LD   A,40h          ; (dead - A is overwritten at 1A6A)
1A63: 00 00 00 00 00                   ; five NOPs: something was patched out here
1A68: C1           POP  BC
1A69: F1           POP  AF
1A6A: 3E 02        LD   A,02h          ; internal timeout code 2
1A6C: 37           SCF                 ; carry = error
1A6D: C9           RET
1A6E: C1           POP  BC             ; .ready
1A6F: F1           POP  AF
1A70: 37           SCF
1A71: 3F           CCF                 ; carry = 0 = success
1A72: C9           RET
```

**The write side of this loop already obeys the rule.** `CALL 0471` waits for a
keypress and tail-jumps to `0x1C40`, which waits for ready *before* sending:

```asm
0471: CD C1 03     CALL 03C1           ; -> HOME 02B0 = F_K_SCAN (KEY-SCAN)
0474: 13           INC  DE             ; KEY-SCAN returns DE=FFFF when no key,
0475: 7A           LD   A,D            ;   so INC DE -> 0000 -> Z when nothing pressed
0476: B3           OR   E
0477: 20 F8        JR   NZ,0471        ; a key is still down -> wait for release
0479: CD 46 05     CALL 0546           ; poll for a new keypress
047C: 28 FB        JR   Z,0479         ; none yet -> keep waiting
047E: C3 40 1C     JP   1C40           ; tail-call: send the key

1C40: CD 54 1A     CALL 1A54           ; *** waits for ready BEFORE writing ***
1C43: DA 87 1B     JP   C,1B87         ; timeout -> error
1C46: C3 9D 22     JP   229D           ; OUT (0Eh),A - send the key byte
```

**The read side, on the loop-back edge, does not.** In v1.1, the instant the key
byte has gone out, `JP NZ,21E7` drops straight back into `CALL 045F`, which reads
the Pico's next string off port `0x0E` — with no `WAIT_PICO_READY` in between. The
Z80 asks for the Pico's answer before the Pico has been given the chance to say it
is ready with the answer.

So the sequence per iteration in **v1.1** is:

```
  print string  ->  wait for key  ->  [wait ready]  ->  send key  ->  READ AGAIN
                                       ^^^^^^^^^^                     ^^^^^^^^^^
                                       handshake present         handshake MISSING
```

and in **v1.5w**:

```
  print string  ->  wait for key  ->  [wait ready]  ->  send key  ->  [wait ready]  ->  READ AGAIN
                                                                       ^^^^^^^^^^
                                                                       handshake added
```

This is the ROM's own idiom, applied to the one edge that lacked it. `0x1A54` has
nine call sites; the one at `0x2247` is the same shape (`CALL 1A54` / `JR C` →
error 9), and `0x2274`'s driver does `CALL 229D` → `CALL 1A54` → `CALL 2298`,
i.e. **write, wait, read** — exactly the discipline the `0x86` loop was missing.

## What v1.5w buys you

1. **Correct synchronization** on the Y/N loop's read edge — the substantive fix.
2. **A bounded wait.** `WAIT_PICO_READY` gives up after 226 polls.
3. **A BREAK escape.** Every status read goes through `0x0655`, which checks the
   keyboard first:
   ```asm
   0655: CD 9F 06   CALL 069F          ; 069F reads keyboard row 0xFE
   0658: D2 AA 06   JP   NC,06AA       ; key pressed -> 06AA: POP BC; JP 1A61 (abort)
   065B: DB 0F      IN   A,(0Fh)       ; else read the status port
   065D: C9         RET
   ```
   BREAK and timeout share the `0x1A61` exit, so callers cannot tell them apart.
4. **A defined failure report** — error 9 — instead of reading whatever the data
   port happened to hold.

## What error 9 means: **Report J**, not Report 9

The user sees **`J Invalid I/O device`**.

`LD A,09h` looks like it should give Report 9 — STOP. It does not. The dispatcher
at `0x1BF3` is entered with `A = status - 1`, and the internal error code `9` is
already in that decremented form, so it lands as **status 10 → Report J**:

| A at `0x1BF3` | Status | Report |
|---|---|---|
| 8 | 9 | 9 — STOP statement |
| **9** | **10** | **J — Invalid I/O device** ← this path |

Which is semantically right: "the device didn't answer" *should* be Report J. It
also means `LOW-LEVEL-PROTOCOL-V5.TXT:195-196` is correct when it promises a
timeout returns "ERROR J - INVALID I/O DEVICE" automatically.

Note the laundering: `WAIT_PICO_READY` returns `A=02h` on timeout, but callers
discard it and substitute 9. `A=02h` is only visible via the BIOS entry at
`0x184C`.

## Practical notes for troubleshooting

- **v1.5w is strictly safer than v1.1 on this path** and behaviourally identical
  everywhere else. Chunk 0 of the EXROM and the whole HOME ROM are untouched, so
  any protocol trace, symbol address, or timing measurement taken on one applies
  unchanged to the other outside the `0x86` handler.
- **v1.5w does not fix the root cause.** It bounds and detects the failure. If you
  see error 9 on v1.5w, the Pico genuinely failed to raise status bit 6 within 226
  polls — that is a Pico-side or timing problem and still needs diagnosing.
- **Suspect this path when a Y/N prompt from the Pico misbehaves** — garbled
  prompt text, a prompt that repeats, or a prompt that ignores `N`. On v1.1 those
  are all consistent with the Z80 reading the string before the Pico has it ready.
- **The guard's timeout is ~20 seconds, not milliseconds.** `LD B,0E2h` is only 226
  polls, but each poll costs ~88 ms (the status read goes through a debounced
  keyboard scan), giving **19.88 s**. Run `python3 tools/wf_nph_timing.py`. So on
  v1.5w a stalled Pico produces a ~20-second freeze and *then* `J Invalid I/O
  device` — not an instant error. Users will report that as "it hangs for a while
  then errors"; that is the fix working.

## Open questions

- **The five NOPs at `0x1A63-0x1A67`**, preceded by a dead `LD A,40h`, are a patch
  remnant inside `WAIT_PICO_READY`'s timeout exit. `0x40` is the READY bit pattern.
  Something was deliberately removed here and it is not recorded anywhere in
  `docs/`. Worth asking Gustavo.
- **The `w` in "1.5w"** is unexplained in the repo.
- **Was the v1.5w fix prompted by a specific field failure?** The patch is narrow
  enough that it looks like a response to a concrete bug report rather than an
  audit sweep. If so, the report would say what the Pico was doing when it failed
  to become ready — which is the root cause this patch only contains.
