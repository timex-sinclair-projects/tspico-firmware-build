# Proposed ZX Spectrum ROM patch: handshake on `$0F` at block boundaries

**Status:** **applied** — the result is committed as
[`ROMs/TSPICO-ZX48-V2.BIN`](../../ROMs/TSPICO-ZX48-V2.BIN) and wired into
[`flash/manifest.json`](../../flash/manifest.json) as slot 0. This document is
the record of what was changed and why.

**Target:** the TS-PICO's customised ZX Spectrum ROM — the 16K at flash
`0x000000` (slot 0 of `Pico-v15w.rom`), crc32 `029861D1`. **Not** for
`Spectrum nuevo LD.rom`; see §6.

**Size:** 29 bytes of new code into stock Sinclair filler, 8 bytes changed
in place at two call sites, plus a 41-byte boot banner (§4). Nothing moves,
no code is displaced.

**Pairs with:** the firmware `MQ_READY` assertions in `LOAD_ZX`,
`LOAD_ZX_C` and `SAVE_ZX` (branch `zx48-dual-port-migration`). Those are
no-ops for the unpatched ROM, so the firmware ships first and this ROM
follows — never the other way round.

---

## 1. The problem

ZX48 mode has no flow control at all. A census of every keyboard/port
access in the 16K:

| Pattern | Meaning | Occurrences |
|---|---|---|
| `OUT ($0E),A` | data port write | 7 |
| `IN A,($0E)` | data port read | 3 |
| **anything on `$0F`** | the status/ready port | **none** |

Synchronisation is entirely fixed `DJNZ` delays: `LD B,$FF / DJNZ`
(~1 ms) around each header byte, and 4- or 16-iteration delays inside the
byte loops. Two consequences:

- **A slow Pico corrupts silently.** `TS_IO_DUAL` uses `pull(noblock)`,
  so an empty TX FIFO drives the X register (0) onto the bus — the Z80
  reads `0x00` and carries on. The only detection is the block checksum
  at the end: `R Tape loading error`, with nothing to distinguish "Pico
  was late" from "bad tape image".
- **The ~1 ms after `'S'` is a guess, and too small.** Between the Z80's
  `OUT ($0E),'S'` and the Pico being ready to receive sit `ZX48_IO`'s
  FIFO poll, its dispatch, a `LOG()` call and a `_thread` spawn. One ms
  does not reliably cover that.

Meanwhile the mechanism to do this properly is already present and
unused: the PIO drops Y (`$0F` bit 6) to BUSY on **every** Z80 OUT
(issue #14 auto-busy), and MicroPython raises it with
`MQ.exec("mov(y, invert(null))")`. The 2068-side ROM has polled `$0F`
this way all along.

## 2. The patch

Poll `$0F` once per block, immediately after the `'L'` / `'S'` that opens
it. Byte cadence inside a block is unchanged — MicroPython cannot
re-assert READY every 43 µs, and it doesn't need to: TX FIFO depth paces
the stream, exactly as it does for `LOAD_TS`.

New code goes at `$3874`, in the stock Sinclair filler. `$3874-$3CFF` is
`$FF` in the genuine 48K ROM *and* in this one (Ricardo's `OUT ($FF),A`
hook occupies `$386E-$3873` immediately before it), and nothing in either
image references it.

```asm
; ---- $3874: wait for the Pico to raise READY on $0F -------------------
; Out: carry set = ready; carry clear = timed out (~3.8 s).
; Corrupts A, BC, D.
3874  16 04        LD D,$04            ; 4 x 65536 polls
3876  01 00 00     LD BC,$0000
3879  DB 0F        IN A,($0F)
387B  E6 40        AND $40             ; bit 6 = READY
387D  20 09        JR NZ,$3888
387F  0B           DEC BC
3880  78           LD A,B
3881  B1           OR C                ; also leaves carry clear
3882  20 F5        JR NZ,$3879
3884  15           DEC D
3885  20 EF        JR NZ,$3876
3887  C9           RET                 ; timeout, carry clear
3888  37           SCF
3889  C9           RET                 ; ready, carry set

; ---- $388A: the SAVE-side wrapper -------------------------------------
388A  CD 74 38     CALL $3874
388D  D8           RET C               ; ready -> back into SA-BYTES
388E  FB           EI                  ; we are inside the DI at $04C7
388F  CF 1A        RST 8 : DEFB $1A    ; Report R, Tape loading error
```

**Call sites — both replace a `LD B,$FF / DJNZ` delay, byte for byte:**

| Address | Before | After | Meaning |
|---|---|---|---|
| `$0563` (LOAD) | `06 FF 10 FE` | `CD 74 38 D0` | `CALL $3874` / `RET NC` |
| `$04CC` (SAVE) | `06 FF 10 FE` | `CD 8A 38 00` | `CALL $388A` / `NOP` |

In context:

```asm
055E  F3           DI                     04C6  F5           PUSH AF
055F  3E 4C        LD A,'L'               04C7  F3           DI
0561  D3 0E        OUT ($0E),A            04C8  3E 53        LD A,'S'
0563  CD 74 38     CALL $3874             04CA  D3 0E        OUT ($0E),A
0566  D0           RET NC                 04CC  CD 8A 38     CALL $388A
0567  DB 0E        IN A,($0E)   ; flag    04CF  00           NOP
0569  67           LD H,A                 04D0  7B           LD A,E
```

### Why the two error exits differ

- **LOAD**: `$055D` pushed `$053F` (SA/LD-RET) and nothing else, so
  `RET NC` lands there with carry clear — the ROM's own "load failed"
  exit. `$053F` re-enables interrupts and the caller reports
  `R Tape loading error`. Stack stays balanced.
- **SAVE**: `$04C6` pushed AF (the flag byte, popped later at `$04DE`),
  so a bare `RET` would consume that as a return address — the exact
  stack-balance trap that bit the V17 SAVE-prompt patch. `RST 8` sidesteps
  it: the error handler restores `SP` from `ERR_SP`. `EI` first, because
  we are inside the `DI` at `$04C7` and the error path must not run with
  interrupts off.

## 3. What this does and does not change

| | Before | After |
|---|---|---|
| Pico late answering `'L'`/`'S'` | reads/writes into the void, checksum fails | waits, up to ~3.8 s |
| Pico absent or hung | same, every time | `R Tape loading error` after ~3.8 s |
| Byte cadence inside a block | fixed delay | **unchanged** |
| SPACE / BREAK behaviour | — | **untouched** |
| VERIFY | — | **untouched** |
| Bytes moved | — | **none** |

The poll runs with interrupts disabled (the ROM's own `DI`), so a dead
Pico freezes the machine for the timeout before reporting. That matches
what the tape routines already do.

## 4. Labelling the ROM

The image is now self-identifying at boot. Ricardo's existing hook at `$386E`
(`OUT ($FF),A` before the copyright print) gets one further redirect, so the
boot line reads:

```
(c) 1982 Sinclair / TS-Pico ZX v2
```

31 characters, one screen line, no scroll. **Sinclair's own string is not
touched** — it stays at `$1539` exactly as it was; the boot simply prints a
different message table:

```asm
3870  CD 91 38     CALL $3891       ; was CALL $0C0A (PO-MSG) directly
...
3891  11 98 38     LD DE,$3898      ; our message table
3894  AF           XOR A            ; message 0
3895  C3 0A 0C     JP $0C0A         ; PO-MSG prints it, then RETs to $3873
3898  A0           DEFB $A0         ; the $80-terminated placeholder
                                    ; PO-SEARCH skips when A = 0
3899  ...          "(c) 1982 Sinclair / TS-Pico ZX v2", last char OR $80
```

The boot code at `$1295` sets `A = 0` / `DE = $1538` before calling the hook;
we override both, so the stock path is unchanged for every other caller of
PO-MSG.

## 5. Checksums

```
16K ZX ROM   crc32  029861D1  ->  B3D40C73     (handshake + banner)
flash slot 0 crc32  A8E12A24  ->  1BE816C2     (32K slot: ROM + 16K of 00)
```

78 bytes differ from the shipped ROM: `$04CC-$04CF`, `$0563-$0566`,
`$3871-$3872`, `$3874-$38B7`.

## 6. Verifying a patched image

```bash
python3 - <<'PY'
import zlib
rom = open("ROMs/TSPICO-ZX48-V2.BIN","rb").read()        # the 16K image
def chk(a, hexs, what):
    want = bytes.fromhex(hexs.replace(" ",""))
    got  = rom[a:a+len(want)]
    print("%-4s $%04X %-34s %s" % ("OK" if got==want else "BAD", a, what,
          "" if got==want else "got " + got.hex(" ")))
chk(0x0563, "CD 74 38 D0", "LOAD call site")
chk(0x04CC, "CD 8A 38 00", "SAVE call site")
chk(0x3874, "16 04 01 00 00 DB 0F E6 40 20 09 0B 78 B1 20 F5 15 20 EF C9 37 C9", "WAIT_RDY")
chk(0x388A, "CD 74 38 D8 FB CF 1A", "SAVE_WAIT")
chk(0x0556, "08 CD 3F 05 21 3F 05 E5", "LD-BYTES head untouched")
chk(0x386E, "D3 FF CD 91 38 C9", "boot hook -> banner")
chk(0x1539, "7F 20 31 39 38 32 20 53 69 6E 63 6C 61 69 72", "Sinclair string untouched")
print("crc32 %08X (expect B3D40C73)" % zlib.crc32(rom))
PY
```

## 7. Do not apply this to `Spectrum nuevo LD.rom`

That image expects a different firmware. Its `LD-BYTES` polls `$0E` for
`0x40` before the first byte — the single-port continue flag, which the
dual-port firmware no longer sends (it lives on `$0F` now as the very Y
register this patch polls). Against current firmware it consumes data
bytes until one happens to equal `$40`. It also carries a one-byte
difference at `$057C` (`JR NC,-3` where the shipped ROM has `JR NC,+3`)
that spins on VERIFY.

If Ricardo's newer image is the one we want to carry forward, it needs
its `$40` poll removed (6 bytes at `$0563`, which is exactly where this
patch's `CALL`/`RET NC` goes) and the `$057C` displacement resolved
first. Worth doing as one revision rather than two.

## 8. Delivery

The ROM lives in flash slot 0, so it ships either in a rebuilt 512K image
(`tools/build-flash.py`, phase 3) or via `romupdate.tap` into a spare
slot. Note that `romupdate` writes whatever `.ROM` is mounted but does
**not** set the boot slot, and `tpi:boot` is a one-shot override that
`LOAD_CONFIG` resets to 1 on the next power-up — so a permanent change
means writing the real slot.
