# BREAK, the SAVE prompt, and what the Pico is never told

Three questions that kept coming up, answered from the EXROM. Addresses are
`ROMs/TSPICO-15w-exrom` unless stated.

## Summary

| Question | Answer |
|---|---|
| Does `SAVE ""` reach the Pico? | **No.** Rejected at `$0228` with Report F, before any pre-header exists. Same branch rejects names over 10 characters. The same check exists in the stock Spectrum 48K ROM at `$0634`. |
| Does the "press any key" prompt send anything first? | **No.** The wait at `$08AA` precedes the first block send at `$0893`. |
| Does SPACE abort? | **Yes — via `$00E5`, which tests SPACE alone.** Two different checks exist and they disagree; see below. |
| Does BREAK at the prompt stop bytes reaching the Pico? | **No.** The keypress comes first and the wait has no break test, so SPACE *satisfies* it; the header block is then sent normally and `$00E5` reports D on the way back out. |
| Is the Pico told when the user BREAKs? | **No.** Provably — see below. |

## `SAVE ""` and over-long names — rejected before the Pico

The filename evaluator, `$021A`:

```asm
021A  21 F6 FF   LD HL,$FFF6      ; -10
021D  0B         DEC BC           ; BC = filename length
021E  09         ADD HL,BC        ; carry <=> length >= 11 ... or length 0
021F  03         INC BC
0220  30 0F      JR NC,$0231      ; length 1..10 -> normal path
0222  3A 74 5C   LD A,($5C74)     ; T-ADDR low = the operation
0225  A7         AND A
0226  20 02      JR NZ,$022A      ; not SAVE -> tolerate
0228  CF 0E      RST 8 : DEFB $0E ; <- Report F.  SAVE only.
022A  78 B1      LD A,B : OR C
022B  28 0A      JR Z,$0238       ; LOAD, empty name -> match anything
022E  01 0A 00   LD BC,$000A      ; LOAD, long name  -> truncate to 10
```

One comparison covers both rejections: an **empty** name makes `DEC BC` wrap to
`$FFFF`, so `$FFF6 + $FFFF` carries and lands in the same branch as an over-long
one. So for SAVE, length 0 and length > 10 are the same error.

The guard on `T-ADDR` is why `LOAD ""` is legal and `SAVE ""` is not: `T-ADDR`
low is 0 for SAVE, non-zero for LOAD/VERIFY/MERGE
([PROTOCOL_FROM_ROM.md](PROTOCOL_FROM_ROM.md) has the full table).

This is all in the filename evaluator — the pre-header builder at `$1BA0` has not
run and `$229D` has not been touched. **Nothing reaches the Pico.**

## The SAVE prompt, and why SPACE does not abort

`$0868` is the tape-prompt sequence:

```asm
0868  CD 26 04   CALL $0426
086B  AF         XOR A                  ; message index 0
086C  11 89 3C   LD DE,$3C89            ; "Start tape, then press any key."
086F..0884       print via the HOME thunk at $0F99
0886  FD CB 02 EE SET 5,(IY+$02)        ; TV-FLAG: clear the lower screen
088A  CD AA 08   CALL $08AA             ; <-- THE KEY WAIT
088D  DD E5      PUSH IX
088F  11 11 00   LD DE,$0011            ; 17 = header length
0892  AF         XOR A                  ; flag 0x00 = header
0893  CD 68 00   CALL $0068             ; <-- FIRST CONTACT WITH THE PICO
0896  DD E1      POP IX
0898  06 32      LD B,$32
089A  76 10 FD   HALT : DJNZ            ; ~1 s pause between blocks
089D  DD 5E 0B   LD E,(IX+$0B)          ; data length
08A0  DD 56 0C   LD D,(IX+$0C)
08A3  3E FF      LD A,$FF               ; flag 0xFF = data
08A5  DD E1      POP IX
08A7  C3 68 00   JP $0068               ; send the data block
```

and the wait itself:

```asm
08AA  F5 C5 D5   PUSH AF : PUSH BC : PUSH DE
08AD  01 40 9C   LD BC,$9C40
08B0  0B 79 B0   DEC BC : LD A,C : OR B
08B3  20 FB      JR NZ,$08B0            ; ~40000-iteration debounce
08B5  AF         XOR A
08B6  DB FE      IN A,($FE)             ; A=0 -> scan ALL keyboard rows at once
08B8  E6 1F      AND $1F
08BA  FE 1F      CP $1F
08BC  28 F7      JR Z,$08B5             ; loop while no key is down
08BE..08D8       HOME thunk, restore, RET
```

**The wait sends nothing** — `CALL $0068` is three instructions later. So the
belief that a SAVE aborted at the prompt never touched the Pico is correct *for
an abort that happens at the prompt*.

**But the wait has no BREAK test.** It exits on *any* key, SPACE and
CAPS+SPACE included, and proceeds to `$0893`. What actually happens when BREAK
is held at the prompt:

1. The wait sees keys down and returns.
2. `$0068` → `$1879`, whose fourth instruction group is
   `$189A: CALL $229D` — **the first pre-header byte goes out**, with no BREAK
   check before it.
3. The first BREAK-sensitive point is the first `CALL $1A54` (`WF_NPH`)
   further in, via `$0655` → `$069F`.

So BREAK at the prompt does **not** prevent the transaction; it aborts a few
bytes in, leaving the Pico mid-transaction. That is the same failure shape as
breaking out of a LOAD loop.

### There are TWO break checks and they do not agree

This is the part that is easy to get wrong — I got it wrong first time round.

**Check 1 — `$00E5`, the tape-return exit. SPACE alone.** Stock TS2068 EXROM
code, byte-identical to the genuine image, and the direct analogue of the
Spectrum's `SA/LD-RET` at `$053F`:

```asm
00E5  F5         PUSH AF
00E6  3A 48 5C   LD A,($5C48)   ; BORDCR
00E9  E6 38      AND $38
00EB  0F 0F 0F   RRCA x3
00EE  D3 FE      OUT ($FE),A    ; restore the border
00F0  3E 7F      LD A,$7F
00F2  DB FE      IN A,($FE)     ; row $7F, bit 0 = SPACE
00F4  1F         RRA
00F5  FB         EI
00F6  38 02      JR C,$00FA     ; SPACE up -> fine
00F8  CF 0C      RST 8 : DEFB $0C  ; <- Report D BREAK.  SPACE ALONE.
00FA  F1 C9      POP AF : RET
```

**Every Pico block send returns through it**, because the sender pushes it as its
own return address:

```asm
1882  21 E5 00   LD HL,$00E5
1885  E5         PUSH HL
```

**Check 2 — `$069F`, guarding the Pico status wait. SPACE *and* CAPS SHIFT.**
This one is TS-Pico code (the `$0655`/`$069F` region differs from the genuine
EXROM in 59 of 96 bytes):

```asm
069F  CD 56 08   CALL $0856     ; 10x $07F6, debounced
06A2  1F         RRA            ; carry = bit 0 of row $7F = SPACE
06A3  D8         RET C          ; SPACE not down -> carry set -> carry on
06A4  3E FE      LD A,$FE
06A6  DB FE      IN A,($FE)     ; row $FE, bit 0 = CAPS SHIFT
06A8  1F C9      RRA : RET      ; carry = CAPS SHIFT state
```

Carry clear — the abort at `$0655`'s `JP NC,$06AA` — needs **both** bits low.

So: **SPACE alone aborts a tape operation** (check 1, and this is what you see in
FUSE, because check 1 is stock), while **a Pico ready-wait needs full BREAK**
(check 2). Do not generalise either one to the other.

### What SPACE at the prompt actually does

1. The wait at `$08AA` sees a key down and returns — it has no BREAK test.
2. `$0893: CALL $0068` → `$1879`, which pushes `$00E5` as its return and sends
   **the whole 21-byte header block to the Pico**.
3. On return, `$00E5` finds SPACE still down and reports **D BREAK**.
4. The data block is never sent.

**The order is prompt → keypress → header → break noticed.** The header is sent
*because* the key was pressed, not before it. `$08AA` is a plain "is any key
down" scan (`IN A,($FE)` with `A=0`, `AND $1F`, loop while nothing is down), so
SPACE counts as the key that starts the save rather than as a break.

**A consequence worth testing on hardware:** whether SPACE aborts at all may
depend on how long it is held. Between the keypress at `$08B6` and the re-test at
`$00E5` sit the HOME thunk, the pre-header, the header block, and at least one
`WF_NPH` wait — and every `WF_NPH` costs >=88 ms even when the Pico answers
immediately (see [PROTOCOL_FROM_ROM.md](PROTOCOL_FROM_ROM.md)). A typical
keypress is 80-150 ms, so a quick tap may well be released before `$00E5` looks,
letting the SAVE run to completion. On stock hardware, where the tape routine has
no Pico round-trip in between, that gap is far smaller — which is why FUSE aborts
reliably and a TS-Pico might not. Unverified; it is an inference from the timing,
not something read off a trace.

So the user sees `D BREAK` and assumes nothing happened, but the Pico has
received a complete SAVE header and is waiting for a data block that will never
come. On this branch that is handled: `SAVE_TS`'s no-data-after-1s guard refuses
with Report R and drains, and the dispatcher's `ACTIVATE_MQ` launders the
leftover status byte.

## The Pico is never told about a BREAK

The abort path, end to end:

```asm
0655  CD 9F 06   READ_STATUS: CALL $069F
0658  D2 AA 06                JP NC,$06AA      ; BREAK -> abort
065B  DB 0F                   IN A,($0F)
065D  C9                      RET

06AA  C1         POP BC
06AB  C3 61 1A   JP $1A61                      ; WF_NPH failure exit: A=$02, SCF, RET
```

and every caller launders that into `$2294: LD A,$09 / SCF / RET`, which reaches
the dispatcher at `$1BF3` as **Report J**.

**No write to `$0E` occurs anywhere on that path.** The EXROM contains exactly
one `OUT ($0E),A`, at `$229D`, and nothing between the BREAK detection and the
return to BASIC calls it. There are no `OUT (C),r` instructions in the EXROM at
all, so the port list is provably complete
([PROTOCOL_FROM_ROM.md](PROTOCOL_FROM_ROM.md)). **The Pico cannot learn about a
BREAK from the wire, because nothing is put on the wire.**

### What the Pico sees instead

It has just streamed a block and is waiting for the Z80 to continue. `LOAD_TS`'s
core-1 `WATCHDOG` (3 s) fires, clears the FIFOs, bounces the state machine and
BLINKs. So the Pico recovers — but `TSP.offset` / `TSP.tap_idx` are left wherever
the search had reached, so the tape is parked at an arbitrary block.

### Why the LOAD loop is unbounded

That is a Pico-side property, not a ROM one. `LOAD_TS` serves **one block per
call** and wraps at EOF with no memory of having completed a pass
(`src/TS/tspico_io.py`, the `TSP.offset >= TSP.totlen` resets). The Z80 drives
the loop: it compares the name itself, and asks again on a mismatch. Nothing on
either side counts laps, so a LOAD that can never match cycles forever.

Any fix has to be Pico-side. A ROM change could signal the break, but the ROM is
the part we do not control.

`LOAD_TS` now bounds it: a search ends after one full lap of the tape with
nothing accepted, answering status `0x07` → **Report 8, End of file**. One lap is
allowed on purpose — a program that legitimately needs to wrap cannot rewind,
because it does not speak TPI — but a second lap would only repeat the first. A
data-block request (`pre[0] == 0xFF`) means the Z80 accepted a header and ends
the search.

> `BLINK()` used to be called from `LOAD_TS`'s wrong-block-type branch. It blocks
> for ~1 second, inside a live transaction. `WF_NPH` tolerated it (19.9 s budget)
> so it never broke anything, but it throttled a mismatch search to roughly one
> block per second — most of why the loop felt like a hang rather than a fast
> spin. It was a visual debug aid, not a protocol step, and has been removed.
