# Proposed EXROM patch: check BREAK *before* the SAVE header is sent

**Status:** proposal, not applied. Written as a self-contained handoff — it
assumes no knowledge of the investigation that produced it.

**Target:** TS-PICO EXROM. Verified against `TSPICO-15w-exrom`
(md5 `639c62742fa3…`, the second 16K of `src/rom/TSPICO.ROM`). The affected
addresses are byte-identical in `TSPICO-11-exrom`, so the same patch applies to
both.

**Size:** 2 operand bytes changed, 7 bytes of new code into free space. Nothing
moves.

---

## 1. The symptom

The user types `SAVE "name"`, gets `Start tape, then press any key.`, and presses
**SPACE**. The 2068 reports `D BREAK` and the user reasonably concludes the SAVE
never happened.

It did happen, partly. **The Pico has already received a complete 21-byte SAVE
header block** and is sitting waiting for a data block that will never arrive.

On a real tape recorder this did not matter — the tape is not listening, and a
partial header is just noise on the medium. The TS-PICO is a stateful receiver,
so a truncated transaction leaves it holding state it has to time out of.

Two further consequences:

- **It is intermittent.** Whether the break is noticed at all depends on how long
  SPACE is held (see §3).
- **The Pico burns a recovery cycle.** Its SAVE handler waits ~1 s for the data
  block, then refuses and drains. Correct, but it should never have been asked.

## 2. Why it happens

The tape-prompt sequence, EXROM `$0868` (this region is stock TS2068 EXROM code —
byte-identical to `ROMs/GENUINE-2068-exrom.bin` from `$086B` on):

```asm
0868  CD 26 04    CALL $0426
086B  AF          XOR A                  ; message index 0
086C  11 89 3C    LD DE,$3C89            ; "Start tape, then press any key."
086F..0884                               ; print, via the HOME thunk at $0F99
0886  FD CB 02 EE SET 5,(IY+$02)         ; TV-FLAG: clear the lower screen
088A  CD AA 08    CALL $08AA             ; <-- (a) wait for a key
088D  DD E5       PUSH IX
088F  11 11 00    LD DE,$0011            ; 17 = header length
0892  AF          XOR A                  ; flag $00 = header block
0893  CD 68 00    CALL $0068             ; <-- (b) SEND THE HEADER TO THE PICO
0896  DD E1       POP IX
0898  06 32       LD B,$32
089A  76 10 FD    HALT : DJNZ            ; ~1 s pause between blocks
089D  DD 5E 0B    LD E,(IX+$0B)          ; data length
08A0  DD 56 0C    LD D,(IX+$0C)
08A3  3E FF       LD A,$FF               ; flag $FF = data block
08A5  DD E1       POP IX
08A7  C3 68 00    JP $0068               ; send the data block
```

and the key wait it calls:

```asm
08AA  F5 C5 D5    PUSH AF : PUSH BC : PUSH DE
08AD  01 40 9C    LD BC,$9C40
08B0  0B 79 B0    DEC BC : LD A,C : OR B
08B3  20 FB       JR NZ,$08B0            ; ~40000-iteration debounce
08B5  AF          XOR A
08B6  DB FE       IN A,($FE)             ; A=0 -> scan ALL keyboard rows at once
08B8  E6 1F       AND $1F
08BA  FE 1F       CP $1F
08BC  28 F7       JR Z,$08B5             ; loop while no key is down
08BE..08D8                               ; HOME thunk, restore, RET
```

**`$08AA` has no BREAK test.** It is a plain "is any key down" scan, so SPACE
satisfies it exactly like `A` or `ENTER` would, and the SAVE proceeds to (b).

The break is noticed later, on the way back out. `$0068` reaches the block sender
at `$1879`, which pushes `$00E5` as its own return address:

```asm
1882  21 E5 00    LD HL,$00E5
1885  E5          PUSH HL
```

`$00E5` is the TS2068 analogue of the Spectrum's `SA/LD-RET` at `$053F`, and it
is also stock:

```asm
00E5  F5          PUSH AF
00E6  3A 48 5C    LD A,($5C48)           ; BORDCR
00E9  E6 38       AND $38
00EB  0F 0F 0F    RRCA x3
00EE  D3 FE       OUT ($FE),A            ; restore the border
00F0  3E 7F       LD A,$7F
00F2  DB FE       IN A,($FE)             ; row $7F, bit 0 = SPACE
00F4  1F          RRA
00F5  FB          EI
00F6  38 02       JR C,$00FA             ; SPACE up -> carry on
00F8  CF 0C       RST 8 : DEFB $0C       ; <- Report D BREAK.  SPACE ALONE.
00FA  F1 C9       POP AF : RET
```

So the real order is **prompt → keypress → header sent → break noticed**. The
header is sent *because* the key was pressed.

> Note this is a check on **SPACE alone**, not CAPS SHIFT + SPACE. The TS-PICO's
> own break guard at `$069F` — which protects the Pico ready-wait, and is *not*
> stock — requires both keys. Two different checks with different conditions; do
> not generalise either to the other.

## 3. Why it is intermittent

Between the keypress at `$08B6` and the re-test at `$00E5` sit the HOME thunk,
the pre-header, the whole header block, and **at least one ready-wait**. Each
ready-wait (`WF_NPH`, `$1A54`) costs **≥88 ms even when the Pico answers
immediately**, because the status read goes through a debounced keyboard scan —
`$1A54 → $0655 → $069F → $0856 → 10× $07F6`. See
[`PROTOCOL_FROM_ROM.md`](PROTOCOL_FROM_ROM.md); `python3 tools/wf_nph_timing.py`
recomputes it from the instruction stream.

A typical keypress lasts 80–150 ms. So a quick tap of SPACE can easily be
released before `$00E5` looks, and the SAVE completes normally. On stock hardware
there is no Pico round-trip in that gap, which is why an emulator running the
genuine ROM aborts reliably and a TS-PICO may not.

*(This part is inference from the instruction timing, not read off a bus trace.
It predicts that on real hardware, tapping SPACE and holding SPACE give different
outcomes. Worth confirming, but the patch below is correct either way — it makes
the check immediate, so the question stops mattering.)*

## 4. The patch

Run the existing break test immediately after the key is detected, before
anything is sent. No new logic — it reuses `$00E5`, the same routine the tape
path already returns through, so the user still just sees the familiar
`D BREAK`.

**Change one call site:**

| Address | Before | After |
|---|---|---|
| `$088A` | `CD AA 08` (`CALL $08AA`) | `CD AE 22` (`CALL $22AE`) |

**Add, at `$22AE`:**

```asm
22AE  CD AA 08    CALL $08AA      ; the stock any-key wait, unchanged
22B1  CD E5 00    CALL $00E5      ; stock SPACE test -> Report D if held
22B4  C9          RET
```

Byte patch: `$088B` `AA`→`AE`, `$088C` `08`→`22`, and 7 bytes written at
`$22AE`.

### Why this is safe

- **`$08AA` has exactly one caller** — `$088A`. Verified by scanning the whole
  16K for `CALL`/`JP $08AA`. Patching the call site cannot affect anything else.
- **`$00E5` is a normal subroutine** (`PUSH AF … POP AF / RET`), so `CALL`ing it
  is fine. Today it is only ever reached as a pushed return address (`LD HL,$00E5`
  at `$0104`, `$1873`, `$1882`, `$1977`), but nothing about it depends on that.
- **`RST 8` from inside a `CALL` is fine** — the error path unwinds through
  `ERR_SP`, as it already does from every other `RST 8` site.
- **`$22AE` is free.** The EXROM has **7506 contiguous bytes of `$FF` from
  `$22AE` to the end**, and `MEMORY_MAP.md` already nominates `$22AE`+ as the
  place for new code because nothing needs to move.
- **Registers are preserved.** `$08AA` saves AF/BC/DE and `$00E5` saves AF, so
  the new stub is transparent to the caller.

### Behaviour change to be aware of

SPACE stops working as "any key" at the SAVE prompt — it becomes an abort. That
matches Spectrum convention (SPACE *is* BREAK during tape operations) and matches
what users already expect from the current behaviour, but it is a real change: a
user who habitually taps SPACE to start a save will now have to press something
else.

If that is unwanted, the alternative is to make the wait ignore SPACE
specifically (accept any key *except* SPACE, and treat SPACE as the abort). That
needs a modified copy of `$08AA` rather than a 3-instruction stub, and it changes
stock code. The patch above was chosen because it is smaller and reuses existing,
already-trusted semantics.

## 5. It has been built and checked

The patch was applied to `TSPICO-15w-exrom` and the result inspected. It is a
clean **9-byte delta** — nothing else moves:

```
changed bytes: 0x88b 0x88c 0x22ae 0x22af 0x22b0 0x22b1 0x22b2 0x22b3 0x22b4
crc32  before: cacf18c5      after: 6ce2b99a
```

and the patched sequence disassembles as intended:

```asm
0886  set 5,(iy+002h)
088a  call 022aeh        ; <- was call 008aah
088d  push ix
088f  ld de,00011h
0892  xor a
0893  call 00068h        ; header still sent here, but only if we get past 22ae

22ae  call 008aah        ; stock any-key wait
22b1  call 000e5h        ; stock SPACE test -> Report D if held
22b4  ret
```

The patched image was **not committed** — cutting a ROM is Gustavo's call, and
the repo's shipped images are checked by crc32 (`tools/romdiff.py`). The numbers
above are here so a rebuild can be confirmed byte-for-byte against them.

## 6. Verifying a patched image

```bash
python3 - <<'PY'
rom = open("ROMs/TSPICO-15w-exrom","rb").read()      # the patched image
ok = True
def chk(addr, hexs, what):
    global ok
    want = bytes(int(x,16) for x in hexs.split())
    got  = rom[addr:addr+len(want)]
    good = got == want; ok &= good
    print("%-4s $%04X %-34s %s" % ("OK" if good else "BAD", addr, what,
          "" if good else "got " + " ".join("%02X"%b for b in got)))
chk(0x088A, "CD AE 22",              "call site retargeted")
chk(0x22AE, "CD AA 08 CD E5 00 C9",  "new stub")
chk(0x08AA, "F5 C5 D5 01 40 9C",     "key wait untouched")
chk(0x00E5, "F5 3A 48 5C E6 38",     "break exit untouched")
# nothing else may have moved
base = open("ROMs/TSPICO-15w-exrom.orig","rb").read()
diff = [i for i in range(len(base)) if base[i] != rom[i]]
print("changed bytes:", [hex(i) for i in diff])
print("EXPECTED     : ['0x88b', '0x88c', '0x22ae'..'0x22b4']")
print("\n" + ("PASS" if ok else "FAIL"))
PY
```

`tools/romdiff.py` crc32-checks every shipped image on each run and will flag the
new EXROM until its expected crc32 is updated — that is the intended prompt to
record the new version.

## 7. Delivery

The firmware already ships a ROM-patching path: `SAVE "tpi:rompatch"` stages
`/assets/rompatch.tap` and the user runs `LOAD ""` to apply it
(`SD card/help/rompatch.txt`). A revised EXROM can go out that way, or bundled in
the normal release.

**No firmware change is required for this patch, and no version pairing problem
exists** — a patched ROM and current firmware work together, and so do an
unpatched ROM and current firmware. The patch only *removes* a transaction that
should never have started; it does not add or alter any wire protocol.

## 8. Related, and deliberately NOT part of this patch

There is a second, larger question: when a user BREAKs out of a **LOAD**, the
Pico is never told. The abort path (`$0655 → $06AA → $1A61`) writes nothing, and
the entire EXROM contains **exactly one `OUT ($0E),A`** (at `$229D`) and **exactly
one `IN A,($0F)`** (at `$065B`), with no `OUT (C),r` anywhere — so the port list
is provably complete and there is no signal to be had.

If that ever needs fixing in ROM, the channel is already available and unused:
the Pico's PIO samples **9 bits** on every Z80 OUT, putting A0 in bit 8 of the
value it queues, so **`OUT ($0F),A` is an out-of-band control write that cannot
be confused with data**. Nothing live uses it — the three `OUT ($0F),A` sites at
`$2020`, `$2023`, `$2236` are unreachable (`BREAK_KEY` ends with `RET` at
`$201D`; what follows is an orphaned stub that looks like an abandoned attempt at
exactly this idea, then `JP $2027` / `JP $202A` self-loops).

It is not proposed here for two reasons. The Pico-side firmware now bounds the
LOAD search itself — it stops after one full pass of the tape and answers
`End of file` — so the runaway loop that made BREAK necessary is gone. And a
signalling ROM would need firmware shipped *first*: current firmware reads the
pre-header with `pre[i] = MQ.get()` **unmasked** into a `bytearray`, so a 9-bit
value ≥ 256 arriving in that window would raise and drop the Pico to a REPL.
Firmware first, then ROM, if it is ever wanted.
